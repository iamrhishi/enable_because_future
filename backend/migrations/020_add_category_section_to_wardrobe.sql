-- Migration 020: Add category_section to wardrobe table
-- This allows filtering wardrobe items by section (upper_body, lower_body, accessoires, wishlist)
-- Without requiring a specific category_id

-- Add category_section column to wardrobe table
ALTER TABLE wardrobe ADD COLUMN category_section VARCHAR(100);

-- Create index for faster filtering by category_section
CREATE INDEX IF NOT EXISTS idx_wardrobe_category_section ON wardrobe(category_section);

-- Note: Existing items will have NULL category_section (backward compatible)
-- Items can have both category_section and category_id set
-- Priority: category_section is the primary way to group items (upper_body, lower_body, accessoires, wishlist)
