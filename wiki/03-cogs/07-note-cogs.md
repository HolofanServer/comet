# ノートCogs

## C.O.M.E.T.について

**C.O.M.E.T.**の名前は以下の頭文字から構成されています：

- **C**ommunity of
- **O**shilove
- **M**oderation &
- **E**njoyment
- **T**ogether

HFS - ホロライブ非公式ファンサーバーのコミュニティを支える、推し愛とモデレーション、そして楽しさを一緒に提供するボットです。

## 概要

ノートCogsは、外部プラットフォーム（主にnote.com）からのコンテンツ統合と通知機能を提供します。RSS フィード監視、音声コンテンツ管理、自動通知システムを含み、コミュニティメンバーに最新情報を効率的に配信します。

## Cogs構成

### 1. ノート通知 (`note_notice.py`)

**目的**: note.comからの新規投稿自動通知システム

**主要機能**:
- RSS フィード監視
- 新規投稿の自動検出
- カスタマイズ可能な通知形式
- 投稿データの永続化
- 重複通知の防止

**場所**: [`cogs/note/note_notice.py`](../cogs/note/note_notice.py)

#### 実装詳細

```python
import feedparser
import aiohttp
import asyncio
from datetime import datetime, timedelta
import pytz
from typing import Dict, List, Optional, Any

class NoteNoticeCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.feed_urls = {}  # guild_id -> feed_url
        self.notification_channels = {}  # guild_id -> channel_id
        self.check_interval = 300  # 5分間隔
        self.last_check = {}  # feed_url -> last_check_time
        self.processed_posts = set()  # 処理済み投稿ID
        
        # バックグラウンドタスクの開始
        self.feed_check_task = self.bot.loop.create_task(self.feed_check_loop())

    def cog_unload(self):
        """Cogアンロード時のクリーンアップ"""
        if hasattr(self, 'feed_check_task'):
            self.feed_check_task.cancel()

    async def feed_check_loop(self):
        """RSS フィード監視ループ"""
        await self.bot.wait_until_ready()
        
        while not self.bot.is_closed():
            try:
                await self.check_all_feeds()
                await asyncio.sleep(self.check_interval)
            except Exception as e:
                logger.error(f"Feed check loop error: {e}")
                await asyncio.sleep(60)  # エラー時は1分待機

    async def check_all_feeds(self):
        """全フィードのチェック"""
        for guild_id, feed_url in self.feed_urls.items():
            try:
                await self.check_feed(guild_id, feed_url)
            except Exception as e:
                logger.error(f"Error checking feed for guild {guild_id}: {e}")

    async def check_feed(self, guild_id: int, feed_url: str):
        """個別フィードのチェック"""
        try:
            # RSS フィードの取得
            async with aiohttp.ClientSession() as session:
                async with session.get(feed_url, timeout=30) as response:
                    if response.status != 200:
                        logger.warning(f"Failed to fetch feed {feed_url}: HTTP {response.status}")
                        return
                    
                    feed_content = await response.text()
            
            # フィードの解析
            feed = feedparser.parse(feed_content)
            
            if feed.bozo:
                logger.warning(f"Invalid feed format: {feed_url}")
                return
            
            # 新規投稿の処理
            new_posts = await self.get_new_posts(feed, feed_url)
            
            for post in new_posts:
                await self.process_new_post(guild_id, post)
                
        except Exception as e:
            logger.error(f"Error processing feed {feed_url}: {e}")

    async def get_new_posts(self, feed: feedparser.FeedParserDict, feed_url: str) -> List[Dict[str, Any]]:
        """新規投稿の抽出"""
        new_posts = []
        last_check = self.last_check.get(feed_url, datetime.now(pytz.UTC) - timedelta(hours=1))
        
        for entry in feed.entries:
            # 投稿日時の解析
            published_time = self.parse_published_time(entry)
            
            if published_time and published_time > last_check:
                # 重複チェック
                post_id = entry.get('id', entry.get('link', ''))
                if post_id not in self.processed_posts:
                    post_data = await self.extract_post_data(entry)
                    new_posts.append(post_data)
                    self.processed_posts.add(post_id)
        
        # 最終チェック時刻の更新
        self.last_check[feed_url] = datetime.now(pytz.UTC)
        
        return new_posts

    def parse_published_time(self, entry: Dict[str, Any]) -> Optional[datetime]:
        """投稿日時の解析"""
        time_fields = ['published_parsed', 'updated_parsed']
        
        for field in time_fields:
            if hasattr(entry, field) and getattr(entry, field):
                time_struct = getattr(entry, field)
                return datetime(*time_struct[:6], tzinfo=pytz.UTC)
        
        return None

    async def extract_post_data(self, entry: Dict[str, Any]) -> Dict[str, Any]:
        """投稿データの抽出"""
        post_data = {
            'id': entry.get('id', entry.get('link', '')),
            'title': entry.get('title', 'タイトルなし'),
            'link': entry.get('link', ''),
            'summary': entry.get('summary', ''),
            'author': entry.get('author', '不明'),
            'published': self.parse_published_time(entry),
            'tags': [tag.term for tag in entry.get('tags', [])],
            'thumbnail_url': None,
            'creator_icon': None
        }
        
        # サムネイル画像の抽出
        if hasattr(entry, 'media_thumbnail') and entry.media_thumbnail:
            post_data['thumbnail_url'] = entry.media_thumbnail[0].get('url')
        
        # 作成者アイコンの抽出
        if hasattr(entry, 'note_creatorimage') and entry.note_creatorimage:
            post_data['creator_icon'] = entry.note_creatorimage
        
        # データベースに保存
        await self.save_post_data(post_data)
        
        return post_data

    async def save_post_data(self, post_data: Dict[str, Any]):
        """投稿データの保存"""
        try:
            query = """
            INSERT OR REPLACE INTO note_posts (
                post_id, title, link, summary, author, published_at,
                tags, thumbnail_url, creator_icon, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
            
            await self.bot.db_service.execute_query(
                query,
                (
                    post_data['id'],
                    post_data['title'],
                    post_data['link'],
                    post_data['summary'],
                    post_data['author'],
                    post_data['published'].isoformat() if post_data['published'] else None,
                    ','.join(post_data['tags']),
                    post_data['thumbnail_url'],
                    post_data['creator_icon'],
                    datetime.now().isoformat()
                )
            )
        except Exception as e:
            logger.error(f"Failed to save post data: {e}")

    async def process_new_post(self, guild_id: int, post_data: Dict[str, Any]):
        """新規投稿の処理"""
        channel_id = self.notification_channels.get(guild_id)
        if not channel_id:
            return
        
        channel = self.bot.get_channel(channel_id)
        if not channel:
            logger.warning(f"Notification channel {channel_id} not found for guild {guild_id}")
            return
        
        # 通知埋め込みの作成
        embed = await self.create_post_embed(post_data)
        
        try:
            await channel.send(embed=embed)
            logger.info(f"Sent note notification for post: {post_data['title']}")
        except Exception as e:
            logger.error(f"Failed to send notification: {e}")

    async def create_post_embed(self, post_data: Dict[str, Any]) -> discord.Embed:
        """投稿通知埋め込みの作成"""
        embed = discord.Embed(
            title=post_data['title'],
            url=post_data['link'],
            description=self.truncate_text(post_data['summary'], 300),
            color=0x00D4AA,  # noteのブランドカラー
            timestamp=post_data['published'] or datetime.now()
        )
        
        # 作成者情報
        embed.set_author(
            name=post_data['author'],
            icon_url=post_data['creator_icon']
        )
        
        # サムネイル画像
        if post_data['thumbnail_url']:
            embed.set_image(url=post_data['thumbnail_url'])
        
        # タグ情報
        if post_data['tags']:
            tags_text = ' '.join([f"`{tag}`" for tag in post_data['tags'][:5]])
            embed.add_field(name="タグ", value=tags_text, inline=False)
        
        # フッター
        embed.set_footer(text="note", icon_url="https://note.com/favicon.ico")
        
        return embed

    def truncate_text(self, text: str, max_length: int) -> str:
        """テキストの切り詰め"""
        if len(text) <= max_length:
            return text
        return text[:max_length-3] + "..."

    @app_commands.command(name="note_setup", description="note通知の設定")
    @app_commands.describe(
        feed_url="監視するnote RSS フィードのURL",
        channel="通知を送信するチャンネル"
    )
    async def setup_note_notifications(
        self, 
        interaction: discord.Interaction, 
        feed_url: str,
        channel: discord.TextChannel
    ):
        """note通知の設定"""
        
        # 権限チェック
        if not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message("この機能を使用する権限がありません。", ephemeral=True)
            return
        
        # フィードURLの検証
        if not await self.validate_feed_url(feed_url):
            await interaction.response.send_message("無効なフィードURLです。", ephemeral=True)
            return
        
        # 設定の保存
        self.feed_urls[interaction.guild.id] = feed_url
        self.notification_channels[interaction.guild.id] = channel.id
        
        await self.save_guild_config(interaction.guild.id, feed_url, channel.id)
        
        embed = discord.Embed(
            title="✅ note通知設定完了",
            description="note通知が正常に設定されました。",
            color=0x00FF00
        )
        embed.add_field(name="フィードURL", value=feed_url, inline=False)
        embed.add_field(name="通知チャンネル", value=channel.mention, inline=True)
        embed.add_field(name="チェック間隔", value=f"{self.check_interval // 60}分", inline=True)
        
        await interaction.response.send_message(embed=embed)

    async def validate_feed_url(self, feed_url: str) -> bool:
        """フィードURLの検証"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(feed_url, timeout=10) as response:
                    if response.status != 200:
                        return False
                    
                    content = await response.text()
                    feed = feedparser.parse(content)
                    
                    return not feed.bozo and len(feed.entries) > 0
        except Exception:
            return False

    async def save_guild_config(self, guild_id: int, feed_url: str, channel_id: int):
        """ギルド設定の保存"""
        try:
            query = """
            INSERT OR REPLACE INTO note_config (
                guild_id, feed_url, notification_channel_id, 
                check_interval, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """
            
            now = datetime.now().isoformat()
            await self.bot.db_service.execute_query(
                query,
                (guild_id, feed_url, channel_id, self.check_interval, now, now)
            )
        except Exception as e:
            logger.error(f"Failed to save guild config: {e}")

    async def load_guild_configs(self):
        """ギルド設定の読み込み"""
        try:
            query = "SELECT guild_id, feed_url, notification_channel_id FROM note_config"
            results = await self.bot.db_service.fetch_all(query, ())
            
            for row in results:
                self.feed_urls[row['guild_id']] = row['feed_url']
                self.notification_channels[row['guild_id']] = row['notification_channel_id']
                
        except Exception as e:
            logger.error(f"Failed to load guild configs: {e}")

    @app_commands.command(name="note_status", description="note通知の状態確認")
    async def check_note_status(self, interaction: discord.Interaction):
        """note通知の状態確認"""
        guild_id = interaction.guild.id
        
        if guild_id not in self.feed_urls:
            await interaction.response.send_message("note通知が設定されていません。", ephemeral=True)
            return
        
        feed_url = self.feed_urls[guild_id]
        channel_id = self.notification_channels.get(guild_id)
        channel = self.bot.get_channel(channel_id) if channel_id else None
        
        embed = discord.Embed(
            title="📊 note通知状態",
            color=0x0099FF
        )
        
        embed.add_field(name="フィードURL", value=feed_url, inline=False)
        embed.add_field(name="通知チャンネル", value=channel.mention if channel else "設定なし", inline=True)
        embed.add_field(name="チェック間隔", value=f"{self.check_interval // 60}分", inline=True)
        
        # 最終チェック時刻
        last_check = self.last_check.get(feed_url)
        if last_check:
            jst_time = last_check.astimezone(pytz.timezone('Asia/Tokyo'))
            embed.add_field(name="最終チェック", value=jst_time.strftime("%Y-%m-%d %H:%M:%S JST"), inline=True)
        
        # 最近の投稿統計
        recent_posts = await self.get_recent_posts_count(7)
        embed.add_field(name="過去7日の投稿", value=f"{recent_posts}件", inline=True)
        
        await interaction.response.send_message(embed=embed)

    async def get_recent_posts_count(self, days: int) -> int:
        """最近の投稿数を取得"""
        try:
            query = """
            SELECT COUNT(*) as count 
            FROM note_posts 
            WHERE created_at > datetime('now', '-{} days')
            """.format(days)
            
            result = await self.bot.db_service.fetch_one(query, ())
            return result['count'] if result else 0
        except Exception:
            return 0
```

