"""
Wardrobe Category model
Supports user-created categories for organizing garments
"""

from typing import Optional, List
import json
from shared.database import db_manager
from shared.logger import logger


def safe_dict_from_row(row) -> dict:
    """Safely convert database row to dict, filtering out non-JSON-serializable values"""
    if not row:
        return {}
    
    result = {}
    for k, v in dict(row).items():
        # Skip bytes objects
        if isinstance(v, bytes):
            continue
        # Test if value is JSON-serializable
        try:
            json.dumps(v)
            result[k] = v
        except (TypeError, ValueError):
            # Convert datetime/date objects to strings
            if hasattr(v, 'isoformat'):
                result[k] = v.isoformat()
            else:
                # Skip non-serializable values
                continue
    return result


class WardrobeCategory:
    """Wardrobe category data model"""
    
    def __init__(self, id: int = None, user_id: str = None, name: str = None,
                 description: str = None, category_section: str = None,
                 created_at: str = None, updated_at: str = None):
        self.id = id
        self.user_id = user_id
        self.name = name
        self.description = description
        self.category_section = category_section  # 'upper_body', 'lower_body', 'accessoires', 'wishlist'
        self.created_at = created_at
        self.updated_at = updated_at
    
    @classmethod
    def get_by_id(cls, category_id: int, user_id: str) -> Optional['WardrobeCategory']:
        """Get category by ID"""
        logger.info(f"WardrobeCategory.get_by_id: ENTRY - id={category_id}, user_id={user_id}")
        try:
            result = db_manager.execute_query(
                "SELECT * FROM wardrobe_categories WHERE id = ? AND user_id = ?",
                (category_id, user_id),
                fetch_one=True
            )
            if result:
                category = cls(**dict(result))
                logger.info(f"WardrobeCategory.get_by_id: EXIT - Category found")
                return category
            logger.info(f"WardrobeCategory.get_by_id: EXIT - Category not found")
            return None
        except Exception as e:
            logger.exception(f"WardrobeCategory.get_by_id: EXIT - Error: {str(e)}")
            raise
    
    @classmethod
    def get_by_name(cls, name: str, user_id: str) -> Optional['WardrobeCategory']:
        """Get category by name"""
        logger.info(f"WardrobeCategory.get_by_name: ENTRY - name={name}, user_id={user_id}")
        try:
            result = db_manager.execute_query(
                "SELECT * FROM wardrobe_categories WHERE name = ? AND user_id = ?",
                (name, user_id),
                fetch_one=True
            )
            if result:
                category = cls(**dict(result))
                logger.info(f"WardrobeCategory.get_by_name: EXIT - Category found")
                return category
            logger.info(f"WardrobeCategory.get_by_name: EXIT - Category not found")
            return None
        except Exception as e:
            logger.exception(f"WardrobeCategory.get_by_name: EXIT - Error: {str(e)}")
            raise
    
    @classmethod
    def get_all_by_user(cls, user_id: str, search: str = None, category_section: str = None) -> List['WardrobeCategory']:
        """Get all categories for a user, optionally filtered by section"""
        logger.info(f"WardrobeCategory.get_all_by_user: ENTRY - user_id={user_id}, search={search}, section={category_section}")
        try:
            query = "SELECT * FROM wardrobe_categories WHERE user_id = ?"
            params = [user_id]
            
            if category_section:
                query += " AND category_section = ?"
                params.append(category_section)
            
            if search:
                query += " AND (name LIKE ? OR description LIKE ?)"
                search_param = f"%{search}%"
                params.extend([search_param, search_param])
            
            query += " ORDER BY name ASC"
            
            results = db_manager.execute_query(query, tuple(params), fetch_all=True)
            categories = [cls(**dict(row)) for row in results] if results else []
            logger.info(f"WardrobeCategory.get_all_by_user: EXIT - Found {len(categories)} categories")
            return categories
        except Exception as e:
            logger.exception(f"WardrobeCategory.get_all_by_user: EXIT - Error: {str(e)}")
            raise
    
    def save(self):
        """Save category to database"""
        logger.info(f"WardrobeCategory.save: ENTRY - user_id={self.user_id}, name={self.name}")
        try:
            if self.id:
                # Update
                db_manager.execute_query(
                    """UPDATE wardrobe_categories SET name = ?, description = ?, 
                       category_section = ?, updated_at = CURRENT_TIMESTAMP 
                       WHERE id = ? AND user_id = ?""",
                    (self.name, self.description, self.category_section, self.id, self.user_id)
                )
                logger.info(f"WardrobeCategory.save: EXIT - Category updated")
            else:
                # Insert
                category_id = db_manager.get_lastrowid(
                    """INSERT INTO wardrobe_categories (user_id, name, description, category_section)
                       VALUES (?, ?, ?, ?)""",
                    (self.user_id, self.name, self.description, self.category_section)
                )
                self.id = category_id
                logger.info(f"WardrobeCategory.save: EXIT - Category created with id={category_id}")
        except Exception as e:
            logger.exception(f"WardrobeCategory.save: EXIT - Error: {str(e)}")
            raise
    
    def delete(self):
        """Delete category"""
        logger.info(f"WardrobeCategory.delete: ENTRY - id={self.id}, user_id={self.user_id}")
        try:
            if self.id:
                # First, remove category from garments (set to NULL or default)
                db_manager.execute_query(
                    """UPDATE wardrobe SET category_id = NULL, custom_category_name = NULL 
                       WHERE category_id = ? AND user_id = ?""",
                    (self.id, self.user_id)
                )
                # Then delete category
                db_manager.execute_query(
                    "DELETE FROM wardrobe_categories WHERE id = ? AND user_id = ?",
                    (self.id, self.user_id)
                )
                logger.info(f"WardrobeCategory.delete: EXIT - Category deleted")
        except Exception as e:
            logger.exception(f"WardrobeCategory.delete: EXIT - Error: {str(e)}")
            raise
    
    def to_dict(self) -> dict:
        """Convert category to dictionary"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'name': self.name,
            'description': self.description,
            'category_section': self.category_section,
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }
    
    @classmethod
    def get_platform_sections(cls) -> List[dict]:
        """Get all platform-defined category sections (user_id IS NULL)"""
        logger.info("WardrobeCategory.get_platform_sections: ENTRY")
        try:
            results = db_manager.execute_query(
                "SELECT * FROM category_sections WHERE user_id IS NULL ORDER BY sort_order ASC",
                fetch_all=True
            )
            sections = [safe_dict_from_row(row) for row in results] if results else []
            # If none exist in DB, use fallback defaults
            if not sections:
                sections = [
                    {
                        'name': 'upper_body',
                        'display_name': 'Upper body',
                        'description': 'Clothing items for upper body',
                        'sort_order': 1
                    },
                    {
                        'name': 'lower_body',
                        'display_name': 'Lower body',
                        'description': 'Clothing items for lower body',
                        'sort_order': 2
                    },
                    {
                        'name': 'accessoires',
                        'display_name': 'Accessoires',
                        'description': 'Accessories and other items',
                        'sort_order': 3
                    },
                    {
                        'name': 'wishlist',
                        'display_name': 'Wishlist',
                        'description': 'Items saved for later',
                        'sort_order': 4
                    }
                ]

            # Add/override icons for platform sections
            for section in sections:
                computed_icon = cls._get_icon_name_for_section(section.get('name'))
                section['icon_name'] = computed_icon
                section['icon_url'] = cls._get_default_icon_url(computed_icon)
            logger.info(f"WardrobeCategory.get_platform_sections: EXIT - Found {len(sections)} sections")
            return sections
        except Exception as e:
            logger.exception(f"WardrobeCategory.get_platform_sections: EXIT - Error: {str(e)}")
            # Return default sections if table doesn't exist yet
            return [
                {
                    'name': 'upper_body',
                    'display_name': 'Upper body',
                    'description': 'Clothing items for upper body',
                    'icon_name': cls._get_icon_name_for_section('upper_body'),
                    'icon_url': cls._get_default_icon_url(cls._get_icon_name_for_section('upper_body'))
                },
                {
                    'name': 'lower_body',
                    'display_name': 'Lower body',
                    'description': 'Clothing items for lower body',
                    'icon_name': cls._get_icon_name_for_section('lower_body'),
                    'icon_url': cls._get_default_icon_url(cls._get_icon_name_for_section('lower_body'))
                },
                {
                    'name': 'accessoires',
                    'display_name': 'Accessoires',
                    'description': 'Accessories and other items',
                    'icon_name': cls._get_icon_name_for_section('accessoires'),
                    'icon_url': cls._get_default_icon_url(cls._get_icon_name_for_section('accessoires'))
                },
                {
                    'name': 'wishlist',
                    'display_name': 'Wishlist',
                    'description': 'Items saved for later',
                    'icon_name': cls._get_icon_name_for_section('wishlist'),
                    'icon_url': cls._get_default_icon_url(cls._get_icon_name_for_section('wishlist'))
                }
            ]
    
    @classmethod
    def get_user_sections(cls, user_id: str) -> List[dict]:
        """Get all user-created category sections"""
        logger.info(f"WardrobeCategory.get_user_sections: ENTRY - user_id={user_id}")
        try:
            results = db_manager.execute_query(
                "SELECT * FROM category_sections WHERE user_id = ? ORDER BY sort_order ASC",
                (user_id,),
                fetch_all=True
            )
            sections = [safe_dict_from_row(row) for row in results] if results else []
            logger.info(f"WardrobeCategory.get_user_sections: EXIT - Found {len(sections)} sections")
            return sections
        except Exception as e:
            logger.exception(f"WardrobeCategory.get_user_sections: EXIT - Error: {str(e)}")
            return []
    
    @classmethod
    def get_all_sections(cls, user_id: str) -> List[dict]:
        """Get all sections (platform + user-created) for a user"""
        logger.info(f"WardrobeCategory.get_all_sections: ENTRY - user_id={user_id}")
        try:
            platform_sections = cls.get_platform_sections()
            user_sections = cls.get_user_sections(user_id)
            all_sections = platform_sections + user_sections
            # Sort by sort_order
            all_sections.sort(key=lambda x: x.get('sort_order', 999))
            # If still empty, fallback to platform defaults
            if not all_sections:
                all_sections = cls.get_platform_sections()
            logger.info(f"WardrobeCategory.get_all_sections: EXIT - Found {len(all_sections)} total sections")
            return all_sections
        except Exception as e:
            logger.exception(f"WardrobeCategory.get_all_sections: EXIT - Error: {str(e)}")
            return []
    
    @classmethod
    def get_section_by_name(cls, name: str, user_id: str = None) -> Optional[dict]:
        """Get a section by name (platform or user-specific)"""
        logger.info(f"WardrobeCategory.get_section_by_name: ENTRY - name={name}, user_id={user_id}")
        try:
            if user_id:
                # Check user section first, then platform
                result = db_manager.execute_query(
                    "SELECT * FROM category_sections WHERE name = ? AND user_id = ?",
                    (name, user_id),
                    fetch_one=True
                )
                if result:
                    return safe_dict_from_row(result)
            
            # Check platform section
            result = db_manager.execute_query(
                "SELECT * FROM category_sections WHERE name = ? AND user_id IS NULL",
                (name,),
                fetch_one=True
            )
            if result:
                section = safe_dict_from_row(result)
                computed_icon = cls._get_icon_name_for_section(section.get('name'))
                section['icon_name'] = computed_icon
                section['icon_url'] = cls._get_default_icon_url(computed_icon)
                return section
            
            logger.info(f"WardrobeCategory.get_section_by_name: EXIT - Section not found")
            return None
        except Exception as e:
            logger.exception(f"WardrobeCategory.get_section_by_name: EXIT - Error: {str(e)}")
            return None
    
    @classmethod
    def create_user_section(cls, user_id: str, name: str, display_name: str, 
                           description: str = None, icon_name: str = None, 
                           icon_url: str = None, sort_order: int = 999) -> dict:
        """Create a user-specific category section"""
        logger.info(f"WardrobeCategory.create_user_section: ENTRY - user_id={user_id}, name={name}")
        try:
            # Check if section already exists for this user
            existing = cls.get_section_by_name(name, user_id)
            if existing:
                raise ValueError(f"Section '{name}' already exists for this user")
            
            # Check if platform section with same name exists
            platform_section = cls.get_section_by_name(name)
            if platform_section:
                raise ValueError(f"Section '{name}' conflicts with platform section")
            
            section_id = db_manager.get_lastrowid(
                """INSERT INTO category_sections (user_id, name, display_name, description, icon_name, icon_url, sort_order)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (user_id, name, display_name, description, icon_name, icon_url, sort_order)
            )
            
            result = {
                'id': section_id,
                'user_id': user_id,
                'name': name,
                'display_name': display_name,
                'description': description,
                'icon_name': icon_name,
                'icon_url': icon_url,
                'sort_order': sort_order
            }
            
            logger.info(f"WardrobeCategory.create_user_section: EXIT - Section created with id={section_id}")
            return result
        except Exception as e:
            logger.exception(f"WardrobeCategory.create_user_section: EXIT - Error: {str(e)}")
            raise
    
    @staticmethod
    def _get_icon_name_for_section(section_name: str) -> str:
        """Get default icon name for a section (unisex)"""
        icon_map = {
            'upper_body': 'Tshirt.jpeg',
            'lower_body': 'Jeans.jpeg',
            'accessoires': 'Bags.jpeg',
            'wishlist': 'Other.jpeg'
        }
        return icon_map.get(section_name, 'Other.jpeg')

    @staticmethod
    def _get_icon_name_for_category(category_name: str) -> str:
        """Get default icon name for a platform category (unisex)"""
        name = (category_name or '').strip().lower()
        category_map = {
            # Upper body
            'blazers': 'Blazer.jpeg',
            'jackets': 'Jackets.jpeg',
            'pullover_cardigans': 'Pullover.jpeg',
            'pullover': 'Pullover.jpeg',
            'shirts': 'Shirts.jpeg',
            'tops': 'Tops.jpeg',
            't_shirts': 'Tshirt.jpeg',
            'others': 'Other.jpeg',
            # Lower body
            'jeans': 'Jeans.jpeg',
            'trousers': 'Trousers.jpeg',
            'long_trousers': 'Trousers.jpeg',
            'shorts': 'Shorts.jpeg',
            'short_trousers': 'Shorts.jpeg',
            'skirts': 'Skirts.jpeg',
            'leggings': 'Legging & Joggers.jpeg',
            'legging & joggers': 'Legging & Joggers.jpeg',
            # Accessories / footwear
            'sneakers': 'Sneakers.jpeg',
            'sandals': 'Sandals.jpeg',
            'bags': 'Bags.jpeg',
            'caps': 'Caps & Hats.jpeg',
            # Misc
            'accessoires': 'Other.jpeg',
            'wishlist': 'Other.jpeg',
        }
        return category_map.get(name, 'Other.jpeg')

    @staticmethod
    def _get_default_icon_url(icon_name: str) -> str:
        """Build default icon URL for platform sections"""
        from shared.url_utils import to_absolute_url
        if not icon_name:
            return None
        return to_absolute_url(f'/icons/{icon_name}')
    
    @classmethod
    def get_platform_categories(cls, category_section: str = None) -> List[dict]:
        """Get platform-defined categories, optionally filtered by section"""
        logger.info(f"WardrobeCategory.get_platform_categories: ENTRY - section={category_section}")
        try:
            # Allowed platform categories (only those we have icons for)
            allowed = {
                'blazers',
                'jackets',
                'pullover_cardigans',
                'pullover',
                'shirts',
                'tops',
                't_shirts',
                'others',
                'jeans',
                'trousers',
                'long_trousers',
                'shorts',
                'short_trousers',
                'skirts',
                'leggings',
                'legging & joggers',
                'sneakers',
                'sandals',
                'bags',
                'caps',
                'accessoires',
                'wishlist',
            }
            if category_section:
                results = db_manager.execute_query(
                    "SELECT * FROM platform_categories WHERE category_section = ? ORDER BY sort_order ASC",
                    (category_section,),
                    fetch_all=True
                )
            else:
                results = db_manager.execute_query(
                    "SELECT * FROM platform_categories ORDER BY category_section ASC, sort_order ASC",
                    fetch_all=True
                )
            categories = [safe_dict_from_row(row) for row in results] if results else []
            # If no platform categories exist in DB, synthesize defaults from allowed/icon map
            if not categories:
                defaults = [
                    # Upper body
                    ('upper_body', 't_shirts', 'T-shirts', 1),
                    ('upper_body', 'shirts', 'Shirts', 2),
                    ('upper_body', 'tops', 'Tops', 3),
                    ('upper_body', 'pullover_cardigans', 'Pullover', 4),
                    ('upper_body', 'jackets', 'Jackets', 5),
                    ('upper_body', 'blazers', 'Blazers', 6),
                    ('upper_body', 'others', 'Others', 99),
                    # Lower body
                    ('lower_body', 'long_trousers', 'Long Trousers', 1),
                    ('lower_body', 'short_trousers', 'Short Trousers', 2),
                    ('lower_body', 'jeans', 'Jeans', 3),
                    ('lower_body', 'skirts', 'Skirts', 4),
                    ('lower_body', 'leggings', 'Leggings', 5),
                    ('lower_body', 'others', 'Others', 99),
                    # Accessories / footwear
                    ('accessoires', 'sneakers', 'Sneakers', 1),
                    ('accessoires', 'sandals', 'Sandals', 2),
                    ('accessoires', 'bags', 'Bags', 3),
                    ('accessoires', 'caps', 'Caps', 4),
                    ('accessoires', 'others', 'Others', 99),
                    # Misc
                    ('wishlist', 'wishlist', 'Wishlist', 99),
                ]
                categories = [
                    {
                        'category_section': sec,
                        'name': name,
                        'display_name': disp,
                        'description': None,
                        'sort_order': sort,
                        'user_id': None,
                        'id': None,
                        'created_at': None,
                        'updated_at': None,
                    }
                    for sec, name, disp, sort in defaults
                    if (category_section is None or sec == category_section)
                ]

            # Add/override icon for platform categories
            filtered = []
            for cat in categories:
                cat_name = (cat.get('name') or '').lower()
                if cat_name not in allowed:
                    continue
                computed_icon = cls._get_icon_name_for_category(cat.get('name'))
                cat['icon_name'] = computed_icon
                cat['icon_url'] = cls._get_default_icon_url(computed_icon)
                filtered.append(cat)
            logger.info(f"WardrobeCategory.get_platform_categories: EXIT - Found {len(filtered)} categories")
            return filtered
        except Exception as e:
            logger.exception(f"WardrobeCategory.get_platform_categories: EXIT - Error: {str(e)}")
            return []

