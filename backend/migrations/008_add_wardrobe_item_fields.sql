-- Migration 008: Add missing fields to wardrobe items
-- Based on mobile app UI requirements: fabric, care_instructions, size, description

-- Add new columns to wardrobe table
ALTER TABLE wardrobe ADD COLUMN fabric TEXT; -- JSON array: [{"name": "cotton", "percentage": 100}]
ALTER TABLE wardrobe ADD COLUMN care_instructions TEXT; -- JSON array or comma-separated text
ALTER TABLE wardrobe ADD COLUMN size TEXT; -- Garment size (e.g., "M", "L", "42")
ALTER TABLE wardrobe ADD COLUMN description TEXT; -- Short description

-- Create indexes for new fields
CREATE INDEX IF NOT EXISTS idx_wardrobe_size ON wardrobe(size);
CREATE INDEX IF NOT EXISTS idx_wardrobe_fabric ON wardrobe(fabric);

