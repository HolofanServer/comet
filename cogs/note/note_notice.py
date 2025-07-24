from discord.ext import commands, tasks
import feedparser
import requests
import datetime
from typing import Optional, Dict, Any
import discord
import asyncio
import re
from html import unescape

from utils.logging import setup_logging
from utils.commands_help import is_owner, log_commands, is_guild
from config.setting import get_settings
from utils.db_manager import db

logger = setup_logging()
settings = get_settings()

class NoteNotify(commands.Cog):
    """
    Note投稿通知機能
    
    note.com/hfs_discordの新規投稿をRSSで監視し、
    リッチなEmbed通知をDiscordに送信します。
    """
    
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.check_note_rss_onthehour.start()
        logger.info("Note通知機能を初期化しました")

    def cog_unload(self) -> None:
        """Cogのアンロード時にタスクを停止"""
        self.check_note_rss_onthehour.cancel()
        logger.info("Note通知機能のタスクを停止しました")

    @tasks.loop(hours=1)
    async def check_note_rss_onthehour(self) -> None:
        """
        毎正時にnoteのRSSをチェックし、新規投稿があれば通知します
        """
        if not settings.note_notification_enabled:
            return
            
        try:
            await self._check_and_notify_new_posts()
        except Exception as e:
            logger.error(f"Note通知のチェック中にエラーが発生しました: {e}")

    @check_note_rss_onthehour.before_loop
    async def before_check_note_rss(self) -> None:
        """タスク開始前にBotの準備完了を待機し、次の正時まで待機"""
        await self.bot.wait_until_ready()
        
        # JST（日本標準時）で次の正時まで待機
        jst = datetime.timezone(datetime.timedelta(hours=9))
        now = datetime.datetime.now(jst)
        next_hour = now.replace(minute=0, second=0, microsecond=0) + datetime.timedelta(hours=1)
        sleep_seconds = (next_hour - now).total_seconds()
        
        if sleep_seconds > 0:
            logger.info(f"JST次の正時（{next_hour.strftime('%H:%M')}）まで {sleep_seconds:.0f}秒 待機します")
            await asyncio.sleep(sleep_seconds)
        
        logger.info("Note通知タスクを開始しました（毎正時実行）")

    async def _check_and_notify_new_posts(self) -> None:
        """
        RSSから新規投稿をチェックし、通知を送信
        """
        try:
            feed = await self._fetch_rss_feed()
            if not feed or not feed.entries:
                logger.warning("RSSフィードが空または取得できませんでした")
                return

            for entry in feed.entries:
                post_data = await self._parse_rss_entry(entry)
                if post_data and await self._is_new_post(post_data['post_id']):
                    await self._send_notification(post_data)
                    await self._save_post_to_db(post_data)
                    logger.info(f"新規note投稿を通知しました: {post_data['title']}")

        except Exception as e:
            logger.error(f"新規投稿チェック中にエラー: {e}")
            raise

    async def _fetch_rss_feed(self, max_retries: int = 3) -> Optional[Any]:
        """
        RSSフィードを非同期で取得（最大3回までリトライ）
        
        Args:
            max_retries: 最大リトライ回数（デフォルト: 3）
            
        Returns:
            feedparser.FeedParserDict: パース済みRSSフィード
        """
        last_exception = None
        
        for attempt in range(1, max_retries + 1):
            try:
                logger.info(f"RSSフィード取得試行 {attempt}/{max_retries}: {settings.note_rss_url}")
                
                loop = asyncio.get_event_loop()
                feed = await loop.run_in_executor(
                    None, 
                    feedparser.parse, 
                    settings.note_rss_url
                )
                
                # 詳細なデバッグ情報をログ出力
                logger.debug(f"フィード取得結果 - Status: {getattr(feed, 'status', 'N/A')}, "
                           f"Bozo: {getattr(feed, 'bozo', 'N/A')}, "
                           f"Entries: {len(feed.entries) if hasattr(feed, 'entries') else 'N/A'}")
                
                # フィードの妥当性を詳細にチェック
                if not feed:
                    logger.warning(f"試行 {attempt}: フィードオブジェクトがNoneまたはFalse")
                    last_exception = Exception("フィードオブジェクトが無効")
                    continue
                    
                if not hasattr(feed, 'entries'):
                    logger.warning(f"試行 {attempt}: フィードオブジェクトにentriesアトリビュートがありません")
                    last_exception = Exception("フィードにentriesがない")
                    continue
                    
                if not feed.entries:
                    logger.warning(f"試行 {attempt}: フィードのentriesが空です")
                    last_exception = Exception("フィードのentriesが空")
                    continue
                
                # 成功時のログ
                logger.info(f"RSSフィード取得成功（試行 {attempt}/{max_retries}）: {len(feed.entries)}件のエントリを取得")
                return feed
                
            except Exception as e:
                last_exception = e
                logger.error(f"RSSフィード取得エラー（試行 {attempt}/{max_retries}）: {e}")
                
                # 最後の試行でない場合は短時間待機
                if attempt < max_retries:
                    await asyncio.sleep(1)  # 1秒待機してリトライ
        
        # 全ての試行が失敗した場合
        logger.error(f"RSSフィード取得が{max_retries}回の試行すべてで失敗しました。最後のエラー: {last_exception}")
        return None

    async def _parse_rss_entry(self, entry: Any) -> Optional[Dict[str, Any]]:
        """
        RSSエントリをパースして投稿データを作成
        
        Args:
            entry: RSSエントリ
            
        Returns:
            Dict[str, Any]: パース済み投稿データ
        """
        try:
            post_id = self._extract_post_id(entry.link)
            if not post_id:
                logger.warning(f"投稿IDを抽出できませんでした: {entry.link}")
                return None
            
            published_at = None
            if hasattr(entry, 'published_parsed') and entry.published_parsed:
                published_at = datetime.datetime(*entry.published_parsed[:6], tzinfo=datetime.timezone.utc)

            summary = self._clean_summary(getattr(entry, 'summary', ''))

            thumbnail_url = self._extract_thumbnail(entry)
            
            creator_icon = self._extract_creator_icon(entry)

            return {
                'post_id': post_id,
                'title': unescape(entry.title),
                'link': entry.link,
                'author': getattr(entry, 'author', 'HFS Discord'),
                'published_at': published_at,
                'summary': summary,
                'thumbnail_url': thumbnail_url,
                'creator_icon': creator_icon
            }

        except Exception as e:
            logger.error(f"RSSエントリパースエラー: {e}")
            return None

    def _extract_post_id(self, link: str) -> Optional[str]:
        """
        noteのリンクから投稿IDを抽出
        
        Args:
            link: noteの投稿リンク
            
        Returns:
            str: 投稿ID
        """
        try:
            match = re.search(r'/n/([a-zA-Z0-9_-]+)', link)
            return match.group(1) if match else None
        except Exception:
            return None

    def _clean_summary(self, summary: str) -> str:
        """
        概要テキストをクリーンアップ
        
        Args:
            summary: 元の概要テキスト
            
        Returns:
            str: クリーンアップされた概要テキスト
        """
        if not summary:
            return ""
        
        summary = re.sub(r'<[^>]+>', '', summary)
        summary = unescape(summary)
        summary = re.sub(r'\s+', ' ', summary)
        if len(summary) > 300:
            summary = summary[:297] + "..."
        
        return summary.strip()

    def _extract_thumbnail(self, entry: Any) -> Optional[str]:
        """
        RSSエントリからサムネイル画像を抽出
        
        Args:
            entry: RSSエントリ
            
        Returns:
            Optional[str]: サムネイル画像URL
        """
        try:
            # media_thumbnailがリスト形式の場合を処理
            if hasattr(entry, 'media_thumbnail') and entry.media_thumbnail:
                if isinstance(entry.media_thumbnail, list) and len(entry.media_thumbnail) > 0:
                    # リストの最初の要素から URL を抽出
                    thumbnail_item = entry.media_thumbnail[0]
                    if isinstance(thumbnail_item, dict) and 'url' in thumbnail_item:
                        url = thumbnail_item['url']
                        return self._validate_url(url)
                elif isinstance(entry.media_thumbnail, str):
                    return self._validate_url(entry.media_thumbnail)
            
            # enclosures から画像を探す
            if hasattr(entry, 'enclosures') and entry.enclosures:
                for enclosure in entry.enclosures:
                    if hasattr(enclosure, 'type') and enclosure.type and enclosure.type.startswith('image/'):
                        if hasattr(enclosure, 'href'):
                            return self._validate_url(enclosure.href)
            
            # tags から画像を探す
            if hasattr(entry, 'tags') and entry.tags:
                for tag in entry.tags:
                    if isinstance(tag, dict):
                        term = tag.get('term', '').lower()
                        if 'media' in term and 'thumbnail' in term and 'href' in tag:
                            return self._validate_url(tag['href'])
            
            return None
            
        except Exception as e:
            logger.warning(f"サムネイル抽出エラー: {e}")
            return None

    def _validate_url(self, url: str) -> Optional[str]:
        """
        URLの形式を検証し、有効なURLのみを返す
        
        Args:
            url: 検証するURL
            
        Returns:
            Optional[str]: 有効なURLまたはNone
        """
        if not url or not isinstance(url, str):
            return None
        
        url = url.strip()
        if not url:
            return None
        
        # HTTP/HTTPSのみ受け入れる
        if not (url.startswith('http://') or url.startswith('https://')):
            return None
        
        # 基本的なURL形式をチェック
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            if not parsed.netloc:
                return None
            return url
        except Exception:
            return None

    def _extract_creator_icon(self, entry: Any) -> Optional[str]:
        """
        RSSエントリから作成者アイコンを抽出
        
        Args:
            entry: RSSエントリ
            
        Returns:
            Optional[str]: 作成者アイコンURL
        """
        try:
            # note特有の creator image 属性をチェック
            if hasattr(entry, 'note_creatorimage') and entry.note_creatorimage:
                url = self._validate_url(entry.note_creatorimage)
                if url:
                    return url
            
            # 標準的な author_detail をチェック
            if hasattr(entry, 'author_detail') and isinstance(entry.author_detail, dict):
                if 'href' in entry.author_detail:
                    url = self._validate_url(entry.author_detail['href'])
                    if url:
                        return url
            
            # links から author リンクを探す
            if hasattr(entry, 'links') and entry.links:
                for link in entry.links:
                    if isinstance(link, dict) and link.get('rel') == 'author' and 'href' in link:
                        url = self._validate_url(link['href'])
                        if url:
                            return url
            
            # デフォルトアイコンを返す
            return "https://images.frwi.net/data/images/59693bc0-5333-42c7-8739-55f240fc63d6.png"
            
        except Exception as e:
            logger.warning(f"クリエイターアイコン抽出エラー: {e}")
            return "https://images.frwi.net/data/images/59693bc0-5333-42c7-8739-55f240fc63d6.png"

    async def _is_new_post(self, post_id: str) -> bool:
        """
        投稿が新規かどうかをデータベースで確認
        
        Args:
            post_id: 投稿ID
            
        Returns:
            bool: 新規投稿の場合True
        """
        try:
            async with db.pool.acquire() as conn:
                result = await conn.fetchrow(
                    "SELECT id FROM note_posts WHERE post_id = $1",
                    post_id
                )
                return result is None
        except Exception as e:
            logger.error(f"投稿の新規チェック中にエラー: {e}")
            return False

    async def _save_post_to_db(self, post_data: Dict[str, Any]) -> None:
        """
        投稿データをデータベースに保存
        
        Args:
            post_data: 投稿データ
        """
        try:
            async with db.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO note_posts (post_id, title, link, author, published_at, summary, thumbnail_url, creator_icon)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                    ON CONFLICT (post_id) DO NOTHING
                    """,
                    post_data['post_id'],
                    post_data['title'],
                    post_data['link'],
                    post_data['author'],
                    post_data['published_at'],
                    post_data['summary'],
                    post_data['thumbnail_url'],
                    post_data['creator_icon']
                )
        except Exception as e:
            logger.error(f"投稿データのDB保存中にエラー: {e}")

    async def _send_notification(self, post_data: Dict[str, Any]) -> None:
        """
        新規投稿の通知を送信
        
        Args:
            post_data: 投稿データ
        """
        try:
            if settings.note_webhook_url:
                await self._send_webhook_notification(post_data)
                
        except Exception as e:
            logger.error(f"通知送信中にエラー: {e}")

    async def _send_webhook_notification(self, post_data: Dict[str, Any]) -> None:
        """
        Webhookで通知を送信（ロールメンション付き）
        
        Args:
            post_data: 投稿データ
        """
        try:
            embed_data = self._create_notification_embed(post_data).to_dict()
            
            # 「HFS Note通知」ロールのメンションとIDを取得
            role_mention, role_id = await self._get_role_mention_and_id("HFS Note通知")
            
            payload = {
                "content": role_mention,
                "embeds": [embed_data],
                "username": "HFS 運営チーム",
                "avatar_url": "https://images.frwi.net/data/images/59693bc0-5333-42c7-8739-55f240fc63d6.png"
            }
            
            # ロールIDがある場合、allowed_mentionsで明示的に通知を許可
            if role_id:
                payload["allowed_mentions"] = {
                    "roles": [role_id],
                    "parse": []
                }
                logger.info(f"allowed_mentionsでロールID {role_id} を指定しました")
            
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: requests.post(
                    settings.note_webhook_url,
                    json=payload,
                    timeout=10
                )
            )

        except Exception as e:
            logger.error(f"Webhook通知送信エラー: {e}")

    async def _get_role_mention_and_id(self, role_name: str) -> tuple[str, Optional[str]]:
        """
        ロール名からロールIDを取得してメンション文字列とIDを作成
        
        Args:
            role_name: 検索するロール名
            
        Returns:
            tuple[str, Optional[str]]: (ロールメンション文字列, ロールID文字列)
        """
        try:
            # 全ギルドを検索してロールを探す
            for guild in self.bot.guilds:
                for role in guild.roles:
                    if role.name == role_name:
                        logger.info(f"ロール '{role_name}' を発見: {role.id} (ギルド: {guild.name})")
                        return f"<@&{role.id}>", str(role.id)
            
            logger.warning(f"ロール '{role_name}' が見つかりませんでした")
            return "", None
            
        except Exception as e:
            logger.error(f"ロール検索エラー: {e}")
            return "", None

    def _create_notification_embed(self, post_data: Dict[str, Any]) -> discord.Embed:
        """
        通知用のリッチなEmbedを作成
        
        Args:
            post_data: 投稿データ
            
        Returns:
            discord.Embed: 通知用Embed
        """
        embed = discord.Embed(
            title=post_data['title'],
            url=post_data['link'],
            description=post_data['summary'] if post_data['summary'] else "新しい記事が投稿されました！",
            color=0x00D4AA,
            timestamp=post_data['published_at'] or datetime.datetime.now(datetime.timezone.utc)
        )
        
        embed.set_author(
            name=post_data['author'],
            icon_url=post_data.get('creator_icon', "https://images.frwi.net/data/images/59693bc0-5333-42c7-8739-55f240fc63d6.png")
        )
        
        if post_data.get('thumbnail_url'):
            embed.set_image(url=post_data['thumbnail_url'])
        
        embed.set_footer(
            text="HFS 運営チーム",
            icon_url="https://images.frwi.net/data/images/59693bc0-5333-42c7-8739-55f240fc63d6.png"
        )
        
        embed.add_field(
            name="📝 記事を読む",
            value=f"[こちらから記事をお読みください]({post_data['link']})",
            inline=False
        )
        
        return embed

    @commands.command(name="note_test", hidden=True)
    @is_owner()
    @is_guild()
    @log_commands()
    async def test_note_notification(self, ctx: commands.Context) -> None:
        """
        Note通知のテストコマンド（管理者専用）
        """
        await ctx.send("📝 Note通知のテストを開始します...")
        
        try:
            await self._check_and_notify_new_posts()
            await ctx.send("✅ Note通知のテストが完了しました。")
        except Exception as e:
            await ctx.send(f"❌ テスト中にエラーが発生しました: {e}")
            logger.error(f"Note通知テストエラー: {e}")

    @commands.command(name="note_status", hidden=True)
    @is_owner()
    @is_guild()
    @log_commands()
    async def note_status(self, ctx: commands.Context) -> None:
        """
        Note通知の状態を確認（管理者専用）
        """
        try:
            async with db.pool.acquire() as conn:
                count = await conn.fetchval(
                    "SELECT COUNT(*) FROM note_posts"
                )
                latest = await conn.fetchrow(
                    "SELECT title, notified_at FROM note_posts ORDER BY notified_at DESC LIMIT 1"
                )
            
            embed = discord.Embed(
                title="📊 Note通知システム状態",
                color=0x00D4AA
            )
            
            embed.add_field(
                name="📝 総投稿数",
                value=f"{count}件",
                inline=True
            )
            
            embed.add_field(
                name="🔔 通知状態",
                value="有効" if settings.note_notification_enabled else "無効",
                inline=True
            )
            
            embed.add_field(
                name="📡 RSS URL",
                value=settings.note_rss_url,
                inline=False
            )
            
            if latest:
                embed.add_field(
                    name="📄 最新通知",
                    value=f"{latest['title']}\n{latest['notified_at'].strftime('%Y-%m-%d %H:%M:%S')}",
                    inline=False
                )
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            await ctx.send(f"❌ 状態取得中にエラーが発生しました: {e}")
            logger.error(f"Note状態取得エラー: {e}")

async def setup(bot: commands.Bot) -> None:
    """Cogをセットアップ"""
    await bot.add_cog(NoteNotify(bot))
