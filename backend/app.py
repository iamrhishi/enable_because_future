from flask import Flask, jsonify, request, Response, send_from_directory, redirect
from werkzeug.exceptions import BadRequest, HTTPException
import requests  # type: ignore
from flask_cors import CORS  # type: ignore
import os
import base64
from config import Config
from shared.database import db_manager
from features.auth.service import generate_token
from shared.response import success_response, error_response, error_response_from_string, server_error_response
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
from features.fit_analysis.controller import fit_analysis_bp
from features.sizing.controller import sizing_bp
from features.garment_discovery.controller import garment_discovery_bp

app = Flask(__name__)
CORS(app, origins=Config.CORS_ORIGINS)

from shared.rate_limit import limiter
limiter.init_app(app)

# Validate configuration
Config.validate()

# Serve images from local storage
@app.route('/images/<path:filename>')
def serve_image(filename):
    """Serve images - redirects to a fresh signed URL when GCS-backed, otherwise local disk"""
    try:
        if Config.GCS_BUCKET_NAME:
            from shared.storage import get_storage_service
            storage_service = get_storage_service()
            try:
                signed_url = storage_service.get_signed_url(filename)
            except Exception:
                return jsonify({"error": "Image not found"}), 404
            return redirect(signed_url)

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

# Serve avatars by userid (looks up actual filename from database)
@app.route('/api/avatar/<userid>')
def get_user_avatar_file(userid):
    """
    Get avatar file for a user by userid
    Looks up the actual avatar path from database and serves the file
    
    Args:
        userid: User ID to fetch avatar for
        
    Returns:
        Avatar image file or 404 if not found
    """
    try:
        from shared.models.user import User
        from pathlib import Path
        
        logger.info(f"get_user_avatar_file: ENTRY - userid={userid}")
        
        # Get user from database
        user = User.get_by_id(userid)
        if not user:
            logger.warning(f"get_user_avatar_file: User not found - userid={userid}")
            return jsonify({"error": "User not found"}), 404
        
        # Check if user has avatar_path
        if not user.avatar_path:
            logger.warning(f"get_user_avatar_file: User has no avatar - userid={userid}")
            return jsonify({"error": "User has no avatar"}), 404

        if Config.GCS_BUCKET_NAME:
            from shared.storage import get_storage_service
            try:
                signed_url = get_storage_service().get_signed_url(user.avatar_path)
            except Exception:
                logger.warning(f"get_user_avatar_file: Avatar object not found - userid={userid}, path={user.avatar_path}")
                return jsonify({"error": "Avatar file not found"}), 404
            logger.info(f"get_user_avatar_file: EXIT - Redirecting to signed URL for userid={userid}")
            return redirect(signed_url)

        # Serve the file
        images_dir = Path(Config.IMAGES_DIR)
        file_path = images_dir / user.avatar_path

        # Security: Ensure file is within images directory
        if not str(file_path.resolve()).startswith(str(images_dir.resolve())):
            logger.warning(f"get_user_avatar_file: Invalid path - userid={userid}")
            return jsonify({"error": "Invalid path"}), 403

        if file_path.exists():
            logger.info(f"get_user_avatar_file: EXIT - Serving avatar for userid={userid}")
            return send_from_directory(str(images_dir), user.avatar_path)
        else:
            logger.warning(f"get_user_avatar_file: Avatar file not found - userid={userid}, path={user.avatar_path}")
            return jsonify({"error": "Avatar file not found"}), 404
            
    except Exception as e:
        logger.exception(f"get_user_avatar_file: EXIT - Error: {str(e)}")
        return jsonify({"error": "Failed to serve avatar"}), 500

