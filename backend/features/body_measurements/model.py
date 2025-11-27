"""
Body measurements model
"""

from typing import Optional, Dict, Any
from shared.database import db_manager
from shared.logger import logger


class BodyMeasurements:
    """Body measurements data model - all measurements in cm (metric)"""
    
    def __init__(self, id: int = None, user_id: str = None, 
                 # Basic measurements
                 height: float = None, weight: float = None,
                 # Circumference measurements (all in cm)
                 shoulder_circumference: float = None, arm_length: float = None,
                 breast_circumference: float = None, under_breast_circumference: float = None,
                 waist_circumference: float = None, hip_circumference: float = None,
                 upper_thigh_circumference: float = None, neck_circumference: float = None,
                 biceps_circumference: float = None, upper_hip_circumference: float = None,
                 wide_hip_circumference: float = None, calf_circumference: float = None,
                 # Length measurements (all in cm)
                 waist_to_crotch_front_length: float = None,
                 waist_to_crotch_back_length: float = None,
                 inner_leg_length: float = None, foot_length: float = None,
                 foot_width: float = None,
                 # Legacy fields (for backward compatibility)
                 chest: float = None, waist: float = None, hips: float = None,
                 inseam: float = None, shoulder_width: float = None,
                 # Unit (always 'metric' for cm)
                 unit: str = 'metric',
                 **kwargs):
        self.id = id
        self.user_id = user_id
        # Basic
        self.height = height
        self.weight = weight
        # Circumferences
        self.shoulder_circumference = shoulder_circumference
        self.arm_length = arm_length
        self.breast_circumference = breast_circumference
        self.under_breast_circumference = under_breast_circumference
        self.waist_circumference = waist_circumference
        self.hip_circumference = hip_circumference
        self.upper_thigh_circumference = upper_thigh_circumference
        self.neck_circumference = neck_circumference
        self.biceps_circumference = biceps_circumference
        self.upper_hip_circumference = upper_hip_circumference
        self.wide_hip_circumference = wide_hip_circumference
        self.calf_circumference = calf_circumference
        # Lengths
        self.waist_to_crotch_front_length = waist_to_crotch_front_length
        self.waist_to_crotch_back_length = waist_to_crotch_back_length
        self.inner_leg_length = inner_leg_length
        self.foot_length = foot_length
        self.foot_width = foot_width
        # Legacy
        self.chest = chest
        self.waist = waist
        self.hips = hips
        self.inseam = inseam
        self.shoulder_width = shoulder_width
        # Unit
        self.unit = unit
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
        """Save body measurements to database (creates or updates)"""
        logger.info(f"BodyMeasurements.save: ENTRY - user_id={self.user_id}")
        try:
            if not self.user_id:
                raise ValueError("user_id is required")
            
            # Check if measurements exist for this user
            existing = db_manager.execute_query(
                "SELECT id FROM body_measurements WHERE user_id = ?",
                (self.user_id,),
                fetch_one=True
            )
            
            if existing:
                # Update existing
                self.id = existing['id']
                db_manager.execute_query(
                    """UPDATE body_measurements 
                       SET height=?, weight=?, shoulder_circumference=?, arm_length=?,
                           breast_circumference=?, under_breast_circumference=?, waist_circumference=?,
                           hip_circumference=?, upper_thigh_circumference=?, neck_circumference=?,
                           biceps_circumference=?, upper_hip_circumference=?, wide_hip_circumference=?,
                           calf_circumference=?, waist_to_crotch_front_length=?, waist_to_crotch_back_length=?,
                           inner_leg_length=?, foot_length=?, foot_width=?,
                           chest=?, waist=?, hips=?, inseam=?, shoulder_width=?,
                           unit=?, updated_at=CURRENT_TIMESTAMP
                       WHERE user_id=?""",
                    (self.height, self.weight, self.shoulder_circumference, self.arm_length,
                     self.breast_circumference, self.under_breast_circumference, self.waist_circumference,
                     self.hip_circumference, self.upper_thigh_circumference, self.neck_circumference,
                     self.biceps_circumference, self.upper_hip_circumference, self.wide_hip_circumference,
                     self.calf_circumference, self.waist_to_crotch_front_length, self.waist_to_crotch_back_length,
                     self.inner_leg_length, self.foot_length, self.foot_width,
                     self.chest, self.waist, self.hips, self.inseam, self.shoulder_width,
                     self.unit, self.user_id)
                )
                logger.info(f"BodyMeasurements.save: EXIT - Measurements updated for user_id={self.user_id}")
            else:
                # Insert new
                measurement_id = db_manager.get_lastrowid(
                    """INSERT INTO body_measurements 
                       (user_id, height, weight, shoulder_circumference, arm_length,
                        breast_circumference, under_breast_circumference, waist_circumference,
                        hip_circumference, upper_thigh_circumference, neck_circumference,
                        biceps_circumference, upper_hip_circumference, wide_hip_circumference,
                        calf_circumference, waist_to_crotch_front_length, waist_to_crotch_back_length,
                        inner_leg_length, foot_length, foot_width,
                        chest, waist, hips, inseam, shoulder_width, unit)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (self.user_id, self.height, self.weight, self.shoulder_circumference, self.arm_length,
                     self.breast_circumference, self.under_breast_circumference, self.waist_circumference,
                     self.hip_circumference, self.upper_thigh_circumference, self.neck_circumference,
                     self.biceps_circumference, self.upper_hip_circumference, self.wide_hip_circumference,
                     self.calf_circumference, self.waist_to_crotch_front_length, self.waist_to_crotch_back_length,
                     self.inner_leg_length, self.foot_length, self.foot_width,
                     self.chest, self.waist, self.hips, self.inseam, self.shoulder_width, self.unit)
                )
                self.id = measurement_id
                logger.info(f"BodyMeasurements.save: EXIT - Measurements created with id={measurement_id} for user_id={self.user_id}")
        except Exception as e:
            logger.exception(f"BodyMeasurements.save: EXIT - Error: {str(e)}")
            raise
    
    def update_from_dict(self, data: Dict[str, Any]):
        """Update model fields from dictionary (partial update)"""
        logger.info(f"BodyMeasurements.update_from_dict: ENTRY - user_id={self.user_id}")
        try:
            # All measurement fields
            measurement_fields = [
                'height', 'weight', 'shoulder_circumference', 'arm_length',
                'breast_circumference', 'under_breast_circumference', 'waist_circumference',
                'hip_circumference', 'upper_thigh_circumference', 'neck_circumference',
                'biceps_circumference', 'upper_hip_circumference', 'wide_hip_circumference',
                'calf_circumference', 'waist_to_crotch_front_length', 'waist_to_crotch_back_length',
                'inner_leg_length', 'foot_length', 'foot_width',
                'chest', 'waist', 'hips', 'inseam', 'shoulder_width', 'unit'
            ]
            
            for field in measurement_fields:
                if field in data:
                    setattr(self, field, data[field])
            
            logger.info(f"BodyMeasurements.update_from_dict: EXIT - Updated fields from dict")
        except Exception as e:
            logger.exception(f"BodyMeasurements.update_from_dict: EXIT - Error: {str(e)}")
            raise
    
    def to_dict(self) -> dict:
        """Convert body measurements to dictionary"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            # Basic
            'height': self.height,
            'weight': self.weight,
            # Circumferences
            'shoulder_circumference': self.shoulder_circumference,
            'arm_length': self.arm_length,
            'breast_circumference': self.breast_circumference,
            'under_breast_circumference': self.under_breast_circumference,
            'waist_circumference': self.waist_circumference,
            'hip_circumference': self.hip_circumference,
            'upper_thigh_circumference': self.upper_thigh_circumference,
            'neck_circumference': self.neck_circumference,
            'biceps_circumference': self.biceps_circumference,
            'upper_hip_circumference': self.upper_hip_circumference,
            'wide_hip_circumference': self.wide_hip_circumference,
            'calf_circumference': self.calf_circumference,
            # Lengths
            'waist_to_crotch_front_length': self.waist_to_crotch_front_length,
            'waist_to_crotch_back_length': self.waist_to_crotch_back_length,
            'inner_leg_length': self.inner_leg_length,
            'foot_length': self.foot_length,
            'foot_width': self.foot_width,
            # Legacy
            'chest': self.chest,
            'waist': self.waist,
            'hips': self.hips,
            'inseam': self.inseam,
            'shoulder_width': self.shoulder_width,
            # Unit
            'unit': self.unit,
            **self._data
        }

