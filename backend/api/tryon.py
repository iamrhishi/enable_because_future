"""
Try-On API endpoints with async job processing
"""

from flask import Blueprint, request, send_file
from io import BytesIO
import base64
import json
import requests
from services.job_queue import job_queue
from services.database import db_manager
from services.image_processing import preprocess_image, fetch_image_from_url, validate_image
from api.garments import categorize_garment
from utils.response import success_response, error_response_from_string
from utils.middleware import require_auth
from utils.logger import logger
from utils.validators import validate_url

tryon_bp = Blueprint('tryon', __name__, url_prefix='/api')


@tryon_bp.route('/tryon', methods=['POST'])
@require_auth
def create_tryon_job():
    """
    Create a new try-on job (async)
    
    Per context.md API contract (lines 121-139):
    - Accepts: selfie (multipart), item_urls[] (JSON array), options (optional)
    - Returns: job_id, status: queued
    """
    logger.info("create_tryon_job: ENTRY")
    
    try:
        user_id = request.user_id
        
        # Get person image (selfie or avatar_id)
        # Per context.md: 'selfie' field name
        person_image = None
        if 'selfie' in request.files:
            person_image = request.files['selfie'].read()
        elif 'person_image' in request.files:
            person_image = request.files['person_image'].read()
        elif 'avatar_id' in request.form:
            # Fetch avatar from database
            avatar_data = db_manager.execute_query(
                "SELECT avatar FROM users WHERE userid = ?",
                (request.form.get('avatar_id'),),
                fetch_one=True
            )
            if avatar_data and avatar_data.get('avatar'):
                person_image = avatar_data['avatar']
        
        if not person_image:
            return error_response_from_string('selfie/person_image or avatar_id required', 400, 'VALIDATION_ERROR')
        
        # Preprocess person image
        try:
            person_image = preprocess_image(person_image, resize=True, normalize=True)
        except Exception as e:
            logger.exception(f"create_tryon_job: Person image preprocessing failed: {str(e)}")
            return error_response_from_string(f'Person image validation failed: {str(e)}', 400, 'VALIDATION_ERROR')
        
        # Get garment image - support multiple methods per context.md
        garment_image = None
        garment_type = 'upper'  # Default
        
        # Method 1: Direct image file
        if 'garment_image' in request.files:
            garment_image = request.files['garment_image'].read()
        
        # Method 2: item_urls[] array (per context.md line 125) - PRIMARY METHOD
        if not garment_image and 'item_urls' in request.form:
            item_urls_str = request.form.get('item_urls')
            try:
                item_urls = json.loads(item_urls_str) if isinstance(item_urls_str, str) else item_urls_str
                if not isinstance(item_urls, list):
                    return error_response_from_string('item_urls must be a JSON array', 400, 'VALIDATION_ERROR')
                
                if not item_urls:
                    return error_response_from_string('item_urls array cannot be empty', 400, 'VALIDATION_ERROR')
                
                # Get garment_index from options (per context.md line 131)
                options = {}
                if 'options' in request.form:
                    try:
                        options = json.loads(request.form.get('options')) if isinstance(request.form.get('options'), str) else request.form.get('options')
                    except:
                        options = {}
                
                garment_index = options.get('garment_index', 0)
                if garment_index >= len(item_urls):
                    garment_index = 0
                
                item_url = item_urls[garment_index]
                logger.info(f"create_tryon_job: Processing item_url[{garment_index}]: {item_url[:100]}")
                
                # Try to scrape product page first (if it's a product URL)
                # Use internal scraping logic instead of calling the endpoint
                try:
                    from bs4 import BeautifulSoup  # type: ignore
                    from urllib.parse import urljoin
                    
                    # Check if URL looks like a product page (has domain, not direct image)
                    if not any(item_url.lower().endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.webp', '.gif']):
                        # Likely a product page, try scraping
                        headers = {
                            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                        }
                        scrape_response = requests.get(item_url, headers=headers, timeout=10)
                        if scrape_response.status_code == 200:
                            soup = BeautifulSoup(scrape_response.text, 'html.parser')
                            
                            # Extract images
                            img_tags = soup.find_all('img', src=True)
                            for img in img_tags[:10]:
                                img_url = img.get('src') or img.get('data-src') or img.get('data-lazy-src')
                                if img_url:
                                    if not img_url.startswith('http'):
                                        img_url = urljoin(item_url, img_url)
                                    # Try to fetch this image
                                    try:
                                        garment_image = fetch_image_from_url(img_url)
                                        logger.info(f"create_tryon_job: Successfully fetched scraped image: {img_url[:100]}")
                                        
                                        # Try to get title for categorization
                                        title_elem = soup.find('h1') or soup.find('title')
                                        title = title_elem.get_text().strip() if title_elem else None
                                        if title:
                                            categorization = categorize_garment(title=title)
                                            garment_type = categorization.get('category', 'upper')
                                            logger.info(f"create_tryon_job: Detected garment_type={garment_type} from title")
                                        
                                        break  # Successfully got image
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
        
        # Method 3: Single garment_url (backward compatibility)
        if not garment_image and 'garment_url' in request.form:
            garment_url = request.form.get('garment_url')
            try:
                garment_image = fetch_image_from_url(garment_url)
            except Exception as e:
                logger.exception(f"create_tryon_job: Failed to fetch image from URL: {str(e)}")
                return error_response_from_string(f'Failed to fetch garment image from URL: {str(e)}', 400, 'VALIDATION_ERROR')
        
        if not garment_image:
            return error_response_from_string('garment_image, garment_url, or item_urls required', 400, 'VALIDATION_ERROR')
        
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
                options = json.loads(request.form.get('options')) if isinstance(request.form.get('options'), str) else request.form.get('options')
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
                options = json.loads(request.form.get('options')) if isinstance(request.form.get('options'), str) else request.form.get('options')
                if not isinstance(options, dict):
                    options = {}
            except:
                options = {}
        
        if 'num_inference_steps' in request.form:
            options['num_inference_steps'] = request.form.get('num_inference_steps')
        
        # Create job
        job_id = job_queue.create_job(
            user_id=user_id,
            person_image=person_image,
            garment_image=garment_image,
            garment_type=garment_type,
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
@require_auth
def get_job_status(job_id):
    """Get try-on job status"""
    try:
        job = job_queue.get_job_status(job_id)
        
        if not job:
            return error_response_from_string('Job not found', 404, 'NOT_FOUND')
        
        # Verify user owns this job
        if job['user_id'] != request.user_id:
            return error_response_from_string('Not authorized', 403, 'AUTHORIZATION_ERROR')
        
        return success_response(data=job)
        
    except Exception as e:
        logger.error(f"Error getting job status: {str(e)}")
        return error_response_from_string(f'Server error: {str(e)}', 500)


@tryon_bp.route('/job/<job_id>/result', methods=['GET'])
@require_auth
def get_job_result(job_id):
    """Get try-on result image"""
    try:
        job = job_queue.get_job_status(job_id)
        
        if not job:
            return error_response_from_string('Job not found', 404, 'NOT_FOUND')
        
        # Verify user owns this job
        if job['user_id'] != request.user_id:
            return error_response_from_string('Not authorized', 403, 'AUTHORIZATION_ERROR')
        
        if job['status'] != 'done':
            return error_response_from_string(f'Job not completed. Status: {job["status"]}', 202, 'JOB_PENDING')
        
        if not job.get('result_url'):
            return error_response_from_string('Result not available', 404, 'NOT_FOUND')
        
        # If result is base64 data URL, decode and return
        if job['result_url'].startswith('data:image'):
            # Extract base64 data
            header, encoded = job['result_url'].split(',', 1)
            image_data = base64.b64decode(encoded)
            return send_file(BytesIO(image_data), mimetype='image/png')
        
        # Otherwise, result_url is a file path or URL
        # For now, return the URL (client can fetch it)
        return success_response(data={'result_url': job['result_url']})
        
    except Exception as e:
        logger.error(f"Error getting job result: {str(e)}")
        return error_response_from_string(f'Server error: {str(e)}', 500)


@tryon_bp.route('/tryon/multi', methods=['POST'])
@require_auth
def create_multi_tryon_job():
    """Create multi-garment try-on job (top + bottom)"""
    try:
        user_id = request.user_id
        
        # Get person image
        person_image = None
        if 'person_image' in request.files:
            person_image = request.files['person_image'].read()
        elif 'avatar_id' in request.form:
            avatar_data = db_manager.execute_query(
                "SELECT avatar FROM users WHERE userid = ?",
                (request.form.get('avatar_id'),),
                fetch_one=True
            )
            if avatar_data and avatar_data.get('avatar'):
                person_image = avatar_data['avatar']
        
        if not person_image:
            return error_response_from_string('person_image or avatar_id required', 400, 'VALIDATION_ERROR')
        
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
        top_job_id = job_queue.create_job(user_id, person_image, top_image, 'upper')
        
        # Then process bottom (in real implementation, would composite both)
        bottom_job_id = job_queue.create_job(user_id, person_image, bottom_image, 'lower')
        
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
        logger.error(f"Error creating multi-garment try-on: {str(e)}")
        return error_response_from_string(f'Server error: {str(e)}', 500)

