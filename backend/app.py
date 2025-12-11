from flask import Flask, jsonify, request, Response, send_from_directory
import requests  # type: ignore
from flask_cors import CORS  # type: ignore
import os
import base64
from config import Config
from shared.database import db_manager, get_db_connection
from features.auth.service import generate_token
from shared.response import success_response, error_response, error_response_from_string
from shared.errors import ValidationError, AuthenticationError, DatabaseError, NotFoundError
from shared.validators import validate_email, validate_password, validate_required
from shared.middleware import require_auth, optional_auth
from shared.logger import logger

# Import blueprints
from features.auth.controller import auth_bp
from features.body_measurements.controller import body_measurements_bp
from features.tryon.controller import tryon_bp
from features.garments.controller import garments_bp
from features.fitting.controller import fitting_bp
from features.users.controller import users_bp
from features.wardrobe.controller import wardrobe_bp

app = Flask(__name__)
CORS(app, origins=Config.CORS_ORIGINS)

# Validate configuration
Config.validate()

# Serve images from local storage
@app.route('/images/<path:filename>')
def serve_image(filename):
    """Serve images from local storage directory"""
    try:
        from pathlib import Path
        images_dir = Path(Config.IMAGES_DIR)
        file_path = images_dir / filename
        
        # Security: Ensure file is within images directory
        if not str(file_path.resolve()).startswith(str(images_dir.resolve())):
            return jsonify({"error": "Invalid path"}), 403
        
        if file_path.exists():
            return send_from_directory(str(images_dir), filename)
        else:
            return jsonify({"error": "Image not found"}), 404
    except Exception as e:
        logger.exception(f"serve_image: Error serving image {filename}: {str(e)}")
        return jsonify({"error": "Failed to serve image"}), 500

# Register blueprints
app.register_blueprint(auth_bp)
app.register_blueprint(body_measurements_bp)
app.register_blueprint(tryon_bp)
app.register_blueprint(garments_bp)
app.register_blueprint(fitting_bp)
app.register_blueprint(users_bp)
app.register_blueprint(wardrobe_bp)

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



@app.route('/api/save-avatar', methods=['POST'])
@require_auth
def save_avatar():
    try:
        # Check if file and user_id are provided
        if 'avatar' not in request.files:
            return error_response_from_string('No avatar file provided', 400, 'VALIDATION_ERROR')
        
        # user_id is already set from JWT token via @require_auth decorator
        # No need to get from form or verify - decorator handles it
        
        avatar_file = request.files['avatar']
        
        # Validate file type
        if not avatar_file or not allowed_file(avatar_file.filename):
            return error_response_from_string(
                'Invalid file type. Please upload PNG, JPG, JPEG, or WEBP',
                400,
                'VALIDATION_ERROR'
            )
        
        # Read file as binary data
        avatar_data = avatar_file.read()
        
        # Validate file size (max 5MB)
        max_size = 5 * 1024 * 1024  # 5MB
        if len(avatar_data) > max_size:
            return error_response_from_string(
                'File too large. Maximum size is 5MB',
                400,
                'VALIDATION_ERROR'
            )
        
        # user_id is already set from JWT token via @require_auth decorator
        user_id = request.user_id
        
        # Always remove background using Gemini (Nano Banana) API
        # Per user requirement: Use Nano Banana to remove background and keep only user image
        try:
            from features.tryon.service import remove_background
            from PIL import Image
            from io import BytesIO
            
            logger.info(f"Removing background from avatar using Gemini API (Nano Banana) for user: {user_id}")
            avatar_data = remove_background(avatar_data)
            
            # Verify that background removal resulted in transparent image
            try:
                img = Image.open(BytesIO(avatar_data))
                original_mode = img.mode
                
                # Check if image has transparency (alpha channel)
                has_transparency = img.mode in ('RGBA', 'LA', 'P')
                
                if not has_transparency:
                    # If image is RGB (no transparency), background removal didn't work properly
                    logger.error(f"Avatar from Gemini is {original_mode} mode (no transparency). Background removal failed to create transparent image.")
                    return error_response_from_string(
                        'Background removal failed to create transparent image. Please try uploading again with a clearer photo.',
                        500,
                        'EXTERNAL_SERVICE_ERROR'
                    )
                
                # Convert to RGBA to ensure proper transparency support
                if img.mode == 'P':
                    # Palette mode - convert to RGBA to preserve transparency
                    img = img.convert('RGBA')
                elif img.mode == 'LA':
                    # Grayscale with alpha - convert to RGBA
                    img = img.convert('RGBA')
                # If already RGBA, keep as is
                
                # Save as PNG with transparency preserved (RGBA mode ensures alpha channel)
                output = BytesIO()
                # PIL automatically preserves alpha channel when saving RGBA images as PNG
                img.save(output, format='PNG')
                avatar_data = output.getvalue()
                
                logger.info(f"Avatar processed with transparency preserved, user: {user_id}, mode: RGBA")
            except Exception as img_check_error:
                logger.exception(f"Error processing avatar transparency: {str(img_check_error)}")
                return error_response_from_string(
                    'Failed to process avatar image. Please try uploading again.',
                    500,
                    'EXTERNAL_SERVICE_ERROR'
                )
            
        except Exception as e:
            logger.exception(f"Background removal error for user {user_id}: {str(e)}")
            # Fail fast - don't save avatar without background removal
            return error_response_from_string(
                f'Failed to remove background from avatar: {str(e)}',
                500,
                'EXTERNAL_SERVICE_ERROR'
            )
        
        logger.info(f"Saving avatar for user: {user_id}, size: {len(avatar_data)} bytes, bg_removed: True, transparent: True")
        
        # Use User model instead of direct SQL
        from shared.models.user import User
        user = User.get_by_id(user_id)
        
        if not user:
            return error_response_from_string('User not found', 404, 'NOT_FOUND')
        
        # Save avatar to disk storage for frontend URL access
        from shared.storage import get_storage_service
        import uuid
        avatar_filename = f"{user_id}_{uuid.uuid4().hex[:8]}.png"
        storage_path = f"avatars/{user_id}/{avatar_filename}"
        
        storage_service = get_storage_service()
        avatar_url = storage_service.upload_image(
            avatar_data,
            storage_path,
            content_type='image/png'
        )
        
        # Construct absolute URL for frontend
        # Get base URL from request (works for both localhost and production)
        base_url = request.url_root.rstrip('/')
        absolute_avatar_url = f"{base_url}{avatar_url}"
        
        # Also save to database for backward compatibility (get_avatar endpoint)
        user.avatar = avatar_data
        user.save()
        
        logger.info(f"Avatar saved successfully for user: {user_id}, URL: {absolute_avatar_url}")
        
        return success_response(
            data={
                'message': 'Avatar saved successfully',
                'background_removed': True,
                'avatar_url': absolute_avatar_url  # Return URL for frontend to use
            },
            message='Avatar saved successfully'
        )
        
    except Exception as e:
        logger.exception(f"save_avatar: EXIT - Error: {str(e)}")
        return error_response_from_string(f'Server error: {str(e)}', 500)

