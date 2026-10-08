"""HFS 閉鎖時の閲覧制限。実行を明示するまでは読み取りのみ。"""

import asyncio
import json
import os
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import discord
from discord import app_commands
from discord.ext import commands

from utils.logging import logger

GUILD_ID = 1092138492173242430
EXCLUDED_CHANNEL_ID = 1556917166434164736
PROTECTED_ROLE_IDS = {1093678152317935696, 1093387737840746646, 1092988310378512434}
# Staff を表示せず管理者ロールを使っている、依頼者自身の運営アカウント。
EXEMPT_MEMBER_IDS = {1092294459317833748}
BACKUP_DIRECTORY = Path("data/server_closure")
OverwriteMap = dict[tuple[int, int], discord.PermissionOverwrite]


def _overwrites(channel: discord.abc.GuildChannel) -> OverwriteMap:
    # キャッシュに存在しないロール・メンバーの Object も取りこぼさない。
    return {
        (
            (
                0
                if isinstance(target, discord.Role)
                or getattr(target, "type", None) is discord.Role
                else 1
            ),
            target.id,
        ): overwrite
        for target, overwrite in channel.overwrites.items()
    }


def _serialize(overwrites: OverwriteMap) -> list[dict]:
    return [
        {
            "id": str(target_id),
            "type": kind,
            "allow": str(overwrite.pair()[0].value),
            "deny": str(overwrite.pair()[1].value),
        }
        for (kind, target_id), overwrite in sorted(overwrites.items())
    ]


def _edit_overwrites(overwrites: OverwriteMap) -> dict:
    return {
        discord.Object(
            id=target_id, type=discord.Role if kind == 0 else discord.User
        ): ow
        for (kind, target_id), ow in overwrites.items()
    }


def _can_view(guild, roles, role_ids, member_id, overwrites):
    """VIEW_CHANNEL のみを Discord の上書き優先順位で評価する。"""
    permissions = roles[guild.id].permissions.value
    for role_id in role_ids:
        permissions |= roles[role_id].permissions.value
    if member_id == guild.owner_id or permissions & 8:
        return True
    visible = bool(permissions & 1024)
    everyone = overwrites.get((0, guild.id))
    if everyone is not None and everyone.view_channel is not None:
        visible = everyone.view_channel
    role_values = [
        overwrites[(0, role_id)].view_channel
        for role_id in role_ids
        if role_id != guild.id and (0, role_id) in overwrites
    ]
    if False in role_values:
        visible = False
    if True in role_values:
        visible = True
    member = overwrites.get((1, member_id))
    if member is not None and member.view_channel is not None:
        visible = member.view_channel
    return visible


@dataclass
class Snapshot:
    guild: discord.Guild
    channels: list
    members: dict[int, discord.Member]


@dataclass
class Change:
    channel: discord.abc.GuildChannel
    before: OverwriteMap
    after: OverwriteMap


@dataclass
class Plan:
    snapshot: Snapshot
    protected: set[int]
    changes: list[Change]
    blockers: list[str]


async def _snapshot(bot: commands.Bot) -> Snapshot:
    # 独立した Guild を取得し、roles / owner と Member.roles を同じ世代で評価。
    # Gateway のメンバーキャッシュが欠けていても個人許可を漏らさない。
    guild = await bot.fetch_guild(GUILD_ID)
    channels = await guild.fetch_channels()
    members = {member.id: member async for member in guild.fetch_members(limit=None)}
    return Snapshot(guild, channels, members)


