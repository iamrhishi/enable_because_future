-- Analytics events table for daily reporting
-- Events are captured, reported daily, then wiped

CREATE TABLE IF NOT EXISTS analytics_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL,           -- 'login', 'logout', 'signup', 'delete_account', 'password_reset', 'tryon', 'wardrobe_add', etc.
    user_id TEXT,                       -- nullable for failed logins
    user_email TEXT,                    -- for reporting (nullable)
    metadata TEXT,                      -- JSON string for extra data
    ip_address TEXT,                    -- client IP
    user_agent TEXT,                    -- client user agent
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Index for efficient daily queries
CREATE INDEX IF NOT EXISTS idx_analytics_events_created_at ON analytics_events(created_at);
CREATE INDEX IF NOT EXISTS idx_analytics_events_type ON analytics_events(event_type);
