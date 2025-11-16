"""
Standardized API response helpers
"""

from flask import jsonify
from utils.errors import BecauseFutureError


def success_response(data=None, message: str = None, status_code: int = 200):
    """
    Create a standardized success response
    
    Args:
        data: Response data
        message: Success message
        status_code: HTTP status code
        
    Returns:
        Flask JSON response
    """
    response = {'success': True}
    if message:
        response['message'] = message
    if data is not None:
        response['data'] = data
    return jsonify(response), status_code


def error_response(error: BecauseFutureError):
    """
    Create a standardized error response from exception
    
    Args:
        error: BecauseFutureError exception
        
    Returns:
        Flask JSON response
    """
    return jsonify({
        'success': False,
        'error': error.message,
        'error_code': error.error_code
    }), error.status_code


def error_response_from_string(message: str, status_code: int = 500, error_code: str = 'ERROR'):
    """
    Create a standardized error response from string
    
    Args:
        message: Error message
        status_code: HTTP status code
        error_code: Error code
        
    Returns:
        Flask JSON response
    """
    return jsonify({
        'success': False,
        'error': message,
        'error_code': error_code
    }), status_code

