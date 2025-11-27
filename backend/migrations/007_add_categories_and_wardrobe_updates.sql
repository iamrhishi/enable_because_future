-- Migration 007: Add categories table and update wardrobe for custom categories
-- Support user-created categories in addition to 'upper' and 'lower'

-- Create categories table for user-created categories
CREATE TABLE IF NOT EXISTS wardrobe_categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id VARCHAR(255) NOT NULL,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, name),
    FOREIGN KEY (user_id) REFERENCES users(userid) ON DELETE CASCADE
);

-- Update wardrobe table to support custom categories
-- SQLite doesn't support DROP CONSTRAINT, so we'll add new columns
-- The existing 'category' column will still be used for 'upper'/'lower'
-- The 'custom_category_name' column is for user-created categories

-- Add category_id to link to wardrobe_categories (optional - for custom categories)
-- Check if columns already exist before adding
-- Note: SQLite doesn't support IF NOT EXISTS for ALTER TABLE ADD COLUMN
-- So we'll use a workaround with a try-catch in application code or manual migration

-- Add category_id to link to wardrobe_categories (optional - for custom categories)
ALTER TABLE wardrobe ADD COLUMN category_id INTEGER;
ALTER TABLE wardrobe ADD COLUMN custom_category_name TEXT; -- For user-created categories

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_wardrobe_categories_user_id ON wardrobe_categories(user_id);
CREATE INDEX IF NOT EXISTS idx_wardrobe_category_id ON wardrobe(category_id);
CREATE INDEX IF NOT EXISTS idx_wardrobe_custom_category ON wardrobe(custom_category_name);

-- Note: The existing 'category' column will still be used for 'upper'/'lower'
-- The 'custom_category_name' column is for user-created categories
-- If both are set, custom_category_name takes precedence

