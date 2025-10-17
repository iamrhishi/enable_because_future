# MySQL setup script for hello_db
CREATE DATABASE IF NOT EXISTS hello_db;
USE hello_db;
CREATE TABLE IF NOT EXISTS hello (
    id INT AUTO_INCREMENT PRIMARY KEY,
    message VARCHAR(255) NOT NULL
);
INSERT INTO hello (message) VALUES ('Hello World')
    ON DUPLICATE KEY UPDATE message=VALUES(message);
