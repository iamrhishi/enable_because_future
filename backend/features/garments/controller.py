"""
Garment scraping and categorization API endpoints
"""

from flask import Blueprint, request
import requests  # type: ignore
from bs4 import BeautifulSoup  # type: ignore
import json
import re
from datetime import datetime, timedelta
from shared.database import db_manager
from shared.response import success_response, error_response_from_string
from shared.middleware import require_auth, optional_auth
from shared.validators import validate_url
from shared.errors import ValidationError
from shared.logger import logger
from shared.garment_utils import categorize_garment

garments_bp = Blueprint('garments', __name__, url_prefix='/api/garments')


def _is_cache_valid(cached_dict, force_refresh=False):
    """
    Check if cached data is valid (has data and is not expired)
    Cache is valid for 3 days
    """
    if force_refresh:
        return False
    
    # Check if cache has valid data
    has_valid_data = (
        cached_dict.get('title') and cached_dict.get('title').strip() or
        cached_dict.get('images') and len(cached_dict.get('images', [])) > 0
    )
    
    if not has_valid_data:
        return False
    
    # Check if cache is expired (older than 3 days)
    scraped_at_str = cached_dict.get('scraped_at') or cached_dict.get('updated_at')
    if scraped_at_str:
        try:
            if isinstance(scraped_at_str, str):
                scraped_at = datetime.strptime(scraped_at_str, '%Y-%m-%d %H:%M:%S')
            else:
                scraped_at = scraped_at_str
            cache_age = datetime.now() - scraped_at
            if cache_age > timedelta(days=3):
                logger.info(f"Cache expired (age: {cache_age.days} days)")
                return False
        except Exception as e:
            logger.warning(f"Failed to parse cache date: {str(e)}")
            return False
    
    return True


def _scrape_and_cache(url):
    """Helper function to scrape product and cache result"""
    # Use brand-specific extractor
    from features.wardrobe.extractors import BrandExtractorFactory
    extractor = BrandExtractorFactory.get_extractor(url)
    product_info = extractor.extract_product_info(url)
    
    # Categorize garment
    categorization = categorize_garment(title=product_info.get('title'))
    
    # Store/update in cache (INSERT OR REPLACE)
    try:
        db_manager.execute_query(
            """INSERT OR REPLACE INTO garment_metadata 
               (url, title, price, images, sizes, colors, brand, scraped_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)""",
            (url, product_info.get('title'), product_info.get('price'),
             json.dumps(product_info.get('images', [])),
             json.dumps(product_info.get('sizes', [])),
             json.dumps(product_info.get('colors', [])),
             product_info.get('brand'))
        )
    except Exception as e:
        logger.warning(f"Failed to cache garment metadata: {str(e)}")
    
    result = {
        'url': url,
        'title': product_info.get('title'),
        'price': product_info.get('price'),
        'images': product_info.get('images', []),
        'sizes': product_info.get('sizes', []),
        'colors': product_info.get('colors', []),
        'brand': product_info.get('brand'),
        'category': categorization['category'],
        'type': categorization['type'],
        'confidence': categorization['confidence']
    }
    
    return result