# Serve icons from backend/icons for platform/user categories
@app.route('/icons/<path:filename>')
def serve_icon(filename):
    """Serve icon assets from backend/icons"""
    try:
        from pathlib import Path
        icons_dir = Path(__file__).resolve().parent / 'icons'
        file_path = icons_dir / filename
        # Security: Ensure file is within icons directory
        if not str(file_path.resolve()).startswith(str(icons_dir.resolve())):
            return jsonify({"error": "Invalid path"}), 403
        if file_path.exists():
            return send_from_directory(str(icons_dir), filename)
        else:
            return jsonify({"error": "Icon not found"}), 404
    except Exception as e:
        logger.exception(f"serve_icon: Error serving icon {filename}: {str(e)}")
        return jsonify({"error": "Failed to serve icon"}), 500

# Register blueprints
app.register_blueprint(auth_bp)
app.register_blueprint(body_measurements_bp)
app.register_blueprint(tryon_bp)
app.register_blueprint(garments_bp)
app.register_blueprint(fitting_bp)
app.register_blueprint(users_bp)
app.register_blueprint(wardrobe_bp)
app.register_blueprint(fit_analysis_bp)
app.register_blueprint(sizing_bp)
app.register_blueprint(garment_discovery_bp)

# Handle BadRequest (415 Unsupported Media Type) specifically
@app.errorhandler(BadRequest)
def handle_bad_request(e):
    """Handle BadRequest exceptions (including 415 Unsupported Media Type)"""
    error_msg = str(e)
    if '415' in error_msg or 'Unsupported Media Type' in error_msg or 'JSON' in error_msg:
        logger.warning(f"BadRequest (415): {error_msg}")
        return error_response_from_string(f'Server error: {error_msg}', 415, 'ERROR')
    logger.error(f"BadRequest: {error_msg}", exc_info=True)
    return error_response_from_string(f'Bad request: {error_msg}', 400, 'VALIDATION_ERROR')


@app.errorhandler(HTTPException)
def handle_http_exception(e: HTTPException):
    """
    Preserve correct status codes for routing and other Werkzeug HTTP errors.

    A catch-all handler on Exception incorrectly turns 404 into 500 unless
    HTTPException is handled first (NotFound subclasses HTTPException).
    """
    code = e.code or 500
    message = e.description if e.description else (e.name or "Request error")
    if code < 500:
        logger.debug("HTTP %s %s: %s", code, getattr(request, "path", ""), message)
    else:
        logger.warning("HTTP %s %s: %s", code, getattr(request, "path", ""), message)
    err_code = "NOT_FOUND" if code == 404 else "HTTP_ERROR"
    return error_response_from_string(message, code, err_code)


# Global error handler
@app.errorhandler(Exception)
def handle_error(e):
    """Global error handler"""
    logger.error(f"Unhandled error: {str(e)}", exc_info=True)
    return error_response_from_string(f'Server error: {str(e)}', 500, 'ERROR')

