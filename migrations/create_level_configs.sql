-- レベリングシステムのAI設定テーブル作成
-- 自然言語で設定されたレベリング設定を格納

CREATE TABLE IF NOT EXISTS level_configs (
    guild_id BIGINT PRIMARY KEY,
    config_data JSONB NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- インデックス作成（パフォーマンス向上）
CREATE INDEX IF NOT EXISTS idx_level_configs_updated_at ON level_configs(updated_at);
CREATE INDEX IF NOT EXISTS idx_level_configs_guild_id ON level_configs(guild_id);

-- JSONB検索用のGINインデックス（設定内容での検索用）
CREATE INDEX IF NOT EXISTS idx_level_configs_config_data ON level_configs USING GIN(config_data);

-- コメント追加
COMMENT ON TABLE level_configs IS 'AI自然言語設定システムで生成されたレベリング設定';
COMMENT ON COLUMN level_configs.guild_id IS 'DiscordサーバーID';
COMMENT ON COLUMN level_configs.config_data IS 'LevelConfigモデルのJSONB形式データ';
COMMENT ON COLUMN level_configs.created_at IS '設定作成日時';
COMMENT ON COLUMN level_configs.updated_at IS '設定更新日時';
