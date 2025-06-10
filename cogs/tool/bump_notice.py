import discord
from discord.ext import commands
import asyncio
from datetime import datetime, timedelta, timezone
from utils.db_manager import db
import httpx

from utils.logging import setup_logging
from utils.commands_help import is_owner, log_commands, is_guild

logger = setup_logging()

class CV2MessageSender:
    """
    CV2形式のコンテナメッセージを送信するユーティリティ
    """
    def __init__(self, bot):
        self.bot = bot
        self.base_url = "https://discord.com/api/v10"
        self.client = httpx.AsyncClient()

    async def send_bump_container(
        self, channel_id: int, text: str, timestamp_text: str, mention: str = None
    ) -> dict:
        """
        bump通知用CV2コンテナメッセージを送信します。
        Args:
            channel_id (int): 送信先チャンネルID
            text (str): 本文
            timestamp_text (str): タイムスタンプ表記
            mention (str): メンション文字列（任意）
        Returns:
            dict: Discord APIレスポンス
        """
        accent_color = 5763719
        container_components = []
        if mention:
            container_components.append({"type": 10, "content": mention})
        container_components.append({"type": 10, "content": text})
        container_components.append({"type": 10, "content": timestamp_text})
        container = {
            "type": 17,
            "accent_color": accent_color,
            "components": container_components
        }
        payload = {"components": [container]}
        endpoint = f"{self.base_url}/channels/{channel_id}/messages"
        headers = {"Authorization": f"Bot {self.bot.http.token}"}
        resp = await self.client.post(endpoint, headers=headers, json=payload)
        return resp.json()

