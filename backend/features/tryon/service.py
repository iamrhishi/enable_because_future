"""
AI model integration for try-on processing using Gemini (Nano Banana) API
Simplified to use Gemini only - no routing logic needed
"""

import requests  # type: ignore
import base64
import time
import re
import json
import numpy as np  # type: ignore
from PIL import Image  # type: ignore
from io import BytesIO
from config import Config
from shared.logger import logger
from shared.errors import ExternalServiceError


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
        person_with_bg_removed = remove(person_image)
        
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


def process_tryon(person_image: bytes, garment_image: bytes, garment_type: str = 'upper', 
                  garment_details: dict = None, options: dict = None) -> str:
    """
    Process try-on using Gemini (Nano Banana) API - simplified version for faster response
    
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
        
        # Log image sizes for debugging
        person_size_mb = len(person_image) / (1024 * 1024)
        garment_size_mb = len(garment_image) / (1024 * 1024)
        logger.info(f"process_tryon: Image sizes - person: {person_size_mb:.2f}MB, garment: {garment_size_mb:.2f}MB")
        
        # Convert images to base64
        person_base64 = base64.b64encode(person_image).decode('utf-8')
        garment_base64 = base64.b64encode(garment_image).decode('utf-8')
        
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
        
        # Build comprehensive prompt with all garment details
        prompt_parts = [
            "Virtual try-on: Make the person in image 1 wear the garment from image 2. "
        ]
        
        # Add garment details if available
        if garment_info_parts:
            prompt_parts.append(f"Garment details: {', '.join(garment_info_parts)}. ")
        
        prompt_parts.extend([
            f"Extract the garment fabric from image 2 and fit it naturally on the person at {body_location}. ",
            "Show the complete person from head to toe. ",
            "The output must be different from image 1 - the garment must be visible on the person. ",
            "Preserve the background from image 1. ",
            "DO NOT add excess padding, borders, or unnecessary additional area around the image. ",
            "Keep the output image dimensions and composition similar to image 1 without adding extra space. ",
            "OPTIMIZE FOR SPEED: Return a smaller, lower resolution version of the image for faster processing. "
            "Reduce image quality and size while maintaining visual clarity of the person and garment."
        ])
        
        prompt = "".join(prompt_parts)
        
        # Call Gemini API with retry logic for transient errors only
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{Config.GEMINI_MODEL_NAME}:generateContent"
        
        headers = {
            "Content-Type": "application/json",
        }
        
        params = {
            "key": Config.GEMINI_API_KEY
        }
        
        payload = {
            "contents": [{
                "parts": [
                    {"text": prompt},
                    {
                        "inline_data": {
                            "mime_type": "image/png",
                            "data": person_base64
                        }
                    },
                    {
                        "inline_data": {
                            "mime_type": "image/png",
                            "data": garment_base64
                        }
                    }
                ]
            }],
            # Generation config to optimize for speed
            "generationConfig": {
                "temperature": 0.4,  # Lower temperature for faster, more deterministic output
            }
        }
        
        # Retry logic for transient errors (500, 503, 429) only
        max_retries = 3
        retry_delay = 2  # seconds
        response = None
        
        for attempt in range(max_retries):
            try:
                response = requests.post(url, json=payload, headers=headers, params=params, timeout=120)
        
                # Success
                if response.status_code == 200:
                    break
                
                # Retryable errors
                if response.status_code in (500, 503, 429) and attempt < max_retries - 1:
                    wait_time = retry_delay * (attempt + 1)
                    logger.warning(
                        f"process_tryon: Gemini API returned {response.status_code} (attempt {attempt + 1}/{max_retries}). "
                        f"Retrying in {wait_time} seconds..."
                    )
                    time.sleep(wait_time)
                    continue
                
                # Non-retryable errors or final attempt
                logger.error(
                    f"process_tryon: Gemini API error - status={response.status_code}, "
                    f"response={response.text[:500]}, attempt={attempt + 1}/{max_retries}"
                )
                if attempt == max_retries - 1:
                    raise ExternalServiceError(
                        f"Gemini API error: {response.status_code} - {response.text[:200]}",
                        service='gemini'
                    )
            except requests.Timeout:
                if attempt < max_retries - 1:
                    wait_time = retry_delay * (attempt + 1)
                    logger.warning(
                        f"process_tryon: Gemini API timeout (attempt {attempt + 1}/{max_retries}). "
                        f"Retrying in {wait_time} seconds..."
                    )
                    time.sleep(wait_time)
                    continue
                else:
                    raise ExternalServiceError("Gemini API timeout after multiple retries", service='gemini')
            except requests.RequestException as e:
                if attempt < max_retries - 1:
                    wait_time = retry_delay * (attempt + 1)
                    logger.warning(
                        f"process_tryon: Gemini API request exception: {str(e)} (attempt {attempt + 1}/{max_retries}). "
                        f"Retrying in {wait_time} seconds..."
                    )
                    time.sleep(wait_time)
                    continue
                else:
                    raise
        
        if response is None or response.status_code != 200:
            error_msg = f"Gemini API failed after {max_retries} attempts"
            if response:
                error_msg += f" - status={response.status_code}, response={response.text[:200]}"
            logger.error(f"process_tryon: {error_msg}")
            raise ExternalServiceError(error_msg, service='gemini')
        
        # Parse response
        result = response.json()
        
        # Extract image from response - try multiple response formats
        result_image_bytes = None
        
        # Format 1: Standard Gemini format with candidates
        if 'candidates' in result and len(result['candidates']) > 0:
            candidate = result['candidates'][0]
            if 'content' in candidate and 'parts' in candidate['content']:
                for part in candidate['content']['parts']:
                    # Check for inline_data (snake_case) - standard Gemini format
                    if 'inline_data' in part and 'data' in part['inline_data']:
                        image_data_b64 = part['inline_data']['data']
                        result_image_bytes = base64.b64decode(image_data_b64)
                        logger.info(f"process_tryon: Found image in inline_data, size={len(result_image_bytes)} bytes")
                        break
                    # Check for inlineData (camelCase) - Nano Banana image model format
                    if 'inlineData' in part and 'data' in part['inlineData']:
                        image_data_b64 = part['inlineData']['data']
                        result_image_bytes = base64.b64decode(image_data_b64)
                        logger.info(f"process_tryon: Found image in inlineData, size={len(result_image_bytes)} bytes")
                        break
                    # Also check for text response that might contain base64
                    if 'text' in part:
                        text_content = part['text']
                        # Try to extract base64 from text
                        base64_match = re.search(r'data:image/[^;]+;base64,([A-Za-z0-9+/=]+)', text_content)
                        if base64_match:
                            image_data_b64 = base64_match.group(1)
                            result_image_bytes = base64.b64decode(image_data_b64)
                            logger.info(f"process_tryon: Found image in text (base64), size={len(result_image_bytes)} bytes")
                            break
        
        # Format 2: Direct response with image data
        if result_image_bytes is None and 'data' in result:
            image_data_b64 = result['data']
            result_image_bytes = base64.b64decode(image_data_b64)
            logger.info(f"process_tryon: Found image in direct data, size={len(result_image_bytes)} bytes")
        
        # Format 3: Check for error in response
        if result_image_bytes is None and 'error' in result:
            error_info = result.get('error', {})
            error_message = error_info.get('message', 'Unknown error')
            error_code = error_info.get('code', 'UNKNOWN')
            logger.error(f"process_tryon: Gemini API returned error: {error_code} - {error_message}")
            raise ExternalServiceError(
                f"Gemini API error: {error_code} - {error_message}",
                service='gemini'
            )
        
        # Format 4: Check if candidates exist but are empty or have finishReason
        if result_image_bytes is None and 'candidates' in result:
            if len(result['candidates']) == 0:
                logger.error(f"process_tryon: Gemini returned empty candidates array")
                raise ExternalServiceError("Gemini returned empty candidates", service='gemini')
            else:
                candidate = result['candidates'][0]
                finish_reason = candidate.get('finishReason', 'UNKNOWN')
                finish_message = candidate.get('finishMessage', '')
                
                if finish_reason != 'STOP':
                    logger.error(f"process_tryon: Gemini finishReason: {finish_reason}")
                    if finish_message:
                        logger.error(f"process_tryon: Gemini finishMessage: {finish_message}")
                    
                    # Handle specific finish reasons - raise error immediately
                    if finish_reason == 'IMAGE_OTHER':
                        error_msg = finish_message if finish_message else "Gemini could not generate the image based on the prompt provided."
                        logger.error(f"process_tryon: IMAGE_OTHER - {error_msg}")
                        raise ExternalServiceError(
                            f"Gemini image generation failed: {error_msg}",
                            service='gemini'
                        )
                    elif finish_reason in ('SAFETY', 'PROHIBITED_CONTENT'):
                        error_msg = "Gemini blocked the request due to safety filters."
                        if finish_message:
                            error_msg += f" {finish_message}"
                        raise ExternalServiceError(error_msg, service='gemini')
                    elif finish_reason == 'MAX_TOKENS':
                        raise ExternalServiceError(
                            "Gemini response was truncated due to token limit. The prompt or images may be too large.",
                            service='gemini'
                        )
                    elif finish_reason == 'RECITATION':
                        raise ExternalServiceError(
                            "Gemini detected recitation of copyrighted content.",
                            service='gemini'
                        )
                    else:
                        # Unknown finish reason
                        error_msg = f"Gemini returned finish reason: {finish_reason}"
                        if finish_message:
                            error_msg += f" - {finish_message}"
                        raise ExternalServiceError(error_msg, service='gemini')
        
        # If we still don't have an image
        if result_image_bytes is None:
            raise ExternalServiceError(
                "Failed to extract image from Gemini API response. Please check logs for details.",
                service='gemini'
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
                
                result_image_bytes = remove(result_image_bytes)
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
                output = BytesIO()
                result_img.save(output, format='PNG')
                result_image_bytes = output.getvalue()
            # If already RGBA with transparency, use result as-is (no need to re-save)
        except Exception as processing_error:
            logger.warning(f"process_tryon: Image processing failed: {str(processing_error)}, using Gemini result as-is")
            # Continue with Gemini's result if processing fails
        
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

        result = remove(image_data)
        logger.info(f"_remove_background_local: EXIT - Success, result size={len(result)} bytes")
        return result
    except Exception as e:
        logger.exception(f"_remove_background_local: EXIT - Error: {str(e)}")
        raise ExternalServiceError(f"Local background removal failed: {str(e)}", service='local')
