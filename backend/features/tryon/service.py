"""
AI model integration for try-on processing
Primary: Mixer-Service API (specialized virtual try-on model)
V2 (unused): Gemini API - kept for reference but not used
"""

import requests  # type: ignore
from requests.auth import HTTPBasicAuth  # type: ignore
import base64
import time
import re
import json
import hashlib
import threading
import numpy as np  # type: ignore
from PIL import Image  # type: ignore
from io import BytesIO
from config import Config
from shared.logger import logger
from shared.errors import ExternalServiceError

_rembg_session = None
_rembg_session_lock = threading.Lock()


def _get_rembg_session():
    """
    Lazily create and reuse a single rembg ONNX session across all calls/threads.
    onnxruntime sessions support concurrent Run() calls, and re-creating one per
    call otherwise re-pays session init cost on every background removal.
    """
    global _rembg_session
    if _rembg_session is None:
        with _rembg_session_lock:
            if _rembg_session is None:
                from rembg import new_session
                _rembg_session = new_session('u2net')
    return _rembg_session


# =============================================================================
# V2 TRY-ON SERVICE: Mixer-Service (Specialized Virtual Try-On Model)
# Currently not used - service is down. Kept for when it becomes available.
# =============================================================================

def process_tryon_v2_mixer(person_image: bytes, garment_image: bytes, garment_type: str = 'upper',
                           garment_details: dict = None, options: dict = None) -> str:
    """
    [V2 - NOT USED] Process try-on using Mixer-Service API (specialized virtual try-on model)

    NOTE: This function is kept for future use when mixer-service becomes available.
    Currently the service at api.becausefuture.tech is unreachable.

    Args:
        person_image: Person image bytes (avatar or selfie with background removed)
        garment_image: Garment image bytes (can be single image or list - uses first)
        garment_type: 'upper' or 'lower'
        garment_details: Dict with garment info (not used by mixer-service, kept for API compatibility)
        options: Additional options including num_inference_steps

    Returns:
        result_url: Base64 data URL of result image

    Raises:
        ExternalServiceError: If processing fails
    """
    logger.info(f"process_tryon_v2_mixer: ENTRY - garment_type={garment_type} (using Mixer-Service)")

    try:
        # Validate config
        if not Config.MIXER_SERVICE_URL:
            raise ExternalServiceError("Mixer-Service URL not configured", service='mixer-service')

        # Handle list of images - use only the first one
        if isinstance(garment_image, list):
            garment_image = garment_image[0]
            logger.info(f"process_tryon: Received list of images, using first one only")

        # Log image sizes for debugging
        person_size_mb = len(person_image) / (1024 * 1024)
        garment_size_mb = len(garment_image) / (1024 * 1024)
        logger.info(f"process_tryon: Image sizes - person: {person_size_mb:.2f}MB, garment: {garment_size_mb:.2f}MB")

        # Prepare files for mixer-service API
        # API expects: person_image, cloth_image, cloth_type
        files = {
            'person_image': ('person.png', BytesIO(person_image), 'image/png'),
            'cloth_image': ('garment.png', BytesIO(garment_image), 'image/png')
        }

        # Prepare form data
        data = {
            'cloth_type': garment_type  # 'upper' or 'lower'
        }

        # Add optional num_inference_steps from options
        if options and options.get('num_inference_steps'):
            data['num_inference_steps'] = str(options['num_inference_steps'])

        # Prepare auth
        auth = HTTPBasicAuth(Config.MIXER_SERVICE_USERNAME, Config.MIXER_SERVICE_PASSWORD)

        # Call mixer-service API with retry logic
        max_retries = 3
        retry_delay = 2
        response = None

        for attempt in range(max_retries):
            try:
                logger.info(f"process_tryon: Calling Mixer-Service API (attempt {attempt + 1}/{max_retries})")
                response = requests.post(
                    Config.MIXER_SERVICE_URL,
                    files=files,
                    data=data,
                    auth=auth,
                    headers={"Accept": "image/png"},
                    timeout=120  # 2 minute timeout
                )

                # Success - got image response
                if response.status_code == 200 and response.headers.get('Content-Type', '').startswith('image/'):
                    logger.info(f"process_tryon: Mixer-Service returned image, size={len(response.content)} bytes")
                    break

                # Retryable errors (5xx, 429)
                if response.status_code in (500, 502, 503, 504, 429) and attempt < max_retries - 1:
                    wait_time = retry_delay * (attempt + 1)
                    logger.warning(
                        f"process_tryon: Mixer-Service returned {response.status_code} (attempt {attempt + 1}/{max_retries}). "
                        f"Retrying in {wait_time} seconds..."
                    )
                    # Reset file positions for retry
                    files['person_image'] = ('person.png', BytesIO(person_image), 'image/png')
                    files['cloth_image'] = ('garment.png', BytesIO(garment_image), 'image/png')
                    time.sleep(wait_time)
                    continue

                # Non-retryable error or final attempt
                error_text = response.text[:500] if response.text else 'No response body'
                logger.error(f"process_tryon: Mixer-Service error - status={response.status_code}, response={error_text}")

                # Try to parse error message
                try:
                    error_json = response.json()
                    error_msg = error_json.get('message', error_text)
                except:
                    error_msg = error_text

                raise ExternalServiceError(
                    f"Mixer-Service error ({response.status_code}): {error_msg}",
                    service='mixer-service'
                )

            except requests.Timeout:
                if attempt < max_retries - 1:
                    wait_time = retry_delay * (attempt + 1)
                    logger.warning(f"process_tryon: Mixer-Service timeout (attempt {attempt + 1}/{max_retries}). Retrying...")
                    # Reset file positions for retry
                    files['person_image'] = ('person.png', BytesIO(person_image), 'image/png')
                    files['cloth_image'] = ('garment.png', BytesIO(garment_image), 'image/png')
                    time.sleep(wait_time)
                    continue
                raise ExternalServiceError("Mixer-Service timeout after multiple retries", service='mixer-service')

            except requests.RequestException as e:
                if attempt < max_retries - 1:
                    wait_time = retry_delay * (attempt + 1)
                    logger.warning(f"process_tryon: Mixer-Service request failed: {str(e)}. Retrying...")
                    # Reset file positions for retry
                    files['person_image'] = ('person.png', BytesIO(person_image), 'image/png')
                    files['cloth_image'] = ('garment.png', BytesIO(garment_image), 'image/png')
                    time.sleep(wait_time)
                    continue
                raise ExternalServiceError(f"Mixer-Service request failed: {str(e)}", service='mixer-service')

        # Validate response
        if response is None or response.status_code != 200:
            raise ExternalServiceError("Mixer-Service failed after all retries", service='mixer-service')

        if not response.headers.get('Content-Type', '').startswith('image/'):
            raise ExternalServiceError(
                f"Mixer-Service returned unexpected content type: {response.headers.get('Content-Type')}",
                service='mixer-service'
            )

        # Get result image bytes
        result_image_bytes = response.content

        # Verify it's a valid image
        try:
            result_img = Image.open(BytesIO(result_image_bytes))
            logger.info(f"process_tryon: Result image valid - size={result_img.size}, mode={result_img.mode}")
        except Exception as img_error:
            raise ExternalServiceError(f"Mixer-Service returned invalid image: {str(img_error)}", service='mixer-service')

        # Convert to base64 data URL (to match expected output format)
        result_base64 = base64.b64encode(result_image_bytes).decode('utf-8')
        result_url = f"data:image/png;base64,{result_base64}"

        logger.info(f"process_tryon_v2_mixer: EXIT - Success, result size={len(result_base64)} chars")
        return result_url

    except ExternalServiceError:
        logger.exception("process_tryon_v2_mixer: EXIT - ExternalServiceError")
        raise
    except Exception as e:
        logger.exception(f"process_tryon_v2_mixer: EXIT - Unexpected error: {str(e)}")
        raise ExternalServiceError(f"Try-on processing failed: {str(e)}", service='mixer-service')


# =============================================================================
# PRIMARY TRY-ON SERVICE: Gemini API
# =============================================================================


