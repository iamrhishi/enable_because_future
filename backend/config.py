"""
Configuration management for becauseFuture backend
Loads all configuration from environment variables
"""

import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

try:
    _job_status_poll_interval_ms_raw = int(os.environ.get('JOB_STATUS_POLL_INTERVAL_MS', '1000'))
except ValueError:
    _job_status_poll_interval_ms_raw = 1000


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

    # Try-on latency (optional):
    # - LITE: on IMAGE_OTHER, only run deterministic + relaxed prompt (2 calls max), not 4.
    GEMINI_TRYON_LITE_IMAGE_OTHER_RETRIES = os.environ.get(
        'GEMINI_TRYON_LITE_IMAGE_OTHER_RETRIES',
        'false',
    ).lower() == 'true'
    # - Cap longest side of person + garment before Gemini (0 = off). Smaller = faster API, lower output res.
    try:
        _gem_tryon_max_edge = int(os.environ.get('GEMINI_TRYON_INPUT_MAX_EDGE', '0'))
    except ValueError:
        _gem_tryon_max_edge = 0
    GEMINI_TRYON_INPUT_MAX_EDGE = max(0, min(_gem_tryon_max_edge, 4096))

    # JWT Configuration
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY', SECRET_KEY)
    JWT_ALGORITHM = os.environ.get('JWT_ALGORITHM', 'HS256')
    JWT_EXPIRATION_HOURS = int(os.environ.get('JWT_EXPIRATION_HOURS', '24'))
    
    # File Upload Configuration
    MAX_UPLOAD_SIZE = int(os.environ.get('MAX_UPLOAD_SIZE', '6291456'))  # 6MB in bytes
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}
    WARDROBE_FOLDER = os.environ.get('WARDROBE_FOLDER', '../frontend/public/images/wardrobe')

    # Reject obvious non-person uploads when saving/updating avatar (requires opencv-python-headless)
    AVATAR_PERSON_CHECK_ENABLED = os.environ.get(
        'AVATAR_PERSON_CHECK_ENABLED',
        'true',
    ).lower() == 'true'

    # Async try-on: recommended delay between GET /api/job/{id} polls while status is queued/processing.
    # Milliseconds (clamped). Clients implement polling; backend only advertises this in JSON responses.
    JOB_STATUS_POLL_INTERVAL_MS = max(250, min(_job_status_poll_interval_ms_raw, 30000))

    # CORS Configuration
    # No safe wildcard default: require explicit origins in every environment.
    CORS_ORIGINS = [o.strip() for o in os.environ.get('CORS_ORIGINS', '').split(',') if o.strip()]
    
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
    
    # Remote Try-On API Configuration
    # NOTE: This is disabled - local processing is used instead
    REMOTE_TRYON_API_URL = os.environ.get('REMOTE_TRYON_API_URL', 'http://35.198.124.100:5000/api/tryon-gemini')
    REMOTE_TRYON_API_ENABLED = os.environ.get('REMOTE_TRYON_API_ENABLED', 'False').lower() == 'true'

    # Mixer-Service API Configuration (specialized virtual try-on model)
    MIXER_SERVICE_URL = os.environ.get('MIXER_SERVICE_URL', 'https://api.becausefuture.tech/mixer-service/tryon')
    # No hardcoded credential defaults: must be set via env/Secret Manager.
    MIXER_SERVICE_USERNAME = os.environ.get('MIXER_SERVICE_USERNAME', '')
    MIXER_SERVICE_PASSWORD = os.environ.get('MIXER_SERVICE_PASSWORD', '')

    # Lovable/Supabase API Configuration (for sizing/garment data)
    LOVABLE_API_BASE = os.environ.get('LOVABLE_API_BASE', 'https://ccjdxxgoahfsxnlthxmm.supabase.co/functions/v1')
    LOVABLE_API_KEY = os.environ.get('LOVABLE_API_KEY', '')

    # Analytics & Daily Report Configuration
    # SMTP for sending daily analytics reports (XLSX)
    # Supports both SMTP_* and EMAIL_* naming (EMAIL_* is Django convention)
    SMTP_HOST = os.environ.get('SMTP_HOST') or os.environ.get('EMAIL_HOST', 'smtp.gmail.com')
    SMTP_PORT = int(os.environ.get('SMTP_PORT') or os.environ.get('EMAIL_PORT', '587'))
    SMTP_USER = os.environ.get('SMTP_USER') or os.environ.get('EMAIL_HOST_USER', '')
    SMTP_PASSWORD = os.environ.get('SMTP_PASSWORD') or os.environ.get('EMAIL_HOST_PASSWORD', '')
    SMTP_FROM = os.environ.get('SMTP_FROM') or os.environ.get('DEFAULT_FROM_EMAIL', '')
    # Comma-separated list of emails to receive daily analytics reports
    ANALYTICS_REPORT_EMAILS = os.environ.get('ANALYTICS_REPORT_EMAILS', '')

    @staticmethod
    def validate():
        """Validate that all required configuration is present"""
        required_vars = []

        using_default_secret = not Config.SECRET_KEY or Config.SECRET_KEY == 'dev-secret-key-change-in-production'
        if using_default_secret:
            if Config.FLASK_ENV == 'production':
                raise RuntimeError(
                    "SECRET_KEY is unset or using the known default value. "
                    "Refusing to start in production - set SECRET_KEY (and JWT_SECRET_KEY) via env/Secret Manager."
                )
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

