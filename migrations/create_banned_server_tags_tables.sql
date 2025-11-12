-- 禁止サーバータグシステム用テーブル作成

-- 禁止サーバータグテーブル
CREATE TABLE IF NOT EXISTS banned_server_tags (
    id SERIAL PRIMARY KEY,
    guild_id BIGINT NOT NULL,
    tag VARCHAR(4) NOT NULL,
    reason TEXT,
    added_by BIGINT NOT NULL,
    added_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(guild_id, tag)
);

-- タグモデレーション設定テーブル
CREATE TABLE IF NOT EXISTS tag_moderation_config (
    id SERIAL PRIMARY KEY,
    guild_id BIGINT NOT NULL UNIQUE,
    alert_channel_id BIGINT,
    timeout_duration INTEGER DEFAULT 604800,
    is_enabled BOOLEAN DEFAULT TRUE,
    auto_timeout BOOLEAN DEFAULT TRUE,
    updated_by BIGINT NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- タグモデレーションログテーブル
CREATE TABLE IF NOT EXISTS tag_moderation_logs (
    id SERIAL PRIMARY KEY,
    guild_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    user_tag VARCHAR(255) NOT NULL,
    banned_tag VARCHAR(4) NOT NULL,
    action_taken VARCHAR(50) NOT NULL,
    timeout_applied BOOLEAN DEFAULT FALSE,
    timeout_duration INTEGER,
    alert_sent BOOLEAN DEFAULT FALSE,
    alert_channel_id BIGINT,
    moderator_notified BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- インデックス作成
CREATE INDEX IF NOT EXISTS idx_banned_server_tags_guild_id ON banned_server_tags(guild_id);
CREATE INDEX IF NOT EXISTS idx_banned_server_tags_tag ON banned_server_tags(tag);
CREATE INDEX IF NOT EXISTS idx_tag_moderation_logs_guild_id ON tag_moderation_logs(guild_id);
CREATE INDEX IF NOT EXISTS idx_tag_moderation_logs_user_id ON tag_moderation_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_tag_moderation_logs_created_at ON tag_moderation_logs(created_at);

-- コメント追加
COMMENT ON TABLE banned_server_tags IS '禁止されているサーバータグのリスト';
COMMENT ON COLUMN banned_server_tags.tag IS '禁止するサーバータグ（最大4文字）';
COMMENT ON COLUMN banned_server_tags.reason IS '禁止理由';
COMMENT ON COLUMN banned_server_tags.added_by IS '追加した管理者のユーザーID';

COMMENT ON TABLE tag_moderation_config IS 'タグモデレーションの設定';
COMMENT ON COLUMN tag_moderation_config.alert_channel_id IS '警告を送信するチャンネルID';
COMMENT ON COLUMN tag_moderation_config.timeout_duration IS 'タイムアウト期間（秒）デフォルト7日間';
COMMENT ON COLUMN tag_moderation_config.is_enabled IS 'モデレーション機能の有効/無効';
COMMENT ON COLUMN tag_moderation_config.auto_timeout IS '自動タイムアウトの有効/無効';

COMMENT ON TABLE tag_moderation_logs IS 'タグモデレーションの実行ログ';
COMMENT ON COLUMN tag_moderation_logs.user_tag IS 'ユーザーが装着していたサーバータグ';
COMMENT ON COLUMN tag_moderation_logs.banned_tag IS 'マッチした禁止タグ';
COMMENT ON COLUMN tag_moderation_logs.action_taken IS '実行されたアクション（timeout, alert, etc）';
