-- Migration 009: Add category_section to wardrobe_categories
-- Links user-created categories to platform-defined sections (upper_body, lower_body, accessoires, wishlist)

ALTER TABLE wardrobe_categories ADD COLUMN category_section TEXT; -- 'upper_body', 'lower_body', 'accessoires', 'wishlist'

-- Create index for category_section
CREATE INDEX IF NOT EXISTS idx_wardrobe_categories_section ON wardrobe_categories(category_section);

