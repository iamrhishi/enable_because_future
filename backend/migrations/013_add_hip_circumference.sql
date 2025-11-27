-- Migration 013: Add hip_circumference column to body_measurements
-- The code expects hip_circumference but migration 006 only added upper_hip_circumference and wide_hip_circumference

ALTER TABLE body_measurements ADD COLUMN hip_circumference REAL;

