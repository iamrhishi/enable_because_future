"""
Try-On API endpoints with async job processing
Uses User model for avatar operations
JWT authentication via @require_auth decorator extracts user_id from token
"""

from flask import Blueprint, request, send_file, Response
from io import BytesIO
import base64
import json
import requests
from config import Config
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


def _attach_job_poll_hint(job_row) -> dict:
    """Build job dict for API; add poll_interval_ms when job is still active."""
    payload = dict(job_row)
    if payload.get('status') in ('queued', 'processing'):
        payload['poll_interval_ms'] = Config.JOB_STATUS_POLL_INTERVAL_MS
    else:
        payload['poll_interval_ms'] = None
    return payload


@tryon_bp.route('/tryon', methods=['POST'])
@require_auth  # JWT decorator validates token and sets request.user_id from token
def create_tryon_job():
    try:
        # user_id is extracted from JWT token by @require_auth decorator
        user_id = request.user_id
        logger.info(f"create_tryon_job: ENTRY - user_id={user_id}")

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
        source_garment_url = None  # Track the source URL for saving with try-on result
        
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
                
                # Extract category_section and category_name from wardrobe item
                # category_section might be in _data or as attribute
                category_section = getattr(wardrobe_item, 'category_section', None) or wardrobe_item._data.get('category_section') if hasattr(wardrobe_item, '_data') else None
                if category_section:
                    garment_details['category_section'] = category_section
                elif wardrobe_item.category:
                    # Map category to category_section
                    if wardrobe_item.category in ['upper']:
                        garment_details['category_section'] = 'upper_body'
                    elif wardrobe_item.category in ['lower']:
                        garment_details['category_section'] = 'lower_body'
                
                # Get category name - use custom_category_name or garment_category_type
                if wardrobe_item.custom_category_name:
                    garment_details['category_name'] = wardrobe_item.custom_category_name
                elif wardrobe_item.garment_category_type:
                    garment_details['category_name'] = wardrobe_item.garment_category_type
                
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
                elif garment_details.get('category_section'):
                    # Map category_section to garment_type
                    if garment_details['category_section'] == 'upper_body':
                        garment_type = 'upper'
                    elif garment_details['category_section'] == 'lower_body':
                        garment_type = 'lower'
                
                # Capture source URL from wardrobe item if available
                if hasattr(wardrobe_item, 'url') and wardrobe_item.url:
                    source_garment_url = wardrobe_item.url
                    logger.info(f"create_tryon_job: Captured garment URL from wardrobe item: {source_garment_url[:100] if source_garment_url else 'None'}")

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
                source_garment_url = item_url  # Track source URL for saving with try-on
                logger.info(f"create_tryon_job: Processing item_url[{garment_index}]: {item_url[:100]}")
                
                # Try to scrape product page first (if it's a product URL)
                # CHECK CACHE FIRST to save Scrape.do credits
                try:
                    from features.garments.scraper import is_image_url
                    from features.wardrobe.extractors import BrandExtractorFactory
                    
                    # Check if URL is a direct image or product page
                    if not is_image_url(item_url):
                        # Likely a product page - CHECK USER'S WARDROBE FIRST (fastest), THEN GLOBAL CACHE
                        product_info = None
                        cached_data = None
                        
                        # OPTIMIZATION 1: Check if user already has this URL in their wardrobe (fastest - image already stored)
                        # Query directly by URL instead of loading all items (much faster!)
                        try:
                            from features.wardrobe.model import WardrobeItem
                            from shared.storage import get_storage_service
                            
                            # Direct database query for wardrobe item with this URL (optimized)
                            matching_item = None
                            try:
                                wardrobe_row = db_manager.execute_query(
                                    "SELECT * FROM wardrobe WHERE user_id = ? AND garment_url = ? LIMIT 1",
                                    (user_id, item_url),
                                    fetch_one=True
                                )
                                if wardrobe_row:
                                    matching_item = WardrobeItem(**dict(wardrobe_row))
                                    logger.info(f"create_tryon_job: Found URL in user's wardrobe via direct query (item_id={matching_item.id})")
                            except Exception as query_error:
                                logger.debug(f"create_tryon_job: Direct wardrobe query failed (garment_url column might not exist): {str(query_error)}")
                                # Fallback: check if garment_url column exists, if not, skip wardrobe check
                                pass
                            
                            if matching_item and matching_item.image_path:
                                # User has this URL in wardrobe - use stored image directly (fastest path!)
                                logger.info(f"create_tryon_job: Found URL in user's wardrobe (item_id={matching_item.id}), using stored image")
                                try:
                                    storage_service = get_storage_service()
                                    image_path = matching_item.image_path
                                    if image_path.startswith('/images/'):
                                        image_path = image_path.replace('/images/', '')
                                    garment_image = storage_service.get_image(image_path)
                                    
                                    # Build garment_details from wardrobe item
                                    garment_details = {
                                        'category': matching_item.category,
                                        'brand': matching_item.brand,
                                        'title': matching_item.title,
                                        'color': matching_item.color,
                                        'garment_category_type': matching_item.garment_category_type,
                                    }
                                    
                                    # Extract category_section and category_name
                                    category_section = getattr(matching_item, 'category_section', None) or matching_item._data.get('category_section') if hasattr(matching_item, '_data') else None
                                    if category_section:
                                        garment_details['category_section'] = category_section
                                    elif matching_item.category:
                                        if matching_item.category in ['upper']:
                                            garment_details['category_section'] = 'upper_body'
                                        elif matching_item.category in ['lower']:
                                            garment_details['category_section'] = 'lower_body'
                                    
                                    if matching_item.custom_category_name:
                                        garment_details['category_name'] = matching_item.custom_category_name
                                    elif matching_item.garment_category_type:
                                        garment_details['category_name'] = matching_item.garment_category_type
                                    
                                    # Add fabric info if available
                                    if matching_item.fabric:
                                        try:
                                            import json as json_module
                                            fabric_data = json_module.loads(matching_item.fabric) if isinstance(matching_item.fabric, str) else matching_item.fabric
                                            if fabric_data and isinstance(fabric_data, list) and len(fabric_data) > 0:
                                                garment_details['material_type'] = ', '.join([f.get('name', '') for f in fabric_data if f.get('name')])
                                        except:
                                            pass
                                    
                                    garment_details = {k: v for k, v in garment_details.items() if v is not None}
                                    
                                    # Set garment_type
                                    if matching_item.category:
                                        garment_type = matching_item.category
                                    elif matching_item.garment_category_type:
                                        garment_type = 'upper' if matching_item.garment_category_type in ['t-shirt', 'shirt', 'jacket', 'sweater', 'hoodie'] else 'lower'
                                    
                                    logger.info(f"create_tryon_job: Using wardrobe item image (fastest path - no scraping needed!)")
                                    # Skip to preprocessing - we have everything we need
                                    product_info = None  # Signal that we already have the image
                                    cached_data = None
                                except Exception as wardrobe_error:
                                    logger.warning(f"create_tryon_job: Failed to load image from wardrobe item: {str(wardrobe_error)}, falling back to cache/scraping")
                                    matching_item = None  # Fall through to cache check
                            else:
                                logger.info(f"create_tryon_job: URL not found in user's wardrobe, checking global cache")
                        except Exception as wardrobe_check_error:
                            logger.warning(f"create_tryon_job: Wardrobe check failed: {str(wardrobe_check_error)}, falling back to cache")
                        
                        # OPTIMIZATION 2: Check global garment_metadata cache BEFORE scraping (GLOBAL - shared across ALL users, no user_id)
                        # IMPORTANT: This check happens BEFORE any scraping to avoid unnecessary API calls
                        # This cache is populated when ANY user scrapes a URL, and can be used by ANY other user
                        # The garment_metadata table has NO user_id column - it's completely global
                        if not product_info and not cached_data and not garment_image:
                            import time as time_module
                            cache_check_start = time_module.time()
                            logger.info(f"create_tryon_job: 🔍 STEP 1: Checking GLOBAL database cache BEFORE scraping (shared across ALL users) for URL: {item_url[:100]}")
                            try:
                                # Normalize URL for cache lookup - remove query params for better matching
                                # URLs with different query params (v1, v2, etc.) should match the same product
                                from urllib.parse import urlparse, urlunparse
                                parsed_url = urlparse(item_url)
                                # Try exact match first
                                cached = db_manager.execute_query(
                                    "SELECT * FROM garment_metadata WHERE url = ?",
                                    (item_url,),
                                    fetch_one=True
                                )
                                
                                if cached:
                                    logger.info(f"create_tryon_job: Found exact URL match in cache")
                                else:
                                    # If exact match fails, try base URL (without query params)
                                    base_url = urlunparse((parsed_url.scheme, parsed_url.netloc, parsed_url.path, '', '', ''))
                                    logger.info(f"create_tryon_job: No exact match, trying base URL: {base_url}")
                                    cached = db_manager.execute_query(
                                        "SELECT * FROM garment_metadata WHERE url LIKE ?",
                                        (f"{base_url}%",),
                                        fetch_one=True
                                    )
                                    if cached:
                                        logger.info(f"create_tryon_job: Found cache with base URL match (query params differ)")
                                
                                if cached:
                                    # Safely convert cached row to dict, keeping image bytes for fast access
                                    import json as json_module  # Ensure json is available in this scope
                                    cached_dict = {}
                                    cached_row_dict = dict(cached)
                                    
                                    # Debug: Check if bytes exist in raw row
                                    has_bytes_in_row = 'cached_image_1' in cached_row_dict and cached_row_dict.get('cached_image_1') is not None
                                    if has_bytes_in_row:
                                        logger.info(f"create_tryon_job: DEBUG - Raw DB row has cached_image_1: {type(cached_row_dict.get('cached_image_1'))}, size: {len(cached_row_dict.get('cached_image_1')) if cached_row_dict.get('cached_image_1') else 0} bytes")
                                    
                                    for k, v in cached_row_dict.items():
                                        # Keep cached_image_1 and cached_image_2 bytes (we need these for fast access)
                                        if isinstance(v, bytes) and k in ['cached_image_1', 'cached_image_2']:
                                            cached_dict[k] = v  # Keep image bytes
                                            logger.debug(f"create_tryon_job: Preserved {k} bytes in cached_dict (size: {len(v)} bytes)")
                                            continue
                                        # Skip other bytes
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
                                    
                                    # Check if cache is valid (has data and not expired - 30 days for better reuse)
                                    # Extended from 3 days to 30 days since URLs are shared across users
                                    from datetime import datetime, timedelta
                                    scraped_at_str = cached_dict.get('scraped_at') or cached_dict.get('updated_at')
                                    is_valid_cache = False
                                    
                                    # Cache is valid if it has images (even if old) - product pages don't change that often
                                    has_images = cached_dict.get('images') and len(cached_dict.get('images', [])) > 0
                                    has_title = cached_dict.get('title') and cached_dict.get('title').strip()
                                    
                                    if has_images or has_title:
                                        # If cache has data, check age but be lenient (30 days instead of 3)
                                        if scraped_at_str:
                                            try:
                                                if isinstance(scraped_at_str, str):
                                                    scraped_at = datetime.strptime(scraped_at_str, '%Y-%m-%d %H:%M:%S')
                                                else:
                                                    scraped_at = scraped_at_str
                                                cache_age = datetime.now() - scraped_at
                                                # Extended cache validity to 30 days for better reuse across users
                                                is_valid_cache = cache_age <= timedelta(days=30)
                                            except:
                                                # If we can't parse date, assume cache is valid if it has data
                                                is_valid_cache = True
                                        else:
                                            # No date but has data - assume valid
                                            is_valid_cache = True
                                    
                                    if is_valid_cache:
                                        cached_data = cached_dict
                                        # Check if we also have cached image bytes (faster than fetching from URL)
                                        # TTL: Cached images expire after 1 day of inactivity
                                        cached_image_bytes = None
                                        cached_images_at = cached_dict.get('cached_images_at')
                                        
                                        # Debug: Check what we have in cached_dict
                                        has_cached_img_1 = 'cached_image_1' in cached_dict and cached_dict.get('cached_image_1') is not None
                                        logger.info(f"create_tryon_job: DEBUG - cached_dict has cached_image_1: {has_cached_img_1}, cached_images_at: {cached_images_at}")
                                        
                                        if cached_dict.get('cached_image_1') and cached_images_at:
                                            # Check TTL: images expire after 1 day
                                            try:
                                                if isinstance(cached_images_at, str):
                                                    cache_time = datetime.strptime(cached_images_at, '%Y-%m-%d %H:%M:%S')
                                                else:
                                                    cache_time = cached_images_at
                                                cache_age = datetime.now() - cache_time
                                                
                                                if cache_age <= timedelta(days=1):
                                                    cached_image_bytes = cached_dict['cached_image_1']
                                                    cached_image_url = cached_dict.get('cached_image_1_url', '')
                                                    logger.info(f"create_tryon_job: ✅ Found cached image bytes! (size: {len(cached_image_bytes)} bytes, age: {cache_age.days}d {cache_age.seconds//3600}h, URL: {cached_image_url[:80]})")
                                                    # Update last_accessed_at for TTL tracking
                                                    try:
                                                        db_manager.execute_query(
                                                            "UPDATE garment_metadata SET last_accessed_at = CURRENT_TIMESTAMP WHERE url = ?",
                                                            (cached_dict.get('url'),)
                                                        )
                                                    except:
                                                        pass
                                                else:
                                                    logger.warning(f"create_tryon_job: ⚠️  Cached image bytes expired (age: {cache_age.days} days > 1 day TTL), will fetch fresh")
                                            except Exception as ttl_check_error:
                                                logger.warning(f"create_tryon_job: TTL check failed: {str(ttl_check_error)}, using cached image anyway")
                                                cached_image_bytes = cached_dict.get('cached_image_1')
                                                if cached_image_bytes:
                                                    logger.info(f"create_tryon_job: Using cached image despite TTL check error (size: {len(cached_image_bytes)} bytes)")
                                        elif cached_dict.get('cached_image_1'):
                                            # Have image bytes but no cached_images_at - use it anyway
                                            cached_image_bytes = cached_dict['cached_image_1']
                                            logger.info(f"create_tryon_job: ✅ Found cached image bytes (no timestamp), using it (size: {len(cached_image_bytes)} bytes)")
                                        else:
                                            logger.info(f"create_tryon_job: ⚠️  No cached image bytes found in cache_dict (keys: {list(cached_dict.keys())[:10]})")
                                        
                                        cached_data['_cached_image_bytes'] = cached_image_bytes  # Store for later use
                                        
                                        cache_check_time = time_module.time() - cache_check_start
                                        cache_age_days = cache_age.days if 'cache_age' in locals() else 'unknown'
                                        logger.info(f"create_tryon_job: ✅ CACHE HIT! Using cached product data (cache age: {cache_age_days} days, check took {cache_check_time:.2f}s, saving Scrape.do credits)")
                                    else:
                                        cache_check_time = time_module.time() - cache_check_start
                                        logger.warning(f"create_tryon_job: ❌ Cache found but invalid/expired (check took {cache_check_time:.2f}s)")
                            except Exception as cache_error:
                                cache_check_time = time_module.time() - cache_check_start
                                logger.warning(f"create_tryon_job: Cache check failed after {cache_check_time:.2f}s: {str(cache_error)}")
                        
                        # STEP 2: If cache is valid, use it; otherwise scrape fresh
                        # Priority 1: If we have cached image bytes, use them immediately (fastest path)
                        if cached_data and cached_data.get('_cached_image_bytes'):
                            garment_image = cached_data['_cached_image_bytes']
                            logger.info(f"create_tryon_job: ✅ STEP 2: Cache HIT with IMAGE BYTES! Using cached image ({len(garment_image)} bytes) - SKIPPING BOTH SCRAPING AND DOWNLOAD (saved ~10-12s total!)")
                            # Set product_info from cache if available (for garment_details)
                            if cached_data.get('images') or cached_data.get('title'):
                                product_info = cached_data
                        # Priority 2: If we have cached metadata with images, use it (but need to fetch images)
                        elif cached_data and cached_data.get('images'):
                            product_info = cached_data
                            logger.info(f"create_tryon_job: ✅ STEP 2: Cache HIT - Using global cached images ({len(product_info.get('images', []))} images) - SKIPPING SCRAPING (saved ~5-7s)")
                            logger.info(f"create_tryon_job: ⚠️  NOTE: Still need to fetch image from URL (this will take ~5-6s even with cache)")
                        # Priority 3: No cache - scrape fresh
                        elif not product_info and not garment_image:
                            # Cache miss or expired - scrape fresh (only if we didn't get image from wardrobe)
                            import time as time_module
                            scrape_start = time_module.time()
                            logger.info(f"create_tryon_job: ❌ STEP 2: Cache MISS - No cache found in database, must scrape fresh (this will take 5-7 seconds)")
                            try:
                                extractor = BrandExtractorFactory.get_extractor(item_url)
                                product_info = extractor.extract_product_info(item_url)
                            except Exception as extractor_error:
                                logger.warning(f"create_tryon_job: Brand extractor failed: {str(extractor_error)}, trying simple scraping")
                                # Fallback to simple scraping
                                from features.garments.scraper import fetch_html, extract_images_from_html, extract_title_from_html
                                try:
                                    html_content = fetch_html(item_url)
                                    if html_content:
                                        image_urls = extract_images_from_html(html_content, item_url, max_images=10)
                                        logger.info(f"create_tryon_job: Simple scraping found {len(image_urls)} image URLs")
                                        if image_urls:
                                            product_info = {
                                                'images': image_urls,
                                                'title': extract_title_from_html(html_content)
                                            }
                                        else:
                                            logger.warning(f"create_tryon_job: Simple scraping found no images from HTML")
                                            product_info = None
                                    else:
                                        logger.warning(f"create_tryon_job: Simple scraping failed to fetch HTML")
                                        product_info = None
                                except Exception as simple_scrape_error:
                                    logger.warning(f"create_tryon_job: Simple scraping also failed: {str(simple_scrape_error)}")
                                    product_info = None
                            
                            scrape_time = time_module.time() - scrape_start
                            logger.info(f"create_tryon_job: Scraping completed in {scrape_time:.2f}s")
                            
                            # IMPORTANT: Cache the scraped result globally (NO user_id - shared across ALL users)
                            # This ensures that once a URL is scraped, all future requests (from any user) can use the cache
                            if product_info and product_info.get('images'):
                                try:
                                    import json as json_module
                                    # Save with the exact URL used, but also save with base URL for better matching
                                    from urllib.parse import urlparse, urlunparse
                                    parsed_url = urlparse(item_url)
                                    base_url = urlunparse((parsed_url.scheme, parsed_url.netloc, parsed_url.path, '', '', ''))
                                    
                                    # Save with exact URL (GLOBAL CACHE - no user_id, shared across all users)
                                    # Only save 1-2 image URLs (the ones we actually use for Gemini), not all images
                                    all_images = product_info.get('images', [])
                                    images_to_cache = all_images[:2]  # Only cache first 2 images
                                    db_manager.execute_query(
                                        """INSERT OR REPLACE INTO garment_metadata 
                                           (url, title, price, images, sizes, colors, brand, scraped_at, updated_at, last_accessed_at)
                                           VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)""",
                                        (item_url, 
                                         product_info.get('title'), 
                                         product_info.get('price'),
                                         json_module.dumps(images_to_cache),  # Only cache 1-2 images, not all
                                         json_module.dumps(product_info.get('sizes', [])),
                                         json_module.dumps(product_info.get('colors', [])),
                                         product_info.get('brand'))
                                    )
                                    logger.info(f"create_tryon_job: ✅ CACHED scraped result globally (exact URL) - {len(images_to_cache)} image URLs cached (out of {len(all_images)} total), title: {product_info.get('title', 'N/A')[:50]}")
                                    
                                    # Also save with base URL (without query params) if different, for better cache hits
                                    if base_url != item_url:
                                        try:
                                            db_manager.execute_query(
                                                """INSERT OR REPLACE INTO garment_metadata 
                                                   (url, title, price, images, sizes, colors, brand, scraped_at, updated_at, last_accessed_at)
                                                   VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)""",
                                                (base_url, 
                                                 product_info.get('title'), 
                                                 product_info.get('price'),
                                                 json_module.dumps(images_to_cache),  # Only cache 1-2 images
                                                 json_module.dumps(product_info.get('sizes', [])),
                                                 json_module.dumps(product_info.get('colors', [])),
                                                 product_info.get('brand'))
                                            )
                                            logger.info(f"create_tryon_job: ✅ Also cached with base URL (without query params) for better matching")
                                        except Exception as base_url_error:
                                            logger.warning(f"create_tryon_job: Failed to cache base URL: {str(base_url_error)}")
                                    
                                    # Cleanup old cached images (TTL: 1 day of inactivity)
                                    try:
                                        db_manager.execute_query(
                                            """UPDATE garment_metadata 
                                               SET cached_image_1 = NULL, cached_image_1_url = NULL,
                                                   cached_image_2 = NULL, cached_image_2_url = NULL,
                                                   cached_images_at = NULL
                                               WHERE last_accessed_at < datetime('now', '-1 day') 
                                                 AND cached_images_at IS NOT NULL""",
                                            ()
                                        )
                                        logger.debug(f"create_tryon_job: Cleaned up cached images older than 1 day")
                                    except Exception as cleanup_error:
                                        logger.debug(f"create_tryon_job: Cache cleanup failed (non-critical): {str(cleanup_error)}")
                                    
                                    logger.info(f"create_tryon_job: ✅ Global cache saved successfully - next request (from any user) will use cache instead of scraping")
                                except Exception as cache_save_error:
                                    logger.error(f"create_tryon_job: ❌ FAILED to cache scraped result: {str(cache_save_error)}")
                                    import traceback
                                    logger.error(traceback.format_exc())
                        
                        # STEP 3: Extract garment images from product info (cached or fresh)
                        # Only fetch 1-2 images that we actually use for Gemini (not all images)
                        # Skip if we already got image from wardrobe or cached bytes
                        garment_images = []
                        if product_info and not garment_image:
                            images = product_info.get('images', [])
                            if images:
                                import time as time_module
                                image_fetch_start = time_module.time()
                                # Only fetch 1-2 images (the ones we actually use for Gemini)
                                images_to_fetch = min(2, len(images))  # Max 2 images
                                logger.info(f"create_tryon_job: ⏱️  STEP 3: Fetching {images_to_fetch} garment image(s) from URLs (only the ones we use for Gemini, not all {len(images)} images)")
                                
                                for idx, img_url in enumerate(images[:images_to_fetch]):
                                    try:
                                        img_fetch_single_start = time_module.time()
                                        garment_img = fetch_image_from_url(img_url)
                                        img_fetch_time = time_module.time() - img_fetch_single_start
                                        garment_images.append((img_url, garment_img))  # Store URL with image for caching
                                        logger.info(f"create_tryon_job: ✅ Fetched image {idx+1}/{images_to_fetch} in {img_fetch_time:.2f}s: {img_url[:100]}")
                                    except Exception as img_fetch_error:
                                        logger.debug(f"create_tryon_job: Failed to fetch image {img_url}: {str(img_fetch_error)}")
                                        continue
                                
                                total_image_fetch_time = time_module.time() - image_fetch_start
                                logger.info(f"create_tryon_job: Total image fetching took {total_image_fetch_time:.2f}s")
                                
                                # If we got at least one image, use the first one
                                if garment_images:
                                    garment_image = garment_images[0][1]  # Use first image bytes
                                    logger.info(f"create_tryon_job: Using first image for try-on ({len(garment_image)} bytes)")
                                    
                                    # CACHE the fetched images for future use (1-2 images only, not all)
                                    if garment_images and item_url:
                                        try:
                                            # Cache first image (always)
                                            cached_img_1 = garment_images[0][1]
                                            cached_img_1_url = garment_images[0][0]
                                            
                                            # Cache second image if available
                                            cached_img_2 = garment_images[1][1] if len(garment_images) > 1 else None
                                            cached_img_2_url = garment_images[1][0] if len(garment_images) > 1 else None
                                            
                                            # Update cache with image bytes (only cache 1-2 images we actually use)
                                            db_manager.execute_query(
                                                """UPDATE garment_metadata 
                                                   SET cached_image_1 = ?, cached_image_1_url = ?,
                                                       cached_image_2 = ?, cached_image_2_url = ?,
                                                       cached_images_at = CURRENT_TIMESTAMP,
                                                       last_accessed_at = CURRENT_TIMESTAMP
                                                   WHERE url = ?""",
                                                (cached_img_1, cached_img_1_url, cached_img_2, cached_img_2_url, item_url)
                                            )
                                            logger.info(f"create_tryon_job: ✅ CACHED {len(garment_images)} image byte(s) for future use (TTL: 1 day) - next request will be instant!")
                                        except Exception as image_cache_error:
                                            logger.warning(f"create_tryon_job: Failed to cache image bytes: {str(image_cache_error)}")
                                            import traceback
                                            logger.debug(traceback.format_exc())
                                    
                                    # Get categorization from product title
                                    categorization = None
                                    if product_info.get('title'):
                                        categorization = categorize_garment(title=product_info.get('title'))
                                    
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
                                    
                                    # Add category_section and category_name from categorization
                                    if categorization:
                                        cat_type = categorization.get('category')  # 'upper' or 'lower'
                                        cat_name = categorization.get('type')  # 'jacket', 'shirt', etc.
                                        
                                        # Map category to category_section
                                        if cat_type == 'upper':
                                            garment_details['category_section'] = 'upper_body'
                                        elif cat_type == 'lower':
                                            garment_details['category_section'] = 'lower_body'
                                        
                                        # Add category name
                                        if cat_name:
                                            garment_details['category_name'] = cat_name
                                    
                                    # Remove None values
                                    garment_details = {k: v for k, v in garment_details.items() if v is not None}
                                    
                                    # Get garment_type from categorization
                                    if categorization:
                                        garment_type = categorization.get('category', 'upper')
                                        logger.info(f"create_tryon_job: Detected garment_type={garment_type}, category_name={garment_details.get('category_name')} from product info")
                except Exception as scrape_error:
                    logger.warning(f"create_tryon_job: Scraping failed: {str(scrape_error)}, trying direct URL")
                
                # If scraping didn't work, try direct image URL (only if it's actually an image URL)
                if not garment_image:
                    # Check if item_url is actually an image URL, not a product page
                    from features.garments.scraper import is_image_url
                    if is_image_url(item_url):
                        try:
                            garment_image = fetch_image_from_url(item_url)
                        except Exception as e:
                            logger.exception(f"create_tryon_job: Failed to fetch image from URL: {str(e)}")
                            return error_response_from_string(f'Failed to fetch garment image from URL: {str(e)}', 400, 'VALIDATION_ERROR')
                    else:
                        logger.warning(f"create_tryon_job: Could not extract images from product URL: {item_url[:100]}")
                        # Provide more helpful error message
                        error_msg = (
                            'Failed to extract garment images from product URL. '
                            'This could be due to:\n'
                            '1. The product page requires JavaScript to load images (try using a direct image URL instead)\n'
                            '2. The scraping service is temporarily unavailable\n'
                            '3. The product page structure has changed\n\n'
                            'Please try:\n'
                            '- Providing a direct image URL (ending in .jpg, .png, etc.)\n'
                            '- Using the /api/garments/scrape endpoint first to extract images\n'
                            '- Checking if the product page is accessible'
                        )
                        return error_response_from_string(error_msg, 400, 'VALIDATION_ERROR')
            except Exception as e:
                logger.exception(f"create_tryon_job: Error processing item_urls: {str(e)}")
                return error_response_from_string(f'Error processing item_urls: {str(e)}', 400, 'VALIDATION_ERROR')
        
        # Method 4: Single garment_url (backward compatibility)
        if not garment_image and 'garment_url' in request.form:
            garment_url = request.form.get('garment_url')
            source_garment_url = garment_url  # Track source URL for saving with try-on
            try:
                garment_image = fetch_image_from_url(garment_url)
            except Exception as e:
                logger.exception(f"create_tryon_job: Failed to fetch image from URL: {str(e)}")
                return error_response_from_string(f'Failed to fetch garment image from URL: {str(e)}', 400, 'VALIDATION_ERROR')
        
        if not garment_image:
            return error_response_from_string('garment_image, wardrobe_item_id, garment_url, or item_urls required', 400, 'VALIDATION_ERROR')
        
        # Preprocess garment image(s) and remove background using rembg
        try:
            from features.tryon.service import _remove_background_local
            if isinstance(garment_image, list):
                garment_image = [preprocess_image(img, resize=True, normalize=True) for img in garment_image]
                garment_image = [_remove_background_local(img) for img in garment_image]
                logger.info(f"create_tryon_job: Preprocessed and background removed for {len(garment_image)} garment images")
            else:
                garment_image = preprocess_image(garment_image, resize=True, normalize=True)
                garment_image = _remove_background_local(garment_image)
                logger.info("create_tryon_job: Preprocessed and background removed for garment image")
            # Add detailed logging for garment image after preprocessing
            if garment_image is None or (isinstance(garment_image, bytes) and len(garment_image) == 0):
                logger.error("create_tryon_job: ERROR - Garment image is None or empty after preprocessing/background removal")
            elif isinstance(garment_image, bytes):
                logger.info(f"create_tryon_job: Garment image bytes length after preprocessing: {len(garment_image)}")
            elif isinstance(garment_image, list):
                logger.info(f"create_tryon_job: Garment image list length after preprocessing: {len(garment_image)}")
        except Exception as e:
            logger.exception(f"create_tryon_job: Garment image preprocessing or background removal failed: {str(e)}")
            return error_response_from_string(f'Garment image validation or background removal failed: {str(e)}', 400, 'VALIDATION_ERROR')
        
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
            options=options,
            garment_url=source_garment_url  # Save source URL with try-on result
        )
        
        logger.info(f"create_tryon_job: EXIT - Job created: {job_id}")
        return success_response(
            data={
                'job_id': job_id,
                'status': 'queued',
                'estimated_time': 15,  # seconds
                'poll_interval_ms': Config.JOB_STATUS_POLL_INTERVAL_MS,
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
        # Normalize user_id comparison (handle string vs int, whitespace, etc.)
        job_user_id = str(job['user_id']).strip() if job.get('user_id') else None
        auth_user_id = str(user_id).strip() if user_id else None
        
        if job_user_id != auth_user_id:
            logger.warning(f"get_job_status: Unauthorized access - job_id={job_id}, job belongs to user_id={job_user_id!r}, but authenticated user_id={auth_user_id!r}")
            return error_response_from_string(
                f'Job {job_id} does not belong to your account. Please use a job ID that belongs to your user account.',
                403,
                'AUTHORIZATION_ERROR'
            )
        
        # Convert result_url to absolute URL if present
        job_payload = dict(job)
        if job_payload.get('result_url'):
            from shared.url_utils import to_absolute_url
            job_payload['result_url'] = to_absolute_url(job_payload['result_url'])

        logger.info(f"get_job_status: EXIT - Job status retrieved for job_id={job_id}")
        return success_response(data=_attach_job_poll_hint(job_payload))
        
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
        # Normalize user_id comparison (handle string vs int, whitespace, etc.)
        job_user_id = str(job['user_id']).strip() if job.get('user_id') else None
        auth_user_id = str(user_id).strip() if user_id else None
        
        if job_user_id != auth_user_id:
            logger.warning(f"get_job_result: Unauthorized access - job_id={job_id}, job belongs to user_id={job_user_id!r}, but authenticated user_id={auth_user_id!r}")
            return error_response_from_string(
                f'Job {job_id} does not belong to your account. Please use a job ID that belongs to your user account.',
                403,
                'AUTHORIZATION_ERROR'
            )
        
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
        
        # Include garment_url in response for reference
        response_data = {'result_url': result_url}
        if job.get('garment_url'):
            response_data['garment_url'] = job['garment_url']

        logger.info(f"get_job_result: EXIT - Returning result URL for job_id={job_id}: {result_url}")
        return success_response(data=response_data)
        
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
                'estimated_time': 30,
                'poll_interval_ms': Config.JOB_STATUS_POLL_INTERVAL_MS,
            },
            message='Multi-garment try-on jobs created',
            status_code=202
        )
        
    except Exception as e:
        logger.exception(f"create_multi_tryon_job: EXIT - Error: {str(e)}")
        return error_response_from_string(f'Server error: {str(e)}', 500)


