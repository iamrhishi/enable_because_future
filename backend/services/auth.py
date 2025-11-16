"""
JWT authentication service
Handles token generation, validation, and user authentication
"""

import jwt
import datetime
from typing import Optional, Dict
from config import Config
from utils.errors import AuthenticationError
from utils.logger import logger


def generate_token(user_id: str, email: str, additional_claims: Dict = None) -> str:
    """
    Generate JWT token for user
    
    Args:
        user_id: User ID
        email: User email
        additional_claims: Additional claims to include in token
        
    Returns:
        JWT token string
    """
    logger.info(f"generate_token: ENTRY - user_id={user_id}, email={email}")
    
    try:
        payload = {
            'user_id': user_id,
            'email': email,
            'iat': datetime.datetime.utcnow(),
            'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=Config.JWT_EXPIRATION_HOURS)
        }
        
        if additional_claims:
            payload.update(additional_claims)
        
        token = jwt.encode(payload, Config.JWT_SECRET_KEY, algorithm=Config.JWT_ALGORITHM)
        logger.info("generate_token: EXIT - Token generated successfully")
        return token
    except Exception as e:
        logger.exception(f"generate_token: EXIT - Error: {str(e)}")
        raise


def verify_token(token: str) -> Dict:
    """
    Verify and decode JWT token
    
    Args:
        token: JWT token string
        
    Returns:
        Decoded token payload
        
    Raises:
        AuthenticationError: If token is invalid or expired
    """
    logger.info("verify_token: ENTRY")
    
    try:
        payload = jwt.decode(token, Config.JWT_SECRET_KEY, algorithms=[Config.JWT_ALGORITHM])
        logger.info(f"verify_token: EXIT - Token verified, user_id={payload.get('user_id')}")
        return payload
    except jwt.ExpiredSignatureError as e:
        logger.warning(f"verify_token: EXIT - Token expired: {str(e)}")
        raise AuthenticationError("Token has expired")
    except jwt.InvalidTokenError as e:
        logger.warning(f"verify_token: EXIT - Invalid token: {str(e)}")
        raise AuthenticationError("Invalid token")
    except Exception as e:
        logger.exception(f"verify_token: EXIT - Unexpected error: {str(e)}")
        raise AuthenticationError(f"Token verification failed: {str(e)}")


def get_user_from_token(token: str) -> Optional[str]:
    """
    Extract user_id from JWT token
    
    Args:
        token: JWT token string
        
    Returns:
        User ID or None if invalid
    """
    logger.info("get_user_from_token: ENTRY")
    
    try:
        payload = verify_token(token)
        user_id = payload.get('user_id')
        logger.info(f"get_user_from_token: EXIT - user_id={user_id}")
        return user_id
    except AuthenticationError as e:
        logger.warning(f"get_user_from_token: EXIT - AuthenticationError: {str(e)}")
        return None
    except Exception as e:
        logger.exception(f"get_user_from_token: EXIT - Unexpected error: {str(e)}")
        return None
