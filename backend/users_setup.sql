-- Create users table for storing user profiles and avatars
-- This table stores user account information and avatar images

USE hello_db;

CREATE TABLE IF NOT EXISTS users (
    id INT PRIMARY KEY AUTO_INCREMENT,
    userid VARCHAR(50) NOT NULL UNIQUE,
    email VARCHAR(255) NOT NULL UNIQUE,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    password VARCHAR(255) NOT NULL,
    age INT NOT NULL,
    gender ENUM('male', 'female', 'other', 'prefer-not-to-say') NOT NULL,
    weight DECIMAL(5,2) NOT NULL,
    height DECIMAL(5,2) NOT NULL,
    physique ENUM('slim', 'muscular', 'thick') NOT NULL,
    avatar LONGBLOB DEFAULT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Create indexes for faster queries
CREATE INDEX idx_users_userid ON users(userid);
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_created_at ON users(created_at);

-- Show table structure
DESCRIBE users;

-- Example queries:
-- Get user by userid:
-- SELECT id, userid, email, first_name, last_name, age, gender, weight, height, physique, 
--        CASE WHEN avatar IS NULL THEN 'No avatar' ELSE 'Has avatar' END as avatar_status
-- FROM users WHERE userid = 'abc12345';

-- Update avatar:
-- UPDATE users SET avatar = ? WHERE userid = ?;

-- Get avatar:
-- SELECT avatar FROM users WHERE userid = 'abc12345';

-- Check if avatar exists:
-- SELECT userid, email, 
--        CASE WHEN avatar IS NULL THEN 'No avatar' ELSE CONCAT('Has avatar (', LENGTH(avatar), ' bytes)') END as avatar_info
-- FROM users;
