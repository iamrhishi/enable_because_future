-- Migration 012: Support user-created category sections
-- Users can create custom sections in addition to platform sections
-- Note: icon_name, icon_url, and user_id should already be in the table from migration 010
-- This migration is for backward compatibility if migration 010 was run before these fields were added

-- Add user_id to category_sections if not exists (NULL = platform, user_id = user-created)
-- SQLite doesn't support IF NOT EXISTS for ALTER TABLE, so we'll check in application code
-- For existing databases, these columns may already exist from migration 010

-- Create index for user sections (if not exists)
CREATE INDEX IF NOT EXISTS idx_category_sections_user_id ON category_sections(user_id);

-- Note: Platform sections have user_id = NULL
-- User-created sections have user_id set to the user's ID
-- Icons are not stored in DB, only icon_name (identifier) and icon_url (optional URL)

