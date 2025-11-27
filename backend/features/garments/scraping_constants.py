"""
Scraping constants for web extraction
Includes user agents, headers, and proxy configuration
"""

import random
import os
from typing import List, Dict, Optional

# Multiple realistic user agents to rotate through
# Helps avoid bot detection by appearing as different browsers/devices
USER_AGENTS: List[str] = [
    # Chrome on Windows
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
    
    # Chrome on macOS
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
    
    # Firefox on Windows
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0',
    
    # Firefox on macOS
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:121.0) Gecko/20100101 Firefox/121.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:120.0) Gecko/20100101 Firefox/120.0',
    
    # Safari on macOS
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15',
    
    # Edge on Windows
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36 Edg/119.0.0.0',
    
    # Chrome on Linux
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    
    # Mobile - Chrome on Android
    'Mozilla/5.0 (Linux; Android 13; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36',
    'Mozilla/5.0 (Linux; Android 12; Pixel 6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36',
    
    # Mobile - Safari on iOS
    'Mozilla/5.0 (iPhone; CPU iPhone OS 17_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Mobile/15E148 Safari/604.1',
    'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1',
]


def get_random_user_agent() -> str:
    """
    Get a random user agent from the list
    
    Returns:
        Random user agent string
    """
    return random.choice(USER_AGENTS)


def get_default_headers(user_agent: Optional[str] = None) -> Dict[str, str]:
    """
    Get default headers for web requests
    
    Args:
        user_agent: Optional specific user agent. If None, uses random one.
        
    Returns:
        Dictionary of HTTP headers
    """
    if user_agent is None:
        user_agent = get_random_user_agent()
    
    return {
        'User-Agent': user_agent,
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Sec-Fetch-User': '?1',
        'Cache-Control': 'max-age=0',
    }


# Proxy configuration
# Can be configured via environment variables (see config.py)
def _load_proxy_config() -> Dict:
    """Load proxy configuration from environment variables"""
    enabled = os.environ.get('ENABLE_PROXY', 'False').lower() == 'true'
    http_proxy = os.environ.get('HTTP_PROXY', '') or None
    https_proxy = os.environ.get('HTTPS_PROXY', '') or None
    
    proxy_auth = None
    proxy_username = os.environ.get('PROXY_USERNAME', '')
    proxy_password = os.environ.get('PROXY_PASSWORD', '')
    if proxy_username and proxy_password:
        try:
            from requests.auth import HTTPProxyAuth  # type: ignore
            proxy_auth = HTTPProxyAuth(proxy_username, proxy_password)
        except ImportError:
            # requests.auth might not be available, skip auth
            pass
    
    # Proxy list for rotation (comma-separated in env)
    proxy_list_str = os.environ.get('PROXY_LIST', '')
    proxy_list = [p.strip() for p in proxy_list_str.split(',') if p.strip()] if proxy_list_str else []
    
    return {
        'enabled': enabled,
        'http_proxy': http_proxy,
        'https_proxy': https_proxy,
        'proxy_auth': proxy_auth,
        'rotate_proxies': len(proxy_list) > 0,
        'proxy_list': proxy_list,
    }

PROXY_CONFIG = _load_proxy_config()


def get_proxy_config() -> Optional[Dict[str, str]]:
    """
    Get proxy configuration for requests
    
    Returns:
        Proxy dictionary for requests library, or None if proxies disabled
    """
    if not PROXY_CONFIG.get('enabled', False):
        return None
    
    proxies = {}
    
    if PROXY_CONFIG.get('http_proxy'):
        proxies['http'] = PROXY_CONFIG['http_proxy']
    
    if PROXY_CONFIG.get('https_proxy'):
        proxies['https'] = PROXY_CONFIG['https_proxy']
    
    # If proxy rotation is enabled and we have a list, pick a random one
    if PROXY_CONFIG.get('rotate_proxies') and PROXY_CONFIG.get('proxy_list'):
        proxy = random.choice(PROXY_CONFIG['proxy_list'])
        proxies['http'] = proxy
        proxies['https'] = proxy
    
    return proxies if proxies else None


def get_proxy_auth() -> Optional[Dict[str, str]]:
    """
    Get proxy authentication if configured
    
    Returns:
        Auth dictionary for requests library, or None
    """
    return PROXY_CONFIG.get('proxy_auth')

