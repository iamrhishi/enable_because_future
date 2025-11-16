from flask import Flask, jsonify, request, Response, send_file
import requests  # type: ignore
from requests.auth import HTTPBasicAuth  # type: ignore
from flask_cors import CORS  # type: ignore
import os
import io
# import numpy as np  # Not currently used
# import cv2  # Commented out temporarily due to installation issue
from io import BytesIO
from werkzeug.utils import secure_filename
import base64
from bs4 import BeautifulSoup  # type: ignore
from urllib.parse import urlparse
import hashlib
import uuid
from werkzeug.security import generate_password_hash, check_password_hash
from config import Config
from services.database import db_manager, get_db_connection
from services.auth import generate_token
from utils.response import success_response, error_response, error_response_from_string
from utils.errors import ValidationError, AuthenticationError, DatabaseError, NotFoundError
from utils.validators import validate_email, validate_password, validate_required
from utils.middleware import require_auth, optional_auth
from utils.logger import logger

# Import blueprints
from api.auth import auth_bp
from api.body_measurements import body_measurements_bp
from api.tryon import tryon_bp
from api.garments import garments_bp
from api.fitting import fitting_bp

app = Flask(__name__)
CORS(app, origins=Config.CORS_ORIGINS)

# Validate configuration
Config.validate()

# Register blueprints
app.register_blueprint(auth_bp)
app.register_blueprint(body_measurements_bp)
app.register_blueprint(tryon_bp)
app.register_blueprint(garments_bp)
app.register_blueprint(fitting_bp)

# Global error handler
@app.errorhandler(Exception)
def handle_error(e):
    """Global error handler"""
    logger.error(f"Unhandled error: {str(e)}", exc_info=True)
    return error_response_from_string(f'Internal server error: {str(e)}', 500, 'INTERNAL_ERROR')

# Health check endpoint
@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    try:
        # Check database connection
        db_manager.execute_query("SELECT 1", fetch_one=True)
        return success_response(data={'status': 'healthy', 'database': 'connected'})
    except Exception as e:
        return error_response_from_string(f'Unhealthy: {str(e)}', 503, 'UNHEALTHY')

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in Config.ALLOWED_EXTENSIONS


# Proxy endpoint for background removal
@app.route('/api/remove-bg', methods=['POST'])
def remove_bg():
    api_url = Config.BG_SERVICE_URL
    api_username = Config.BG_SERVICE_USERNAME
    api_password = Config.BG_SERVICE_PASSWORD
    if 'file' not in request.files:
        return {'error': 'No file uploaded'}, 400
    file = request.files['file']
    files = {'file': (file.filename, file.stream, file.mimetype)}
    try:
        resp = requests.post(
            api_url,
            files=files,
            auth=(api_username, api_password),
            headers={"Accept":"image/png"},
            timeout=60
        )
        if resp.status_code == 200:
            return Response(resp.content, mimetype='image/png')
        else:
            return resp.json(), resp.status_code
    except Exception as e:
        return {'error': str(e)}, 500


