-- アチーブメント・スキルツリー・プレステージシステム用テーブル
-- Discord.py レベリングシステム ゲーミフィケーション機能

-- 1. アチーブメント定義テーブル
CREATE TABLE IF NOT EXISTS achievements (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT NOT NULL,
    type TEXT NOT NULL CHECK (type IN ('level', 'xp_total', 'xp_daily', 'message_count', 'voice_time', 'voice_xp', 'streak_daily', 'streak_weekly', 'social', 'special', 'custom')),
    rarity TEXT NOT NULL CHECK (rarity IN ('common', 'uncommon', 'rare', 'epic', 'legendary', 'mythic')),
    
    -- 条件
    condition_type TEXT NOT NULL,
    target_value INTEGER NOT NULL CHECK (target_value > 0),
    additional_params JSONB DEFAULT '{}',
    
    -- 報酬
    xp_reward INTEGER DEFAULT 0 CHECK (xp_reward >= 0),
    skill_points_reward INTEGER DEFAULT 0 CHECK (skill_points_reward >= 0),
    title_reward TEXT,
    role_reward TEXT,
    custom_rewards JSONB DEFAULT '{}',
    
    -- メタデータ
    icon TEXT,
    color INTEGER,
    hidden BOOLEAN DEFAULT FALSE,
    one_time BOOLEAN DEFAULT TRUE,
    requires_achievements TEXT[] DEFAULT '{}',
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    -- インデックス
    CONSTRAINT achievements_color_range CHECK (color IS NULL OR (color >= 0 AND color <= 16777215))
);

-- 2. ユーザーアチーブメント進捗テーブル
CREATE TABLE IF NOT EXISTS user_achievements (
    guild_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    achievement_id TEXT NOT NULL REFERENCES achievements(id) ON DELETE CASCADE,
    
    -- 進捗
    current_progress INTEGER DEFAULT 0 CHECK (current_progress >= 0),
    is_completed BOOLEAN DEFAULT FALSE,
    completion_date TIMESTAMP WITH TIME ZONE,
    
    -- メタデータ
    first_seen TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_updated TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    notification_sent BOOLEAN DEFAULT FALSE,
    
    -- 制約
    PRIMARY KEY (guild_id, user_id, achievement_id),
    CONSTRAINT user_achievements_completion_consistency 
        CHECK (is_completed = FALSE OR completion_date IS NOT NULL)
);

-- 3. スキルノード定義テーブル
CREATE TABLE IF NOT EXISTS skill_nodes (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT NOT NULL,
    type TEXT NOT NULL CHECK (type IN ('xp_boost', 'voice_boost', 'cooldown_reduce', 'quality_boost', 'streak_protect', 'social_boost', 'special_access')),
    
    -- ツリー構造
    tier INTEGER NOT NULL CHECK (tier >= 1 AND tier <= 10),
    prerequisites TEXT[] DEFAULT '{}',
    
    -- コスト・効果
    skill_points_cost INTEGER NOT NULL CHECK (skill_points_cost > 0),
    max_level INTEGER DEFAULT 1 CHECK (max_level >= 1 AND max_level <= 10),
    effect_per_level DECIMAL(10,6) NOT NULL,
    
    -- メタデータ
    icon TEXT,
    color INTEGER,
    category TEXT DEFAULT 'general',
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    -- 制約
    CONSTRAINT skill_nodes_color_range CHECK (color IS NULL OR (color >= 0 AND color <= 16777215))
);

-- 4. ユーザースキル習得状況テーブル
CREATE TABLE IF NOT EXISTS user_skills (
    guild_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    skill_id TEXT NOT NULL REFERENCES skill_nodes(id) ON DELETE CASCADE,
    
    current_level INTEGER DEFAULT 0 CHECK (current_level >= 0),
    total_invested_points INTEGER DEFAULT 0 CHECK (total_invested_points >= 0),
    unlocked_at TIMESTAMP WITH TIME ZONE,
    last_upgraded TIMESTAMP WITH TIME ZONE,
    
    PRIMARY KEY (guild_id, user_id, skill_id)
);

