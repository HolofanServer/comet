# ツールCogs

## C.O.M.E.T.について

**C.O.M.E.T.**の名前は以下の頭文字から構成されています：

- **C**ommunity of
- **O**shilove
- **M**oderation &
- **E**njoyment
- **T**ogether

HFS - ホロライブ非公式ファンサーバーのコミュニティを支える、推し愛とモデレーション、そして楽しさを一緒に提供するボットです。

## 概要

ツールCogsは、サーバーメンバーと管理者向けのユーティリティ機能、分析機能、インタラクティブ機能を提供します。

## 利用可能なツールCogs

### 詳細ドキュメント

以下の機能には詳細なドキュメントがあります：

- [**ホロライブおみくじシステム**](05-tool-cogs/01-omikuji-system.md) - 電脳桜神社おみくじ・タロット運勢
- [**ギブアウェイシステム**](05-tool-cogs/02-giveaway-system.md) - 自動抽選システム

### 1. ホロライブおみくじ (`omikuji.py`)

**目的**: みこちをテーマにした日本の伝統的なおみくじとVtuber文化の融合

**主要機能**:
- **1日1回おみくじ**: `/omikuji` - 電脳桜神社でおみくじを引く
- **タロット運勢**: `/fortune` - みおしゃのタロット占い
- **ランキング**: `/ranking` - 連続参拝ランキング
- **運勢管理**: `/cyber` - カスタム運勢の追加・削除

**特徴**:
- 連続参拝ボーナスシステム
- データベース完全管理
- ホロライブキャラクター演出
- 超レア・チャンス演出

📖 [詳細ドキュメント](05-tool-cogs/01-omikuji-system.md)

### 2. ギブアウェイ (`giveaway.py`)

**目的**: サーバー内で賞品を抽選する自動化システム

**主要機能**:
- **ギブアウェイ作成**: `/giveaway` - 期間・賞品指定で開始
- **再抽選**: `/reroll` - 終了後の当選者再抽選

**特徴**:
- リアクションベースの参加
- Bot再起動後も継続
- 自動終了・当選者発表
- PostgreSQL永続化

📖 [詳細ドキュメント](05-tool-cogs/02-giveaway-system.md)

### 3. ユーザーアナライザー (`user_analyzer.py`)

**目的**: OpenAI GPT-4を使用したユーザー行動とコミュニケーションパターンのAI分析。

**主要機能**:
- **メッセージ収集**: サーバーチャンネルからユーザーメッセージをスキャン
- **AI分析**: GPT-4を使用してコミュニケーションパターンを分析
- **包括的レポート**: 詳細な性格と行動の洞察を生成
- **ファイル出力**: 分析結果をMarkdownファイルとして保存
- **進捗追跡**: 分析中のリアルタイム進捗更新

**実装詳細**:
```python
@app_commands.command(name="user_analyze")
@is_guild_app()
@is_owner_app()
async def analyze_user(self, interaction, user: discord.Member, 
                      channel_limit: Optional[int] = None,
                      message_limit: Optional[int] = None):
```

**分析プロセス**:
1. **メッセージ収集**: 指定されたチャンネルからユーザーメッセージをスキャン
2. **データフォーマット**: タイムスタンプ、リアクション、添付ファイル付きでメッセージを構造化
3. **AI処理**: 分析のためにOpenAI GPT-4にデータを送信
4. **レポート生成**: 包括的な性格分析を作成
5. **ファイル保存**: 結果を`cache/user_analysis/`に保存

**分析カテゴリ**:
- コミュニケーションスタイルとパターン
- トピックの好みと興味
- 感情的傾向
- 社会的相互作用パターン
- 言語使用特性
- 性格特性評価

### 2. バグレポーター (`bug.py`)

**目的**: ユーザーが開発者に直接問題を報告するための合理化されたバグ報告システム。

**主要機能**:
- **DM専用インターフェース**: ダイレクトメッセージによるプライベートバグ報告
- **画像添付**: スクリーンショット添付のサポート
- **自動転送**: 指定されたバグ報告チャンネルにレポートをルーティング
- **ユーザーフレンドリー**: シンプルなコマンドインターフェース

