# ランク & レベリングシステム

## 概要

COMET ボットの高度なレベリング・実績システムは、従来のメッセージカウント方式を超越した、多次元エンゲージメント評価を実現します。カスタマイズ可能なレベル公式、ボイスアクティビティ追跡、AI品質分析、実績システムを統合した包括的なコミュニティエンゲージメントプラットフォームです。

## システムアーキテクチャ

```
rank/
├── __init__.py                    # ランクモジュールエクスポート
├── rank.py                        # メインランクCog
├── rank_config.py                 # ランク設定管理
├── voice_config.py                # ボイス設定管理
├── voice_tracker.py               # ボイスアクティビティ追跡
├── formula_config.py              # レベル公式設定
└── achievements.py                # 実績システムCog

models/rank/
├── __init__.py
├── level_config.py                # レベル設定モデル
├── level_formula.py               # レベル公式モデル
├── voice_activity.py              # ボイスアクティビティモデル
├── achievements.py                # 実績モデル
└── quality_analysis.py            # 品質分析モデル

utils/rank/
├── __init__.py
├── formula_manager.py             # レベル公式マネージャー
├── voice_manager.py               # ボイスマネージャー
├── quality_analyzer.py            # AI品質分析
├── achievement_manager.py         # 実績マネージャー
└── ai_config.py                   # AI設定
```

## 主要機能

### 1. 高度なXP計算システム

#### 多次元エンゲージメント評価

従来の単純なメッセージカウントではなく、複数の要素を総合評価：

```python
class AdvancedXPCalculator:
    """高度なXP計算エンジン"""
    
    async def calculate_xp(
        self, 
        message: discord.Message,
        guild_config: GuildConfig
    ) -> int:
        base_xp = guild_config.base_xp_per_message
        
        # 複数要素による動的XP計算
        multipliers = {
            'message_quality': await self._analyze_message_quality(message),
            'interaction_density': await self._calculate_interaction_score(message),
            'time_context': self._get_time_multiplier(message.created_at),
            'channel_importance': guild_config.channel_weights.get(message.channel.id, 1.0),
            'streak_bonus': await self._calculate_streak_multiplier(message.author.id),
            'community_engagement': await self._measure_social_impact(message)
        }
        
        final_xp = base_xp * reduce(lambda x, y: x * y, multipliers.values())
        return int(final_xp * guild_config.global_multiplier)
```

#### AI品質分析

```python
class QualityAnalyzer:
    """AI搭載メッセージ品質分析"""
    
    async def analyze_message_quality(self, content: str) -> float:
        """
        メッセージの質を分析
        
        評価基準:
        - 文章の長さと構造
        - 語彙の多様性
        - 建設的な内容
        - スパム/低品質検出
        
        Returns:
            float: 品質スコア (0.5 ~ 2.0)
        """
        # 基本的な品質チェック
        if len(content) < 10:
            return 0.5  # 短すぎるメッセージ
            
        if self._is_spam(content):
            return 0.3  # スパム検出
            
        # AI分析（オプション）
        if self.ai_enabled:
            return await self._ai_analyze(content)
            
        # 基本的な品質評価
        return self._basic_quality_score(content)
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

#### `/rank [@user]`
ランクカードを表示

**パラメータ**:
- `user` (オプション): 表示するユーザー

**表示内容**:
- 現在レベル・XP
- 次レベルまでの進捗
- サーバー内順位
- メッセージ数・ボイス時間
- カスタマイズ可能なランクカード画像

#### `/leaderboard [page]`
リーダーボードを表示

**パラメータ**:
- `page` (オプション): ページ番号（1-based）

**表示内容**:
- トップ10ユーザー（ページネーション）
- レベル・総XP
- メッセージ数

#### `/achievements [@user]`
実績一覧を表示

**パラメータ**:
- `user` (オプション): 表示するユーザー

**表示内容**:
- 取得済み実績
- 未取得実績（進捗表示）
- 総実績数・取得率

### 管理者コマンド

#### `/rank_config`
ランクシステム設定

**必要権限**: `manage_guild`

**設定項目**:
- ベースXP（メッセージごと）
- グローバル乗数
- 除外チャンネル
- ロールリワード
- レベルアップ通知

#### `/formula_create <name> <type>`
レベル公式を作成

**必要権限**: `manage_guild`

**パラメータ**:
- `name`: 公式名
- `type`: `linear` | `exponential` | `logarithmic` | `mee6_style` | `custom`

#### `/formula_list`
公式一覧を表示

**必要権限**: `manage_guild`

#### `/formula_activate <formula_id>`
公式をアクティブ化

**必要権限**: `manage_guild`

#### `/add_xp <user> <amount>`
XPを手動付与

**必要権限**: `manage_guild`

#### `/remove_xp <user> <amount>`
XPを手動削除

**必要権限**: `manage_guild`

#### `/reset_user <user>`
ユーザーのレベルをリセット

**必要権限**: `administrator`

## セットアップガイド

### 1. データベースマイグレーション

```bash
# 順番に実行
psql $DATABASE_URL -f migrations/create_level_formulas.sql
psql $DATABASE_URL -f migrations/create_level_configs.sql
psql $DATABASE_URL -f migrations/create_voice_system.sql
psql $DATABASE_URL -f migrations/create_achievements_system.sql
psql $DATABASE_URL -f migrations/create_quality_cache.sql
```

### 2. 環境変数設定（オプション）

```bash
# AI品質分析を有効化する場合
RANK_AI_ENABLED=true
RANK_AI_MODEL=gpt-3.5-turbo

