-- Migration 034: Add is_deleted/deleted_at to users table
-- Explicit erasure-status flag/timestamp, distinct from is_active (which is
-- also flipped for other reasons). Set by User.deactivate_account() once all
-- of the user's personal data has been erased/anonymized.

ALTER TABLE users ADD COLUMN is_deleted BOOLEAN DEFAULT FALSE;
ALTER TABLE users ADD COLUMN deleted_at DATETIME;