@tryon_bp.route('/tryon/layered', methods=['POST'])
@require_auth
def create_layered_tryon():
    """
    Layered multi-garment try-on (synchronous)

    Applies multiple garments sequentially - result of garment 1 becomes
    the avatar for garment 2, etc. Useful for layering (e.g., top + jacket).

    Request (multipart/form-data):
    - garment_images[]: Array of garment image files (in order to apply)
    - garment_urls[]: Array of garment URLs to scrape (alternative to files)
    - garment_types[]: Optional array of types ('upper'/'lower') for each garment

    Returns:
    - results[]: Array of result URLs (one per garment applied)
    - final_result_url: The final combined result

    Note: This is synchronous and may take 30-60+ seconds for multiple garments.
    """
    user_id = request.user_id
    logger.info(f"create_layered_tryon: ENTRY - user_id={user_id}")

    try:
        from features.tryon.service import process_tryon, process_tryon_layered
        from shared.storage import get_storage_service
        import uuid

        # Get person image (avatar)
        person_image = None
        if 'person_image' in request.files:
            person_image = request.files['person_image'].read()
            logger.info("create_layered_tryon: Using uploaded person_image")
        else:
            current_user = User.get_by_id(user_id)
            if current_user and current_user.avatar:
                person_image = current_user.avatar
                logger.info(f"create_layered_tryon: Using saved avatar for user_id={user_id}")
            else:
                return error_response_from_string(
                    'No person image. Upload person_image or save avatar first via /api/save-avatar',
                    400, 'VALIDATION_ERROR'
                )

        # Collect garment images
        garment_images = []
        garment_types = []

        # From uploaded files
        if 'garment_images[]' in request.files:
            files = request.files.getlist('garment_images[]')
            for f in files:
                if f and f.filename:
                    garment_images.append(f.read())
            logger.info(f"create_layered_tryon: Got {len(garment_images)} garment files")

        # From URLs
        if 'garment_urls[]' in request.form:
            urls = request.form.getlist('garment_urls[]')
            from features.wardrobe.extractors import BrandExtractorFactory

            for url in urls:
                if not url:
                    continue
                try:
                    # Check if direct image URL
                    from features.garments.scraper import is_image_url
                    if is_image_url(url):
                        img_bytes = fetch_image_from_url(url)
                        garment_images.append(img_bytes)
                    else:
                        # Scrape product page
                        extractor = BrandExtractorFactory.get_extractor(url)
                        product_info = extractor.extract_product_info(url)
                        if product_info.get('images'):
                            img_url = product_info['images'][0]
                            img_bytes = fetch_image_from_url(img_url)
                            garment_images.append(img_bytes)
                except Exception as e:
                    logger.warning(f"create_layered_tryon: Failed to fetch garment from {url}: {str(e)}")

            logger.info(f"create_layered_tryon: Got {len(garment_images)} total garments after URL scraping")

        # Get garment types if provided
        if 'garment_types[]' in request.form:
            garment_types = request.form.getlist('garment_types[]')

        # Pad garment_types to match garment_images length
        while len(garment_types) < len(garment_images):
            garment_types.append('upper')  # Default to upper

        if len(garment_images) < 1:
            return error_response_from_string(
                'At least one garment image required. Use garment_images[] or garment_urls[]',
                400, 'VALIDATION_ERROR'
            )

        if len(garment_images) > 5:
            return error_response_from_string(
                'Maximum 5 garments allowed per request',
                400, 'VALIDATION_ERROR'
            )

        logger.info(f"create_layered_tryon: Processing {len(garment_images)} garments sequentially")

        # Process garments sequentially
        results = []
        current_avatar = person_image
        storage_service = get_storage_service()
        base_url = request.url_root.rstrip('/')

        for idx, (garment_image, garment_type) in enumerate(zip(garment_images, garment_types)):
            logger.info(f"create_layered_tryon: Processing garment {idx + 1}/{len(garment_images)}, type={garment_type}")

            try:
                # First garment: normal try-on on avatar
                # Subsequent garments: layer over existing outfit
                if idx == 0:
                    logger.info("create_layered_tryon: Using process_tryon for first garment")
                    result_data_url = process_tryon(
                        person_image=current_avatar,
                        garment_image=garment_image,
                        garment_type=garment_type
                    )
                else:
                    logger.info("create_layered_tryon: Using process_tryon_layered for subsequent garment")
                    result_data_url = process_tryon_layered(
                        person_image=current_avatar,
                        garment_image=garment_image,
                        garment_type=garment_type
                    )

                # Extract base64 data and convert to bytes
                if result_data_url.startswith('data:'):
                    # Remove data URL prefix
                    base64_data = result_data_url.split(',', 1)[1]
                else:
                    base64_data = result_data_url

                result_bytes = base64.b64decode(base64_data)

                # Save result to storage
                result_filename = f"{user_id}_{uuid.uuid4().hex[:8]}_layer{idx + 1}.png"
                storage_path = f"tryon-results/{user_id}/{result_filename}"
                result_url = storage_service.upload_image(
                    result_bytes,
                    storage_path,
                    content_type='image/png'
                )
                absolute_url = f"{base_url}{result_url}"

                results.append({
                    'layer': idx + 1,
                    'garment_type': garment_type,
                    'result_url': absolute_url
                })

                # Use this result as avatar for next garment
                current_avatar = result_bytes

                logger.info(f"create_layered_tryon: Layer {idx + 1} complete, saved to {absolute_url}")

            except Exception as e:
                logger.exception(f"create_layered_tryon: Failed at layer {idx + 1}: {str(e)}")
                return error_response_from_string(
                    f'Failed at garment {idx + 1}: {str(e)}',
                    500, 'GENERATION_ERROR'
                )

        final_result = results[-1] if results else None

        logger.info(f"create_layered_tryon: EXIT - Success, {len(results)} layers processed")
        return success_response(
            data={
                'results': results,
                'final_result_url': final_result['result_url'] if final_result else None,
                'layers_processed': len(results)
            },
            message=f'Layered try-on complete with {len(results)} garments'
        )

    except Exception as e:
        logger.exception(f"create_layered_tryon: EXIT - Error: {str(e)}")
        return error_response_from_string(f'Server error: {str(e)}', 500)


