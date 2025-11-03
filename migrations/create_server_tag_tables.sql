-- サーバータグシステム用テーブル作成

-- サーバータグ履歴テーブル
CREATE TABLE IF NOT EXISTS server_tag_history (
    id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    guild_id BIGINT NOT NULL,
    tag VARCHAR(4) NOT NULL,
    identity_guild_id BIGINT NOT NULL,
    badge VARCHAR(255),
    checked_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, guild_id)
);

-- インデックス作成
CREATE INDEX IF NOT EXISTS idx_server_tag_history_user_id ON server_tag_history(user_id);
CREATE INDEX IF NOT EXISTS idx_server_tag_history_guild_id ON server_tag_history(guild_id);
CREATE INDEX IF NOT EXISTS idx_server_tag_history_tag ON server_tag_history(tag);
CREATE INDEX IF NOT EXISTS idx_server_tag_history_identity_guild_id ON server_tag_history(identity_guild_id);
CREATE INDEX IF NOT EXISTS idx_server_tag_history_checked_at ON server_tag_history(checked_at);

-- コメント追加
COMMENT ON TABLE server_tag_history IS 'Discordサーバータグの取得履歴を保存するテーブル';
COMMENT ON COLUMN server_tag_history.user_id IS 'ユーザーのDiscord ID';
COMMENT ON COLUMN server_tag_history.guild_id IS 'コマンドが実行されたサーバーのID';
COMMENT ON COLUMN server_tag_history.tag IS 'ユーザーが装着しているサーバータグ（最大4文字）';
COMMENT ON COLUMN server_tag_history.identity_guild_id IS 'タグが紐づけられているサーバーのID';
COMMENT ON COLUMN server_tag_history.badge IS 'タグのバッジハッシュID';
COMMENT ON COLUMN server_tag_history.checked_at IS 'タグ情報を最後に確認した日時';