# キャッシュ設定
RANK_CACHE_ENABLED=true
RANK_CACHE_TTL=3600
```

### 3. Cogsロード

```python
@bot.event
async def on_ready():
    await bot.load_extension('rank.rank')
    await bot.load_extension('rank.achievements')
    await bot.load_extension('rank.voice_tracker')
    await bot.tree.sync()
```

### 4. デフォルト公式セットアップ

```python
# 初回セットアップ時に実行
await formula_manager.create_default_formula(
    guild_id=guild.id,
    formula_type='mee6_style'
)
```

## パフォーマンス最適化

### キャッシング戦略

```python
from functools import lru_cache
import redis.asyncio as redis

class RankCache:
    def __init__(self):
        self.redis = redis.from_url(os.getenv('REDIS_URL'))
        self.local_cache = {}
    
    @lru_cache(maxsize=1000)
    async def get_user_xp(self, user_id: int, guild_id: int):
        """L1: メモリキャッシュ"""
        cache_key = f"xp:{guild_id}:{user_id}"
        
        # L2: Redis
        cached = await self.redis.get(cache_key)
        if cached:
            return int(cached)
        
        # L3: データベース
        xp = await self.db.fetch_user_xp(user_id, guild_id)
        await self.redis.setex(cache_key, 3600, xp)
        
        return xp
```

### バッチ処理

```python
class BatchProcessor:
    """XP更新のバッチ処理"""
    
    def __init__(self):
        self.batch_queue = []
        self.batch_size = 100
        
    async def add_to_batch(self, user_id: int, guild_id: int, xp: int):
        """バッチキューに追加"""
        self.batch_queue.append((user_id, guild_id, xp))
        
        if len(self.batch_queue) >= self.batch_size:
            await self.flush_batch()
    
    async def flush_batch(self):
        """バッチを一括処理"""
        if not self.batch_queue:
            return
            
        await self.db.bulk_update_xp(self.batch_queue)
        self.batch_queue.clear()
```

## 関連ドキュメント

- [データベース管理](../04-utilities/01-database-management.md)
- [AI統合](../04-utilities/03-ai-integration.md)
- [パフォーマンス最適化](../05-development/02-monitoring-debugging.md)

## バージョン履歴

- **v2.0** (2025-11): 高度なシステム実装
  - AI品質分析統合
  - カスタムレベル公式
  - ボイスアクティビティ追跡
  - 実績システム
  - 多次元エンゲージメント評価