# API to get avatar blob
@app.route('/api/get-avatar', methods=['GET'])
@require_auth
def get_avatar():
    """
    Get authenticated user's avatar image
    Uses User model for data access
    user_id is extracted from JWT token by @require_auth decorator
    """
    # user_id comes from JWT token via @require_auth decorator
    user_id = request.user_id
    logger.info(f"get_avatar: ENTRY - user_id={user_id} (from JWT)")
    
    try:
        # Use User model instead of direct SQL
        from shared.models.user import User
        user = User.get_by_id(user_id)
        
        if not user or not user.avatar:
            return error_response_from_string('Avatar not found', 404, 'NOT_FOUND')
        
        # Try to find avatar URL from disk storage first
        # Look for avatar files in avatars/{user_id}/ directory
        from pathlib import Path
        from config import Config
        images_dir = Path(Config.IMAGES_DIR)
        avatar_dir = images_dir / 'avatars' / user_id
        
        avatar_url = None
        if avatar_dir.exists():
            # Find most recent avatar file
            avatar_files = sorted(avatar_dir.glob('*.png'), key=lambda p: p.stat().st_mtime, reverse=True)
            if avatar_files:
                # Construct URL
                relative_path = f"avatars/{user_id}/{avatar_files[0].name}"
                base_url = request.url_root.rstrip('/')
                avatar_url = f"{base_url}/images/{relative_path}"
        
        # If no disk file found, return blob (backward compatibility)
        # But also include URL if available
        if avatar_url:
            logger.info(f"get_avatar: EXIT - Avatar URL retrieved for user_id={user_id}: {avatar_url}")
            return success_response(data={'avatar_url': avatar_url})
        else:
            # Fallback: return blob if no disk file (backward compatibility)
            logger.info(f"get_avatar: EXIT - Avatar blob retrieved for user_id={user_id} (no disk file)")
            return Response(
                user.avatar,
                mimetype='image/png',
                headers={
                    'Content-Disposition': f'inline; filename=avatar_{user_id}.png',
                    'Cache-Control': 'max-age=300'  # Cache for 5 minutes
                }
            )
        
    except Exception as e:
        logger.exception(f"get_avatar: EXIT - Error: {str(e)}")
        return error_response_from_string(f'Server error: {str(e)}', 500)

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


if __name__ == "__main__":
    port = int(os.environ.get('PORT', 8000))
    app.run(debug=True, host="0.0.0.0", port=port)