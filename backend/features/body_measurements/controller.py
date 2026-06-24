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
        # Handle JSON requests safely
        content_type = request.content_type or ''
        if 'application/json' in content_type:
            data = request.get_json(silent=True, force=False) or {}
        else:
            data = {}
        
        logger.info(f"create_or_update_measurements: Raw request data: {data}")
        
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
            measurement_data['height'] = validate_measurement(data['height'], 'Height (cm)', 50, 250)
        if 'weight' in data:
            measurement_data['weight'] = validate_measurement(data['weight'], 'Weight (kg)', 20, 250)
        
        # Circumference measurements with specific ranges
        circumference_fields = {
            'shoulder_circumference': (60, 200),
            'arm_length': (25, 100),
            'biceps_circumference': (10, 100),
            'breast_circumference': (50, 300),
            'under_breast_circumference': (40, 300),
            'neck_circumference': (20, 100),
            'upper_hip_circumference': (40, 200),
            'waist_circumference': (30, 300),
            'hip_circumference': (50, 300),
            'upper_thigh_circumference': (25, 300),
            'wide_hip_circumference': (40, 200),
            'calf_circumference': (20, 100)
        }
        for field, (min_val, max_val) in circumference_fields.items():
            if field in data:
                measurement_data[field] = validate_measurement(data[field], field.replace('_', ' ').title(), min_val, max_val)
        
        # Length measurements with specific ranges
        length_fields = {
            'collarbone_to_belly_button_length': (30, 150),
            'waist_to_crotch_front_length': (15, 100),
            'waist_to_crotch_back_length': (15, 100),
            'inner_leg_length': (50, 200),
            'foot_length': (10, 60),
            'foot_width': (5, 20)
        }
        for field, (min_val, max_val) in length_fields.items():
            if field in data:
                measurement_data[field] = validate_measurement(data[field], field.replace('_', ' ').title(), min_val, max_val)
        
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
            logger.info(f"create_or_update_measurements: Updating existing measurements, measurement_data keys: {measurement_data.keys()}")
            measurements.update_from_dict(measurement_data)
            measurements.save()
            message = 'Body measurements updated successfully'
        else:
            # Create new
            logger.info(f"create_or_update_measurements: Creating new measurements, measurement_data: {measurement_data}")
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
        # Handle JSON requests safely
        content_type = request.content_type or ''
        if 'application/json' in content_type:
            data = request.get_json(silent=True, force=False) or {}
        else:
            data = {}
        
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