def _crop_to_aspect_ratio(img: Image.Image, target_ratio: float, person_center_x: float = None, person_info: dict = None) -> Image.Image:
    """
    Crop image to match target aspect ratio while preserving entire person including extended body parts
    
    Args:
        img: PIL Image to crop
        target_ratio: Target aspect ratio (width / height)
        person_center_x: Optional person center X coordinate for person-aware cropping
        person_info: Optional dict with person boundary info (bbox, center) to preserve extended parts
        
    Returns:
        Cropped PIL Image matching target aspect ratio with full person preserved
    """
    w, h = img.size
    current_ratio = w / h if h > 0 else 1.0
    
    if abs(current_ratio - target_ratio) < 0.001:  # Already matches (within 0.1% tolerance)
        return img
    
    # If we have person info, use it to ensure we don't crop off extended body parts
    if person_info and person_info.get('bbox'):
        bbox = person_info['bbox']
        bbox_x, bbox_y, bbox_w, bbox_h = bbox
        person_center = person_info.get('center', (bbox_x + bbox_w // 2, bbox_y + bbox_h // 2))
        
        # Add padding around person to preserve extended parts (hands, feet, etc.)
        # Use 3% of image dimensions or minimum 20 pixels
        padding_x = max(int(w * 0.03), 20)
        padding_y = max(int(h * 0.03), 20)
        
        # Calculate person bounds with padding
        person_left = max(0, bbox_x - padding_x)
        person_right = min(w, bbox_x + bbox_w + padding_x)
        person_top = max(0, bbox_y - padding_y)
        person_bottom = min(h, bbox_y + bbox_h + padding_y)
        
        person_width = person_right - person_left
        person_height = person_bottom - person_top
        person_ratio = person_width / person_height if person_height > 0 else 1.0
        
        # If cropping width, ensure person fits horizontally
        if current_ratio > target_ratio:
            new_w = int(h * target_ratio)
            # Ensure person fits within the crop
            if person_width > new_w:
                # Person is wider than target - center on person
                person_center_x = person_center[0]
                ideal_left = person_center_x - new_w / 2
                left = max(0, min(int(ideal_left), w - new_w))
            else:
                # Person fits - center crop but ensure person is included
                ideal_left = person_center[0] - new_w / 2
                left = max(0, min(int(ideal_left), w - new_w))
                # Adjust if person would be cut off
                if person_right > left + new_w:
                    left = max(0, person_right - new_w)
                if person_left < left:
                    left = max(0, person_left)
            
            right = left + new_w
            logger.info(f"_crop_to_aspect_ratio: Person-aware width crop from {w} to {new_w} (person bbox: {bbox}, padding: {padding_x}px)")
            return img.crop((left, 0, right, h))
        else:
            # Crop height - ensure person fits vertically
            new_h = int(w / target_ratio)
            # Ensure person fits within the crop
            if person_height > new_h:
                # Person is taller than target - center on person
                person_center_y = person_center[1]
                ideal_top = person_center_y - new_h / 2
                top = max(0, min(int(ideal_top), h - new_h))
            else:
                # Person fits - center crop but ensure person is included
                ideal_top = person_center[1] - new_h / 2
                top = max(0, min(int(ideal_top), h - new_h))
                # Adjust if person would be cut off
                if person_bottom > top + new_h:
                    top = max(0, person_bottom - new_h)
                if person_top < top:
                    top = max(0, person_top)
            
            bottom = top + new_h
            logger.info(f"_crop_to_aspect_ratio: Person-aware height crop from {h} to {new_h} (person bbox: {bbox}, padding: {padding_y}px)")
            return img.crop((0, top, w, bottom))
    
    # Fallback to original logic if no person info
    if current_ratio > target_ratio:
        # Crop width (image is wider than target)
        new_w = int(h * target_ratio)
        crop_amount = w - new_w
        
        # Use person center if provided, otherwise center crop
        if person_center_x is not None:
            # Person-aware cropping: try to keep person centered
            # Calculate crop position to keep person as centered as possible
            ideal_left = person_center_x - new_w / 2
            # Clamp to valid range
            left = max(0, min(int(ideal_left), crop_amount))
            logger.info(f"_crop_to_aspect_ratio: Person-aware cropping width from {w} to {new_w} (person center: {person_center_x:.1f}, crop left: {left})")
        else:
            # Center crop
            left = crop_amount // 2
            logger.info(f"_crop_to_aspect_ratio: Center cropping width from {w} to {new_w} (target ratio: {target_ratio:.3f}, current: {current_ratio:.3f})")
        
        right = left + new_w
        return img.crop((left, 0, right, h))
    else:
        # Crop height (image is taller than target) - always center crop vertically
        new_h = int(w / target_ratio)
        crop_amount = h - new_h
        top = crop_amount // 2
        bottom = top + new_h
        logger.info(f"_crop_to_aspect_ratio: Center cropping height from {h} to {new_h} (target ratio: {target_ratio:.3f}, current: {current_ratio:.3f})")
        return img.crop((0, top, w, bottom))


def _detect_person_boundaries(person_image: bytes) -> dict:
    """
    Detect person boundaries using rembg to get person mask, then extract bounding box
    
    Args:
        person_image: Person image bytes
        
    Returns:
        dict with person info: {
            'bbox': (x, y, width, height),
            'center': (cx, cy),
            'scale': (width_ratio, height_ratio),
            'aspect_ratio': float
        }
    """
    try:
        from rembg import remove  # type: ignore

        # Remove background to get person mask
        person_with_bg_removed = remove(person_image, session=_get_rembg_session())
        
        # Convert to PIL Image
        img = Image.open(BytesIO(person_with_bg_removed))
        if img.mode != 'RGBA':
            img = img.convert('RGBA')
        
        # Get alpha channel as mask
        alpha = np.array(img.split()[3])  # Get alpha channel
        
        # Find bounding box of non-transparent pixels (person)
        rows = np.any(alpha > 0, axis=1)
        cols = np.any(alpha > 0, axis=0)
        
        if not (np.any(rows) and np.any(cols)):
            # If no person detected, assume person fills most of image
            img_width, img_height = img.size
            logger.warning("_detect_person_boundaries: No person pixels detected in mask, using full image bounds")
            return {
                'bbox': (0, 0, img_width, img_height),
                'center': (img_width // 2, img_height // 2),
                'scale': (1.0, 1.0),
                'aspect_ratio': img_width / img_height,
                'image_size': (img_width, img_height)
            }
        
        y_min, y_max = np.where(rows)[0][[0, -1]]
        x_min, x_max = np.where(cols)[0][[0, -1]]
        
        bbox_x = x_min
        bbox_y = y_min
        bbox_width = x_max - x_min + 1
        bbox_height = y_max - y_min + 1
        
        # Calculate center
        center_x = bbox_x + bbox_width // 2
        center_y = bbox_y + bbox_height // 2
        
        # Get image dimensions
        img_width, img_height = img.size
        
        # Calculate scale ratios
        width_ratio = bbox_width / img_width
        height_ratio = bbox_height / img_height
        
        # Calculate aspect ratio
        aspect_ratio = bbox_width / bbox_height if bbox_height > 0 else 1.0
        
        logger.info(f"_detect_person_boundaries: Person bbox: ({bbox_x}, {bbox_y}, {bbox_width}, {bbox_height}), "
                  f"center: ({center_x}, {center_y}), scale: ({width_ratio:.3f}, {height_ratio:.3f}), aspect_ratio: {aspect_ratio:.3f}")
        
        return {
            'bbox': (bbox_x, bbox_y, bbox_width, bbox_height),
            'center': (center_x, center_y),
            'scale': (width_ratio, height_ratio),
            'aspect_ratio': aspect_ratio,
            'image_size': (img_width, img_height)
        }
    except Exception as e:
        logger.error(f"_detect_person_boundaries: Error detecting person boundaries: {str(e)}")
        # Fallback: assume person fills most of image
        img = Image.open(BytesIO(person_image))
        img_width, img_height = img.size
        return {
            'bbox': (0, 0, img_width, img_height),
            'center': (img_width // 2, img_height // 2),
            'scale': (1.0, 1.0),
            'aspect_ratio': img_width / img_height,
            'image_size': (img_width, img_height)
        }


def _strip_gemini_feedback_markdown(message: str) -> str:
    """Turn '[text](url)' from API copy into plain 'text' for logs and client errors."""
    if not message:
        return message
    return re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', message)


def _raise_gemini_tryon_finish_error(finish_reason: str, finish_message: str) -> None:
    """Raise ExternalServiceError for a Gemini candidate finishReason (no image returned)."""
    raw_message = _strip_gemini_feedback_markdown(finish_message or '')
    logger.error(f'process_tryon: finish_reason={finish_reason}, raw_message={raw_message}')

    if finish_reason == 'IMAGE_OTHER':
        # Clean up verbose Gemini messages for user display
        user_msg = (
            'Try-on could not be completed for this combination. '
            'Try a different pose or garment.'
        )
        raise ExternalServiceError(user_msg, service='gemini')

    if finish_reason in ('SAFETY', 'PROHIBITED_CONTENT'):
        user_msg = (
            'This image combination was blocked by safety filters. '
            'Please try a different photo or garment.'
        )
        raise ExternalServiceError(user_msg, service='gemini')

    if finish_reason == 'MAX_TOKENS':
        raise ExternalServiceError(
            'Image processing limit reached. Try with a smaller image.',
            service='gemini'
        )

    if finish_reason == 'RECITATION':
        raise ExternalServiceError(
            'Could not process this garment image. Please try another.',
            service='gemini'
        )

    # Generic fallback
    raise ExternalServiceError(
        'Try-on failed unexpectedly. Please try again.',
        service='gemini'
    )


def _parse_gemini_tryon_image_response(result: dict):
    """
    Parse Gemini generateContent JSON for try-on. Returns:
      ('ok', image_bytes) — success
      ('finish', finish_reason, finish_message) — finished without an image
    """
    if 'error' in result:
        error_info = result.get('error', {})
        error_message = error_info.get('message', 'Unknown error')
        error_code = error_info.get('code', 'UNKNOWN')
        logger.error(f'process_tryon: Gemini API returned error: {error_code} - {error_message}')
        raise ExternalServiceError(
            f'Gemini API error: {error_code} - {error_message}',
            service='gemini'
        )

    result_image_bytes = None

    if 'candidates' in result and len(result['candidates']) > 0:
        candidate = result['candidates'][0]
        if 'content' in candidate and 'parts' in candidate['content']:
            for part in candidate['content']['parts']:
                if 'inline_data' in part and 'data' in part['inline_data']:
                    image_data_b64 = part['inline_data']['data']
                    result_image_bytes = base64.b64decode(image_data_b64)
                    logger.info(f'process_tryon: Found image in inline_data, size={len(result_image_bytes)} bytes')
                    break
                if 'inlineData' in part and 'data' in part['inlineData']:
                    image_data_b64 = part['inlineData']['data']
                    result_image_bytes = base64.b64decode(image_data_b64)
                    logger.info(f'process_tryon: Found image in inlineData, size={len(result_image_bytes)} bytes')
                    break
                if 'text' in part:
                    text_content = part['text']
                    base64_match = re.search(r'data:image/[^;]+;base64,([A-Za-z0-9+/=]+)', text_content)
                    if base64_match:
                        image_data_b64 = base64_match.group(1)
                        result_image_bytes = base64.b64decode(image_data_b64)
                        logger.info(f'process_tryon: Found image in text (base64), size={len(result_image_bytes)} bytes')
                        break

    if result_image_bytes is None and 'data' in result:
        image_data_b64 = result['data']
        result_image_bytes = base64.b64decode(image_data_b64)
        logger.info(f'process_tryon: Found image in direct data, size={len(result_image_bytes)} bytes')

    if result_image_bytes is not None:
        return ('ok', result_image_bytes)

    if 'candidates' not in result:
        raise ExternalServiceError(
            'Failed to extract image from Gemini API response. Please check logs for details.',
            service='gemini'
        )

    if len(result['candidates']) == 0:
        logger.error('process_tryon: Gemini returned empty candidates array')
        raise ExternalServiceError('Gemini returned empty candidates', service='gemini')

    candidate = result['candidates'][0]
    finish_reason = candidate.get('finishReason', 'UNKNOWN')
    finish_message = candidate.get('finishMessage', '')

    if finish_reason != 'STOP':
        logger.error(f'process_tryon: Gemini finishReason: {finish_reason}')
        if finish_message:
            logger.error(f'process_tryon: Gemini finishMessage: {finish_message}')
        return ('finish', finish_reason, finish_message)

    raise ExternalServiceError(
        'Failed to extract image from Gemini API response. Please check logs for details.',
        service='gemini'
    )


def _tryon_resize_max_long_edge(image_bytes: bytes, max_edge: int) -> bytes:
    """
    If longest side exceeds max_edge, shrink proportionally (LANCZOS).
    Writes PNG. Used to shorten Gemini multimodal payloads (latency vs fidelity trade-off).
    """
    if max_edge <= 0 or not image_bytes:
        return image_bytes
    try:
        img = Image.open(BytesIO(image_bytes))
        w, h = img.size
        long_edge = max(w, h)
        if long_edge <= max_edge:
            return image_bytes
        scale = max_edge / float(long_edge)
        nw = max(1, int(round(w * scale)))
        nh = max(1, int(round(h * scale)))
        if img.mode == 'RGBA':
            pass
        elif img.mode == 'RGB':
            pass
        elif img.mode == 'P' and 'transparency' in img.info:
            img = img.convert('RGBA')
        else:
            img = img.convert('RGB')
        img = img.resize((nw, nh), Image.Resampling.LANCZOS)
        out = BytesIO()
        img.save(out, format='PNG', optimize=True)
        return out.getvalue()
    except Exception as e:
        logger.warning(f'process_tryon: _tryon_resize_max_long_edge skipped: {e}')
        return image_bytes


def process_tryon(person_image: bytes, garment_image: bytes, garment_type: str = 'upper',
                  garment_details: dict = None, options: dict = None) -> str:
    """
    Process try-on using Gemini (Nano Banana) API - PRIMARY SERVICE

    This is the main try-on service using Google's Gemini image generation model.
    While Gemini is a general-purpose model (not specifically trained for virtual try-on),
    we use enhanced prompts to improve garment matching and framing preservation.

    Args:
        person_image: Person image bytes (avatar or selfie with background removed)
        garment_image: Garment image bytes (can be single image or list of images)
        garment_type: 'upper' or 'lower'
        garment_details: Dict with garment info (category, material_type, brand, color, style, etc.)
        options: Additional options (not currently used, kept for compatibility)

    Returns:
        result_url: Base64 data URL of result image

    Raises:
        ExternalServiceError: If processing fails
    """
    logger.info(f"process_tryon: ENTRY - garment_type={garment_type}, garment_details={garment_details}")
    
    try:
        if not Config.GEMINI_API_KEY:
            raise ExternalServiceError("Gemini API key not configured", service='gemini')
        
        # Handle list of images - use only the first one
        if isinstance(garment_image, list):
            garment_image = garment_image[0]
            logger.info(f"process_tryon: Received list of images, using first one only")

        # Focus crop garment image to isolate upper/lower item if full-model photo
        from shared.image_processing import crop_garment_to_relevant_region
        garment_image = crop_garment_to_relevant_region(garment_image, garment_type=garment_type)

        if Config.GEMINI_TRYON_INPUT_MAX_EDGE > 0:
            me = Config.GEMINI_TRYON_INPUT_MAX_EDGE
            p0_len, g0_len = len(person_image), len(garment_image)
            person_image = _tryon_resize_max_long_edge(person_image, me)
            garment_image = _tryon_resize_max_long_edge(garment_image, me)
            if len(person_image) != p0_len or len(garment_image) != g0_len:
                logger.info(
                    'process_tryon: GEMINI_TRYON_INPUT_MAX_EDGE=%s (person bytes %s→%s, garment %s→%s)',
                    me, p0_len, len(person_image), g0_len, len(garment_image),
                )

        # Log image sizes for debugging
        person_size_mb = len(person_image) / (1024 * 1024)
        garment_size_mb = len(garment_image) / (1024 * 1024)
        logger.info(f"process_tryon: Image sizes - person: {person_size_mb:.2f}MB, garment: {garment_size_mb:.2f}MB")
        
        # Convert images to base64
        person_base64 = base64.b64encode(person_image).decode('utf-8')
        garment_base64 = base64.b64encode(garment_image).decode('utf-8')
        
        # Generate deterministic seed from input images for consistent outputs
        # Hash the images together to create a seed that's the same for identical inputs
        input_hash = hashlib.sha256(person_image + garment_image).digest()
        # Convert first 8 bytes to integer for seed (max 64-bit integer)
        seed = int.from_bytes(input_hash[:8], byteorder='big') % (2**31)  # Limit to 32-bit signed int range
        logger.info(f"process_tryon: Generated seed={seed} from input images hash for deterministic output")
        
        # Determine body location text
        body_location = "appropriate body location"
        if garment_details:
            category_section = garment_details.get('category_section')
            if category_section == 'upper_body':
                body_location = "upper body/torso"
            elif category_section == 'lower_body':
                body_location = "lower body/legs"
        elif garment_type == 'upper':
            body_location = "upper body/torso"
        elif garment_type == 'lower':
            body_location = "lower body/legs"
        
        # Build garment details text from available information
        garment_info_parts = []
        if garment_details:
            if garment_details.get('category_name'):
                category_display = garment_details['category_name'].replace('_', ' ').title()
                garment_info_parts.append(f"Category: {category_display}")
            elif garment_details.get('category'):
                category_display = garment_details['category'].replace('_', ' ').title()
                garment_info_parts.append(f"Category: {category_display}")
            
            if garment_details.get('material_type'):
                material_display = garment_details['material_type'].replace('_', ' ').title()
                garment_info_parts.append(f"Material: {material_display}")
            
            if garment_details.get('brand'):
                garment_info_parts.append(f"Brand: {garment_details['brand']}")
            
            if garment_details.get('color'):
                garment_info_parts.append(f"Color: {garment_details['color']}")
            
            if garment_details.get('style'):
                style_display = garment_details['style'].replace('_', ' ').title()
                garment_info_parts.append(f"Style: {style_display}")
        
        # Get input image dimensions and pad to standard aspect ratio
        # Gemini tends to zoom/reframe unusual aspect ratios, so we pad to ~3:4 or 1:1
        # then crop back to original dimensions after processing
        original_width, original_height = None, None
        padded_person_image = person_image
        pad_left, pad_top = 0, 0
        # Pixel size of image 1 actually sent to Gemini (after optional horizontal padding)
        api_canvas_width = None
        api_canvas_height = None

        try:
            person_img = Image.open(BytesIO(person_image))
            original_width, original_height = person_img.size
            input_ratio = original_width / original_height
            logger.info(f"process_tryon: Original person image: {original_width}x{original_height}, ratio={input_ratio:.3f}")
            api_canvas_width, api_canvas_height = original_width, original_height

            # If aspect ratio is very narrow (< 0.6), pad to prevent Gemini from reframing.
            # Previously always padded to a fixed 0.75 (3:4) - for very narrow inputs
            # (e.g. ~0.35) that more than doubled the canvas width, and Gemini appeared
            # to respond to that extreme a transformation by rendering the person
            # notably shorter than full-frame (feet/shoes cut off), even with explicit
            # prompt instructions to preserve them. Capping how much ratio we add (+0.2)
            # rather than jumping straight to a fixed target keeps the transformation
            # proportionally gentler for very narrow inputs, while still adding enough
            # width to discourage reframing/zoom. (Must stay > input_ratio or the
            # "padding" would compute a narrower width than the original.)
            if input_ratio < 0.6:
                target_ratio = min(0.75, input_ratio + 0.2)
                new_width = int(original_height * target_ratio)

                # Create padded canvas with transparent background
                if person_img.mode != 'RGBA':
                    person_img = person_img.convert('RGBA')

                padded_img = Image.new('RGBA', (new_width, original_height), (0, 0, 0, 0))

                # Center the original image on the padded canvas
                pad_left = (new_width - original_width) // 2
                pad_top = 0
                padded_img.paste(person_img, (pad_left, pad_top), person_img)

                # Convert padded image to bytes
                padded_buffer = BytesIO()
                padded_img.save(padded_buffer, format='PNG')
                padded_person_image = padded_buffer.getvalue()

                # Update base64 for API call
                person_base64 = base64.b64encode(padded_person_image).decode('utf-8')

                api_canvas_width, api_canvas_height = new_width, original_height

                logger.info(f"process_tryon: Padded person image to {new_width}x{original_height} (ratio={target_ratio:.3f}), pad_left={pad_left}")

        except Exception as e:
            logger.warning(f"process_tryon: Could not process input dimensions: {e}")
            original_width, original_height = None, None
            api_canvas_width, api_canvas_height = None, None

        if api_canvas_width and api_canvas_height:
            logger.info(
                f"process_tryon: Image 1 (person) canvas for Gemini API: "
                f"{api_canvas_width}x{api_canvas_height}px"
                + (
                    f" (unpadded subject {original_width}x{original_height}, will crop back after generation)"
                    if (original_width and original_height
                        and (api_canvas_width != original_width or api_canvas_height != original_height))
                    else ""
                )
            )

        # Build comprehensive prompt with all garment details
        prompt_parts = [
            "TASK: Virtual try-on - dress the person in image 1 with the garment from image 2.\n\n",
            "CRITICAL FULL-BODY PRESERVATION:\n",
            "- The person's SHOES/FEET touching the ground MUST be visible at the very bottom of the frame, exactly as in Image 1. "
            "Do NOT stop at the ankle, calf, or knee - the legs must extend all the way down to the shoes.\n",
            "- If Image 1 shows a full-body person (head to toe including legs, pants, and shoes), you MUST preserve the full-body framing.\n",
            "- You MUST generate the FULL-BODY of the person from head to toe.\n",
            "- Do NOT crop at the waist, do NOT zoom in, and do NOT generate a half-body or waist-up portrait.\n",
            "- Do NOT render the person shorter or smaller than in Image 1 - the full height from head to shoes must be preserved.\n",
            "- Keep the person's lower body (pants, legs, and shoes) fully visible exactly as shown in Image 1.\n",
            "- Keep BOTH ARMS AND HANDS fully visible within the frame, at the same width/position as Image 1. "
            "Do NOT crop, cut off, or extend the arms beyond the sides of the frame.\n\n"
        ]

        # Add garment details if available
        if garment_info_parts:
            prompt_parts.append(f"GARMENT TO APPLY: {', '.join(garment_info_parts)}.\n")

        prompt_parts.extend([
            f"Apply the garment from image 2 onto the {body_location} of the person in image 1.\n\n",
            "GARMENT MATCHING REQUIREMENTS (CRITICAL):\n",
            "- Reproduce the EXACT garment design from image 2: same sleeve length, neckline, hem length, cuts, and all design details.\n",
            "- Preserve the exact fabric pattern, texture, color, and material appearance.\n",
            "- If the garment has asymmetric elements (one sleeve longer, off-shoulder, etc.), maintain that asymmetry exactly.\n",
            "- Do NOT modify, simplify, or interpret the garment differently - copy it precisely.\n\n",
            "FRAMING AND DIMENSION REQUIREMENTS (CRITICAL):\n",
        ])

        # Add explicit dimension constraint: must match image 1 (what Gemini actually receives).
        # Bug fix: padded inputs used to still ask for original_width x original_height, which
        # contradicts image 1 and often yields finishReason IMAGE_OTHER.
        if api_canvas_width and api_canvas_height:
            prompt_parts.append(
                f"- Output image MUST be exactly {api_canvas_width}x{api_canvas_height} pixels "
                "(same width and height as image 1).\n"
            )

        prompt_parts.extend([
            "- The person's HEAD must be at the EXACT same vertical position (same distance from top edge).\n",
            "- The person's FEET, SHOES, AND LEGS must remain fully visible at the EXACT same position from image 1.\n",
            "- If feet/shoes are visible in image 1, they MUST be visible in the output at the same position.\n",
            "- Maintain full-body camera framing (do not convert full body into a half-body or waist-up portrait).\n",
            "- The person must occupy the SAME area of the frame as in image 1.\n",
            "- Maintain identical aspect ratio, framing, and composition.\n\n",
            "SINGLE PERSON AND COMPOSITION REQUIREMENTS (CRITICAL):\n",
            "- Output ONLY ONE SINGLE PERSON centered in the frame.\n",
            "- Do NOT include any secondary people, background models, mannequin reflections, or extra bodies.\n",
            "- Output ONLY a single edited image (no side-by-side, no before/after comparison).\n",
            "- The garment must look naturally fitted on the person's body.\n",
            "- Preserve the person's pose, face, hair, skin, and any visible accessories.\n"
        ])
        
        prompt = "".join(prompt_parts)

        # Last-resort wording if same-prompt IMAGE_OTHER retries exhaust (fewer contradictory constraints).
        relaxed_parts = [
            "TASK: Virtual try-on.\n\n",
            f"Image 1 shows a person. Image 2 shows a garment.\n"
            f"Edit image 1 so the person wears the garment from image 2 on their {body_location}. "
            "Keep the exact same full-body framing (head to toe including legs, pants, and shoes), pose, face, hair, skin tone, and camera framing as image 1.\n",
            "Do NOT crop at the waist or generate a waist-up shot. Keep the full body and feet visible exactly as in image 1.\n",
            "The shoes/feet touching the ground must be visible at the bottom of the frame - do not stop at the ankle or calf, and do not render the person shorter than in image 1.\n",
            "Keep both arms and hands fully visible within the frame, at the same width as image 1 - do not crop them at the sides.\n\n",
            "Match the garment's colors, patterns, cut, neckline, sleeves, hem, and silhouette from image 2 as faithfully as reasonable.\n",
            "Output one photorealistic full image only. No collage, no before/after split, no text, no labels.\n\n",
        ]
        if garment_info_parts:
            relaxed_parts.insert(1, f"Garment context: {', '.join(garment_info_parts)}.\n")
        prompt_relaxed = "".join(relaxed_parts)

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{Config.GEMINI_MODEL_NAME}:generateContent"
        headers = {"Content-Type": "application/json"}
        params = {"key": Config.GEMINI_API_KEY}

        mod = 2 ** 31
        # True retries use the same prompt; only seed/temperature change (stochastic resample).
        if Config.GEMINI_TRYON_LITE_IMAGE_OTHER_RETRIES:
            generation_attempts = [
                ('deterministic', prompt, seed, 0.0),
                ('relaxed_prompt_fallback', prompt_relaxed, (seed + 1_000_003) % mod, 0.42),
            ]
            logger.info(
                'process_tryon: GEMINI_TRYON_LITE_IMAGE_OTHER_RETRIES enabled '
                '(at most %s Gemini calls on IMAGE_OTHER stall)',
                len(generation_attempts),
            )
        else:
            generation_attempts = [
                ("deterministic", prompt, seed, 0.0),
                ("same_prompt_resample_a", prompt, (seed + 982_451_653) % mod, 0.28),
                ("same_prompt_resample_b", prompt, (seed + 1_629_268_779) % mod, 0.42),
                ("relaxed_prompt_fallback", prompt_relaxed, (seed + 1_000_003) % mod, 0.42),
            ]

        max_retries = 3
        retry_delay = 2
        result_image_bytes = None

        for attempt_idx, (attempt_name, use_prompt, use_seed, use_temp) in enumerate(generation_attempts):
            payload = {
                "contents": [{
                    "parts": [
                        {"text": use_prompt},
                        {"text": "\n[IMAGE 1: PERSON / AVATAR MODEL TO DRESS]\n"},
                        {
                            "inline_data": {
                                "mime_type": "image/png",
                                "data": person_base64,
                            },
                        },
                        {"text": "\n[IMAGE 2: GARMENT / CLOTHING ITEM TO FIT ONTO PERSON IN IMAGE 1]\n"},
                        {
                            "inline_data": {
                                "mime_type": "image/png",
                                "data": garment_base64,
                            },
                        },
                    ],
                }],
                "generationConfig": {
                    "temperature": use_temp,
                    "seed": use_seed,
                    "responseModalities": ["IMAGE"],
                },
            }

            response = None
            for req_attempt in range(max_retries):
                try:
                    response = requests.post(url, json=payload, headers=headers, params=params, timeout=120)
                    if response.status_code == 200:
                        break
                    if response.status_code in (500, 503, 429) and req_attempt < max_retries - 1:
                        wait_time = retry_delay * (req_attempt + 1)
                        logger.warning(
                            f"process_tryon: Gemini API returned {response.status_code} "
                            f"(http_try {req_attempt + 1}/{max_retries}, gen_attempt={attempt_name}). "
                            f"Retrying in {wait_time} seconds..."
                        )
                        time.sleep(wait_time)
                        continue
                    logger.error(
                        f"process_tryon: Gemini API error - status={response.status_code}, "
                        f"response={response.text[:500]}, http_try={req_attempt + 1}/{max_retries}, gen_attempt={attempt_name}"
                    )
                    if req_attempt == max_retries - 1:
                        raise ExternalServiceError(
                            f"Gemini API error: {response.status_code} - {response.text[:200]}",
                            service='gemini',
                        )
                except requests.Timeout:
                    if req_attempt < max_retries - 1:
                        wait_time = retry_delay * (req_attempt + 1)
                        logger.warning(
                            f"process_tryon: Gemini API timeout (http_try {req_attempt + 1}/{max_retries}, "
                            f"gen_attempt={attempt_name}). Retrying in {wait_time} seconds..."
                        )
                        time.sleep(wait_time)
                        continue
                    raise ExternalServiceError("Gemini API timeout after multiple retries", service='gemini')
                except requests.RequestException as e:
                    if req_attempt < max_retries - 1:
                        wait_time = retry_delay * (req_attempt + 1)
                        logger.warning(
                            f"process_tryon: Gemini API request exception: {str(e)} "
                            f"(http_try {req_attempt + 1}/{max_retries}, gen_attempt={attempt_name}). "
                            f"Retrying in {wait_time} seconds..."
                        )
                        time.sleep(wait_time)
                        continue
                    raise

            if response is None or response.status_code != 200:
                error_msg = f"Gemini API failed after {max_retries} attempts (gen_attempt={attempt_name})"
                if response:
                    error_msg += f" - status={response.status_code}, response={response.text[:200]}"
                logger.error(f"process_tryon: {error_msg}")
                raise ExternalServiceError(error_msg, service='gemini')

            result = response.json()
            parsed = _parse_gemini_tryon_image_response(result)
            if parsed[0] == "ok":
                candidate_image_bytes = parsed[1]
                from shared.image_processing import is_image_substantially_unchanged
                if (
                    attempt_idx < len(generation_attempts) - 1
                    and is_image_substantially_unchanged(padded_person_image, candidate_image_bytes)
                ):
                    logger.warning(
                        "process_tryon: Gemini returned an unchanged image on %s (%s/%s); retrying",
                        attempt_name,
                        attempt_idx + 1,
                        len(generation_attempts),
                    )
                    continue
                result_image_bytes = candidate_image_bytes
                if attempt_idx > 0:
                    logger.info(
                        "process_tryon: Gemini succeeded on generation attempt %s/%s (%s)",
                        attempt_idx + 1,
                        len(generation_attempts),
                        attempt_name,
                    )
                break
            if parsed[0] == "finish":
                _, finish_reason, finish_message = parsed
                if finish_reason == "IMAGE_OTHER" and attempt_idx < len(generation_attempts) - 1:
                    logger.warning(
                        "process_tryon: Gemini IMAGE_OTHER on %s (%s/%s); retrying%s (finishMessage=%s)",
                        attempt_name,
                        attempt_idx + 1,
                        len(generation_attempts),
                        (
                            " with identical prompt + new seed/temp"
                            if use_prompt == prompt
                            else " with relaxed prompt fallback"
                        ),
                        (finish_message or "")[:220],
                    )
                    continue
                _raise_gemini_tryon_finish_error(finish_reason, finish_message)

        if result_image_bytes is None:
            raise ExternalServiceError(
                "Failed to extract image from Gemini API response after all generation attempts.",
                service="gemini",
            )

        # Check if background removal is needed
        try:
            result_img = Image.open(BytesIO(result_image_bytes))
            has_transparency = result_img.mode in ('RGBA', 'LA', 'P')
            logger.info(f"process_tryon: Gemini result has transparency: {has_transparency}, mode: {result_img.mode}")
            
            if not has_transparency:
                # Use rembg to remove background
                logger.info("process_tryon: Gemini result has no transparency - using rembg to remove background")
                from rembg import remove  # type: ignore

                result_image_bytes = remove(result_image_bytes, session=_get_rembg_session())
                logger.info(f"process_tryon: rembg processed image, new size={len(result_image_bytes)} bytes")
                
                # Verify and convert rembg result to RGBA if needed
                result_img = Image.open(BytesIO(result_image_bytes))
                if result_img.mode != 'RGBA':
                    result_img = result_img.convert('RGBA')
                
                # Save as PNG
                output = BytesIO()
                result_img.save(output, format='PNG')
                result_image_bytes = output.getvalue()
            elif result_img.mode != 'RGBA':
                # Only convert if not already RGBA (e.g., LA or P mode)
                result_img = result_img.convert('RGBA')
            # Always solidify alpha mask to prevent semi-transparency
            from shared.image_processing import clean_and_solidify_alpha_mask
            result_image_bytes = clean_and_solidify_alpha_mask(result_image_bytes)
        except Exception as processing_error:
            logger.warning(f"process_tryon: Image processing failed: {str(processing_error)}, using Gemini result as-is")
            # Continue with Gemini's result if processing fails

        # Post-processing: Handle padded input and ensure output dimensions match
        if original_width and original_height:
            try:
                result_img = Image.open(BytesIO(result_image_bytes))
                result_width, result_height = result_img.size
                logger.info(f"process_tryon: Gemini output dimensions: {result_width}x{result_height}")

                # Ensure RGBA mode for transparency preservation
                if result_img.mode != 'RGBA':
                    result_img = result_img.convert('RGBA')

                # If we padded the input, we need to extract the center portion
                if pad_left > 0 or pad_top > 0:
                    # Must match dimensions of image 1 sent to the API
                    padded_width = api_canvas_width if api_canvas_width else original_width + (2 * pad_left)
                    padded_height = api_canvas_height if api_canvas_height else original_height + (2 * pad_top)
                    logger.info(f"process_tryon: Input was padded to {padded_width}x{padded_height}, need to extract center {original_width}x{original_height}")

                    # Scale result to fit padded dimensions without cropping body parts
                    if result_width != padded_width or result_height != padded_height:
                        output_ratio = result_width / result_height if result_height > 0 else 1.0
                        target_ratio = padded_width / padded_height if padded_height > 0 else 1.0

                        if abs(output_ratio - target_ratio) < 0.05:
                            result_img = result_img.resize((padded_width, padded_height), Image.Resampling.LANCZOS)
                            logger.info(f"process_tryon: Resized output to match padded canvas: {padded_width}x{padded_height}")
                        else:
                            scale = min(padded_width / float(result_width), padded_height / float(result_height))
                            new_w = int(result_width * scale)
                            new_h = int(result_height * scale)
                            resized_img = result_img.resize((new_w, new_h), Image.Resampling.LANCZOS)

                            canvas = Image.new('RGBA', (padded_width, padded_height), (0, 0, 0, 0))
                            paste_x = (padded_width - new_w) // 2
                            paste_y = (padded_height - new_h) // 2
                            canvas.paste(resized_img, (paste_x, paste_y), resized_img)
                            result_img = canvas
                            logger.info(f"process_tryon: Scaled to fit padded canvas: {padded_width}x{padded_height}")

                    # Crop to extract the original (unpadded) region - but only as a
                    # starting point. Gemini isn't guaranteed to keep the subject
                    # within that exact window (e.g. it may draw arms/hands wider
                    # than the source photo); blindly cropping to it would clip
                    # them. Widen the crop to the actual subject bbox if it extends
                    # beyond the intended window, same "never crop off body parts"
                    # principle already used in the non-padded branch below.
                    crop_left = pad_left
                    crop_top = pad_top
                    crop_right = crop_left + original_width
                    crop_bottom = crop_top + original_height

                    subject_bbox = result_img.getbbox()
                    if subject_bbox:
                        bbox_left, bbox_top, bbox_right, bbox_bottom = subject_bbox
                        crop_left = min(crop_left, bbox_left)
                        crop_top = min(crop_top, bbox_top)
                        crop_right = max(crop_right, bbox_right)
                        crop_bottom = max(crop_bottom, bbox_bottom)

                    result_img = result_img.crop((crop_left, crop_top, crop_right, crop_bottom))
                    logger.info(
                        f"process_tryon: Cropped to {crop_right - crop_left}x{crop_bottom - crop_top} "
                        f"(target was {original_width}x{original_height})"
                    )

                else:
                    # No padding was applied - use original dimension matching logic
                    if result_width != original_width or result_height != original_height:
                        logger.info(f"process_tryon: Dimension mismatch - output {result_width}x{result_height} vs input {original_width}x{original_height}. Adjusting...")

                        output_ratio = result_width / result_height if result_height > 0 else 1.0
                        input_ratio = original_width / original_height if original_height > 0 else 1.0

                        if abs(output_ratio - input_ratio) < 0.05:
                            # Same aspect ratio - simple high-quality resize
                            result_img = result_img.resize((original_width, original_height), Image.Resampling.LANCZOS)
                            logger.info(f"process_tryon: Resized output to match input dimensions (same aspect ratio)")
                        else:
                            # Different aspect ratio - scale to FIT without cropping off body parts
                            scale_w = original_width / float(result_width)
                            scale_h = original_height / float(result_height)
                            scale = min(scale_w, scale_h)

                            new_w = int(result_width * scale)
                            new_h = int(result_height * scale)
                            resized_img = result_img.resize((new_w, new_h), Image.Resampling.LANCZOS)

                            canvas = Image.new('RGBA', (original_width, original_height), (0, 0, 0, 0))
                            paste_x = (original_width - new_w) // 2
                            paste_y = (original_height - new_h) // 2
                            canvas.paste(resized_img, (paste_x, paste_y), resized_img)
                            result_img = canvas
                            logger.info(f"process_tryon: Scaled to fit canvas without cropping body (aspect ratio: {output_ratio:.3f} -> {input_ratio:.3f})")
                    else:
                        logger.info(f"process_tryon: Output dimensions already match input: {result_width}x{result_height}")

                # Ensure minimum output resolution (768px minimum dimension)
                MIN_OUTPUT_DIMENSION = 768
                final_width, final_height = result_img.size
                min_dim = min(final_width, final_height)
                if min_dim < MIN_OUTPUT_DIMENSION:
                    scale = MIN_OUTPUT_DIMENSION / min_dim
                    new_width = int(final_width * scale)
                    new_height = int(final_height * scale)
                    result_img = result_img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                    logger.info(f"process_tryon: Upscaled from {final_width}x{final_height} to {new_width}x{new_height} (min dimension {MIN_OUTPUT_DIMENSION}px)")

                # Save final image
                output = BytesIO()
                result_img.save(output, format='PNG')
                result_image_bytes = output.getvalue()
                
                # Apply normalize_avatar_framing to format final canvas framing nicely
                from shared.image_processing import normalize_avatar_framing
                result_image_bytes = normalize_avatar_framing(result_image_bytes)
                logger.info(f"process_tryon: Final output dimensions after framing: {result_img.size[0]}x{result_img.size[1]}")
            except Exception as resize_error:
                logger.warning(f"process_tryon: Dimension matching failed: {str(resize_error)}, using result as-is")

        # Convert to base64 data URL
        result_base64 = base64.b64encode(result_image_bytes).decode('utf-8')
        result = f"data:image/png;base64,{result_base64}"
        logger.info(f"process_tryon: EXIT - Success, result size={len(result_base64)} chars")
        return result
        
    except requests.RequestException as e:
        logger.exception(f"process_tryon: EXIT - Request failed: {str(e)}")
        raise ExternalServiceError(f"Gemini API request failed: {str(e)}", service='gemini')
    except ExternalServiceError:
        logger.exception("process_tryon: EXIT - ExternalServiceError")
        raise
    except Exception as e:
        logger.exception(f"process_tryon: EXIT - Unexpected error: {str(e)}")
        raise ExternalServiceError(f"Try-on processing failed: {str(e)}", service='gemini')


def process_tryon_layered(person_image: bytes, garment_image: bytes, garment_type: str = 'upper',
                          garment_details: dict = None) -> str:
    """
    Process try-on with LAYERING mode - adds garment OVER existing outfit.

    Use this for layering scenarios like: top + jacket, dress + coat, etc.
    The prompt explicitly tells Gemini to preserve existing clothing.

    Args:
        person_image: Person image bytes (can be previous try-on result with clothing)
        garment_image: Garment image bytes to layer on top
        garment_type: 'upper' or 'lower' or 'outerwear'
        garment_details: Optional dict with garment info

    Returns:
        result_url: Base64 data URL of result image
    """
    logger.info(f"process_tryon_layered: ENTRY - garment_type={garment_type}")

    try:
        if not Config.GEMINI_API_KEY:
            raise ExternalServiceError("Gemini API key not configured", service='gemini')

        # Handle list of images - use only the first one
        if isinstance(garment_image, list):
            garment_image = garment_image[0]

        # Focus crop garment image to isolate upper/lower item if full-model photo
        from shared.image_processing import crop_garment_to_relevant_region
        garment_image = crop_garment_to_relevant_region(garment_image, garment_type=garment_type)

        # Log image sizes
        person_size_mb = len(person_image) / (1024 * 1024)
        garment_size_mb = len(garment_image) / (1024 * 1024)
        logger.info(f"process_tryon_layered: Image sizes - person: {person_size_mb:.2f}MB, garment: {garment_size_mb:.2f}MB")

        # Convert images to base64
        person_base64 = base64.b64encode(person_image).decode('utf-8')
        garment_base64 = base64.b64encode(garment_image).decode('utf-8')

        # Generate seed for consistency
        input_hash = hashlib.sha256(person_image + garment_image).digest()
        seed = int.from_bytes(input_hash[:8], byteorder='big') % (2**31)
        logger.info(f"process_tryon_layered: Generated seed={seed}")

        # Determine garment type description
        garment_type_desc = "garment"
        if garment_type == 'upper' or garment_type == 'outerwear':
            garment_type_desc = "jacket/outerwear/top layer"
        elif garment_type == 'lower':
            garment_type_desc = "bottom layer garment"

        # Build garment details text
        garment_info_parts = []
        if garment_details:
            if garment_details.get('category_name'):
                garment_info_parts.append(f"Type: {garment_details['category_name']}")
            if garment_details.get('brand'):
                garment_info_parts.append(f"Brand: {garment_details['brand']}")
            if garment_details.get('color'):
                garment_info_parts.append(f"Color: {garment_details['color']}")

        # Get input dimensions
        input_width, input_height = None, None
        try:
            person_img = Image.open(BytesIO(person_image))
            input_width, input_height = person_img.size
            logger.info(f"process_tryon_layered: Input dimensions: {input_width}x{input_height}")
        except Exception as e:
            logger.warning(f"process_tryon_layered: Could not get dimensions: {e}")

        # Build LAYERING-specific prompt
        prompt_parts = [
            "TASK: Add a new garment LAYER over the person's existing outfit.\n\n",
            "CRITICAL FULL-BODY PRESERVATION:\n",
            "- If Image 1 shows a full-body person (head to toe including legs, pants, and shoes), you MUST preserve the full-body framing.\n",
            "- You MUST generate the FULL-BODY of the person from head to toe.\n",
            "- Do NOT crop at the waist, do NOT zoom in, and keep lower body (pants, legs, shoes) visible.\n\n",
            "CRITICAL: The person in image 1 is ALREADY WEARING CLOTHES. ",
            "You must PRESERVE their existing outfit and ADD the new garment FROM IMAGE 2 on top.\n\n"
        ]

        if garment_info_parts:
            prompt_parts.append(f"NEW GARMENT TO ADD: {', '.join(garment_info_parts)}.\n\n")

        prompt_parts.extend([
            f"Add the {garment_type_desc} from image 2 OVER the person's current clothing.\n\n",
            "LAYERING REQUIREMENTS (CRITICAL):\n",
            "- DO NOT remove or replace the person's existing clothes - they stay visible underneath.\n",
            "- The new garment goes ON TOP of what they're already wearing.\n",
            "- If adding a jacket over a shirt, the shirt collar/sleeves may peek out - this is correct.\n",
            "- If adding outerwear, it should look like they put it on over their current outfit.\n\n",
            "GARMENT MATCHING REQUIREMENTS:\n",
            "- Reproduce the EXACT garment design from image 2: same style, cut, details.\n",
            "- Preserve the exact fabric pattern, texture, color, and material appearance.\n",
            "- The garment must fit naturally over the existing clothes.\n\n",
            "FRAMING REQUIREMENTS:\n",
        ])

        if input_width and input_height:
            prompt_parts.append(f"- Output image MUST be exactly {input_width}x{input_height} pixels.\n")

        prompt_parts.extend([
            "- Keep the person's HEAD at the EXACT same position (same distance from top).\n",
            "- Keep the person's FEET, SHOES, AND LEGS at the EXACT same position from image 1.\n",
            "- Do NOT zoom, crop, or change the framing in any way.\n",
            "- Maintain full-body camera framing (do not convert full body into a half-body or waist-up portrait).\n",
            "- Do NOT cut off any body parts.\n\n",
            "OUTPUT:\n",
            "- Single edited image showing the person wearing their original outfit WITH the new garment layered on top.\n",
            "- Preserve face, hair, pose, and all original details.\n"
        ])

        prompt = "".join(prompt_parts)

        # Call Gemini API
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{Config.GEMINI_MODEL_NAME}:generateContent"

        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": Config.GEMINI_API_KEY
        }

        payload = {
            "contents": [{
                "parts": [
                    {"text": prompt},
                    {"text": "\n[IMAGE 1: PERSON / AVATAR MODEL TO DRESS]\n"},
                    {
                        "inline_data": {
                            "mime_type": "image/png",
                            "data": person_base64
                        }
                    },
                    {"text": "\n[IMAGE 2: GARMENT / CLOTHING ITEM TO FIT ONTO PERSON IN IMAGE 1]\n"},
                    {
                        "inline_data": {
                            "mime_type": "image/png",
                            "data": garment_base64
                        }
                    }
                ]
            }],
            "generationConfig": {
                "responseModalities": ["image", "text"],
                "temperature": 0.2,
                "seed": seed
            }
        }

        # Make API call with retries
        max_retries = 2
        last_error = None

        for attempt in range(max_retries + 1):
            try:
                logger.info(f"process_tryon_layered: API call attempt {attempt + 1}/{max_retries + 1}")
                response = requests.post(url, headers=headers, json=payload, timeout=120)

                if response.status_code == 200:
                    result = response.json()

                    # Extract image from response
                    if 'candidates' in result and len(result['candidates']) > 0:
                        candidate = result['candidates'][0]
                        if 'content' in candidate and 'parts' in candidate['content']:
                            for part in candidate['content']['parts']:
                                if 'inlineData' in part:
                                    raw_b64 = part['inlineData']['data']
                                    raw_bytes = base64.b64decode(raw_b64)
                                    from rembg import remove  # type: ignore
                                    try:
                                        raw_bytes = remove(raw_bytes, session=_get_rembg_session())
                                    except Exception as bg_err:
                                        logger.warning(f"process_tryon_layered: rembg error: {bg_err}")
                                    from shared.image_processing import clean_and_solidify_alpha_mask
                                    processed_bytes = clean_and_solidify_alpha_mask(raw_bytes)
                                    new_b64 = base64.b64encode(processed_bytes).decode('utf-8')
                                    result_url = f"data:image/png;base64,{new_b64}"
                                    logger.info(f"process_tryon_layered: EXIT - Success (normalized framing)")
                                    return result_url

                    raise ExternalServiceError("No image in Gemini response", service='gemini')

                elif response.status_code in [429, 500, 502, 503]:
                    # Retryable errors
                    last_error = f"HTTP {response.status_code}"
                    if attempt < max_retries:
                        wait_time = (attempt + 1) * 5
                        logger.warning(f"process_tryon_layered: {last_error}, retrying in {wait_time}s")
                        time.sleep(wait_time)
                        continue
                else:
                    error_text = response.text[:500]
                    raise ExternalServiceError(f"Gemini API error {response.status_code}: {error_text}", service='gemini')

            except requests.Timeout:
                last_error = "Timeout"
                if attempt < max_retries:
                    logger.warning(f"process_tryon_layered: Timeout, retrying...")
                    continue
                raise ExternalServiceError("Gemini API timeout", service='gemini')

        raise ExternalServiceError(f"Gemini API failed after retries: {last_error}", service='gemini')

    except ExternalServiceError:
        raise
    except Exception as e:
        logger.exception(f"process_tryon_layered: EXIT - Error: {str(e)}")
        raise ExternalServiceError(f"Layered try-on failed: {str(e)}", service='gemini')


def remove_background(image_data: bytes) -> bytes:
    """
    Remove background from image using Gemini API
    
    Args:
        image_data: Image bytes
        
    Returns:
        Image bytes with background removed (transparent PNG in RGBA format)
        
    Raises:
        ExternalServiceError: If processing fails
    """
    logger.info("remove_background: ENTRY")
    
    try:
        if not Config.GEMINI_API_KEY:
            raise ExternalServiceError("Gemini API key not configured", service='gemini')
        
        # Convert image to base64
        image_base64 = base64.b64encode(image_data).decode('utf-8')
        
        # Prepare prompt for background removal - explicitly request transparent background
        # Use a more specific prompt that requests image output
        prompt = """Remove the background from this image, keeping only the person/subject visible. 
Make the background completely transparent using an alpha channel. 
Return ONLY a PNG image with RGBA format where:
- Background pixels have alpha=0 (fully transparent)
- Person/subject pixels have alpha=255 (fully opaque)
- The image should be in PNG format with transparency support."""
        
        # Call Gemini API for image editing
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{Config.GEMINI_MODEL_NAME}:generateContent"
        
        payload = {
            "contents": [{
                "parts": [
                    {"text": prompt},
                    {
                        "inline_data": {
                            "mime_type": "image/png",
                            "data": image_base64
                        }
                    }
                ]
            }]
            # Note: Gemini generateContent API may not support response_mime_type for images
            # We'll handle the response format dynamically
        }
        
        headers = {
            "Content-Type": "application/json",
        }
        
        params = {
            "key": Config.GEMINI_API_KEY
        }
        
        logger.info(f"remove_background: Calling Gemini API - model={Config.GEMINI_MODEL_NAME}")
        # Increase timeout to 600 seconds (10 minutes) for image processing
        # Gemini API can take longer for image generation/editing tasks
        response = requests.post(url, json=payload, headers=headers, params=params, timeout=600)
        
        if response.status_code != 200:
            logger.error(f"remove_background: Gemini API error - status={response.status_code}, response={response.text[:500]}")
            raise ExternalServiceError(
                f"Gemini API error: {response.status_code} - {response.text[:200]}",
                service='gemini'
            )
        
        # Parse response - Gemini returns base64 encoded image in response
        result = response.json()
        logger.debug(f"remove_background: Response structure keys: {list(result.keys())}")
        
        image_bytes = None
        
        # Extract image from response - try multiple response formats
        # Format 1: Standard Gemini format with candidates
        if 'candidates' in result and len(result['candidates']) > 0:
            candidate = result['candidates'][0]
            if 'content' in candidate and 'parts' in candidate['content']:
                for part in candidate['content']['parts']:
                    # Check for inline_data (snake_case) - standard Gemini format
                    if 'inline_data' in part and 'data' in part['inline_data']:
                        image_data_b64 = part['inline_data']['data']
                        image_bytes = base64.b64decode(image_data_b64)
                        logger.info(f"remove_background: Found image in inline_data, size={len(image_bytes)} bytes")
                        break
                    # Check for inlineData (camelCase) - Nano Banana image model format
                    if 'inlineData' in part and 'data' in part['inlineData']:
                        image_data_b64 = part['inlineData']['data']
                        image_bytes = base64.b64decode(image_data_b64)
                        logger.info(f"remove_background: Found image in inlineData, size={len(image_bytes)} bytes")
                        break
                    # Also check for text response that might contain base64
                    if 'text' in part:
                        text_content = part['text']
                        logger.debug(f"remove_background: Found text content, length={len(text_content)}")
                        # Try to extract base64 from text
                        base64_match = re.search(r'data:image/[^;]+;base64,([A-Za-z0-9+/=]+)', text_content)
                        if base64_match:
                            image_data_b64 = base64_match.group(1)
                            image_bytes = base64.b64decode(image_data_b64)
                            logger.info(f"remove_background: Found image in text (base64), size={len(image_bytes)} bytes")
                            break
                        else:
                            # Log text content for debugging - this is likely the issue
                            logger.error(f"remove_background: Gemini returned TEXT instead of IMAGE. Text content: {text_content[:500]}")
                            logger.error(f"remove_background: This indicates Gemini's generateContent API does not support image generation/editing.")
                            logger.error(f"remove_background: Gemini generateContent is for text generation, not image editing.")
                            raise ExternalServiceError(
                                f"Gemini API returned text instead of an image. The generateContent API does not support image generation/editing. "
                                f"Text response: {text_content[:200]}... "
                                f"Please use /api/save-avatar-local for PIL-based background removal.",
                                service='gemini'
                            )
        
        # Format 2: Direct response with image data
        if image_bytes is None and 'data' in result:
            image_data_b64 = result['data']
            image_bytes = base64.b64decode(image_data_b64)
            logger.info(f"remove_background: Found image in direct data, size={len(image_bytes)} bytes")
        
        # If no image found, log full response and raise error
        if image_bytes is None:
            logger.error(f"remove_background: No image found in response. Full response structure: {str(result)[:1000]}")
            raise ExternalServiceError(
                "Gemini API did not return an image. The API may not support image generation/editing. "
                "Response: " + str(result)[:500],
                service='gemini'
            )
        
        # Verify that Gemini returned a valid image
        # We trust Gemini's output - no additional PIL processing
        try:
            img = Image.open(BytesIO(image_bytes))
            original_mode = img.mode
            logger.info(f"remove_background: Gemini returned image, mode={original_mode}, size={img.size}")
            
            # Convert to RGBA if needed (preserve any existing transparency)
            if img.mode not in ('RGBA', 'LA', 'P'):
                logger.warning(f"remove_background: Gemini returned {img.mode} mode (no transparency). Converting to RGBA.")
                img = img.convert('RGBA')
            elif img.mode == 'P':
                img = img.convert('RGBA')
            elif img.mode == 'LA':
                img = img.convert('RGBA')
            
            # Save as PNG with transparency preserved
            output = BytesIO()
            img.save(output, format='PNG')
            image_bytes = output.getvalue()
            
            logger.info(f"remove_background: EXIT - Success, result size={len(image_bytes)} bytes, mode=RGBA")
            return image_bytes
        
        except Exception as img_error:
            logger.exception(f"remove_background: Error processing Gemini image: {str(img_error)}")
            # If image processing fails, return the original bytes
            logger.warning(f"remove_background: Returning image bytes as-is due to processing error")
            return image_bytes
        
    except requests.Timeout:
        logger.exception(f"remove_background: EXIT - Gemini API timeout after 600 seconds")
        raise ExternalServiceError("Gemini API timeout after 600 seconds. Please try again or use /api/save-avatar-local for PIL-based background removal.", service='gemini')
    except requests.RequestException as e:
        logger.exception(f"remove_background: EXIT - Request failed: {str(e)}")
        raise ExternalServiceError(f"Gemini API request failed: {str(e)}. Please try /api/save-avatar-local for PIL-based background removal.", service='gemini')
    except ExternalServiceError:
        logger.exception("remove_background: EXIT - ExternalServiceError")
        raise
    except Exception as e:
        logger.exception(f"remove_background: EXIT - Unexpected error: {str(e)}")
        raise ExternalServiceError(f"Background removal failed: {str(e)}", service='gemini')


def _remove_background_local(image_data: bytes) -> bytes:
    """
    Local background removal using rembg (fallback when Gemini API fails)
    
    Args:
        image_data: Image bytes
        
    Returns:
        Image bytes with background removed (transparent PNG in RGBA format)
    """
    logger.info("_remove_background_local: ENTRY - Using rembg for local background removal")

    try:
        from rembg import remove  # type: ignore

        result = remove(image_data, session=_get_rembg_session())
        logger.info(f"_remove_background_local: EXIT - Success, result size={len(result)} bytes")
        return result
    except Exception as e:
        logger.exception(f"_remove_background_local: EXIT - Error: {str(e)}")
        raise ExternalServiceError(f"Local background removal failed: {str(e)}", service='local')
