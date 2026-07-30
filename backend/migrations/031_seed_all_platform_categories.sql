-- Migration 031: Seed all platform categories for all sections
PRAGMA foreign_keys = OFF;

INSERT OR IGNORE INTO platform_categories (category_section, name, display_name, sort_order) VALUES
('upper_body', 't_shirts', 'T-shirts', 1),
('upper_body', 'shirts', 'Shirts', 2),
('upper_body', 'tops', 'Tops', 3),
('upper_body', 'pullover', 'Pullover', 4),
('upper_body', 'jackets', 'Jackets', 5),
('upper_body', 'blazers', 'Blazers', 6),
('upper_body', 'others', 'Others', 99),

('lower_body', 'long_trousers', 'Long Trousers', 1),
('lower_body', 'short_trousers', 'Short Trousers', 2),
('lower_body', 'jeans', 'Jeans', 3),
('lower_body', 'skirts', 'Skirts', 4),
('lower_body', 'leggings', 'Leggings', 5),
('lower_body', 'others', 'Others', 99),

('accessoires', 'sneakers', 'Sneakers', 1),
('accessoires', 'sandals', 'Sandals', 2),
('accessoires', 'caps', 'Caps', 3),
('accessoires', 'bags', 'Bags', 4),
('accessoires', 'others', 'Others', 99);

PRAGMA foreign_keys = ON;
