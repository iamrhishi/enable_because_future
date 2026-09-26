-- Migration 037: Create tryon_monthly_usage
-- Backs the per-user monthly try-on quota (30/user/month). One row per
-- (user_id, year_month); count is incremented atomically as try-ons are
-- started via /tryon, /tryon/multi, /tryon/layered and /tryon-gemini.

CREATE TABLE IF NOT EXISTS tryon_monthly_usage (
    user_id TEXT NOT NULL,
    year_month TEXT NOT NULL,          -- 'YYYY-MM'
    count INTEGER NOT NULL DEFAULT 0,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, year_month)
);