-- 5. プレステージティア定義テーブル
CREATE TABLE IF NOT EXISTS prestige_tiers (
    tier INTEGER NOT NULL,
    name TEXT NOT NULL,
    type TEXT NOT NULL CHECK (type IN ('standard', 'voice', 'social', 'streamer', 'developer')),
    
    -- 必要条件
    required_level INTEGER NOT NULL CHECK (required_level >= 50),
    required_achievements INTEGER DEFAULT 0 CHECK (required_achievements >= 0),
    required_skill_points INTEGER DEFAULT 0 CHECK (required_skill_points >= 0),
    
    -- 特典
    benefits JSONB NOT NULL,
    reset_progress BOOLEAN DEFAULT TRUE,
    keep_skills BOOLEAN DEFAULT FALSE,
    
    -- 視覚効果
    icon TEXT,
    color INTEGER,
    badge TEXT,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    PRIMARY KEY (tier, type),
    
    -- 制約
    CONSTRAINT prestige_tiers_color_range CHECK (color IS NULL OR (color >= 0 AND color <= 16777215))
);

-- 6. ユーザープレステージ状況テーブル
CREATE TABLE IF NOT EXISTS user_prestige (
    guild_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    
    current_tier INTEGER DEFAULT 0 CHECK (current_tier >= 0),
    current_type TEXT,
    total_prestiges INTEGER DEFAULT 0 CHECK (total_prestiges >= 0),
    
    -- 履歴
    last_prestige_date TIMESTAMP WITH TIME ZONE,
    prestige_history JSONB DEFAULT '[]',
    
    -- 統計
    total_levels_before_prestige INTEGER DEFAULT 0 CHECK (total_levels_before_prestige >= 0),
    total_xp_before_prestige BIGINT DEFAULT 0 CHECK (total_xp_before_prestige >= 0),
    
    last_updated TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    PRIMARY KEY (guild_id, user_id),
    
    -- 制約
    FOREIGN KEY (current_tier, current_type) REFERENCES prestige_tiers(tier, type) DEFERRABLE
);

-- 7. ゲーミフィケーション設定テーブル
CREATE TABLE IF NOT EXISTS gamification_configs (
    guild_id BIGINT PRIMARY KEY,
    
    -- システム有効化
    achievements_enabled BOOLEAN DEFAULT TRUE,
    skills_enabled BOOLEAN DEFAULT TRUE,
    prestige_enabled BOOLEAN DEFAULT TRUE,
    
    -- 通知設定
    achievement_notifications BOOLEAN DEFAULT TRUE,
    skill_unlock_notifications BOOLEAN DEFAULT TRUE,
    prestige_notifications BOOLEAN DEFAULT TRUE,
    
    -- カスタム設定
    custom_achievements JSONB DEFAULT '[]',
    skill_point_base_rate DECIMAL(10,6) DEFAULT 1.0 CHECK (skill_point_base_rate >= 0.1 AND skill_point_base_rate <= 10.0),
    achievement_channel_id BIGINT,
    
    -- メタデータ
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_by BIGINT
);

-- 8. ゲーミフィケーション統計テーブル
CREATE TABLE IF NOT EXISTS gamification_stats (
    guild_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    
    -- アチーブメント統計
    total_achievements INTEGER DEFAULT 0 CHECK (total_achievements >= 0),
    completed_achievements INTEGER DEFAULT 0 CHECK (completed_achievements >= 0),
    achievement_completion_rate DECIMAL(5,2) DEFAULT 0.0 CHECK (achievement_completion_rate >= 0.0 AND achievement_completion_rate <= 100.0),
    
    -- スキル統計
    total_skill_points_earned INTEGER DEFAULT 0 CHECK (total_skill_points_earned >= 0),
    total_skill_points_spent INTEGER DEFAULT 0 CHECK (total_skill_points_spent >= 0),
    unlocked_skills_count INTEGER DEFAULT 0 CHECK (unlocked_skills_count >= 0),
    max_skill_tier INTEGER DEFAULT 0 CHECK (max_skill_tier >= 0),
    
    -- プレステージ統計
    prestige_level INTEGER DEFAULT 0 CHECK (prestige_level >= 0),
    total_prestiges INTEGER DEFAULT 0 CHECK (total_prestiges >= 0),
    prestige_xp_bonus DECIMAL(10,6) DEFAULT 0.0 CHECK (prestige_xp_bonus >= 0.0),
    
    -- 全体統計
    gamification_score DECIMAL(15,6) DEFAULT 0.0 CHECK (gamification_score >= 0.0),
    last_updated TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    PRIMARY KEY (guild_id, user_id),
    
    -- 制約
    CONSTRAINT gamification_stats_achievement_consistency 
        CHECK (completed_achievements <= total_achievements),
    CONSTRAINT gamification_stats_skill_consistency 
        CHECK (total_skill_points_spent <= total_skill_points_earned)
);