@tryon_bp.route('/tryon-gemini', methods=['POST'])
@require_auth  # JWT decorator validates token and sets request.user_id from token
def tryon_gemini_remote():
    """
    Synchronous try-on using local Gemini API
    Processes try-on request locally and returns result image directly
    
    Optional:
    - avatar_image: File (PNG/JPG/JPEG) - The person's photo to dress (if not provided, uses user's saved avatar)
    
    Required (at least one):
    - garment_image: File (PNG/JPG/JPEG) - Direct garment image file
    - cloth_type: String - 'upper' or 'lower' garment type
    
    Optional Parameters:
    - num_inference_steps: Integer (default 50) - Number of inference steps
    
    Returns:
    - PNG image directly (binary content)
    """
    logger.info("🎯 tryon_gemini_remote: ENTRY - Starting synchronous try-on")
    
    try:
        user_id = request.user_id
        logger.info(f"👤 tryon_gemini_remote: User ID: {user_id}")
        
        # Get avatar image - use provided file or user's saved avatar
        avatar_bytes = None
        
        if 'avatar_image' in request.files:
            avatar_file = request.files['avatar_image']
            if avatar_file and avatar_file.filename:
                logger.info("📸 tryon_gemini_remote: Using provided avatar_image file")
                avatar_bytes = avatar_file.read()
            else:
                logger.warning("⚠️  tryon_gemini_remote: avatar_image file is empty")
        
        # If no avatar file provided, use user's saved avatar
        if not avatar_bytes:
            current_user = User.get_by_id(user_id)
            if current_user and current_user.avatar:
                avatar_bytes = current_user.avatar
                logger.info(f"✅ tryon_gemini_remote: Using user's saved avatar")
            else:
                logger.warning(f"❌ tryon_gemini_remote: No avatar_image provided and user has no saved avatar")
                return error_response_from_string(
                    'No avatar image provided. Please upload an avatar_image file or save an avatar first using /api/save-avatar',
                    400,
                    'INVALID_INPUT'
                )
        
        # Get garment image - this is required
        if 'garment_image' not in request.files:
            logger.warning("❌ tryon_gemini_remote: garment_image is required")
            return error_response_from_string(
                'garment_image file is required',
                400,
                'INVALID_INPUT'
            )
        
        garment_file = request.files['garment_image']
        if not garment_file or not garment_file.filename:
            logger.warning("❌ tryon_gemini_remote: garment_image file is empty")
            return error_response_from_string(
                'garment_image file is empty',
                400,
                'INVALID_INPUT'
            )
        
        garment_bytes = garment_file.read()
        logger.info(f"📦 tryon_gemini_remote: Garment image size: {len(garment_bytes)} bytes")
        
        # Get garment type
        cloth_type = request.form.get('cloth_type', 'upper')
        if cloth_type not in ['upper', 'lower']:
            logger.warning(f"⚠️  tryon_gemini_remote: Invalid cloth_type: {cloth_type}, using 'upper'")
            cloth_type = 'upper'
        logger.info(f"👕 tryon_gemini_remote: Garment type: {cloth_type}")
        
        # Get num_inference_steps
        num_inference_steps = request.form.get('num_inference_steps', '50')
        try:
            num_inference_steps = int(num_inference_steps)
            if num_inference_steps < 1 or num_inference_steps > 100:
                num_inference_steps = 50
        except (ValueError, TypeError):
            num_inference_steps = 50
        logger.info(f"⚙️  tryon_gemini_remote: num_inference_steps: {num_inference_steps}")
        
        # Preprocess images
        logger.info("🔄 tryon_gemini_remote: Preprocessing avatar...")
        avatar_bytes = preprocess_image(avatar_bytes, resize=True, normalize=True)
        logger.info(f"✅ tryon_gemini_remote: Avatar preprocessed: {len(avatar_bytes)} bytes")
        
        logger.info("🔄 tryon_gemini_remote: Preprocessing garment...")
        garment_bytes = preprocess_image(garment_bytes, resize=True, normalize=True)
        logger.info(f"✅ tryon_gemini_remote: Garment preprocessed: {len(garment_bytes)} bytes")
        
        # Remove background from garment
        logger.info("🎨 tryon_gemini_remote: Removing garment background...")
        try:
            from features.tryon.service import _remove_background_local
            garment_bytes = _remove_background_local(garment_bytes)
            logger.info(f"✅ tryon_gemini_remote: Garment background removed: {len(garment_bytes)} bytes")
        except Exception as e:
            logger.warning(f"⚠️  tryon_gemini_remote: Background removal failed: {str(e)}, continuing without removal")
        
        # Call local Gemini try-on service
        logger.info("🤖 tryon_gemini_remote: Calling local Gemini try-on service...")
        try:
            from features.tryon.service import process_tryon
            result_data_url = process_tryon(
                person_image=avatar_bytes,
                garment_image=garment_bytes,
                garment_type=cloth_type,
                garment_details=None,
                options={'num_inference_steps': num_inference_steps}
            )
            logger.info(f"✅ tryon_gemini_remote: Gemini try-on completed")
            
            # Convert data URL to bytes
            if result_data_url.startswith('data:image/png;base64,'):
                result_bytes = base64.b64decode(result_data_url.split(',')[1])
                logger.info(f"✅ tryon_gemini_remote: Converted data URL to bytes: {len(result_bytes)} bytes")
            else:
                logger.error(f"❌ tryon_gemini_remote: Invalid result format from service")
                return error_response_from_string(
                    'Try-on service returned invalid format',
                    500,
                    'GENERATION_ERROR'
                )
        except Exception as e:
            logger.exception(f"❌ tryon_gemini_remote: Gemini try-on failed: {str(e)}")
            return error_response_from_string(
                f'Try-on processing failed: {str(e)}',
                500,
                'GENERATION_ERROR'
            )
        
        # Return PNG image directly
        logger.info("📤 tryon_gemini_remote: Returning result image")
        return Response(
            result_bytes,
            mimetype='image/png'
        )
    
    except Exception as e:
        logger.exception(f"❌ tryon_gemini_remote: EXIT - Error: {str(e)}")
        return error_response_from_string(f'Server error: {str(e)}', 500, 'GENERATION_ERROR')


