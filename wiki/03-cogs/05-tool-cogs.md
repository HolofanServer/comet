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

### 5. リマインダー (`reminder.py`)

**目的**: 指定した時間にリマインダーを送信する機能。

**主要機能**:
- **時間指定**: 秒・分・時間・日・週の複合指定に対応
- **通知方法選択**: チャンネルまたはDMで通知
- **一覧表示**: 設定中のリマインダーを確認
- **キャンセル機能**: 不要なリマインダーを削除

**利用可能なコマンド**:
- `/remind`: リマインダーを設定（例: `/remind 30m 会議開始`）
- `/remind_list`: 設定中のリマインダー一覧
- `/remind_cancel`: リマインダーをキャンセル

**対応時間形式**:
- `30s`, `30秒` - 30秒後
- `5m`, `5分` - 5分後
- `2h`, `2時間` - 2時間後
- `1d`, `1日` - 1日後
- `1w`, `1週間` - 1週間後
- `1d2h30m` - 複合指定

### 6. スケジュール投稿 (`scheduled_post.py`)

**目的**: 指定した日時にメッセージを自動投稿。

**主要機能**:
- **柔軟な日時指定**: 絶対日時・相対時間・自然言語対応
- **繰り返し設定**: 毎日・毎週・毎月の定期投稿
- **チャンネル指定**: 任意のチャンネルに投稿
- **Embed対応**: リッチなメッセージ投稿

**利用可能なコマンド**:
- `/schedule`: スケジュール投稿を設定
- `/schedule_list`: スケジュール投稿一覧
- `/schedule_cancel`: スケジュール投稿をキャンセル

**対応日時形式**:
- `2024-12-25 09:00` - 年月日 時分
- `12/25 09:00` - 月日 時分（今年）
- `09:00` - 時分（今日または明日）
- `明日 09:00` - 明日の指定時刻
- `+30m`, `+2h`, `+1d` - 相対時間

### 7. 新規参加者フォローアップ (`newcomer_followup.py`)

**目的**: Week 1 Retention改善のための自動DMフォローアップシステム。

**主要機能**:
- **自動検知**: 新規メンバー参加時にDBに記録
- **条件付きDM**: 12時間経過+発言なしのユーザーにDM送信
- **発言追跡**: 発言検知時にフラグを更新
- **統計収集**: 効果測定用の統計情報

**利用可能なコマンド**:
- `/newcomer_followup status`: システム状態を確認
- `/newcomer_followup enable`: 機能の有効/無効切り替え
- `/newcomer_followup set_delay`: 待機時間を設定
- `/newcomer_followup set_channel`: 雑談チャンネルを設定
- `/newcomer_followup test`: テストDMを送信
- `/newcomer_followup preview`: DMプレビューを表示

### 8. 表示名スタイル (`display_name_style.py`)

**目的**: Botの表示名スタイル（フォント、エフェクト、カラー）をギルドごとに管理。

**主要機能**:
- **フォント設定**: 12種類のフォントから選択
- **エフェクト設定**: solid, gradient, neon, toon, pop, glow
- **カラー設定**: 最大2色のグラデーション指定
- **リセット機能**: デフォルトに戻す

**利用可能なコマンド**:
- `!style set <font> <effect> [colors...]`: スタイルを設定
- `!style list`: 使用可能なオプションを表示
- `!style reset`: デフォルトにリセット

### 9. 追加ツールCogs

コードベース構造に基づく追加ツールCogsには以下が含まれます:

- **アナウンスメント新** (`announcement_new.py`): 高度なアナウンスシステム
- **推しロールパネル** (`oshi_role_panel.py`): ロール選択インターフェース
- **カスタムアナウンスメント** (`custom_announcement.py`): カスタマイズ可能なアナウンス
- **サーバー統計** (`server_stats.py`): リアルタイムサーバー統計
- **自動リアクション** (`auto_reaction.py`): 特定条件でリアクション自動付与
- **Bumpリマインダー** (`bump_notice.py`): サーバーBump通知
- **ピン留めメッセージ** (`pin_message.py`): メッセージピン留め管理
- **VC通知** (`vc_notic.py`): ボイスチャンネル参加通知
- **サーバータグ** (`server_tag.py`): サーバータグ管理
- **FAQ初回メッセージ** (`send_first_message_to_faq.py`): FAQ自動送信

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