-- 9. スキルポイント履歴テーブル
CREATE TABLE IF NOT EXISTS skill_point_history (
    id BIGSERIAL PRIMARY KEY,
    guild_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    
    points_gained INTEGER NOT NULL,
    source TEXT NOT NULL, -- 'achievement', 'level_up', 'prestige', 'admin'
    source_id TEXT,
    description TEXT,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT skill_point_history_points_positive CHECK (points_gained > 0)
);

-- 10. アチーブメント通知キューテーブル
CREATE TABLE IF NOT EXISTS achievement_notifications (
    id BIGSERIAL PRIMARY KEY,
    guild_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    achievement_id TEXT NOT NULL,
    
    notification_type TEXT NOT NULL CHECK (notification_type IN ('unlocked', 'progress', 'completed')),
    message_data JSONB NOT NULL,
    
    status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'sent', 'failed')),
    attempts INTEGER DEFAULT 0 CHECK (attempts >= 0),
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    sent_at TIMESTAMP WITH TIME ZONE,
    error_message TEXT
);

-- インデックス作成

-- アチーブメント関連インデックス
CREATE INDEX idx_achievements_type_rarity ON achievements(type, rarity);
CREATE INDEX idx_achievements_hidden ON achievements(hidden) WHERE hidden = TRUE;

-- ユーザーアチーブメント関連インデックス
CREATE INDEX idx_user_achievements_guild_completed ON user_achievements(guild_id, is_completed);
CREATE INDEX idx_user_achievements_user_completed ON user_achievements(user_id, is_completed);
CREATE INDEX idx_user_achievements_completion_date ON user_achievements(completion_date) WHERE completion_date IS NOT NULL;
CREATE INDEX idx_user_achievements_last_updated ON user_achievements(last_updated);

-- スキル関連インデックス
CREATE INDEX idx_skill_nodes_tier_category ON skill_nodes(tier, category);
CREATE INDEX idx_skill_nodes_type ON skill_nodes(type);

-- ユーザースキル関連インデックス
CREATE INDEX idx_user_skills_guild_level ON user_skills(guild_id, current_level);
CREATE INDEX idx_user_skills_user_unlocked ON user_skills(user_id, unlocked_at) WHERE unlocked_at IS NOT NULL;

-- プレステージ関連インデックス
CREATE INDEX idx_prestige_tiers_type_tier ON prestige_tiers(type, tier);
CREATE INDEX idx_user_prestige_tier_type ON user_prestige(current_tier, current_type);
CREATE INDEX idx_user_prestige_last_prestige ON user_prestige(last_prestige_date) WHERE last_prestige_date IS NOT NULL;

-- 統計関連インデックス
CREATE INDEX idx_gamification_stats_guild_score ON gamification_stats(guild_id, gamification_score DESC);
CREATE INDEX idx_gamification_stats_achievements ON gamification_stats(guild_id, completed_achievements DESC);

-- スキルポイント履歴関連インデックス
CREATE INDEX idx_skill_point_history_user ON skill_point_history(guild_id, user_id);
CREATE INDEX idx_skill_point_history_source ON skill_point_history(source, source_id);
CREATE INDEX idx_skill_point_history_created ON skill_point_history(created_at);

-- 通知キュー関連インデックス
CREATE INDEX idx_achievement_notifications_status ON achievement_notifications(status) WHERE status = 'pending';
CREATE INDEX idx_achievement_notifications_guild_user ON achievement_notifications(guild_id, user_id);
CREATE INDEX idx_achievement_notifications_created ON achievement_notifications(created_at);

-- トリガー関数: updated_atの自動更新

