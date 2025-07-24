-- Migration: Add thumbnail_url and creator_icon fields to note_posts table
-- Date: 2025-07-17
-- Description: Add support for thumbnail images and creator icons in note notifications

-- Add thumbnail_url column if it doesn't exist
ALTER TABLE note_posts 
ADD COLUMN IF NOT EXISTS thumbnail_url TEXT;

-- Add creator_icon column if it doesn't exist
ALTER TABLE note_posts 
ADD COLUMN IF NOT EXISTS creator_icon TEXT;

-- Add comment for documentation
COMMENT ON COLUMN note_posts.thumbnail_url IS 'サムネイル画像のURL (RSS media:thumbnail から取得)';
COMMENT ON COLUMN note_posts.creator_icon IS '作成者アイコンのURL (RSS note:creatorImage から取得)';

-- Display current table structure
SELECT column_name, data_type, is_nullable, column_default
FROM information_schema.columns 
WHERE table_name = 'note_posts'
ORDER BY ordinal_position;
