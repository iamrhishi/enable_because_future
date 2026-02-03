"""
Wardrobe item model
"""

from typing import Optional, List
from shared.database import db_manager
from shared.logger import logger


class WardrobeItem:
    """Wardrobe item data model"""
    
    def __init__(self, id: int = None, user_id: str = None, image_path: str = None,
                 category: str = None, garment_category_type: str = None,
                 brand: str = None, color: str = None, is_external: bool = False,
                 title: str = None, category_id: int = None, custom_category_name: str = None,
                 fabric: str = None, care_instructions: str = None, size: str = None,
                 description: str = None, category_section: str = None, url: str = None, **kwargs):
        self.id = id
        self.user_id = user_id
        self.image_path = image_path
        self.category = category  # 'upper', 'lower', or None if using custom category
        self.category_id = category_id  # ID of custom category
        self.custom_category_name = custom_category_name  # Name of custom category
        self.category_section = category_section  # 'upper_body', 'lower_body', 'accessoires', 'wishlist'
        self.garment_category_type = garment_category_type
        self.brand = brand
        self.color = color
        self.is_external = is_external
        self.title = title
        self.fabric = fabric  # JSON string: [{"name": "cotton", "percentage": 100}]
        self.care_instructions = care_instructions  # TEXT or JSON array
        self.size = size  # TEXT: "M", "L", "42", etc.
        self.description = description  # TEXT: Short description
        self.url = url  # TEXT: Product page URL
        self._data = kwargs
    
    @classmethod
    def get_by_id(cls, item_id: int, user_id: str) -> Optional['WardrobeItem']:
        """Get wardrobe item by ID"""
        logger.info(f"WardrobeItem.get_by_id: ENTRY - id={item_id}, user_id={user_id}")
        try:
            result = db_manager.execute_query(
                "SELECT * FROM wardrobe WHERE id = ? AND user_id = ?",
                (item_id, user_id),
                fetch_one=True
            )
            if result:
                item = cls(**dict(result))
                logger.info(f"WardrobeItem.get_by_id: EXIT - Item found")
                return item
            logger.info(f"WardrobeItem.get_by_id: EXIT - Item not found")
            return None
        except Exception as e:
            logger.exception(f"WardrobeItem.get_by_id: EXIT - Error: {str(e)}")
            raise
    
    @classmethod
    def get_by_user(cls, user_id: str, category: str = None, 
                   search: str = None, category_id: int = None,
                   platform_category_name: str = None, item_id: int = None,
                   category_section: str = None) -> List['WardrobeItem']:
        """
        Get all wardrobe items for a user
        
        Args:
            user_id: User ID
            category: Legacy category filter ('upper', 'lower')
            search: Search term for title/brand/color/etc
            category_id: Category ID (works for both user-created and platform categories)
                        Filters by category_id column in wardrobe table directly
            platform_category_name: Platform category name (for platform categories, also filter by garment_category_type)
            item_id: Item ID to filter by (filters by id column in wardrobe table)
            category_section: Section filter ('upper_body', 'lower_body', 'accessoires', 'wishlist')
        """
        logger.info(f"WardrobeItem.get_by_user: ENTRY - user_id={user_id}, category={category}, category_id={category_id}, platform_category_name={platform_category_name}, item_id={item_id}, category_section={category_section}, search={search}")
        try:
            query = "SELECT * FROM wardrobe WHERE user_id = ?"
            params = [user_id]
            
            if item_id is not None:
                # Filter by item ID directly
                query += " AND id = ?"
                params.append(item_id)
            
            if category:
                query += " AND category = ?"
                params.append(category)
            
            if category_section:
                # Filter by category_section
                query += " AND category_section = ?"
                params.append(category_section)
            
            if category_id is not None:
                # Filter by category_id directly - works for both user-created and platform categories
                # Items can have category_id set to either:
                # - User category ID (from wardrobe_categories table)
                # - Platform category ID (from platform_categories table)
                if platform_category_name:
                    # For platform categories, also check garment_category_type as fallback
                    # Some items might have garment_category_type set but not category_id
                    query += " AND (category_id = ? OR garment_category_type = ?)"
                    params.extend([category_id, platform_category_name])
                else:
                    # For user categories, filter by category_id only
                    query += " AND category_id = ?"
                    params.append(category_id)
            
            if search:
                query += " AND (title LIKE ? OR brand LIKE ? OR color LIKE ? OR garment_category_type LIKE ? OR description LIKE ? OR size LIKE ?)"
                search_param = f"%{search}%"
                params.extend([search_param, search_param, search_param, search_param, search_param, search_param])
            
            query += " ORDER BY id DESC"
            
            results = db_manager.execute_query(query, tuple(params), fetch_all=True)
            items = [cls(**dict(row)) for row in results] if results else []
            logger.info(f"WardrobeItem.get_by_user: EXIT - Found {len(items)} items")
            return items
        except Exception as e:
            logger.exception(f"WardrobeItem.get_by_user: EXIT - Error: {str(e)}")
            raise
    
    def save(self):
        """Save wardrobe item to database"""
        logger.info(f"WardrobeItem.save: ENTRY - user_id={self.user_id}")
        try:
            if self.id:
                # Update
                db_manager.execute_query(
                    """UPDATE wardrobe SET image_path = ?, category = ?,
                       category_id = ?, custom_category_name = ?, category_section = ?,
                       garment_category_type = ?, brand = ?, color = ?,
                       is_external = ?, title = ?, fabric = ?,
                       care_instructions = ?, size = ?, description = ?, url = ?
                       WHERE id = ? AND user_id = ?""",
                    (self.image_path, self.category, self.category_id, self.custom_category_name,
                     self.category_section, self.garment_category_type, self.brand, self.color,
                     self.is_external, self.title, self.fabric, self.care_instructions,
                     self.size, self.description, self.url, self.id, self.user_id)
                )
                logger.info(f"WardrobeItem.save: EXIT - Item updated")
            else:
                # Insert
                # Generate a default garment_id (legacy field, required by schema)
                import uuid
                garment_id = f"item_{uuid.uuid4().hex[:8]}"
                
                # Map category to garment_type (legacy field, required by schema)
                # garment_type must be 'upper' or 'lower'
                garment_type = self.category if self.category in ['upper', 'lower'] else 'upper'
                
                # Provide empty blob for garment_image (legacy field, required by schema)
                # We use image_path instead, but schema still requires garment_image
                garment_image = b''  # Empty bytes for legacy BLOB field
                
                item_id = db_manager.get_lastrowid(
                    """INSERT INTO wardrobe (user_id, garment_id, garment_image, garment_type, image_path, category,
                       category_id, custom_category_name, category_section,
                       garment_category_type, brand, color, is_external, title,
                       fabric, care_instructions, size, description, url)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (self.user_id, garment_id, garment_image, garment_type, self.image_path, self.category,
                     self.category_id, self.custom_category_name, self.category_section,
                     self.garment_category_type, self.brand, self.color,
                     self.is_external, self.title, self.fabric,
                     self.care_instructions, self.size, self.description, self.url)
                )
                self.id = item_id
                logger.info(f"WardrobeItem.save: EXIT - Item created with id={item_id}")
        except Exception as e:
            logger.exception(f"WardrobeItem.save: EXIT - Error: {str(e)}")
            raise
    
    def delete(self):
        """Delete wardrobe item"""
        logger.info(f"WardrobeItem.delete: ENTRY - id={self.id}, user_id={self.user_id}")
        try:
            if self.id:
                db_manager.execute_query(
                    "DELETE FROM wardrobe WHERE id = ? AND user_id = ?",
                    (self.id, self.user_id)
                )
                logger.info(f"WardrobeItem.delete: EXIT - Item deleted")
        except Exception as e:
            logger.exception(f"WardrobeItem.delete: EXIT - Error: {str(e)}")
            raise
    
    def to_dict(self) -> dict:
        """Convert wardrobe item to dictionary"""
        import json
        # Filter out bytes objects and legacy fields that shouldn't be serialized
        # Also filter out any non-JSON-serializable types
        filtered_data = {}
        if self._data:
            for k, v in self._data.items():
                # Skip bytes objects and legacy fields
                if isinstance(v, bytes):
                    continue
                if k in ['garment_image', 'garment_id', 'garment_type', 'garment_url']:
                    continue
                # Only include JSON-serializable values
                try:
                    json.dumps(v)  # Test if serializable
                    filtered_data[k] = v
                except (TypeError, ValueError):
                    continue  # Skip non-serializable values
        
        result = {
            'id': self.id,
            'user_id': self.user_id,
            'image_path': self.image_path,
            'category': self.category,
            'category_id': self.category_id,
            'custom_category_name': self.custom_category_name,
            'category_section': self.category_section,
            'garment_category_type': self.garment_category_type,
            'brand': self.brand,
            'color': self.color,
            'is_external': self.is_external,
            'title': self.title,
            'fabric': json.loads(self.fabric) if self.fabric else None,
            'care_instructions': json.loads(self.care_instructions) if self.care_instructions and self.care_instructions.startswith('[') else self.care_instructions,
            'size': self.size,
            'description': self.description,
            'url': self.url,
        }
        
        # Add date_added and updated_at if they exist in _data
        if self._data:
            if 'date_added' in self._data and self._data['date_added']:
                result['date_added'] = str(self._data['date_added'])
            if 'created_at' in self._data and self._data['created_at']:
                result['created_at'] = str(self._data['created_at'])
            if 'updated_at' in self._data and self._data['updated_at']:
                result['updated_at'] = str(self._data['updated_at'])
        
        # Merge filtered additional data
        result.update(filtered_data)
        return result

