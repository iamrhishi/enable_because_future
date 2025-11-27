"""
Middleware utilities for Flask routes
"""

from functools import wraps
from flask import request
from features.auth.service import verify_token
from shared.errors import AuthenticationError
from shared.response import error_response, error_response_from_string


def require_auth(f):
    """
    Decorator to require JWT authentication for a route
    
    Usage:
        @app.route('/api/protected')
        @require_auth
        def protected_route():
            user_id = request.user_id  # Available after authentication
            ...
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth_header = request.headers.get('Authorization')
        
        if not auth_header:
            return error_response_from_string("Authorization header required", 401, 'AUTH_REQUIRED')
        
        try:
            # Extract token from "Bearer <token>"
            if auth_header.startswith('Bearer '):
                token = auth_header.split(' ')[1]
            else:
                token = auth_header
            
            # Verify token and get user info
            payload = verify_token(token)
            request.user_id = payload.get('user_id')
            request.user_email = payload.get('email')
            
        except AuthenticationError as e:
            return error_response(e)
        except Exception as e:
            return error_response_from_string("Invalid token", 401, 'INVALID_TOKEN')
        
        return f(*args, **kwargs)
    
    return decorated_function


def optional_auth(f):
    """
    Decorator to optionally authenticate (doesn't fail if no token)
    
    Usage:
        @app.route('/api/optional')
        @optional_auth
        def optional_route():
            user_id = getattr(request, 'user_id', None)  # May be None
            ...
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth_header = request.headers.get('Authorization')
        
        if auth_header:
            try:
                if auth_header.startswith('Bearer '):
                    token = auth_header.split(' ')[1]
                else:
                    token = auth_header
                
                payload = verify_token(token)
                request.user_id = payload.get('user_id')
                request.user_email = payload.get('email')
            except:
                # Silently fail for optional auth
                pass
        
        return f(*args, **kwargs)
    
    return decorated_function

