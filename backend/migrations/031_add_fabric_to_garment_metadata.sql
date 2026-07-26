-- Migration 031: Add fabric to garment_metadata table
ALTER TABLE garment_metadata ADD COLUMN fabric TEXT;
