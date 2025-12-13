"""
Try-On API endpoints with async job processing
Uses User model for avatar operations
JWT authentication via @require_auth decorator extracts user_id from token
"""

from flask import Blueprint, request, send_file
from io import BytesIO
import base64
import json
import requests
from features.tryon.job_queue import get_job_queue
from shared.database import db_manager
from shared.image_processing import preprocess_image, fetch_image_from_url, validate_image
from shared.garment_utils import categorize_garment
from shared.models.user import User
from shared.response import success_response, error_response_from_string
from shared.middleware import require_auth
from shared.logger import logger
from shared.validators import validate_url

tryon_bp = Blueprint('tryon', __name__, url_prefix='/api')


@tryon_bp.route('/tryon', methods=['POST'])
@require_auth  # JWT decorator validates token and sets request.user_id from token
def create_tryon_job():
    """
    Create a new try-on job (async)
    Uses User model for avatar operations
    user_id is extracted from JWT token by @require_auth decorator
    
    Per context.md API contract (lines 121-139):
    - Accepts: selfie (multipart), item_urls[] (JSON array), options (optional)
    - Returns: job_id, status: queued
    """
    # user_id comes from JWT token via @require_auth decorator
    user_id = request.user_id
    logger.info(f"create_tryon_job: ENTRY - user_id={user_id} (from JWT)")
    
    try:
        
        # Get person image (selfie, person_image file, or use current user's saved avatar)
        # Priority: 1) selfie file, 2) person_image file, 3) current user's saved avatar (no need to send from frontend)
        person_image = None
        if 'selfie' in request.files:
            person_image = request.files['selfie'].read()
            logger.info(f"create_tryon_job: Using selfie file for person image")
        elif 'person_image' in request.files:
            person_image = request.files['person_image'].read()
            logger.info(f"create_tryon_job: Using person_image file for person image")
        else:
            # Use current user's saved avatar (already stored in backend, no need to send from frontend)
            # Security: Always use the authenticated user's avatar, not arbitrary avatar_id
            current_user = User.get_by_id(user_id)
            if current_user and current_user.avatar:
                person_image = current_user.avatar
                logger.info(f"create_tryon_job: Using current user's saved avatar (user_id={user_id})")
            else:
                return error_response_from_string(
                    'No person image provided. Please upload a selfie/person_image file or save an avatar first using /api/save-avatar',
                    400,
                    'VALIDATION_ERROR'
                )
        
        if not person_image:
            return error_response_from_string('selfie/person_image required or save avatar first', 400, 'VALIDATION_ERROR')
        
        # Preprocess person image
        try:
            person_image = preprocess_image(person_image, resize=True, normalize=True)
        except Exception as e:
            logger.exception(f"create_tryon_job: Person image preprocessing failed: {str(e)}")
            return error_response_from_string(f'Person image validation failed: {str(e)}', 400, 'VALIDATION_ERROR')
        
        # Get garment image - support multiple methods per context.md
        garment_image = None
        garment_type = 'upper'  # Default
        garment_details = None  # Will be populated from scraping or request
        
        # Method 1: Wardrobe item ID (most efficient - uses already stored images)
        if 'wardrobe_item_id' in request.form or 'item_id' in request.form:
            wardrobe_item_id = request.form.get('wardrobe_item_id') or request.form.get('item_id')
            try:
                wardrobe_item_id = int(wardrobe_item_id)
                from features.wardrobe.model import WardrobeItem
                from shared.storage import get_storage_service
                
                # Fetch wardrobe item (ensures it belongs to the authenticated user)
                wardrobe_item = WardrobeItem.get_by_id(wardrobe_item_id, user_id)
                if not wardrobe_item:
                    return error_response_from_string(
                        f'Wardrobe item {wardrobe_item_id} not found or does not belong to user',
                        404,
                        'NOT_FOUND'
                    )
                
                # Load image from storage
                if wardrobe_item.image_path:
                    storage_service = get_storage_service()
                    # Extract path from image_path (remove /images/ prefix if present)
                    image_path = wardrobe_item.image_path
                    if image_path.startswith('/images/'):
                        image_path = image_path.replace('/images/', '')
                    
                    try:
                        garment_image = storage_service.get_image(image_path)
                        logger.info(f"create_tryon_job: Using wardrobe item {wardrobe_item_id} image from storage")
                    except Exception as storage_error:
                        logger.warning(f"create_tryon_job: Failed to load image from storage: {str(storage_error)}")
                        return error_response_from_string(
                            f'Failed to load image for wardrobe item {wardrobe_item_id}: {str(storage_error)}',
                            404,
                            'NOT_FOUND'
                        )
                else:
                    return error_response_from_string(
                        f'Wardrobe item {wardrobe_item_id} has no image',
                        400,
                        'VALIDATION_ERROR'
                    )
                
                # Build garment_details from wardrobe item
                garment_details = {
                    'category': wardrobe_item.category,
                    'brand': wardrobe_item.brand,
                    'title': wardrobe_item.title,
                    'color': wardrobe_item.color,
                    'garment_category_type': wardrobe_item.garment_category_type,
                }
                # Add fabric info if available
                if wardrobe_item.fabric:
                    try:
                        import json
                        import json as json_module  # Ensure json is available
                        fabric_data = json_module.loads(wardrobe_item.fabric) if isinstance(wardrobe_item.fabric, str) else wardrobe_item.fabric
                        if fabric_data and isinstance(fabric_data, list) and len(fabric_data) > 0:
                            garment_details['material_type'] = ', '.join([f.get('name', '') for f in fabric_data if f.get('name')])
                    except:
                        pass
                
                # Remove None values
                garment_details = {k: v for k, v in garment_details.items() if v is not None}
                
                # Set garment_type from wardrobe item category
                if wardrobe_item.category:
                    garment_type = wardrobe_item.category
                elif wardrobe_item.garment_category_type:
                    # Infer from garment_category_type if category not set
                    garment_type = 'upper' if wardrobe_item.garment_category_type in ['t-shirt', 'shirt', 'jacket', 'sweater', 'hoodie'] else 'lower'
                
                logger.info(f"create_tryon_job: Using wardrobe item {wardrobe_item_id}, garment_type={garment_type}")
            except ValueError:
                return error_response_from_string('wardrobe_item_id must be a valid integer', 400, 'VALIDATION_ERROR')
            except Exception as e:
                logger.exception(f"create_tryon_job: Error loading wardrobe item: {str(e)}")
                return error_response_from_string(f'Error loading wardrobe item: {str(e)}', 500)
        
        # Method 2: Direct image file
        if not garment_image and 'garment_image' in request.files:
            garment_image = request.files['garment_image'].read()
            logger.info(f"create_tryon_job: Using garment_image file")
        
        # Method 3: item_urls[] array (per context.md line 125) - for external product URLs
        if not garment_image and 'item_urls' in request.form:
            item_urls_str = request.form.get('item_urls')
            try:
                import json as json_module  # Ensure json is available in this scope
                item_urls = json_module.loads(item_urls_str) if isinstance(item_urls_str, str) else item_urls_str
                if not isinstance(item_urls, list):
                    return error_response_from_string('item_urls must be a JSON array', 400, 'VALIDATION_ERROR')
                
                if not item_urls:
                    return error_response_from_string('item_urls array cannot be empty', 400, 'VALIDATION_ERROR')
                
                # Get garment_index from options (per context.md line 131)
                options = {}
                if 'options' in request.form:
                    try:
                        import json as json_module  # Ensure json is available in this scope
                        options = json_module.loads(request.form.get('options')) if isinstance(request.form.get('options'), str) else request.form.get('options')
                    except:
                        options = {}
                
                garment_index = options.get('garment_index', 0)
                if garment_index >= len(item_urls):
                    garment_index = 0
                
                item_url = item_urls[garment_index]
                logger.info(f"create_tryon_job: Processing item_url[{garment_index}]: {item_url[:100]}")
                
                # Try to scrape product page first (if it's a product URL)
                # CHECK CACHE FIRST to save Scrape.do credits
                try:
                    from features.garments.scraper import is_image_url
                    from features.wardrobe.extractors import BrandExtractorFactory
                    
                    # Check if URL is a direct image or product page
                    if not is_image_url(item_url):
                        # Likely a product page - CHECK CACHE FIRST
                        product_info = None
                        cached_data = None
                        
                        # Check cache for this URL
                        try:
                            cached = db_manager.execute_query(
                                "SELECT * FROM garment_metadata WHERE url = ?",
                                (item_url,),
                                fetch_one=True
                            )
                            
                            if cached:
                                # Safely convert cached row to dict, filtering out non-serializable values
                                import json as json_module  # Ensure json is available in this scope
                                cached_dict = {}
                                for k, v in dict(cached).items():
                                    if isinstance(v, bytes):
                                        continue
                                    try:
                                        json_module.dumps(v)
                                        cached_dict[k] = v
                                    except (TypeError, ValueError):
                                        if hasattr(v, 'isoformat'):
                                            cached_dict[k] = v.isoformat()
                                        else:
                                            continue
                                
                                # Parse JSON fields
                                if cached_dict.get('images'):
                                    try:
                                        cached_dict['images'] = json_module.loads(cached_dict['images'])
                                    except:
                                        cached_dict['images'] = []
                                if cached_dict.get('sizes'):
                                    try:
                                        cached_dict['sizes'] = json_module.loads(cached_dict['sizes'])
                                    except:
                                        cached_dict['sizes'] = []
                                if cached_dict.get('colors'):
                                    try:
                                        cached_dict['colors'] = json_module.loads(cached_dict['colors'])
                                    except:
                                        cached_dict['colors'] = []
                                
                                # Check if cache is valid (has data and not expired - 3 days)
                                from datetime import datetime, timedelta
                                scraped_at_str = cached_dict.get('scraped_at') or cached_dict.get('updated_at')
                                is_valid_cache = False
                                
                                if scraped_at_str:
                                    try:
                                        if isinstance(scraped_at_str, str):
                                            scraped_at = datetime.strptime(scraped_at_str, '%Y-%m-%d %H:%M:%S')
                                        else:
                                            scraped_at = scraped_at_str
                                        cache_age = datetime.now() - scraped_at
                                        is_valid_cache = cache_age <= timedelta(days=3) and (
                                            (cached_dict.get('title') and cached_dict.get('title').strip()) or
                                            (cached_dict.get('images') and len(cached_dict.get('images', [])) > 0)
                                        )
                                    except:
                                        is_valid_cache = False
                                
                                if is_valid_cache:
                                    cached_data = cached_dict
                                    logger.info(f"create_tryon_job: Using cached product data for URL (saving Scrape.do credits)")
                        except Exception as cache_error:
                            logger.warning(f"create_tryon_job: Cache check failed: {str(cache_error)}")
                        
                        # If cache is valid, use it; otherwise scrape fresh
                        if cached_data and cached_data.get('images'):
                            product_info = cached_data
                            logger.info(f"create_tryon_job: Using cached images ({len(product_info.get('images', []))} images)")
                        else:
                            # Cache miss or expired - scrape fresh
                            logger.info(f"create_tryon_job: Cache miss/expired, scraping fresh data")
                            try:
                                extractor = BrandExtractorFactory.get_extractor(item_url)
                                product_info = extractor.extract_product_info(item_url)
                            except Exception as extractor_error:
                                logger.warning(f"create_tryon_job: Brand extractor failed: {str(extractor_error)}, trying simple scraping")
                                # Fallback to simple scraping
                                from features.garments.scraper import fetch_html, extract_images_from_html, extract_title_from_html
                                html_content = fetch_html(item_url)
                                if html_content:
                                    image_urls = extract_images_from_html(html_content, item_url, max_images=10)
                                    product_info = {
                                        'images': image_urls,
                                        'title': extract_title_from_html(html_content)
                                    }
                        
                        # Extract garment image from product info (cached or fresh)
                        if product_info:
                            images = product_info.get('images', [])
                            if images:
                                for img_url in images[:3]:  # Try top 3 images
                                    try:
                                        garment_image = fetch_image_from_url(img_url)
                                        logger.info(f"create_tryon_job: Successfully fetched image: {img_url[:100]}")
                                        
                                        # Build garment_details from product_info for Gemini
                                        garment_details = {
                                            'category': product_info.get('category'),
                                            'brand': product_info.get('brand'),
                                            'title': product_info.get('title'),
                                            'color': product_info.get('color') or (product_info.get('colors', [])[0] if product_info.get('colors') else None),
                                            'price': product_info.get('price'),
                                            'style': product_info.get('style'),
                                            'material_type': product_info.get('material_type')
                                        }
                                        # Remove None values
                                        garment_details = {k: v for k, v in garment_details.items() if v is not None}
                                        
                                        # Get garment_type from categorization
                                        if product_info.get('title'):
                                            categorization = categorize_garment(title=product_info.get('title'))
                                            garment_type = categorization.get('category', 'upper')
                                            logger.info(f"create_tryon_job: Detected garment_type={garment_type} from product info")
                                        
                                        break  # Successfully got image and details
                                    except Exception as img_fetch_error:
                                        logger.debug(f"create_tryon_job: Failed to fetch image {img_url}: {str(img_fetch_error)}")
                                        continue
                except Exception as scrape_error:
                    logger.warning(f"create_tryon_job: Scraping failed: {str(scrape_error)}, trying direct URL")
                
                # If scraping didn't work, try direct image URL
                if not garment_image:
                    try:
                        garment_image = fetch_image_from_url(item_url)
                    except Exception as e:
                        logger.exception(f"create_tryon_job: Failed to fetch image from URL: {str(e)}")
                        return error_response_from_string(f'Failed to fetch garment image from URL: {str(e)}', 400, 'VALIDATION_ERROR')
            except Exception as e:
                logger.exception(f"create_tryon_job: Error processing item_urls: {str(e)}")
                return error_response_from_string(f'Error processing item_urls: {str(e)}', 400, 'VALIDATION_ERROR')
        
        # Method 4: Single garment_url (backward compatibility)
        if not garment_image and 'garment_url' in request.form:
            garment_url = request.form.get('garment_url')
            try:
                garment_image = fetch_image_from_url(garment_url)
            except Exception as e:
                logger.exception(f"create_tryon_job: Failed to fetch image from URL: {str(e)}")
                return error_response_from_string(f'Failed to fetch garment image from URL: {str(e)}', 400, 'VALIDATION_ERROR')
        
        if not garment_image:
            return error_response_from_string('garment_image, wardrobe_item_id, garment_url, or item_urls required', 400, 'VALIDATION_ERROR')
        
        # Preprocess garment image
        try:
            garment_image = preprocess_image(garment_image, resize=True, normalize=True)
        except Exception as e:
            logger.exception(f"create_tryon_job: Garment image preprocessing failed: {str(e)}")
            return error_response_from_string(f'Garment image validation failed: {str(e)}', 400, 'VALIDATION_ERROR')
        
        # Get garment_type from form or options, or use detected type
        if 'garment_type' in request.form:
            garment_type = request.form.get('garment_type')
        elif 'options' in request.form:
            try:
                import json as json_module  # Ensure json is available
                options = json_module.loads(request.form.get('options')) if isinstance(request.form.get('options'), str) else request.form.get('options')
                if isinstance(options, dict) and 'garment_type' in options:
                    garment_type = options['garment_type']
            except:
                pass
        
        if garment_type not in ['upper', 'lower']:
            garment_type = 'upper'  # Default
        
        # Build options dict
        options = {}
        if 'options' in request.form:
            try:
                import json as json_module  # Ensure json is available
                options = json_module.loads(request.form.get('options')) if isinstance(request.form.get('options'), str) else request.form.get('options')
                if not isinstance(options, dict):
                    options = {}
            except:
                options = {}
        
        if 'num_inference_steps' in request.form:
            options['num_inference_steps'] = request.form.get('num_inference_steps')
        
        # Get garment_details from options if not already set from scraping
        if not garment_details and 'garment_details' in options:
            garment_details = options.get('garment_details')
            if isinstance(garment_details, str):
                try:
                    import json as json_module  # Ensure json is available
                    garment_details = json_module.loads(garment_details)
                except:
                    garment_details = None
        
        # Create job with garment_details for Gemini API
        job_queue = get_job_queue()
        job_id = job_queue.create_job(
            user_id=user_id,
            person_image=person_image,
            garment_image=garment_image,
            garment_type=garment_type,
            garment_details=garment_details,  # Pass garment details to Gemini
            options=options
        )
        
        logger.info(f"create_tryon_job: EXIT - Job created: {job_id}")
        return success_response(
            data={
                'job_id': job_id,
                'status': 'queued',
                'estimated_time': 15  # seconds
            },
            message='Try-on job created',
            status_code=202
        )
        
    except Exception as e:
        logger.exception(f"create_tryon_job: EXIT - Error: {str(e)}")
        return error_response_from_string(f'Server error: {str(e)}', 500)