@app.route("/", methods=["GET"])
def root():
    """Bare root URL for scanners and load balancers; API lives under /api and /health."""
    return jsonify(
        {
            "service": "becauseFuture-backend",
            "health": "/health",
        }
    )


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
    user_id = getattr(request, 'user_id', 'unknown')
    logger.info(f"save_avatar: ENTRY - user_id={user_id}")
    try:
        # Check if file and user_id are provided
        if 'avatar' not in request.files:
            logger.warning(f"save_avatar: No avatar file in request for user_id={user_id}")
            logger.info(f"save_avatar: Request files keys: {list(request.files.keys())}")
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
        
        user_id = request.user_id
        avatar_data = avatar_file.read()
        logger.info(f"save_avatar: Got avatar file, size={len(avatar_data)} bytes, user_id={user_id}")

        from shared.avatar_person_check import reject_message_if_avatar_not_person

        rejection = reject_message_if_avatar_not_person(avatar_data)
        if rejection:
            logger.warning(f"save_avatar: Avatar rejected for user_id={user_id}: {rejection}")
            from shared.analytics import track_event, EventType
            from shared.models.user import User
            user_for_email = User.get_by_id(user_id)
            track_event(
                EventType.AVATAR_FAILED,
                user_id=user_id,
                user_email=user_for_email.email if user_for_email else None,
                metadata={'reason': rejection[:100]}
            )
            return error_response_from_string(rejection, 400, 'INVALID_AVATAR_NOT_PERSON')

        try:
            from features.tryon.service import _remove_background_local
            from PIL import Image
            from io import BytesIO

            # Ensure minimum resolution for avatar (768px minimum dimension)
            MIN_AVATAR_DIMENSION = 768
            try:
                img = Image.open(BytesIO(avatar_data))
                width, height = img.size
                min_dim = min(width, height)
                if min_dim < MIN_AVATAR_DIMENSION:
                    scale = MIN_AVATAR_DIMENSION / min_dim
                    new_width = int(width * scale)
                    new_height = int(height * scale)
                    img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                    logger.info(f"Avatar upscaled from {width}x{height} to {new_width}x{new_height} (min dimension {MIN_AVATAR_DIMENSION}px)")
                    output = BytesIO()
                    # Preserve original format
                    img_format = img.format or 'PNG'
                    if img.mode == 'RGBA' and img_format == 'JPEG':
                        img_format = 'PNG'
                    img.save(output, format=img_format)
                    avatar_data = output.getvalue()
            except Exception as scale_error:
                logger.warning(f"Could not check/scale avatar resolution: {str(scale_error)}, continuing with original")

            logger.info(f"Removing background from avatar using rembg (local) for user: {user_id}")
            avatar_data = _remove_background_local(avatar_data)
            try:
                img = Image.open(BytesIO(avatar_data))
                if img.mode != 'RGBA':
                    img = img.convert('RGBA')
                bbox = img.getbbox()
                if bbox:
                    original_size = img.size
                    img_width, img_height = original_size
                    padding_x = max(int(img_width * 0.02), 15)
                    padding_y = max(int(img_height * 0.02), 15)
                    left, top, right, bottom = bbox
                    left = max(0, left - padding_x)
                    top = max(0, top - padding_y)
                    right = min(img_width, right + padding_x)
                    bottom = min(img_height, bottom + padding_y)
                    img = img.crop((left, top, right, bottom))
                    logger.info(f"Avatar trimmed from {original_size} to {img.size} (removed transparent padding, preserved {padding_x}x{padding_y}px margin for extended body parts)")
                    output = BytesIO()
                    img.save(output, format='PNG')
                    avatar_data = output.getvalue()
                else:
                    logger.warning(f"Avatar has no visible content (all transparent)")
            except Exception as trim_error:
                logger.warning(f"Could not trim avatar padding: {str(trim_error)}, using original size")
            
            # Solidify alpha mask to fill interior semi-transparency and prevent background bleed-through
            from shared.image_processing import clean_and_solidify_alpha_mask, normalize_avatar_framing
            avatar_data = clean_and_solidify_alpha_mask(avatar_data)
            avatar_data = normalize_avatar_framing(avatar_data)
        except Exception as e:
            logger.exception(f"Background removal error for user {user_id}: {str(e)}")
            return error_response_from_string(
                f'Failed to remove background from avatar: {str(e)}',
                500,
                'EXTERNAL_SERVICE_ERROR'
            )
        logger.info(f"Saving avatar for user: {user_id}, size: {len(avatar_data)} bytes, bg_removed: True, transparent: True")
        from shared.models.user import User
        user = User.get_by_id(user_id)
        if not user:
            return error_response_from_string('User not found', 404, 'NOT_FOUND')
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
        base_url = request.url_root.rstrip('/')
        absolute_avatar_url = f"{base_url}{avatar_url}"
        user.avatar = avatar_data
        user.avatar_path = storage_path  # Store the file path reference
        user.save()
        logger.info(f"Avatar saved successfully for user: {user_id}, URL: {absolute_avatar_url}")
        from shared.analytics import track_event, EventType
        track_event(
            EventType.AVATAR_SAVED,
            user_id=user_id,
            user_email=user.email,
            metadata={'method': 'rembg', 'size_bytes': len(avatar_data)}
        )
        return success_response(
            data={
                'message': 'Avatar saved successfully (rembg-based background removal)',
                'background_removed': True,
                'method': 'rembg',
                'avatar_url': absolute_avatar_url
            },
            message='Avatar saved successfully'
        )
        
    except Exception as e:
        logger.exception(f"save_avatar: EXIT - Error: {str(e)}")
        return error_response_from_string(f'Server error: {str(e)}', 500)


