-- Migration 024: Clean up users table
-- Remove age, weight, height, physique from users table
-- These measurements belong in body_measurements table

-- Note: SQLite doesn't support direct column deletion with ALTER TABLE
-- We need to recreate the table with the desired schema

-- Create new users table with only required fields
CREATE TABLE IF NOT EXISTS users_new (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
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
    avatar BLOB,
    avatar_path VARCHAR(255),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE
);

-- Copy data from old users table to new users table (selecting only the columns we want)
INSERT INTO users_new 
  (id, userid, email, first_name, last_name, password, gender, birthday, street, city, postal_code, avatar, avatar_path, created_at, updated_at, is_active)
SELECT 
  id, userid, email, first_name, last_name, password, gender, birthday, street, city, postal_code, avatar, avatar_path, created_at, updated_at, is_active
FROM users;

-- Drop old users table
DROP TABLE users;

-- Rename new users table to users
ALTER TABLE users_new RENAME TO users;

-- Recreate indexes
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_userid ON users(userid);
CREATE INDEX IF NOT EXISTS idx_users_avatar_path ON users(avatar_path);
