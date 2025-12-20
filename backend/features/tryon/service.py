"""
AI model integration for try-on processing using Gemini (Nano Banana) API
Simplified to use Gemini only - no routing logic needed
"""

import requests  # type: ignore
import base64
import time
import re
import json
from PIL import Image  # type: ignore
from io import BytesIO
from config import Config
from shared.logger import logger
from shared.errors import ExternalServiceError


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
        
        prompt_parts = [
            "TASK: Virtual try-on - Make the person in image 1 wear the garment from image 2. ",
            "",
            garment_category_text,
            "",
            "REQUIREMENTS:",
            "1. Background: Copy image 1's background exactly - do not change any background pixels. ",
            "2. Person: Keep image 1's person unchanged (face, body, pose, hands, arms, legs). ",
            f"3. Garment: Extract only the clothing fabric from image 2 (no body parts) and fit it onto the person at {body_location}. ",
            "   - Apply 3D transformation to wrap the garment around the body naturally. ",
            "   - The garment should follow body contours, pose, and perspective. ",
            "   - Add proper depth, shadows, and highlights for realistic appearance. ",
            "   - Only modify pixels in the garment area, not the background. ",
            "",
            "OUTPUT: PNG with RGBA channels. Background must match image 1 exactly."
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
        
        # Log result image info for debugging
        try:
            result_img = Image.open(BytesIO(result_image_bytes))
            logger.info(f"process_tryon: Gemini returned image, mode={result_img.mode}, size={result_img.size}")
        except Exception as img_check_error:
            logger.warning(f"process_tryon: Could not verify result image: {str(img_check_error)}")
        
        # Post-process with rembg to remove background and make it transparent
        logger.info("process_tryon: Processing Gemini result with rembg to remove background")
        try:
            from rembg import remove  # type: ignore
            result_image_bytes = remove(result_image_bytes)
            logger.info(f"process_tryon: rembg processed image, new size={len(result_image_bytes)} bytes")
            
            # Verify the result has transparency and trim padding
            try:
                processed_img = Image.open(BytesIO(result_image_bytes))
                logger.info(f"process_tryon: rembg result image, mode={processed_img.mode}, size={processed_img.size}")
                if processed_img.mode != 'RGBA':
                    logger.warning(f"process_tryon: rembg result is {processed_img.mode}, converting to RGBA")
                    processed_img = processed_img.convert('RGBA')
                
                # Trim transparent padding to make person fill more of the frame (same as avatar processing)
                try:
                    # Get bounding box of non-transparent pixels
                    bbox = processed_img.getbbox()
                    if bbox:
                        # Crop to bounding box to remove transparent padding
                        original_size = processed_img.size
                        processed_img = processed_img.crop(bbox)
                        logger.info(f"process_tryon: Trimmed result from {original_size} to {processed_img.size} (removed transparent padding)")
                    else:
                        logger.warning(f"process_tryon: Result has no visible content (all transparent)")
                except Exception as trim_error:
                    logger.warning(f"process_tryon: Could not trim padding: {str(trim_error)}, using original size")
                
                # Save trimmed image
                output = BytesIO()
                processed_img.save(output, format='PNG')
                result_image_bytes = output.getvalue()
            except Exception as img_verify_error:
                logger.warning(f"process_tryon: Could not verify rembg result image: {str(img_verify_error)}")
        except Exception as rembg_error:
            logger.warning(f"process_tryon: rembg processing failed: {str(rembg_error)}, using Gemini result as-is")
            # Continue with Gemini's result if rembg fails
        
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
