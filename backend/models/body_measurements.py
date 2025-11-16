"""
Body measurements model
"""

from typing import Optional
from services.database import db_manager
from utils.logger import logger


class BodyMeasurements:
    """Body measurements data model"""
    
    def __init__(self, id: int = None, user_id: str = None, 
                 chest: float = None, waist: float = None, hips: float = None,
                 inseam: float = None, height: float = None, weight: float = None,
                 **kwargs):
        self.id = id
        self.user_id = user_id
        self.chest = chest
        self.waist = waist
        self.hips = hips
        self.inseam = inseam
        self.height = height
        self.weight = weight
        self._data = kwargs
    
    @classmethod
    def get_by_user(cls, user_id: str) -> Optional['BodyMeasurements']:
        """Get body measurements for a user"""
        logger.info(f"BodyMeasurements.get_by_user: ENTRY - user_id={user_id}")
        try:
            result = db_manager.execute_query(
                "SELECT * FROM body_measurements WHERE user_id = ? ORDER BY id DESC LIMIT 1",
                (user_id,),
                fetch_one=True
            )
            if result:
                measurements = cls(**dict(result))
                logger.info(f"BodyMeasurements.get_by_user: EXIT - Measurements found")
                return measurements
            logger.info(f"BodyMeasurements.get_by_user: EXIT - No measurements found")
            return None
        except Exception as e:
            logger.exception(f"BodyMeasurements.get_by_user: EXIT - Error: {str(e)}")
            raise
    
    def save(self):
        """Save body measurements to database"""
        logger.info(f"BodyMeasurements.save: ENTRY - user_id={self.user_id}")
        try:
            if self.id:
                # Update
                db_manager.execute_query(
                    """UPDATE body_measurements SET chest = ?, waist = ?, hips = ?,
                       inseam = ?, height = ?, weight = ? WHERE id = ? AND user_id = ?""",
                    (self.chest, self.waist, self.hips, self.inseam, 
                     self.height, self.weight, self.id, self.user_id)
                )
                logger.info(f"BodyMeasurements.save: EXIT - Measurements updated")
            else:
                # Insert
                measurement_id = db_manager.get_lastrowid(
                    """INSERT INTO body_measurements (user_id, chest, waist, hips, 
                       inseam, height, weight) VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (self.user_id, self.chest, self.waist, self.hips,
                     self.inseam, self.height, self.weight)
                )
                self.id = measurement_id
                logger.info(f"BodyMeasurements.save: EXIT - Measurements created with id={measurement_id}")
        except Exception as e:
            logger.exception(f"BodyMeasurements.save: EXIT - Error: {str(e)}")
            raise
    
    def to_dict(self) -> dict:
        """Convert body measurements to dictionary"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'chest': self.chest,
            'waist': self.waist,
            'hips': self.hips,
            'inseam': self.inseam,
            'height': self.height,
            'weight': self.weight,
            **self._data
        }

