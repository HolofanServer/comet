-- AUS (Art Unauthorized-repost Shield) システムのテーブル作成
-- 作成日: 2025年11月6日

-- 認証済み絵師情報テーブル
CREATE TABLE IF NOT EXISTS verified_artists (
    user_id BIGINT PRIMARY KEY,
    twitter_handle TEXT NOT NULL,
    twitter_url TEXT NOT NULL,
    verified_at TIMESTAMP DEFAULT NOW(),
    verified_by BIGINT,
    notes TEXT
);

-- インデックス作成
CREATE INDEX IF NOT EXISTS idx_verified_artists_twitter_handle 
    ON verified_artists(twitter_handle);

-- 絵師認証申請チケットテーブル
CREATE TABLE IF NOT EXISTS verification_tickets (
    ticket_id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    twitter_handle TEXT NOT NULL,
    twitter_url TEXT,
    proof_description TEXT,
    status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected')),
    created_at TIMESTAMP DEFAULT NOW(),
    resolved_at TIMESTAMP,
    resolved_by BIGINT,
    channel_id BIGINT,
    rejection_reason TEXT
);

-- インデックス作成
CREATE INDEX IF NOT EXISTS idx_verification_tickets_user_id 
    ON verification_tickets(user_id);
CREATE INDEX IF NOT EXISTS idx_verification_tickets_status 
    ON verification_tickets(status);
CREATE INDEX IF NOT EXISTS idx_verification_tickets_channel_id 
    ON verification_tickets(channel_id);

-- コメント追加
COMMENT ON TABLE verified_artists IS '認証済み絵師情報を管理';
COMMENT ON TABLE verification_tickets IS '絵師認証申請チケットを管理';

COMMENT ON COLUMN verified_artists.user_id IS 'Discord User ID (主キー)';
COMMENT ON COLUMN verified_artists.twitter_handle IS 'Twitterハンドルネーム (@なし)';
COMMENT ON COLUMN verified_artists.twitter_url IS 'Twitter プロフィールURL';
COMMENT ON COLUMN verified_artists.verified_at IS '認証日時';
COMMENT ON COLUMN verified_artists.verified_by IS '承認した運営のUser ID';
COMMENT ON COLUMN verified_artists.notes IS '備考・メモ';

COMMENT ON COLUMN verification_tickets.ticket_id IS 'チケットID (自動採番)';
COMMENT ON COLUMN verification_tickets.user_id IS '申請者のDiscord User ID';
COMMENT ON COLUMN verification_tickets.twitter_handle IS 'Twitterハンドルネームまたは URL';
COMMENT ON COLUMN verification_tickets.twitter_url IS 'Twitter プロフィールURL (正規化後)';
COMMENT ON COLUMN verification_tickets.proof_description IS '本人確認方法の説明';
COMMENT ON COLUMN verification_tickets.status IS 'チケットステータス: pending/approved/rejected';
COMMENT ON COLUMN verification_tickets.created_at IS 'チケット作成日時';
COMMENT ON COLUMN verification_tickets.resolved_at IS 'チケット解決日時';
COMMENT ON COLUMN verification_tickets.resolved_by IS '処理した運営のUser ID';
COMMENT ON COLUMN verification_tickets.channel_id IS '専用チケットチャンネルID';
COMMENT ON COLUMN verification_tickets.rejection_reason IS '却下理由（却下時のみ）';