@tryon_bp.route('/tryon-results', methods=['POST'])
@require_auth  # JWT decorator validates token and sets request.user_id from token
def save_tryon_result():
    """
    Save a try-on result to database
    user_id is extracted from JWT token by @require_auth decorator
    
    Required:
    - result_image: Base64 encoded PNG
    - applied_garments: JSON array of applied garments (e.g., [{"id": 123, "type": "upper"}, ...])
    - try_on_count: Integer (1 or 2)
    - original_avatar: Base64 encoded original avatar
    """
    user_id = request.user_id
    logger.info(f"save_tryon_result: ENTRY - user_id={user_id}")
    
    try:
        # Get required fields from JSON body
        data = request.get_json() or {}
        result_image = data.get('result_image')
        applied_garments = data.get('applied_garments')
        try_on_count = data.get('try_on_count')
        original_avatar = data.get('original_avatar')
        
        # Validation
        if not result_image or not applied_garments or try_on_count is None or not original_avatar:
            logger.warning(f"save_tryon_result: Missing required fields")
            return error_response_from_string(
                'Missing required fields: result_image, applied_garments, try_on_count, original_avatar',
                400,
                'VALIDATION_ERROR'
            )
        
        if try_on_count not in [1, 2]:
            logger.warning(f"save_tryon_result: Invalid try_on_count={try_on_count}")
            return error_response_from_string('try_on_count must be 1 or 2', 400, 'VALIDATION_ERROR')
        
        # Convert applied_garments to JSON if it's a list
        if isinstance(applied_garments, list):
            import json as json_lib
            applied_garments = json_lib.dumps(applied_garments)
        
        # Insert into database
        query = """
            INSERT INTO tryon_results (user_id, result_image, applied_garments, try_on_count, original_avatar)
            VALUES (?, ?, ?, ?, ?)
        """
        result = db_manager.execute_query(query, (user_id, result_image, applied_garments, try_on_count, original_avatar))
        
        logger.info(f"save_tryon_result: EXIT - Successfully saved try-on result")
        return success_response(data={'id': result}, message='Try-on result saved successfully')
        
    except Exception as e:
        logger.exception(f"save_tryon_result: EXIT - Error: {str(e)}")
        return error_response_from_string(f'Failed to save try-on result: {str(e)}', 500, 'DATABASE_ERROR')


