import discord
from discord.ext import commands
from datetime import datetime

from config.setting import get_settings

from utils.logging import setup_logging

logger = setup_logging("D")
settings = get_settings()

main_guild_id = int(settings.admin_main_guild_id)


class NoticeModCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.mod_role_names = "moderator"
        self.hensyu_role_name = "編集部"
        self.channel_names = {
            main_guild_id: ["モデレーター", "main"],
        }
        self.channel_ids = {}

    async def setup_channels(self):
        for guild_id, channel_names in self.channel_names.items():
            guild = self.bot.get_guild(guild_id)
            if guild:
                for channel_name in channel_names:
                    channel = discord.utils.get(guild.channels, name=channel_name)
                    if channel:
                        self.channel_ids[guild_id] = channel.id
                        logger.info(f"Channel ID set for {guild.name}: {channel_name} ({channel.id})")
                        break
                if guild_id not in self.channel_ids:
                    logger.warning(f"No matching channels found in guild {guild.name}. Tried: {', '.join(channel_names)}")
            else:
                logger.warning(f"Guild {guild_id} not found")

    @commands.Cog.listener()
    async def on_ready(self):
        """Bot起動時にチャンネルIDを設定"""
        await self.setup_channels()
        logger.info("Channel IDs setup complete")

    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        logger.debug(f"on_member_update: {before.display_name} -> {after.display_name}")
        if before.roles == after.roles:
            logger.debug("Roles are the same")
            return

        added_roles = set(after.roles) - set(before.roles)
        removed_roles = set(before.roles) - set(after.roles)

        mod_role_names = [role.name for role in added_roles.union(removed_roles)]
        if not any(role_name in [self.mod_role_names, self.hensyu_role_name] for role_name in mod_role_names):
            logger.debug(f"Target roles not found: {mod_role_names}")
            return
        
        if after.guild.id != main_guild_id:
            logger.debug(f"Guild not supported: {after.guild.id}")
            return

        channel_id = self.channel_ids.get(after.guild.id)
        if not channel_id:
            logger.warning(f"Channel ID not found for guild: {after.guild.id}")
            return

        guild = self.bot.get_guild(after.guild.id)
        if not guild:
            logger.error(f"Bot is not in guild {after.guild.name} ({after.guild.id})")
            return

        channel = guild.get_channel(channel_id)
        if not channel:
            logger.error(f"Channel {channel_id} not found in guild {guild.name}. Available channels: {[ch.name for ch in guild.channels]}")
            try:
                channel = await self.bot.fetch_channel(channel_id)
            except discord.NotFound:
                logger.error(f"Channel {channel_id} not found")
                return
            except discord.Forbidden:
                logger.error(f"Bot doesn't have permission to access channel {channel_id} in guild {guild.name}")
                bot_member = guild.get_member(self.bot.user.id)
                if bot_member:
                    logger.error(f"Bot roles in guild: {[role.name for role in bot_member.roles]}")
                return
            except Exception as e:
                logger.error(f"Error fetching channel {channel_id}: {str(e)}")
                return

        permissions = channel.permissions_for(after.guild.me)
        logger.debug(f"Channel permissions in {after.guild.name} - {channel.name}:")
        logger.debug(f"view_channel: {permissions.view_channel}")
        logger.debug(f"send_messages: {permissions.send_messages}")
        logger.debug(f"embed_links: {permissions.embed_links}")
        logger.debug(f"read_message_history: {permissions.read_message_history}")
        logger.debug(f"send_messages_in_threads: {permissions.send_messages_in_threads}")

        if not permissions.view_channel:
            logger.error(f"Bot doesn't have permission to view channel {channel.name} ({channel_id})")
            return
        if not permissions.send_messages:
            logger.error(f"Bot doesn't have permission to send messages in channel {channel.name} ({channel_id})")
            return
        if not permissions.embed_links:
            logger.error(f"Bot doesn't have permission to embed links in channel {channel.name} ({channel_id})")
            return
        if not permissions.send_messages_in_threads:
            logger.error(f"Bot doesn't have permission to send messages in threads in channel {channel.name} ({channel_id})")
            return
        
        action = "追加" if added_roles else "削除"
        target_roles = added_roles if action == "追加" else removed_roles
        role_names = [role.name for role in target_roles]
        
        if action == "追加":
            logger.info(f"{', '.join(role_names)}が{after.display_name}に追加されました。")
            embed = discord.Embed(
                title="⚠️重要通知⚠️",
                description=f"{', '.join(role_names)}が{after.display_name}に{action}されました。",
                timestamp=datetime.now(),
                color=discord.Color.blue()
            )
        else:
            logger.info(f"{', '.join(role_names)}が{after.display_name}から削除されました。")
            embed = discord.Embed(
                title="⚠️重要通知⚠️",
                description=f"{', '.join(role_names)}が{after.display_name}から{action}されました。",
                timestamp=datetime.now(),
                color=discord.Color.red()
            )

        embed.add_field(name="ユーザー情報", value=f"{after.mention} ({after.display_name})", inline=True)
        embed.add_field(name="ユーザーID", value=after.id, inline=False)
        embed.add_field(name="アカウント作成日", value=f"<t:{int(after.created_at.timestamp())}:F>", inline=True)
        embed.add_field(name="サーバー参加日", value=f"<t:{int(after.joined_at.timestamp())}:F>", inline=False)

        embed.add_field(name="操作", value=f"ロール{action}: {', '.join(role_names)}", inline=False)

        try:
            async for entry in after.guild.audit_logs(limit=1, action=discord.AuditLogAction.member_role_update):
                if entry.target.id == after.id:
                    logger.debug(f"Entry target ID: {entry.target.id}")
                    logger.debug(f"Entry user ID: {entry.user.id}")
                    logger.debug(f"Entry user display name: {entry.user.display_name}")
                    logger.debug(f"Entry user mention: {entry.user.mention}")
                    embed.add_field(name="変更者", value=f"{entry.user.mention} ({entry.user.display_name})", inline=False)
                    embed.add_field(name="変更者ID", value=entry.user.id, inline=False)
                break
        except discord.Forbidden:
            logger.error(f"Bot doesn't have permission to view audit logs in guild {after.guild.name}")
        except Exception as e:
            logger.error(f"Error fetching audit logs: {str(e)}")

        mod_role = discord.utils.get(after.guild.roles, name=self.mod_role_names)
        
        logger.debug(f"logging: {entry.user.display_name} {action} {', '.join(role_names)} from {after.display_name}")
        
        mention_roles = []
        if mod_role:
            mention_roles.append(mod_role.mention)
        
        if mention_roles:
            mention_message = " ".join(mention_roles)
        else:
            mention_message = "No target roles found"
            logger.warning(f"No target roles found in guild: {after.guild.id}")

        try:
            await channel.send(content=mention_message, embed=embed)
            logger.info(f"Notice sent to {channel.name} in {after.guild.name}")
        except discord.Forbidden:
            logger.error(f"Bot doesn't have permission to send messages in {channel.name} in {after.guild.name}")
        except discord.HTTPException as e:
            logger.error(f"Failed to send message: {str(e)}")


async def setup(bot):
    await bot.add_cog(NoticeModCog(bot))
