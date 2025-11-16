"""
Garment scraping and categorization API endpoints
"""

from flask import Blueprint, request
import requests  # type: ignore
from bs4 import BeautifulSoup  # type: ignore
import json
import re
from services.database import db_manager
from utils.response import success_response, error_response_from_string
from utils.middleware import require_auth, optional_auth
from utils.validators import validate_url
from utils.logger import logger

garments_bp = Blueprint('garments', __name__, url_prefix='/api/garments')


def categorize_garment(image_url: str = None, image_data: bytes = None, title: str = None) -> dict:
    """
    Categorize garment using rule-based classification
    
    Returns:
        dict with category, type, confidence
    """
    logger.info(f"categorize_garment: ENTRY - title={title[:50] if title else None}")
    
    try:
        category = None
        garment_type = None
        confidence = 0.5
        
        # Rule-based classification using keywords
        text = (title or '').lower()
        
        # Upper body categories
        upper_keywords = {
            'shirt': ['shirt', 'blouse', 'top', 'tee', 't-shirt', 'tank', 'cami'],
            'jacket': ['jacket', 'coat', 'blazer', 'cardigan', 'hoodie', 'sweater'],
            'dress': ['dress', 'gown', 'frock'],
            'top': ['top', 'blouse', 'shirt']
        }
        
        # Lower body categories
        lower_keywords = {
            'pants': ['pants', 'trousers', 'jeans', 'slacks'],
            'shorts': ['shorts', 'bermuda'],
            'skirt': ['skirt'],
            'leggings': ['leggings', 'tights']
        }
        
        # Check for upper body
        for gtype, keywords in upper_keywords.items():
            if any(kw in text for kw in keywords):
                category = 'upper'
                garment_type = gtype
                confidence = 0.8
                break
        
        # Check for lower body
        if not category:
            for gtype, keywords in lower_keywords.items():
                if any(kw in text for kw in keywords):
                    category = 'lower'
                    garment_type = gtype
                    confidence = 0.8
                    break
        
        # Default category if no match found
        if not category:
            if 'dress' in text:
                category = 'upper'
                garment_type = 'dress'
                confidence = 0.6
            else:
                category = 'upper'  # Default
                garment_type = 'top'
                confidence = 0.3
        
        result = {
            'category': category,
            'type': garment_type,
            'confidence': confidence
        }
        logger.info(f"categorize_garment: EXIT - result={result}")
        return result
    except Exception as e:
        logger.exception(f"categorize_garment: EXIT - Error: {str(e)}")
        raise


@garments_bp.route('/scrape', methods=['POST'])
@optional_auth
def scrape_product():
    """Scrape product information from URL"""
    logger.info("scrape_product: ENTRY")
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
            return success_response(data=dict(cached))
        
        # Scrape product page
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Extract product information (basic implementation)
        title = None
        price = None
        images = []
        sizes = []
        colors = []
        
        # Try to find title
        title_elem = soup.find('h1') or soup.find('title')
        if title_elem:
            title = title_elem.get_text().strip()
        
        # Try to find price
        price_elem = soup.find(class_=re.compile('price', re.I))
        if price_elem:
            price = price_elem.get_text().strip()
        
        # Try to find images
        img_tags = soup.find_all('img', src=True)
        for img in img_tags[:10]:  # Limit to 10 images
            img_url = img.get('src') or img.get('data-src')
            if img_url:
                if not img_url.startswith('http'):
                    # Make absolute URL
                    from urllib.parse import urljoin
                    img_url = urljoin(url, img_url)
                images.append(img_url)
        
        # Try to find sizes (basic - would need site-specific logic)
        size_elements = soup.find_all(text=re.compile(r'\b(XS|S|M|L|XL|XXL|\d+)\b'))
        sizes = list(set([s.strip() for s in size_elements if len(s.strip()) <= 5]))[:10]
        
        # Categorize garment
        categorization = categorize_garment(title=title)
        
        # Store in cache
        try:
            db_manager.get_lastrowid(
                """INSERT INTO garment_metadata (url, title, price, images, sizes, colors)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (url, title, price, json.dumps(images), json.dumps(sizes), json.dumps(colors))
            )
        except Exception as e:
            logger.warning(f"Failed to cache garment metadata: {str(e)}")
        
        result = {
            'url': url,
            'title': title,
            'price': price,
            'images': images,
            'sizes': sizes,
            'colors': colors,
            'category': categorization['category'],
            'type': categorization['type'],
            'confidence': categorization['confidence']
        }
        
        logger.info("scrape_product: EXIT - Success")
        return success_response(data=result)
        
    except Exception as e:
        logger.exception(f"scrape_product: EXIT - Error: {str(e)}")
        return error_response_from_string(f'Error scraping product: {str(e)}', 500)


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
    """Extract images from URL"""
    logger.info("extract_images: ENTRY")
    try:
        data = request.get_json() or request.form
        url = validate_url(data.get('url', '').strip())
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        images = []
        
        img_tags = soup.find_all('img', src=True)
        for img in img_tags:
            img_url = img.get('src') or img.get('data-src') or img.get('data-lazy-src')
            if img_url:
                if not img_url.startswith('http'):
                    from urllib.parse import urljoin
                    img_url = urljoin(url, img_url)
                images.append(img_url)
        
        # Remove duplicates
        images = list(dict.fromkeys(images))
        
        logger.info(f"extract_images: EXIT - Success, found {len(images)} images")
        return success_response(data={'images': images[:20]})  # Limit to 20 images
        
    except Exception as e:
        logger.exception(f"extract_images: EXIT - Error: {str(e)}")
        return error_response_from_string(f'Error extracting images: {str(e)}', 500)

