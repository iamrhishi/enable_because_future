"""
Wardrobe item model
"""

from typing import Optional, List
from services.database import db_manager
from utils.logger import logger


class WardrobeItem:
    """Wardrobe item data model"""
    
    def __init__(self, id: int = None, user_id: str = None, image_path: str = None,
                 category: str = None, garment_category_type: str = None,
                 brand: str = None, color: str = None, is_external: bool = False,
                 title: str = None, **kwargs):
        self.id = id
        self.user_id = user_id
        self.image_path = image_path
        self.category = category
        self.garment_category_type = garment_category_type
        self.brand = brand
        self.color = color
        self.is_external = is_external
        self.title = title
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
                   search: str = None) -> List['WardrobeItem']:
        """Get all wardrobe items for a user"""
        logger.info(f"WardrobeItem.get_by_user: ENTRY - user_id={user_id}, category={category}")
        try:
            query = "SELECT * FROM wardrobe WHERE user_id = ?"
            params = [user_id]
            
            if category:
                query += " AND category = ?"
                params.append(category)
            
            if search:
                query += " AND (title LIKE ? OR brand LIKE ? OR color LIKE ?)"
                search_param = f"%{search}%"
                params.extend([search_param, search_param, search_param])
            
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
                       garment_category_type = ?, brand = ?, color = ?, 
                       is_external = ?, title = ? WHERE id = ? AND user_id = ?""",
                    (self.image_path, self.category, self.garment_category_type,
                     self.brand, self.color, self.is_external, self.title,
                     self.id, self.user_id)
                )
                logger.info(f"WardrobeItem.save: EXIT - Item updated")
            else:
                # Insert
                item_id = db_manager.get_lastrowid(
                    """INSERT INTO wardrobe (user_id, image_path, category, 
                       garment_category_type, brand, color, is_external, title)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (self.user_id, self.image_path, self.category,
                     self.garment_category_type, self.brand, self.color,
                     self.is_external, self.title)
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
        return {
            'id': self.id,
            'user_id': self.user_id,
            'image_path': self.image_path,
            'category': self.category,
            'garment_category_type': self.garment_category_type,
            'brand': self.brand,
            'color': self.color,
            'is_external': self.is_external,
            'title': self.title,
            **self._data
        }