@tryon_bp.route('/job/<job_id>', methods=['GET'])
@require_auth  # JWT decorator validates token and sets request.user_id from token
def get_job_status(job_id):
    """
    Get try-on job status
    user_id is extracted from JWT token by @require_auth decorator
    """
    # user_id comes from JWT token via @require_auth decorator
    user_id = request.user_id
    logger.info(f"get_job_status: ENTRY - job_id={job_id}, user_id={user_id} (from JWT)")
    
    try:
        job_queue = get_job_queue()
        job = job_queue.get_job_status(job_id)
        
        if not job:
            logger.warning(f"get_job_status: Job not found - job_id={job_id}")
            return error_response_from_string('Job not found', 404, 'NOT_FOUND')
        
        # Verify user owns this job
        if job['user_id'] != user_id:
            logger.warning(f"get_job_status: Unauthorized access - job_id={job_id}, user_id={user_id}")
            return error_response_from_string('Not authorized', 403, 'AUTHORIZATION_ERROR')
        
        # Convert result_url to absolute URL if present
        if job.get('result_url'):
            from shared.url_utils import to_absolute_url
            job['result_url'] = to_absolute_url(job['result_url'])
        
        logger.info(f"get_job_status: EXIT - Job status retrieved for job_id={job_id}")
        return success_response(data=job)
        
    except Exception as e:
        logger.exception(f"get_job_status: EXIT - Error: {str(e)}")
        return error_response_from_string(f'Server error: {str(e)}', 500)


