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
CONVERTIBLE_FORMATS = ['AVIF', 'HEIC', 'HEIF', 'BMP', 'TIFF', 'GIF']  # Will be converted to PNG
ALLOWED_MIMETYPES = ['image/jpeg', 'image/jpg', 'image/png', 'image/webp', 'image/avif']


def convert_to_supported_format(image_data: bytes) -> bytes:
    """
    Convert unsupported image formats (AVIF, HEIC, etc.) to PNG.

    Args:
        image_data: Image bytes (possibly in unsupported format)

    Returns:
        Image bytes in supported format (PNG if converted, original if already supported)
    """
    try:
        img = Image.open(BytesIO(image_data))
        img_format = img.format

        if img_format in ALLOWED_FORMATS:
            # Already supported, return as-is
            return image_data

        if img_format in CONVERTIBLE_FORMATS:
            logger.info(f"convert_to_supported_format: Converting {img_format} to PNG")
            # Convert to RGB/RGBA and save as PNG
            if img.mode in ('RGBA', 'LA', 'PA'):
                img = img.convert('RGBA')
            elif img.mode == 'P':
                img = img.convert('RGBA')
            else:
                img = img.convert('RGB')

            output = BytesIO()
            img.save(output, format='PNG', optimize=True)
            result = output.getvalue()
            logger.info(f"convert_to_supported_format: Converted {img_format} to PNG ({len(result)} bytes)")
            return result

        # Unknown format, return original and let validation handle it
        logger.warning(f"convert_to_supported_format: Unknown format {img_format}, returning original")
        return image_data

    except Exception as e:
        logger.warning(f"convert_to_supported_format: Error: {str(e)}, returning original")
        return image_data


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
        
        # Check if data looks like HTML (common mistake when fetching product pages instead of images)
        if image_data.startswith(b'<') or image_data.startswith(b'<!DOCTYPE') or image_data.startswith(b'<!doctype'):
            raise ValidationError("Invalid image format: Received HTML content instead of image. Please provide a direct image URL, not a product page URL.")
        
        # Open and validate image
        try:
            img = Image.open(BytesIO(image_data))
            img_format = img.format
            img_size = img.size  # (width, height)
        except Exception as e:
            # Check if it might be HTML or other non-image content
            if b'<html' in image_data[:500].lower() or b'<!doctype' in image_data[:500].lower():
                raise ValidationError("Invalid image format: Received HTML content instead of image. Please provide a direct image URL, not a product page URL.")
            raise ValidationError(f"Invalid image format: {str(e)}")
        
        # Check format
        if img_format not in ALLOWED_FORMATS:
            errors.append(f"Format {img_format} not allowed. Allowed: {', '.join(ALLOWED_FORMATS)}. Tip: Use preprocess_image() to auto-convert AVIF/HEIC.")
        
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
            # Preserve transparency (RGBA mode) for PNG
            if img.mode not in ('RGBA', 'LA', 'P'):
                # If image doesn't have alpha channel, keep as is
                img.save(output, format='PNG', optimize=True)
            else:
                # Ensure RGBA mode for transparency
                if img.mode == 'P':
                    img = img.convert('RGBA')
                elif img.mode == 'LA':
                    img = img.convert('RGBA')
                # Save with transparency preserved
                img.save(output, format='PNG', optimize=True)
        elif target_format == 'WEBP':
            # WEBP also supports transparency
            if img.mode in ('RGBA', 'LA', 'P'):
                if img.mode == 'P':
                    img = img.convert('RGBA')
                elif img.mode == 'LA':
                    img = img.convert('RGBA')
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
        # Convert unsupported formats (AVIF, HEIC, etc.) to PNG first
        image_data = convert_to_supported_format(image_data)

        # Quick dimension check first - if image exceeds MAX_DIMENSION, resize immediately
        # This prevents validation errors for large images that will be resized anyway
        try:
            img = Image.open(BytesIO(image_data))
            max_dim = max(img.size)
            if max_dim > MAX_DIMENSION and resize:
                logger.info(f"preprocess_image: Image dimension {max_dim}px exceeds {MAX_DIMENSION}px, resizing first")
                image_data = resize_image(image_data, max_dimension=MAX_DIMENSION_RESIZE)
        except Exception as e:
            # If we can't open the image, let validation handle it
            logger.debug(f"preprocess_image: Could not check dimensions: {str(e)}, proceeding to validation")

        # Validate (after potential conversion and initial resize)
        validation = validate_image(image_data, filename)
        logger.info(f"preprocess_image: Image validated - {validation['format']}, {validation['size']}")
        
        processed = image_data
        
        # Resize if needed (for images that are within MAX_DIMENSION but larger than MAX_DIMENSION_RESIZE)
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


