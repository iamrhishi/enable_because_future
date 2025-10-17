-- Create wardrobe table for storing user favorite garments (MySQL version)
CREATE TABLE IF NOT EXISTS wardrobe (
    id INT PRIMARY KEY AUTO_INCREMENT,
    user_id VARCHAR(255) NOT NULL,
    garment_id VARCHAR(255) NOT NULL,
    garment_image LONGBLOB NOT NULL,
    garment_type ENUM('upper', 'lower') NOT NULL,
    garment_url TEXT,
    date_added DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY unique_user_garment (user_id, garment_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Create indexes for faster queries
CREATE INDEX idx_wardrobe_user_id ON wardrobe(user_id);
CREATE INDEX idx_wardrobe_garment_type ON wardrobe(garment_type);
CREATE INDEX idx_wardrobe_date_added ON wardrobe(date_added);

-- Example queries:
-- Get all garments for a user:
-- SELECT * FROM wardrobe WHERE user_id = 'user123' ORDER BY date_added DESC;

-- Get only upper garments for a user:
-- SELECT * FROM wardrobe WHERE user_id = 'user123' AND garment_type = 'upper' ORDER BY date_added DESC;