@tryon_bp.route('/job/<job_id>/result', methods=['GET'])
@require_auth  # JWT decorator validates token and sets request.user_id from token
def get_job_result(job_id):
    """
    Get try-on job result
    user_id is extracted from JWT token by @require_auth decorator
    """
    # user_id comes from JWT token via @require_auth decorator
    user_id = request.user_id
    logger.info(f"get_job_result: ENTRY - job_id={job_id}, user_id={user_id} (from JWT)")
    
    try:
        job_queue = get_job_queue()
        job = job_queue.get_job_status(job_id)
        
        if not job:
            logger.warning(f"get_job_result: Job not found - job_id={job_id}")
            return error_response_from_string('Job not found', 404, 'NOT_FOUND')
        
        # Verify user owns this job
        if job['user_id'] != user_id:
            logger.warning(f"get_job_result: Unauthorized access - job_id={job_id}, user_id={user_id}")
            return error_response_from_string('Not authorized', 403, 'AUTHORIZATION_ERROR')
        
        if job['status'] != 'done':
            logger.info(f"get_job_result: Job not completed - job_id={job_id}, status={job['status']}")
            return error_response_from_string(f'Job not completed. Status: {job["status"]}', 202, 'JOB_PENDING')
        
        if not job.get('result_url'):
            logger.warning(f"get_job_result: Result not available - job_id={job_id}")
            return error_response_from_string('Result not available', 404, 'NOT_FOUND')
        
        # If result is base64 data URL, decode and return
        if job['result_url'].startswith('data:image'):
            # Extract base64 data
            header, encoded = job['result_url'].split(',', 1)
            image_data = base64.b64decode(encoded)
            logger.info(f"get_job_result: EXIT - Returning base64 image for job_id={job_id}")
            return send_file(BytesIO(image_data), mimetype='image/png')
        
        # Otherwise, result_url is a file path or URL
        # Convert relative URL to absolute URL for frontend
        from shared.url_utils import to_absolute_url
        result_url = to_absolute_url(job['result_url'])
        
        logger.info(f"get_job_result: EXIT - Returning result URL for job_id={job_id}: {result_url}")
        return success_response(data={'result_url': result_url})
        
    except Exception as e:
        logger.exception(f"get_job_result: EXIT - Error: {str(e)}")
        return error_response_from_string(f'Server error: {str(e)}', 500)


