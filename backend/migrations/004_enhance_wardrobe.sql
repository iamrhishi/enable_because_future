-- Migration 004: Enhance wardrobe table
-- Add category, type, brand, color fields and is_external flag

-- Add new columns to wardrobe table
ALTER TABLE wardrobe ADD COLUMN category TEXT CHECK(category IN ('upper', 'lower'));
ALTER TABLE wardrobe ADD COLUMN garment_category_type TEXT; -- e.g., 'shirt', 'pants', 'jacket'
ALTER TABLE wardrobe ADD COLUMN brand TEXT;
ALTER TABLE wardrobe ADD COLUMN color TEXT;
ALTER TABLE wardrobe ADD COLUMN is_external BOOLEAN DEFAULT FALSE; -- True for saved external products
ALTER TABLE wardrobe ADD COLUMN title TEXT; -- For external products
ALTER TABLE wardrobe ADD COLUMN price TEXT; -- For external products

-- Update existing rows: set category from garment_type
UPDATE wardrobe SET category = garment_type WHERE category IS NULL;

-- Create indexes for new fields
CREATE INDEX IF NOT EXISTS idx_wardrobe_category ON wardrobe(category);
CREATE INDEX IF NOT EXISTS idx_wardrobe_is_external ON wardrobe(is_external);

