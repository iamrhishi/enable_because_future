"""
AI model integration for try-on processing
Supports mixer-service and Gemini/Nano Banana
"""

import requests  # type: ignore
from requests.auth import HTTPBasicAuth  # type: ignore
from io import BytesIO
from config import Config
from utils.logger import logger
from utils.errors import ExternalServiceError


def process_tryon(person_image: bytes, garment_image: bytes, garment_type: str = 'upper', 
                  options: dict = None) -> str:
    """
    Process try-on using configured AI model
    
    Args:
        person_image: Person image bytes (avatar or selfie)
        garment_image: Garment image bytes
        garment_type: 'upper' or 'lower'
        options: Additional options (e.g., model_name, num_inference_steps)
        
    Returns:
        result_url: Base64 data URL or file path to result image
        
    Raises:
        ExternalServiceError: If processing fails
    """
    logger.info(f"process_tryon: ENTRY - garment_type={garment_type}, options={options}")
    
    try:
        if options is None:
            options = {}
        
        # Add model name from config if not specified
        if 'model_name' not in options and Config.GEMINI_MODEL_NAME:
            options['model_name'] = Config.GEMINI_MODEL_NAME
        
        provider = Config.AI_MODEL_PROVIDER.lower()
        logger.info(f"process_tryon: Using provider={provider}")
        
        # Use configured provider - no fallback
        if provider == 'gemini':
            if not Config.GEMINI_API_KEY:
                logger.error("process_tryon: GEMINI_API_KEY not configured")
                raise ExternalServiceError("GEMINI_API_KEY not configured", service='gemini')
            logger.info("process_tryon: Calling Gemini/Nano Banana")
            result = _process_with_gemini(person_image, garment_image, garment_type, options)
            logger.info("process_tryon: EXIT - Gemini processing successful")
            return result
        elif provider == 'mixer':
            logger.info("process_tryon: Calling mixer-service")
            result = _process_with_mixer(person_image, garment_image, garment_type, options)
            logger.info("process_tryon: EXIT - Mixer processing successful")
            return result
        else:
            logger.error(f"process_tryon: Invalid provider={provider}")
            raise ExternalServiceError(f"Invalid AI_MODEL_PROVIDER: {provider}", service='config')
            
    except ExternalServiceError:
        logger.exception("process_tryon: EXIT - ExternalServiceError")
        raise
    except Exception as e:
        logger.exception(f"process_tryon: EXIT - Unexpected error: {str(e)}")
        raise ExternalServiceError(f"Try-on processing failed: {str(e)}", service='unknown')


def _process_with_mixer(person_image: bytes, garment_image: bytes, 
                       garment_type: str, options: dict) -> str:
    """Process try-on using mixer-service"""
    logger.info(f"_process_with_mixer: ENTRY - garment_type={garment_type}")
    
    try:
        files = {
            'person_image': ('person.png', BytesIO(person_image), 'image/png'),
            'cloth_image': ('garment.png', BytesIO(garment_image), 'image/png')
        }
        
        data = {'cloth_type': garment_type}
        if options and 'num_inference_steps' in options:
            data['num_inference_steps'] = options['num_inference_steps']
        
        logger.info(f"_process_with_mixer: Sending request to {Config.MIXER_SERVICE_URL}")
        response = requests.post(
            Config.MIXER_SERVICE_URL,
            files=files,
            auth=HTTPBasicAuth(Config.MIXER_SERVICE_USERNAME, Config.MIXER_SERVICE_PASSWORD),
            data=data,
            headers={'Accept': 'image/png'},
            timeout=120
        )
        
        logger.info(f"_process_with_mixer: Response status={response.status_code}")
        
        if response.status_code != 200:
            logger.error(f"_process_with_mixer: Service returned error status={response.status_code}")
            raise ExternalServiceError(
                f"Mixer service error: {response.status_code} - {response.text[:200]}",
                service='mixer-service'
            )
        
        # Return base64 encoded result
        import base64
        result_base64 = base64.b64encode(response.content).decode('utf-8')
        result = f"data:image/png;base64,{result_base64}"
        logger.info(f"_process_with_mixer: EXIT - Success, result size={len(result_base64)} chars")
        return result
            
    except requests.RequestException as e:
        logger.exception(f"_process_with_mixer: EXIT - Request failed: {str(e)}")
        raise ExternalServiceError(f"Mixer service request failed: {str(e)}", service='mixer-service')
    except ExternalServiceError:
        logger.exception("_process_with_mixer: EXIT - ExternalServiceError")
        raise
    except Exception as e:
        logger.exception(f"_process_with_mixer: EXIT - Unexpected error: {str(e)}")
        raise ExternalServiceError(f"Mixer service processing failed: {str(e)}", service='mixer-service')


