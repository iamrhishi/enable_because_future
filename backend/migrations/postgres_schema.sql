-- Postgres schema for Cloud SQL, translated from the live SQLite schema on
-- bcf-internal (pulled directly from database.db, not replayed from the
-- historical SQLite migration files, since it reflects the actual current
-- production shape after all 30 migrations).
--
-- Translation rules applied:
--   INTEGER PRIMARY KEY AUTOINCREMENT -> SERIAL PRIMARY KEY
--   REAL                              -> DOUBLE PRECISION
--   BLOB / LONGBLOB                   -> BYTEA
--   DATETIME                          -> TIMESTAMP
--   sqlite_sequence                   -> dropped (Postgres manages SERIAL internally)
--   JSON-as-text columns kept as TEXT (app does its own json.dumps/loads,
--     never relies on Postgres JSON operators, so no behavior change needed)

CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    userid VARCHAR(255) NOT NULL UNIQUE,
    email VARCHAR(255) NOT NULL UNIQUE,
    first_name VARCHAR(255),
    last_name VARCHAR(255),
    password VARCHAR(255) NOT NULL,
    gender VARCHAR(50),
    birthday DATE,
    street TEXT,
    city TEXT,
    postal_code TEXT,
    country TEXT, -- migration 030, not yet applied on the VM's live DB
    avatar BYTEA,
    avatar_path VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE
);

CREATE TABLE body_measurements (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL UNIQUE REFERENCES users(userid) ON DELETE CASCADE,
    height DOUBLE PRECISION,
    weight DOUBLE PRECISION,
    chest DOUBLE PRECISION,
    waist DOUBLE PRECISION,
    hips DOUBLE PRECISION,
    inseam DOUBLE PRECISION,
    shoulder_width DOUBLE PRECISION,
    arm_length DOUBLE PRECISION,
    unit TEXT DEFAULT 'metric' CHECK(unit IN ('metric', 'imperial')),
    neck_circumference DOUBLE PRECISION,
    shoulder_circumference DOUBLE PRECISION,
    biceps_circumference DOUBLE PRECISION,
    breast_circumference DOUBLE PRECISION,
    under_breast_circumference DOUBLE PRECISION,
    waist_circumference DOUBLE PRECISION,
    upper_hip_circumference DOUBLE PRECISION,
    wide_hip_circumference DOUBLE PRECISION,
    upper_thigh_circumference DOUBLE PRECISION,
    calf_circumference DOUBLE PRECISION,
    waist_to_crotch_front_length DOUBLE PRECISION,
    waist_to_crotch_back_length DOUBLE PRECISION,
    inner_leg_length DOUBLE PRECISION,
    foot_length DOUBLE PRECISION,
    foot_width DOUBLE PRECISION,
    hip_circumference DOUBLE PRECISION,
    collarbone_to_belly_button_length DOUBLE PRECISION,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE category_sections (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    display_name VARCHAR(255) NOT NULL,
    description TEXT,
    sort_order INTEGER DEFAULT 0,
    icon_name VARCHAR(255),
    icon_url TEXT,
    user_id VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, name)
);

CREATE TABLE platform_categories (
    id SERIAL PRIMARY KEY,
    -- Not a formal FK: category_sections.name isn't unique on its own
    -- (only the (user_id, name) pair is) - SQLite never enforced this
    -- reference either, so this preserves the original behavior.
    category_section VARCHAR(255) NOT NULL,
    name VARCHAR(255) NOT NULL,
    display_name VARCHAR(255) NOT NULL,
    description TEXT,
    sort_order INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(category_section, name)
);

CREATE TABLE wardrobe_categories (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL REFERENCES users(userid) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    category_section TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, name)
);

CREATE TABLE wardrobe (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    garment_id VARCHAR(255) NOT NULL,
    garment_image BYTEA NOT NULL,
    garment_type TEXT NOT NULL CHECK(garment_type IN ('upper', 'lower')),
    garment_url TEXT,
    date_added TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    category TEXT CHECK(category IN ('upper', 'lower')),
    garment_category_type TEXT,
    brand TEXT,
    color TEXT,
    is_external BOOLEAN DEFAULT FALSE,
    title TEXT,
    price TEXT,
    category_id INTEGER,
    custom_category_name TEXT,
    fabric TEXT,
    care_instructions TEXT,
    size TEXT,
    description TEXT,
    image_path TEXT,
    category_section VARCHAR(100),
    url TEXT,
    UNIQUE(user_id, garment_id)
);

CREATE TABLE garment_metadata (
    id SERIAL PRIMARY KEY,
    url TEXT NOT NULL UNIQUE,
    title TEXT,
    price TEXT,
    brand TEXT,
    images TEXT,
    sizes TEXT,
    size_chart TEXT,
    colors TEXT,
    fabric TEXT,
    description TEXT,
    cached_image_1 BYTEA,
    cached_image_2 BYTEA,
    cached_image_1_url TEXT,
    cached_image_2_url TEXT,
    cached_images_at TIMESTAMP,
    last_accessed_at TIMESTAMP,
    scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE tryon_jobs (
    id SERIAL PRIMARY KEY,
    job_id VARCHAR(255) NOT NULL UNIQUE,
    user_id VARCHAR(255) NOT NULL REFERENCES users(userid) ON DELETE CASCADE,
    status TEXT NOT NULL DEFAULT 'queued' CHECK(status IN ('queued', 'processing', 'done', 'failed')),
    progress INTEGER DEFAULT 0 CHECK(progress >= 0 AND progress <= 100),
    result_url TEXT,
    error_message TEXT,
    garment_url TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE tryon_results (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL REFERENCES users(userid) ON DELETE CASCADE,
    result_image BYTEA NOT NULL,
    applied_garments TEXT NOT NULL,
    try_on_count INTEGER NOT NULL,
    original_avatar BYTEA NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE analytics_events (
    id SERIAL PRIMARY KEY,
    event_type TEXT NOT NULL,
    user_id TEXT,
    user_email TEXT,
    metadata TEXT,
    ip_address TEXT,
    user_agent TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Permanent, never-deleted mirror of analytics_events. The existing daily
-- email report wipes analytics_events after sending (see shared/analytics.py
-- delete_events_before) - this table is archived into just before that wipe,
-- so the Looker Studio dashboard has full history to query.
CREATE TABLE analytics_events_archive (
    id SERIAL PRIMARY KEY,
    event_type TEXT NOT NULL,
    user_id TEXT,
    user_email TEXT,
    metadata TEXT,
    ip_address TEXT,
    user_agent TEXT,
    created_at TIMESTAMP
);
CREATE INDEX idx_analytics_archive_created_at ON analytics_events_archive(created_at);
CREATE INDEX idx_analytics_archive_event_type ON analytics_events_archive(event_type);

CREATE TABLE hello (
    id SERIAL PRIMARY KEY,
    message VARCHAR(255) NOT NULL
);

CREATE TABLE schema_migrations (
    version INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Single source for the analytics dashboard (Looker Studio): full event
-- history (archive) plus whatever hasn't been archived/wiped yet (today's
-- live events), so the dashboard is always current without querying two tables.
CREATE VIEW analytics_events_all AS
SELECT event_type, user_id, user_email, metadata, ip_address, user_agent, created_at
FROM analytics_events_archive
UNION ALL
SELECT event_type, user_id, user_email, metadata, ip_address, user_agent, created_at
FROM analytics_events;
