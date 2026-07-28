from flask import Blueprint, request
from shared.models.user import User
from shared.response import success_response, error_response_from_string, server_error_response
from shared.middleware import require_auth
from shared.analytics import track_event, EventType
from shared.validators import validate_email, validate_password
from shared.errors import ValidationError
from shared.logger import logger
from shared.database import db_manager
from datetime import datetime

users_bp = Blueprint('users', __name__, url_prefix='/api/users')

# ...existing endpoints...

@users_bp.route('/avatar', methods=['GET'])
@require_auth
def get_avatar():
    """
    Get current user's avatar URL (file path)
    Returns the URL path to the avatar image that can be served via /images endpoint
    """
    user_id = request.user_id
    logger.info(f"get_avatar: ENTRY - user_id={user_id} (from JWT)")
    try:
        user = User.get_by_id(user_id)
        if not user:
            logger.warning(f"get_avatar: User not found - user_id={user_id}")
            return error_response_from_string('User not found', 404, 'NOT_FOUND')
        if user.avatar_path:
            # Return the URL path to the avatar image
            avatar_url = f"/images/{user.avatar_path}"
            logger.info(f"get_avatar: EXIT - Avatar URL retrieved for user_id={user_id}")
            return success_response(data={
                'avatar_url': avatar_url,
                'avatar_path': user.avatar_path,
                'message': 'Avatar URL retrieved successfully'
            })
        else:
            logger.info(f"get_avatar: EXIT - No avatar for user_id={user_id}")
            return success_response(data={
                'avatar_url': None,
                'avatar_path': None,
                'message': 'No avatar found for user'
            })
    except Exception as e:
        logger.exception(f"get_avatar: EXIT - Error: {str(e)}")
        return server_error_response(e, context='Server error', status_code=500)

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
        
        if not user or not user.is_active:
            logger.warning(f"get_profile: User not found - user_id={user_id}")
            return error_response_from_string('User not found', 404, 'NOT_FOUND')
        
        logger.info(f"get_profile: EXIT - Profile retrieved for user_id={user_id}")
        return success_response(data=user.to_dict())
        
    except Exception as e:
        logger.exception(f"get_profile: EXIT - Error: {str(e)}")
        return server_error_response(e, context='Server error', status_code=500)


@users_bp.route('/profile', methods=['PUT', 'PATCH'])
@require_auth
def update_profile():
    """
    Update current user's profile
    Uses User model
    user_id is extracted from JWT token by @require_auth decorator
    """
    user_id = request.user_id
    logger.info(f"update_profile: ENTRY - user_id={user_id} (from JWT)")

    try:
        content_type = request.content_type or ''
        if 'application/json' in content_type:
            data = request.get_json(silent=True, force=False) or {}
        else:
            data = {}

        if not data:
            return error_response_from_string('No data provided', 400, 'VALIDATION_ERROR')

        user = User.get_by_id(user_id)
        if not user:
            logger.warning(f"update_profile: User not found - user_id={user_id}")
            return error_response_from_string('User not found', 404, 'NOT_FOUND')

        update_data = {}

        if 'email' in data:
            new_email = validate_email(str(data['email']).strip())
            if new_email != user.email:
                existing_user = User.get_by_email(new_email)
                if existing_user and existing_user.userid != user_id:
                    return error_response_from_string('Email already registered', 409, 'EMAIL_EXISTS')
            update_data['email'] = new_email

        # Gender is optional; validate only when a non-empty value is provided
        if 'gender' in data:
            valid_genders = ['male', 'female', 'other', 'prefer-not-to-say']
            gender_value = (str(data['gender']).strip() if data['gender'] else None) or None
            if gender_value and gender_value not in valid_genders:
                return error_response_from_string(
                    f'Invalid gender. Must be one of: {", ".join(valid_genders)}',
                    400,
                    'VALIDATION_ERROR'
                )
            update_data['gender'] = gender_value

        birthday_key = 'birthday' if 'birthday' in data else ('birthdate' if 'birthdate' in data else None)
        if birthday_key:
            birthday_value = data.get(birthday_key)
            if birthday_value:
                try:
                    datetime.strptime(str(birthday_value), '%Y-%m-%d')
                except ValueError:
                    return error_response_from_string(
                        'Birthday must be in YYYY-MM-DD format',
                        400,
                        'VALIDATION_ERROR'
                    )
                update_data['birthday'] = str(birthday_value).strip()
            else:
                update_data['birthday'] = None

        for field in ['first_name', 'last_name', 'street', 'city', 'postal_code', 'country']:
            if field in data:
                value = str(data[field]).strip() if data[field] else None
                update_data[field] = value

        if not update_data:
            return error_response_from_string('No valid fields to update', 400, 'VALIDATION_ERROR')

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
        return server_error_response(e, context='Server error', status_code=500)


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
        return server_error_response(e, context='Server error', status_code=500)


