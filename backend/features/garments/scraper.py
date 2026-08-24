"""
Centralized web scraping utilities
Eliminates code duplication across the codebase
Uses rotating user agents and optional proxy support to avoid bot detection
"""

import re
import requests  # type: ignore
from bs4 import BeautifulSoup  # type: ignore
from urllib.parse import urljoin
from typing import Optional, List
from shared.logger import logger
from features.garments.scraping_constants import get_default_headers, get_proxy_config, get_proxy_auth

# Matches site-chrome assets (nav/header logos, flag icons, promo banners) that
# turn up interspersed with real product photos when just grabbing the page's
# first N <img> tags in DOM order - confirmed via a real production trace on a
# SuitSupply product page, where the first 16 <img> tags were exclusively a
# country-flag icon, 2 logo variants, and 13 nav-menu collection/occasion
# banners, with the actual product photo only appearing at position 17 of 21.
_NON_PRODUCT_IMAGE_PATTERN = re.compile(
    r'(logo|favicon|sprite|/flags?/|nav-menu|nav_|/icons?/|icon[-_]|placeholder|spinner|/badges?/)',
    re.I
)


def _looks_like_product_image(url: str) -> bool:
    if url.lower().endswith('.svg'):
        return False
    return not _NON_PRODUCT_IMAGE_PATTERN.search(url)


def unwrap_redirect_url(url: str) -> str:
    """
    Unwraps Google Vertex AI grounding redirect links (vertexaisearch.cloud.google.com/grounding-api-redirect/...)
    to return the actual target e-commerce store URL.
    """
    if not url or not isinstance(url, str):
        return url
    if 'grounding-api-redirect' in url or 'vertexaisearch' in url or 'google.com/url' in url:
        try:
            headers = get_default_headers()
            # 1. Fast check: HTTP 301/302/307 Location header
            resp = requests.head(url, headers=headers, allow_redirects=False, timeout=3)
            if resp.status_code in [301, 302, 303, 307, 308] and resp.headers.get('Location'):
                location = resp.headers.get('Location')
                if location and 'vertexaisearch' not in location:
                    logger.info(f"unwrap_redirect_url: Fast unwrapped Location header to {location}")
                    return location
            
            # 2. Fallback: Follow redirects with GET request
            resp = requests.get(url, headers=headers, allow_redirects=True, timeout=3, stream=True)
            if resp and resp.url and 'vertexaisearch' not in resp.url:
                logger.info(f"unwrap_redirect_url: Unwrapped redirect URL to {resp.url}")
                return resp.url
        except Exception as e:
            logger.warning(f"unwrap_redirect_url failed: {str(e)}")
    return url