### 2. HFS音声 (`hfs_voices.py`)

**目的**: 音声コンテンツの管理と配信

**主要機能**:
- 音声ファイルの管理
- 音声コンテンツのメタデータ管理
- 再生リストの作成
- 音声品質の最適化

**実装例**:

```python
import os
import json
from pathlib import Path
from typing import Dict, List, Optional
import aiofiles

class HFSVoicesCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.voice_directory = Path("resources/voices")
        self.voice_metadata = {}
        self.playlists = {}
        
        # 音声ディレクトリの作成
        self.voice_directory.mkdir(parents=True, exist_ok=True)
        
        # メタデータの読み込み
        self.bot.loop.create_task(self.load_voice_metadata())

    async def load_voice_metadata(self):
        """音声メタデータの読み込み"""
        metadata_file = self.voice_directory / "metadata.json"
        
        if metadata_file.exists():
            try:
                async with aiofiles.open(metadata_file, 'r', encoding='utf-8') as f:
                    content = await f.read()
                    self.voice_metadata = json.loads(content)
            except Exception as e:
                logger.error(f"Failed to load voice metadata: {e}")
                self.voice_metadata = {}
        else:
            self.voice_metadata = {}

    async def save_voice_metadata(self):
        """音声メタデータの保存"""
        metadata_file = self.voice_directory / "metadata.json"
        
        try:
            async with aiofiles.open(metadata_file, 'w', encoding='utf-8') as f:
                await f.write(json.dumps(self.voice_metadata, indent=2, ensure_ascii=False))
        except Exception as e:
            logger.error(f"Failed to save voice metadata: {e}")

    @app_commands.command(name="voice_add", description="音声ファイルの追加")
    @app_commands.describe(
        name="音声の名前",
        file="音声ファイル",
        description="音声の説明",
        category="カテゴリ"
    )
    async def add_voice(
        self, 
        interaction: discord.Interaction, 
        name: str,
        file: discord.Attachment,
        description: str = "",
        category: str = "general"
    ):
        """音声ファイルの追加"""
        
        # 権限チェック
        if not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message("この機能を使用する権限がありません。", ephemeral=True)
            return
        
        # ファイル形式チェック
        allowed_formats = ['.mp3', '.wav', '.ogg', '.m4a']
        file_extension = Path(file.filename).suffix.lower()
        
        if file_extension not in allowed_formats:
            await interaction.response.send_message(
                f"サポートされていないファイル形式です。対応形式: {', '.join(allowed_formats)}", 
                ephemeral=True
            )
            return
        
        # ファイルサイズチェック (25MB制限)
        if file.size > 25 * 1024 * 1024:
            await interaction.response.send_message("ファイルサイズが大きすぎます（25MB以下）。", ephemeral=True)
            return
        
        await interaction.response.defer()
        
        try:
            # ファイルの保存
            safe_name = self.sanitize_filename(name)
            file_path = self.voice_directory / f"{safe_name}{file_extension}"
            
            # 重複チェック
            if file_path.exists():
                await interaction.followup.send("同名の音声ファイルが既に存在します。", ephemeral=True)
                return
            
            # ファイルのダウンロードと保存
            await file.save(file_path)
            
            # メタデータの追加
            self.voice_metadata[safe_name] = {
                "original_name": name,
                "filename": file_path.name,
                "description": description,
                "category": category,
                "file_size": file.size,
                "duration": await self.get_audio_duration(file_path),
                "added_by": interaction.user.id,
                "added_at": datetime.now().isoformat(),
                "play_count": 0
            }
            
            await self.save_voice_metadata()
            
            embed = discord.Embed(
                title="✅ 音声ファイル追加完了",
                description=f"音声「{name}」が正常に追加されました。",
                color=0x00FF00
            )
            embed.add_field(name="ファイル名", value=file.filename, inline=True)
            embed.add_field(name="カテゴリ", value=category, inline=True)
            embed.add_field(name="ファイルサイズ", value=f"{file.size / 1024:.1f} KB", inline=True)
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Failed to add voice file: {e}")
            await interaction.followup.send("音声ファイルの追加に失敗しました。", ephemeral=True)

    def sanitize_filename(self, filename: str) -> str:
        """ファイル名のサニタイズ"""
        import re
        # 危険な文字を除去
        safe_name = re.sub(r'[<>:"/\\|?*]', '_', filename)
        # 長さ制限
        return safe_name[:50]

    async def get_audio_duration(self, file_path: Path) -> Optional[float]:
        """音声ファイルの長さを取得"""
        try:
            # ffprobeまたは類似ツールを使用して音声の長さを取得
            # 実装は環境に依存
            return None
        except Exception:
            return None

    @app_commands.command(name="voice_list", description="音声ファイル一覧")
    @app_commands.describe(category="表示するカテゴリ")
    async def list_voices(self, interaction: discord.Interaction, category: str = None):
        """音声ファイル一覧の表示"""
        
        if not self.voice_metadata:
            await interaction.response.send_message("登録されている音声ファイルがありません。", ephemeral=True)
            return
        
        # カテゴリフィルタリング
        voices = self.voice_metadata
        if category:
            voices = {k: v for k, v in voices.items() if v.get('category', 'general') == category}
        
        if not voices:
            await interaction.response.send_message(f"カテゴリ「{category}」に音声ファイルがありません。", ephemeral=True)
            return
        
        # ページネーション用の準備
        voices_per_page = 10
        voice_list = list(voices.items())
        total_pages = (len(voice_list) + voices_per_page - 1) // voices_per_page
        
        # 最初のページを表示
        embed = await self.create_voice_list_embed(voice_list, 0, voices_per_page, total_pages, category)
        
        if total_pages > 1:
            view = VoiceListView(voice_list, voices_per_page, category)
            await interaction.response.send_message(embed=embed, view=view)
        else:
            await interaction.response.send_message(embed=embed)

    async def create_voice_list_embed(
        self, 
        voice_list: List[tuple], 
        page: int, 
        per_page: int, 
        total_pages: int, 
        category: str = None
    ) -> discord.Embed:
        """音声リスト埋め込みの作成"""
        start_idx = page * per_page
        end_idx = min(start_idx + per_page, len(voice_list))
        
        title = "🎵 音声ファイル一覧"
        if category:
            title += f" - {category}"
        
        embed = discord.Embed(title=title, color=0x0099FF)
        
        for i in range(start_idx, end_idx):
            name, metadata = voice_list[i]
            description = metadata.get('description', '説明なし')
            play_count = metadata.get('play_count', 0)
            
            field_value = f"説明: {description}\n再生回数: {play_count}回"
            embed.add_field(name=metadata['original_name'], value=field_value, inline=False)
        
        embed.set_footer(text=f"ページ {page + 1}/{total_pages} | 総数: {len(voice_list)}件")
        
        return embed

    @app_commands.command(name="voice_play", description="音声ファイルの再生")
    @app_commands.describe(name="再生する音声の名前")
    async def play_voice(self, interaction: discord.Interaction, name: str):
        """音声ファイルの再生"""
        
        # 音声ファイルの検索
        voice_data = None
        for voice_name, metadata in self.voice_metadata.items():
            if metadata['original_name'].lower() == name.lower():
                voice_data = metadata
                break
        
        if not voice_data:
            await interaction.response.send_message("指定された音声ファイルが見つかりません。", ephemeral=True)
            return
        
        # ボイスチャンネル接続チェック
        if not interaction.user.voice:
            await interaction.response.send_message("ボイスチャンネルに接続してください。", ephemeral=True)
            return
        
        voice_channel = interaction.user.voice.channel
        
        try:
            # ボイスクライアントの取得または作成
            voice_client = interaction.guild.voice_client
            if not voice_client:
                voice_client = await voice_channel.connect()
            elif voice_client.channel != voice_channel:
                await voice_client.move_to(voice_channel)
            
            # 音声ファイルの再生
            file_path = self.voice_directory / voice_data['filename']
            
            if not file_path.exists():
                await interaction.response.send_message("音声ファイルが見つかりません。", ephemeral=True)
                return
            
            # FFmpegソースの作成
            source = discord.FFmpegPCMAudio(str(file_path))
            
            if voice_client.is_playing():
                voice_client.stop()
            
            voice_client.play(source)
            
            # 再生回数の更新
            voice_data['play_count'] = voice_data.get('play_count', 0) + 1
            await self.save_voice_metadata()
            
            embed = discord.Embed(
                title="🎵 音声再生中",
                description=f"「{voice_data['original_name']}」を再生しています。",
                color=0x00FF00
            )
            
            await interaction.response.send_message(embed=embed)
            
        except Exception as e:
            logger.error(f"Failed to play voice: {e}")
            await interaction.response.send_message("音声の再生に失敗しました。", ephemeral=True)

    @app_commands.command(name="voice_remove", description="音声ファイルの削除")
    @app_commands.describe(name="削除する音声の名前")
    async def remove_voice(self, interaction: discord.Interaction, name: str):
        """音声ファイルの削除"""
        
        # 権限チェック
        if not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message("この機能を使用する権限がありません。", ephemeral=True)
            return
        
        # 音声ファイルの検索
        voice_key = None
        voice_data = None
        for voice_name, metadata in self.voice_metadata.items():
            if metadata['original_name'].lower() == name.lower():
                voice_key = voice_name
                voice_data = metadata
                break
        
        if not voice_data:
            await interaction.response.send_message("指定された音声ファイルが見つかりません。", ephemeral=True)
            return
        
        try:
            # ファイルの削除
            file_path = self.voice_directory / voice_data['filename']
            if file_path.exists():
                file_path.unlink()
            
            # メタデータから削除
            del self.voice_metadata[voice_key]
            await self.save_voice_metadata()
            
            embed = discord.Embed(
                title="✅ 音声ファイル削除完了",
                description=f"音声「{voice_data['original_name']}」が削除されました。",
                color=0xFF0000
            )
            
            await interaction.response.send_message(embed=embed)
            
        except Exception as e:
            logger.error(f"Failed to remove voice: {e}")
            await interaction.response.send_message("音声ファイルの削除に失敗しました。", ephemeral=True)

class VoiceListView(discord.ui.View):
    def __init__(self, voice_list: List[tuple], per_page: int, category: str = None):
        super().__init__(timeout=300)
        self.voice_list = voice_list
        self.per_page = per_page
        self.category = category
        self.current_page = 0
        self.total_pages = (len(voice_list) + per_page - 1) // per_page

    @discord.ui.button(label="◀️", style=discord.ButtonStyle.secondary)
    async def previous_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page > 0:
            self.current_page -= 1
            embed = await self.create_voice_list_embed()
            await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="▶️", style=discord.ButtonStyle.secondary)
    async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page < self.total_pages - 1:
            self.current_page += 1
            embed = await self.create_voice_list_embed()
            await interaction.response.edit_message(embed=embed, view=self)

    async def create_voice_list_embed(self) -> discord.Embed:
        """現在のページの埋め込みを作成"""
        # HFSVoicesCogのメソッドを呼び出し
        # 実装は簡略化
        pass
```