@garments_bp.route('/scrape', methods=['POST'])
@optional_auth  # Optional authentication - user_id available if token provided
def scrape_product():
    """
    Scrape comprehensive product information from URL (RECOMMENDED)
    Uses brand-specific extractors (Abstract Factory pattern) for optimal extraction
    Returns: title, price, images, sizes, colors, brand, category, type, confidence
    
    Query Parameters:
    - force_refresh (boolean): If true, bypasses cache and forces re-scraping
    
    Cache: Results are cached for 3 days to save Scrape.do credits.
    After 3 days, cache expires and fresh data is fetched automatically.
    
    Note: This is the recommended endpoint for extracting product data.
    Use /extract-images only if you need images without other product details.
    """
    # user_id may be available from JWT token if provided (via optional_auth decorator)
    user_id = getattr(request, 'user_id', None)
    logger.info(f"scrape_product: ENTRY - user_id={user_id if user_id else 'anonymous'}")
    try:
        # Handle both JSON and form-data safely
        content_type = request.content_type or ''
        if 'application/json' in content_type:
            data = request.get_json(silent=True, force=False) or {}
        else:
            data = request.form
        url = validate_url(data.get('url', '').strip())
        
        # Check for force_refresh parameter
        force_refresh = False
        if isinstance(data, dict):
            force_refresh = data.get('force_refresh', False) in [True, 'true', 'True', '1', 1]
        elif hasattr(request, 'args'):
            force_refresh = request.args.get('force_refresh', 'false').lower() in ['true', '1']
        
        if force_refresh:
            logger.info(f"scrape_product: Force refresh requested, bypassing cache")
            # Delete existing cache if any
            try:
                db_manager.execute_query(
                    "DELETE FROM garment_metadata WHERE url = ?",
                    (url,)
                )
            except Exception as e:
                logger.warning(f"Failed to delete cache for force refresh: {str(e)}")
        else:
            # Check cache first - return if valid and not expired
            cached = db_manager.execute_query(
                "SELECT * FROM garment_metadata WHERE url = ?",
                (url,),
                fetch_one=True
            )
            
            if cached:
                # Safely convert cached row to dict, filtering out non-serializable values
                cached_dict = {}
                for k, v in dict(cached).items():
                    if isinstance(v, bytes):
                        continue
                    try:
                        json.dumps(v)
                        cached_dict[k] = v
                    except (TypeError, ValueError):
                        if hasattr(v, 'isoformat'):
                            cached_dict[k] = v.isoformat()
                        else:
                            continue
                
                # Parse JSON fields
                if cached_dict.get('images'):
                    try:
                        cached_dict['images'] = json.loads(cached_dict['images'])
                    except:
                        cached_dict['images'] = []
                if cached_dict.get('sizes'):
                    try:
                        cached_dict['sizes'] = json.loads(cached_dict['sizes'])
                    except:
                        cached_dict['sizes'] = []
                if cached_dict.get('colors'):
                    try:
                        cached_dict['colors'] = json.loads(cached_dict['colors'])
                    except:
                        cached_dict['colors'] = []
                
                # Check if cache is valid (has data and not expired)
                if _is_cache_valid(cached_dict, force_refresh=False):
                    logger.info(f"scrape_product: EXIT - Returning cached data (valid for 3 days)")
                    return success_response(data=cached_dict)
                else:
                    logger.info(f"scrape_product: Cache expired or invalid, re-scraping")
                    # Delete expired/invalid cache entry
                    try:
                        db_manager.execute_query(
                            "DELETE FROM garment_metadata WHERE url = ?",
                            (url,)
                        )
                    except Exception as e:
                        logger.warning(f"Failed to delete expired cache: {str(e)}")
        
        # Scrape fresh data
        result = _scrape_and_cache(url)
        
        logger.info(f"scrape_product: EXIT - Success, url={url[:100]}")
        return success_response(data=result)
        
    except ValidationError as e:
        logger.exception(f"scrape_product: EXIT - ValidationError: {str(e)}")
        return error_response_from_string(str(e), 400, 'VALIDATION_ERROR')
    except Exception as e:
        logger.exception(f"scrape_product: EXIT - Error: {str(e)}")
        return error_response_from_string(f'Server error: {str(e)}', 500)


@garments_bp.route('/refresh', methods=['POST'])
@optional_auth
def refresh_product():
    """
    Force refresh product data by re-scraping (bypasses cache)
    This endpoint always fetches fresh data regardless of cache status.
    Useful when user suspects data is outdated.
    
    Request Body:
    {
        "url": "https://example.com/product"
    }
    
    Returns: Fresh scraped product data (same format as /scrape)
    """
    user_id = getattr(request, 'user_id', None)
    logger.info(f"refresh_product: ENTRY - user_id={user_id if user_id else 'anonymous'}")
    try:
        # Handle both JSON and form-data safely
        content_type = request.content_type or ''
        if 'application/json' in content_type:
            data = request.get_json(silent=True, force=False) or {}
        else:
            data = request.form
        url = validate_url(data.get('url', '').strip())
        
        # Always delete existing cache and re-scrape
        logger.info(f"refresh_product: Force refresh - deleting cache and re-scraping")
        try:
            db_manager.execute_query(
                "DELETE FROM garment_metadata WHERE url = ?",
                (url,)
            )
        except Exception as e:
            logger.warning(f"Failed to delete cache: {str(e)}")
        
        # Scrape fresh data
        result = _scrape_and_cache(url)
        
        logger.info(f"refresh_product: EXIT - Success, url={url[:100]}")
        return success_response(data=result, message="Product data refreshed successfully")
        
    except ValidationError as e:
        logger.exception(f"refresh_product: EXIT - ValidationError: {str(e)}")
        return error_response_from_string(str(e), 400, 'VALIDATION_ERROR')
    except Exception as e:
        logger.exception(f"refresh_product: EXIT - Error: {str(e)}")
        return error_response_from_string(f'Server error: {str(e)}', 500)


