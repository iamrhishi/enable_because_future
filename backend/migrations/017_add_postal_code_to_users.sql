-- Migration 017: Add postal_code to users table
-- Adds postal_code field for user address information

ALTER TABLE users ADD COLUMN postal_code TEXT;