def clean_and_solidify_alpha_mask(image_bytes: bytes, threshold: int = 15) -> bytes:
    """
    Clean and solidify the interior alpha mask of a PNG image.
    Fills interior semi-transparent pixels (alpha > threshold) to alpha = 255 (100% solid opacity),
    while using erosion to leave perimeter anti-aliased edge pixels untouched (preventing dark halos).
    """
    try:
        import numpy as np
        img = Image.open(BytesIO(image_bytes))
        if img.mode != 'RGBA':
            img = img.convert('RGBA')

        arr = np.array(img)
        alpha = arr[:, :, 3]

        fg_mask = alpha > threshold
        if not np.any(fg_mask):
            return image_bytes

        # Try using OpenCV erosion to solidify ONLY interior pixels while preserving soft edge anti-aliasing
        try:
            import cv2
            fg_bytes = fg_mask.astype(np.uint8)
            kernel_size = 5  # 5x5 ellipse kernel (~2-3px erosion from perimeter)
            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_size, kernel_size))
            eroded_fg = cv2.erode(fg_bytes, kernel)
            
            # Make interior 100% opaque to stop background bleed, preserving outer soft edge
            arr[:, :, 3][eroded_fg > 0] = 255
        except Exception as cv_err:
            logger.warning(f"clean_and_solidify_alpha_mask: OpenCV erosion failed ({cv_err}), falling back to gentle solidifying")
            # Fallback without cv2: only solidify high-confidence foreground pixels (alpha > 200)
            arr[:, :, 3][alpha > 200] = 255

        out_img = Image.fromarray(arr, mode='RGBA')
        buf = BytesIO()
        out_img.save(buf, format='PNG')
        result = buf.getvalue()
        logger.info(f"clean_and_solidify_alpha_mask: Solidified alpha mask (size {len(result)} bytes)")
        return result
    except Exception as e:
        logger.warning(f"clean_and_solidify_alpha_mask error: {e}, returning original")
        return image_bytes


def normalize_avatar_framing(
    image_bytes: bytes,
    target_canvas_size: tuple[int, int] = (900, 1200),
    target_height_percent: float = 0.95,
    bottom_margin_percent: float = 0.02
) -> bytes:
    """
    Normalize an avatar / try-on result image to standard 3:4 canvas framing.
    Crops empty transparent padding around subject.
    For full-body figures, scales height to target_height_percent (default 95%).
    For upper-body / 3/4 figures, preserves natural scale matching avatar proportions
    instead of blowing up upper-body crops to giant sizes.
    """
    try:
        img = Image.open(BytesIO(image_bytes))
        if img.mode != 'RGBA':
            img = img.convert('RGBA')

        bbox = img.getbbox()
        if not bbox:
            logger.warning("normalize_avatar_framing: Image has no non-transparent pixels")
            return image_bytes

        left, top, right, bottom = bbox
        crop_w = right - left
        crop_h = bottom - top

        canvas_w, canvas_h = target_canvas_size
        img_w, img_h = img.size

        # Check if subject is full body (spans top to bottom, height >= 78% of image height)
        is_full_body = crop_h >= (img_h * 0.78) or (crop_h / float(crop_w) >= 2.1)

        if is_full_body:
            # Full body: scale to target_height_percent (95% height) and anchor near bottom
            desired_subject_h = int(canvas_h * target_height_percent)
            scale = desired_subject_h / float(crop_h)
            scaled_w = int(crop_w * scale)
            scaled_h = desired_subject_h

            max_allowed_w = int(canvas_w * 0.92)
            if scaled_w > max_allowed_w:
                scale = max_allowed_w / float(crop_w)
                scaled_w = max_allowed_w
                scaled_h = int(crop_h * scale)

            cropped_img = img.crop(bbox)
            resized_subject = cropped_img.resize((scaled_w, scaled_h), Image.Resampling.LANCZOS)

            canvas = Image.new('RGBA', (canvas_w, canvas_h), (0, 0, 0, 0))
            paste_x = (canvas_w - scaled_w) // 2
            bottom_margin = int(canvas_h * bottom_margin_percent)
            paste_y = canvas_h - bottom_margin - scaled_h
            if paste_y < 0:
                paste_y = (canvas_h - scaled_h) // 2

            canvas.paste(resized_subject, (paste_x, paste_y), resized_subject)
        else:
            # Upper body / partial crop:
            # If the image is ALREADY on standard canvas (900x1200) with head near top (top <= 120),
            # DO NOT STRETCH/BLOW UP the upper body! Preserve original canvas scale and positioning.
            if img_w == canvas_w and img_h == canvas_h and top <= 120:
                canvas = img
            else:
                # Scale proportionally based on width scale to match standard avatar proportions
                scale = canvas_w / float(img_w) if img_w > 0 else 1.0
                scaled_w = int(crop_w * scale)
                scaled_h = int(crop_h * scale)

                # Cap width to max 75% of canvas width to prevent giant shoulders
                max_w = int(canvas_w * 0.75)
                if scaled_w > max_w:
                    scale = max_w / float(crop_w)
                    scaled_w = max_w
                    scaled_h = int(crop_h * scale)

                cropped_img = img.crop(bbox)
                resized_subject = cropped_img.resize((scaled_w, scaled_h), Image.Resampling.LANCZOS)
                canvas = Image.new('RGBA', (canvas_w, canvas_h), (0, 0, 0, 0))
                paste_x = (canvas_w - scaled_w) // 2
                paste_y = int(top * scale)
                canvas.paste(resized_subject, (paste_x, paste_y), resized_subject)

        buf = BytesIO()
        canvas.save(buf, format='PNG')
        result = buf.getvalue()
        logger.info(f"normalize_avatar_framing: Normalized to {canvas_w}x{canvas_h} canvas, is_full_body={is_full_body}")
        return result
    except Exception as e:
        logger.warning(f"normalize_avatar_framing error: {e}, returning original bytes")
        return image_bytes


