-- カスタムレベル計算公式テーブル作成
-- Linear/Exponential/Logarithmic/Custom/Stepped公式による
-- 柔軟なレベル進行システムの設定を格納

CREATE TABLE IF NOT EXISTS level_formulas (
    guild_id BIGINT PRIMARY KEY,
    formula_data JSONB NOT NULL,
    formula_name VARCHAR(100) NOT NULL,
    formula_type VARCHAR(20) NOT NULL,
    max_level INTEGER DEFAULT 100,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_by BIGINT, -- Discord User ID
    is_active BOOLEAN DEFAULT TRUE
);

-- インデックス作成（パフォーマンス向上）
CREATE INDEX IF NOT EXISTS idx_level_formulas_type ON level_formulas(formula_type);
CREATE INDEX IF NOT EXISTS idx_level_formulas_active ON level_formulas(guild_id, is_active);
CREATE INDEX IF NOT EXISTS idx_level_formulas_updated ON level_formulas(updated_at);

-- JSONB検索用のGINインデックス（公式データ検索用）
CREATE INDEX IF NOT EXISTS idx_level_formulas_data ON level_formulas USING GIN(formula_data);

-- プリセット公式テンプレートテーブル
CREATE TABLE IF NOT EXISTS formula_presets (
    preset_id SERIAL PRIMARY KEY,
    preset_name VARCHAR(100) NOT NULL UNIQUE,
    formula_data JSONB NOT NULL,
    description TEXT,
    category VARCHAR(50) DEFAULT 'custom',
    difficulty_level INTEGER DEFAULT 1 CHECK (difficulty_level BETWEEN 1 AND 5),
    recommended_guild_size VARCHAR(20) DEFAULT 'any', -- small/medium/large/any
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    is_public BOOLEAN DEFAULT TRUE
);

-- プリセット公式の初期データ挿入
INSERT INTO formula_presets (preset_name, formula_data, description, category, difficulty_level) VALUES
('バランス線形', 
 '{"formula_type": "linear", "name": "バランス線形", "description": "一定ペースでレベルアップ。初心者に優しい設計", "linear": {"base_xp": 100, "level_multiplier": 50}, "max_level": 100}',
 '一定ペースでレベルアップする初心者向け公式', 'balanced', 1),

('競争型指数',
 '{"formula_type": "exponential", "name": "競争型指数", "description": "高レベルほど大幅にXP必要。長期コミット型", "exponential": {"base_xp": 80, "growth_rate": 1.15, "max_level_xp": 1000000}, "max_level": 200}',
 '高レベルで急激に難しくなる競争型公式', 'competitive', 3),

('カジュアル対数',
 '{"formula_type": "logarithmic", "name": "カジュアル対数", "description": "高レベルでも比較的上がりやすい。ライト層向け", "logarithmic": {"base_xp": 120, "log_base": 1.8, "scale_factor": 1.3}, "max_level": 150}',
 'ライト層向けのゆるやかな成長公式', 'casual', 2),

('ハイブリッド段階式',
 '{"formula_type": "stepped", "name": "ハイブリッド段階式", "description": "レベル帯ごとに異なる成長率を適用", "stepped": {"level_ranges": [{"min_level": 1, "max_level": 25, "base_xp": 50, "multiplier": 1.0}, {"min_level": 26, "max_level": 75, "base_xp": 100, "multiplier": 1.5}, {"min_level": 76, "max_level": null, "base_xp": 200, "multiplier": 2.0}]}, "max_level": 150}',
 'レベル帯ごとに成長率が変わる段階式公式', 'hybrid', 4);

-- レベル計算キャッシュテーブル（パフォーマンス最適化用）
CREATE TABLE IF NOT EXISTS level_calculation_cache (
    guild_id BIGINT,
    level INTEGER,
    total_xp_required BIGINT,
    level_xp_required INTEGER,
    cache_time TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    PRIMARY KEY (guild_id, level)
);

-- インデックス
CREATE INDEX IF NOT EXISTS idx_level_cache_time ON level_calculation_cache(cache_time);

-- コメント追加
COMMENT ON TABLE level_formulas IS 'サーバーごとのカスタムレベル計算公式設定';
COMMENT ON COLUMN level_formulas.guild_id IS 'DiscordサーバーID';
COMMENT ON COLUMN level_formulas.formula_data IS 'LevelFormulaモデルのJSONB形式データ';
COMMENT ON COLUMN level_formulas.formula_name IS '公式名（表示用）';
COMMENT ON COLUMN level_formulas.formula_type IS '公式タイプ（linear/exponential/logarithmic/custom/stepped）';
COMMENT ON COLUMN level_formulas.max_level IS '最大レベル制限';
COMMENT ON COLUMN level_formulas.created_by IS '作成者のDiscord User ID';
COMMENT ON COLUMN level_formulas.is_active IS 'アクティブ状態';

COMMENT ON TABLE formula_presets IS '公式プリセットテンプレート';
COMMENT ON TABLE level_calculation_cache IS 'レベル計算結果のキャッシュ（パフォーマンス向上用）';
