-- Migration 030: Add country to users table
-- Adds country field for user address information

ALTER TABLE users ADD COLUMN country TEXT;