def fetch_html(url: str, timeout: int = 10, retry_with_different_ua: bool = True, follow_bot_redirects: bool = True) -> Optional[str]:
    """
    Fetch HTML content from URL with rotating user agents and optional proxy support.
    Attempts to follow bot detection redirects (e.g., Zara's bm-verify).
    
    Args:
        url: URL to fetch
        timeout: Request timeout in seconds
        retry_with_different_ua: If True and first attempt fails, retry with different user agent
        follow_bot_redirects: If True, attempt to follow bot detection redirects (meta refresh with bm-verify)
        
    Returns:
        HTML content as string, or None if failed
    """
    url = unwrap_redirect_url(url)
    logger.info(f"fetch_html: ENTRY - url={url[:100]}")
    
    headers = get_default_headers()
    proxies = get_proxy_config()
    auth = get_proxy_auth()
    
    try:
        response = requests.get(
            url, 
            headers=headers, 
            timeout=timeout,
            proxies=proxies,
            auth=auth,
            allow_redirects=True
        )
        response.raise_for_status()
        html_content = response.text
        html_size = len(html_content)
        logger.info(f"fetch_html: EXIT - Success, size={html_size} chars, user_agent={headers['User-Agent'][:50]}")
        
        # Check if this is a bot detection page (Zara uses meta refresh with bm-verify)
        if html_size < 5000 and follow_bot_redirects:
            import re
            from urllib.parse import urljoin
            
            # Look for meta refresh with bm-verify parameter
            meta_refresh_match = re.search(r'<meta\s+http-equiv=["\']refresh["\']\s+content=["\']\d+;\s*URL=["\']([^"\']+)["\']', html_content, re.IGNORECASE)
            if meta_refresh_match:
                redirect_url = meta_refresh_match.group(1)
                # Check if it contains bm-verify (bot mitigation)
                if 'bm-verify' in redirect_url:
                    logger.info(f"fetch_html: Detected bot mitigation redirect, attempting to follow: {redirect_url[:100]}")
                    # Make redirect URL absolute if needed
                    if not redirect_url.startswith('http'):
                        redirect_url = urljoin(url, redirect_url)
                    
                    # Wait a bit (as the meta refresh suggests) and follow the redirect
                    import time
                    time.sleep(2)  # Wait 2 seconds (less than the 5 second meta refresh)
                    
                    # Follow the redirect with cookies from first request
                    redirect_response = requests.get(
                        redirect_url,
                        headers=headers,
                        cookies=response.cookies,
                        timeout=timeout,
                        proxies=proxies,
                        auth=auth,
                        allow_redirects=True
                    )
                    redirect_response.raise_for_status()
                    redirect_html = redirect_response.text
                    redirect_size = len(redirect_html)
                    logger.info(f"fetch_html: Followed bot mitigation redirect, new size={redirect_size} chars")
                    
                    if redirect_size > html_size:  # Only use if we got more content
                        return redirect_html
                    else:
                        logger.warning(f"fetch_html: Redirect didn't provide more content ({redirect_size} vs {html_size} chars)")
        
        # Log warning if HTML is suspiciously small (likely bot detection)
        if html_size < 5000:
            logger.warning(f"fetch_html: HTML response is very small ({html_size} chars). This might be a bot detection page. URL: {url[:100]}")
            # Log first 200 chars to help debug
            logger.debug(f"fetch_html: First 200 chars of response: {html_content[:200]}")
        
        return html_content
    except Exception as e:
        logger.warning(f"fetch_html: First attempt failed: {str(e)}")
        
        # Retry with different user agent if enabled
        if retry_with_different_ua:
            try:
                logger.info("fetch_html: Retrying with different user agent")
                headers = get_default_headers()  # Get a different random user agent
                response = requests.get(
                    url,
                    headers=headers,
                    timeout=timeout,
                    proxies=proxies,
                    auth=auth,
                    allow_redirects=True
                )
                response.raise_for_status()
                logger.info(f"fetch_html: EXIT - Success on retry, size={len(response.text)} chars")
                return response.text
            except Exception as retry_error:
                logger.warning(f"fetch_html: Retry also failed: {str(retry_error)}")
                
                # Try Scrape.do as a last resort fallback
                from config import Config
                if getattr(Config, 'SCRAPE_DO_ENABLED', False) and getattr(Config, 'SCRAPE_DO_API_KEY', None):
                    logger.info("fetch_html: Retrying with Scrape.do API as last resort")
                    try:
                        import urllib.parse
                        scrape_do_url = (
                            f"http://api.scrape.do/"
                            f"?url={urllib.parse.quote(url, safe='')}"
                            f"&token={Config.SCRAPE_DO_API_KEY}"
                            f"&render=true"
                            f"&super=true"
                        )
                        scrape_do_resp = requests.get(scrape_do_url, timeout=60)
                        scrape_do_resp.raise_for_status()
                        logger.info(f"fetch_html: EXIT - Success with Scrape.do, size={len(scrape_do_resp.text)} chars")
                        return scrape_do_resp.text
                    except Exception as scrape_do_err:
                        logger.exception(f"fetch_html: EXIT - Scrape.do also failed: {str(scrape_do_err)}")
                        return None
                else:
                    logger.exception(f"fetch_html: EXIT - Error: {str(retry_error)}")
                    return None
        else:
            logger.exception(f"fetch_html: EXIT - Error: {str(e)}")
            return None


def extract_images_from_html(html_content: str, base_url: str, max_images: int = 20) -> List[str]:
    """
    Extract image URLs from HTML content
    
    Args:
        html_content: HTML content to parse
        base_url: Base URL for resolving relative URLs
        max_images: Maximum number of images to extract
        
    Returns:
        List of absolute image URLs
    """
    logger.info(f"extract_images_from_html: ENTRY - max_images={max_images}")
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        images = []
        img_tags = soup.find_all('img', src=True)

        # Scan further than max_images in DOM order (bounded) rather than slicing
        # to max_images up front - a page's first N <img> tags are frequently all
        # header/nav/logo assets, which _looks_like_product_image filters out, so
        # slicing before filtering could return zero real product photos even
        # when plenty exist further down the page.
        scan_limit = max(max_images * 4, 40)
        for img in img_tags[:scan_limit]:
            if len(images) >= max_images:
                break
            img_url = img.get('src') or img.get('data-src') or img.get('data-lazy-src')
            if img_url:
                if not img_url.startswith('http'):
                    img_url = urljoin(base_url, img_url)
                if img_url not in images and _looks_like_product_image(img_url):
                    images.append(img_url)

        logger.info(f"extract_images_from_html: EXIT - Found {len(images)} images")
        return images
    except Exception as e:
        logger.exception(f"extract_images_from_html: EXIT - Error: {str(e)}")
        return []


def extract_title_from_html(html_content: str) -> Optional[str]:
    """
    Extract title from HTML content
    
    Args:
        html_content: HTML content to parse
        
    Returns:
        Title string or None
    """
    logger.info("extract_title_from_html: ENTRY")
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        title_elem = soup.find('h1') or soup.find('title')
        if title_elem:
            title = title_elem.get_text().strip()
            logger.info(f"extract_title_from_html: EXIT - Found title: {title[:50]}")
            return title
        logger.info("extract_title_from_html: EXIT - No title found")
        return None
    except Exception as e:
        logger.exception(f"extract_title_from_html: EXIT - Error: {str(e)}")
        return None


def is_image_url(url: str) -> bool:
    """
    Check if URL is a direct image URL
    
    Args:
        url: URL to check
        
    Returns:
        True if URL appears to be a direct image
    """
    image_extensions = ['.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp']
    return any(url.lower().endswith(ext) for ext in image_extensions)

