-- Migration 022: Add garment_url to tryon_jobs table
-- Links try-on results to their source garment URLs

ALTER TABLE tryon_jobs ADD COLUMN garment_url TEXT;
