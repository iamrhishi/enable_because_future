-- Migration 005: Add garment_metadata table
-- Stores metadata for scraped products

CREATE TABLE IF NOT EXISTS garment_metadata (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    url TEXT NOT NULL UNIQUE,
    title TEXT,
    price TEXT,
    brand TEXT,
    images TEXT, -- JSON array of image URLs
    sizes TEXT, -- JSON array of available sizes
    size_chart TEXT, -- JSON object with size measurements
    colors TEXT, -- JSON array of available colors
    scraped_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_garment_metadata_url ON garment_metadata(url);

