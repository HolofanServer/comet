-- Migration: Add animated column to role_emoji_mappings table
-- Date: 2025-07-17
-- Description: Add animated field to support animated emoji flags

-- Add animated column if it doesn't exist
ALTER TABLE role_emoji_mappings 
ADD COLUMN IF NOT EXISTS animated BOOLEAN DEFAULT FALSE;

-- Add comment for documentation
COMMENT ON COLUMN role_emoji_mappings.animated IS '絵文字がアニメーション絵文字かどうかのフラグ';

-- Display current table structure
SELECT column_name, data_type, is_nullable, column_default
FROM information_schema.columns 
WHERE table_name = 'role_emoji_mappings'
ORDER BY ordinal_position;
