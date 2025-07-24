-- ホロライブおみくじ機能用テーブル作成マイグレーション
-- 作成日: 2025-07-25

-- おみくじの運勢マスターテーブル
CREATE TABLE IF NOT EXISTS omikuji_fortunes (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    display_name VARCHAR(100) NOT NULL,
    weight INTEGER DEFAULT 1,
    is_special BOOLEAN DEFAULT FALSE,
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- ユーザーのおみくじ履歴テーブル
CREATE TABLE IF NOT EXISTS user_omikuji_history (
    id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    guild_id BIGINT NOT NULL,
    fortune_id INTEGER REFERENCES omikuji_fortunes(id),
    drawn_date DATE NOT NULL,
    is_super_rare BOOLEAN DEFAULT FALSE,
    is_chance BOOLEAN DEFAULT FALSE,
    streak_count INTEGER DEFAULT 1,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- ユーザーの運勢履歴テーブル
CREATE TABLE IF NOT EXISTS user_fortune_history (
    id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    guild_id BIGINT NOT NULL,
    fortune_level VARCHAR(50) NOT NULL,
    lucky_color VARCHAR(100),
    lucky_item VARCHAR(200),
    lucky_app VARCHAR(200),
    drawn_date DATE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- ユーザーのストリーク情報テーブル
CREATE TABLE IF NOT EXISTS user_omikuji_streaks (
    id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    guild_id BIGINT NOT NULL,
    current_streak INTEGER DEFAULT 0,
    max_streak INTEGER DEFAULT 0,
    last_draw_date DATE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, guild_id)
);

-- 日次統計テーブル
CREATE TABLE IF NOT EXISTS omikuji_daily_stats (
    id SERIAL PRIMARY KEY,
    guild_id BIGINT NOT NULL,
    stat_date DATE NOT NULL,
    omikuji_count INTEGER DEFAULT 0,
    fortune_count INTEGER DEFAULT 0,
    unique_users INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(guild_id, stat_date)
);

-- インデックス作成
CREATE INDEX IF NOT EXISTS idx_user_omikuji_history_user_date ON user_omikuji_history(user_id, drawn_date DESC);
CREATE INDEX IF NOT EXISTS idx_user_omikuji_history_guild_date ON user_omikuji_history(guild_id, drawn_date DESC);
CREATE INDEX IF NOT EXISTS idx_user_fortune_history_user_date ON user_fortune_history(user_id, drawn_date DESC);
CREATE INDEX IF NOT EXISTS idx_user_fortune_history_guild_date ON user_fortune_history(guild_id, drawn_date DESC);
CREATE INDEX IF NOT EXISTS idx_user_omikuji_streaks_user_guild ON user_omikuji_streaks(user_id, guild_id);
CREATE INDEX IF NOT EXISTS idx_omikuji_daily_stats_guild_date ON omikuji_daily_stats(guild_id, stat_date DESC);

-- ホロライブおみくじの初期データ投入
INSERT INTO omikuji_fortunes (name, display_name, weight, is_special, description) VALUES
    ('holo_daikichi', 'ホロ大吉', 8, true, 'ホロライブの最高の運勢！推しからのお便りが届くかも？'),
    ('holo_kichi', 'ホロ吉', 20, false, 'ホロメンの配信が楽しめる良い日！'),
    ('holo_chukichi', 'ホロ中吉', 25, false, 'まずまずの運勢。新しいホロメンに出会えるかも'),
    ('holo_shoukichi', 'ホロ小吉', 30, false, '普通の運勢。いつものように配信を楽しもう'),
    ('holo_suekichi', 'ホロ末吉', 15, false, '少し注意が必要。推しの配信を見て運気アップ！'),
    ('holo_kyo', 'ホロ凶', 2, false, '今日は少し運が悪いかも。でも推しが支えてくれる！'),
    ('oshi_daikichi', '推し大吉', 5, true, '推しメンバーに関する特別な運勢！'),
    ('collab_kichi', 'コラボ吉', 10, false, 'コラボ配信に恵まれる運勢'),
    ('stream_kichi', '配信吉', 15, false, '配信運に恵まれる日'),
    ('fan_kichi', 'ファン吉', 12, false, 'ホロリス同士の交流に恵まれる')
ON CONFLICT (name) DO NOTHING;

-- 更新日時自動更新のトリガー関数
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- 更新日時自動更新のトリガー設定
CREATE TRIGGER update_omikuji_fortunes_updated_at 
    BEFORE UPDATE ON omikuji_fortunes 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_user_omikuji_streaks_updated_at 
    BEFORE UPDATE ON user_omikuji_streaks 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_omikuji_daily_stats_updated_at 
    BEFORE UPDATE ON omikuji_daily_stats 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
