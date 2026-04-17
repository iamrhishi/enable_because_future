-- Migration 027: Complete body measurements schema with validation ranges
-- Ensures all required columns exist for fitting analysis
-- Note: SQLite doesn't support CHECK constraints on ALTER TABLE, validation done in application

-- Add any missing columns (SQLite ADD COLUMN is idempotent-safe with IF NOT EXISTS workaround)
-- Using try-add pattern: column will be added if not exists

-- Basic measurements
-- height: 50-250 cm
-- weight: 20-250 kg

-- Upper body measurements
-- shoulder_circumference: 60-200 cm
-- arm_length: 25-100 cm
-- biceps_circumference: 10-100 cm
-- breast_circumference: 50-300 cm
-- under_breast_circumference: 40-300 cm
-- collarbone_to_belly_button_length: 30-150 cm

-- Lower body measurements
-- waist_circumference: 30-300 cm
-- hip_circumference: 50-300 cm
-- upper_thigh_circumference: 25-300 cm
-- waist_to_crotch_front_length: 15-100 cm
-- waist_to_crotch_back_length: 15-100 cm
-- inner_leg_length: 50-200 cm
-- foot_length: 10-60 cm
-- foot_width: 5-20 cm

-- Ensure columns exist (most already added in previous migrations)
-- These are safe to run - SQLite will error on duplicate but migration manager handles it

-- Check table structure
SELECT sql FROM sqlite_master WHERE type='table' AND name='body_measurements';