@body_measurements_bp.route('/estimate', methods=['POST'])
@require_auth
def estimate_measurements():
    """
    Estimate body measurements from front (and optional side) Base64 images and height/weight.
    Saves/updates the estimated measurements to the database.
    """
    user_id = request.user_id
    logger.info(f"estimate_measurements: ENTRY - user_id={user_id}")
    
    try:
        import cv2
        import numpy as np
        import base64
        
        # Handle JSON requests safely
        content_type = request.content_type or ''
        if 'application/json' not in content_type:
            return error_response_from_string('Content-Type must be application/json', 415, 'VALIDATION_ERROR')
            
        data = request.get_json(silent=True, force=False) or {}
        if not data:
            return error_response_from_string('No data provided', 400, 'VALIDATION_ERROR')
            
        height = data.get('height')
        weight = data.get('weight')
        front_image_b64 = data.get('frontImage')
        side_image_b64 = data.get('sideImage')
        
        if height is None or weight is None or not front_image_b64:
            return error_response_from_string('height, weight, and frontImage are required', 400, 'VALIDATION_ERROR')
            
        # Validate numeric inputs
        try:
            height = float(height)
            weight = float(weight)
        except (ValueError, TypeError):
            return error_response_from_string('height and weight must be numeric', 400, 'VALIDATION_ERROR')
            
        if not (50 <= height <= 250):
            return error_response_from_string('Height must be between 50 and 250 cm', 400, 'VALIDATION_ERROR')
        if not (20 <= weight <= 250):
            return error_response_from_string('Weight must be between 20 and 250 kg', 400, 'VALIDATION_ERROR')
            
        # Base64 Image Decoding Helper
        def decode_base64_image(base64_str: str) -> np.ndarray:
            if "," in base64_str:
                base64_str = base64_str.split(",")[1]
            img_data = base64.b64decode(base64_str)
            nparr = np.frombuffer(img_data, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if img is None:
                raise ValueError("Failed to decode image. Format may be corrupt.")
            return img

        # Downscale image to optimize performance & limit resource usage
        def preprocess_and_resize(img: np.ndarray, target_height: int = 1280) -> np.ndarray:
            h, w = img.shape[:2]
            if h > target_height:
                scale = target_height / h
                target_width = int(w * scale)
                return cv2.resize(img, (target_width, target_height), interpolation=cv2.INTER_AREA)
            return img

        # Decode front image
        try:
            front_img = decode_base64_image(front_image_b64)
            front_img = preprocess_and_resize(front_img)
        except Exception as e:
            logger.warning(f"Failed to decode front image for user_id={user_id}: {str(e)}")
            return error_response_from_string(f"Invalid frontImage: {str(e)}", 400, 'VALIDATION_ERROR')
            
        # Decode side image (optional)
        side_img = None
        if side_image_b64:
            try:
                side_img = decode_base64_image(side_image_b64)
                side_img = preprocess_and_resize(side_img)
            except Exception as e:
                logger.warning(f"Failed to decode side image for user_id={user_id}: {str(e)}")
                return error_response_from_string(f"Invalid sideImage: {str(e)}", 400, 'VALIDATION_ERROR')

        # Run detection and estimation
        # MediaPipe isn't thread-safe, so we must instantiate and close within context block
        from body_estimator.detector import MediaPipeDetector
        from body_estimator.estimator import estimate_body_measurements
        from body_estimator.visualizer import draw_visual_debug
        from body_estimator.utils import get_largest_connected_component
        
        try:
            with MediaPipeDetector() as detector:
                # 1. Run detection for overlays
                landmarks_front, mask_front, _ = detector.detect(front_img)
                if landmarks_front is None:
                    return error_response_from_string(
                        "No pose landmarks detected in the front-facing image. Please ensure the entire body is visible.",
                        400, 'VALIDATION_ERROR'
                    )
                
                landmarks_side = None
                mask_side = None
                if side_img is not None:
                    landmarks_side, mask_side, _ = detector.detect(side_img)
                
                # 2. Run estimation pipeline
                result = estimate_body_measurements(
                    front_img_np=front_img,
                    height_cm=height,
                    weight_kg=weight,
                    side_img_np=side_img,
                    detector=detector
                )
                
                # 3. Create cleaned masks & generate scanner overlays
                cleaned_mask_front = get_largest_connected_component(mask_front)
                front_overlay = draw_visual_debug(
                    front_img, landmarks_front, cleaned_mask_front, side_view=False
                )
                
                side_overlay = None
                if side_img is not None and landmarks_side is not None and mask_side is not None:
                    cleaned_mask_side = get_largest_connected_component(mask_side)
                    side_overlay = draw_visual_debug(
                        side_img, landmarks_side, cleaned_mask_side, side_view=True
                    )
        except Exception as e:
            logger.exception(f"Estimation pipeline failed for user_id={user_id}: {str(e)}")
            return error_response_from_string(f"Estimation pipeline failed: {str(e)}", 500)
            
        # 4. Map camelCase estimation results to database snake_case fields
        est_measurements = result["measurements"]
        
        mapped_data = {
            'height': height,
            'weight': weight,
            'shoulder_circumference': est_measurements.get('shoulderCircumference'),
            'arm_length': est_measurements.get('armLength'),
            'breast_circumference': est_measurements.get('breastCircumference'),
            'under_breast_circumference': est_measurements.get('underBreastCircumference'),
            'waist_circumference': est_measurements.get('waistCircumference'),
            'hip_circumference': est_measurements.get('hipCircumference'),
            'upper_thigh_circumference': est_measurements.get('upperThighCircumference'),
            'biceps_circumference': est_measurements.get('bicepsCircumference'),
            'collarbone_to_belly_button_length': est_measurements.get('collarboneToBellyButtonLength'),
            'foot_length': est_measurements.get('footLength'),
            'foot_width': est_measurements.get('footWidth'),
            'waist_to_crotch_front_length': est_measurements.get('waistToCrotchFrontLength'),
            'waist_to_crotch_back_length': est_measurements.get('waistToCrotchBackLength'),
            'inner_leg_length': est_measurements.get('innerLegLength'),
            'unit': 'metric'
        }
        
        # 5. Persist to database
        db_model = BodyMeasurements.get_by_user(user_id)
        if db_model:
            db_model.update_from_dict(mapped_data)
            db_model.save()
            msg = 'Body measurements estimated and updated successfully'
        else:
            db_model = BodyMeasurements(user_id=user_id, **mapped_data)
            db_model.save()
            msg = 'Body measurements estimated and created successfully'
            
        # 6. Construct response using database model schema (snake_case)
        response_data = {
            'measurements': db_model.to_dict(),
            'confidence': result['confidence'],
            'frontOverlay': front_overlay,
            'sideOverlay': side_overlay
        }
        
        logger.info(f"estimate_measurements: EXIT - {msg} for user_id={user_id}")
        return success_response(data=response_data, message=msg)
        
    except Exception as e:
        logger.exception(f"estimate_measurements: EXIT - Error: {str(e)}")
        return error_response_from_string(f'Server error: {str(e)}', 500)


