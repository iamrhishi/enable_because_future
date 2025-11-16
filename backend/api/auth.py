"""
Authentication API endpoints
"""

from flask import Blueprint, request, jsonify
from services.auth import generate_token
from services.database import db_manager
from werkzeug.security import generate_password_hash, check_password_hash
from utils.response import success_response, error_response_from_string
from utils.validators import validate_email, validate_password
from utils.errors import ValidationError, AuthenticationError
from config import Config
from utils.logger import logger
import uuid

auth_bp = Blueprint('auth', __name__, url_prefix='/api')


@auth_bp.route('/create-account', methods=['POST'])
def create_account():
    """Create a new user account"""
    try:
        data = request.get_json() if request.is_json else request.form
        
        email = validate_email(data.get('email', '').strip())
        password = validate_password(data.get('password', ''))
        first_name = data.get('first_name', '').strip()
        last_name = data.get('last_name', '').strip()
        age = data.get('age')
        gender = data.get('gender', '').strip()
        weight = data.get('weight')
        height = data.get('height')
        physique = data.get('physique', '').strip()
        
        # Validate ranges
        if age and not (13 <= int(age) <= 100):
            return error_response_from_string('Age must be between 13 and 100', 400, 'VALIDATION_ERROR')
        
        if weight and not (30 <= float(weight) <= 300):
            return error_response_from_string('Weight must be between 30 and 300 kg', 400, 'VALIDATION_ERROR')
        
        if height and not (100 <= float(height) <= 250):
            return error_response_from_string('Height must be between 100 and 250 cm', 400, 'VALIDATION_ERROR')
        
        # Validate enum values
        valid_genders = ['male', 'female', 'other', 'prefer-not-to-say']
        valid_physiques = ['slim', 'muscular', 'thick']
        
        if gender and gender not in valid_genders:
            return error_response_from_string('Invalid gender selection', 400, 'VALIDATION_ERROR')
        
        if physique and physique not in valid_physiques:
            return error_response_from_string('Invalid physique selection', 400, 'VALIDATION_ERROR')
        
        # Generate unique userid
        userid = str(uuid.uuid4())[:8]
        
        # Hash password
        hashed_password = generate_password_hash(password)
        
        # Check if email already exists
        existing = db_manager.execute_query(
            "SELECT id FROM users WHERE email = ?",
            (email,),
            fetch_one=True
        )
        
        if existing:
            return error_response_from_string('Email already registered', 409, 'EMAIL_EXISTS')
        
        # Insert user data
        user_id = db_manager.get_lastrowid(
            """INSERT INTO users (userid, email, first_name, last_name, password, age, gender, weight, height, physique, avatar)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (userid, email, first_name, last_name, hashed_password, age, gender, weight, height, physique, None)
        )
        
        # Generate JWT token
        token = generate_token(userid, email)
        
        return success_response(
            data={
                'token': token,
                'user': {
                    'id': user_id,
                    'userid': userid,
                    'email': email,
                    'first_name': first_name,
                    'last_name': last_name,
                    'age': age,
                    'gender': gender,
                    'weight': weight,
                    'height': height,
                    'physique': physique
                }
            },
            message='Account created successfully',
            status_code=201
        )
        
    except ValidationError as e:
        return error_response_from_string(str(e), 400, 'VALIDATION_ERROR')
    except Exception as e:
        logger.error(f"Error creating account: {str(e)}")
        return error_response_from_string(f'Server error: {str(e)}', 500)


@auth_bp.route('/login', methods=['POST'])
def login():
    """Login user and return JWT token"""
    try:
        data = request.get_json() if request.is_json else request.form
        
        email = data.get('email', '').strip()
        password = data.get('password', '')
        
        if not email or not password:
            return error_response_from_string('Email and password are required', 400, 'VALIDATION_ERROR')
        
        # Get user by email
        user = db_manager.execute_query(
            """SELECT id, userid, email, first_name, last_name, password, age, gender, 
                      weight, height, physique, created_at, is_active 
               FROM users WHERE email = ? AND is_active = TRUE""",
            (email,),
            fetch_one=True
        )
        
        if not user or not check_password_hash(user['password'], password):
            return error_response_from_string('Invalid email or password', 401, 'AUTHENTICATION_ERROR')
        
        # Generate JWT token
        token = generate_token(user['userid'], user['email'])
        
        # Remove password from response
        user_dict = dict(user)
        del user_dict['password']
        
        return success_response(
            data={
                'token': token,
                'user': user_dict
            },
            message='Login successful'
        )
        
    except Exception as e:
        logger.error(f"Error during login: {str(e)}")
        return error_response_from_string(f'Server error: {str(e)}', 500)


@auth_bp.route('/oauth/google', methods=['POST'])
def google_oauth():
    """Google OAuth sign-in/sign-up"""
    try:
        from google.auth.transport import requests as google_requests
        from google.oauth2 import id_token
        
        data = request.get_json()
        id_token_str = data.get('id_token')
        
        if not id_token_str:
            return error_response_from_string('id_token is required', 400, 'VALIDATION_ERROR')
        
        # Verify Google token
        try:
            idinfo = id_token.verify_oauth2_token(
                id_token_str, 
                google_requests.Request(), 
                Config.GOOGLE_CLIENT_ID
            )
        except ValueError:
            return error_response_from_string('Invalid Google token', 401, 'AUTHENTICATION_ERROR')
        
        # Extract user info
        email = idinfo.get('email')
        name = idinfo.get('name', '')
        picture = idinfo.get('picture')
        google_id = idinfo.get('sub')
        
        if not email:
            return error_response_from_string('Email not provided by Google', 400, 'VALIDATION_ERROR')
        
        # Check if user exists
        user = db_manager.execute_query(
            "SELECT * FROM users WHERE email = ?",
            (email,),
            fetch_one=True
        )
        
        if user:
            # Existing user - login
            userid = user['userid']
        else:
            # New user - create account
            userid = str(uuid.uuid4())[:8]
            name_parts = name.split(' ', 1) if name else ['', '']
            
            user_id = db_manager.get_lastrowid(
                """INSERT INTO users (userid, email, first_name, last_name, password, is_active)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (userid, email, name_parts[0], name_parts[1] if len(name_parts) > 1 else '', '', True)
            )
            
            user = db_manager.execute_query(
                "SELECT * FROM users WHERE userid = ?",
                (userid,),
                fetch_one=True
            )
        
        # Generate JWT token
        token = generate_token(userid, email)
        
        # Remove password from response
        user_dict = dict(user)
        if 'password' in user_dict:
            del user_dict['password']
        
        return success_response(
            data={
                'token': token,
                'user': user_dict,
                'picture': picture
            },
            message='Google sign-in successful'
        )
        
    except ImportError:
        return error_response_from_string('Google OAuth not configured. Install google-auth library.', 500, 'CONFIG_ERROR')
    except Exception as e:
        logger.error(f"Error during Google OAuth: {str(e)}")
        return error_response_from_string(f'Server error: {str(e)}', 500)

