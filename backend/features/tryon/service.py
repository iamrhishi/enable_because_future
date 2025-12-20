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


def _crop_to_aspect_ratio(img: Image.Image, target_ratio: float, person_center_x: float = None) -> Image.Image:
    """
    Crop image to match target aspect ratio using center crop (or person-aware crop if person_center_x provided)
    
    Args:
        img: PIL Image to crop
        target_ratio: Target aspect ratio (width / height)
        person_center_x: Optional person center X coordinate for person-aware cropping
        
    Returns:
        Cropped PIL Image matching target aspect ratio
    """
    w, h = img.size
    current_ratio = w / h if h > 0 else 1.0
    
    if abs(current_ratio - target_ratio) < 0.001:  # Already matches (within 0.1% tolerance)
        return img
    
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
    Process try-on using Gemini (Nano Banana) API
    
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
        
        # Handle list of images - use only the first one (revert to single image approach that was working)
        if isinstance(garment_image, list):
            garment_image = garment_image[0]  # Use first image only
            logger.info(f"process_tryon: Received list of {len(garment_image)} images, using first one only")
        
        # Log image sizes for debugging
        person_size_mb = len(person_image) / (1024 * 1024)
        garment_size_mb = len(garment_image) / (1024 * 1024)
        logger.info(f"process_tryon: Image sizes - person: {person_size_mb:.2f}MB, garment: {garment_size_mb:.2f}MB")
        
        # Capture original avatar dimensions to ensure result matches (prevents size mismatch)
        person_img = Image.open(BytesIO(person_image))
        original_avatar_size = person_img.size  # (width, height)
        original_avatar_aspect = original_avatar_size[0] / original_avatar_size[1]
        logger.info(f"process_tryon: Original avatar dimensions: {original_avatar_size}, aspect_ratio: {original_avatar_aspect:.3f}")
        
        # Detect person boundaries using rembg
        person_info = _detect_person_boundaries(person_image)
        logger.info(f"process_tryon: Person boundaries - bbox: {person_info['bbox']}, center: {person_info['center']}, "
                  f"scale: {person_info['scale']}, aspect_ratio: {person_info['aspect_ratio']:.3f}")
        
        # Convert images to base64
        person_base64 = base64.b64encode(person_image).decode('utf-8')
        garment_base64 = base64.b64encode(garment_image).decode('utf-8')
        
        # Log base64 sizes
        person_b64_size_mb = len(person_base64) / (1024 * 1024)
        garment_b64_size_mb = len(garment_base64) / (1024 * 1024)
        logger.info(f"process_tryon: Base64 sizes - person: {person_b64_size_mb:.2f}MB, garment: {garment_b64_size_mb:.2f}MB")
        
        # Build prompt with garment details - direct and technical approach
        # Extract category information from garment_details
        category_section = None
        category_name = None
        if garment_details:
            category_section = garment_details.get('category_section')
            category_name = garment_details.get('category_name')
        
        # Build category information text
        garment_category_text = ""
        if category_section and category_name:
            # Use actual category section and category name
            section_display = category_section.replace('_', ' ').title()  # 'upper_body' -> 'Upper Body'
            category_display = category_name.replace('_', ' ').title()  # 't_shirts' -> 'T Shirts'
            garment_category_text = f"GARMENT INFORMATION: Category Section = {section_display}, Category = {category_display}. "
            if category_section == 'upper_body':
                garment_category_text += f"This is an upper body garment (specifically a {category_display}) that goes on the torso/upper body. "
            elif category_section == 'lower_body':
                garment_category_text += f"This is a lower body garment (specifically a {category_display}) that goes on the legs/lower body. "
        elif garment_type:
            # Fallback to garment_type if category info not available
            garment_category_text = f"GARMENT TYPE: {garment_type.upper()} BODY ("
            if garment_type == 'upper':
                garment_category_text += "shirt, jacket, hoodie, top, etc. - goes on upper body/torso). "
            else:
                garment_category_text += "pants, jeans, shorts, etc. - goes on lower body/legs). "
        
        # Determine body location text
        body_location = "appropriate body location"
        if category_section == 'upper_body':
            body_location = "upper body/torso"
        elif category_section == 'lower_body':
            body_location = "lower body/legs"
        elif garment_type == 'upper':
            body_location = "upper body/torso"
        elif garment_type == 'lower':
            body_location = "lower body/legs"
        
        # Build person positioning info for prompt
        person_position_text = ""
        if person_info:
            bbox_x, bbox_y, bbox_w, bbox_h = person_info['bbox']
            center_x, center_y = person_info['center']
            width_ratio, height_ratio = person_info['scale']
            aspect_ratio = person_info['aspect_ratio']
            person_position_text = (
                f"PERSON POSITIONING INFO: The person in image 1 is centered at ({center_x}, {center_y}) pixels, "
                f"with bounding box ({bbox_x}, {bbox_y}, {bbox_w}, {bbox_h}) pixels. "
                f"The person occupies {width_ratio*100:.1f}% of image width and {height_ratio*100:.1f}% of image height. "
                f"The person's aspect ratio is {aspect_ratio:.3f}. "
                f"Maintain this exact positioning, scale, and aspect ratio in the output. "
            )
        
        prompt_parts = [
            "CRITICAL INSTRUCTIONS - READ FIRST:",
            "",
            f"OUTPUT IMAGE SIZE: EXACTLY {original_avatar_size[0]} pixels wide × {original_avatar_size[1]} pixels tall (same as image 1).",
            f"PERSON VISIBILITY: Show the COMPLETE person from head to toe - ALL body parts including legs and feet must be visible.",
            "",
            "TASK: Virtual try-on - Make the person in image 1 wear the garment from image 2. ",
            "",
            garment_category_text,
            "",
            person_position_text,
            "",
            "ABSOLUTE REQUIREMENTS (MUST FOLLOW EXACTLY):",
            "",
            "1. OUTPUT DIMENSIONS (CRITICAL - MUST MATCH - NO EXCEPTIONS): ",
            f"   - The output image MUST be EXACTLY {original_avatar_size[0]} pixels wide and {original_avatar_size[1]} pixels tall. ",
            f"   - This is the EXACT same size as image 1. DO NOT change these dimensions. ",
            f"   - DO NOT add padding, borders, or resize. Output must be {original_avatar_size[0]}x{original_avatar_size[1]}. ",
            f"   - Width: {original_avatar_size[0]} pixels. Height: {original_avatar_size[1]} pixels. ",
            "   - If you return any other dimensions, the output will be REJECTED. ",
            "",
            "2. PERSON (MANDATORY - HIGHEST PRIORITY - DO NOT CROP OR ZOOM): ",
            "   - Keep image 1's person COMPLETELY unchanged and FULLY visible in the output. ",
            "   - Preserve the ENTIRE person: face, head, neck, shoulders, torso, arms, hands, waist, legs, knees, ankles, feet - EVERY body part. ",
            "   - DO NOT crop, cut off, zoom in, or hide ANY part of the person. ",
            "   - DO NOT focus on just the garment area - show the FULL person from head to toe. ",
            "   - The person's complete body must be visible in the output, exactly as shown in image 1. ",
            "   - CRITICAL: If image 1 shows the person's feet, the output MUST show feet. If image 1 shows full legs, the output MUST show full legs. ",
            "   - CRITICAL: The person's legs and feet are visible in image 1 - they MUST be fully visible in the output. DO NOT crop or cut off the legs. ",
            "   - The person must appear at the SAME scale and position as in image 1. ",
            f"   - The person in image 1 occupies {person_info['scale'][0]*100:.1f}% width and {person_info['scale'][1]*100:.1f}% height. Maintain this exact scale. ",
            f"   - The person's bounding box is ({person_info['bbox'][0]}, {person_info['bbox'][1]}, {person_info['bbox'][2]}, {person_info['bbox'][3]}). Keep the person in the same position. ",
            f"   - The person's height in image 1 is {person_info['bbox'][3]} pixels. The output must show the full {person_info['bbox'][3]} pixels of the person's height. ",
            "   - DO NOT zoom in on the upper body or garment area - the full person from head to toe must be visible. ",
            "   - WARNING: If you crop or zoom the person, the output will be REJECTED. The full person must be visible. ",
            "",
            "3. BACKGROUND (MANDATORY): ",
            "   - Copy image 1's background EXACTLY pixel-by-pixel. ",
            "   - DO NOT add any padding, borders, or extra space. ",
            "   - DO NOT change background dimensions. ",
            "   - Background must be IDENTICAL to image 1 - same size, same pixels. ",
            "",
            f"4. GARMENT: ",
            "   - Extract only the clothing fabric from image 2 (no body parts, no models, no people). ",
            "   - Fit the garment onto the person at {body_location} ONLY. ",
            "   - Apply 3D transformation to wrap the garment around the body naturally. ",
            "   - The garment should follow body contours, pose, and perspective. ",
            "   - Add proper depth, shadows, and highlights for realistic appearance. ",
            "   - Only modify pixels in the garment area - do NOT touch the person, background, or any other area. ",
            "",
            "FINAL OUTPUT CHECKLIST:",
            f"- Image dimensions: EXACTLY {original_avatar_size[0]}x{original_avatar_size[1]} pixels (same as image 1). ",
            "- Full person visible: head to toe, all body parts, same scale as image 1. ",
            "- Background: identical to image 1, pixel-by-pixel. ",
            "- Format: PNG with RGBA channels. ",
            "- NO padding, NO borders, NO cropping, NO compression. "
        ]
        
        # Add garment details to prompt if provided
        if garment_details:
            details_text = "Additional garment information: "
            if garment_details.get('category'):
                details_text += f"Category: {garment_details['category']}. "
            if garment_details.get('material_type'):
                details_text += f"Material: {garment_details['material_type']}. "
            if garment_details.get('brand'):
                details_text += f"Brand: {garment_details['brand']}. "
            if garment_details.get('color'):
                details_text += f"Color: {garment_details['color']}. "
            if garment_details.get('style'):
                details_text += f"Style: {garment_details['style']}. "
            prompt_parts.append("")
            prompt_parts.append(details_text)
        
        prompt = "".join(prompt_parts)
        
        # Log full prompt and all details being sent
        logger.info("=" * 80)
        logger.info("process_tryon: FULL PROMPT BEING SENT TO GEMINI:")
        logger.info("-" * 80)
        logger.info(prompt)
        logger.info("-" * 80)
        logger.info(f"process_tryon: Prompt length: {len(prompt)} characters")
        
        # Log garment details if provided
        if garment_details:
            logger.info("process_tryon: GARMENT DETAILS BEING SENT:")
            logger.info(f"  - garment_type: {garment_type}")
            logger.info(f"  - category_section: {category_section}")
            logger.info(f"  - category_name: {category_name}")
            logger.info(f"  - full garment_details: {garment_details}")
        else:
            logger.info("process_tryon: No garment_details provided")
        
        # Check if payload might be too large (Gemini has limits)
        total_payload_size = len(person_base64) + len(garment_base64) + len(prompt)
        total_payload_size_mb = total_payload_size / (1024 * 1024)
        logger.info(f"process_tryon: Total payload size: {total_payload_size_mb:.2f}MB")
        
        if total_payload_size_mb > 20:  # Gemini typically has ~20MB limit
            logger.warning(f"process_tryon: Payload size ({total_payload_size_mb:.2f}MB) may exceed Gemini limits")
        
        # Call Gemini API
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{Config.GEMINI_MODEL_NAME}:generateContent"
        
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
            }]
        }
        
        headers = {
            "Content-Type": "application/json",
        }
        
        params = {
            "key": Config.GEMINI_API_KEY
        }
        
        # Log full request details
        logger.info("process_tryon: GEMINI API REQUEST DETAILS:")
        logger.info(f"  - URL: {url}")
        logger.info(f"  - Model: {Config.GEMINI_MODEL_NAME}")
        logger.info(f"  - Headers: {headers}")
        logger.info(f"  - Payload structure:")
        logger.info(f"    - contents[0].parts[0]: text prompt ({len(prompt)} chars)")
        logger.info(f"    - contents[0].parts[1]: person image (base64, {len(person_base64)} chars)")
        logger.info(f"    - contents[0].parts[2]: garment image (base64, {len(garment_base64)} chars)")
        logger.info("=" * 80)
        
        logger.info(f"process_tryon: Calling Gemini API - model={Config.GEMINI_MODEL_NAME}")
        
        # Retry logic for transient errors (500, 503, 429)
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
        logger.debug(f"process_tryon: Response structure keys: {list(result.keys())}")
        
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
                        # Check if text contains base64 image data
                        if 'data:image' in text_content or len(text_content) > 1000:
                            logger.debug(f"process_tryon: Found text content, length={len(text_content)}")
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
            else:
                candidate = result['candidates'][0]
                finish_reason = candidate.get('finishReason', 'UNKNOWN')
                finish_message = candidate.get('finishMessage', '')
                
                if finish_reason != 'STOP':
                    logger.error(f"process_tryon: Gemini finishReason: {finish_reason}")
                    if finish_message:
                        logger.error(f"process_tryon: Gemini finishMessage: {finish_message}")
                    if 'safetyRatings' in candidate:
                        logger.error(f"process_tryon: Safety ratings: {candidate['safetyRatings']}")
                    
                    # Handle specific finish reasons with helpful error messages
                    if finish_reason == 'IMAGE_OTHER':
                        error_msg = finish_message if finish_message else "Gemini could not generate the image based on the prompt provided."
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
        
        if result_image_bytes is None:
            # Log full response structure for debugging (up to 2000 chars)
            try:
                response_str = json.dumps(result, indent=2)
                logger.error(f"process_tryon: Unexpected response structure. Full response ({len(response_str)} chars):")
                logger.error(response_str[:2000])
                if len(response_str) > 2000:
                    logger.error(f"... (truncated, total length: {len(response_str)} chars)")
            except Exception:
                logger.error(f"process_tryon: Unexpected response structure. Full response: {str(result)[:2000]}")
            
            raise ExternalServiceError(
                "Unexpected response format from Gemini API. Please check logs for full response structure.",
                service='gemini'
            )
        
        # Log result image info and process for transparency
        try:
            result_img = Image.open(BytesIO(result_image_bytes))
            gemini_result_size = result_img.size
            gemini_aspect = gemini_result_size[0] / gemini_result_size[1] if gemini_result_size[1] > 0 else 1.0
            logger.info(f"process_tryon: Gemini returned image, mode={result_img.mode}, size={gemini_result_size}, aspect_ratio: {gemini_aspect:.3f}")
            logger.info(f"process_tryon: Avatar dimensions: {original_avatar_size}, aspect_ratio: {original_avatar_aspect:.3f}")
            logger.info(f"process_tryon: Gemini returned: {gemini_result_size}, aspect_ratio: {gemini_aspect:.3f}")
            
            # Verify aspect ratio matches avatar
            aspect_ratio_diff = abs(gemini_aspect - original_avatar_aspect)
            if aspect_ratio_diff > 0.1:  # Allow 10% tolerance
                logger.warning(f"process_tryon: Aspect ratio mismatch! Avatar: {original_avatar_aspect:.3f}, Gemini: {gemini_aspect:.3f}, diff: {aspect_ratio_diff:.3f}")
            else:
                logger.info(f"process_tryon: Aspect ratio matches avatar (diff: {aspect_ratio_diff:.3f})")
            
            # Check if Gemini already provided transparency
            has_transparency = result_img.mode in ('RGBA', 'LA', 'P')
            logger.info(f"process_tryon: Gemini result has transparency: {has_transparency}, mode: {result_img.mode}")
            
            # Process Gemini result: background removal + aspect ratio matching
            if has_transparency:
                logger.info("process_tryon: Gemini result already has transparency - processing aspect ratio")
                if result_img.mode != 'RGBA':
                    result_img = result_img.convert('RGBA')
            else:
                # Gemini has no transparency - use rembg to remove background
                logger.info("process_tryon: Gemini result has no transparency - using rembg to remove background")
                from rembg import remove  # type: ignore
                
                logger.info(f"process_tryon: Image dimensions before rembg: {gemini_result_size}")
                
                result_image_bytes = remove(result_image_bytes)
                logger.info(f"process_tryon: rembg processed image, new size={len(result_image_bytes)} bytes")
                
                # Process rembg result
                try:
                    result_img = Image.open(BytesIO(result_image_bytes))
                    rembg_size = result_img.size
                    logger.info(f"process_tryon: rembg result image, mode={result_img.mode}, size={rembg_size}")
                    
                    if result_img.mode != 'RGBA':
                        result_img = result_img.convert('RGBA')
                except Exception as img_verify_error:
                    logger.warning(f"process_tryon: Could not verify rembg result: {str(img_verify_error)}")
                    # Fallback to original Gemini result
                    result_img = Image.open(BytesIO(result_image_bytes))
                    if result_img.mode != 'RGBA':
                        result_img = result_img.convert('RGBA')
            
            # Step 1: Detect person in Gemini result for accurate cropping
            avatar_ratio = original_avatar_aspect
            
            # Detect person boundaries in the result image (more accurate than using avatar info)
            logger.info("process_tryon: Detecting person boundaries in Gemini result for accurate cropping")
            result_img_bytes = BytesIO()
            result_img.save(result_img_bytes, format='PNG')
            result_img_bytes.seek(0)
            
            result_person_info = _detect_person_boundaries(result_img_bytes.getvalue())
            result_person_center_x = result_person_info['center'][0] if result_person_info else None
            
            if result_person_center_x:
                logger.info(f"process_tryon: Detected person center in result: ({result_person_center_x}, {result_person_info['center'][1]}), bbox: {result_person_info['bbox']}")
            else:
                logger.warning("process_tryon: Could not detect person in result, using center crop")
            
            # Crop to match avatar aspect ratio using person center from result
            result_img = _crop_to_aspect_ratio(result_img, avatar_ratio, person_center_x=result_person_center_x)
            logger.info(f"process_tryon: Cropped to avatar aspect ratio: {avatar_ratio:.3f}, new size: {result_img.size}")
            
            # Step 2: Resize to exact avatar dimensions
            if result_img.size != original_avatar_size:
                logger.info(f"process_tryon: Resizing from {result_img.size} to {original_avatar_size} to match avatar dimensions")
                result_img = result_img.resize(original_avatar_size, Image.Resampling.LANCZOS)
            
            # Save final result
            output = BytesIO()
            result_img.save(output, format='PNG')
            result_image_bytes = output.getvalue()
            logger.info(f"process_tryon: Final result size: {result_img.size}, matches avatar: {result_img.size == original_avatar_size}, aspect_ratio: {result_img.size[0]/result_img.size[1]:.3f}")
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