## データベース設計

### ノート関連テーブル

```sql
-- note投稿テーブル
CREATE TABLE note_posts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    post_id TEXT UNIQUE NOT NULL,
    title TEXT NOT NULL,
    link TEXT NOT NULL,
    summary TEXT,
    author TEXT,
    published_at TIMESTAMP,
    tags TEXT,
    thumbnail_url TEXT,
    creator_icon TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- note設定テーブル
CREATE TABLE note_config (
    guild_id INTEGER PRIMARY KEY,
    feed_url TEXT NOT NULL,
    notification_channel_id INTEGER NOT NULL,
    check_interval INTEGER DEFAULT 300,
    last_check TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 音声ファイルテーブル
CREATE TABLE voice_files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    filename TEXT NOT NULL,
    description TEXT,
    category TEXT DEFAULT 'general',
    file_size INTEGER,
    duration REAL,
    play_count INTEGER DEFAULT 0,
    added_by INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## 設定とカスタマイズ

### 1. RSS フィード設定

```python
class NoteFeedConfig:
    def __init__(self):
        self.default_check_interval = 300  # 5分
        self.max_posts_per_check = 10
        self.timeout_seconds = 30
        
    def get_feed_settings(self, guild_id: int) -> Dict[str, Any]:
        """ギルド固有のフィード設定を取得"""
        return {
            "check_interval": self.default_check_interval,
            "max_posts": self.max_posts_per_check,
            "timeout": self.timeout_seconds,
            "custom_filters": []
        }
