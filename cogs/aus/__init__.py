"""
AUS (Art Unauthorized-repost Shield) システム
無断転載ファンアート検出・絵師認証システム
"""

from discord.ext import commands

from utils.logging import setup_logging

from .database import DatabaseManager

logger = setup_logging()


async def setup(bot: commands.Bot):
    """AUS (Art Unauthorized-repost Shield) システムのセットアップ"""
    # データベース初期化（既存のPostgreSQLに接続）
    db = DatabaseManager()
    await db.initialize()

    # BotにDBインスタンスを保存（他のCogsからアクセス可能に）
    bot.db = db

    # Cogsロード
    await bot.load_extension('cogs.aus.image_detection')
    await bot.load_extension('cogs.aus.artist_verification')
    await bot.load_extension('cogs.aus.moderation')

    # Persistent Views登録（Bot起動時に呼び出される）
    from .views.notification_views import NoSourceNotificationView, WebSearchResultView
    from .views.verification_views import VerificationButtons

    bot.add_view(NoSourceNotificationView(0, "", ""))
    bot.add_view(VerificationButtons(0))
    bot.add_view(WebSearchResultView(0, []))

    logger.info("✅ AUS System loaded successfully")
    logger.info("✅ AUS Persistent Views registered")
