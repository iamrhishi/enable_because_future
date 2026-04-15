-- Migration 025: Update body measurements with new field and validation ranges
-- Adds collarbone_to_belly_button_length field
-- All measurements now have specific validation ranges

ALTER TABLE body_measurements ADD COLUMN collarbone_to_belly_button_length REAL;
