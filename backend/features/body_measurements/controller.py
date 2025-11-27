"""
Body Measurements API endpoints
Uses BodyMeasurements model for data operations
JWT authentication via @require_auth decorator extracts user_id from token
"""

from flask import Blueprint, request
from features.body_measurements.model import BodyMeasurements
from shared.response import success_response, error_response_from_string
from shared.middleware import require_auth
from shared.validators import validate_numeric
from shared.errors import NotFoundError, ValidationError
from shared.logger import logger

body_measurements_bp = Blueprint('body_measurements', __name__, url_prefix='/api/body-measurements')


@body_measurements_bp.route('', methods=['POST'])
@require_auth  # JWT decorator validates token and sets request.user_id from token
def create_or_update_measurements():
    """
    Create or update body measurements for authenticated user
    Uses BodyMeasurements model for data operations
    user_id is extracted from JWT token by @require_auth decorator
    """
    # user_id comes from JWT token via @require_auth decorator
    user_id = request.user_id
    logger.info(f"create_or_update_measurements: ENTRY - user_id={user_id} (from JWT)")
    
    try:
        data = request.get_json()
        if not data:
            return error_response_from_string('No data provided', 400, 'VALIDATION_ERROR')
        
        # Validate unit if provided
        unit = data.get('unit', 'metric')
        if unit not in ['metric', 'imperial']:
            return error_response_from_string('Unit must be metric or imperial', 400, 'VALIDATION_ERROR')
        
        # Validate numeric values if provided
        def validate_measurement(value, field_name, min_val, max_val):
            if value is not None:
                try:
                    return validate_numeric(value, field_name, min_value=min_val, max_value=max_val)
                except ValidationError as e:
                    raise ValueError(f'{field_name}: {str(e)}')
            return value
        
        # Validate and prepare measurement data
        measurement_data = {}
        
        # Basic measurements
        if 'height' in data:
            measurement_data['height'] = validate_measurement(data['height'], 'height', 50, 300)
        if 'weight' in data:
            measurement_data['weight'] = validate_measurement(data['weight'], 'weight', 20, 500)
        
        # Circumference measurements (20-200 cm range)
        circumference_fields = [
            'shoulder_circumference', 'arm_length', 'breast_circumference',
            'under_breast_circumference', 'waist_circumference', 'hip_circumference',
            'upper_thigh_circumference', 'neck_circumference', 'biceps_circumference',
            'upper_hip_circumference', 'wide_hip_circumference', 'calf_circumference'
        ]
        for field in circumference_fields:
            if field in data:
                measurement_data[field] = validate_measurement(data[field], field.replace('_', ' ').title(), 20, 200)
        
        # Length measurements (10-200 cm range)
        length_fields = [
            'waist_to_crotch_front_length', 'waist_to_crotch_back_length',
            'inner_leg_length', 'foot_length', 'foot_width'
        ]
        for field in length_fields:
            if field in data:
                measurement_data[field] = validate_measurement(data[field], field.replace('_', ' ').title(), 10, 200)
        
        # Legacy fields
        legacy_fields = ['chest', 'waist', 'hips']
        for field in legacy_fields:
            if field in data:
                measurement_data[field] = validate_measurement(data[field], field, 50, 200)
        if 'inseam' in data:
            measurement_data['inseam'] = validate_measurement(data['inseam'], 'inseam', 10, 200)
        if 'shoulder_width' in data:
            measurement_data['shoulder_width'] = validate_measurement(data['shoulder_width'], 'shoulder_width', 20, 200)
        
        measurement_data['unit'] = unit
        
        # Get or create measurements model
        measurements = BodyMeasurements.get_by_user(user_id)
        
        if measurements:
            # Update existing
            measurements.update_from_dict(measurement_data)
            measurements.save()
            message = 'Body measurements updated successfully'
        else:
            # Create new
            measurements = BodyMeasurements(user_id=user_id, **measurement_data)
            measurements.save()
            message = 'Body measurements created successfully'
        
        logger.info(f"create_or_update_measurements: EXIT - {message} for user_id={user_id}")
        return success_response(data=measurements.to_dict(), message=message)
        
    except ValueError as e:
        logger.exception(f"create_or_update_measurements: EXIT - ValidationError: {str(e)}")
        return error_response_from_string(str(e), 400, 'VALIDATION_ERROR')
    except Exception as e:
        logger.exception(f"create_or_update_measurements: EXIT - Error: {str(e)}")
        return error_response_from_string(f'Server error: {str(e)}', 500)


