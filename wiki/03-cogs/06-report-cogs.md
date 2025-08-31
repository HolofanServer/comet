# レポートCogs

## C.O.M.E.T.について

**C.O.M.E.T.**の名前は以下の頭文字から構成されています：

- **C**ommunity of
- **O**shilove
- **M**oderation &
- **E**njoyment
- **T**ogether

HFS - ホロライブ非公式ファンサーバーのコミュニティを支える、推し愛とモデレーション、そして楽しさを一緒に提供するボットです。

## 概要

レポートCogsは、サーバー内での不適切な行動やコンテンツを報告するための包括的なシステムを提供します。メッセージ通報、ユーザー通報、設定管理機能を含み、モデレーションチームの効率的な対応を支援します。

## Cogs構成

### 1. メッセージ通報 (`report_message.py`)

**目的**: 不適切なメッセージの通報システム

**主要機能**:
- 右クリックコンテキストメニューによる通報
- 詳細な通報理由の選択
- モデレーターへの自動通知
- 通報履歴の記録

**場所**: [`cogs/report/report_message.py`](../cogs/report/report_message.py)

#### 通報理由カテゴリ

| 理由 | 説明 | 重要度 |
|------|------|--------|
| スパム | 繰り返し投稿や宣伝 | 中 |
| 不適切な内容 | 一般的な不適切コンテンツ | 中 |
| ハラスメント | 嫌がらせや攻撃的行動 | 高 |
| メンバーシップの情報公開 | 有料コンテンツの無断共有 | 高 |
| 誤情報 | 虚偽または誤解を招く情報 | 中 |
| 違法な行為 | 法的問題のある内容 | 最高 |
| 自傷/他傷行為 | 危険な行為の促進 | 最高 |
| 生成AIコンテンツ | 無断AI生成コンテンツ | 低 |
| 差別的発言 | 差別や偏見に基づく発言 | 高 |
| プライバシー侵害 | 個人情報の無断公開 | 高 |
| 荒らし行為 | 意図的な妨害行為 | 中 |
| その他 | 上記以外の理由 | 変動 |

#### 実装詳細

```python
class ReportMessageCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

async def setup(bot):
    cog = ReportMessageCog(bot)
    await bot.add_cog(cog)

    async def report_message(interaction: discord.Interaction, message: discord.Message):
        # 設定の読み込み
        from .settings import ReportSettingsCog
        mod_channel_id = await ReportSettingsCog.load_config(interaction.guild.id)
        mod_role_id = await ReportSettingsCog.load_mod_role(interaction.guild.id)

        # 設定確認
        if mod_channel_id is None:
            await interaction.response.send_message("通報チャンネルが設定されていません。", ephemeral=True)
            return

        mod_channel = interaction.guild.get_channel(mod_channel_id)
        if mod_channel is None:
            await interaction.response.send_message("モデレーションチャンネルが見つかりません", ephemeral=True)
            return

        # 通報理由選択UI
        view = ReportReasonView(message=message, mod_channel=mod_channel)
        await interaction.response.send_message("通報理由を選択してください：", view=view, ephemeral=True)
        await view.wait()

        # 通報処理
        if view.value and view.value != "その他":
            await _send_report_embed(interaction, message, view.value, mod_channel, mod_role_id)

    # コンテキストメニューの登録
    command = app_commands.ContextMenu(
        name="メッセージを運営に通報",
        callback=report_message,
        type=discord.AppCommandType.message
    )
    bot.tree.add_command(command)
```

#### 通報理由選択UI

```python
class ReportReasonSelect(discord.ui.Select):
    def __init__(self, message: discord.Message, mod_channel: discord.TextChannel):
        super().__init__()
        self.message = message
        self.mod_channel = mod_channel
        self.placeholder = '通報理由を選択してください'
        self.options = [
            discord.SelectOption(label="スパム", value="スパム"),
            discord.SelectOption(label="不適切な内容", value="不適切な内容"),
            discord.SelectOption(label="ハラスメント", value="ハラスメント"),
            discord.SelectOption(label="メンバーシップの情報公開", value="メンバーシップの情報公開"),
            discord.SelectOption(label="誤情報", value="誤情報"),
            discord.SelectOption(label="違法な行為", value="違法な行為"),
            discord.SelectOption(label="自傷/他傷行為", value="自傷/他傷行為"),
            discord.SelectOption(label="生成AIコンテンツ", value="生成AIコンテンツ"),
            discord.SelectOption(label="差別的発言", value="差別的発言"),
            discord.SelectOption(label="プライバシー侵害", value="プライバシー侵害"),
            discord.SelectOption(label="荒らし行為", value="荒らし行為"),
            discord.SelectOption(label="その他", value="その他"),
        ]

    async def callback(self, interaction: discord.Interaction):
        self.view.value = self.values[0]
        if self.view.value == "その他":
            # カスタム理由入力モーダル
            modal = OtherReasonModal(message=self.message, mod_channel=self.mod_channel)
            await interaction.response.send_modal(modal)
        else:
            await interaction.response.send_message(f"通報理由を {self.view.value} に設定しました。", ephemeral=True)
            self.view.stop()
```

