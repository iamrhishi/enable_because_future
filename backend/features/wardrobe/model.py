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
                 description: str = None, **kwargs):
        self.id = id
        self.user_id = user_id
        self.image_path = image_path
        self.category = category  # 'upper', 'lower', or None if using custom category
        self.category_id = category_id  # ID of custom category
        self.custom_category_name = custom_category_name  # Name of custom category
        self.garment_category_type = garment_category_type
        self.brand = brand
        self.color = color
        self.is_external = is_external
        self.title = title
        self.fabric = fabric  # JSON string: [{"name": "cotton", "percentage": 100}]
        self.care_instructions = care_instructions  # TEXT or JSON array
        self.size = size  # TEXT: "M", "L", "42", etc.
        self.description = description  # TEXT: Short description
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
                   search: str = None, custom_category_name: str = None) -> List['WardrobeItem']:
        """Get all wardrobe items for a user"""
        logger.info(f"WardrobeItem.get_by_user: ENTRY - user_id={user_id}, category={category}, custom_category={custom_category_name}")
        try:
            query = "SELECT * FROM wardrobe WHERE user_id = ?"
            params = [user_id]
            
            if category:
                query += " AND category = ?"
                params.append(category)
            
            if custom_category_name:
                query += " AND custom_category_name = ?"
                params.append(custom_category_name)
            
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
                       category_id = ?, custom_category_name = ?,
                       garment_category_type = ?, brand = ?, color = ?, 
                       is_external = ?, title = ?, fabric = ?, 
                       care_instructions = ?, size = ?, description = ?
                       WHERE id = ? AND user_id = ?""",
                    (self.image_path, self.category, self.category_id, self.custom_category_name,
                     self.garment_category_type, self.brand, self.color, self.is_external, self.title,
                     self.fabric, self.care_instructions, self.size, self.description,
                     self.id, self.user_id)
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
                       category_id, custom_category_name,
                       garment_category_type, brand, color, is_external, title,
                       fabric, care_instructions, size, description)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (self.user_id, garment_id, garment_image, garment_type, self.image_path, self.category,
                     self.category_id, self.custom_category_name,
                     self.garment_category_type, self.brand, self.color,
                     self.is_external, self.title, self.fabric, 
                     self.care_instructions, self.size, self.description)
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
        result = {
            'id': self.id,
            'user_id': self.user_id,
            'image_path': self.image_path,
            'category': self.category,
            'category_id': self.category_id,
            'custom_category_name': self.custom_category_name,
            'garment_category_type': self.garment_category_type,
            'brand': self.brand,
            'color': self.color,
            'is_external': self.is_external,
            'title': self.title,
            'fabric': json.loads(self.fabric) if self.fabric else None,
            'care_instructions': json.loads(self.care_instructions) if self.care_instructions and self.care_instructions.startswith('[') else self.care_instructions,
            'size': self.size,
            'description': self.description,
            **self._data
        }
        return result