**コマンド**:
```python
@commands.hybrid_command(name="bug_report")
@commands.dm_only()
async def bug_report(self, ctx, 内容: str, 画像: discord.Attachment = None):
```

### 3. メッセージアナライザー (`ms_ana.py`)

**目的**: モデレーションと洞察のためのメッセージパターンとコンテンツの分析。

**主要機能**:
- **メッセージパターン分析**: サーバーコミュニケーションのトレンドを特定
- **コンテンツ分析**: 様々な指標でメッセージコンテンツを検査
- **ファイル処理**: アップロードされたテキストファイルを分析可能
- **統計レポート**: 使用統計とパターンを生成

**コマンド**:
- `analyze`: 最近のサーバーメッセージを分析
- `analyze_file`: アップロードされたテキストファイルを分析

### 4. ウェルカムメッセージ (`welcom_message.py`)

**目的**: ウェルカムメッセージと新メンバーオンボーディングの管理。

**主要機能**:
- **カスタムウェルカムメッセージ**: 設定可能なウェルカムコンテンツ
- **チャンネル管理**: 特定のウェルカムチャンネルを設定
- **ロール割り当て**: 新メンバーへの自動ロール割り当て
- **パーソナライゼーション**: カスタマイズ可能なウェルカム体験

**コマンド**:
```python
@commands.hybrid_command(name="set_welcome_channel")
@is_guild()
@is_owner()
async def set_welcome_channel(self, ctx, channel: discord.TextChannel):
```

### 5. 追加ツールCogs

コードベース構造に基づく追加ツールCogsには以下が含まれます:

- **アナウンスメント新** (`announcement_new.py`): 高度なアナウンスシステム
- **レコーダー** (`recorder.py`): 音声/アクティビティ録音機能
- **推しロールパネル** (`oshi_role_panel.py`): ロール選択インターフェース
- **カスタムアナウンスメント** (`custom_announcement.py`): カスタマイズ可能なアナウンス
- **サーバー統計** (`server_stats.py`): リアルタイムサーバー統計
- **CV2テスト** (`cv2_test.py`): コンピュータビジョンテストツール

## 共通パターン

### 権限デコレーター
```python
@is_guild_app()      # Guild-only slash commands
@is_owner_app()      # Owner-only slash commands
@is_guild()          # Guild-only prefix commands
@is_owner()          # Owner-only prefix commands
@log_commands()      # Command usage logging
```

### エラーハンドリング
```python
try:
    # Tool operation
    result = await perform_analysis()
    await interaction.response.send_message(f"✅ {result}")
except Exception as e:
    logger.error(f"Tool operation failed: {e}")
    await interaction.response.send_message(f"❌ Operation failed: {e}")
```

### 非同期タスク管理
```python
# For long-running operations
task = asyncio.create_task(long_running_analysis())
self.analysis_tasks[user.id] = task
```

## 設定

### APIキー
ツールCogsは外部API アクセスを必要とすることが多いです:
```python
OPENAI_API_KEY = settings.etc_api_openai_api_key
async_client_ai = AsyncOpenAI(api_key=OPENAI_API_KEY)
```

### ファイルストレージ
結果は通常、整理されたディレクトリに保存されます:
```
cache/
├── user_analysis/
│   └── analysis_123456_20240101_120000.md
├── message_data/
└── reports/
```

### レート制限
コマンドは適切なレート制限を実装します:
```python
@commands.cooldown(1, 30, commands.BucketType.user)
```

## 使用例

### ユーザー分析
```
/user_analyze user:@username channel_limit:10 message_limit:500
```

### バグ報告
```
/bug_report 内容:"Bot crashes when using command" 画像:[screenshot.png]
```

### ウェルカム設定
```
/set_welcome_channel channel:#welcome
```

---

## 関連ドキュメント

- [AI統合](../04-utilities/03-ai-integration.md)
- [ファイル管理](../04-utilities/04-file-management.md)
- [コマンドカテゴリ](../06-commands/01-command-categories.md)
- [エラーハンドリング](../02-core/04-error-handling.md)