#### カスタム理由入力モーダル

```python
class OtherReasonModal(Modal):
    def __init__(self, message: discord.Message, mod_channel: discord.TextChannel):
        super().__init__(title="通報理由の詳細")
        self.message = message
        self.mod_channel = mod_channel
        self.reason = TextInput(
            label="詳細な通報理由", 
            style=discord.TextStyle.long, 
            placeholder="ここに詳細な通報理由を記入してください...", 
            required=True
        )
        self.add_item(self.reason)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.send_message("通報理由が送信されました。", ephemeral=True)
        
        # モデレーター通知
        mod_role = discord.utils.get(interaction.guild.roles, name="moderator")
        embed = discord.Embed(
            title="メッセージ通報",
            description=f"{interaction.user.mention} が {self.message.jump_url} ({self.message.author.mention}) を **その他の理由** で通報しました。\n直ちに事実確認を行い適切な対応をしてください。",
            color=0xFF0000,
            timestamp=datetime.now().astimezone(pytz.timezone('Asia/Tokyo'))
        )
        embed.add_field(name="通報理由", value=self.reason.value, inline=False)
        embed.add_field(name="通報されたメッセージ", value=f"{self.message.content}\n\n`{self.message.content}`", inline=False)
        embed.set_author(name=f"通報者：{interaction.user.display_name} | {interaction.user.id}\n通報されたユーザー：{self.message.author.display_name} | {self.message.author.id}")
        
        await self.mod_channel.send(embed=embed, content=f"{mod_role.mention}")
        await interaction.followup.send("メッセージが運営に通報されました。", ephemeral=True)
```

### 2. ユーザー通報 (`report_user.py`)

**目的**: 問題のあるユーザーの通報システム

**主要機能**:
- ユーザープロフィールからの通報
- 行動パターンの分析
- 複数通報の統合管理
- 自動警告システム連携

**実装例**:

```python
class ReportUserCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.report_cache = {}  # 一時的な通報データ

    @app_commands.context_menu(name="ユーザーを通報")
    async def report_user(self, interaction: discord.Interaction, member: discord.Member):
        """ユーザー通報のコンテキストメニュー"""
        
        # 自分自身や管理者の通報を防ぐ
        if member == interaction.user:
            await interaction.response.send_message("自分自身を通報することはできません。", ephemeral=True)
            return
        
        if member.guild_permissions.administrator:
            await interaction.response.send_message("管理者を通報することはできません。", ephemeral=True)
            return
        
        # 通報理由選択
        view = UserReportReasonView(member)
        await interaction.response.send_message(
            f"{member.mention} を通報する理由を選択してください：", 
            view=view, 
            ephemeral=True
        )

class UserReportReasonView(discord.ui.View):
    def __init__(self, target_member: discord.Member):
        super().__init__()
        self.target_member = target_member
        self.add_item(UserReportReasonSelect(target_member))

class UserReportReasonSelect(discord.ui.Select):
    def __init__(self, target_member: discord.Member):
        super().__init__()
        self.target_member = target_member
        self.placeholder = 'ユーザー通報理由を選択'
        self.options = [
            discord.SelectOption(label="継続的なハラスメント", value="harassment", emoji="🚫"),
            discord.SelectOption(label="スパム行為", value="spam", emoji="📢"),
            discord.SelectOption(label="不適切なプロフィール", value="inappropriate_profile", emoji="👤"),
            discord.SelectOption(label="ルール違反の繰り返し", value="rule_violation", emoji="⚠️"),
            discord.SelectOption(label="荒らし行為", value="trolling", emoji="🎭"),
            discord.SelectOption(label="差別的行動", value="discrimination", emoji="⚖️"),
            discord.SelectOption(label="その他", value="other", emoji="❓"),
        ]

    async def callback(self, interaction: discord.Interaction):
        reason = self.values[0]
        
        if reason == "other":
            # カスタム理由入力
            modal = UserReportModal(self.target_member)
            await interaction.response.send_modal(modal)
        else:
            # 定型理由での通報
            await self._process_user_report(interaction, reason)

    async def _process_user_report(self, interaction: discord.Interaction, reason: str):
        """ユーザー通報の処理"""
        reason_map = {
            "harassment": "継続的なハラスメント",
            "spam": "スパム行為",
            "inappropriate_profile": "不適切なプロフィール",
            "rule_violation": "ルール違反の繰り返し",
            "trolling": "荒らし行為",
            "discrimination": "差別的行動"
        }
        
        reason_text = reason_map.get(reason, reason)
        
        # モデレーションチャンネルに通知
        await self._send_user_report_notification(interaction, reason_text)
        
        # データベースに記録
        await self._record_user_report(interaction, reason)
        
        await interaction.response.send_message(
            f"{self.target_member.mention} の通報が送信されました。", 
            ephemeral=True
        )

    async def _send_user_report_notification(self, interaction: discord.Interaction, reason: str):
        """モデレーターへの通知"""
        from .settings import ReportSettingsCog
        mod_channel_id = await ReportSettingsCog.load_config(interaction.guild.id)
        
        if not mod_channel_id:
            return
        
        mod_channel = interaction.guild.get_channel(mod_channel_id)
        if not mod_channel:
            return
        
        embed = discord.Embed(
            title="👤 ユーザー通報",
            description=f"{interaction.user.mention} が {self.target_member.mention} を通報しました。",
            color=0xFF6600,
            timestamp=datetime.now().astimezone(pytz.timezone('Asia/Tokyo'))
        )
        
        embed.add_field(name="通報理由", value=reason, inline=False)
        embed.add_field(name="通報されたユーザー", value=f"{self.target_member.mention}\nID: {self.target_member.id}", inline=True)
        embed.add_field(name="通報者", value=f"{interaction.user.mention}\nID: {interaction.user.id}", inline=True)
        embed.add_field(name="アカウント作成日", value=self.target_member.created_at.strftime("%Y-%m-%d"), inline=True)
        embed.add_field(name="サーバー参加日", value=self.target_member.joined_at.strftime("%Y-%m-%d"), inline=True)
        
        # 過去の通報履歴
        past_reports = await self._get_past_reports(self.target_member.id)
        if past_reports > 0:
            embed.add_field(name="⚠️ 過去の通報", value=f"{past_reports}件", inline=True)
        
        # ユーザーのロール情報
        roles = [role.name for role in self.target_member.roles if role.name != "@everyone"]
        if roles:
            embed.add_field(name="ロール", value=", ".join(roles[:5]), inline=False)
        
        await mod_channel.send(embed=embed)

    async def _record_user_report(self, interaction: discord.Interaction, reason: str):
        """通報の記録"""
        # データベースに通報を記録
        # 実装は具体的なデータベース構造に依存
        pass

    async def _get_past_reports(self, user_id: int) -> int:
        """過去の通報件数を取得"""
        # データベースから過去の通報件数を取得
        # 実装は具体的なデータベース構造に依存
        return 0
```

### 3. 設定管理 (`settings.py`)

**目的**: レポートシステムの設定管理

**主要機能**:
- モデレーションチャンネルの設定
- モデレーターロールの設定
- 通報設定の管理
- 自動アクション設定

**実装例**:

```python
class ReportSettingsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config_cache = {}

    @app_commands.command(name="report_setup", description="通報システムの設定")
    @app_commands.describe(
        channel="モデレーション通知を送信するチャンネル",
        role="モデレーターロール"
    )
    async def setup_report_system(
        self, 
        interaction: discord.Interaction, 
        channel: discord.TextChannel,
        role: discord.Role
    ):
        """通報システムの初期設定"""
        
        # 権限チェック
        if not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message("この機能を使用する権限がありません。", ephemeral=True)
            return
        
        # 設定の保存
        await self.save_config(interaction.guild.id, channel.id)
        await self.save_mod_role(interaction.guild.id, role.id)
        
        embed = discord.Embed(
            title="✅ 通報システム設定完了",
            description="通報システムが正常に設定されました。",
            color=0x00FF00
        )
        embed.add_field(name="モデレーションチャンネル", value=channel.mention, inline=True)
        embed.add_field(name="モデレーターロール", value=role.mention, inline=True)
        
        await interaction.response.send_message(embed=embed)

    @staticmethod
    async def load_config(guild_id: int) -> Optional[int]:
        """ギルドの設定を読み込み"""
        try:
            with open(f"config/report_config_{guild_id}.json", "r") as f:
                config = json.load(f)
                return config.get("mod_channel_id")
        except FileNotFoundError:
            return None

    @staticmethod
    async def save_config(guild_id: int, channel_id: int):
        """ギルドの設定を保存"""
        config = {"mod_channel_id": channel_id}
        os.makedirs("config", exist_ok=True)
        with open(f"config/report_config_{guild_id}.json", "w") as f:
            json.dump(config, f, indent=2)

    @staticmethod
    async def load_mod_role(guild_id: int) -> Optional[int]:
        """モデレーターロールIDを読み込み"""
        try:
            with open(f"config/report_config_{guild_id}.json", "r") as f:
                config = json.load(f)
                return config.get("mod_role_id")
        except FileNotFoundError:
            return None

    @staticmethod
    async def save_mod_role(guild_id: int, role_id: int):
        """モデレーターロールIDを保存"""
        try:
            with open(f"config/report_config_{guild_id}.json", "r") as f:
                config = json.load(f)
        except FileNotFoundError:
            config = {}
        
        config["mod_role_id"] = role_id
        os.makedirs("config", exist_ok=True)
        with open(f"config/report_config_{guild_id}.json", "w") as f:
            json.dump(config, f, indent=2)

    @app_commands.command(name="report_stats", description="通報統計の表示")
    async def show_report_stats(self, interaction: discord.Interaction):
        """通報統計の表示"""
        
        # 権限チェック
        mod_role_id = await self.load_mod_role(interaction.guild.id)
        if mod_role_id:
            mod_role = interaction.guild.get_role(mod_role_id)
            if mod_role not in interaction.user.roles and not interaction.user.guild_permissions.manage_guild:
                await interaction.response.send_message("この機能を使用する権限がありません。", ephemeral=True)
                return
        
        # 統計データの取得
        stats = await self._get_report_statistics(interaction.guild.id)
        
        embed = discord.Embed(
            title="📊 通報統計",
            description="過去30日間の通報統計",
            color=0x0099FF
        )
        
        embed.add_field(name="総通報数", value=stats.get("total_reports", 0), inline=True)
        embed.add_field(name="メッセージ通報", value=stats.get("message_reports", 0), inline=True)
        embed.add_field(name="ユーザー通報", value=stats.get("user_reports", 0), inline=True)
        
        # 最も多い通報理由
        top_reasons = stats.get("top_reasons", [])
        if top_reasons:
            reasons_text = "\n".join([f"{i+1}. {reason['name']}: {reason['count']}件" for i, reason in enumerate(top_reasons[:5])])
            embed.add_field(name="主な通報理由", value=reasons_text, inline=False)
        
        await interaction.response.send_message(embed=embed)

    async def _get_report_statistics(self, guild_id: int) -> Dict[str, Any]:
        """通報統計の取得"""
        # データベースから統計を取得
        # 実装は具体的なデータベース構造に依存
        return {
            "total_reports": 0,
            "message_reports": 0,
            "user_reports": 0,
            "top_reasons": []
        }
```

## 通報処理フロー

### 1. メッセージ通報フロー

```
1. ユーザーがメッセージを右クリック
   ↓
2. "メッセージを運営に通報" を選択
   ↓
3. 通報理由選択UI表示
   ↓
4. 理由選択 or カスタム理由入力
   ↓
5. モデレーションチャンネルに通知
   ↓
6. データベースに記録
   ↓
7. 確認メッセージ表示
```

### 2. ユーザー通報フロー

```
1. ユーザープロフィールを右クリック
   ↓
2. "ユーザーを通報" を選択
   ↓
3. 通報理由選択UI表示
   ↓
4. 理由選択 or カスタム理由入力
   ↓
5. 過去の通報履歴確認
   ↓
6. モデレーションチャンネルに通知
   ↓
7. 自動アクション判定
   ↓
8. データベースに記録
```

## データベース設計

### 通報テーブル構造

