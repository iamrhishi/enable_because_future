"""
Authentication API endpoints
Uses User and BodyMeasurements models for data operations
"""

from flask import Blueprint, request, jsonify
from features.auth.service import generate_token
from shared.models.user import User
from features.body_measurements.model import BodyMeasurements
from shared.response import success_response, error_response_from_string
from shared.validators import validate_email, validate_password, validate_numeric
from shared.errors import ValidationError, AuthenticationError
from config import Config
from shared.logger import logger
import uuid

auth_bp = Blueprint('auth', __name__, url_prefix='/api')


@auth_bp.route('/create-account', methods=['POST'])
def create_account():
    """Create a new user account with personal information and body measurements"""
    logger.info("create_account: ENTRY")
    try:
        data = request.get_json() if request.is_json else request.form
        
        # ===== Personal Information =====
        # Use (data.get('field') or '') to handle both missing keys and null values
        email = validate_email((data.get('email') or '').strip())
        password = validate_password(data.get('password') or '')
        confirm_password = data.get('confirm_password') or ''
        first_name = (data.get('first_name') or '').strip()
        last_name = (data.get('last_name') or '').strip()
        gender = (data.get('gender') or '').strip()
        birthday = (data.get('birthday') or data.get('birthdate') or '').strip()  # Format: YYYY-MM-DD
        street = (data.get('street') or '').strip()
        city = (data.get('city') or '').strip()
        postal_code = (data.get('postal_code') or data.get('postal-code') or '').strip()  # Support both formats
        
        # Validate password confirmation
        if password != confirm_password:
            logger.warning("create_account: Password confirmation mismatch")
            return error_response_from_string('Password and confirm password do not match', 400, 'VALIDATION_ERROR')
        
        # Validate required fields
        if not first_name:
            return error_response_from_string('First name is required', 400, 'VALIDATION_ERROR')
        if not last_name:
            return error_response_from_string('Last name is required', 400, 'VALIDATION_ERROR')
        
        # Gender is optional; validate only when provided
        valid_genders = ['male', 'female', 'other', 'prefer-not-to-say']
        if gender and gender not in valid_genders:
            return error_response_from_string('Invalid gender selection', 400, 'VALIDATION_ERROR')
        
        # Validate birthday format if provided
        if birthday:
            try:
                from datetime import datetime
                datetime.strptime(birthday, '%Y-%m-%d')
            except ValueError:
                return error_response_from_string('Birthday must be in YYYY-MM-DD format', 400, 'VALIDATION_ERROR')
        
        # ===== Body Measurements =====
        # Basic measurements
        height = data.get('height')  # in cm
        weight = data.get('weight')  # in kg
        
        # Circumference measurements (all in cm)
        shoulder_circumference = data.get('shoulder_circumference')
        arm_length = data.get('arm_length')
        biceps_circumference = data.get('biceps_circumference')
        breast_circumference = data.get('breast_circumference')
        under_breast_circumference = data.get('under_breast_circumference')
        waist_circumference = data.get('waist_circumference')
        hip_circumference = data.get('hip_circumference')
        upper_thigh_circumference = data.get('upper_thigh_circumference')
        
        # Additional detailed measurements
        neck_circumference = data.get('neck_circumference')
        upper_hip_circumference = data.get('upper_hip_circumference')
        wide_hip_circumference = data.get('wide_hip_circumference')
        calf_circumference = data.get('calf_circumference')
        
        # Length measurements (all in cm)
        collarbone_to_belly_button_length = data.get('collarbone_to_belly_button_length')
        waist_to_crotch_front_length = data.get('waist_to_crotch_front_length')
        waist_to_crotch_back_length = data.get('waist_to_crotch_back_length')
        inner_leg_length = data.get('inner_leg_length')
        foot_length = data.get('foot_length')
        foot_width = data.get('foot_width')
        
        # Validate measurement ranges (if provided)
        def validate_measurement(value, field_name, min_val, max_val):
            if value is not None:
                try:
                    val = float(value)
                    if not (min_val <= val <= max_val):
                        return f'{field_name} must be between {min_val} and {max_val}'
                except (ValueError, TypeError):
                    return f'{field_name} must be a valid number'
            return None
        
        # Validate basic measurements
        if height:
            error = validate_measurement(height, 'Height', 50, 250)
            if error:
                return error_response_from_string(error, 400, 'VALIDATION_ERROR')
        if weight:
            error = validate_measurement(weight, 'Weight', 20, 250)
            if error:
                return error_response_from_string(error, 400, 'VALIDATION_ERROR')
        
        # Validate circumference measurements with specific ranges
        circumference_fields = {
            'shoulder_circumference': (shoulder_circumference, 60, 200),
            'arm_length': (arm_length, 25, 100),
            'biceps_circumference': (biceps_circumference, 10, 100),
            'breast_circumference': (breast_circumference, 50, 300),
            'under_breast_circumference': (under_breast_circumference, 40, 300),
            'neck_circumference': (neck_circumference, 20, 100),
            'upper_hip_circumference': (upper_hip_circumference, 40, 200),
            'waist_circumference': (waist_circumference, 30, 300),
            'hip_circumference': (hip_circumference, 50, 300),
            'upper_thigh_circumference': (upper_thigh_circumference, 25, 300),
            'wide_hip_circumference': (wide_hip_circumference, 40, 200),
            'calf_circumference': (calf_circumference, 20, 100),
        }
        for field_name, (value, min_val, max_val) in circumference_fields.items():
            if value:
                error = validate_measurement(value, field_name.replace('_', ' ').title(), min_val, max_val)
                if error:
                    return error_response_from_string(error, 400, 'VALIDATION_ERROR')
        
        # Validate length measurements with specific ranges
        length_fields = {
            'collarbone_to_belly_button_length': (collarbone_to_belly_button_length, 30, 150),
            'waist_to_crotch_front_length': (waist_to_crotch_front_length, 15, 100),
            'waist_to_crotch_back_length': (waist_to_crotch_back_length, 15, 100),
            'inner_leg_length': (inner_leg_length, 50, 200),
            'foot_length': (foot_length, 10, 60),
            'foot_width': (foot_width, 5, 20),
        }
        for field_name, (value, min_val, max_val) in length_fields.items():
            if value:
                error = validate_measurement(value, field_name.replace('_', ' ').title(), min_val, max_val)
                if error:
                    return error_response_from_string(error, 400, 'VALIDATION_ERROR')
        
        # Generate unique userid
        userid = str(uuid.uuid4())[:8]
        
        # Check if email already exists using User model
        existing_user = User.get_by_email(email)
        if existing_user:
            logger.warning(f"create_account: Email already exists: {email}")
            return error_response_from_string('Email already registered', 409, 'EMAIL_EXISTS')
        
        # Create user using User model
        user = User(
            userid=userid,
            email=email,
            first_name=first_name,
            last_name=last_name,
            password=password,  # Will be hashed in save()
            gender=gender if gender else None,
            birthday=birthday if birthday else None,
            street=street if street else None,
            city=city if city else None,
            postal_code=postal_code if postal_code else None,
            is_active=True
        )
        user.save()  # This will hash the password
        logger.info(f"create_account: User created with userid={userid}")
        
        # Create body measurements if any are provided
        measurements_provided = any([
            height, weight, shoulder_circumference, arm_length, biceps_circumference,
            breast_circumference, under_breast_circumference, waist_circumference, 
            hip_circumference, upper_thigh_circumference, neck_circumference, 
            upper_hip_circumference, wide_hip_circumference, calf_circumference,
            collarbone_to_belly_button_length, waist_to_crotch_front_length, 
            waist_to_crotch_back_length, inner_leg_length, foot_length, foot_width
        ])
        
        if measurements_provided:
            # Prepare measurement data
            measurement_data = {
                'height': height,
                'weight': weight,
                'shoulder_circumference': shoulder_circumference,
                'arm_length': arm_length,
                'biceps_circumference': biceps_circumference,
                'breast_circumference': breast_circumference,
                'under_breast_circumference': under_breast_circumference,
                'waist_circumference': waist_circumference,
                'hip_circumference': hip_circumference,
                'upper_thigh_circumference': upper_thigh_circumference,
                'neck_circumference': neck_circumference,
                'upper_hip_circumference': upper_hip_circumference,
                'wide_hip_circumference': wide_hip_circumference,
                'calf_circumference': calf_circumference,
                'collarbone_to_belly_button_length': collarbone_to_belly_button_length,
                'waist_to_crotch_front_length': waist_to_crotch_front_length,
                'waist_to_crotch_back_length': waist_to_crotch_back_length,
                'inner_leg_length': inner_leg_length,
                'foot_length': foot_length,
                'foot_width': foot_width,
                'unit': 'metric'
            }
            
            # Create measurements using BodyMeasurements model
            measurements = BodyMeasurements(user_id=userid, **measurement_data)
            measurements.save()
            logger.info(f"create_account: Body measurements saved for userid={userid}")
        
        # Generate JWT token
        token = generate_token(userid, email)
        
        logger.info(f"create_account: EXIT - Account created successfully for userid={userid}")
        
        return success_response(
            data={
                'token': token,
                'user': user.to_dict()
            },
            message='Account created successfully',
            status_code=201
        )
        
    except ValidationError as e:
        logger.exception(f"create_account: EXIT - ValidationError: {str(e)}")
        return error_response_from_string(str(e), 400, 'VALIDATION_ERROR')
    except Exception as e:
        logger.exception(f"create_account: EXIT - Error: {str(e)}")
        return error_response_from_string(f'Server error: {str(e)}', 500)