def _plan(snapshot: Snapshot, bot_id: int) -> Plan:
    guild, channels, members = snapshot.guild, snapshot.channels, snapshot.members
    roles = {role.id: role for role in guild.roles}
    if guild.id != GUILD_ID or not PROTECTED_ROLE_IDS <= roles.keys():
        raise ValueError(
            "対象サーバーまたは Staff / bot / bot2 ロールを確認できません。"
        )
    excluded = next((c for c in channels if c.id == EXCLUDED_CHANNEL_ID), None)
    if excluded is None or not isinstance(excluded, discord.TextChannel):
        raise ValueError("例外テキストチャンネルを確認できません。変更は開始しません。")
    if bot_id not in members:
        raise ValueError("Bot のサーバーメンバー情報を確認できません。")

    protected = PROTECTED_ROLE_IDS | {
        role.id for role in roles.values() if role.is_bot_managed()
    }
    protected_members = {
        member.id
        for member in members.values()
        if member.id in {guild.owner_id, bot_id, *EXEMPT_MEMBER_IDS}
        or member.bot
        or any(role.id in protected for role in member.roles)
    }
    blockers = []
    for member in members.values():
        if member.id not in protected_members and (
            roles[guild.id].permissions.administrator
            or any(role.permissions.administrator for role in member.roles)
        ):
            blockers.append(f"保護対象外の管理者: {member.id}")

    changes = []
    # 親カテゴリを変えると同期済みの例外にも伝播するため、親は保護する。
    excluded_ids = {excluded.id, excluded.category_id}
    for channel in sorted(
        channels, key=lambda c: (isinstance(c, discord.CategoryChannel), c.id)
    ):
        if channel.id in excluded_ids:
            continue
        before = _overwrites(channel)
        after = {
            key: discord.PermissionOverwrite.from_pair(*ow.pair())
            for key, ow in before.items()
        }
        after.setdefault((0, guild.id), discord.PermissionOverwrite()).view_channel = (
            False
        )
        for (kind, target_id), overwrite in after.items():
            keep = target_id in (protected if kind == 0 else protected_members)
            if not keep and overwrite.view_channel is True:
                overwrite.view_channel = False

        # @everyone 拒否によって運営・Bot が失う既存の閲覧権限だけを補う。
        for role_id in protected:
            if _can_view(guild, roles, [role_id], None, before):
                after.setdefault(
                    (0, role_id), discord.PermissionOverwrite()
                ).view_channel = True
        for member_id in protected_members:
            role_ids = [role.id for role in members[member_id].roles]
            visible_before = _can_view(guild, roles, role_ids, member_id, before)
            if visible_before != _can_view(guild, roles, role_ids, member_id, after):
                # 他ロールの拒否を新しい保護ロール許可が上回る場合も補正し、
                # 以前見えなかったチャンネルへのアクセスを広げない。
                after.setdefault(
                    (1, member_id), discord.PermissionOverwrite()
                ).view_channel = visible_before

        if before != after:
            permissions = channel.permissions_for(members[bot_id])
            if not (permissions.manage_roles and permissions.manage_channels):
                blockers.append(f"Bot の権限不足: {channel.id}")
            changes.append(Change(channel, before, after))
    return Plan(snapshot, protected, changes, blockers)


def _save_backup(plan: Plan, actor_id: int) -> Path:
    BACKUP_DIRECTORY.mkdir(parents=True, exist_ok=True)
    path = BACKUP_DIRECTORY / f"{GUILD_ID}_{uuid4().hex}.json"
    data = {
        "version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "guild_id": str(GUILD_ID),
        "actor_id": str(actor_id),
        "excluded_channel_id": str(EXCLUDED_CHANNEL_ID),
        "protected_role_ids": sorted(map(str, plan.protected)),
        "roles": [
            {"id": str(r.id), "name": r.name, "permissions": str(r.permissions.value)}
            for r in plan.snapshot.guild.roles
        ],
        "channels": [
            {
                "id": str(c.id),
                "name": c.name,
                "type": c.type.value,
                "parent_id": str(c.category_id) if c.category_id else None,
                "permission_overwrites": _serialize(_overwrites(c)),
            }
            for c in plan.snapshot.channels
        ],
    }
    # 書き込み・同期が失敗した場合は Discord 上の変更を開始しない。
    with path.open("x", encoding="utf-8") as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2)
        stream.flush()
        os.fsync(stream.fileno())
    return path


def _verify(plan: Plan, latest: Snapshot, bot_id: int) -> None:
    remaining = _plan(latest, bot_id)
    if remaining.blockers or remaining.changes:
        raise ValueError(
            "適用後の検証で未閉鎖チャンネルまたは管理者の例外を検出しました。"
        )
    expected = {c.id: _overwrites(c) for c in plan.snapshot.channels}
    expected.update({change.channel.id: change.after for change in plan.changes})
    actual = {c.id: _overwrites(c) for c in latest.channels}
    if actual != expected:
        raise ValueError("適用後のチャンネル権限が計画と一致しません。")
    before_roles = {r.id: r.permissions.value for r in plan.snapshot.guild.roles}
    if before_roles != {r.id: r.permissions.value for r in latest.guild.roles}:
        raise ValueError("処理中にサーバーのロール構成・権限が変更されました。")