# --- Try-On API Proxy (Legacy - use /api/tryon from blueprint) ---
@app.route('/api/tryon', methods=['POST'])
@require_auth
def tryon_legacy():
    api_url = Config.MIXER_SERVICE_URL
    api_username = Config.MIXER_SERVICE_USERNAME
    api_password = Config.MIXER_SERVICE_PASSWORD 

    try:
        # Get files and form data
        person_image = request.files.get('person_image')
        cloth_image = request.files.get('cloth_image')
        cloth_type = request.form.get('cloth_type')
        num_inference_steps = request.form.get('num_inference_steps')

        if not person_image or not cloth_image or not cloth_type:
            return jsonify({"message": "Missing required fields", "code": "INVALID_INPUT", "statusCode": 400}), 400

        files = {
            'person_image': (person_image.filename, person_image.stream, person_image.mimetype),
            'cloth_image': (cloth_image.filename, cloth_image.stream, cloth_image.mimetype)
        }

        data = {'cloth_type': cloth_type}
        
        if num_inference_steps:
            data['num_inference_steps'] = num_inference_steps        
        
        logger.debug(f"Try-on request data: {data}")

        # Forward to the actual try-on API
        headers = {"Accept":"image/png"}
        
        resp = requests.post(api_url, files=files, auth=(api_username, api_password), data=data, headers=headers, timeout=120)

        if resp.status_code == 200 and resp.headers.get('Content-Type', '').startswith('image/'):
            return send_file(BytesIO(resp.content), mimetype=resp.headers['Content-Type'])
        else:
            logger.error(f"Try-on API error: {resp.text}")
            # Try to return JSON if possible, else return raw text
            try:
                return jsonify(resp.json()), resp.status_code
            except Exception:
                return Response(resp.text, status=resp.status_code, mimetype='text/plain')

    except Exception as e:
        return jsonify({"message": str(e), "code": "SERVER_ERROR", "statusCode": 500}), 500