@auth_bp.route('/login', methods=['POST'])
def login():
    """
    Login user and return JWT token
    Uses User model for authentication
    """
    logger.info("login: ENTRY")
    try:
        data = request.get_json() if request.is_json else request.form
        
        email = (data.get('email') or '').strip()
        password = data.get('password') or ''
        
        if not email or not password:
            logger.warning("login: Missing email or password")
            return error_response_from_string('Email and password are required', 400, 'VALIDATION_ERROR')
        
        # Get user by email using User model
        user = User.get_by_email(email)
        
        if not user or not user.is_active:
            logger.warning(f"login: User not found or inactive - email={email}")
            return error_response_from_string('Invalid email or password', 401, 'AUTHENTICATION_ERROR')
        
        # Check password using User model method
        if not user.check_password(password):
            logger.warning(f"login: Invalid password for email={email}")
            return error_response_from_string('Invalid email or password', 401, 'AUTHENTICATION_ERROR')
        
        # Generate JWT token
        token = generate_token(user.userid, user.email)
        
        logger.info(f"login: EXIT - Login successful for userid={user.userid}")
        
        return success_response(
            data={
                'token': token,
                'user': user.to_dict()
            },
            message='Login successful'
        )
        
    except Exception as e:
        logger.exception(f"login: EXIT - Error: {str(e)}")
        return error_response_from_string(f'Server error: {str(e)}', 500)



