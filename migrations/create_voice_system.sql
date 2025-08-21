-- 音声チャンネルXP・複数トラックシステム用データベーススキーマ
-- 時間ベース音声XP、チャンネル別トラック管理、セッション記録、統計データを格納

-- 音声XP設定テーブル（サーバーごと）
CREATE TABLE IF NOT EXISTS voice_configs (
    guild_id BIGINT PRIMARY KEY,
    config_data JSONB NOT NULL,
    voice_xp_enabled BOOLEAN DEFAULT TRUE,
    global_voice_multiplier FLOAT DEFAULT 1.0,
    daily_voice_xp_limit INTEGER DEFAULT 1000,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_by BIGINT  -- Discord User ID
);

-- 音声セッション記録テーブル
CREATE TABLE IF NOT EXISTS voice_sessions (
    session_id VARCHAR(36) PRIMARY KEY,  -- UUID
    guild_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    channel_id BIGINT NOT NULL,
    
    -- 時間情報
    start_time TIMESTAMP WITH TIME ZONE NOT NULL,
    end_time TIMESTAMP WITH TIME ZONE,
    duration_seconds INTEGER DEFAULT 0,
    
    -- 活動統計
    total_speaking_seconds INTEGER DEFAULT 0,
    total_listening_seconds INTEGER DEFAULT 0,
    total_afk_seconds INTEGER DEFAULT 0,
    total_muted_seconds INTEGER DEFAULT 0,
    
    -- 活動ログ（JSONB形式）
    activity_log JSONB DEFAULT '[]'::jsonb,
    
    -- XP情報
    base_xp_earned INTEGER DEFAULT 0,
    bonus_xp_earned INTEGER DEFAULT 0,
    total_xp_earned INTEGER DEFAULT 0,
    
    -- セッション情報
    peak_participants INTEGER DEFAULT 1,
    track_type VARCHAR(20) DEFAULT 'general',
    
    is_completed BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 音声統計テーブル（ユーザーごと）
CREATE TABLE IF NOT EXISTS voice_stats (
    guild_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    
    -- 累計統計
    total_voice_time_seconds BIGINT DEFAULT 0,
    total_voice_xp BIGINT DEFAULT 0,
    total_sessions INTEGER DEFAULT 0,
    
    -- トラック別統計（JSONB）
    track_stats JSONB DEFAULT '{}'::jsonb,
    
    -- 日別統計（最近30日分、JSONB）
    daily_stats JSONB DEFAULT '{}'::jsonb,
    
    -- ベスト記録
    longest_session_seconds INTEGER DEFAULT 0,
    highest_daily_xp INTEGER DEFAULT 0,
    most_productive_hour INTEGER DEFAULT 12,
    
    -- レート情報
    average_xp_per_minute FLOAT DEFAULT 0.0,
    favorite_channels JSONB DEFAULT '[]'::jsonb,
    
    last_updated TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    PRIMARY KEY (guild_id, user_id)
);

-- 現在アクティブな音声セッション（メモリ効率化）
CREATE TABLE IF NOT EXISTS active_voice_sessions (
    guild_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    channel_id BIGINT NOT NULL,
    session_id VARCHAR(36) NOT NULL,
    
    -- 現在の状態
    current_activity VARCHAR(20) DEFAULT 'listening',  -- speaking/listening/afk/muted/deafened
    join_time TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_activity_time TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_speaking_time TIMESTAMP WITH TIME ZONE,
    
    -- リアルタイム統計
    session_speaking_seconds INTEGER DEFAULT 0,
    session_listening_seconds INTEGER DEFAULT 0,
    session_afk_seconds INTEGER DEFAULT 0,
    
    -- 現在の参加者数（キャッシュ）
    current_participants INTEGER DEFAULT 1,
    
    -- XP累積（一時的）
    pending_xp INTEGER DEFAULT 0,
    last_xp_calculation TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    PRIMARY KEY (guild_id, user_id),
    FOREIGN KEY (session_id) REFERENCES voice_sessions(session_id) ON DELETE CASCADE
);

-- 音声チャンネル別設定テーブル
CREATE TABLE IF NOT EXISTS voice_channel_configs (
    guild_id BIGINT NOT NULL,
    channel_id BIGINT NOT NULL,
    channel_name TEXT,
    track_type VARCHAR(20) DEFAULT 'general',
    
    -- XP設定
    base_xp_per_minute INTEGER DEFAULT 5,
    max_xp_per_hour INTEGER DEFAULT 300,
    min_duration_minutes INTEGER DEFAULT 2,
    
    -- 倍率設定（JSONB）
    activity_multipliers JSONB DEFAULT '[]'::jsonb,
    time_multipliers JSONB DEFAULT '{}'::jsonb,
    participant_bonus JSONB DEFAULT '{}'::jsonb,
    
    is_enabled BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    PRIMARY KEY (guild_id, channel_id)
);

-- 音声XP履歴テーブル（監査・分析用）
CREATE TABLE IF NOT EXISTS voice_xp_history (
    id SERIAL PRIMARY KEY,
    guild_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    session_id VARCHAR(36) NOT NULL,
    
    -- XP付与情報
    xp_amount INTEGER NOT NULL,
    xp_type VARCHAR(20) DEFAULT 'voice',  -- voice/bonus/penalty
    calculation_method VARCHAR(50),  -- 計算方法の説明
    
    -- 計算詳細（JSONB）
    calculation_details JSONB DEFAULT '{}'::jsonb,
    
    -- 付与時の状況
    channel_id BIGINT NOT NULL,
    activity_type VARCHAR(20) NOT NULL,
    participants_count INTEGER DEFAULT 1,
    session_duration_seconds INTEGER DEFAULT 0,
    
    awarded_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- インデックス作成（パフォーマンス向上）

-- voice_sessions テーブル
CREATE INDEX IF NOT EXISTS idx_voice_sessions_guild_user ON voice_sessions(guild_id, user_id);
CREATE INDEX IF NOT EXISTS idx_voice_sessions_channel ON voice_sessions(guild_id, channel_id);
CREATE INDEX IF NOT EXISTS idx_voice_sessions_time ON voice_sessions(start_time DESC);
CREATE INDEX IF NOT EXISTS idx_voice_sessions_completed ON voice_sessions(guild_id, is_completed);

-- voice_stats テーブル
CREATE INDEX IF NOT EXISTS idx_voice_stats_xp ON voice_stats(guild_id, total_voice_xp DESC);
CREATE INDEX IF NOT EXISTS idx_voice_stats_time ON voice_stats(guild_id, total_voice_time_seconds DESC);
CREATE INDEX IF NOT EXISTS idx_voice_stats_updated ON voice_stats(last_updated);

-- active_voice_sessions テーブル
CREATE INDEX IF NOT EXISTS idx_active_voice_guild ON active_voice_sessions(guild_id);
CREATE INDEX IF NOT EXISTS idx_active_voice_channel ON active_voice_sessions(guild_id, channel_id);
CREATE INDEX IF NOT EXISTS idx_active_voice_activity ON active_voice_sessions(last_activity_time);

-- voice_channel_configs テーブル
CREATE INDEX IF NOT EXISTS idx_voice_channel_enabled ON voice_channel_configs(guild_id, is_enabled);
CREATE INDEX IF NOT EXISTS idx_voice_channel_track ON voice_channel_configs(guild_id, track_type);

-- voice_xp_history テーブル
CREATE INDEX IF NOT EXISTS idx_voice_xp_history_user ON voice_xp_history(guild_id, user_id);
CREATE INDEX IF NOT EXISTS idx_voice_xp_history_session ON voice_xp_history(session_id);
CREATE INDEX IF NOT EXISTS idx_voice_xp_history_time ON voice_xp_history(awarded_at DESC);

-- JSONB検索用のGINインデックス
CREATE INDEX IF NOT EXISTS idx_voice_configs_data ON voice_configs USING GIN(config_data);
CREATE INDEX IF NOT EXISTS idx_voice_sessions_activity ON voice_sessions USING GIN(activity_log);
CREATE INDEX IF NOT EXISTS idx_voice_stats_track ON voice_stats USING GIN(track_stats);
CREATE INDEX IF NOT EXISTS idx_voice_stats_daily ON voice_stats USING GIN(daily_stats);

-- パーティション用のトリガー（大量データ対応）
-- voice_xp_history テーブルを月別にパーティション分割（オプション）
-- 大規模サーバー用の最適化として後で追加可能

-- 自動クリーンアップ用のトリガー（古いデータ削除）
CREATE OR REPLACE FUNCTION cleanup_old_voice_data() RETURNS TRIGGER AS $$
BEGIN
    -- 90日より古いセッションデータを削除
    DELETE FROM voice_sessions 
    WHERE start_time < NOW() - INTERVAL '90 days';
    
    -- 1年より古いXP履歴を削除
    DELETE FROM voice_xp_history 
    WHERE awarded_at < NOW() - INTERVAL '365 days';
    
    -- daily_statsから90日より古いデータを削除（JSONB内）
    UPDATE voice_stats 
    SET daily_stats = (
        SELECT jsonb_object_agg(key, value)
        FROM jsonb_each(daily_stats)
        WHERE key::date > CURRENT_DATE - INTERVAL '90 days'
    )
    WHERE daily_stats IS NOT NULL AND daily_stats != '{}'::jsonb;
    
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

-- 定期クリーンアップのトリガー（新しいセッション作成時に実行）
-- CREATE TRIGGER trigger_cleanup_voice_data
--     AFTER INSERT ON voice_sessions
--     FOR EACH STATEMENT
--     EXECUTE FUNCTION cleanup_old_voice_data();

-- 統計情報の自動更新関数
CREATE OR REPLACE FUNCTION update_voice_stats_on_session_complete() RETURNS TRIGGER AS $$
BEGIN
    -- セッション完了時に統計を更新
    IF NEW.is_completed = TRUE AND OLD.is_completed = FALSE THEN
        INSERT INTO voice_stats (guild_id, user_id, total_voice_time_seconds, total_voice_xp, total_sessions)
        VALUES (NEW.guild_id, NEW.user_id, NEW.duration_seconds, NEW.total_xp_earned, 1)
        ON CONFLICT (guild_id, user_id)
        DO UPDATE SET
            total_voice_time_seconds = voice_stats.total_voice_time_seconds + NEW.duration_seconds,
            total_voice_xp = voice_stats.total_voice_xp + NEW.total_xp_earned,
            total_sessions = voice_stats.total_sessions + 1,
            longest_session_seconds = GREATEST(voice_stats.longest_session_seconds, NEW.duration_seconds),
            last_updated = NOW();
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- セッション完了時の統計更新トリガー
CREATE TRIGGER trigger_update_voice_stats
    AFTER UPDATE ON voice_sessions
    FOR EACH ROW
    EXECUTE FUNCTION update_voice_stats_on_session_complete();

-- コメント追加
COMMENT ON TABLE voice_configs IS 'サーバーごとの音声XP設定';
COMMENT ON TABLE voice_sessions IS '音声セッション記録（完了済み）';
COMMENT ON TABLE voice_stats IS 'ユーザーごとの音声活動統計';
COMMENT ON TABLE active_voice_sessions IS '現在アクティブな音声セッション（リアルタイム）';
COMMENT ON TABLE voice_channel_configs IS '音声チャンネル別設定';
COMMENT ON TABLE voice_xp_history IS '音声XP付与履歴（監査・分析用）';

COMMENT ON COLUMN voice_sessions.session_id IS 'UUID形式のセッション識別子';
COMMENT ON COLUMN voice_sessions.activity_log IS '活動履歴のJSONB配列';
COMMENT ON COLUMN voice_stats.track_stats IS 'トラック別統計のJSONBオブジェクト';
COMMENT ON COLUMN voice_stats.daily_stats IS '日別統計のJSONBオブジェクト（YYYY-MM-DD: stats）';
COMMENT ON COLUMN active_voice_sessions.current_activity IS '現在の活動状態（speaking/listening/afk/muted/deafened）';
