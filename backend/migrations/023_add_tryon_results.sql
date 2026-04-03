-- Migration 023: Add tryon_results table
-- Stores saved try-on results for users (extension-based synchronous try-ons)

CREATE TABLE IF NOT EXISTS tryon_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id VARCHAR(255) NOT NULL,
    result_image LONGBLOB NOT NULL,  -- Base64 encoded PNG or binary
    applied_garments JSON NOT NULL,  -- Array: [{"id": 123, "type": "upper"}, {"id": 456, "type": "lower"}]
    try_on_count INTEGER NOT NULL,   -- 1 or 2 (number of layers)
    original_avatar LONGBLOB NOT NULL,  -- Original avatar base64 for reference
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(userid) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_tryon_results_user_id ON tryon_results(user_id);
CREATE INDEX IF NOT EXISTS idx_tryon_results_created_at ON tryon_results(created_at DESC);