```sql
-- メッセージ通報テーブル
CREATE TABLE message_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER NOT NULL,
    reporter_id INTEGER NOT NULL,
    reported_message_id INTEGER NOT NULL,
    reported_user_id INTEGER NOT NULL,
    channel_id INTEGER NOT NULL,
    reason TEXT NOT NULL,
    custom_reason TEXT,
    status TEXT DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMP,
    resolved_by INTEGER,
    resolution_note TEXT
);

-- ユーザー通報テーブル
CREATE TABLE user_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER NOT NULL,
    reporter_id INTEGER NOT NULL,
    reported_user_id INTEGER NOT NULL,
    reason TEXT NOT NULL,
    custom_reason TEXT,
    status TEXT DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMP,
    resolved_by INTEGER,
    resolution_note TEXT
);

-- 通報設定テーブル
CREATE TABLE report_settings (
    guild_id INTEGER PRIMARY KEY,
    mod_channel_id INTEGER,
    mod_role_id INTEGER,
    auto_action_enabled BOOLEAN DEFAULT FALSE,
    auto_action_threshold INTEGER DEFAULT 3,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## 自動アクション機能

### 1. 閾値ベースアクション

```python
class AutoActionManager:
    def __init__(self, bot):
        self.bot = bot
        self.action_thresholds = {
            "warning": 2,      # 2回通報で警告
            "timeout": 3,      # 3回通報でタイムアウト
            "kick": 5,         # 5回通報でキック
            "ban": 7           # 7回通報でBAN
        }

    async def check_auto_action(self, guild_id: int, user_id: int):
        """自動アクション判定"""
        report_count = await self._get_recent_report_count(guild_id, user_id)
        
        for action, threshold in self.action_thresholds.items():
            if report_count >= threshold:
                await self._execute_auto_action(guild_id, user_id, action)
                break

    async def _execute_auto_action(self, guild_id: int, user_id: int, action: str):
        """自動アクションの実行"""
        guild = self.bot.get_guild(guild_id)
        member = guild.get_member(user_id)
        
        if not member:
            return
        
        if action == "warning":
            await self._send_warning(member)
        elif action == "timeout":
            await self._timeout_member(member)
        elif action == "kick":
            await self._kick_member(member)
        elif action == "ban":
            await self._ban_member(member)

    async def _get_recent_report_count(self, guild_id: int, user_id: int) -> int:
        """最近の通報件数を取得"""
        # 過去7日間の通報件数を取得
        # データベース実装に依存
        return 0
```

## セキュリティ機能

### 1. 通報スパム防止

```python
class ReportSpamProtection:
    def __init__(self):
        self.report_cooldowns = {}  # user_id -> last_report_time
        self.cooldown_duration = 300  # 5分

    def can_report(self, user_id: int) -> bool:
        """通報可能かチェック"""
        now = time.time()
        last_report = self.report_cooldowns.get(user_id, 0)
        
        if now - last_report < self.cooldown_duration:
            return False
        
        self.report_cooldowns[user_id] = now
        return True

    def get_remaining_cooldown(self, user_id: int) -> int:
        """残りクールダウン時間を取得"""
        now = time.time()
        last_report = self.report_cooldowns.get(user_id, 0)
        remaining = self.cooldown_duration - (now - last_report)
        return max(0, int(remaining))
```

### 2. 虚偽通報検出

```python
class FalseReportDetector:
    def __init__(self):
        self.false_report_threshold = 3

    async def check_false_reports(self, reporter_id: int, guild_id: int) -> bool:
        """虚偽通報の検出"""
        false_reports = await self._count_false_reports(reporter_id, guild_id)
        
        if false_reports >= self.false_report_threshold:
            await self._handle_false_reporter(reporter_id, guild_id)
            return True
        
        return False

    async def _count_false_reports(self, reporter_id: int, guild_id: int) -> int:
        """虚偽通報件数の取得"""
        # データベースから虚偽通報件数を取得
        return 0

    async def _handle_false_reporter(self, reporter_id: int, guild_id: int):
        """虚偽通報者への対応"""
        # 通報機能の一時停止など
        pass
```

---

## 関連ドキュメント

- [Cogsアーキテクチャ](01-cogs-architecture.md)
- [管理Cogs](04-management-cogs.md)
- [エラーハンドリング](../02-core/04-error-handling.md)
- [データベース管理](../04-utilities/01-database-management.md)