@tryon_bp.route('/tryon-results', methods=['GET'])
@require_auth  # JWT decorator validates token and sets request.user_id from token
def get_tryon_results():
    """
    Get all saved try-on results for authenticated user
    user_id is extracted from JWT token by @require_auth decorator
    
    Returns:
    - List of try-on results with id, result_image (thumbnail), applied_garments, try_on_count, created_at
    """
    user_id = request.user_id
    logger.info(f"get_tryon_results: ENTRY - user_id={user_id}")
    
    try:
        query = """
            SELECT id, result_image, applied_garments, try_on_count, created_at
            FROM tryon_results
            WHERE user_id = ?
            ORDER BY created_at DESC
        """
        results = db_manager.execute_query(query, (user_id,), fetch_all=True)
        
        if not results:
            logger.info(f"get_tryon_results: No results found for user_id={user_id}")
            return success_response(data=[])
        
        # Convert results to list of dicts
        import json as json_lib
        results_list = []
        for row in results:
            result_dict = dict(row) if hasattr(row, 'keys') else row
            # Parse applied_garments from JSON string
            if isinstance(result_dict.get('applied_garments'), str):
                result_dict['applied_garments'] = json_lib.loads(result_dict['applied_garments'])
            results_list.append(result_dict)
        
        logger.info(f"get_tryon_results: EXIT - Found {len(results_list)} results")
        return success_response(data=results_list)
        
    except Exception as e:
        logger.exception(f"get_tryon_results: EXIT - Error: {str(e)}")
        return error_response_from_string(f'Failed to fetch try-on results: {str(e)}', 500, 'DATABASE_ERROR')


