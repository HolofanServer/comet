-- メッセージ品質分析結果のキャッシュテーブル作成
-- AI分析結果を保存してパフォーマンス向上とコスト削減を図る

CREATE TABLE IF NOT EXISTS quality_cache (
    message_hash VARCHAR(32) PRIMARY KEY,
    analysis_data JSONB NOT NULL,
    cache_time TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    hit_count INTEGER DEFAULT 1,
    guild_id BIGINT,
    channel_id BIGINT
);

-- インデックス作成（パフォーマンス向上）
CREATE INDEX IF NOT EXISTS idx_quality_cache_time ON quality_cache(cache_time);
CREATE INDEX IF NOT EXISTS idx_quality_cache_guild ON quality_cache(guild_id);
CREATE INDEX IF NOT EXISTS idx_quality_cache_channel ON quality_cache(guild_id, channel_id);

-- JSONB検索用のGINインデックス（分析データ検索用）
CREATE INDEX IF NOT EXISTS idx_quality_cache_analysis ON quality_cache USING GIN(analysis_data);

-- 古いキャッシュを自動削除するためのパーティション（オプション）
-- CREATE INDEX IF NOT EXISTS idx_quality_cache_cleanup ON quality_cache(cache_time) WHERE cache_time < NOW() - INTERVAL '1 week';

-- コメント追加
COMMENT ON TABLE quality_cache IS 'AI品質分析結果のキャッシュ（パフォーマンス向上・コスト削減用）';
COMMENT ON COLUMN quality_cache.message_hash IS 'メッセージ内容のMD5ハッシュ値';
COMMENT ON COLUMN quality_cache.analysis_data IS 'MessageAnalysisモデルのJSONB形式データ';
COMMENT ON COLUMN quality_cache.cache_time IS 'キャッシュ作成日時';
COMMENT ON COLUMN quality_cache.hit_count IS 'キャッシュヒット回数（統計用）';
COMMENT ON COLUMN quality_cache.guild_id IS 'DiscordサーバーID（統計用）';
COMMENT ON COLUMN quality_cache.channel_id IS 'DiscordチャンネルID（統計用）';