-- gamification_configs用トリガー関数
CREATE OR REPLACE FUNCTION update_gamification_configs_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- gamification_configs用トリガー
DROP TRIGGER IF EXISTS trigger_update_gamification_configs_updated_at ON gamification_configs;
CREATE TRIGGER trigger_update_gamification_configs_updated_at
    BEFORE UPDATE ON gamification_configs
    FOR EACH ROW
    EXECUTE FUNCTION update_gamification_configs_updated_at();

-- user_achievements用トリガー関数
CREATE OR REPLACE FUNCTION update_user_achievements_last_updated()
RETURNS TRIGGER AS $$
BEGIN
    NEW.last_updated = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- user_achievements用トリガー
DROP TRIGGER IF EXISTS trigger_update_user_achievements_last_updated ON user_achievements;
CREATE TRIGGER trigger_update_user_achievements_last_updated
    BEFORE UPDATE ON user_achievements
    FOR EACH ROW
    EXECUTE FUNCTION update_user_achievements_last_updated();

-- gamification_stats用トリガー関数
CREATE OR REPLACE FUNCTION update_gamification_stats_last_updated()
RETURNS TRIGGER AS $$
BEGIN
    NEW.last_updated = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- gamification_stats用トリガー
DROP TRIGGER IF EXISTS trigger_update_gamification_stats_last_updated ON gamification_stats;
CREATE TRIGGER trigger_update_gamification_stats_last_updated
    BEFORE UPDATE ON gamification_stats
    FOR EACH ROW
    EXECUTE FUNCTION update_gamification_stats_last_updated();

-- user_prestige用トリガー関数
CREATE OR REPLACE FUNCTION update_user_prestige_last_updated()
RETURNS TRIGGER AS $$
BEGIN
    NEW.last_updated = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- user_prestige用トリガー
DROP TRIGGER IF EXISTS trigger_update_user_prestige_last_updated ON user_prestige;
CREATE TRIGGER trigger_update_user_prestige_last_updated
    BEFORE UPDATE ON user_prestige
    FOR EACH ROW
    EXECUTE FUNCTION update_user_prestige_last_updated();

-- ビュー作成: ユーザーアチーブメント進捗ビュー
CREATE OR REPLACE VIEW user_achievement_progress AS
SELECT 
    ua.guild_id,
    ua.user_id,
    ua.achievement_id,
    a.name AS achievement_name,
    a.description,
    a.type,
    a.rarity,
    a.target_value,
    ua.current_progress,
    CASE 
        WHEN a.target_value > 0 THEN 
            ROUND((ua.current_progress::DECIMAL / a.target_value * 100), 2)
        ELSE 0 
    END AS progress_percentage,
    ua.is_completed,
    ua.completion_date,
    a.xp_reward,
    a.skill_points_reward,
    a.icon,
    a.hidden
FROM user_achievements ua
JOIN achievements a ON ua.achievement_id = a.id;

-- ビュー作成: ユーザースキル詳細ビュー
CREATE OR REPLACE VIEW user_skill_details AS
SELECT 
    us.guild_id,
    us.user_id,
    us.skill_id,
    sn.name AS skill_name,
    sn.description,
    sn.type,
    sn.tier,
    sn.category,
    us.current_level,
    sn.max_level,
    us.total_invested_points,
    sn.skill_points_cost,
    sn.effect_per_level,
    (us.current_level * sn.effect_per_level) AS total_effect,
    us.unlocked_at,
    us.last_upgraded,
    sn.icon
FROM user_skills us
JOIN skill_nodes sn ON us.skill_id = sn.id;

-- ビュー作成: ギルドアチーブメント統計ビュー
CREATE OR REPLACE VIEW guild_achievement_stats AS
SELECT 
    guild_id,
    COUNT(DISTINCT user_id) AS total_users,
    COUNT(*) AS total_user_achievements,
    COUNT(*) FILTER (WHERE is_completed = TRUE) AS completed_achievements,
    ROUND(
        (COUNT(*) FILTER (WHERE is_completed = TRUE)::DECIMAL / COUNT(*) * 100), 2
    ) AS completion_rate,
    COUNT(DISTINCT achievement_id) AS unique_achievements_attempted,
    AVG(current_progress) AS avg_progress
FROM user_achievements
GROUP BY guild_id;

