"""
AI model integration for try-on processing using Gemini (Nano Banana) API
Simplified to use Gemini only - no routing logic needed
"""

import requests  # type: ignore
import base64
from config import Config
from shared.logger import logger
from shared.errors import ExternalServiceError


def process_tryon(person_image: bytes, garment_image: bytes, garment_type: str = 'upper', 
                  garment_details: dict = None, options: dict = None) -> str:
    """
    Process try-on using Gemini (Nano Banana) API
    
    Args:
        person_image: Person image bytes (avatar or selfie with background removed)
        garment_image: Garment image bytes
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
        
        # Convert images to base64
        person_base64 = base64.b64encode(person_image).decode('utf-8')
        garment_base64 = base64.b64encode(garment_image).decode('utf-8')
        
        # Build prompt with garment details
        prompt_parts = [
            "Place the garment from the second image onto the person in the first image. ",
            "Keep the person's pose, body shape, and facial features exactly as they are. ",
            "Adjust the garment to fit naturally on the person's body. ",
            "Maintain realistic lighting and shadows. ",
            "Do not modify the person's appearance, only add the garment. ",
            "Return a single composited image showing the person wearing the garment."
        ]
        
        # Add garment details to prompt if provided
        if garment_details:
            details_text = "Garment details: "
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
            prompt_parts.append(details_text)
        
        prompt = "".join(prompt_parts)
        
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
        
        logger.info(f"process_tryon: Calling Gemini API - model={Config.GEMINI_MODEL_NAME}")
        response = requests.post(url, json=payload, headers=headers, params=params, timeout=120)
        
        if response.status_code != 200:
            logger.error(f"process_tryon: Gemini API error - status={response.status_code}, response={response.text[:500]}")
            raise ExternalServiceError(
                f"Gemini API error: {response.status_code} - {response.text[:200]}",
                service='gemini'
            )
        
        # Parse response
        result = response.json()
        logger.debug(f"process_tryon: Response structure keys: {list(result.keys())}")
        
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
                        # Convert to base64 data URL
                        result_base64 = base64.b64encode(image_bytes).decode('utf-8')
                        result = f"data:image/png;base64,{result_base64}"
                        logger.info(f"process_tryon: EXIT - Success, result size={len(result_base64)} chars")
                        return result
                    # Check for inlineData (camelCase) - Nano Banana image model format
                    if 'inlineData' in part and 'data' in part['inlineData']:
                        image_data_b64 = part['inlineData']['data']
                        image_bytes = base64.b64decode(image_data_b64)
                        # Convert to base64 data URL
                        result_base64 = base64.b64encode(image_bytes).decode('utf-8')
                        result = f"data:image/png;base64,{result_base64}"
                        logger.info(f"process_tryon: EXIT - Success (Nano Banana format), result size={len(result_base64)} chars")
                        return result
                    # Also check for text response that might contain base64
                    if 'text' in part:
                        text_content = part['text']
                        # Check if text contains base64 image data
                        if 'data:image' in text_content or len(text_content) > 1000:
                            logger.debug(f"process_tryon: Found text content, length={len(text_content)}")
                            # Try to extract base64 from text
                            import re
                            base64_match = re.search(r'data:image/[^;]+;base64,([A-Za-z0-9+/=]+)', text_content)
                            if base64_match:
                                image_data_b64 = base64_match.group(1)
                                image_bytes = base64.b64decode(image_data_b64)
                                result_base64 = base64.b64encode(image_bytes).decode('utf-8')
                                result = f"data:image/png;base64,{result_base64}"
                                logger.info(f"process_tryon: EXIT - Success (extracted from text), result size={len(result_base64)} chars")
                                return result
        
        # Format 2: Direct response with image data
        if 'data' in result:
            image_data_b64 = result['data']
            image_bytes = base64.b64decode(image_data_b64)
            result_base64 = base64.b64encode(image_bytes).decode('utf-8')
            result = f"data:image/png;base64,{result_base64}"
            logger.info(f"process_tryon: EXIT - Success (direct data), result size={len(result_base64)} chars")
            return result
        
        # Log full response structure for debugging
        logger.warning(f"process_tryon: Unexpected response structure. Full response: {str(result)[:500]}")
        raise ExternalServiceError("Unexpected response format from Gemini API", service='gemini')
        
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
                        import re
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
        from PIL import Image
        from io import BytesIO
        
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
    Local background removal using PIL (fallback when Gemini API fails)
    
    Args:
        image_data: Image bytes
        
    Returns:
        Image bytes with background removed (transparent PNG in RGBA format)
    """
    logger.info("_remove_background_local: ENTRY - Using local background removal")
    
    try:
        from PIL import Image
        from io import BytesIO
        
        img = Image.open(BytesIO(image_data))
        original_mode = img.mode
        logger.info(f"_remove_background_local: Image opened, mode={original_mode}, size={img.size}")
        
        # Convert to RGBA if not already
        if img.mode not in ('RGBA', 'LA', 'P'):
            img = img.convert('RGBA')
        elif img.mode == 'P':
            img = img.convert('RGBA')
        elif img.mode == 'LA':
            img = img.convert('RGBA')
        
        # Process the image to remove background
        # Strategy: Use edge-based flood fill approach - start from edges and remove similar colors
        pixels = img.load()
        width, height = img.size
        
        # Sample edge pixels more comprehensively to determine background color range
        edge_samples = []
        # Sample all 4 edges more densely
        sample_step = max(1, min(width, height) // 20)  # Sample every 5% of the smaller dimension
        
        # Top and bottom edges
        for x in range(0, width, sample_step):
            edge_samples.append(pixels[x, 0][:3])  # Top
            edge_samples.append(pixels[x, height - 1][:3])  # Bottom
        # Left and right edges
        for y in range(0, height, sample_step):
            edge_samples.append(pixels[0, y][:3])  # Left
            edge_samples.append(pixels[width - 1, y][:3])  # Right
        
        # Calculate background color statistics (mean and std dev for better threshold)
        if edge_samples:
            avg_r = sum(s[0] for s in edge_samples) // len(edge_samples)
            avg_g = sum(s[1] for s in edge_samples) // len(edge_samples)
            avg_b = sum(s[2] for s in edge_samples) // len(edge_samples)
            bg_color = (avg_r, avg_g, avg_b)
            
            # Calculate standard deviation to determine threshold dynamically
            import math
            variances = [
                sum((s[0] - avg_r) ** 2 for s in edge_samples),
                sum((s[1] - avg_g) ** 2 for s in edge_samples),
                sum((s[2] - avg_b) ** 2 for s in edge_samples)
            ]
            std_dev = math.sqrt(sum(variances) / (len(edge_samples) * 3))
            # Use 3.0 * std_dev as threshold for more aggressive removal, but cap between 30 and 80
            threshold_distance = max(30, min(80, int(3.0 * std_dev + 20)))
            
            logger.info(f"_remove_background_local: Detected background color: RGB({avg_r}, {avg_g}, {avg_b}), threshold: {threshold_distance}, std_dev: {std_dev:.2f}")
        else:
            bg_color = (240, 240, 240)
            threshold_distance = 50  # Increased default threshold
            logger.warning(f"_remove_background_local: Could not detect background color, using fallback: {bg_color}, threshold: {threshold_distance}")
        
        # Create a mask for pixels to remove (start from edges)
        # Use a more sophisticated approach: flood fill from edges
        transparent_count = 0
        
        # First pass: mark edge pixels as background
        edge_mask = set()
        for x in range(width):
            edge_mask.add((x, 0))
            edge_mask.add((x, height - 1))
        for y in range(height):
            edge_mask.add((0, y))
            edge_mask.add((width - 1, y))
        
        # Flood fill from edges - mark pixels similar to background
        to_process = list(edge_mask)
        processed = set()
        background_pixels = set()
        
        while to_process:
            x, y = to_process.pop(0)
            if (x, y) in processed:
                continue
            processed.add((x, y))
            
            r, g, b, a = pixels[x, y]
            
            # Calculate color distance from background
            color_distance = (
                abs(r - bg_color[0]) +
                abs(g - bg_color[1]) +
                abs(b - bg_color[2])
            ) / 3.0
            
            # If pixel is similar to background, mark it and check neighbors
            if color_distance <= threshold_distance:
                background_pixels.add((x, y))
                
                # Check 4-connected neighbors
                for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < width and 0 <= ny < height and (nx, ny) not in processed:
                        to_process.append((nx, ny))
        
        # Second pass: make background pixels transparent
        for x, y in background_pixels:
            r, g, b, a = pixels[x, y]
            color_distance = (
                abs(r - bg_color[0]) +
                abs(g - bg_color[1]) +
                abs(b - bg_color[2])
            ) / 3.0
            
            # Gradually reduce alpha based on similarity - more aggressive removal
            similarity = 1.0 - (color_distance / threshold_distance)
            # Make pixels fully transparent if very similar, gradually fade for less similar
            if similarity > 0.8:  # Very similar to background
                new_alpha = 0  # Fully transparent
            else:
                new_alpha = int(a * (1.0 - similarity * 0.95))  # Gradually fade
            pixels[x, y] = (r, g, b, new_alpha)
            if new_alpha < 10:
                transparent_count += 1
        
        logger.info(f"_remove_background_local: Applied background removal. Made {transparent_count} pixels transparent out of {len(background_pixels)} background pixels.")
        
        # Save as PNG with transparency preserved
        output = BytesIO()
        img.save(output, format='PNG')
        image_bytes = output.getvalue()
        
        logger.info(f"_remove_background_local: EXIT - Success, result size={len(image_bytes)} bytes, mode=RGBA")
        return image_bytes
        
    except Exception as e:
        logger.exception(f"_remove_background_local: EXIT - Error: {str(e)}")
        raise ExternalServiceError(f"Local background removal failed: {str(e)}", service='local')
