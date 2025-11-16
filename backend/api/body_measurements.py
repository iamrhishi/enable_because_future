"""
Body Measurements API endpoints
"""

from flask import Blueprint, request
from services.database import db_manager
from utils.response import success_response, error_response_from_string
from utils.middleware import require_auth
from utils.validators import validate_numeric
from utils.errors import NotFoundError
from utils.logger import logger

body_measurements_bp = Blueprint('body_measurements', __name__, url_prefix='/api/body-measurements')


@body_measurements_bp.route('', methods=['POST'])
@require_auth
def create_or_update_measurements():
    """Create or update body measurements for authenticated user"""
    try:
        user_id = request.user_id
        data = request.get_json()
        
        # Extract measurements
        height = data.get('height')
        weight = data.get('weight')
        chest = data.get('chest')
        waist = data.get('waist')
        hips = data.get('hips')
        inseam = data.get('inseam')
        shoulder_width = data.get('shoulder_width')
        arm_length = data.get('arm_length')
        unit = data.get('unit', 'metric')  # metric or imperial
        
        if unit not in ['metric', 'imperial']:
            return error_response_from_string('Unit must be metric or imperial', 400, 'VALIDATION_ERROR')
        
        # Validate numeric values if provided
        if height:
            height = validate_numeric(height, 'height', min_value=50, max_value=300)
        if weight:
            weight = validate_numeric(weight, 'weight', min_value=20, max_value=500)
        if chest:
            chest = validate_numeric(chest, 'chest', min_value=50, max_value=200)
        if waist:
            waist = validate_numeric(waist, 'waist', min_value=50, max_value=200)
        if hips:
            hips = validate_numeric(hips, 'hips', min_value=50, max_value=200)
        
        # Check if measurements exist
        existing = db_manager.execute_query(
            "SELECT id FROM body_measurements WHERE user_id = ?",
            (user_id,),
            fetch_one=True
        )
        
        if existing:
            # Update existing
            db_manager.execute_query(
                """UPDATE body_measurements 
                   SET height=?, weight=?, chest=?, waist=?, hips=?, inseam=?, 
                       shoulder_width=?, arm_length=?, unit=?, updated_at=CURRENT_TIMESTAMP
                   WHERE user_id=?""",
                (height, weight, chest, waist, hips, inseam, shoulder_width, arm_length, unit, user_id)
            )
            message = 'Body measurements updated successfully'
        else:
            # Create new
            db_manager.get_lastrowid(
                """INSERT INTO body_measurements 
                   (user_id, height, weight, chest, waist, hips, inseam, shoulder_width, arm_length, unit)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (user_id, height, weight, chest, waist, hips, inseam, shoulder_width, arm_length, unit)
            )
            message = 'Body measurements created successfully'
        
        # Fetch updated measurements
        measurements = db_manager.execute_query(
            "SELECT * FROM body_measurements WHERE user_id = ?",
            (user_id,),
            fetch_one=True
        )
        
        return success_response(data=measurements, message=message)
        
    except Exception as e:
        logger.error(f"Error saving body measurements: {str(e)}")
        return error_response_from_string(f'Server error: {str(e)}', 500)


@body_measurements_bp.route('/<user_id>', methods=['GET'])
@require_auth
def get_measurements(user_id):
    """Get body measurements for a user"""
    try:
        # Verify user can access this data (own data or admin)
        if request.user_id != user_id:
            return error_response_from_string('Not authorized to access this data', 403, 'AUTHORIZATION_ERROR')
        
        measurements = db_manager.execute_query(
            "SELECT * FROM body_measurements WHERE user_id = ?",
            (user_id,),
            fetch_one=True
        )
        
        if not measurements:
            return error_response_from_string('Body measurements not found', 404, 'NOT_FOUND')
        
        return success_response(data=measurements)
        
    except Exception as e:
        logger.error(f"Error fetching body measurements: {str(e)}")
        return error_response_from_string(f'Server error: {str(e)}', 500)


@body_measurements_bp.route('/<user_id>', methods=['PUT'])
@require_auth
def update_measurements(user_id):
    """Update body measurements (partial update allowed)"""
    try:
        # Verify user can update this data
        if request.user_id != user_id:
            return error_response_from_string('Not authorized', 403, 'AUTHORIZATION_ERROR')
        
        data = request.get_json()
        
        # Build update query dynamically
        updates = []
        values = []
        
        fields = ['height', 'weight', 'chest', 'waist', 'hips', 'inseam', 'shoulder_width', 'arm_length', 'unit']
        for field in fields:
            if field in data:
                if field == 'unit' and data[field] not in ['metric', 'imperial']:
                    return error_response_from_string('Unit must be metric or imperial', 400, 'VALIDATION_ERROR')
                updates.append(f"{field} = ?")
                values.append(data[field])
        
        if not updates:
            return error_response_from_string('No fields to update', 400, 'VALIDATION_ERROR')
        
        values.append(user_id)
        query = f"UPDATE body_measurements SET {', '.join(updates)}, updated_at=CURRENT_TIMESTAMP WHERE user_id = ?"
        
        db_manager.execute_query(query, tuple(values))
        
        # Fetch updated measurements
        measurements = db_manager.execute_query(
            "SELECT * FROM body_measurements WHERE user_id = ?",
            (user_id,),
            fetch_one=True
        )
        
        if not measurements:
            return error_response_from_string('Body measurements not found', 404, 'NOT_FOUND')
        
        return success_response(data=measurements, message='Body measurements updated successfully')
        
    except Exception as e:
        logger.error(f"Error updating body measurements: {str(e)}")
        return error_response_from_string(f'Server error: {str(e)}', 500)

