"""
User model
"""

from typing import Optional
from services.database import db_manager
from utils.logger import logger


class User:
    """User data model"""
    
    def __init__(self, userid: str, email: str = None, name: str = None, 
                 avatar: bytes = None, **kwargs):
        self.userid = userid
        self.email = email
        self.name = name
        self.avatar = avatar
        self._data = kwargs
    
    @classmethod
    def get_by_id(cls, userid: str) -> Optional['User']:
        """Get user by ID"""
        logger.info(f"User.get_by_id: ENTRY - userid={userid}")
        try:
            result = db_manager.execute_query(
                "SELECT * FROM users WHERE userid = ?",
                (userid,),
                fetch_one=True
            )
            if result:
                user = cls(**dict(result))
                logger.info(f"User.get_by_id: EXIT - User found")
                return user
            logger.info(f"User.get_by_id: EXIT - User not found")
            return None
        except Exception as e:
            logger.exception(f"User.get_by_id: EXIT - Error: {str(e)}")
            raise
    
    @classmethod
    def get_by_email(cls, email: str) -> Optional['User']:
        """Get user by email"""
        logger.info(f"User.get_by_email: ENTRY - email={email}")
        try:
            result = db_manager.execute_query(
                "SELECT * FROM users WHERE email = ?",
                (email,),
                fetch_one=True
            )
            if result:
                user = cls(**dict(result))
                logger.info(f"User.get_by_email: EXIT - User found")
                return user
            logger.info(f"User.get_by_email: EXIT - User not found")
            return None
        except Exception as e:
            logger.exception(f"User.get_by_email: EXIT - Error: {str(e)}")
            raise
    
    def save(self):
        """Save user to database"""
        logger.info(f"User.save: ENTRY - userid={self.userid}")
        try:
            # Check if user exists
            existing = self.get_by_id(self.userid)
            if existing:
                # Update
                db_manager.execute_query(
                    """UPDATE users SET email = ?, name = ?, avatar = ?
                       WHERE userid = ?""",
                    (self.email, self.name, self.avatar, self.userid)
                )
                logger.info(f"User.save: EXIT - User updated")
            else:
                # Insert
                db_manager.get_lastrowid(
                    """INSERT INTO users (userid, email, name, avatar)
                       VALUES (?, ?, ?, ?)""",
                    (self.userid, self.email, self.name, self.avatar)
                )
                logger.info(f"User.save: EXIT - User created")
        except Exception as e:
            logger.exception(f"User.save: EXIT - Error: {str(e)}")
            raise
    
    def to_dict(self, include_avatar: bool = False) -> dict:
        """Convert user to dictionary"""
        data = {
            'userid': self.userid,
            'email': self.email,
            'name': self.name,
            **self._data
        }
        if include_avatar and self.avatar:
            import base64
            data['avatar'] = base64.b64encode(self.avatar).decode('utf-8')
        return data

