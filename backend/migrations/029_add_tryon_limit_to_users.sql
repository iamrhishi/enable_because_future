-- Migration 029: Add tryon_count to users table
ALTER TABLE users ADD COLUMN tryon_count INTEGER DEFAULT 0;
