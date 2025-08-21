-- ユーザー警告システム用テーブル作成

-- 監視対象ユーザーテーブル
CREATE TABLE IF NOT EXISTS monitored_users (
    id SERIAL PRIMARY KEY,
    guild_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    added_by BIGINT NOT NULL,
    added_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    reason TEXT,
    UNIQUE(guild_id, user_id)
);

-- 除外チャンネルテーブル
CREATE TABLE IF NOT EXISTS excluded_channels (
    id SERIAL PRIMARY KEY,
    guild_id BIGINT NOT NULL,
    channel_id BIGINT NOT NULL,
    added_by BIGINT NOT NULL,
    added_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    reason TEXT,
    UNIQUE(guild_id, channel_id)
);

-- 警告システム設定テーブル
CREATE TABLE IF NOT EXISTS warning_system_config (
    id SERIAL PRIMARY KEY,
    guild_id BIGINT NOT NULL UNIQUE,
    warning_channel_id BIGINT,
    is_enabled BOOLEAN DEFAULT TRUE,
    updated_by BIGINT NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 警告ログテーブル
CREATE TABLE IF NOT EXISTS warning_logs (
    id SERIAL PRIMARY KEY,
    guild_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    channel_id BIGINT NOT NULL,
    message_content TEXT,
    warning_channel_id BIGINT,
    moderator_id BIGINT,
    timeout_applied BOOLEAN DEFAULT FALSE,
    timeout_applied_by BIGINT,
    timeout_applied_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- インデックス作成
CREATE INDEX IF NOT EXISTS idx_monitored_users_guild_id ON monitored_users(guild_id);
CREATE INDEX IF NOT EXISTS idx_monitored_users_user_id ON monitored_users(user_id);
CREATE INDEX IF NOT EXISTS idx_excluded_channels_guild_id ON excluded_channels(guild_id);
CREATE INDEX IF NOT EXISTS idx_excluded_channels_channel_id ON excluded_channels(channel_id);
CREATE INDEX IF NOT EXISTS idx_warning_logs_guild_id ON warning_logs(guild_id);
CREATE INDEX IF NOT EXISTS idx_warning_logs_user_id ON warning_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_warning_logs_created_at ON warning_logs(created_at);