@app.route('/api/save-avatar-local', methods=['POST'])
@require_auth
def save_avatar_local():
    """
    Save avatar with rembg-based local background removal (no Gemini API)
    """
    user_id = getattr(request, 'user_id', 'unknown')
    logger.info(f"save_avatar_local: ENTRY - user_id={user_id}")
    try:
        # Check if file is provided
        if 'avatar' not in request.files:
            logger.warning(f"save_avatar_local: No avatar file in request for user_id={user_id}")
            return error_response_from_string('No avatar file provided', 400, 'VALIDATION_ERROR')
        
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
        
        user_id = request.user_id
        logger.info(f"save_avatar_local: Got avatar file, size={len(avatar_data)} bytes, user_id={user_id}")

        # Remove background using rembg-based local algorithm
        try:
            from shared.avatar_person_check import reject_message_if_avatar_not_person

            rejection = reject_message_if_avatar_not_person(avatar_data)
            if rejection:
                logger.warning(f"save_avatar_local: Avatar rejected for user_id={user_id}: {rejection}")
                from shared.analytics import track_event, EventType
                from shared.models.user import User
                user_for_email = User.get_by_id(user_id)
                track_event(
                    EventType.AVATAR_FAILED,
                    user_id=user_id,
                    user_email=user_for_email.email if user_for_email else None,
                    metadata={'reason': rejection[:100], 'method': 'local'}
                )
                return error_response_from_string(rejection, 400, 'INVALID_AVATAR_NOT_PERSON')

            from features.tryon.service import _remove_background_local
            from PIL import Image
            from io import BytesIO

            logger.info(f"Removing background from avatar using rembg (local) for user: {user_id}")
            avatar_data = _remove_background_local(avatar_data)
            
            # Trim transparent padding to make person fill more of the frame
            # IMPORTANT: Add padding around bounding box to preserve extended body parts (hands, etc.)
            try:
                img = Image.open(BytesIO(avatar_data))
                # Ensure RGBA mode
                if img.mode != 'RGBA':
                    img = img.convert('RGBA')
                
                # Get bounding box of non-transparent pixels
                bbox = img.getbbox()
                if bbox:
                    original_size = img.size
                    img_width, img_height = original_size
                    
                    # Add padding margin to preserve extended body parts (hands, feet, etc.)
                    # Use 2% of image dimensions or minimum 15 pixels, whichever is larger
                    padding_x = max(int(img_width * 0.02), 15)
                    padding_y = max(int(img_height * 0.02), 15)
                    
                    # Extract bounding box coordinates
                    left, top, right, bottom = bbox
                    
                    # Expand bounding box with padding, but stay within image boundaries
                    left = max(0, left - padding_x)
                    top = max(0, top - padding_y)
                    right = min(img_width, right + padding_x)
                    bottom = min(img_height, bottom + padding_y)
                    
                    # Crop with padding to preserve entire person including extended parts
                    img = img.crop((left, top, right, bottom))
                    logger.info(f"Avatar trimmed from {original_size} to {img.size} (removed transparent padding, preserved {padding_x}x{padding_y}px margin for extended body parts)")
                    
                    # Save trimmed image
                    output = BytesIO()
                    img.save(output, format='PNG')
                    avatar_data = output.getvalue()
                else:
                    logger.warning(f"Avatar has no visible content (all transparent)")
            except Exception as trim_error:
                logger.warning(f"Could not trim avatar padding: {str(trim_error)}, using original size")
                
            from shared.image_processing import clean_and_solidify_alpha_mask, normalize_avatar_framing
            avatar_data = clean_and_solidify_alpha_mask(avatar_data)
            avatar_data = normalize_avatar_framing(avatar_data)
        except Exception as e:
            logger.exception(f"Background removal error for user {user_id}: {str(e)}")
            return error_response_from_string(
                f'Failed to remove background from avatar: {str(e)}',
                500,
                'EXTERNAL_SERVICE_ERROR'
            )
        
        logger.info(f"Saving avatar (local) for user: {user_id}, size: {len(avatar_data)} bytes, bg_removed: True, transparent: True")
        
        # Use User model
        from shared.models.user import User
        user = User.get_by_id(user_id)
        
        if not user:
            return error_response_from_string('User not found', 404, 'NOT_FOUND')
        
        # Save avatar to disk storage
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
        
        # Construct absolute URL
        base_url = request.url_root.rstrip('/')
        absolute_avatar_url = f"{base_url}{avatar_url}"
        
        # Also save to database for backward compatibility
        user.avatar = avatar_data
        user.avatar_path = storage_path  # Store the file path reference
        user.save()

        logger.info(f"Avatar saved successfully (local) for user: {user_id}, URL: {absolute_avatar_url}")
        from shared.analytics import track_event, EventType
        track_event(
            EventType.AVATAR_SAVED,
            user_id=user_id,
            user_email=user.email,
            metadata={'method': 'rembg_local', 'size_bytes': len(avatar_data)}
        )

        return success_response(
            data={
                'message': 'Avatar saved successfully (rembg-based background removal)',
                'background_removed': True,
                'method': 'rembg',
                'avatar_url': absolute_avatar_url
            },
            message='Avatar saved successfully'
        )
        
    except Exception as e:
        logger.exception(f"save_avatar_local: EXIT - Error: {str(e)}")
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
        
        # Prefer the stored avatar_path reference (works for both local disk
        # and GCS - avoids scanning the filesystem, which doesn't exist on
        # Cloud Run's ephemeral disk / doesn't apply to GCS-backed storage).
        avatar_url = None
        if user.avatar_path:
            base_url = request.url_root.rstrip('/')
            avatar_url = f"{base_url}/images/{user.avatar_path}"
        
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
        
        if not data or 'avatar_data' not in data:
            return jsonify({
                'success': False,
                'error': 'Avatar data is required'
            }), 400

        # Always operate on the authenticated user from the JWT, never a
        # client-supplied user_id, to prevent overwriting another user's avatar.
        user_id = request.user_id
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
        
        from shared.avatar_person_check import reject_message_if_avatar_not_person

        rejection = reject_message_if_avatar_not_person(avatar_data)
        if rejection:
            return error_response_from_string(rejection, 400, 'INVALID_AVATAR_NOT_PERSON')

        # Validate file size (max 5MB)
        max_size = 5 * 1024 * 1024  # 5MB
        if len(avatar_data) > max_size:
            return jsonify({
                'success': False,
                'error': 'File too large. Maximum size is 5MB'
            }), 400
        
        logger.info(f"Updating avatar for user: {user_id}, size: {len(avatar_data)} bytes")

        # Check if user exists
        user = db_manager.execute_query(
            "SELECT id FROM users WHERE userid = ?", (user_id,), fetch_one=True
        )

        if not user:
            return jsonify({
                'success': False,
                'error': 'User not found'
            }), 404

        # Update user's avatar
        db_manager.execute_query(
            "UPDATE users SET avatar = ? WHERE userid = ?", (avatar_data, user_id)
        )

        logger.info(f"Avatar updated successfully for user: {user_id}")
        
        return jsonify({
            'success': True,
            'message': 'Avatar updated successfully'
        }), 200
        
    except Exception as e:
        logger.exception(f"update_avatar: Server error: {e}")
        return server_error_response(e, context='Server error')


if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5001))
    app.run(debug=Config.FLASK_DEBUG, host="0.0.0.0", port=port)