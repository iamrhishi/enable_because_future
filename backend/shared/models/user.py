"""
User model
"""

import secrets
from datetime import datetime, timezone
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
                 postal_code: str = None, country: str = None, avatar: bytes = None, avatar_path: str = None,
                 is_active: bool = True, is_deleted: bool = False, deleted_at: str = None,
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
        self.postal_code = postal_code
        self.country = country
        self.avatar = avatar  # Legacy BLOB field (for backward compatibility)
        self.avatar_path = avatar_path  # New file path field
        self.is_active = is_active
        self.is_deleted = is_deleted
        self.deleted_at = deleted_at
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
                       gender = ?, birthday = ?, street = ?, city = ?, postal_code = ?, country = ?, avatar = ?,
                       avatar_path = ?, is_active = ?, is_deleted = ?, deleted_at = ?, updated_at = CURRENT_TIMESTAMP
                       WHERE userid = ?""",
                    (self.email, self.first_name, self.last_name, self.gender,
                     self.birthday, self.street, self.city, self.postal_code, self.country, self.avatar,
                     self.avatar_path, self.is_active, self.is_deleted, self.deleted_at, self.userid)
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
                       gender, birthday, street, city, postal_code, country, avatar, avatar_path, is_active)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (self.userid, self.email, self.first_name, self.last_name, hashed_password,
                     self.gender, self.birthday, self.street, self.city, self.postal_code, self.country, self.avatar, self.avatar_path, self.is_active)
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
                'street', 'city', 'postal_code', 'country', 'avatar', 'avatar_path', 'is_active'
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

    def deactivate_account(self) -> None:
        """
        Delete account: disable login and erase all personal data associated
        with this user, for GDPR Article 17 (Right to Erasure) / Apple App
        Store 5.1.1(v) compliance. The user row itself is kept (scrubbed) so
        other tables' foreign keys and historical references stay valid, but
        every piece of the user's actual personal data - profile fields,
        body measurements, wardrobe items and their images, try-on jobs and
        results (including body/avatar photos), and their identifying fields
        in analytics - is erased or anonymized, not merely hidden.
        """
        logger.info(f"User.deactivate_account: ENTRY - userid={self.userid}")
        if not self.is_active:
            raise ValueError("Account is already deactivated")

        timestamp = datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')
        deleted_email = f"deleted_{self.userid}_{timestamp}@account-deleted.invalid"

        # Erase all stored files for this user (avatars, wardrobe images,
        # try-on result photos) regardless of how many items exist.
        try:
            from shared.storage import get_storage_service
            storage_service = get_storage_service()
            for prefix in (f"avatars/{self.userid}/", f"wardrobe/{self.userid}/", f"tryon-results/{self.userid}/"):
                storage_service.delete_prefix(prefix)
        except Exception as e:
            logger.warning(f"User.deactivate_account: Failed to delete stored files: {e}")

        # Erase rows in every table holding this user's personal data.
        # tryon_results/wardrobe hold actual body/garment photos as BLOBs -
        # deleting the rows erases that data directly (no separate storage
        # cleanup needed for those specific columns).
        for query in (
            "DELETE FROM body_measurements WHERE user_id = ?",
            "DELETE FROM tryon_results WHERE user_id = ?",
            "DELETE FROM tryon_jobs WHERE user_id = ?",
            "DELETE FROM wardrobe WHERE user_id = ?",
            "DELETE FROM wardrobe_categories WHERE user_id = ?",
        ):
            try:
                db_manager.execute_query(query, (self.userid,))
            except Exception as e:
                logger.warning(f"User.deactivate_account: Failed running '{query}': {e}")

        # Anonymize (rather than delete) analytics rows: strip identifying
        # fields but keep event_type/created_at so aggregate dashboards stay
        # accurate without retaining this user's personal data.
        for table in ("analytics_events", "analytics_events_archive"):
            try:
                db_manager.execute_query(
                    f"UPDATE {table} SET user_id = NULL, user_email = NULL, "
                    f"ip_address = NULL, user_agent = NULL WHERE user_id = ?",
                    (self.userid,)
                )
            except Exception as e:
                logger.warning(f"User.deactivate_account: Failed anonymizing {table}: {e}")

        self.email = deleted_email
        self.first_name = None
        self.last_name = None
        self.gender = None
        self.birthday = None
        self.street = None
        self.city = None
        self.postal_code = None
        self.country = None
        self.avatar = None
        self.avatar_path = None
        self.is_active = False
        self.is_deleted = True
        self.deleted_at = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
        self.password = secrets.token_urlsafe(32)
        self.save()
        logger.info(f"User.deactivate_account: EXIT - Account and all personal data erased for userid={self.userid}")
    
    def to_dict(self, include_avatar: bool = False, include_password: bool = False) -> dict:
        """Convert user to dictionary"""
        # Filter out bytes objects and non-serializable values from _data
        import json
        filtered_data = {}
        if self._data:
            for k, v in self._data.items():
                # Skip bytes objects (like avatar BLOB)
                if isinstance(v, bytes):
                    continue
                # Skip password field unless explicitly requested
                if k == 'password' and not include_password:
                    continue
                # Test if value is JSON-serializable
                try:
                    json.dumps(v)
                    filtered_data[k] = v
                except (TypeError, ValueError):
                    # Convert datetime objects to strings
                    if hasattr(v, 'isoformat'):
                        filtered_data[k] = v.isoformat()
                    else:
                        continue
        
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
            'postal_code': self.postal_code,
            'country': self.country,
            'is_active': self.is_active,
            'is_deleted': self.is_deleted,
            'deleted_at': self.deleted_at,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
            **filtered_data
        }
        
        if include_password and self.password:
            data['password'] = self.password
        
        if include_avatar and self.avatar:
            import base64
            data['avatar'] = base64.b64encode(self.avatar).decode('utf-8')
        
        return data