@tryon_bp.route('/tryon-results/<int:result_id>', methods=['DELETE'])
@require_auth  # JWT decorator validates token and sets request.user_id from token
def delete_tryon_result(result_id):
    """
    Delete a saved try-on result
    user_id is extracted from JWT token by @require_auth decorator
    Only allows deletion of results belonging to authenticated user
    """
    user_id = request.user_id
    logger.info(f"delete_tryon_result: ENTRY - result_id={result_id}, user_id={user_id}")
    
    try:
        # First verify the result belongs to the user
        query = "SELECT user_id FROM tryon_results WHERE id = ?"
        result = db_manager.execute_query(query, (result_id,), fetch_one=True)
        
        if not result:
            logger.warning(f"delete_tryon_result: Result not found - result_id={result_id}")
            return error_response_from_string('Result not found', 404, 'NOT_FOUND')
        
        result_user_id = result.get('user_id')
        if str(result_user_id).strip() != str(user_id).strip():
            logger.warning(f"delete_tryon_result: Unauthorized - result_id={result_id} belongs to user_id={result_user_id}, not {user_id}")
            return error_response_from_string('Unauthorized to delete this result', 403, 'AUTHORIZATION_ERROR')
        
        # Delete the result
        delete_query = "DELETE FROM tryon_results WHERE id = ?"
        db_manager.execute_query(delete_query, (result_id,))
        
        logger.info(f"delete_tryon_result: EXIT - Successfully deleted result_id={result_id}")
        return success_response(message='Try-on result deleted successfully')
        
    except Exception as e:
        logger.exception(f"delete_tryon_result: EXIT - Error: {str(e)}")
        return error_response_from_string(f'Failed to delete try-on result: {str(e)}', 500, 'DATABASE_ERROR')


