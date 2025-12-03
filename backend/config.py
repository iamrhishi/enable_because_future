"""
Configuration management for becauseFuture backend
Loads all configuration from environment variables
"""

import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class Config:
    """Application configuration loaded from environment variables"""
    
    # Flask Configuration
    FLASK_ENV = os.environ.get('FLASK_ENV', 'development')
    FLASK_DEBUG = os.environ.get('FLASK_DEBUG', 'True').lower() == 'true'
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
    
    # Database Configuration
    DATABASE_PATH = os.environ.get('DATABASE_PATH', 'database.db')
    
    # Google Gemini (Nano Banana) API Configuration
    # Used for both background removal and try-on processing
    GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', '')
    GEMINI_MODEL_NAME = os.environ.get('GEMINI_MODEL_NAME', 'gemini-2.5-flash-image')  # Nano Banana image model
    
    # JWT Configuration
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY', SECRET_KEY)
    JWT_ALGORITHM = os.environ.get('JWT_ALGORITHM', 'HS256')
    JWT_EXPIRATION_HOURS = int(os.environ.get('JWT_EXPIRATION_HOURS', '24'))
    
    # File Upload Configuration
    MAX_UPLOAD_SIZE = int(os.environ.get('MAX_UPLOAD_SIZE', '6291456'))  # 6MB in bytes
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}
    WARDROBE_FOLDER = os.environ.get('WARDROBE_FOLDER', '../frontend/public/images/wardrobe')
    
    # CORS Configuration
    CORS_ORIGINS = os.environ.get('CORS_ORIGINS', '*').split(',')
    
    # Local File Storage Configuration
    IMAGES_DIR = os.environ.get('IMAGES_DIR', 'images')  # Base directory for storing images
    IMAGES_BASE_URL = os.environ.get('IMAGES_BASE_URL', '/images')  # Base URL for serving images
    
    # Scraping Configuration (optional)
    # Proxy support - set ENABLE_PROXY=true to enable
    ENABLE_PROXY = os.environ.get('ENABLE_PROXY', 'True').lower() == 'true'
    HTTP_PROXY = os.environ.get('HTTP_PROXY', '')  # e.g., 'http://proxy.example.com:8080'
    HTTPS_PROXY = os.environ.get('HTTPS_PROXY', '')  # e.g., 'https://proxy.example.com:8080'
    PROXY_USERNAME = os.environ.get('PROXY_USERNAME', '')
    PROXY_PASSWORD = os.environ.get('PROXY_PASSWORD', '')
    
    # Scrape.do Configuration
    # Used for bypassing bot detection with residential proxies and JavaScript rendering
    SCRAPE_DO_API_KEY = os.environ.get('SCRAPE_DO_API_KEY', '')
    SCRAPE_DO_ENABLED = os.environ.get('SCRAPE_DO_ENABLED', 'False').lower() == 'true'
    
    @staticmethod
    def validate():
        """Validate that all required configuration is present"""
        required_vars = []
        
        if not Config.SECRET_KEY or Config.SECRET_KEY == 'dev-secret-key-change-in-production':
            required_vars.append('SECRET_KEY (using default - change in production)')
        
        
        if not Config.ENABLE_PROXY:
            msg = (
                "Proxy support is disabled (ENABLE_PROXY=False). "
                "Zara extraction requires proxy support. "
                "Set ENABLE_PROXY=true in your .env file."
            )
            raise RuntimeError(msg)
        
        if required_vars:
            print(f"⚠️  Warning: Missing or default configuration: {', '.join(required_vars)}")
        
        return len(required_vars) == 0

