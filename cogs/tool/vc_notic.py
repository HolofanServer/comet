"""
VC入室通知システム
誰かがボイスチャンネルに参加したら特定のユーザーをメンション
"""

# import time
# from collections import defaultdict

# import discord
from discord.ext import commands

from utils.logging import setup_logging

logger = setup_logging()


class VCNotification(commands.Cog):
    """VC入室通知システム"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    #     self.mention_user_id = 1355706337480278207
    #     self.excluded_vc_ids = {
    #         1207357253980651520,
    #         1093229787620847616,
    #         1408442320600436908,
    #         1147214899840294992
    #     }

    #     self.notification_channel_id = None

    #     self.last_notification_time = defaultdict(float)
    #     self.cooldown_seconds = 5

    # @commands.Cog.listener()
    # async def on_voice_state_update(
    #     self,
    #     member: discord.Member,
    #     before: discord.VoiceState,
    #     after: discord.VoiceState
    # ):
    #     if member.bot:
    #         return

    #     if before.channel is None and after.channel is not None:
    #         vc = after.channel

    #         if vc.id in self.excluded_vc_ids:
    #             logger.debug(f"⏭️ Excluded VC: {vc.name} ({vc.id})")
    #             return

    #         is_from_excluded_vc = before.channel and before.channel.id in self.excluded_vc_ids

    #         if not is_from_excluded_vc:
    #             current_time = time.time()
    #             last_time = self.last_notification_time[member.id]
    #             if current_time - last_time < self.cooldown_seconds:
    #                 logger.debug(f"⏭️ Cooldown: {member.display_name} (last notification {current_time - last_time:.1f}s ago)")
    #                 return
    #         else:
    #             logger.debug(f"✅ From excluded VC, skipping cooldown for {member.display_name}")
    #             current_time = time.time()

    #         notification_channel = await self._get_notification_channel(vc)

    #         if not notification_channel:
    #             logger.warning(f"⚠️ Notification channel not found for VC: {vc.name}")
    #             return

    #         mention_user = self.bot.get_user(self.mention_user_id)
    #         if not mention_user:
    #             logger.warning(f"⚠️ Mention user not found: {self.mention_user_id}")
    #             return

    #         try:
    #             await notification_channel.send(
    #                 f"{mention_user.mention} 🔔 {member.display_name} が {vc.mention} に参加しました"
    #             )
    #             self.last_notification_time[member.id] = current_time
    #             logger.info(f"📢 VC notification sent: {member.display_name} joined {vc.name}")
    #         except discord.Forbidden:
    #             logger.error(f"❌ Permission error: Cannot send message to {notification_channel.name}")
    #         except Exception as e:
    #             logger.error(f"❌ Error sending VC notification: {e}")

    # async def _get_notification_channel(self, vc: discord.VoiceChannel) -> discord.TextChannel | None:
    #     if self.notification_channel_id:
    #         return self.bot.get_channel(self.notification_channel_id)

    #     if vc.category:
    #         for channel in vc.category.text_channels:
    #             permissions = channel.permissions_for(vc.guild.me)
    #             if permissions.send_messages:
    #                 return channel

    #     for channel in vc.guild.text_channels:
    #         permissions = channel.permissions_for(vc.guild.me)
    #         if permissions.send_messages:
    #             return channel

    #     return None


async def setup(bot: commands.Bot):
    await bot.add_cog(VCNotification(bot))