def _detect_person_in_image(image_bytes: bytes) -> bool:
    """Check if an image contains a human face or body using OpenCV."""
    try:
        import cv2
        import numpy as np
        img = cv2.imdecode(np.frombuffer(image_bytes, dtype=np.uint8), cv2.IMREAD_COLOR)
        if img is None or img.size == 0:
            return False

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        frontal_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
        frontal = cv2.CascadeClassifier(frontal_path)
        if not frontal.empty():
            faces = frontal.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=3, minSize=(30, 30))
            if faces is not None and len(faces) > 0:
                return True

        profile_path = cv2.data.haarcascades + 'haarcascade_profileface.xml'
        profile = cv2.CascadeClassifier(profile_path)
        if not profile.empty():
            pfaces = profile.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=3, minSize=(30, 30))
            if pfaces is not None and len(pfaces) > 0:
                return True

        return False
    except Exception:
        return False


def crop_garment_to_relevant_region(garment_bytes: bytes, garment_type: str = 'upper') -> bytes:
    """
    Crop garment image to isolate the relevant clothing item if it's a full-model photo.
    For 'upper' (shirts, blazers, tops, sweaters), crops to upper ~85% region to include full garment hem.
    For 'lower' (pants, skirts, shorts), crops to lower ~65% region.
    Only crops if image has a tall aspect ratio AND contains a human model figure.
    Flat-lay photos, hanger shots, or already cropped product images remain 100% untouched.
    """
    try:
        img = Image.open(BytesIO(garment_bytes))
        w, h = img.size
        aspect_ratio = h / float(w)

        # 1. Only crop if image has tall aspect ratio typical of full-body model photos (h/w > 1.15)
        if aspect_ratio <= 1.15:
            logger.info(f"crop_garment_to_relevant_region: Aspect ratio {aspect_ratio:.2f} <= 1.15 (already cropped/wide) - keeping original")
            return garment_bytes

        # 2. Check if a human model is actually present in the photo
        has_model = _detect_person_in_image(garment_bytes)
        if not has_model:
            logger.info("crop_garment_to_relevant_region: No human model detected in garment photo (flat-lay/isolated product) - keeping original")
            return garment_bytes

        logger.info(f"crop_garment_to_relevant_region: Detected human model in tall photo ({w}x{h}, ratio {aspect_ratio:.2f}) - cropping for {garment_type}")

        if img.mode in ('RGBA', 'LA'):
            bbox = img.getbbox()
            if bbox:
                img = img.crop(bbox)
                w, h = img.size

        if garment_type == 'upper':
            crop_box = (0, 0, w, int(h * 0.85))
        elif garment_type == 'lower':
            crop_box = (0, int(h * 0.35), w, h)
        else:
            return garment_bytes

        cropped = img.crop(crop_box)
        buf = BytesIO()
        cropped.save(buf, format=img.format or 'PNG')
        result = buf.getvalue()
        logger.info(f"crop_garment_to_relevant_region: Cropped {garment_type} garment from {w}x{h} to {cropped.size[0]}x{cropped.size[1]}")
        return result
    except Exception as e:
        logger.warning(f"crop_garment_to_relevant_region error: {e}, returning original")
        return garment_bytes


def is_image_substantially_unchanged(img1_bytes: bytes, img2_bytes: bytes, max_mean_diff: float = 8.0) -> bool:
    """
    Check if img2 is substantially identical to img1 (indicating Gemini returned the original avatar unchanged).
    """
    try:
        import numpy as np
        img1 = Image.open(BytesIO(img1_bytes)).convert('RGB').resize((128, 128))
        img2 = Image.open(BytesIO(img2_bytes)).convert('RGB').resize((128, 128))

        arr1 = np.array(img1, dtype=np.float32)
        arr2 = np.array(img2, dtype=np.float32)

        mean_diff = float(np.mean(np.abs(arr1 - arr2)))
        unchanged = mean_diff < max_mean_diff
        logger.info(f"is_image_substantially_unchanged: mean_pixel_diff={mean_diff:.2f}, unchanged={unchanged}")
        return unchanged
    except Exception as e:
        logger.warning(f"is_image_substantially_unchanged error: {e}")
        return False