```

### 2. 通知カスタマイズ

```python
class NotificationCustomizer:
    def __init__(self):
        self.templates = {
            "default": {
                "title": "{title}",
                "description": "{summary}",
                "color": 0x00D4AA,
                "show_author": True,
                "show_tags": True,
                "show_thumbnail": True
            },
            "minimal": {
                "title": "{title}",
                "description": "",
                "color": 0x808080,
                "show_author": False,
                "show_tags": False,
                "show_thumbnail": False
            }
        }
    
    def create_custom_embed(self, post_data: Dict[str, Any], template_name: str = "default") -> discord.Embed:
        """カスタムテンプレートで埋め込みを作成"""
        template = self.templates.get(template_name, self.templates["default"])
        
        embed = discord.Embed(
            title=template["title"].format(**post_data),
            url=post_data["link"],
            description=template["description"].format(**post_data),
            color=template["color"],
            timestamp=post_data["published"]
        )
        
        if template["show_author"]:
            embed.set_author(name=post_data["author"])
        
        if template["show_thumbnail"] and post_data["thumbnail_url"]:
            embed.set_image(url=post_data["thumbnail_url"])
        
        if template["show_tags"] and post_data["tags"]:
            tags_text = " ".join([f"`{tag}`" for tag in post_data["tags"][:5]])
            embed.add_field(name="タグ", value=tags_text, inline=False)
        
        return embed
```

---

## 関連ドキュメント

- [Cogsアーキテクチャ](01-cogs-architecture.md)
- [ツールCogs](05-tool-cogs.md)
- [データベース管理](../04-utilities/01-database-management.md)
- [外部API統合](../04-utilities/02-api-integration.md)
