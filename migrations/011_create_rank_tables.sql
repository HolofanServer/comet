-- HFS Rank システム用テーブル
-- Checkpoint DB (cp) と共有

-- ユーザーXP・ランク情報
CREATE TABLE IF NOT EXISTS rank_users (
    id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    guild_id BIGINT NOT NULL,
    yearly_xp INT NOT NULL DEFAULT 0,
    lifetime_xp BIGINT NOT NULL DEFAULT 0,
    active_days INT NOT NULL DEFAULT 0,
    current_level INT NOT NULL DEFAULT 1,
    is_regular BOOLEAN NOT NULL DEFAULT FALSE,
    last_message_xp_at TIMESTAMP WITH TIME ZONE,
    last_omikuji_xp_date DATE,
    last_active_date DATE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, guild_id)
);

CREATE INDEX IF NOT EXISTS idx_rank_users_guild ON rank_users(guild_id);
CREATE INDEX IF NOT EXISTS idx_rank_users_yearly_xp ON rank_users(guild_id, yearly_xp DESC);
CREATE INDEX IF NOT EXISTS idx_rank_users_lifetime_xp ON rank_users(guild_id, lifetime_xp DESC);

-- シーズン別統計（年度別アーカイブ用）
CREATE TABLE IF NOT EXISTS rank_season_stats (
    id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    guild_id BIGINT NOT NULL,
    year SMALLINT NOT NULL,
    yearly_xp INT NOT NULL DEFAULT 0,
    active_days INT NOT NULL DEFAULT 0,
    final_level INT NOT NULL DEFAULT 1,
    was_regular BOOLEAN NOT NULL DEFAULT FALSE,
    message_xp INT NOT NULL DEFAULT 0,
    vc_xp INT NOT NULL DEFAULT 0,
    omikuji_xp INT NOT NULL DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, guild_id, year)
);

CREATE INDEX IF NOT EXISTS idx_rank_season_year ON rank_season_stats(guild_id, year);

-- XP設定（係数調整用）
CREATE TABLE IF NOT EXISTS rank_config (
    id SERIAL PRIMARY KEY,
    guild_id BIGINT NOT NULL UNIQUE,
    message_xp INT NOT NULL DEFAULT 5,
    message_cooldown_seconds INT NOT NULL DEFAULT 60,
    omikuji_xp INT NOT NULL DEFAULT 15,
    vc_xp_per_10min INT NOT NULL DEFAULT 5,
    regular_xp_threshold INT NOT NULL DEFAULT 10000,
    regular_days_threshold INT NOT NULL DEFAULT 50,
    excluded_channels BIGINT[] DEFAULT '{}',
    excluded_roles BIGINT[] DEFAULT '{}',
    is_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- レベル閾値テーブル
CREATE TABLE IF NOT EXISTS rank_levels (
    level INT PRIMARY KEY,
    required_xp INT NOT NULL,
    role_id BIGINT,
    badge_name VARCHAR(50)
);

-- デフォルトレベル閾値を挿入
INSERT INTO rank_levels (level, required_xp) VALUES
    (1, 0),
    (2, 100),
    (3, 300),
    (4, 600),
    (5, 1000),
    (6, 1500),
    (7, 2100),
    (8, 2800),
    (9, 3600),
    (10, 4500),
    (11, 5500),
    (12, 6600),
    (13, 7800),
    (14, 9100),
    (15, 10500),
    (16, 12000),
    (17, 13600),
    (18, 15300),
    (19, 17100),
    (20, 19000),
    (25, 30000),
    (30, 45000),
    (35, 65000),
    (40, 90000),
    (45, 120000),
    (50, 160000)
ON CONFLICT (level) DO NOTHING;
