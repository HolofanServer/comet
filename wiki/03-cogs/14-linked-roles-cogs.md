# Linked Roles Cogs

## 概要

Linked Roles CogsはDiscord Linked Roles APIを管理し、MyHFSとの連携を提供します。ユーザーのMyHFS情報をDiscordプロフィールに表示し、サーバーロールの条件として使用できます。

## 利用可能なCogs

### 1. Linked Roles (`linked_roles.py`)

**目的**: Discord Linked Roles APIを使用してMyHFSとの連携を管理。

**主要機能**:
- **メタデータスキーマ登録**: Discordにメタデータスキーマを登録
- **バッチ更新**: 全連携ユーザーのメタデータを定期更新（1日1回）
- **トークン管理**: OAuth2トークンの自動リフレッシュ
- **MyHFS API連携**: MyHFSからユーザー情報を取得

**メタデータスキーマ**:
| キー | 名前 | タイプ | 説明 |
|------|------|--------|------|
| `card_created` | カード作成済み | BOOLEAN_EQUAL | MyHFSでカードを作成済み |
| `member_number` | メンバー番号 | INTEGER_GREATER_THAN_OR_EQUAL | MyHFSメンバー番号 |
| `joined_at` | 参加日 | DATETIME_GREATER_THAN_OR_EQUAL | HFS参加日からの経過日数 |
| `oshi_count` | 推し人数 | INTEGER_GREATER_THAN_OR_EQUAL | 登録した推しメンバーの人数 |

**利用可能なコマンド**:
- `/linkedroles-setup`: メタデータスキーマをDiscordに登録
- `/linkedroles-schema`: 現在のスキーマを表示
- `/linkedroles-batch`: 全ユーザーのメタデータを手動更新
- `/linkedroles-status`: 連携統計情報を表示
- `/linkedroles-test`: API接続テスト

## システムアーキテクチャ

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Discord API   │◄────│   COMET Bot     │────►│   MyHFS API     │
│  (Linked Roles) │     │ (LinkedRolesCog)│     │ (User Data)     │
└─────────────────┘     └─────────────────┘     └─────────────────┘
        │                       │                       │
        ▼                       ▼                       ▼
   メタデータ更新          バッチ処理              ユーザー情報
   トークン管理           (24時間ごと)            トークン同期
```

## セットアップ

### 1. Discord Developer Portal設定

1. **General Information**:
   - LINKED ROLES VERIFICATION URLを設定

2. **OAuth2**:
   - Redirectsを設定
   - `role_connections.write`スコープを有効化

### 2. 環境変数

```env
DISCORD_CLIENT_ID=your_client_id
DISCORD_CLIENT_SECRET=your_client_secret
MYHFS_LINKED_ROLES_API_URL=https://api.myhfs.example.com
MYHFS_LINKED_ROLES_TOKEN=your_myhfs_token
```

### 3. スキーマ登録

```
/linkedroles-setup
```

## バッチ処理フロー

1. **ユーザー取得**: MyHFS APIから連携ユーザー一覧を取得
2. **トークン確認**: 各ユーザーのOAuth2トークン有効期限をチェック
3. **トークンリフレッシュ**: 期限切れの場合は自動リフレッシュ
4. **メタデータ更新**: Discord APIでユーザーメタデータを更新
5. **トークン同期**: 新しいトークンをMyHFSに通知

## エラーハンドリング

- **レート制限**: 429エラー時は自動リトライ
- **トークン失効**: リフレッシュ失敗時はスキップしてログ記録
- **API障害**: エラーカウントを記録し、バッチ完了時にサマリー出力

## 関連ドキュメント

- [MyHFS Linked Roles仕様書](../../docs/myhfs-linked-roles-spec-v2.md)
- [Discord Linked Roles API](https://discord.com/developers/docs/tutorials/configuring-app-metadata-for-linked-roles)
- [OAuth2認証](../04-utilities/02-authentication.md)