def _process_with_gemini(person_image: bytes, garment_image: bytes, 
                        garment_type: str, options: dict) -> str:
    """
    Process try-on using Gemini/Nano Banana Image Edit API
    
    Per context.md specifications (lines 149-166):
    - Use Gemini image edit with person + garment images
    - Parameters: keep_pose=true, lighting_match=medium, skin_tone_preserve=high, seam_blend=high
    - Expect SynthID watermark (acceptable for preview)
    
    NOTE: Gemini 2.5 Flash Image (Nano Banana) model identifier: 'gemini-2.5-flash-image'
    The standard google-generativeai SDK may not support direct image editing.
    This implementation attempts to use the model but may need updates when the official
    image editing API is available.
    """
    logger.info(f"_process_with_gemini: ENTRY - garment_type={garment_type}, options={options}")
    
    try:
        import google.generativeai as genai  # type: ignore
        from PIL import Image  # type: ignore
        import base64
        
        if not Config.GEMINI_API_KEY:
            logger.error("_process_with_gemini: GEMINI_API_KEY not configured")
            raise ExternalServiceError("GEMINI_API_KEY not configured", service='gemini')
        
        logger.info("_process_with_gemini: Configuring Gemini API")
        genai.configure(api_key=Config.GEMINI_API_KEY)
        
        # Prepare images
        logger.info("_process_with_gemini: Preparing images")
        person_img = Image.open(BytesIO(person_image))
        garment_img = Image.open(BytesIO(garment_image))
        
        # Construct prompt per context.md (lines 165-166)
        # System instruction from context.md line 154
        system_instruction = """You are a professional fashion try-on compositor. 
        Maintain the subject's identity (face, hair, skin tone) and pose. 
        Align garment scale and perspective naturally. 
        Avoid artifacts on hands/necklines. Keep background intact."""
        
        # User prompt from context.md line 166
        user_prompt = """Place the garment from GARMENT_IMAGE onto the person in PERSON_IMAGE. 
        Keep the person's pose and hair visible, adjust garment drape naturally. 
        Do not modify facial features. Output a single composited image suitable for app preview.
        
        Parameters:
        - keep_pose=true: Maintain the person's original pose
        - lighting_match=medium: Match lighting between person and garment
        - skin_tone_preserve=high: Preserve the person's skin tone
        - seam_blend=high: Blend garment seams naturally"""
        
        # Get model name from options or config
        # Try gemini-2.5-flash-image first (Nano Banana), fallback to configured model
        model_name = options.get('model_name') if options else None
        if not model_name:
            # Try Nano Banana model first
            try:
                model_name = 'gemini-2.5-flash-image'
                test_model = genai.GenerativeModel(model_name)
                logger.info(f"_process_with_gemini: Using Nano Banana model: {model_name}")
            except Exception:
                # Fallback to configured model
                model_name = Config.GEMINI_MODEL_NAME or 'gemini-1.5-flash'
                logger.info(f"_process_with_gemini: Using configured model: {model_name}")
        
        try:
            model = genai.GenerativeModel(
                model_name,
                system_instruction=system_instruction
            )
            logger.info(f"_process_with_gemini: Model {model_name} initialized with system instruction")
        except Exception as e:
            logger.exception(f"_process_with_gemini: Failed to initialize model {model_name}: {str(e)}")
            raise ExternalServiceError(f"Failed to initialize Gemini model {model_name}: {str(e)}", service='gemini')
        
        # Generation config optimized for image editing
        generation_config = {
            'temperature': 0.3,  # Lower for more consistent image editing
            'top_p': 0.95,
            'top_k': 40,
        }
        
        # Safety settings
        safety_settings = [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"}
        ]
        
        logger.info("_process_with_gemini: Calling Gemini API with person and garment images")
        # Note: The standard generate_content API may not support image editing directly
        # This may need to be updated when Gemini's image editing API is officially available
        response = model.generate_content(
            [user_prompt, person_img, garment_img],
            generation_config=generation_config,
            safety_settings=safety_settings
        )
        
        logger.info("_process_with_gemini: Processing Gemini response")
        
        # Try to extract image from response
        if hasattr(response, 'candidates') and response.candidates:
            candidate = response.candidates[0]
            
            if hasattr(candidate, 'content') and hasattr(candidate.content, 'parts'):
                for part in candidate.content.parts:
                    # Check if response contains image data
                    if hasattr(part, 'inline_data') and part.inline_data:
                        image_data = base64.b64decode(part.inline_data.data)
                        result_base64 = base64.b64encode(image_data).decode('utf-8')
                        result = f"data:image/png;base64,{result_base64}"
                        logger.info(f"_process_with_gemini: EXIT - Success, result size={len(result_base64)} chars")
                        return result
                    
                    # If response is text (description), log it
                    if hasattr(part, 'text') and part.text:
                        logger.warning(f"_process_with_gemini: Gemini returned text: {part.text[:200]}")
                        # For now, if we get text, it means the model doesn't support image generation
                        # This is expected with current Gemini API - image editing may not be available yet
                        raise ExternalServiceError(
                            f"Gemini model {model_name} returned text instead of image. "
                            f"The image editing API may not be available yet. "
                            f"Response: {part.text[:200]}",
                            service='gemini'
                        )
        
        # If no image returned, fail
        logger.error("_process_with_gemini: Gemini did not return an image in response")
        raise ExternalServiceError(
            f"Gemini API did not return an image in the expected format. "
            f"Model {model_name} may not support image editing yet. "
            f"Please use 'mixer' provider or wait for official Gemini image editing API.",
            service='gemini'
        )
        
    except ImportError as e:
        logger.exception(f"_process_with_gemini: EXIT - Missing dependency: {str(e)}")
        raise ExternalServiceError(f"Missing required library: {str(e)}", service='gemini')
    except ExternalServiceError:
        logger.exception("_process_with_gemini: EXIT - ExternalServiceError")
        raise
    except Exception as e:
        logger.exception(f"_process_with_gemini: EXIT - Unexpected error: {str(e)}")
        raise ExternalServiceError(f"Gemini processing failed: {str(e)}", service='gemini')