@app.route('/api/message')
def get_message():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT message FROM hello LIMIT 1;')
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        if result:
            return jsonify({'message': result[0]})
        else:
            return jsonify({'message': 'No message found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/save-clothing', methods=['POST'])
def save_clothing():
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        save_path = os.path.join(Config.WARDROBE_FOLDER, filename)
        os.makedirs(Config.WARDROBE_FOLDER, exist_ok=True)
        file.save(save_path)
        return jsonify({"success": True, "filename": filename}), 200
    else:
        return jsonify({"error": "Invalid file type"}), 400

@app.route('/api/wardrobe-images', methods=['GET'])
def get_wardrobe_images():
    wardrobe_folder = Config.WARDROBE_FOLDER
    try:
        files = [
            f for f in os.listdir(wardrobe_folder)
            if os.path.isfile(os.path.join(wardrobe_folder, f))
               and f.lower().endswith(('.png', '.jpg', '.jpeg', '.webp'))
        ]
        return jsonify({"images": files})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
@app.route('/api/create-account', methods=['POST'])
def create_account():
    try:
        # Get form data
        data = request.get_json() if request.is_json else request.form
        
        # Extract required fields
        email = data.get('email', '').strip()
        first_name = data.get('firstname', '').strip()
        last_name = data.get('lastname', '').strip()
        password = data.get('password', '')
        age = data.get('age', '')
        gender = data.get('gender', '')
        weight = data.get('weight', '')
        height = data.get('height', '')
        physique = data.get('physique', '')
        
        # Validate required fields
        if not all([email, first_name, last_name, password, age, gender, weight, height, physique]):
            return jsonify({
                'success': False,
                'error': 'All fields are required'
            }), 400
        
        # Validate email format
        import re
        email_regex = r'^[^\s@]+@[^\s@]+\.[^\s@]+$'
        if not re.match(email_regex, email):
            return jsonify({
                'success': False,
                'error': 'Invalid email format'
            }), 400
        
        # Validate password length
        if len(password) < 6:
            return jsonify({
                'success': False,
                'error': 'Password must be at least 6 characters long'
            }), 400
        
        # Validate numeric fields
        try:
            age = int(age)
            weight = float(weight)
            height = float(height)
        except ValueError:
            return jsonify({
                'success': False,
                'error': 'Age, weight, and height must be valid numbers'
            }), 400
        
        # Validate ranges
        if not (13 <= age <= 100):
            return jsonify({
                'success': False,
                'error': 'Age must be between 13 and 100'
            }), 400
        
        if not (30 <= weight <= 300):
            return jsonify({
                'success': False,
                'error': 'Weight must be between 30 and 300 kg'
            }), 400
        
        if not (100 <= height <= 250):
            return jsonify({
                'success': False,
                'error': 'Height must be between 100 and 250 cm'
            }), 400
        
        # Validate enum values
        valid_genders = ['male', 'female', 'other', 'prefer-not-to-say']
        valid_physiques = ['slim', 'muscular', 'thick']
        
        if gender not in valid_genders:
            return jsonify({
                'success': False,
                'error': 'Invalid gender selection'
            }), 400
        
        if physique not in valid_physiques:
            return jsonify({
                'success': False,
                'error': 'Invalid physique selection'
            }), 400
        
        # Generate unique userid
        userid = str(uuid.uuid4())[:8]  # 8-character unique ID
        
        # Hash password
        hashed_password = generate_password_hash(password)
        
        # Connect to database
        connection = get_db_connection()
        cursor = connection.cursor()
        
        # Check if email already exists
        cursor.execute("SELECT id FROM users WHERE email = ?", (email,))
        if cursor.fetchone():
            return jsonify({
                'success': False,
                'error': 'Email already registered'
            }), 409
        
        # Insert user data (avatar left as NULL)
        insert_query = """
        INSERT INTO users (userid, email, first_name, last_name, password, age, gender, weight, height, physique, avatar)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        
        cursor.execute(insert_query, (
            userid, email, first_name, last_name, hashed_password,
            age, gender, weight, height, physique, None  # avatar is NULL
        ))
        
        connection.commit()
        user_id = cursor.lastrowid
        
        cursor.close()
        connection.close()
        
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
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Server error: {str(e)}'
        }), 500

@app.route('/api/login', methods=['POST'])
def login_legacy():
        try:
            # Get form data
            data = request.get_json() if request.is_json else request.form
            
            email = data.get('email', '').strip()
            password = data.get('password', '')
            
            if not email or not password:
                return jsonify({
                    'success': False,
                    'error': 'Email and password are required'
                }), 400
            
            # Connect to database
            connection = get_db_connection()
            cursor = connection.cursor()
            
            # Get user by email
            cursor.execute("""
                SELECT id, userid, email, first_name, last_name, password, age, gender, 
                    weight, height, physique, created_at, is_active 
                FROM users WHERE email = ? AND is_active = TRUE
            """, (email,))
            
            user = cursor.fetchone()
            
            if not user or not check_password_hash(user['password'], password):
                return jsonify({
                    'success': False,
                    'error': 'Invalid email or password'
                }), 401
            
            # Generate JWT token
            token = generate_token(user['userid'], user['email'])
            
            # Remove password from response
            user_dict = dict(user)
            del user_dict['password']
            
            cursor.close()
            connection.close()
            
            return success_response(
                data={
                    'token': token,
                    'user': user_dict
                },
                message='Login successful'
            )
            
        except Exception as e:
            return error_response_from_string(f'Server error: {str(e)}', 500)

@app.route('/api/save-avatar', methods=['POST'])
@require_auth
def save_avatar():
    try:
        # Check if file and user_id are provided
        if 'avatar' not in request.files:
            return jsonify({
                'success': False,
                'error': 'No avatar file provided'
            }), 400
        
        user_id = request.form.get('user_id') or request.user_id
        if not user_id:
            return error_response_from_string('User ID is required', 400, 'VALIDATION_ERROR')
        
        # Verify user owns this avatar
        if user_id != request.user_id:
            return error_response_from_string('Not authorized', 403, 'AUTHORIZATION_ERROR')
        
        avatar_file = request.files['avatar']
        
        # Validate file type
        if not avatar_file or not allowed_file(avatar_file.filename):
            return jsonify({
                'success': False,
                'error': 'Invalid file type. Please upload PNG, JPG, JPEG, or WEBP'
            }), 400
        
        # Read file as binary data
        avatar_data = avatar_file.read()
        
        # Validate file size (max 5MB)
        max_size = 5 * 1024 * 1024  # 5MB
        if len(avatar_data) > max_size:
            return jsonify({
                'success': False,
                'error': 'File too large. Maximum size is 5MB'
            }), 400
        
        # Optional: Remove background if requested
        # Per context.md: Avatar should be realistic digital twin, background removal available
        remove_background = request.form.get('remove_background', 'false').lower() == 'true'
        if remove_background:
            try:
                files = {'file': ('avatar.png', BytesIO(avatar_data), 'image/png')}
                bg_response = requests.post(
                    Config.BG_SERVICE_URL,
                    files=files,
                    auth=(Config.BG_SERVICE_USERNAME, Config.BG_SERVICE_PASSWORD),
                    headers={"Accept": "image/png"},
                    timeout=30
                )
                if bg_response.status_code == 200:
                    avatar_data = bg_response.content
                    logger.info(f"Background removed from avatar for user: {user_id}")
                else:
                    logger.warning(f"Background removal failed for user {user_id}, saving original image")
            except Exception as e:
                logger.warning(f"Background removal error for user {user_id}: {str(e)}, saving original image")
        
        logger.info(f"Saving avatar for user: {user_id}, size: {len(avatar_data)} bytes, bg_removed: {remove_background}")
        
        # Connect to database
        connection = get_db_connection()
        cursor = connection.cursor()
        
        # Check if user exists
        cursor.execute("SELECT id FROM users WHERE userid = ?", (user_id,))
        user = cursor.fetchone()
        
        if not user:
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'error': 'User not found'
            }), 404
        
        # Update user's avatar
        update_query = "UPDATE users SET avatar = ? WHERE userid = ?"
        cursor.execute(update_query, (avatar_data, user_id))
        
        connection.commit()
        cursor.close()
        connection.close()
        
        logger.info(f"Avatar saved successfully for user: {user_id}")
        
        return jsonify({
            'success': True,
            'message': 'Avatar saved successfully',
            'background_removed': remove_background
        }), 200
        
    except Exception as e:
        logger.error(f"Server error: {e}")
        return jsonify({
            'success': False,
            'error': f'Server error: {str(e)}'
        }), 500

# API to get avatar blob
@app.route('/api/get-avatar/<user_id>', methods=['GET'])
@require_auth
def get_avatar(user_id):
    try:
        # Connect to database
        connection = get_db_connection()
        cursor = connection.cursor()
        
        # Get user's avatar
        cursor.execute("SELECT avatar FROM users WHERE userid = ?", (user_id,))
        result = cursor.fetchone()
        
        cursor.close()
        connection.close()
        
        if not result or not result[0]:
            return jsonify({
                'success': False,
                'error': 'Avatar not found'
            }), 404
        
        avatar_data = result[0]
        
        # Return the image as binary response
        return Response(
            avatar_data,
            mimetype='image/png',
            headers={
                'Content-Disposition': f'inline; filename=avatar_{user_id}.png',
                'Cache-Control': 'max-age=300'  # Cache for 5 minutes
            }
        )
        
    except Exception as e:
        logger.error(f"Server error: {e}")
        return jsonify({
            'success': False,
            'error': f'Server error: {str(e)}'
        }), 500

# API to update avatar (alternative endpoint)
@app.route('/api/update-avatar', methods=['PUT'])
@require_auth
def update_avatar():
    try:
        # Get JSON data with base64 encoded image
        data = request.get_json()
        
        if not data or 'user_id' not in data or 'avatar_data' not in data:
            return jsonify({
                'success': False,
                'error': 'User ID and avatar data are required'
            }), 400
        
        user_id = data.get('user_id')
        avatar_base64 = data.get('avatar_data')
        
        # Remove data URL prefix if present (e.g., "data:image/png;base64,")
        if avatar_base64.startswith('data:'):
            avatar_base64 = avatar_base64.split(',')[1]
        
        # Decode base64 to binary
        try:
            avatar_data = base64.b64decode(avatar_base64)
        except Exception as e:
            return jsonify({
                'success': False,
                'error': 'Invalid base64 data'
            }), 400
        
        # Validate file size (max 5MB)
        max_size = 5 * 1024 * 1024  # 5MB
        if len(avatar_data) > max_size:
            return jsonify({
                'success': False,
                'error': 'File too large. Maximum size is 5MB'
            }), 400
        
        logger.info(f"Updating avatar for user: {user_id}, size: {len(avatar_data)} bytes")
        
        # Connect to database
        connection = get_db_connection()
        cursor = connection.cursor()
        
        # Check if user exists
        cursor.execute("SELECT id FROM users WHERE userid = ?", (user_id,))
        user = cursor.fetchone()
        
        if not user:
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'error': 'User not found'
            }), 404
        
        # Update user's avatar
        update_query = "UPDATE users SET avatar = ? WHERE userid = ?"
        cursor.execute(update_query, (avatar_data, user_id))
        
        connection.commit()
        cursor.close()
        connection.close()
        
        logger.info(f"Avatar updated successfully for user: {user_id}")
        
        return jsonify({
            'success': True,
            'message': 'Avatar updated successfully'
        }), 200
        
    except Exception as e:
        logger.error(f"Database error: {e}")
        return jsonify({
            'success': False,
            'error': f'Database error: {str(e)}'
        }), 500
        
    except Exception as e:
        logger.error(f"Server error: {e}")
        return jsonify({
            'success': False,
            'error': f'Server error: {str(e)}'
        }), 500

# API to get user data
@app.route('/api/get-user-data/<user_id>', methods=['GET'])
@require_auth
def get_user_data(user_id):
    try:
        logger.info(f"Fetching user data for user: {user_id}")
        
        # Connect to database
        connection = get_db_connection()
        cursor = connection.cursor()
        
        # Get user data (excluding password and avatar for security/performance)
        cursor.execute("""
            SELECT id, userid, email, first_name, last_name, age, gender, 
                   weight, height, physique, created_at, updated_at, is_active
            FROM users WHERE userid = ?
        """, (user_id,))
        
        user = cursor.fetchone()
        
        cursor.close()
        connection.close()
        
        if not user:
            return jsonify({
                'success': False,
                'error': 'User not found'
            }), 404
        
        # Convert datetime objects to strings for JSON serialization
        if user['created_at']:
            user['created_at'] = user['created_at'].isoformat()
        if user['updated_at']:
            user['updated_at'] = user['updated_at'].isoformat()
        
        logger.info(f"User data retrieved successfully for: {user_id}")
        
        return jsonify({
            'success': True,
            'user_data': user
        }), 200
        
    except Exception as e:
        logger.error(f"Server error: {e}")
        return jsonify({
            'success': False,
            'error': f'Server error: {str(e)}'
        }), 500

# API to get user data by email (alternative endpoint)
@app.route('/api/get-user-data-by-email/<email>', methods=['GET'])
def get_user_data_by_email(email):
    try:
        logger.info(f"Fetching user data for email: {email}")
        
        # Connect to database
        connection = get_db_connection()
        cursor = connection.cursor()
        
        # Get user data (excluding password and avatar)
        cursor.execute("""
            SELECT id, userid, email, first_name, last_name, age, gender, 
                   weight, height, physique, created_at, updated_at, is_active
            FROM users WHERE email = ?
        """, (email,))
        
        user = cursor.fetchone()
        
        cursor.close()
        connection.close()
        
        if not user:
            return jsonify({
                'success': False,
                'error': 'User not found'
            }), 404
        
        # Convert datetime objects to strings for JSON serialization
        if user['created_at']:
            user['created_at'] = user['created_at'].isoformat()
        if user['updated_at']:
            user['updated_at'] = user['updated_at'].isoformat()
        
        logger.info(f"User data retrieved successfully for email: {email}")
        
        return jsonify({
            'success': True,
            'user_data': user
        }), 200
        
    except Exception as e:
        logger.error(f"Server error: {e}")
        return jsonify({
            'success': False,
            'error': f'Server error: {str(e)}'
        }), 500

# API to update user data
@app.route('/api/update-user-data/<user_id>', methods=['PUT'])
@require_auth
def update_user_data(user_id):
    try:
        # Verify user owns this data
        if user_id != request.user_id:
            return error_response_from_string('Not authorized', 403, 'AUTHORIZATION_ERROR')
        
        logger.info(f"Updating user data for user: {user_id}")
        
        # Get JSON data
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'error': 'No data provided'
            }), 400
        
        # Connect to database
        connection = get_db_connection()
        cursor = connection.cursor()
        
        # Check if user exists
        cursor.execute("SELECT id FROM users WHERE userid = ?", (user_id,))
        user = cursor.fetchone()
        
        if not user:
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'error': 'User not found'
            }), 404
        
        # Build update query dynamically based on provided fields
        allowed_fields = ['first_name', 'last_name', 'age', 'gender', 'weight', 'height', 'physique']
        update_fields = []
        update_values = []
        
        for field in allowed_fields:
            if field in data:
                update_fields.append(f"{field} = ?")
                
                # Validate and convert data types
                if field in ['age']:
                    try:
                        update_values.append(int(data[field]))
                    except ValueError:
                        return jsonify({
                            'success': False,
                            'error': f'Invalid {field}: must be a number'
                        }), 400
                elif field in ['weight', 'height']:
                    try:
                        update_values.append(float(data[field]))
                    except ValueError:
                        return jsonify({
                            'success': False,
                            'error': f'Invalid {field}: must be a number'
                        }), 400
                else:
                    update_values.append(data[field])
        
        if not update_fields:
            return jsonify({
                'success': False,
                'error': 'No valid fields to update'
            }), 400
        
        # Add updated_at timestamp
        update_fields.append("updated_at = CURRENT_TIMESTAMP")
        
        # Build and execute update query
        update_query = f"UPDATE users SET {', '.join(update_fields)} WHERE userid = ?"
        update_values.append(user_id)
        
        cursor.execute(update_query, update_values)
        connection.commit()
        
        cursor.close()
        connection.close()
        
        logger.info(f"User data updated successfully for: {user_id}")
        
        return jsonify({
            'success': True,
            'message': 'User data updated successfully'
        }), 200
        
    except Exception as e:
        logger.error(f"Server error: {e}")
        return jsonify({
            'success': False,
            'error': f'Server error: {str(e)}'
        }), 500

# ===== WARDROBE ENDPOINTS =====

@app.route('/api/wardrobe/save', methods=['POST'])
def save_to_wardrobe():
    """Save a garment to user's wardrobe"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'error': 'No data provided'
            }), 400
        
        # Extract required fields
        user_id = data.get('user_id')
        garment_id = data.get('garment_id')
        garment_image = data.get('garment_image')  # Base64 string
        garment_type = data.get('garment_type')
        garment_url = data.get('garment_url')
        
        if not all([user_id, garment_id, garment_image, garment_type]):
            return jsonify({
                'success': False,
                'error': 'Missing required fields: user_id, garment_id, garment_image, garment_type'
            }), 400
        
        # Convert base64 to binary for storage
        try:
            # Remove data URL prefix if present
            if garment_image.startswith('data:'):
                garment_image = garment_image.split(',')[1]
            
            image_binary = base64.b64decode(garment_image)
        except Exception as e:
            return jsonify({
                'success': False,
                'error': f'Invalid image data: {str(e)}'
            }), 400
        
        # Connect to database
        connection = get_db_connection()
        cursor = connection.cursor()
        
        # Insert or replace garment in wardrobe (SQLite uses INSERT OR REPLACE)
        insert_query = """
            INSERT OR REPLACE INTO wardrobe 
            (user_id, garment_id, garment_image, garment_type, garment_url, 
             category, garment_category_type, brand, color, is_external, title, date_added)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """
        
        cursor.execute(insert_query, (
            user_id, garment_id, image_binary, garment_type, garment_url,
            category, garment_category_type, brand, color, is_external, title
        ))
        connection.commit()
        
        cursor.close()
        connection.close()
        
        logger.info(f"Garment saved to wardrobe: {garment_id} for user {user_id}")
        
        return jsonify({
            'success': True,
            'message': 'Garment saved to wardrobe successfully',
            'garment_id': garment_id
        }), 200
        
    except Exception as e:
        logger.error(f"Server error: {e}")
        return jsonify({
            'success': False,
            'error': f'Server error: {str(e)}'
        }), 500

