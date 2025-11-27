-- Migration 011: Seed platform-defined categories
-- These categories are available to all users under each section
-- Users can also create custom categories under these sections

-- Note: Platform categories are stored with user_id = 'PLATFORM' or NULL
-- When a user registers, we'll copy these platform categories for that user
-- OR we can use a separate table for platform categories and reference them

-- For now, we'll create a table to store platform categories
CREATE TABLE IF NOT EXISTS platform_categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category_section VARCHAR(255) NOT NULL, -- 'upper_body', 'lower_body', 'accessoires', 'wishlist'
    name VARCHAR(255) NOT NULL, -- 'T-shirts', 'Shirts', 'Tops', etc.
    display_name VARCHAR(255) NOT NULL,
    description TEXT,
    sort_order INTEGER DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(category_section, name),
    FOREIGN KEY (category_section) REFERENCES category_sections(name)
);

-- Seed platform categories for Upper body
INSERT OR IGNORE INTO platform_categories (category_section, name, display_name, sort_order) VALUES
('upper_body', 't_shirts', 'T-shirts', 1),
('upper_body', 'shirts', 'Shirts', 2),
('upper_body', 'tops', 'Tops', 3),
('upper_body', 'pullover_cardigans', 'Pullover & Cardigans', 4),
('upper_body', 'jackets', 'Jackets', 5),
('upper_body', 'others', 'Others', 99);

-- Seed platform categories for Lower body
INSERT OR IGNORE INTO platform_categories (category_section, name, display_name, sort_order) VALUES
('lower_body', 'long_trousers', 'Long Trousers', 1),
('lower_body', 'short_trousers', 'Short Trousers', 2),
('lower_body', 'skirts', 'Skirts', 3),
('lower_body', 'leggings', 'Leggings', 4),
('lower_body', 'others', 'Others', 99);

-- Seed platform categories for Accessoires
INSERT OR IGNORE INTO platform_categories (category_section, name, display_name, sort_order) VALUES
('accessoires', 'sandals', 'Sandals', 1),
('accessoires', 'sneakers', 'Sneakers', 2),
('accessoires', 'caps', 'Caps', 3),
('accessoires', 'bags', 'Bags', 4),
('accessoires', 'others', 'Others', 99);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_platform_categories_section ON platform_categories(category_section);
CREATE INDEX IF NOT EXISTS idx_platform_categories_name ON platform_categories(name);

