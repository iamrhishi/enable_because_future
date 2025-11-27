"""
Brand-specific product extractors using Abstract Factory pattern
Supports Zara and other brands with a default fallback extractor
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional
from urllib.parse import urlparse
import requests  # type: ignore
from bs4 import BeautifulSoup  # type: ignore
from scrapy.selector import Selector  # type: ignore
import re
import json
from shared.logger import logger
from shared.errors import ExternalServiceError
from config import Config


class BrandExtractor(ABC):
    """Abstract base class for brand-specific product extractors"""
    
    @abstractmethod
    def extract_product_info(self, url: str, html_content: str = None) -> Dict:
        """
        Extract product information from URL
        
        Args:
            url: Product page URL
            html_content: Optional pre-fetched HTML content
            
        Returns:
            dict with keys: title, price, images, sizes, colors, brand, description
        """
        pass
    
    @abstractmethod
    def can_extract(self, url: str) -> bool:
        """Check if this extractor can handle the given URL"""
        pass


class DefaultExtractor(BrandExtractor):
    """Default extractor for unknown brands - generic extraction"""
    
    def can_extract(self, url: str) -> bool:
        """Default extractor can handle any URL"""
        return True
    
    def extract_product_info(self, url: str, html_content: str = None) -> Dict:
        """Generic product extraction"""
        logger.info(f"DefaultExtractor.extract_product_info: ENTRY - url={url[:100]}")
        
        try:
            if not html_content:
                from features.garments.scraper import fetch_html
                html_content = fetch_html(url, retry_with_different_ua=True)
                if not html_content:
                    raise ExternalServiceError("Failed to fetch HTML content. Site may be blocking requests or require JavaScript.", service='default-extractor')
            
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Extract title using centralized utility
            from features.garments.scraper import extract_title_from_html
            title = extract_title_from_html(html_content)
            
            # Extract price
            price = None
            price_elem = soup.find(class_=re.compile('price', re.I))
            if price_elem:
                price = price_elem.get_text().strip()
            
            # Extract images using centralized utility
            from features.garments.scraper import extract_images_from_html
            images = extract_images_from_html(html_content, url, max_images=20)
            
            # Extract sizes
            sizes = []
            size_elements = soup.find_all(text=re.compile(r'\b(XS|S|M|L|XL|XXL|\d+)\b'))
            sizes = list(set([s.strip() for s in size_elements if len(s.strip()) <= 5]))[:10]
            
            # Extract colors
            colors = []
            color_elements = soup.find_all(class_=re.compile('color', re.I))
            for elem in color_elements[:10]:
                color_text = elem.get_text().strip()
                if color_text and len(color_text) < 50:
                    colors.append(color_text)
            
            result = {
                'title': title,
                'price': price,
                'images': images,
                'sizes': sizes,
                'colors': colors,
                'brand': None,  # Will be detected from URL or title
                'description': None
            }
            
            logger.info(f"DefaultExtractor.extract_product_info: EXIT - Success, found {len(images)} images")
            return result
            
        except Exception as e:
            logger.exception(f"DefaultExtractor.extract_product_info: EXIT - Error: {str(e)}")
            raise ExternalServiceError(f"Failed to extract product info: {str(e)}", service='extractor')


class ZaraExtractor(BrandExtractor):
    """Zara-specific product extractor"""
    
    def can_extract(self, url: str) -> bool:
        """Check if URL is from Zara"""
        parsed = urlparse(url)
        return 'zara.com' in parsed.netloc.lower()
    
    def extract_product_info(self, url: str, html_content: str = None) -> Dict:
        """Extract product information from Zara product page using Scrape.do + Scrapy"""
        logger.info(f"ZaraExtractor.extract_product_info: ENTRY - url={url[:100]}")
        
        try:
            if not html_content:
                # Use Scrape.do to fetch HTML with residential proxies and JavaScript rendering
                html_content = self._fetch_with_scrape_do(url)
                if not html_content:
                    raise ExternalServiceError("Failed to fetch HTML content via Scrape.do.", service='zara-extractor')
            
            # Log HTML size and first 500 chars for debugging
            logger.info(f"ZaraExtractor: Received HTML size={len(html_content)} chars")
            if len(html_content) < 5000:
                logger.warning(f"ZaraExtractor: HTML is very small ({len(html_content)} chars), likely a bot detection page. First 500 chars: {html_content[:500]}")
            
            # Use Scrapy Selector for parsing (more powerful than BeautifulSoup for complex selectors)
            selector = Selector(text=html_content)
            soup = BeautifulSoup(html_content, 'html.parser')  # Keep for compatibility with existing methods
            
            # Try to extract from JSON-LD structured data first (most reliable)
            json_ld_data = self._extract_json_ld(soup)
            if json_ld_data:
                logger.info("ZaraExtractor: Found JSON-LD structured data")
                json_ld_result = self._parse_json_ld(json_ld_data, url)
                normalized_json_ld_images: List[str] = []
                for img_url in json_ld_result.get('images', []):
                    normalized = self._normalize_image_url(img_url, url)
                    if normalized and normalized_json_ld_images.count(normalized) == 0:
                        normalized_json_ld_images.append(normalized)
                json_ld_result['images'] = normalized_json_ld_images
                
                # If JSON-LD doesn't include enough images/details, augment with Scrapy extraction
                needs_augmentation = len(json_ld_result.get('images', [])) < 3 or not json_ld_result.get('sizes')
                if needs_augmentation:
                    logger.info("ZaraExtractor: JSON-LD missing details, augmenting with Scrapy selectors")
                    scrapy_result = self._extract_with_scrapy(selector, soup, html_content, url)
                    if scrapy_result:
                        combined_images: List[str] = []
                        for img_url in (json_ld_result.get('images') or []) + (scrapy_result.get('images') or []):
                            normalized = self._normalize_image_url(img_url, url)
                            if normalized and normalized not in combined_images:
                                combined_images.append(normalized)
                        json_ld_result['images'] = combined_images
                        for key in ['title', 'price', 'sizes', 'colors', 'brand', 'description']:
                            if not json_ld_result.get(key):
                                json_ld_result[key] = scrapy_result.get(key)
                return json_ld_result
            else:
                logger.info("ZaraExtractor: No JSON-LD structured data found")
            
            # Try to extract from script tags (Zara often embeds product data in scripts)
            script_data = self._extract_from_scripts(soup)
            if script_data:
                logger.info("ZaraExtractor: Found product data in script tags")
                return script_data
            else:
                logger.info("ZaraExtractor: No product data found in script tags")
            
            # Use Scrapy selectors for HTML parsing (more robust)
            logger.info("ZaraExtractor: Attempting HTML parsing with Scrapy selectors")
            return self._extract_with_scrapy(selector, soup, html_content, url)
            
        except Exception as e:
            logger.exception(f"ZaraExtractor.extract_product_info: EXIT - Error: {str(e)}")
            raise ExternalServiceError(f"Failed to extract Zara product info: {str(e)}", service='zara-extractor')
    
    def _fetch_with_scrape_do(self, url: str) -> Optional[str]:
        """Fetch HTML using Scrape.do with residential proxies and JavaScript rendering"""
        logger.info(f"ZaraExtractor._fetch_with_scrape_do: ENTRY - url={url[:100]}")
        
        if not Config.SCRAPE_DO_ENABLED or not Config.SCRAPE_DO_API_KEY:
            logger.error("ZaraExtractor._fetch_with_scrape_do: Scrape.do not enabled or key missing")
            raise ExternalServiceError("Scrape.do is required for Zara extraction but is not configured. Set SCRAPE_DO_API_KEY and SCRAPE_DO_ENABLED=True in .env", service='scrape-do')
        
        # Scrape.do endpoint - format: http://api.scrape.do/?url=<encoded>&token=<key>&render=true&super=true
        from urllib.parse import quote
        encoded_url = quote(url, safe='')
        scrape_do_url = (
            f"http://api.scrape.do/"
            f"?url={encoded_url}"
            f"&token={Config.SCRAPE_DO_API_KEY}"
            f"&render=true"
            f"&super=true"
            f"&blockResources=false"
        )
        
        try:
            response = requests.get(scrape_do_url, timeout=60)
            response.raise_for_status()
            
            html_content = response.text
            logger.info(f"ZaraExtractor._fetch_with_scrape_do: EXIT - Success, size={len(html_content)} chars")
            return html_content
            
        except requests.exceptions.RequestException as e:
            logger.exception(f"ZaraExtractor._fetch_with_scrape_do: EXIT - Scrape.do request failed: {str(e)}")
            raise ExternalServiceError(f"Scrape.do request failed: {str(e)}", service='scrape-do')
        except Exception as e:
            logger.exception(f"ZaraExtractor._fetch_with_scrape_do: EXIT - Unexpected error: {str(e)}")
            raise ExternalServiceError(f"Failed to fetch HTML via Scrape.do: {str(e)}", service='scrape-do')
    
    def _extract_json_ld(self, soup: BeautifulSoup) -> Optional[Dict]:
        """Extract JSON-LD structured data"""
        try:
            json_ld_scripts = soup.find_all('script', type='application/ld+json')
            for script in json_ld_scripts:
                try:
                    data = json.loads(script.string)
                    if isinstance(data, dict) and data.get('@type') in ['Product', 'ItemPage']:
                        return data
                    elif isinstance(data, list):
                        for item in data:
                            if isinstance(item, dict) and item.get('@type') in ['Product', 'ItemPage']:
                                return item
                except json.JSONDecodeError:
                    continue
        except Exception as e:
            logger.warning(f"ZaraExtractor._extract_json_ld: Error parsing JSON-LD: {str(e)}")
        return None
    
    def _parse_json_ld(self, data: Dict, base_url: str) -> Dict:
        """Parse JSON-LD structured data into product info"""
        from urllib.parse import urljoin
        
        images = []
        if 'image' in data:
            if isinstance(data['image'], list):
                images = [urljoin(base_url, img) if not img.startswith('http') else img 
                         for img in data['image'] if img]
            elif isinstance(data['image'], str):
                images = [urljoin(base_url, data['image']) if not data['image'].startswith('http') else data['image']]
        
        # Also check for offers/price
        price = None
        if 'offers' in data:
            offers = data['offers']
            if isinstance(offers, dict) and 'price' in offers:
                price = str(offers['price'])
            elif isinstance(offers, list) and len(offers) > 0 and 'price' in offers[0]:
                price = str(offers[0]['price'])
        
        return {
            'title': data.get('name', ''),
            'price': price,
            'images': images[:20],  # Limit to 20 images
            'sizes': [],
            'colors': [],
            'brand': 'Zara',
            'description': data.get('description', '')
        }
    
    def _normalize_image_url(self, img_url: Optional[str], base_url: str) -> Optional[str]:
        """Normalize and validate image URLs"""
        if not img_url:
            return None
        candidate = img_url.strip()
        if not candidate:
            return None
        from urllib.parse import urljoin
        resolved = candidate if candidate.startswith('http') else urljoin(base_url, candidate)
        if '?' in resolved:
            resolved = resolved.split('?')[0]
        lower_resolved = resolved.lower()
        if 'transparent' in lower_resolved or 'placeholder' in lower_resolved:
            return None
        if (
            any(ext in lower_resolved for ext in ['.jpg', '.jpeg', '.png', '.webp'])
            or 'static.zara.net' in lower_resolved
        ):
            return resolved
        return None
    
    def _extract_from_scripts(self, soup: BeautifulSoup) -> Optional[Dict]:
        """Extract product data from script tags (Zara often embeds data here)"""
        try:
            scripts = soup.find_all('script')
            logger.info(f"ZaraExtractor._extract_from_scripts: Found {len(scripts)} script tags")
            
            for script in scripts:
                if not script.string:
                    continue
                
                # Look for product data patterns
                script_text = script.string
                
                # Pattern 0: Look for image URLs directly in script (common in modern sites)
                # Zara might have image URLs in variables like: var images = ["url1", "url2"]
                image_url_patterns = [
                    r'["\'](https?://[^"\']*static\.zara\.net[^"\']*\.(jpg|jpeg|png|webp)[^"\']*)["\']',
                    r'image["\']?\s*[:=]\s*["\'](https?://[^"\']*\.(jpg|jpeg|png|webp)[^"\']*)["\']',
                    r'images["\']?\s*[:=]\s*\[([^\]]+)\]',
                ]
                
                for pattern in image_url_patterns:
                    matches = re.findall(pattern, script_text, re.IGNORECASE)
                    if matches:
                        logger.info(f"ZaraExtractor._extract_from_scripts: Found image URLs in script using pattern")
                        images = []
                        for match in matches:
                            if isinstance(match, tuple):
                                url = match[0] if match[0].startswith('http') else match[1] if len(match) > 1 else None
                            else:
                                url = match
                            if url and url.startswith('http'):
                                images.append(url)
                        if images:
                            return {
                                'title': None,
                                'price': None,
                                'images': images[:20],
                                'sizes': [],
                                'colors': [],
                                'brand': 'Zara',
                                'description': None
                            }
                
                # Pattern 1: Look for window.__INITIAL_STATE__ or similar
                if '__INITIAL_STATE__' in script_text or 'productData' in script_text or 'product' in script_text.lower():
                    logger.info(f"ZaraExtractor._extract_from_scripts: Found potential product data in script")
                    # Try to extract JSON object
                    json_match = re.search(r'\{[^{}]*"product"[^{}]*\}', script_text, re.DOTALL)
                    if json_match:
                        try:
                            data = json.loads(json_match.group())
                            if 'product' in data or 'images' in data:
                                return self._parse_script_data(data)
                        except json.JSONDecodeError:
                            pass
                
                # Pattern 2: Look for image URLs in script tags (including static.zara.net)
                image_urls = re.findall(r'https?://[^"\')\s]+\.(?:jpg|jpeg|png|webp)', script_text, re.I)
                if image_urls:
                    # Filter for Zara product images (static.zara.net or zara.com)
                    zara_images = [img for img in image_urls 
                                 if ('static.zara.net' in img.lower() or 'zara' in img.lower()) 
                                 and ('product' in img.lower() or 'item' in img.lower() or 'garment' in img.lower())]
                    if zara_images:
                        return {
                            'title': None,
                            'price': None,
                            'images': list(set(zara_images))[:20],
                            'sizes': [],
                            'colors': [],
                            'brand': 'Zara',
                            'description': None
                        }
        except Exception as e:
            logger.warning(f"ZaraExtractor._extract_from_scripts: Error: {str(e)}")
        return None
    
    def _parse_script_data(self, data: Dict) -> Dict:
        """Parse product data from script tag"""
        images = []
        if 'images' in data:
            images = data['images'] if isinstance(data['images'], list) else [data['images']]
        elif 'product' in data and isinstance(data['product'], dict):
            product = data['product']
            if 'images' in product:
                images = product['images'] if isinstance(product['images'], list) else [product['images']]
        
        return {
            'title': data.get('name') or data.get('title') or (data.get('product', {}).get('name') if isinstance(data.get('product'), dict) else None),
            'price': data.get('price') or (data.get('product', {}).get('price') if isinstance(data.get('product'), dict) else None),
            'images': images[:20],
            'sizes': data.get('sizes', []),
            'colors': data.get('colors', []),
            'brand': 'Zara',
            'description': data.get('description', '')
        }
    
    def _extract_with_scrapy(self, selector: Selector, soup: BeautifulSoup, html_content: str, url: str) -> Dict:
        """Extract product info using Scrapy selectors (more powerful than BeautifulSoup)"""
        logger.info(f"ZaraExtractor._extract_with_scrapy: ENTRY")
        from urllib.parse import urljoin
        
        # Use Scrapy selectors for more robust extraction
        # Extract title using Scrapy CSS/XPath selectors
        title = None
        title_selectors = [
            'h1.product-detail-info__header-name::text',
            'h1[data-testid="product-name"]::text',
            'h1.product-name::text',
            'h1::text',
            '//h1[@itemprop="name"]/text()',
            '//h1/text()',
        ]
        for sel in title_selectors:
            try:
                if sel.startswith('//'):
                    result = selector.xpath(sel).get()
                else:
                    result = selector.css(sel).get()
                if result:
                    title = result.strip()
                    break
            except:
                continue
        
        if not title:
            # Fallback to BeautifulSoup
            title_elem = soup.find('h1')
            if title_elem:
                title = title_elem.get_text().strip()
        
        # Extract price using Scrapy selectors
        price = None
        price_selectors = [
            '.price::text',
            '.money::text',
            '[data-testid="price"]::text',
            '[itemprop="price"]::text',
            '//span[@itemprop="price"]/text()',
        ]
        for sel in price_selectors:
            try:
                if sel.startswith('//'):
                    result = selector.xpath(sel).get()
                else:
                    result = selector.css(sel).get()
                if result:
                    price = result.strip()
                    break
            except:
                continue
        
        # Extract images using Scrapy selectors (more powerful)
        images = []
        
        # Strategy 0: OpenGraph meta tag
        og_image = selector.css('meta[property="og:image"]::attr(content)').get()
        if og_image:
            if not og_image.startswith('http'):
                og_image = urljoin(url, og_image)
            if any(ext in og_image.lower() for ext in ['.jpg', '.jpeg', '.png', '.webp']) or 'static.zara.net' in og_image.lower():
                images.append(og_image)
                logger.info(f"ZaraExtractor: Found OpenGraph image via Scrapy: {og_image[:100]}")
        
        def _add_image_candidate(candidate: Optional[str]):
            normalized = self._normalize_image_url(candidate, url)
            if normalized and normalized not in images:
                images.append(normalized)

        # Strategy 1: Product image containers using Scrapy
        img_containers = selector.css('.product-detail-images img, .media img, .gallery img, .carousel img')
        for img in img_containers:
            img_url = img.css('::attr(src)').get() or img.css('::attr(data-src)').get() or img.css('::attr(data-lazy-src)').get()
            if img_url and any(keyword in img_url.lower() for keyword in ['product', 'item', 'garment', 'zara', 'static.zara.net']):
                _add_image_candidate(img_url)
        
        # Strategy 2: Picture/source tags with Scrapy
        picture_sources = selector.css('picture source::attr(srcset)').getall()
        for srcset in picture_sources:
            urls = re.findall(r'(https?://[^\s,]+)', srcset)
            for img_url in urls:
                if any(keyword in img_url.lower() for keyword in ['product', 'item', 'garment', 'zara', 'static.zara.net']):
                    _add_image_candidate(img_url)
        
        # Strategy 3: All images with static.zara.net pattern
        all_zara_images = selector.css('img[src*="static.zara.net"]::attr(src)').getall()
        for img_url in all_zara_images:
            _add_image_candidate(img_url)

        # Fallback collector if fewer than 3 images found
        if len(images) < 3:
            logger.info("ZaraExtractor: Fewer than 3 images found, running fallback collector for hi-res sources")
            for img in soup.find_all('img'):
                candidates: List[str] = []
                for attr in ['data-zoom-image', 'data-main-image', 'data-src', 'data-hires', 'src']:
                    val = img.get(attr)
                    if val:
                        candidates.append(val)
                srcset = img.get('srcset')
                if srcset:
                    for part in srcset.split(','):
                        url_part = part.strip().split(' ')[0]
                        if url_part:
                            candidates.append(url_part)
                for candidate in candidates:
                    _add_image_candidate(candidate)
                    if len(images) >= 6:
                        break
                if len(images) >= 6:
                    break
        
        # Extract sizes using Scrapy
        sizes = []
        size_elements = selector.css('.size::text, .option::text, [class*="size"]::text').getall()
        for size_text in size_elements:
            size_text = size_text.strip() if size_text else ''
            if re.match(r'^(XS|S|M|L|XL|XXL|\d+)$', size_text, re.I):
                if size_text.upper() not in [s.upper() for s in sizes]:
                    sizes.append(size_text)
        
        # Extract colors using Scrapy
        colors = []
        color_elements = selector.css('.color::text, .swatch::text, [class*="color"]::text').getall()
        for color_text in color_elements:
            color_text = color_text.strip() if color_text else ''
            if color_text and len(color_text) < 50 and color_text.lower() not in ['select', 'choose', 'color']:
                if color_text not in colors:
                    colors.append(color_text)
        
        # Extract description using Scrapy
        description = None
        desc_selectors = [
            '.product-description::text',
            '[itemprop="description"]::text',
            '.product-detail-info__description::text',
        ]
        for sel in desc_selectors:
            try:
                desc = selector.css(sel).get()
                if desc:
                    description = desc.strip()
                    break
            except:
                continue
        
        result = {
            'title': title,
            'price': price,
            'images': images[:20],  # Limit to 20 images
            'sizes': sizes[:10],
            'colors': colors[:10],
            'brand': 'Zara',
            'description': description
        }
        
        logger.info(f"ZaraExtractor._extract_with_scrapy: EXIT - Found {len(images)} images, title={title[:50] if title else 'None'}")
        return result
    
    def _extract_from_html(self, soup: BeautifulSoup, html_content: str, url: str) -> Dict:
        """Fallback HTML extraction method"""
        from urllib.parse import urljoin
        from features.garments.scraper import extract_title_from_html, extract_images_from_html
        
        # Extract title
        title = None
        title_elem = soup.find('h1', class_=re.compile('product-detail-info|product-name', re.I)) or \
                    soup.find('h1', {'data-testid': 'product-name'}) or \
                    soup.find('h1', {'itemprop': 'name'}) or \
                    soup.find('h1')
        if title_elem:
            title = title_elem.get_text().strip()
        if not title:
            title = extract_title_from_html(html_content)
        
        # Extract price
        price = None
        price_elem = soup.find(class_=re.compile('price|money', re.I)) or \
                    soup.find('span', {'data-testid': 'price'}) or \
                    soup.find('span', {'itemprop': 'price'})
        if price_elem:
            price = price_elem.get_text().strip()
        
        # Extract images - multiple strategies
        images = []
        
        # Strategy 0: OpenGraph meta tags (most reliable for main image)
        og_img = soup.find('meta', property='og:image')
        if og_img and og_img.get('content'):
            og_img_url = og_img['content']
            if not og_img_url.startswith('http'):
                og_img_url = urljoin(url, og_img_url)
            # Check if it's a valid image URL (static.zara.net or similar)
            if any(ext in og_img_url.lower() for ext in ['.jpg', '.jpeg', '.png', '.webp']) or 'static.zara.net' in og_img_url.lower():
                images.append(og_img_url)
                logger.info(f"ZaraExtractor: Found OpenGraph image: {og_img_url[:100]}")
        
        # Strategy 1: Look for Zara-specific image containers
        img_containers = soup.find_all(['div', 'section'], class_=re.compile('product-detail-images|media|gallery|carousel', re.I))
        for container in img_containers:
            imgs = container.find_all('img')
            for img in imgs:
                img_url = img.get('src') or img.get('data-src') or img.get('data-lazy-src') or img.get('data-original')
                if img_url:
                    # Check if it's a valid image URL (has image extension or is from static.zara.net)
                    is_image = any(ext in img_url.lower().split('?')[0] for ext in ['.jpg', '.jpeg', '.png', '.webp']) or 'static.zara.net' in img_url.lower()
                    # Filter for product images (exclude logos, icons)
                    is_product = any(keyword in img_url.lower() for keyword in ['product', 'item', 'garment', 'zara', 'static.zara.net'])
                    if is_image and is_product:
                        if not img_url.startswith('http'):
                            img_url = urljoin(url, img_url)
                        # Remove query params that might limit image size
                        if '?' in img_url:
                            base_img_url = img_url.split('?')[0]
                            # Try to get higher resolution version
                            if 'thumbnail' in img_url.lower() or 'small' in img_url.lower():
                                img_url = base_img_url.replace('thumbnail', 'large').replace('small', 'large')
                            else:
                                img_url = base_img_url
                        if img_url not in images:
                            images.append(img_url)
        
        # Strategy 2: Look for picture/source tags (modern responsive images)
        picture_tags = soup.find_all('picture')
        for picture in picture_tags:
            sources = picture.find_all('source')
            for source in sources:
                srcset = source.get('srcset', '')
                if srcset:
                    # Extract first URL from srcset
                    urls = re.findall(r'(https?://[^\s,]+)', srcset)
                    for img_url in urls:
                        if any(keyword in img_url.lower() for keyword in ['product', 'item', 'garment', 'zara']):
                            if img_url not in images:
                                images.append(img_url)
        
        # Strategy 3: Generic image extraction with filtering (including static.zara.net)
        if not images:
            generic_images = extract_images_from_html(html_content, url, max_images=50)
            # Filter for product-related images (including static.zara.net)
            images = [img for img in generic_images 
                     if (any(keyword in img.lower() for keyword in ['product', 'item', 'garment', 'zara', 'static.zara.net'])
                         or any(ext in img.lower().split('?')[0] for ext in ['.jpg', '.jpeg', '.png', '.webp']))
                     and not any(exclude in img.lower() for exclude in ['logo', 'icon', 'banner', 'header', 'footer'])]
        
        # Extract sizes
        sizes = []
        size_elements = soup.find_all(['button', 'span', 'div'], class_=re.compile('size|option', re.I))
        for elem in size_elements:
            size_text = elem.get_text().strip()
            # Common size patterns
            if re.match(r'^(XS|S|M|L|XL|XXL|\d+)$', size_text, re.I):
                if size_text.upper() not in [s.upper() for s in sizes]:
                    sizes.append(size_text)
        
        # Extract colors
        colors = []
        color_elements = soup.find_all(['button', 'span', 'div'], class_=re.compile('color|swatch', re.I))
        for elem in color_elements:
            color_text = elem.get_text().strip()
            if color_text and len(color_text) < 50 and color_text.lower() not in ['select', 'choose', 'color']:
                if color_text not in colors:
                    colors.append(color_text)
        
        result = {
            'title': title,
            'price': price,
            'images': images[:20],  # Limit to 20 images
            'sizes': sizes[:10],
            'colors': colors[:10],
            'brand': 'Zara',
            'description': None
        }
        
        logger.info(f"ZaraExtractor._extract_from_html: EXIT - Found {len(images)} images")
        
        # Debug: Log HTML structure if no images found
        if len(images) == 0:
            logger.warning("ZaraExtractor._extract_from_html: No images found. Debugging HTML structure...")
            # Check for common Zara image patterns
            all_imgs = soup.find_all('img')
            logger.info(f"ZaraExtractor._extract_from_html: Found {len(all_imgs)} total <img> tags in HTML")
            if len(all_imgs) > 0:
                # Log first few img tags for debugging
                for i, img in enumerate(all_imgs[:5]):
                    src = img.get('src') or img.get('data-src') or img.get('data-lazy-src')
                    logger.debug(f"ZaraExtractor._extract_from_html: img[{i}]: src={src[:100] if src else 'None'}, classes={img.get('class', [])}")
            
            # Check for picture tags
            pictures = soup.find_all('picture')
            logger.info(f"ZaraExtractor._extract_from_html: Found {len(pictures)} <picture> tags")
            
            # Check for OpenGraph image
            og_image = soup.find('meta', property='og:image')
            if og_image:
                og_url = og_image.get('content', '')
                logger.info(f"ZaraExtractor._extract_from_html: Found og:image: {og_url[:100]}")
                if og_url and og_url not in images:
                    images.append(og_url)
                    logger.info(f"ZaraExtractor._extract_from_html: Added og:image to images list")
        
        return result


class BrandExtractorFactory:
    """Factory for creating brand-specific extractors"""
    
    _extractors: List[BrandExtractor] = []
    _default_extractor: BrandExtractor = None
    
    @classmethod
    def register_extractor(cls, extractor: BrandExtractor):
        """Register a brand extractor"""
        logger.info(f"BrandExtractorFactory.register_extractor: ENTRY - {extractor.__class__.__name__}")
        cls._extractors.append(extractor)
    
    @classmethod
    def get_extractor(cls, url: str) -> BrandExtractor:
        """
        Get appropriate extractor for URL
        Returns brand-specific extractor if available, otherwise default
        """
        logger.info(f"BrandExtractorFactory.get_extractor: ENTRY - url={url[:100]}")
        
        # Try brand-specific extractors first
        for extractor in cls._extractors:
            if extractor.can_extract(url):
                logger.info(f"BrandExtractorFactory.get_extractor: Using {extractor.__class__.__name__}")
                return extractor
        
        # Fallback to default
        if not cls._default_extractor:
            cls._default_extractor = DefaultExtractor()
        logger.info(f"BrandExtractorFactory.get_extractor: Using DefaultExtractor")
        return cls._default_extractor


# Initialize factory with registered extractors
BrandExtractorFactory.register_extractor(ZaraExtractor())

