"""
Image preprocessing service
Handles resize, validation, normalization before AI processing
Per context.md: max 2048px, ≤ 6MB, max 4096x4096
"""

from PIL import Image  # type: ignore
from io import BytesIO
import base64
from shared.logger import logger
from shared.errors import ValidationError


# Constants per context.md
MAX_FILE_SIZE = 6 * 1024 * 1024  # 6 MB (context.md line 124)
MAX_DIMENSION = 4096  # 4096x4096 (context.md line 124)
MAX_DIMENSION_RESIZE = 2048  # 2048px max dimension (context.md line 78)
ALLOWED_FORMATS = ['JPEG', 'PNG', 'WEBP']
ALLOWED_MIMETYPES = ['image/jpeg', 'image/jpg', 'image/png', 'image/webp']


def validate_image(image_data: bytes, filename: str = None) -> dict:
    """
    Validate image size, format, and dimensions
    
    Args:
        image_data: Image bytes
        filename: Optional filename for format detection
        
    Returns:
        dict with validation results: {'valid': bool, 'format': str, 'size': tuple, 'errors': list}
        
    Raises:
        ValidationError: If image is invalid
    """
    logger.info("validate_image: ENTRY")
    
    try:
        errors = []
        
        # Check file size
        file_size = len(image_data)
        if file_size > MAX_FILE_SIZE:
            errors.append(f"File size {file_size / 1024 / 1024:.2f}MB exceeds maximum {MAX_FILE_SIZE / 1024 / 1024}MB")
        
        if file_size == 0:
            raise ValidationError("Image file is empty")
        
        # Open and validate image
        try:
            img = Image.open(BytesIO(image_data))
            img_format = img.format
            img_size = img.size  # (width, height)
        except Exception as e:
            raise ValidationError(f"Invalid image format: {str(e)}")
        
        # Check format
        if img_format not in ALLOWED_FORMATS:
            errors.append(f"Format {img_format} not allowed. Allowed: {', '.join(ALLOWED_FORMATS)}")
        
        # Check dimensions
        max_dim = max(img_size)
        if max_dim > MAX_DIMENSION:
            errors.append(f"Image dimension {max_dim}px exceeds maximum {MAX_DIMENSION}px")
        
        if errors:
            error_msg = "; ".join(errors)
            logger.warning(f"validate_image: EXIT - Validation failed: {error_msg}")
            raise ValidationError(error_msg)
        
        result = {
            'valid': True,
            'format': img_format,
            'size': img_size,
            'file_size': file_size
        }
        logger.info(f"validate_image: EXIT - Valid: {img_format}, {img_size}, {file_size} bytes")
        return result
        
    except ValidationError:
        raise
    except Exception as e:
        logger.exception(f"validate_image: EXIT - Error: {str(e)}")
        raise ValidationError(f"Image validation failed: {str(e)}")


def resize_image(image_data: bytes, max_dimension: int = MAX_DIMENSION_RESIZE, 
                 maintain_aspect: bool = True) -> bytes:
    """
    Resize image to max dimension (per context.md line 78: 2048px max)
    
    Args:
        image_data: Image bytes
        max_dimension: Maximum dimension (default 2048px)
        maintain_aspect: Maintain aspect ratio
        
    Returns:
        Resized image bytes
    """
    logger.info(f"resize_image: ENTRY - max_dimension={max_dimension}")
    
    try:
        img = Image.open(BytesIO(image_data))
        original_size = img.size
        
        # Check if resize is needed
        max_current_dim = max(original_size)
        if max_current_dim <= max_dimension:
            logger.info(f"resize_image: EXIT - No resize needed: {original_size}")
            return image_data
        
        # Calculate new size
        if maintain_aspect:
            ratio = max_dimension / max_current_dim
            new_size = (int(original_size[0] * ratio), int(original_size[1] * ratio))
        else:
            new_size = (max_dimension, max_dimension)
        
        # Resize with high-quality resampling
        img_resized = img.resize(new_size, Image.Resampling.LANCZOS)
        
        # Convert to bytes
        output = BytesIO()
        # Preserve format
        if img.format == 'PNG':
            img_resized.save(output, format='PNG', optimize=True)
        elif img.format == 'WEBP':
            img_resized.save(output, format='WEBP', quality=85)
        else:
            # JPEG
            img_resized.save(output, format='JPEG', quality=85, optimize=True)
        
        result = output.getvalue()
        logger.info(f"resize_image: EXIT - Resized from {original_size} to {new_size}, {len(result)} bytes")
        return result
        
    except Exception as e:
        logger.exception(f"resize_image: EXIT - Error: {str(e)}")
        raise ValidationError(f"Image resize failed: {str(e)}")


