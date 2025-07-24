# ホームページCogs

## 概要

ホームページCogsは、Discordサーバーとウェブサイト間の統合を管理し、スタッフ情報の同期とメンバーデータ管理を処理します。

## 利用可能なホームページCogs

### 1. スタッフマネージャー (`staff_manager.py`)

**目的**: Discordサーバーのロールとメンバー情報をウェブサイトAPIと同期します。

**主要機能**:
- **自動同期**: `@tasks.loop(hours=3)`により3時間ごとにスタッフデータを更新
- **ロールベースカテゴリ**: メンバーをスタッフ、スペシャルサンクス、テスターに分類
- **API統合**: ウェブサイトAPIエンドポイント（`https://hfs.jp/api`）にデータを送信
- **メンバーデータ**: アバター、参加日、ロール色、カスタムメッセージを収集
- **キャッシュシステム**: APIフォールバック付きローカルJSONキャッシュ

#### スタッフロール階層
```python
role_priority = {
    "Administrator": 1,
    "Moderator": 2, 
    "Staff": 3
}
```

#### メンバーデータ構造
```json
{
  "id": "123456789",
  "name": "DisplayName",
  "role": "Administrator",
  "avatar": "https://cdn.discordapp.com/avatars/...",
  "message": "Custom message",
  "joinedAt": "2024-01-01",
  "joinedAtJp": "2024年01月01日",
  "roleColor": "#ff0000",
  "socials": {}
}
```

#### 管理カテゴリ
1. **スタッフメンバー**: Administrator、Moderator、またはStaffロールを持つユーザー
2. **スペシャルサンクス**: "常連"で始まるロールを持つユーザー（常連）
3. **テスター**: "テスター"ロールを持つ特定のユーザーIDのハードコードリスト

#### API統合
- **エンドポイント**: `POST /api/members/update`
- **認証**: `STAFF_API_KEY`によるBearerトークン
- **データ形式**: staff、specialThanks、testersの配列を含むJSON
- **フォールバック**: API利用不可時のローカルJSONキャッシュ

#### 利用可能なコマンド

| コマンド | タイプ | 権限 | 説明 |
|---------|------|------------|-------------|
| `update_staff` | プレフィックス | Administrator | 手動スタッフデータ更新 |
| `/ひとこと` | ハイブリッド | 誰でも | 個人メッセージを設定 |
| `/ひとことリセット` | ハイブリッド | 誰でも | 個人メッセージをクリア |
| `staff_status` | プレフィックス | Administrator | 現在のスタッフデータ状態を表示 |

#### 実装詳細

**自動更新**:
```python
@tasks.loop(hours=3)
async def auto_update_staff(self):
    await self.update_staff_data()
```

**データ収集プロセス**:
1. すべてのサーバーメンバーをスキャン
2. スタッフロール（Administrator、Moderator、Staff）をチェック
3. スペシャルサンクスロール（"常連"で始まる）をチェック
4. ハードコードされたテスターメンバーを追加
5. メンバーデータ（アバター、参加日、ロール色）を収集
6. 既存のメッセージとソーシャルリンクを保持
7. APIに送信してローカルにキャッシュ

**エラーハンドリング**:
- API失敗時はローカルキャッシュにフォールバック
- 個別メンバーエラーはバッチ処理を停止しない
- デバッグ用の包括的ログ

**設定**:
```python
self.api_endpoint = "https://hfs.jp/api"
self.api_token = settings.staff_api_key
self.config_path = 'config/members.json'
```

---

## 関連ドキュメント

- [API統合](../04-utilities/02-api-integration.md)
- [データベース管理](../04-utilities/01-database-management.md)
- [設定管理](../01-architecture/04-configuration-management.md)
- [エラーハンドリング](../02-core/04-error-handling.md)
