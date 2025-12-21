-- Migration 016: Rename "Pullover & Cardigans" to "Pullover"
-- Update display_name for pullover_cardigans category

UPDATE platform_categories 
SET display_name = 'Pullover' 
WHERE name = 'pullover_cardigans' AND display_name = 'Pullover & Cardigans';

-- Also update any user-created categories with the same display name (if any)
UPDATE platform_categories 
SET display_name = 'Pullover' 
WHERE name = 'pullover_cardigans' AND display_name = 'Pullover & Cardigans';

