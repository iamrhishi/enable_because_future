"""
Centralized web scraping utilities
Eliminates code duplication across the codebase
Uses rotating user agents and optional proxy support to avoid bot detection
"""

import requests  # type: ignore
from bs4 import BeautifulSoup  # type: ignore
from urllib.parse import urljoin
from typing import Optional, List
from shared.logger import logger
from features.garments.scraping_constants import get_default_headers, get_proxy_config, get_proxy_auth


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
                logger.exception(f"fetch_html: EXIT - Retry also failed: {str(retry_error)}")
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
        
        for img in img_tags[:max_images]:
            img_url = img.get('src') or img.get('data-src') or img.get('data-lazy-src')
            if img_url:
                if not img_url.startswith('http'):
                    img_url = urljoin(base_url, img_url)
                if img_url not in images:
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

