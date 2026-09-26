-- Migration 036: Create analytics_events_archive
-- Permanent, never-deleted mirror of analytics_events. The daily email report
-- wipes analytics_events after sending (see shared/analytics.py
-- delete_events_before), which already archives into this table just before
-- the wipe - it just never had a table to land in. This adds it so events
-- are retained per day instead of being lost.

CREATE TABLE IF NOT EXISTS analytics_events_archive (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL,
    user_id TEXT,
    user_email TEXT,
    metadata TEXT,
    ip_address TEXT,
    user_agent TEXT,
    created_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_analytics_archive_created_at ON analytics_events_archive(created_at);
CREATE INDEX IF NOT EXISTS idx_analytics_archive_event_type ON analytics_events_archive(event_type);
