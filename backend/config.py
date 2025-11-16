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
    
    # Background Removal Service
    BG_SERVICE_URL = os.environ.get('BG_SERVICE_URL', 'https://api.becausefuture.tech/bg-service/api/remove')
    BG_SERVICE_USERNAME = os.environ.get('BG_SERVICE_USERNAME', 'becausefuture')
    BG_SERVICE_PASSWORD = os.environ.get('BG_SERVICE_PASSWORD', 'becausefuture!2025')
    
    # Mixer Service (Try-On)
    MIXER_SERVICE_URL = os.environ.get('MIXER_SERVICE_URL', 'https://api.becausefuture.tech/mixer-service/tryon')
    MIXER_SERVICE_USERNAME = os.environ.get('MIXER_SERVICE_USERNAME', 'becausefuture')
    MIXER_SERVICE_PASSWORD = os.environ.get('MIXER_SERVICE_PASSWORD', 'becausefuture!2025')
    
    # Gemini/Nano Banana API (Recommended per context.md)
    GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', '')
    AI_MODEL_PROVIDER = os.environ.get('AI_MODEL_PROVIDER', 'gemini')  # 'mixer' or 'gemini' - default to gemini per context.md
    GEMINI_MODEL_NAME = os.environ.get('GEMINI_MODEL_NAME', 'gemini-1.5-flash')  # 'gemini-1.5-flash' or 'gemini-1.5-pro'
    
    # JWT Configuration
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY', SECRET_KEY)
    JWT_ALGORITHM = os.environ.get('JWT_ALGORITHM', 'HS256')
    JWT_EXPIRATION_HOURS = int(os.environ.get('JWT_EXPIRATION_HOURS', '24'))
    
    # Google OAuth Configuration
    GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID', '')
    GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET', '')
    
    # File Upload Configuration
    MAX_UPLOAD_SIZE = int(os.environ.get('MAX_UPLOAD_SIZE', '6291456'))  # 6MB in bytes
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}
    WARDROBE_FOLDER = os.environ.get('WARDROBE_FOLDER', '../frontend/public/images/wardrobe')
    
    # CORS Configuration
    CORS_ORIGINS = os.environ.get('CORS_ORIGINS', '*').split(',')
    
    # Storage Configuration (GCS/S3)
    STORAGE_PROVIDER = os.environ.get('STORAGE_PROVIDER', 'gcs').lower()  # 'gcs' (default) or 's3' or empty (disabled)
    
    # AWS S3 Configuration
    AWS_ACCESS_KEY_ID = os.environ.get('AWS_ACCESS_KEY_ID', '')
    AWS_SECRET_ACCESS_KEY = os.environ.get('AWS_SECRET_ACCESS_KEY', '')
    AWS_S3_BUCKET = os.environ.get('AWS_S3_BUCKET', '')
    AWS_REGION = os.environ.get('AWS_REGION', 'us-east-1')
    
    # Google Cloud Storage Configuration
    GCS_BUCKET_NAME = os.environ.get('GCS_BUCKET_NAME', '')
    GCS_CREDENTIALS_PATH = os.environ.get('GCS_CREDENTIALS_PATH', '')
    
    @staticmethod
    def validate():
        """Validate that all required configuration is present"""
        required_vars = []
        
        if not Config.SECRET_KEY or Config.SECRET_KEY == 'dev-secret-key-change-in-production':
            required_vars.append('SECRET_KEY (using default - change in production)')
        
        if Config.AI_MODEL_PROVIDER == 'gemini' and not Config.GEMINI_API_KEY:
            required_vars.append('GEMINI_API_KEY (required if using Gemini)')
        
        if required_vars:
            print(f"⚠️  Warning: Missing or default configuration: {', '.join(required_vars)}")
        
        return len(required_vars) == 0

