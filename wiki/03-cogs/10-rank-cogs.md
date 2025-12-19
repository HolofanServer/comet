# ランク & レベリングシステム

## 概要

HFS Rankシステムは、Discordサーバー内のユーザー活動を追跡し、XPとレベルを管理する機能を提供します。メッセージ送信、VC参加、リアクション、おみくじなどの活動に応じてXPを付与し、レベルアップや常連ロールの自動付与を行います。

## システムアーキテクチャ

```
cogs/rank/
├── __init__.py                    # Cogs セットアップ・エントリーポイント
├── ranking.py                     # メインCog・コマンド実装
├── service.py                     # XP計算・付与ロジック
├── models.py                      # データモデル・DBアクセス
└── logging.py                     # イベントログ収集Cog
```

## 主要機能

### 1. XP計算システム

#### RankService

XP計算と付与を担当するサービスクラス：

```python
class RankService:
    """Rankサービスクラス"""
    
    def calculate_final_xp(
        self,
        base_xp: int,
        content: str,
        channel_id: int,
        streak: int,
        config: RankConfig,
    ) -> int:
        """
        最終的なXPを計算（全ての倍率・ボーナスを適用）
        """
        # 品質ボーナス
        quality_bonus = self._calculate_quality_bonus(content) if config.quality_bonus_enabled else 0
        
        # ストリーク倍率
        streak_multiplier = self._calculate_streak_multiplier(streak) if config.streak_bonus_enabled else 1.0
        
        # チャンネル倍率
        channel_multiplier = self._get_channel_multiplier(channel_id, config)
        
        # グローバル倍率（イベント用）
        global_multiplier = config.global_multiplier
        
        # 最終XP計算
        final_xp = (base_xp + quality_bonus) * streak_multiplier * channel_multiplier * global_multiplier
        return int(final_xp)
```

#### メッセージ品質ボーナス

```python
def _calculate_quality_bonus(self, content: str) -> int:
    """
    メッセージ品質に応じたボーナスXPを計算
    - 長文（100文字以上）: +2 XP
    - 長文（50文字以上）: +1 XP
    - 絵文字/カスタム絵文字: +1 XP
    - URL含む: +1 XP
    - 最大5XPまで
    """
    bonus = 0
    if len(content) >= 100:
        bonus += 2
    elif len(content) >= 50:
        bonus += 1
    # 絵文字・URL検出...
    return min(bonus, 5)
```

### 2. カスタマイズ可能なレベル公式

#### 公式タイプ

```python
class FormulaType(Enum):
    LINEAR = "linear"              # level * base_requirement
    EXPONENTIAL = "exponential"    # (level ** 2) * multiplier
    LOGARITHMIC = "logarithmic"    # 100 * log(level + 1) * base
    MEE6_STYLE = "mee6_style"      # 5*(level**2) + 50*level + 100
    CUSTOM = "custom"              # ユーザー定義式
```

#### カスタム公式エンジン

```python
class CustomProgressionEngine:
    """カスタムレベル進行エンジン"""
    
    def __init__(self, formula_type: str, params: dict):
        self.formula_functions = {
            'linear': lambda lvl: lvl * params.get('base_requirement', 100),
            'exponential': lambda lvl: int((lvl ** 2) * params.get('exp_multiplier', 50)),
            'logarithmic': lambda lvl: int(100 * math.log(lvl + 1) * params.get('log_base', 10)),
            'mee6_style': lambda lvl: 5 * (lvl ** 2) + (50 * lvl) + 100,
            'custom': lambda lvl: self._eval_custom_formula(lvl, params['custom_formula'])
        }
        self.active_formula = self.formula_functions[formula_type]
    
    def xp_required_for_level(self, level: int) -> int:
        """指定レベルに必要な累積XP"""
        return sum(self.active_formula(i) for i in range(1, level + 1))
```

#### 公式管理コマンド

```python
# レベル公式の作成
@commands.command()
@commands.has_permissions(manage_guild=True)
async def create_formula(self, ctx, name: str, formula_type: str):
    """新しいレベル公式を作成"""
    await self.formula_manager.create_formula(
        guild_id=ctx.guild.id,
        name=name,
        formula_type=formula_type,
        parameters={}
    )

# 公式のアクティブ化
@commands.command()
@commands.has_permissions(manage_guild=True)
async def activate_formula(self, ctx, formula_id: int):
    """レベル公式をアクティブ化"""
    await self.formula_manager.activate_formula(
        guild_id=ctx.guild.id,
        formula_id=formula_id
    )
```