@garments_bp.route('/categorize', methods=['POST'])
@optional_auth
def categorize():
    """Categorize a garment from image or metadata"""
    logger.info("categorize: ENTRY")
    try:
        # Handle both JSON and form-data safely
        content_type = request.content_type or ''
        if 'application/json' in content_type:
            data = request.get_json(silent=True, force=False) or {}
        else:
            data = request.form
        
        image_url = data.get('image_url')
        image_data = None
        if 'image' in request.files:
            image_data = request.files['image'].read()
        title = data.get('title', '')
        
        categorization = categorize_garment(
            image_url=image_url,
            image_data=image_data,
            title=title
        )
        
        logger.info("categorize: EXIT - Success")
        return success_response(data=categorization)
        
    except Exception as e:
        logger.exception(f"categorize: EXIT - Error: {str(e)}")
        return error_response_from_string(f'Error categorizing: {str(e)}', 500)


@garments_bp.route('/extract-images', methods=['POST'])
@optional_auth
def extract_images():
    """
    Extract images from URL using brand-specific extractors
    This endpoint uses the same extraction logic as /scrape but only returns images
    For better results, use /scrape which returns images, title, price, sizes, colors, and categorization
    """
    # user_id may be available from JWT token if provided (via optional_auth decorator)
    user_id = getattr(request, 'user_id', None)
    logger.info(f"extract_images: ENTRY - user_id={user_id if user_id else 'anonymous'}")
    try:
        # Handle both JSON and form-data safely
        content_type = request.content_type or ''
        if 'application/json' in content_type:
            data = request.get_json(silent=True, force=False) or {}
        else:
            data = request.form
        url = validate_url(data.get('url', '').strip())
        
        # Use brand-specific extractor (same as /scrape endpoint)
        from features.wardrobe.extractors import BrandExtractorFactory
        extractor = BrandExtractorFactory.get_extractor(url)
        product_info = extractor.extract_product_info(url)
        
        images = product_info.get('images', [])
        
        if not images:
            reason = "No product images found. Possible reasons: " + \
                    "1) Page requires JavaScript to load images (modern e-commerce sites), " + \
                    "2) Images are loaded dynamically via AJAX, " + \
                    "3) Page structure changed, " + \
                    "4) Access blocked or page not accessible. " + \
                    "Try using /api/garments/scrape for more comprehensive extraction with brand-specific logic."
            logger.warning(f"extract_images: No images found for url={url[:100]}")
            return success_response(
                data={'images': [], 'reason': reason, 'url': url},
                message='No images extracted'
            )
        
        logger.info(f"extract_images: EXIT - Success, found {len(images)} images")
        return success_response(data={'images': images[:3], 'url': url})  # Return top 3 images
        
    except ValidationError as e:
        logger.exception(f"extract_images: EXIT - ValidationError: {str(e)}")
        return error_response_from_string(str(e), 400, 'VALIDATION_ERROR')
    except Exception as e:
        logger.exception(f"extract_images: EXIT - Error: {str(e)}")
        reason = f"Extraction failed: {str(e)}. " + \
                "Possible reasons: " + \
                "1) Page requires JavaScript to load content, " + \
                "2) Access blocked or rate-limited, " + \
                "3) Invalid URL or page structure changed. " + \
                "Try using /api/garments/scrape for more comprehensive extraction with brand-specific logic."
        return error_response_from_string(reason, 500, 'EXTRACTION_ERROR')

