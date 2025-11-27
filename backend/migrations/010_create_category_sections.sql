-- Migration 010: Create platform category sections
-- Platform-defined sections available to all users

CREATE TABLE IF NOT EXISTS category_sections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(255) NOT NULL, -- 'upper_body', 'lower_body', 'accessoires', 'wishlist'
    display_name VARCHAR(255) NOT NULL, -- 'Upper body', 'Lower body', 'Accessoires', 'Wishlist'
    description TEXT,
    sort_order INTEGER DEFAULT 0,
    icon_name VARCHAR(255), -- Icon identifier/name (not stored in DB, just reference)
    icon_url TEXT, -- Optional icon URL if user provides one
    user_id VARCHAR(255), -- NULL for platform sections, user_id for user-created sections
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, name) -- Allow same name for different users, but unique per user
);

-- Insert platform-defined sections (user_id = NULL for platform sections)
INSERT OR IGNORE INTO category_sections (name, display_name, description, sort_order, icon_name, user_id) VALUES
('upper_body', 'Upper body', 'Clothing items for upper body', 1, 'upper_body', NULL),
('lower_body', 'Lower body', 'Clothing items for lower body', 2, 'lower_body', NULL),
('accessoires', 'Accessoires', 'Accessories and other items', 3, 'accessoires', NULL),
('wishlist', 'Wishlist', 'Items saved for later', 4, 'wishlist', NULL);

-- Create index
CREATE INDEX IF NOT EXISTS idx_category_sections_name ON category_sections(name);

