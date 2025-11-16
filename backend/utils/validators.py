"""
Input validation utilities
"""

import re
from utils.errors import ValidationError


def validate_email(email: str) -> str:
    """Validate email format"""
    if not email:
        raise ValidationError("Email is required", field='email')
    
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(pattern, email):
        raise ValidationError("Invalid email format", field='email')
    
    return email.lower().strip()


def validate_password(password: str, min_length: int = 6) -> str:
    """Validate password"""
    if not password:
        raise ValidationError("Password is required", field='password')
    
    if len(password) < min_length:
        raise ValidationError(f"Password must be at least {min_length} characters long", field='password')
    
    return password


def validate_required(data: dict, fields: list):
    """Validate that required fields are present"""
    missing = [field for field in fields if field not in data or not data[field]]
    if missing:
        raise ValidationError(f"Missing required fields: {', '.join(missing)}")


def validate_numeric(value, field_name: str, min_value: float = None, max_value: float = None):
    """Validate numeric value"""
    try:
        num_value = float(value)
        if min_value is not None and num_value < min_value:
            raise ValidationError(f"{field_name} must be at least {min_value}", field=field_name)
        if max_value is not None and num_value > max_value:
            raise ValidationError(f"{field_name} must be at most {max_value}", field=field_name)
        return num_value
    except (ValueError, TypeError):
        raise ValidationError(f"{field_name} must be a number", field=field_name)


def validate_integer(value, field_name: str, min_value: int = None, max_value: int = None):
    """Validate integer value"""
    try:
        int_value = int(value)
        if min_value is not None and int_value < min_value:
            raise ValidationError(f"{field_name} must be at least {min_value}", field=field_name)
        if max_value is not None and int_value > max_value:
            raise ValidationError(f"{field_name} must be at most {max_value}", field=field_name)
        return int_value
    except (ValueError, TypeError):
        raise ValidationError(f"{field_name} must be an integer", field=field_name)


def validate_url(url: str) -> str:
    """Validate URL format"""
    if not url:
        raise ValidationError("URL is required", field='url')
    
    pattern = r'^https?://.+'
    if not re.match(pattern, url):
        raise ValidationError("Invalid URL format", field='url')
    
    return url.strip()