@app.route('/api/wardrobe/user/<user_id>', methods=['GET'])
@require_auth
def get_user_wardrobe(user_id):
    """Get all wardrobe items for a specific user"""
    try:
        # Connect to database
        connection = get_db_connection()
        cursor = connection.cursor()
        
        # Verify user owns this wardrobe
        if user_id != request.user_id:
            return error_response_from_string('Not authorized', 403, 'AUTHORIZATION_ERROR')
        
        # Get query parameters for filtering
        category = request.args.get('category')
        search = request.args.get('search', '').strip().lower()
        
        # Build query with filters
        select_query = """
            SELECT 
                id,
                user_id,
                garment_id,
                garment_image,
                garment_type,
                garment_url,
                category,
                garment_category_type,
                brand,
                color,
                is_external,
                title,
                date_added
            FROM wardrobe 
            WHERE user_id = ?
        """
        params = [user_id]
        
        if category:
            select_query += " AND category = ?"
            params.append(category)
        
        if search:
            select_query += " AND (garment_category_type LIKE ? OR brand LIKE ? OR color LIKE ? OR title LIKE ?)"
            search_pattern = f"%{search}%"
            params.extend([search_pattern, search_pattern, search_pattern, search_pattern])
        
        select_query += " ORDER BY date_added DESC"
        
        cursor.execute(select_query, tuple(params))
        wardrobe_items = cursor.fetchall()
        
        # Convert binary image data to base64 for JSON response
        for item in wardrobe_items:
            if item['garment_image']:
                # Convert binary to base64 string
                image_b64 = base64.b64encode(item['garment_image']).decode('utf-8')
                item['garment_image'] = f"data:image/png;base64,{image_b64}"
            
            # Convert datetime to string for JSON serialization
            if item['date_added']:
                item['date_added'] = item['date_added'].isoformat()
        
        cursor.close()
        connection.close()
        
        logger.info(f"Retrieved {len(wardrobe_items)} wardrobe items for user {user_id}")
        
        return jsonify(wardrobe_items), 200
        
    except Exception as e:
        logger.error(f"Server error: {e}")
        return jsonify({
            'success': False,
            'error': f'Server error: {str(e)}'
        }), 500

