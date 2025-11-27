-- Migration 006: Extend users table and body_measurements table
-- Adds personal information fields (birthday, street, city) to users
-- Adds comprehensive body measurement fields to body_measurements

-- Add personal information fields to users table
ALTER TABLE users ADD COLUMN birthday DATE;
ALTER TABLE users ADD COLUMN street TEXT;
ALTER TABLE users ADD COLUMN city TEXT;

-- Extend body_measurements table with comprehensive measurement fields
-- Note: SQLite doesn't support ALTER TABLE ADD COLUMN for multiple columns in one statement
-- We'll add them one by one

ALTER TABLE body_measurements ADD COLUMN neck_circumference REAL;
ALTER TABLE body_measurements ADD COLUMN shoulder_circumference REAL;
ALTER TABLE body_measurements ADD COLUMN biceps_circumference REAL;
ALTER TABLE body_measurements ADD COLUMN breast_circumference REAL;
ALTER TABLE body_measurements ADD COLUMN under_breast_circumference REAL;
ALTER TABLE body_measurements ADD COLUMN waist_circumference REAL;
ALTER TABLE body_measurements ADD COLUMN upper_hip_circumference REAL;
ALTER TABLE body_measurements ADD COLUMN wide_hip_circumference REAL;
ALTER TABLE body_measurements ADD COLUMN upper_thigh_circumference REAL;
ALTER TABLE body_measurements ADD COLUMN calf_circumference REAL;
ALTER TABLE body_measurements ADD COLUMN waist_to_crotch_front_length REAL;
ALTER TABLE body_measurements ADD COLUMN waist_to_crotch_back_length REAL;
ALTER TABLE body_measurements ADD COLUMN inner_leg_length REAL;
ALTER TABLE body_measurements ADD COLUMN foot_length REAL;
ALTER TABLE body_measurements ADD COLUMN foot_width REAL;