-- 初期データ挿入: デフォルトアチーブメント

-- レベル系アチーブメント
INSERT INTO achievements (id, name, description, type, rarity, condition_type, target_value, xp_reward, skill_points_reward, icon) 
VALUES 
    ('level_5', '初心者卒業', 'レベル5に到達しました', 'level', 'common', 'level', 5, 500, 1, '🎯'),
    ('level_10', '成長の道', 'レベル10に到達しました', 'level', 'common', 'level', 10, 1000, 1, '📈'),
    ('level_25', '上級者への道', 'レベル25に到達しました', 'level', 'uncommon', 'level', 25, 2500, 2, '⭐'),
    ('level_50', '熟練者', 'レベル50に到達しました', 'level', 'rare', 'level', 50, 5000, 5, '💎'),
    ('level_75', 'エキスパート', 'レベル75に到達しました', 'level', 'epic', 'level', 75, 7500, 7, '🏆'),
    ('level_100', 'レジェンド', 'レベル100に到達しました', 'level', 'legendary', 'level', 100, 10000, 10, '👑')
ON CONFLICT (id) DO NOTHING;

-- XP系アチーブメント
INSERT INTO achievements (id, name, description, type, rarity, condition_type, target_value, xp_reward, skill_points_reward, icon)
VALUES 
    ('total_xp_1000', '千の道のり', '総XP 1,000獲得', 'xp_total', 'common', 'xp_total', 1000, 100, 1, '💫'),
    ('total_xp_10000', '万の実績', '総XP 10,000獲得', 'xp_total', 'uncommon', 'xp_total', 10000, 1000, 2, '⚡'),
    ('total_xp_50000', '経験豊富', '総XP 50,000獲得', 'xp_total', 'rare', 'xp_total', 50000, 2500, 5, '🌟'),
    ('total_xp_100000', '百戦練磨', '総XP 100,000獲得', 'xp_total', 'epic', 'xp_total', 100000, 5000, 10, '✨'),
    ('total_xp_500000', '経験の王者', '総XP 500,000獲得', 'xp_total', 'legendary', 'xp_total', 500000, 25000, 20, '🔥')
ON CONFLICT (id) DO NOTHING;

-- メッセージ系アチーブメント
INSERT INTO achievements (id, name, description, type, rarity, condition_type, target_value, xp_reward, skill_points_reward, icon)
VALUES 
    ('message_100', 'おしゃべり好き', 'メッセージを100回送信', 'message_count', 'common', 'message_count', 100, 200, 1, '💬'),
    ('message_1000', '会話の達人', 'メッセージを1,000回送信', 'message_count', 'uncommon', 'message_count', 1000, 500, 2, '🗣️'),
    ('message_5000', 'コミュニケーター', 'メッセージを5,000回送信', 'message_count', 'rare', 'message_count', 5000, 1000, 5, '📢')
ON CONFLICT (id) DO NOTHING;

-- 初期データ挿入: デフォルトスキルノード

-- ティア1: 基本スキル
INSERT INTO skill_nodes (id, name, description, type, tier, skill_points_cost, max_level, effect_per_level, icon, category)
VALUES 
    ('xp_boost_basic', '経験値アップ I', 'メッセージXP獲得量を5%増加', 'xp_boost', 1, 1, 5, 0.05, '📚', '基本'),
    ('voice_boost_basic', '音声経験値アップ I', '音声XP獲得量を3%増加', 'voice_boost', 1, 1, 5, 0.03, '🎤', '音声'),
    ('social_boost_basic', 'ソーシャルボーナス I', 'ソーシャル活動でのボーナス2%増加', 'social_boost', 1, 1, 3, 0.02, '👥', 'ソーシャル')
ON CONFLICT (id) DO NOTHING;

-- ティア2: 中級スキル
INSERT INTO skill_nodes (id, name, description, type, tier, prerequisites, skill_points_cost, max_level, effect_per_level, icon, category)
VALUES 
    ('cooldown_reduce_basic', 'クールダウン短縮 I', 'XPクールダウンを2秒短縮', 'cooldown_reduce', 2, ARRAY['xp_boost_basic'], 2, 3, 2.0, '⏱️', '効率'),
    ('voice_boost_advanced', '音声経験値アップ II', '音声XP獲得量を5%増加', 'voice_boost', 2, ARRAY['voice_boost_basic'], 2, 5, 0.05, '🎵', '音声'),
    ('streak_protect_basic', 'ストリーク保護 I', '連続記録の保護機能', 'streak_protect', 2, ARRAY['social_boost_basic'], 3, 2, 1.0, '🛡️', '保護')