### 3. ボイスアクティビティ追跡

#### 品質ベースのXP付与

```python
class VoiceTracker:
    """ボイスチャンネルアクティビティ追跡"""
    
    async def calculate_voice_xp(
        self,
        user_id: int,
        duration: int,  # 秒数
        quality_factors: dict
    ) -> int:
        """
        ボイスアクティビティXP計算
        
        品質要素:
        - アクティブ人数（2人以上）
        - ミュート状態
        - カメラ使用
        - 画面共有
        """
        base_xp_per_minute = 5
        
        # 品質乗数
        multipliers = {
            'active_participants': quality_factors.get('participants', 1) * 0.2,
            'not_muted': 1.5 if not quality_factors.get('muted', True) else 0.5,
            'camera_on': 1.3 if quality_factors.get('camera', False) else 1.0,
            'screen_share': 1.2 if quality_factors.get('screen_share', False) else 1.0
        }
        
        minutes = duration / 60
        total_multiplier = reduce(lambda x, y: x * y, multipliers.values())
        
        return int(base_xp_per_minute * minutes * total_multiplier)
```

#### ボイスイベント処理

```python
@commands.Cog.listener()
async def on_voice_state_update(
    self,
    member: discord.Member,
    before: discord.VoiceState,
    after: discord.VoiceState
):
    """ボイス状態変更の追跡"""
    
    # VC参加
    if before.channel is None and after.channel is not None:
        await self.voice_manager.start_session(
            user_id=member.id,
            channel_id=after.channel.id
        )
    
    # VC退出
    elif before.channel is not None and after.channel is None:
        session_data = await self.voice_manager.end_session(
            user_id=member.id
        )
        
        # XP計算・付与
        xp = await self.calculate_voice_xp(
            user_id=member.id,
            duration=session_data['duration'],
            quality_factors=session_data['quality']
        )
        
        await self.add_xp(member.id, xp, source='voice')
```

### 4. 実績システム

#### 実績タイプ

```python
class AchievementType(Enum):
    MESSAGE_COUNT = "message_count"       # メッセージ数
    LEVEL_MILESTONE = "level_milestone"   # レベル到達
    VOICE_TIME = "voice_time"             # ボイス時間
    STREAK = "streak"                     # 連続日数
    SOCIAL = "social"                     # ソーシャル活動
    SPECIAL = "special"                   # 特別イベント
```

#### 実績定義

```python
achievements = [
    {
        'id': 'first_message',
        'name': '最初の一歩',
        'description': '最初のメッセージを送信',
        'type': AchievementType.MESSAGE_COUNT,
        'requirement': 1,
        'reward_xp': 50,
        'icon': '🎉'
    },
    {
        'id': 'level_10',
        'name': '駆け出し',
        'description': 'レベル10に到達',
        'type': AchievementType.LEVEL_MILESTONE,
        'requirement': 10,
        'reward_xp': 500,
        'icon': '⭐'
    },
    {
        'id': 'voice_1hour',
        'name': 'おしゃべり',
        'description': 'ボイスチャンネルで1時間',
        'type': AchievementType.VOICE_TIME,
        'requirement': 3600,
        'reward_xp': 300,
        'icon': '🎤'
    },
    {
        'id': 'week_streak',
        'name': '継続は力なり',
        'description': '7日連続でアクティブ',
        'type': AchievementType.STREAK,
        'requirement': 7,
        'reward_xp': 1000,
        'icon': '🔥'
    }
]
```

#### 実績チェック

```python
class AchievementManager:
    """実績管理システム"""
    
    async def check_achievements(
        self,
        user_id: int,
        guild_id: int,
        event_type: str,
        value: int
    ):
        """実績条件チェック・付与"""
        
        user_achievements = await self.get_user_achievements(user_id, guild_id)
        unlocked = []
        
        for achievement in self.achievements:
            # 既に取得済みならスキップ
            if achievement['id'] in user_achievements:
                continue
                
            # 条件チェック
            if self._check_requirement(achievement, event_type, value):
                # 実績付与
                await self.unlock_achievement(
                    user_id,
                    guild_id,
                    achievement['id']
                )
                
                # 報酬XP付与
                await self.add_xp(user_id, achievement['reward_xp'])
                
                unlocked.append(achievement)
        
        return unlocked
```

## データベーススキーマ

### ユーザーXPテーブル

