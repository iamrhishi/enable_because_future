-- Migration 003: Add tryon_jobs table
-- Tracks async try-on job status and results

CREATE TABLE IF NOT EXISTS tryon_jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id VARCHAR(255) NOT NULL UNIQUE,
    user_id VARCHAR(255) NOT NULL,
    status TEXT NOT NULL DEFAULT 'queued' CHECK(status IN ('queued', 'processing', 'done', 'failed')),
    progress INTEGER DEFAULT 0 CHECK(progress >= 0 AND progress <= 100),
    result_url TEXT,
    error_message TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(userid) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_tryon_jobs_job_id ON tryon_jobs(job_id);
CREATE INDEX IF NOT EXISTS idx_tryon_jobs_user_id ON tryon_jobs(user_id);
CREATE INDEX IF NOT EXISTS idx_tryon_jobs_status ON tryon_jobs(status);

