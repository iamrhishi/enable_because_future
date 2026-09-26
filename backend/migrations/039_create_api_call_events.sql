-- Migration 039: Create api_call_events
-- Lightweight per-request log (every /api/* call, not just curated business
-- events) backing the "API calls per website / device / user count" section
-- of the daily analytics report. Wiped daily after the report like
-- analytics_events - see api_call_events_archive for the permanent copy.

CREATE TABLE IF NOT EXISTS api_call_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    path TEXT NOT NULL,
    method TEXT NOT NULL,
    user_id TEXT,
    platform TEXT NOT NULL,        -- 'mobile' or 'web'
    website_domain TEXT,           -- origin/referer host when platform='web' and known
    ip_address TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_api_call_events_created_at ON api_call_events(created_at);
CREATE INDEX IF NOT EXISTS idx_api_call_events_platform ON api_call_events(platform);

CREATE TABLE IF NOT EXISTS api_call_events_archive (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    path TEXT NOT NULL,
    method TEXT NOT NULL,
    user_id TEXT,
    platform TEXT NOT NULL,
    website_domain TEXT,
    ip_address TEXT,
    created_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_api_call_events_archive_created_at ON api_call_events_archive(created_at);
