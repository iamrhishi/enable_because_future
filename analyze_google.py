#!/usr/bin/env python3

import requests
from bs4 import BeautifulSoup
import urllib.parse
import json

def analyze_google_images(query):
    """Analyze Google Images HTML structure to understand how to extract images"""
    print(f"🔍 Analyzing Google Images for: '{query}'")
    print("=" * 60)
    
    try:
        search_query = urllib.parse.quote_plus(f"{query} clothing fashion")
        search_url = f"https://www.google.com/search?q={search_query}&tbm=isch"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        
        response = requests.get(search_url, headers=headers, timeout=15)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        print(f"📄 Response size: {len(response.content)} bytes")
        print(f"📄 Total HTML elements: {len(soup.find_all())}")
        
        # Look for JavaScript data that contains image URLs
        print(f"\n🔍 Looking for JavaScript data containing image URLs...")
        scripts = soup.find_all('script')
        print(f"   Found {len(scripts)} script tags")
        
        image_urls = []
        
        for i, script in enumerate(scripts):
            if script.string:
                script_content = script.string
                # Look for common patterns in Google Images JS
                if 'https://' in script_content and ('jpg' in script_content or 'png' in script_content or 'jpeg' in script_content):
                    print(f"   Script {i+1} contains image URLs")
                    # Try to extract URLs from the script
                    import re
                    urls = re.findall(r'https://[^\s"\']+\.(?:jpg|jpeg|png|webp)', script_content)
                    image_urls.extend(urls)
        
        # Remove duplicates and filter
        unique_urls = list(set(image_urls))
        filtered_urls = [url for url in unique_urls if 'google' not in url and len(url) > 20]
        
        print(f"\n📊 JavaScript URL extraction results:")
        print(f"   Total URLs found in scripts: {len(image_urls)}")
        print(f"   Unique URLs: {len(unique_urls)}")
        print(f"   Filtered URLs (no Google, length > 20): {len(filtered_urls)}")
        
        if filtered_urls:
            print(f"\n📸 Sample extracted URLs:")
            for i, url in enumerate(filtered_urls[:5]):
                print(f"   {i+1}. {url}")
        
        # Also try different CSS selectors
        print(f"\n🔍 Trying alternative CSS selectors...")
        
        selectors_to_try = [
            'div[jsname] img',
            'div[data-ri] img', 
            '.rg_i img',
            'img[data-src]',
            'img[jsname]',
            '[role="img"]',
            'div[data-ved] img[alt*="dress"]',
            'img[alt]:not([alt=""])',  # Images with non-empty alt text
        ]
        
        for selector in selectors_to_try:
            elements = soup.select(selector)
            print(f"   '{selector}': {len(elements)} elements")
            
            if elements and len(elements) > 0:
                print(f"     First element sample:")
                first = elements[0]
                print(f"       Tag: {first.name}")
                print(f"       Attributes: {dict(list(first.attrs.items())[:5])}...")
                print(f"       Alt text: {first.get('alt', 'None')[:50]}...")
                
        # Try to find divs that might contain image metadata
        print(f"\n🔍 Looking for divs with image metadata...")
        meta_divs = soup.find_all('div', {'data-ri': True})
        print(f"   Found {len(meta_divs)} divs with data-ri attribute")
        
        if meta_divs:
            print(f"   First meta div:")
            first_meta = meta_divs[0]
            print(f"     data-ri: {first_meta.get('data-ri', 'None')}")
            print(f"     Other attributes: {dict(list(first_meta.attrs.items())[:3])}...")
            
            # Look for nested image tags
            nested_imgs = first_meta.find_all('img')
            print(f"     Nested images: {len(nested_imgs)}")
            
            if nested_imgs:
                print(f"     First nested image:")
                print(f"       Attributes: {nested_imgs[0].attrs}")
        
        return filtered_urls
        
    except Exception as e:
        print(f"❌ Analysis error: {e}")
        import traceback
        traceback.print_exc()
        return []

if __name__ == "__main__":
    # Analyze Google Images structure
    urls = analyze_google_images("black dress")
    
    print(f"\n🎯 Analysis Complete:")
    print(f"   Extracted {len(urls)} potential image URLs from JavaScript")
    
    if urls:
        print(f"\n✅ SUCCESS: Found image URLs in JavaScript data")
        print(f"   This suggests we should parse JavaScript instead of HTML img tags")
    else:
        print(f"\n❌ No URLs found - Google Images is heavily JavaScript-dependent")