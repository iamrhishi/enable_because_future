-- Migration 019: Add image caching to garment_metadata table
-- Cache actual image bytes (not just URLs) for faster try-on requests
-- Only cache 1-2 images that are actually used for Gemini

-- SQLite doesn't support IF NOT EXISTS for ALTER TABLE, so we check first
-- Add columns only if they don't exist (handled by migration manager or manual check)

-- Note: If columns already exist, this will fail - that's okay, migration will be skipped
ALTER TABLE garment_metadata ADD COLUMN cached_image_1 BLOB;  -- First image bytes (most commonly used)
ALTER TABLE garment_metadata ADD COLUMN cached_image_2 BLOB;  -- Second image bytes (optional)
ALTER TABLE garment_metadata ADD COLUMN cached_image_1_url TEXT;  -- URL of first cached image
ALTER TABLE garment_metadata ADD COLUMN cached_image_2_url TEXT;  -- URL of second cached image
ALTER TABLE garment_metadata ADD COLUMN cached_images_at DATETIME;  -- When images were cached
ALTER TABLE garment_metadata ADD COLUMN last_accessed_at DATETIME;  -- Track last access for TTL (set via code, not default)

-- Set initial last_accessed_at for existing rows
UPDATE garment_metadata SET last_accessed_at = updated_at WHERE last_accessed_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_garment_metadata_last_accessed ON garment_metadata(last_accessed_at);
CREATE INDEX IF NOT EXISTS idx_garment_metadata_cached_images_at ON garment_metadata(cached_images_at);