@app.route('/api/wardrobe/remove', methods=['DELETE'])
@require_auth
def remove_from_wardrobe():
    """Remove a garment from user's wardrobe"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'error': 'No data provided'
            }), 400
        
        user_id = data.get('user_id')
        garment_id = data.get('garment_id')
        
        # Verify user owns this wardrobe item
        if user_id != request.user_id:
            return error_response_from_string('Not authorized', 403, 'AUTHORIZATION_ERROR')
        
        if not all([user_id, garment_id]):
            return error_response_from_string('Missing required fields: user_id, garment_id', 400, 'VALIDATION_ERROR')
        
        # Connect to database
        connection = get_db_connection()
        cursor = connection.cursor()
        
        # Delete garment from wardrobe
        delete_query = "DELETE FROM wardrobe WHERE user_id = ? AND garment_id = ?"
        cursor.execute(delete_query, (user_id, garment_id))
        
        if cursor.rowcount == 0:
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'error': 'Garment not found in wardrobe'
            }), 404
        
        connection.commit()
        cursor.close()
        connection.close()
        
        logger.info(f"Garment removed from wardrobe: {garment_id} for user {user_id}")
        
        return jsonify({
            'success': True,
            'message': 'Garment removed from wardrobe successfully'
        }), 200
        
    except Exception as e:
        logger.error(f"Server error: {e}")
        return jsonify({
            'success': False,
            'error': f'Server error: {str(e)}'
        }), 500

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)