-- Migration: 029_create_garment_discovery_tables.sql
-- Description: Create tables for AI-powered conversational garment discovery feature

DROP TABLE IF EXISTS discovery_messages;
DROP TABLE IF EXISTS discovery_sessions;

CREATE TABLE IF NOT EXISTS discovery_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT UNIQUE NOT NULL,
    user_id TEXT,
    status TEXT NOT NULL DEFAULT 'active',
    title TEXT,
    preferences_json TEXT NOT NULL DEFAULT '{}',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS discovery_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    sender TEXT NOT NULL, -- 'user', 'assistant', 'system'
    content TEXT NOT NULL,
    garments_json TEXT,
    metadata_json TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES discovery_sessions(session_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_discovery_sessions_user_id ON discovery_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_discovery_sessions_status ON discovery_sessions(status);
CREATE INDEX IF NOT EXISTS idx_discovery_messages_session_id ON discovery_messages(session_id);