```sql
CREATE TABLE user_xp (
    user_id BIGINT,
    guild_id BIGINT,
    total_xp BIGINT DEFAULT 0,
    current_level INTEGER DEFAULT 1,
    message_xp BIGINT DEFAULT 0,
    voice_xp BIGINT DEFAULT 0,
    message_count INTEGER DEFAULT 0,
    last_activity TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    streak_count INTEGER DEFAULT 0,
    PRIMARY KEY (guild_id, user_id)
) PARTITION BY HASH (guild_id);

CREATE INDEX idx_guild_xp_ranking ON user_xp (guild_id, total_xp DESC);
CREATE INDEX idx_activity_time ON user_xp (guild_id, last_activity);
```

### レベル公式テーブル

```sql
CREATE TABLE level_formulas (
    formula_id SERIAL PRIMARY KEY,
    guild_id BIGINT NOT NULL,
    name TEXT NOT NULL,
    formula_type TEXT NOT NULL,
    parameters JSONB DEFAULT '{}',
    is_active BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX idx_guild_active_formula 
ON level_formulas (guild_id) 
WHERE is_active = TRUE;
```

### ボイスアクティビティテーブル

```sql
CREATE TABLE voice_sessions (
    session_id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    guild_id BIGINT NOT NULL,
    channel_id BIGINT NOT NULL,
    start_time TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    end_time TIMESTAMP WITH TIME ZONE,
    duration INTEGER,
    xp_earned INTEGER DEFAULT 0,
    quality_data JSONB DEFAULT '{}'
);

CREATE INDEX idx_active_sessions 
ON voice_sessions (user_id, guild_id) 
WHERE end_time IS NULL;
```

### 実績テーブル

```sql
CREATE TABLE achievements (
    achievement_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT NOT NULL,
    type TEXT NOT NULL,
    requirement INTEGER NOT NULL,
    reward_xp INTEGER DEFAULT 0,
    icon TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE user_achievements (
    user_id BIGINT,
    guild_id BIGINT,
    achievement_id TEXT,
    unlocked_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (guild_id, user_id, achievement_id),
    FOREIGN KEY (achievement_id) REFERENCES achievements(achievement_id)
);

CREATE INDEX idx_user_achievements ON user_achievements (guild_id, user_id);
```

### 品質キャッシュテーブル

```sql
CREATE TABLE quality_cache (
    cache_id SERIAL PRIMARY KEY,
    message_id BIGINT UNIQUE,
    user_id BIGINT NOT NULL,
    quality_score FLOAT NOT NULL,
    analyzed_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_quality_cache_message ON quality_cache (message_id);
CREATE INDEX idx_quality_cache_expiry ON quality_cache (analyzed_at);
```

## コマンドリファレンス

### ユーザーコマンド

#### `/rank [user]`
ランクを表示

**パラメータ**:
- `user` (オプション): 表示するユーザー（省略時は自分）

**表示内容**:
- 順位
- レベル・XP
- 次レベルまでの進捗バー
- 連続ログイン日数（ストリークボーナス表示）
- アクティブ日数
- 通算XP

#### `/ranktop [category]`
XPランキングを表示

**パラメータ**:
- `category` (オプション): ランキングカテゴリ
  - `yearly_xp` (デフォルト): 今年のXP
  - `lifetime_xp`: 通算XP
  - `active_days`: アクティブ日数

**表示内容**:
- トップ10ユーザー
- レベル・XP

#### `/top`
サーバーのランキング一覧を表示

**表示内容**:
- メッセージ送信者ランキング（Top5）
- ボイチャ勢ランキング（Top5）
- XPランキング（Top5）
- おみくじ勢ランキング（Top5）

### 管理者コマンド

#### `/rank-settings view`
現在の設定を表示

**必要権限**: Moderator

**表示内容**:
- ステータス（有効/無効）
- XP設定（メッセージ、おみくじ、VC）
- 常連ロール設定
- 除外ロール・チャンネル

#### `/rank-settings toggle`
Rankシステムの有効/無効を切り替え

**必要権限**: Moderator

#### `/rank-settings exclude-role <action> <role>`
除外ロールを追加/削除

**必要権限**: Moderator

**パラメータ**:
- `action`: `追加` | `削除`
- `role`: 対象のロール

#### `/rank-settings exclude-channel <action> <channel>`
除外チャンネルを追加/削除

**必要権限**: Moderator

**パラメータ**:
- `action`: `追加` | `削除`
- `channel`: 対象のチャンネル