@body_measurements_bp.route('', methods=['GET'])
@require_auth  # JWT decorator validates token and sets request.user_id from token
def get_measurements():
    """
    Get body measurements for current authenticated user
    Uses BodyMeasurements model
    user_id is extracted from JWT token by @require_auth decorator
    """
    # user_id comes from JWT token via @require_auth decorator
    user_id = request.user_id
    logger.info(f"get_measurements: ENTRY - user_id={user_id} (from JWT)")
    
    try:
        measurements = BodyMeasurements.get_by_user(user_id)
        
        if not measurements:
            logger.info(f"get_measurements: EXIT - No measurements found for user_id={user_id}")
            return error_response_from_string('Body measurements not found', 404, 'NOT_FOUND')
        
        logger.info(f"get_measurements: EXIT - Measurements retrieved for user_id={user_id}")
        return success_response(data=measurements.to_dict())
        
    except Exception as e:
        logger.exception(f"get_measurements: EXIT - Error: {str(e)}")
        return error_response_from_string(f'Server error: {str(e)}', 500)


@body_measurements_bp.route('', methods=['PUT'])
@require_auth  # JWT decorator validates token and sets request.user_id from token
def update_measurements():
    """
    Update body measurements for current authenticated user (partial update allowed)
    Uses BodyMeasurements model
    user_id is extracted from JWT token by @require_auth decorator
    """
    # user_id comes from JWT token via @require_auth decorator
    user_id = request.user_id
    logger.info(f"update_measurements: ENTRY - user_id={user_id} (from JWT)")
    
    try:
        data = request.get_json()
        if not data:
            return error_response_from_string('No data provided', 400, 'VALIDATION_ERROR')
        
        # Get existing measurements
        measurements = BodyMeasurements.get_by_user(user_id)
        if not measurements:
            logger.warning(f"update_measurements: Measurements not found for user_id={user_id}")
            return error_response_from_string('Body measurements not found. Use POST to create.', 404, 'NOT_FOUND')
        
        # Validate unit if provided
        if 'unit' in data:
            if data['unit'] not in ['metric', 'imperial']:
                return error_response_from_string('Unit must be metric or imperial', 400, 'VALIDATION_ERROR')
        
        # Validate numeric values if provided
        def validate_measurement(value, field_name, min_val, max_val):
            if value is not None:
                try:
                    return validate_numeric(value, field_name, min_value=min_val, max_value=max_val)
                except ValidationError as e:
                    raise ValueError(f'{field_name}: {str(e)}')
            return value
        
        # Prepare update data with validation
        update_data = {}
        
        # Basic measurements
        if 'height' in data:
            update_data['height'] = validate_measurement(data['height'], 'height', 50, 300)
        if 'weight' in data:
            update_data['weight'] = validate_measurement(data['weight'], 'weight', 20, 500)
        
        # Circumference measurements
        circumference_fields = [
            'shoulder_circumference', 'arm_length', 'breast_circumference',
            'under_breast_circumference', 'waist_circumference', 'hip_circumference',
            'upper_thigh_circumference', 'neck_circumference', 'biceps_circumference',
            'upper_hip_circumference', 'wide_hip_circumference', 'calf_circumference'
        ]
        for field in circumference_fields:
            if field in data:
                update_data[field] = validate_measurement(data[field], field.replace('_', ' ').title(), 20, 200)
        
        # Length measurements
        length_fields = [
            'waist_to_crotch_front_length', 'waist_to_crotch_back_length',
            'inner_leg_length', 'foot_length', 'foot_width'
        ]
        for field in length_fields:
            if field in data:
                update_data[field] = validate_measurement(data[field], field.replace('_', ' ').title(), 10, 200)
        
        # Legacy fields
        legacy_fields = ['chest', 'waist', 'hips']
        for field in legacy_fields:
            if field in data:
                update_data[field] = validate_measurement(data[field], field, 50, 200)
        if 'inseam' in data:
            update_data['inseam'] = validate_measurement(data['inseam'], 'inseam', 10, 200)
        if 'shoulder_width' in data:
            update_data['shoulder_width'] = validate_measurement(data['shoulder_width'], 'shoulder_width', 20, 200)
        
        if 'unit' in data:
            update_data['unit'] = data['unit']
        
        if not update_data:
            return error_response_from_string('No fields to update', 400, 'VALIDATION_ERROR')
        
        # Update model and save
        measurements.update_from_dict(update_data)
        measurements.save()
        
        logger.info(f"update_measurements: EXIT - Measurements updated for user_id={user_id}")
        return success_response(data=measurements.to_dict(), message='Body measurements updated successfully')
        
    except ValueError as e:
        logger.exception(f"update_measurements: EXIT - ValidationError: {str(e)}")
        return error_response_from_string(str(e), 400, 'VALIDATION_ERROR')
    except Exception as e:
        logger.exception(f"update_measurements: EXIT - Error: {str(e)}")
        return error_response_from_string(f'Server error: {str(e)}', 500)

