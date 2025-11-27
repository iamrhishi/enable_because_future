"""
User model
"""

from typing import Optional, Dict, Any
from shared.database import db_manager
from shared.logger import logger
from werkzeug.security import generate_password_hash, check_password_hash


class User:
    """User data model - complete user profile information"""
    
    def __init__(self, userid: str = None, email: str = None, 
                 first_name: str = None, last_name: str = None,
                 password: str = None, gender: str = None,
                 birthday: str = None, street: str = None, city: str = None,
                 avatar: bytes = None, is_active: bool = True,
                 id: int = None, created_at: str = None, updated_at: str = None,
                 **kwargs):
        self.id = id
        self.userid = userid
        self.email = email
        self.first_name = first_name
        self.last_name = last_name
        self.password = password  # Hashed password
        self.gender = gender
        self.birthday = birthday  # YYYY-MM-DD format
        self.street = street
        self.city = city
        self.avatar = avatar
        self.is_active = is_active
        self.created_at = created_at
        self.updated_at = updated_at
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
        """Save user to database (creates or updates)"""
        logger.info(f"User.save: ENTRY - userid={self.userid}")
        try:
            if not self.userid:
                raise ValueError("userid is required")
            
            # Check if user exists
            existing = self.get_by_id(self.userid)
            
            # Hash password if it's provided and not already hashed
            hashed_password = self.password
            if self.password and not self.password.startswith('$2b$') and not self.password.startswith('$2a$') and not self.password.startswith('pbkdf2:'):
                # Password is plain text, hash it
                # Use pbkdf2:sha256 method for Python 3.9 compatibility (scrypt not available)
                hashed_password = generate_password_hash(self.password, method='pbkdf2:sha256')
            
            if existing:
                # Update existing user
                db_manager.execute_query(
                    """UPDATE users SET email = ?, first_name = ?, last_name = ?, 
                       gender = ?, birthday = ?, street = ?, city = ?, avatar = ?,
                       is_active = ?, updated_at = CURRENT_TIMESTAMP
                       WHERE userid = ?""",
                    (self.email, self.first_name, self.last_name, self.gender,
                     self.birthday, self.street, self.city, self.avatar,
                     self.is_active, self.userid)
                )
                # Update password if provided
                if hashed_password:
                    db_manager.execute_query(
                        "UPDATE users SET password = ? WHERE userid = ?",
                        (hashed_password, self.userid)
                    )
                self.password = hashed_password  # Store hashed version
                logger.info(f"User.save: EXIT - User updated for userid={self.userid}")
            else:
                # Insert new user
                if not hashed_password:
                    raise ValueError("password is required for new users")
                
                user_id = db_manager.get_lastrowid(
                    """INSERT INTO users (userid, email, first_name, last_name, password,
                       gender, birthday, street, city, avatar, is_active)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (self.userid, self.email, self.first_name, self.last_name, hashed_password,
                     self.gender, self.birthday, self.street, self.city, self.avatar, self.is_active)
                )
                self.id = user_id
                self.password = hashed_password  # Store hashed version
                logger.info(f"User.save: EXIT - User created with id={user_id} for userid={self.userid}")
        except Exception as e:
            logger.exception(f"User.save: EXIT - Error: {str(e)}")
            raise
    
    def update_from_dict(self, data: Dict[str, Any]):
        """Update user fields from dictionary (partial update)"""
        logger.info(f"User.update_from_dict: ENTRY - userid={self.userid}")
        try:
            allowed_fields = [
                'email', 'first_name', 'last_name', 'gender', 'birthday',
                'street', 'city', 'avatar', 'is_active'
            ]
            
            for field in allowed_fields:
                if field in data:
                    setattr(self, field, data[field])
            
            # Handle password separately (needs hashing)
            if 'password' in data:
                self.password = generate_password_hash(data['password'])
            
            logger.info(f"User.update_from_dict: EXIT - Updated fields from dict")
        except Exception as e:
            logger.exception(f"User.update_from_dict: EXIT - Error: {str(e)}")
            raise
    
    def check_password(self, password: str) -> bool:
        """Check if provided password matches user's password"""
        if not self.password:
            return False
        return check_password_hash(self.password, password)
    
    def to_dict(self, include_avatar: bool = False, include_password: bool = False) -> dict:
        """Convert user to dictionary"""
        data = {
            'id': self.id,
            'userid': self.userid,
            'email': self.email,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'gender': self.gender,
            'birthday': self.birthday,
            'street': self.street,
            'city': self.city,
            'is_active': self.is_active,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
            **self._data
        }
        
        if include_password and self.password:
            data['password'] = self.password
        
        if include_avatar and self.avatar:
            import base64
            data['avatar'] = base64.b64encode(self.avatar).decode('utf-8')
        
        return data

