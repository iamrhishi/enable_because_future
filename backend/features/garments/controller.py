"""
Garment scraping and categorization API endpoints
"""

from flask import Blueprint, request
import requests  # type: ignore
from bs4 import BeautifulSoup  # type: ignore
import json
import re
from shared.database import db_manager
from shared.response import success_response, error_response_from_string
from shared.middleware import require_auth, optional_auth
from shared.validators import validate_url
from shared.errors import ValidationError
from shared.logger import logger
from shared.garment_utils import categorize_garment

garments_bp = Blueprint('garments', __name__, url_prefix='/api/garments')


@garments_bp.route('/scrape', methods=['POST'])
@optional_auth  # Optional authentication - user_id available if token provided
def scrape_product():
    """
    Scrape comprehensive product information from URL (RECOMMENDED)
    Uses brand-specific extractors (Abstract Factory pattern) for optimal extraction
    Returns: title, price, images, sizes, colors, brand, category, type, confidence
    Uses optional_auth - user_id available if JWT token provided (for caching/user-specific features)
    
    Note: This is the recommended endpoint for extracting product data.
    Use /extract-images only if you need images without other product details.
    """
    # user_id may be available from JWT token if provided (via optional_auth decorator)
    user_id = getattr(request, 'user_id', None)
    logger.info(f"scrape_product: ENTRY - user_id={user_id if user_id else 'anonymous'}")
    try:
        data = request.get_json() or request.form
        url = validate_url(data.get('url', '').strip())
        
        # Check cache first
        cached = db_manager.execute_query(
            "SELECT * FROM garment_metadata WHERE url = ?",
            (url,),
            fetch_one=True
        )
        
        if cached:
            cached_dict = dict(cached)
            # Parse JSON fields
            if cached_dict.get('images'):
                cached_dict['images'] = json.loads(cached_dict['images'])
            if cached_dict.get('sizes'):
                cached_dict['sizes'] = json.loads(cached_dict['sizes'])
            if cached_dict.get('colors'):
                cached_dict['colors'] = json.loads(cached_dict['colors'])
            logger.info(f"scrape_product: EXIT - Returning cached data")
            return success_response(data=cached_dict)
        
        # Use brand-specific extractor
        from features.wardrobe.extractors import BrandExtractorFactory
        extractor = BrandExtractorFactory.get_extractor(url)
        product_info = extractor.extract_product_info(url)
        
        # Categorize garment
        categorization = categorize_garment(title=product_info.get('title'))
        
        # Store in cache
        try:
            db_manager.get_lastrowid(
                """INSERT INTO garment_metadata (url, title, price, images, sizes, colors, brand)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
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
        
        logger.info(f"scrape_product: EXIT - Success, url={url[:100]}")
        return success_response(data=result)
        
    except ValidationError as e:
        logger.exception(f"scrape_product: EXIT - ValidationError: {str(e)}")
        return error_response_from_string(str(e), 400, 'VALIDATION_ERROR')
    except Exception as e:
        logger.exception(f"scrape_product: EXIT - Error: {str(e)}")
        return error_response_from_string(f'Server error: {str(e)}', 500)


@garments_bp.route('/categorize', methods=['POST'])
@optional_auth
def categorize():
    """Categorize a garment from image or metadata"""
    logger.info("categorize: ENTRY")
    try:
        data = request.get_json() or request.form
        
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
        data = request.get_json() or request.form
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

