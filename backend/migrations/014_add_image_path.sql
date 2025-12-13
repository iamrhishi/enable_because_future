-- Migration 014: Add image_path column to wardrobe table
-- Replaces garment_image BLOB with image_path TEXT for local file storage

-- Add image_path column to wardrobe table
ALTER TABLE wardrobe ADD COLUMN image_path TEXT;

-- Create index for image_path
CREATE INDEX IF NOT EXISTS idx_wardrobe_image_path ON wardrobe(image_path);