@tryon_bp.route('/tryon/multi', methods=['POST'])
@require_auth  # JWT decorator validates token and sets request.user_id from token
def create_multi_tryon_job():
    """
    Create multi-garment try-on job (top + bottom)
    Uses User model for avatar operations
    user_id is extracted from JWT token by @require_auth decorator
    """
    # user_id comes from JWT token via @require_auth decorator
    user_id = request.user_id
    logger.info(f"create_multi_tryon_job: ENTRY - user_id={user_id} (from JWT)")
    
    try:
        # Get person image - use current user's saved avatar if no file provided
        person_image = None
        if 'person_image' in request.files:
            person_image = request.files['person_image'].read()
            logger.info(f"create_multi_tryon_job: Using person_image file")
        else:
            # Use current user's saved avatar (already stored in backend)
            current_user = User.get_by_id(user_id)
            if current_user and current_user.avatar:
                person_image = current_user.avatar
                logger.info(f"create_multi_tryon_job: Using current user's saved avatar (user_id={user_id})")
            else:
                return error_response_from_string(
                    'No person image provided. Please upload a person_image file or save an avatar first using /api/save-avatar',
                    400,
                    'VALIDATION_ERROR'
                )
        
        if not person_image:
            return error_response_from_string('person_image required or save avatar first', 400, 'VALIDATION_ERROR')
        
        # Get top and bottom garments
        top_image = None
        bottom_image = None
        
        if 'top_garment_image' in request.files:
            top_image = request.files['top_garment_image'].read()
        elif 'top_garment_url' in request.form:
            import requests
            response = requests.get(request.form.get('top_garment_url'), timeout=10)
            if response.status_code == 200:
                top_image = response.content
        
        if 'bottom_garment_image' in request.files:
            bottom_image = request.files['bottom_garment_image'].read()
        elif 'bottom_garment_url' in request.form:
            import requests
            response = requests.get(request.form.get('bottom_garment_url'), timeout=10)
            if response.status_code == 200:
                bottom_image = response.content
        
        if not top_image or not bottom_image:
            return error_response_from_string('Both top and bottom garments required', 400, 'VALIDATION_ERROR')
        
        # For multi-garment, process sequentially for V1
        # First process top
        job_queue = get_job_queue()
        top_job_id = job_queue.create_job(user_id, person_image, top_image, 'upper')
        
        # Then process bottom (in real implementation, would composite both)
        bottom_job_id = job_queue.create_job(user_id, person_image, bottom_image, 'lower')
        
        logger.info(f"create_multi_tryon_job: EXIT - Multi-garment jobs created for user_id={user_id}")
        return success_response(
            data={
                'top_job_id': top_job_id,
                'bottom_job_id': bottom_job_id,
                'status': 'queued',
                'estimated_time': 30
            },
            message='Multi-garment try-on jobs created',
            status_code=202
        )
        
    except Exception as e:
        logger.exception(f"create_multi_tryon_job: EXIT - Error: {str(e)}")
        return error_response_from_string(f'Server error: {str(e)}', 500)