ON CONFLICT (id) DO NOTHING;

-- ティア3: 上級スキル
INSERT INTO skill_nodes (id, name, description, type, tier, prerequisites, skill_points_cost, max_level, effect_per_level, icon, category)
VALUES 
    ('quality_boost_advanced', '品質分析ボーナス', 'AI品質分析ボーナスを10%増加', 'quality_boost', 3, ARRAY['xp_boost_basic', 'cooldown_reduce_basic'], 5, 3, 0.10, '🧠', '高度'),
    ('xp_boost_master', '経験値アップ Master', 'すべてのXP獲得量を7%増加', 'xp_boost', 3, ARRAY['xp_boost_basic', 'voice_boost_advanced'], 7, 3, 0.07, '⚡', '究極')
ON CONFLICT (id) DO NOTHING;

-- 初期データ挿入: デフォルトプレステージティア

-- 標準プレステージティア
INSERT INTO prestige_tiers (tier, name, type, required_level, required_achievements, required_skill_points, benefits, icon, badge)
VALUES 
    (1, '新星', 'standard', 100, 10, 50, '{"xp_multiplier": 1.1, "skill_point_multiplier": 1.2, "daily_xp_bonus": 500, "exclusive_titles": ["新星の道"]}', '🌟', '⭐'),
    (2, '熟練者', 'standard', 150, 25, 100, '{"xp_multiplier": 1.2, "skill_point_multiplier": 1.4, "daily_xp_bonus": 1000, "exclusive_titles": ["熟練者の証"], "achievement_bonus": 1.2}', '💎', '💎'),
    (3, 'マスター', 'standard', 200, 50, 200, '{"xp_multiplier": 1.5, "voice_xp_multiplier": 1.3, "skill_point_multiplier": 1.6, "daily_xp_bonus": 2000, "exclusive_titles": ["マスターの称号"], "achievement_bonus": 1.5, "special_features": {"custom_rank_card": true}}', '👑', '👑')
ON CONFLICT (tier, type) DO NOTHING;

-- 音声特化プレステージティア
INSERT INTO prestige_tiers (tier, name, type, required_level, required_achievements, required_skill_points, benefits, icon, badge)
VALUES 
    (1, 'ボイスマスター', 'voice', 100, 5, 30, '{"voice_xp_multiplier": 1.5, "skill_point_multiplier": 1.1, "daily_xp_bonus": 300, "exclusive_titles": ["ボイスマスター"]}', '🎤', '🎵'),
    (2, 'サウンドレジェンド', 'voice', 150, 15, 75, '{"voice_xp_multiplier": 2.0, "xp_multiplier": 1.1, "skill_point_multiplier": 1.3, "daily_xp_bonus": 800, "exclusive_titles": ["サウンドレジェンド"]}', '🎶', '🎼')
ON CONFLICT (tier, type) DO NOTHING;

-- インデックス統計更新
ANALYZE achievements;
ANALYZE user_achievements;
ANALYZE skill_nodes;
ANALYZE user_skills;
ANALYZE prestige_tiers;
ANALYZE user_prestige;
ANALYZE gamification_configs;
ANALYZE gamification_stats;

-- 完了メッセージ
DO $$
BEGIN
    RAISE NOTICE 'アチーブメント・スキルツリー・プレステージシステムのデータベーススキーマとデフォルトデータの作成が完了しました。';
    RAISE NOTICE 'テーブル数: 10個、インデックス数: 21個、ビュー数: 3個、トリガー数: 4個';
    RAISE NOTICE 'デフォルトアチーブメント: %個、デフォルトスキル: %個、デフォルトプレステージティア: %個', 
        (SELECT COUNT(*) FROM achievements),
        (SELECT COUNT(*) FROM skill_nodes),
        (SELECT COUNT(*) FROM prestige_tiers);
END $$;