def normalize_image(image_data: bytes, target_format: str = 'PNG') -> bytes:
    """
    Normalize image format and optimize
    
    Args:
        image_data: Image bytes
        target_format: Target format (PNG, JPEG, WEBP)
        
    Returns:
        Normalized image bytes
    """
    logger.info(f"normalize_image: ENTRY - target_format={target_format}")
    
    try:
        img = Image.open(BytesIO(image_data))
        
        # Convert RGBA to RGB if needed (for JPEG)
        if target_format == 'JPEG' and img.mode in ('RGBA', 'LA', 'P'):
            # Create white background
            background = Image.new('RGB', img.size, (255, 255, 255))
            if img.mode == 'P':
                img = img.convert('RGBA')
            background.paste(img, mask=img.split()[-1] if img.mode in ('RGBA', 'LA') else None)
            img = background
        
        # Convert to target format
        output = BytesIO()
        if target_format == 'PNG':
            img.save(output, format='PNG', optimize=True)
        elif target_format == 'WEBP':
            img.save(output, format='WEBP', quality=85)
        else:  # JPEG
            img.save(output, format='JPEG', quality=85, optimize=True)
        
        result = output.getvalue()
        logger.info(f"normalize_image: EXIT - Normalized to {target_format}, {len(result)} bytes")
        return result
        
    except Exception as e:
        logger.exception(f"normalize_image: EXIT - Error: {str(e)}")
        raise ValidationError(f"Image normalization failed: {str(e)}")


def preprocess_image(image_data: bytes, filename: str = None, 
                    resize: bool = True, normalize: bool = True) -> bytes:
    """
    Complete image preprocessing pipeline
    
    Per context.md requirements:
    - Validate size (≤ 6MB, max 4096x4096)
    - Resize (max 2048px)
    - Normalize format
    
    Args:
        image_data: Image bytes
        filename: Optional filename
        resize: Whether to resize (default True)
        normalize: Whether to normalize format (default True)
        
    Returns:
        Preprocessed image bytes
    """
    logger.info("preprocess_image: ENTRY")
    
    try:
        # Validate first
        validation = validate_image(image_data, filename)
        logger.info(f"preprocess_image: Image validated - {validation['format']}, {validation['size']}")
        
        processed = image_data
        
        # Resize if needed
        if resize:
            processed = resize_image(processed, max_dimension=MAX_DIMENSION_RESIZE)
        
        # Normalize format
        if normalize:
            # Use PNG for consistency (good for transparency)
            processed = normalize_image(processed, target_format='PNG')
        
        logger.info(f"preprocess_image: EXIT - Preprocessed: {len(processed)} bytes")
        return processed
        
    except ValidationError:
        raise
    except Exception as e:
        logger.exception(f"preprocess_image: EXIT - Error: {str(e)}")
        raise ValidationError(f"Image preprocessing failed: {str(e)}")


def fetch_image_from_url(url: str, timeout: int = 10) -> bytes:
    """
    Fetch image from URL
    
    Args:
        url: Image URL
        timeout: Request timeout in seconds
        
    Returns:
        Image bytes
        
    Raises:
        ValidationError: If fetch fails
    """
    logger.info(f"fetch_image_from_url: ENTRY - url={url[:100]}")
    
    try:
        import requests
        
        from features.garments.scraping_constants import get_default_headers, get_proxy_config, get_proxy_auth
        headers = get_default_headers()
        proxies = get_proxy_config()
        auth = get_proxy_auth()
        
        response = requests.get(url, headers=headers, timeout=timeout, proxies=proxies, auth=auth)
        response.raise_for_status()
        
        # Validate content type
        content_type = response.headers.get('Content-Type', '').lower()
        if not any(mt in content_type for mt in ALLOWED_MIMETYPES):
            logger.warning(f"fetch_image_from_url: Unexpected content type: {content_type}")
        
        image_data = response.content
        logger.info(f"fetch_image_from_url: EXIT - Fetched {len(image_data)} bytes")
        return image_data
        
    except requests.RequestException as e:
        logger.exception(f"fetch_image_from_url: EXIT - Request failed: {str(e)}")
        raise ValidationError(f"Failed to fetch image from URL: {str(e)}")
    except Exception as e:
        logger.exception(f"fetch_image_from_url: EXIT - Error: {str(e)}")
        raise ValidationError(f"Error fetching image: {str(e)}")