def _parse_delete_account_body():
    """Read optional JSON body for account deletion (password confirmation)."""
    content_type = request.content_type or ''
    if 'application/json' in content_type:
        return request.get_json(silent=True, force=False) or {}
    return {}


def _delete_user_account(user_id: str):
    """
    Soft-delete the authenticated user's account.
    Accepts password or current_password in the JSON body when provided.
    """
    data = _parse_delete_account_body()
    password = (
        (data.get('password') or data.get('current_password') or '')
        .strip()
    )

    if password:
        user = User.get_by_id(user_id)
        if not user:
            logger.warning(f"delete_account: User not found - user_id={user_id}")
            return error_response_from_string('User not found', 404, 'NOT_FOUND')

        if not user.is_active:
            return error_response_from_string('Account not found', 404, 'NOT_FOUND')

        if not user.check_password(password):
            logger.warning(f"delete_account: Invalid password for user_id={user_id}")
            return error_response_from_string('Password is incorrect', 401, 'AUTHENTICATION_ERROR')
    else:
        user = User.get_by_id(user_id)
        if not user:
            logger.warning(f"delete_account: User not found - user_id={user_id}")
            return error_response_from_string('User not found', 404, 'NOT_FOUND')

        if not user.is_active:
            return error_response_from_string('Account not found', 404, 'NOT_FOUND')

    user.deactivate_account()

    # Track account deletion
    track_event(EventType.DELETE_ACCOUNT, user_id=user_id, user_email=user.email)

    logger.info(f"delete_account: EXIT - Account deleted for user_id={user_id}")
    return success_response(message='Your account has been deleted successfully')


@users_bp.route('/profile', methods=['DELETE'])
@users_bp.route('/account', methods=['DELETE'])
@require_auth
def delete_account():
    """
    Permanently close the authenticated user's account (soft delete).
    Flutter clients call DELETE /api/users/profile; /api/users/account is also supported.
    """
    user_id = request.user_id
    logger.info(f"delete_account: ENTRY - user_id={user_id} (from JWT)")

    try:
        return _delete_user_account(user_id)
    except ValueError as e:
        logger.warning(f"delete_account: EXIT - {str(e)}")
        return error_response_from_string(str(e), 400, 'VALIDATION_ERROR')
    except Exception as e:
        logger.exception(f"delete_account: EXIT - Error: {str(e)}")
        return server_error_response(e, context='Server error', status_code=500)


@users_bp.route('/data-export', methods=['GET'])
@require_auth
def export_my_data():
    """
    GDPR Article 15 (right of access) / Article 20 (data portability):
    return everything stored about the authenticated user in one bundle.

    Image bytes themselves aren't inlined (impractical for a JSON response) -
    wardrobe/avatar images are referenced by their existing /images URLs,
    which the user can fetch directly; try-on result/original photos are
    listed by job id with their existing metadata.
    """
    user_id = request.user_id
    logger.info(f"export_my_data: ENTRY - user_id={user_id}")

    try:
        user = User.get_by_id(user_id)
        if not user:
            return error_response_from_string('User not found', 404, 'NOT_FOUND')

        body_measurements = db_manager.execute_query(
            "SELECT * FROM body_measurements WHERE user_id = ?", (user_id,), fetch_one=True
        )
        wardrobe_items = db_manager.execute_query(
            "SELECT id, garment_id, garment_type, garment_url, title, brand, color, size, "
            "price, fabric, description, category, category_section, image_path, url, date_added "
            "FROM wardrobe WHERE user_id = ?", (user_id,), fetch_all=True
        )
        wardrobe_categories = db_manager.execute_query(
            "SELECT name, description, category_section, created_at FROM wardrobe_categories WHERE user_id = ?",
            (user_id,), fetch_all=True
        )
        tryon_jobs = db_manager.execute_query(
            "SELECT job_id, status, progress, result_url, garment_url, error_message, created_at, updated_at "
            "FROM tryon_jobs WHERE user_id = ?", (user_id,), fetch_all=True
        )
        tryon_results = db_manager.execute_query(
            "SELECT id, try_on_count, applied_garments, created_at FROM tryon_results WHERE user_id = ?",
            (user_id,), fetch_all=True
        )
        analytics_events = db_manager.execute_query(
            "SELECT event_type, metadata, created_at FROM analytics_events_all WHERE user_id = ? ORDER BY created_at",
            (user_id,), fetch_all=True
        ) if db_manager.table_exists('analytics_events_all') else []

        export = {
            'profile': user.to_dict(),
            'body_measurements': body_measurements,
            'wardrobe_items': wardrobe_items or [],
            'wardrobe_categories': wardrobe_categories or [],
            'tryon_jobs': tryon_jobs or [],
            'tryon_results': tryon_results or [],
            'analytics_events': analytics_events or [],
        }

        logger.info(f"export_my_data: EXIT - Exported data for user_id={user_id}")
        return success_response(data=export)

    except Exception as e:
        logger.exception(f"export_my_data: EXIT - Error: {str(e)}")
        return server_error_response(e, context='Server error', status_code=500)

