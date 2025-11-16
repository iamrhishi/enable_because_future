-- Migration 002: Add body_measurements table
-- Stores user body measurements for fitting calculations

CREATE TABLE IF NOT EXISTS body_measurements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id VARCHAR(255) NOT NULL,
    height REAL,
    weight REAL,
    chest REAL,
    waist REAL,
    hips REAL,
    inseam REAL,
    shoulder_width REAL,
    arm_length REAL,
    unit TEXT DEFAULT 'metric' CHECK(unit IN ('metric', 'imperial')),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(userid) ON DELETE CASCADE,
    UNIQUE(user_id)
);

CREATE INDEX IF NOT EXISTS idx_body_measurements_user_id ON body_measurements(user_id);