class BumpNoticeCog(commands.Cog):
    """
    指定BOTのbump embed検知→CV2形式コンテナ送信→2時間後削除/再送信を管理します。
    深夜(JST 0-7時)はメンションを行いません。
    """
    BUMP_EMBED_KEYWORD = "表示順をアップしたよ👍"
    BUMP_INTERVAL = timedelta(hours=2)
    JST = timezone(timedelta(hours=9))
    NIGHT_START = 0
    NIGHT_END = 7

    def __init__(self, bot):
        self.bot = bot
        self.cv2_sender = CV2MessageSender(bot)
        self.active_task = None
        self.last_bump_message_id = None
        self.last_bump_sent_at = None
        self.channel = None

    @commands.hybrid_group(name="bumpnotice", description="bump通知設定コマンド（管理者専用）")
    @is_owner()
    @log_commands()
    @is_guild()
    async def bumpnotice(self, ctx):
        """bump通知の設定を行います。"""
        if ctx.invoked_subcommand is None:
            await ctx.send("サブコマンドを指定してください。/bumpnotice set_channel など")

    @bumpnotice.command(name="set_channel", description="bump通知を送るチャンネルを設定します")
    async def set_channel(self, ctx, channel: discord.TextChannel):
        await db.set_bump_notice_settings(ctx.guild.id, channel_id=channel.id)
        await ctx.send(f"bump通知チャンネルを {channel.mention} に設定しました。")

    @bumpnotice.command(name="set_bot", description="bump通知の対象BOTのIDを設定します")
    async def set_bot(self, ctx, bot_id: discord.User):
        try:
            # 先にインタラクションに応答
            await ctx.defer(ephemeral=True)
            
            # DB設定を保存
            await db.set_bump_notice_settings(ctx.guild.id, bot_id=bot_id.id)
            
            # 遅延応答で結果を送信
            await ctx.send(f"bump通知対象BOTのIDを <@{bot_id.id}> に設定しました。", ephemeral=True)
        except Exception as e:
            await ctx.send(f"設定中にエラーが発生しました: {e}", ephemeral=True)

    @bumpnotice.command(name="set_role", description="bump通知時にメンションするロールを設定します")
    async def set_role(self, ctx, role: discord.Role):
        try:
            # 先にインタラクションに応答
            await ctx.defer(ephemeral=True)
            
            # DB設定を保存
            await db.set_bump_notice_settings(ctx.guild.id, role_id=role.id)
            
            # 遅延応答で結果を送信
            await ctx.send(f"bump通知時にメンションするロールを {role.mention} に設定しました。", ephemeral=True)
        except Exception as e:
            await ctx.send(f"設定中にエラーが発生しました: {e}", ephemeral=True)

    @bumpnotice.command(name="show", description="現在のbump通知設定を表示します")
    async def show_settings(self, ctx):
        settings = await db.get_bump_notice_settings(ctx.guild.id)
        if not settings:
            await ctx.send("設定がありません。")
            return

        desc = ""
        if settings.get("channel_id"):
            channel = ctx.guild.get_channel(settings["channel_id"])
            desc += f"通知チャンネル: {channel.mention if channel else '不明'}\n"
        if settings.get("bot_id"):
            desc += f"対象BOT: <@{settings['bot_id']}>\n"
        if settings.get("role_id"):
            role = ctx.guild.get_role(settings["role_id"])
            desc += f"メンションロール: {role.mention if role else '不明'}"
        
        await ctx.send(f"現在の設定:\n{desc}")

    @bumpnotice.command(name="test", description="テスト用のbumpメッセージを送信します")
    @is_owner()
    @log_commands()
    @is_guild()
    async def test_bump(self, ctx):

        embed = discord.Embed(
            title="DISBOARD: The Public Server List",
            description=f"{ctx.guild.name}の表示順をアップしたよ👍",
            color=0x2ecc71
        )
        embed.set_footer(text="Server bumped")
        embed.set_image(url="https://images.frwi.net/data/images/3908cc04-e168-4801-8783-f5799fa92c57.png")

        await ctx.send(embed=embed)

    @commands.Cog.listener()
    async def on_message(self, message):
        if not message.guild:
            return
        logger.info(f"メッセージ受信: {message.author.name} ({message.author.id}) - {message.content[:50]}")

        settings = await db.get_bump_notice_settings(message.guild.id)
        if not settings or not settings.get('bot_id') or not settings.get('channel_id'):
            logger.info("設定が見つかりません。")
            return

        if message.author.id != settings['bot_id']:
            logger.info("対象BOTではありません。")
            return

        if not message.embeds:
            logger.info("embedがありません。")
            return

        for embed in message.embeds:
            logger.info(f"embed受信: {embed.title} - {embed.description}")
            if embed.description and self.BUMP_EMBED_KEYWORD in embed.description:
                logger.info(f"Bump検知: サーバー {message.guild.name} (ID: {message.guild.id})")
                self.channel = message.guild.get_channel(settings['channel_id'])
                if not self.channel:
                    logger.info("通知チャンネルが見つかりません。")
                    return
                self.role_id = settings.get('role_id')
                await self.start_bump_timer(message.guild)
                logger.info("bumpタイマー開始: サーバー {message.guild.name}")
                break
    
    async def start_bump_timer(self, guild):
        if self.active_task and not self.active_task.done():
            self.active_task.cancel()
        self.active_task = asyncio.create_task(self.bump_timer_loop(guild))

    async def bump_timer_loop(self, guild):
        logger.info(f"bumpタイマー開始: サーバー {guild.name}")

        if not self.channel:
            logger.error(f"通知チャンネルが見つかりません: {guild.name}")
            return

        # 最初の通知
        now = datetime.now(self.JST)
        next_bump = now + self.BUMP_INTERVAL
        next_bump_ts = int(next_bump.timestamp())

        # 最初の通知embed
        embed_first = discord.Embed(
            title="Bumpを確認しました",
            description=f"<t:{next_bump_ts}:R> に再度bumpが可能になります\n<t:{next_bump_ts}>"
        )
        embed_first.set_image(url="https://images.frwi.net/data/images/3908cc04-e168-4801-8783-f5799fa92c57.png")
        
        # 最初のメッセージを送信
        self.last_bump_message = await self.channel.send(embed=embed_first, silent=True)

        # 2時間待機
        try:
            await asyncio.sleep(self.BUMP_INTERVAL.total_seconds())
        except asyncio.CancelledError:
            return

        # 前回のメッセージを削除
        try:
            await self.last_bump_message.delete()
        except Exception:
            pass

        # 2時間後の通知
        now = datetime.now(self.JST)
        new_embed = discord.Embed(
            title="Bumpが可能になりました!", 
            description="</bump:947088344167366698>を使おう!"
        )
        new_embed.set_image(url="https://images.frwi.net/data/images/3908cc04-e168-4801-8783-f5799fa92c57.png")

        # 深夜帯判定
        if self.NIGHT_START <= now.hour < self.NIGHT_END:
            mention = "深夜のためメンションは行われません。"
            await self.channel.send(mention, embed=new_embed, silent=True)
        else:
            mention = f"<@&{self.role_id}>" if self.role_id else ""
            await self.channel.send(mention, embed=new_embed)

async def setup(bot):
    await db.initialize()
    await bot.add_cog(BumpNoticeCog(bot))
