"""
URL utility functions for converting relative URLs to absolute URLs
"""

from flask import request


def to_absolute_url(relative_url: str) -> str:
    """
    Convert a relative URL to an absolute URL using the current request's base URL
    
    Args:
        relative_url: Relative URL (e.g., '/images/avatars/user123/avatar.png')
        
    Returns:
        Absolute URL (e.g., 'http://localhost:8000/images/avatars/user123/avatar.png')
    """
    if not relative_url:
        return relative_url
    
    # If already absolute, return as-is
    if relative_url.startswith('http://') or relative_url.startswith('https://') or relative_url.startswith('data:'):
        return relative_url
    
    # Get base URL from request
    base_url = request.url_root.rstrip('/')
    
    # Ensure relative_url starts with /
    if not relative_url.startswith('/'):
        relative_url = f'/{relative_url}'
    
    return f"{base_url}{relative_url}"

