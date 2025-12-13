"""
User Profile API endpoints
CRUD operations for user profile data
Uses User model for data operations
JWT authentication via @require_auth decorator extracts user_id from token
"""

from flask import Blueprint, request
from shared.models.user import User
from shared.response import success_response, error_response_from_string
from shared.middleware import require_auth
from shared.validators import validate_email, validate_password
from shared.errors import ValidationError
from shared.logger import logger
from datetime import datetime

users_bp = Blueprint('users', __name__, url_prefix='/api/users')


@users_bp.route('/profile', methods=['GET'])
@require_auth  # JWT decorator validates token and sets request.user_id from token
def get_profile():
    """
    Get current user's profile
    Uses User model
    user_id is extracted from JWT token by @require_auth decorator
    """
    # user_id comes from JWT token via @require_auth decorator
    user_id = request.user_id
    logger.info(f"get_profile: ENTRY - user_id={user_id} (from JWT)")
    
    try:
        user = User.get_by_id(user_id)
        
        if not user:
            logger.warning(f"get_profile: User not found - user_id={user_id}")
            return error_response_from_string('User not found', 404, 'NOT_FOUND')
        
        logger.info(f"get_profile: EXIT - Profile retrieved for user_id={user_id}")
        return success_response(data=user.to_dict())
        
    except Exception as e:
        logger.exception(f"get_profile: EXIT - Error: {str(e)}")
        return error_response_from_string(f'Server error: {str(e)}', 500)


@users_bp.route('/profile', methods=['PUT'])
@require_auth  # JWT decorator validates token and sets request.user_id from token
def update_profile():
    """
    Update current user's profile
    Uses User model
    user_id is extracted from JWT token by @require_auth decorator
    """
    # user_id comes from JWT token via @require_auth decorator
    user_id = request.user_id
    logger.info(f"update_profile: ENTRY - user_id={user_id} (from JWT)")
    
    try:
        # Handle JSON requests safely
        content_type = request.content_type or ''
        if 'application/json' in content_type:
            data = request.get_json(silent=True, force=False) or {}
        else:
            data = {}
        
        if not data:
            return error_response_from_string('No data provided', 400, 'VALIDATION_ERROR')
        
        # Get existing user
        user = User.get_by_id(user_id)
        if not user:
            logger.warning(f"update_profile: User not found - user_id={user_id}")
            return error_response_from_string('User not found', 404, 'NOT_FOUND')
        
        # Validate and prepare update data
        update_data = {}
        
        # Validate email if provided
        if 'email' in data:
            update_data['email'] = validate_email(str(data['email']).strip())
        
        # Validate gender if provided
        if 'gender' in data:
            valid_genders = ['male', 'female', 'other', 'prefer-not-to-say']
            if data['gender'] not in valid_genders:
                return error_response_from_string(
                    f'Invalid gender. Must be one of: {", ".join(valid_genders)}',
                    400,
                    'VALIDATION_ERROR'
                )
            update_data['gender'] = data['gender']
        
        # Validate birthday format if provided
        if 'birthday' in data and data['birthday']:
            try:
                datetime.strptime(str(data['birthday']), '%Y-%m-%d')
                update_data['birthday'] = str(data['birthday']).strip()
            except ValueError:
                return error_response_from_string(
                    'Birthday must be in YYYY-MM-DD format',
                    400,
                    'VALIDATION_ERROR'
                )
        
        # Handle other string fields
        for field in ['first_name', 'last_name', 'street', 'city']:
            if field in data:
                value = str(data[field]).strip() if data[field] else None
                update_data[field] = value
        
        if not update_data:
            return error_response_from_string('No valid fields to update', 400, 'VALIDATION_ERROR')
        
        # Update user model
        user.update_from_dict(update_data)
        user.save()
        
        logger.info(f"update_profile: EXIT - Profile updated for user_id={user_id}")
        return success_response(
            data=user.to_dict(),
            message='Profile updated successfully'
        )
        
    except ValidationError as e:
        logger.exception(f"update_profile: EXIT - ValidationError: {str(e)}")
        return error_response_from_string(str(e), 400, 'VALIDATION_ERROR')
    except Exception as e:
        logger.exception(f"update_profile: EXIT - Error: {str(e)}")
        return error_response_from_string(f'Server error: {str(e)}', 500)


@users_bp.route('/profile/change-password', methods=['POST'])
@require_auth  # JWT decorator validates token and sets request.user_id from token
def change_password():
    """
    Change user password
    Requires current password verification
    Uses User model
    user_id is extracted from JWT token by @require_auth decorator
    """
    # user_id comes from JWT token via @require_auth decorator
    user_id = request.user_id
    logger.info(f"change_password: ENTRY - user_id={user_id} (from JWT)")
    
    try:
        # Handle JSON requests safely
        content_type = request.content_type or ''
        if 'application/json' in content_type:
            data = request.get_json(silent=True, force=False) or {}
        else:
            data = {}
        
        if not data:
            return error_response_from_string('No data provided', 400, 'VALIDATION_ERROR')
        
        current_password = data.get('current_password', '')
        new_password = data.get('new_password', '')
        confirm_password = data.get('confirm_password', '')
        
        # Validate required fields
        if not current_password:
            return error_response_from_string('Current password is required', 400, 'VALIDATION_ERROR')
        if not new_password:
            return error_response_from_string('New password is required', 400, 'VALIDATION_ERROR')
        if not confirm_password:
            return error_response_from_string('Confirm password is required', 400, 'VALIDATION_ERROR')
        
        # Validate password confirmation
        if new_password != confirm_password:
            return error_response_from_string('New password and confirm password do not match', 400, 'VALIDATION_ERROR')
        
        # Validate new password strength
        try:
            validate_password(new_password)
        except ValidationError as e:
            return error_response_from_string(str(e), 400, 'VALIDATION_ERROR')
        
        # Get user
        user = User.get_by_id(user_id)
        if not user:
            logger.warning(f"change_password: User not found - user_id={user_id}")
            return error_response_from_string('User not found', 404, 'NOT_FOUND')
        
        # Verify current password
        if not user.check_password(current_password):
            logger.warning(f"change_password: Invalid current password for user_id={user_id}")
            return error_response_from_string('Current password is incorrect', 401, 'AUTHENTICATION_ERROR')
        
        # Check if new password is same as current
        if user.check_password(new_password):
            return error_response_from_string('New password must be different from current password', 400, 'VALIDATION_ERROR')
        
        # Update password
        user.password = new_password  # Will be hashed in save() method
        user.save()
        
        logger.info(f"change_password: EXIT - Password changed successfully for user_id={user_id}")
        return success_response(
            data={'message': 'Password changed successfully'},
            message='Password changed successfully'
        )
        
    except ValidationError as e:
        logger.exception(f"change_password: EXIT - ValidationError: {str(e)}")
        return error_response_from_string(str(e), 400, 'VALIDATION_ERROR')
    except Exception as e:
        logger.exception(f"change_password: EXIT - Error: {str(e)}")
        return error_response_from_string(f'Server error: {str(e)}', 500)

