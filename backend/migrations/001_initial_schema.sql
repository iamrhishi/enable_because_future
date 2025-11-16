-- Migration 001: Initial schema
-- Creates users, wardrobe, and hello tables

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    userid VARCHAR(255) NOT NULL UNIQUE,
    email VARCHAR(255) NOT NULL UNIQUE,
    first_name VARCHAR(255),
    last_name VARCHAR(255),
    password VARCHAR(255) NOT NULL,
    age INTEGER,
    gender VARCHAR(50),
    weight REAL,
    height REAL,
    physique VARCHAR(255),
    avatar BLOB,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS wardrobe (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id VARCHAR(255) NOT NULL,
    garment_id VARCHAR(255) NOT NULL,
    garment_image BLOB NOT NULL,
    garment_type TEXT NOT NULL CHECK(garment_type IN ('upper', 'lower')),
    garment_url TEXT,
    date_added DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, garment_id)
);

CREATE TABLE IF NOT EXISTS hello (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    message VARCHAR(255) NOT NULL
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_userid ON users(userid);
CREATE INDEX IF NOT EXISTS idx_wardrobe_user_id ON wardrobe(user_id);
CREATE INDEX IF NOT EXISTS idx_wardrobe_garment_type ON wardrobe(garment_type);
CREATE INDEX IF NOT EXISTS idx_wardrobe_date_added ON wardrobe(date_added);

-- Insert test message
INSERT OR IGNORE INTO hello (message) VALUES ('Hello World');

