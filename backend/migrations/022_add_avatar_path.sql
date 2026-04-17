-- Migration 022: Add avatar_path column for file-based avatar storage
-- This migration adds the avatar_path column to store file paths instead of BLOBs

ALTER TABLE users ADD COLUMN avatar_path VARCHAR(255);

CREATE INDEX IF NOT EXISTS idx_users_avatar_path ON users(avatar_path);