class ServerClose(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_command(
        name="server_close",
        description="HFS の閉鎖をプレビュー／実行（例外1チャンネル）",
    )
    @commands.guild_only()
    @commands.has_guild_permissions(administrator=True)
    @commands.bot_has_permissions(attach_files=True)
    @commands.max_concurrency(1, per=commands.BucketType.guild, wait=False)
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(execute="false: 確認のみ、true: バックアップ後に閲覧を制限")
    async def server_close(self, ctx: commands.Context, execute: bool = False) -> None:
        if ctx.guild is None or ctx.guild.id != GUILD_ID:
            await ctx.send(
                "このコマンドは対象の HFS サーバー専用です。", ephemeral=True
            )
            return
        if execute and ctx.interaction is None:
            await ctx.send(
                "権限バックアップを実行者だけに表示するため、"
                "実行は /server_close execute:true を使ってください。"
            )
            return
        await ctx.defer(ephemeral=True)
        completed = 0
        backup = None
        try:
            snapshot = await _snapshot(self.bot)
            # decorator に加え、現在の実行者の権限を REST の情報で再確認。
            actor = snapshot.members.get(ctx.author.id)
            if actor is None or not actor.guild_permissions.administrator:
                raise ValueError("実行者の管理者権限を確認できません。")
            plan = _plan(snapshot, self.bot.user.id)
            summary = (
                f"変更対象: {len(plan.changes)} チャンネル（カテゴリを含む）。\n"
                f"例外: <#{EXCLUDED_CHANNEL_ID}> の権限は変更しません。\n"
                "Staff / bot / bot2・Bot 固有ロールの既存の閲覧権限を維持します。\n"
                "所有者と指定済みの運営アカウントも対象外です。\n"
                "その他の @everyone・ロール・個人の閲覧許可を閉じます。"
            )
            if plan.blockers:
                await ctx.send(
                    summary
                    + "\n実行不可（変更なし）:\n"
                    + "\n".join(plan.blockers[:15]),
                    ephemeral=True,
                    allowed_mentions=discord.AllowedMentions.none(),
                )
                return
            if not execute:
                await ctx.send(
                    summary + "\nプレビューのみです。実行する場合は execute:true。",
                    ephemeral=True,
                    allowed_mentions=discord.AllowedMentions.none(),
                )
                return
            if not plan.changes:
                await ctx.send("変更対象はありません。", ephemeral=True)
                return
            backup = await asyncio.to_thread(_save_backup, plan, ctx.author.id)
            with closing(discord.File(backup, filename=backup.name)) as attachment:
                await ctx.send(
                    summary
                    + "\n変更前の権限バックアップを保存しました。閉鎖を開始します。",
                    file=attachment,
                    ephemeral=True,
                    allowed_mentions=discord.AllowedMentions.none(),
                )
            reason = f"HFS server_close by {ctx.author.id}; backup={backup.name}"
            for change in plan.changes:
                current = await snapshot.guild.fetch_channel(change.channel.id)
                if (
                    _overwrites(current) != change.before
                    or current.category_id != change.channel.category_id
                ):
                    raise ValueError(
                        f"処理中に権限・カテゴリが変更されました: {current.id}"
                    )
                await current.edit(
                    overwrites=_edit_overwrites(change.after), reason=reason
                )
                completed += 1
                logger.info(
                    "閉鎖権限適用: guild_id=%s channel_id=%s actor_id=%s",
                    GUILD_ID,
                    current.id,
                    ctx.author.id,
                )
            _verify(plan, await _snapshot(self.bot), self.bot.user.id)
        except (
            discord.HTTPException,
            discord.ClientException,
            OSError,
            ValueError,
            asyncio.TimeoutError,
        ) as error:
            logger.exception(
                "サーバー閉鎖未完了: guild_id=%s updated=%s", GUILD_ID, completed
            )
            await ctx.send(
                f"閉鎖は完了していません。更新成功: {completed} チャンネル。"
                "権限・同時変更・ログを確認してください。"
                + (f" {error}" if isinstance(error, ValueError) else "")
                + (
                    f" バックアップ: {backup.name}"
                    if backup
                    else " 変更前バックアップ未作成。"
                ),
                ephemeral=True,
            )
            return
        await ctx.send(
            f"{completed} チャンネルの閉鎖と権限検証が完了しました。"
            "例外チャンネルの権限は変更していません。",
            ephemeral=True,
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ServerClose(bot))