@tryon_bp.route('/tryon-results/<int:result_id>', methods=['GET'])
@require_auth  # JWT decorator validates token and sets request.user_id from token
def get_tryon_result_details(result_id):
    """
    Get full details of a specific try-on result including original_avatar
    user_id is extracted from JWT token by @require_auth decorator
    """
    user_id = request.user_id
    logger.info(f"get_tryon_result_details: ENTRY - result_id={result_id}, user_id={user_id}")
    
    try:
        query = """
            SELECT id, result_image, original_avatar, applied_garments, try_on_count, created_at
            FROM tryon_results
            WHERE id = ? AND user_id = ?
        """
        result = db_manager.execute_query(query, (result_id, user_id), fetch_one=True)
        
        if not result:
            logger.warning(f"get_tryon_result_details: Result not found - result_id={result_id}")
            return error_response_from_string('Result not found', 404, 'NOT_FOUND')
        
        # Parse JSON if needed
        import json as json_lib
        if isinstance(result.get('applied_garments'), str):
            result['applied_garments'] = json_lib.loads(result['applied_garments'])
        
        logger.info(f"get_tryon_result_details: EXIT - Found result_id={result_id}")
        return success_response(data=result)
        
    except Exception as e:
        logger.exception(f"get_tryon_result_details: EXIT - Error: {str(e)}")
        return error_response_from_string(f'Failed to fetch result details: {str(e)}', 500, 'DATABASE_ERROR')
