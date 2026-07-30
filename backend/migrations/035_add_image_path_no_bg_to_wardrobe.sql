-- Migration 035: Add image_path_no_bg to wardrobe
-- Caches the background-removed version of a wardrobe item's image the first
-- time it's used in a try-on, so subsequent try-ons with the same item skip
-- the rembg call entirely instead of recomputing it every time.

ALTER TABLE wardrobe ADD COLUMN image_path_no_bg TEXT;