#### `/rank-settings xp [message_xp] [omikuji_xp] [vc_xp] [cooldown]`
XP設定を変更

**必要権限**: Moderator

**パラメータ**:
- `message_xp` (オプション): メッセージXP
- `omikuji_xp` (オプション): おみくじXP
- `vc_xp` (オプション): VC XP（10分あたり）
- `cooldown` (オプション): クールダウン秒数

#### `/rank-settings regular <role> [xp_threshold] [days_threshold]`
常連ロール設定を変更

**必要権限**: Moderator

**パラメータ**:
- `role`: 常連ロール
- `xp_threshold` (オプション): 必要XP
- `days_threshold` (オプション): 必要日数

#### `/rank-settings regular-clear`
常連ロール設定をクリア

**必要権限**: Moderator

### 管理者専用コマンド（rank-admin）

#### `/rank-admin add-xp <user> <amount>`
XPを手動付与

**必要権限**: Administrator

#### `/rank-admin remove-xp <user> <amount>`
XPを手動削除

**必要権限**: Administrator

#### `/rank-admin set-xp <user> <yearly_xp> [lifetime_xp]`
XPを直接設定

**必要権限**: Administrator

#### `/rank-admin reset <user>`
ユーザーのランクデータをリセット

**必要権限**: Administrator

#### `/rank-admin check <user>`
ユーザーの詳細データを確認

**必要権限**: Administrator

#### `/rank-admin channel-multiplier <channel> <multiplier>`
チャンネルXP倍率を設定

**必要権限**: Administrator

**パラメータ**:
- `channel`: 対象チャンネル
- `multiplier`: 倍率（0.0〜5.0）

#### `/rank-admin event <multiplier>`
グローバルXP倍率を設定（イベント用）

**必要権限**: Administrator

**パラメータ**:
- `multiplier`: 倍率（0.5〜5.0）

## セットアップガイド

### 1. データベーステーブル

Rankシステムは以下のテーブルを使用します（CP Databaseに作成）：

```sql
-- ユーザーランク情報
CREATE TABLE rank_users (
    user_id BIGINT NOT NULL,
    guild_id BIGINT NOT NULL,
    yearly_xp INTEGER DEFAULT 0,
    lifetime_xp BIGINT DEFAULT 0,
    active_days INTEGER DEFAULT 0,
    current_level INTEGER DEFAULT 1,
    is_regular BOOLEAN DEFAULT FALSE,
    current_streak INTEGER DEFAULT 0,
    last_message_xp_at TIMESTAMP WITH TIME ZONE,
    last_omikuji_xp_date DATE,
    last_active_date DATE,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, guild_id)
);

-- ギルド設定
CREATE TABLE rank_config (
    guild_id BIGINT PRIMARY KEY,
    message_xp INTEGER DEFAULT 5,
    message_cooldown_seconds INTEGER DEFAULT 60,
    omikuji_xp INTEGER DEFAULT 15,
    vc_xp_per_10min INTEGER DEFAULT 5,
    regular_xp_threshold INTEGER DEFAULT 10000,
    regular_days_threshold INTEGER DEFAULT 50,
    regular_role_id BIGINT,
    excluded_channels BIGINT[],
    excluded_roles BIGINT[],
    is_enabled BOOLEAN DEFAULT TRUE,
    streak_bonus_enabled BOOLEAN DEFAULT TRUE,
    quality_bonus_enabled BOOLEAN DEFAULT TRUE,
    channel_multipliers JSONB,
    global_multiplier FLOAT DEFAULT 1.0,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- レベル閾値
CREATE TABLE rank_levels (
    level INTEGER PRIMARY KEY,
    required_xp INTEGER NOT NULL
);
```

### 2. Cogsロード

Rankシステムは自動的にロードされます：

```python
# cogs/rank/__init__.py
from .logging import RankLogging
from .ranking import RankCommands

async def setup(bot):
    await bot.add_cog(RankLogging(bot))
    await bot.add_cog(RankCommands(bot))
```

### 3. 初期設定

サーバーでRankシステムを有効化するには：

1. `/rank-settings view` で現在の設定を確認
2. `/rank-settings toggle` で有効化
3. `/rank-settings regular <role>` で常連ロールを設定
4. `/rank-settings exclude-channel` で除外チャンネルを設定

## 関連ドキュメント

- [データベース管理](../04-utilities/01-database-management.md)
- [チェックポイントシステム](./12-cp-cogs.md)
- [パフォーマンス最適化](../05-development/02-monitoring-debugging.md)
