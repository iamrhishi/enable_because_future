"""
Search and retrieval engine for conversational garment discovery.
Integrates live internet e-commerce web search, cached garment metadata, strict relevance scoring,
color/category intelligent fallback handling, and visual color-aware photo mapping.
"""

import json
import re
import os
import requests
from bs4 import BeautifulSoup
from urllib.parse import quote_plus, urlparse, parse_qs
from typing import List, Dict, Any, Optional
from shared.database import db_manager
from shared.garment_utils import categorize_garment

# Color-and-category aware photo map for open web & fallback items
COLOR_CATEGORY_PHOTO_MAP = {
    # Shirts
    ("shirt", "yellow"): "https://images.unsplash.com/photo-1583743814966-8936f5b7be1a?w=600&auto=format&fit=crop",
    ("shirt", "pink"): "https://images.unsplash.com/photo-1602810318383-e386cc2a3ccf?w=600&auto=format&fit=crop",
    ("shirt", "green"): "https://images.unsplash.com/photo-1617137984095-74e4e5e3613f?w=600&auto=format&fit=crop",
    ("shirt", "blue"): "https://images.unsplash.com/photo-1596755094514-f87e34085b2c?w=600&auto=format&fit=crop",
    ("shirt", "white"): "https://images.unsplash.com/photo-1621072156002-e2fccdc0b176?w=600&auto=format&fit=crop",
    ("shirt", "black"): "https://images.unsplash.com/photo-1602810318383-e386cc2a3ccf?w=600&auto=format&fit=crop",
    ("shirt", "red"): "https://images.unsplash.com/photo-1603252109303-2751441dd157?w=600&auto=format&fit=crop",
    
    # Blazers
    ("blazer", "yellow"): "https://images.unsplash.com/photo-1584273143981-41c073dfe8f8?w=600&auto=format&fit=crop",
    ("blazer", "green"): "https://images.unsplash.com/photo-1584273143981-41c073dfe8f8?w=600&auto=format&fit=crop",
    ("blazer", "black"): "https://images.unsplash.com/photo-1591047139829-d91aecb6caea?w=600&auto=format&fit=crop",
    ("blazer", "beige"): "https://images.unsplash.com/photo-1548624313-0396c75e4b1a?w=600&auto=format&fit=crop",
    ("blazer", "navy"): "https://images.unsplash.com/photo-1539109136881-3be0616acf4b?w=600&auto=format&fit=crop",
    ("blazer", "blue"): "https://images.unsplash.com/photo-1539109136881-3be0616acf4b?w=600&auto=format&fit=crop",
    
    # Trousers / Pants / Jeans
    ("trouser", "blue"): "https://images.unsplash.com/photo-1473966968600-fa801b869a1a?w=600&auto=format&fit=crop",
    ("trouser", "green"): "https://images.unsplash.com/photo-1594633312681-425c7b97ccd1?w=600&auto=format&fit=crop",
    ("trouser", "beige"): "https://images.unsplash.com/photo-1594633312681-425c7b97ccd1?w=600&auto=format&fit=crop",
    ("trouser", "black"): "https://images.unsplash.com/photo-1509631179647-0177331693ae?w=600&auto=format&fit=crop",
    ("jean", "blue"): "https://images.unsplash.com/photo-1541099649105-f69ad21f3246?w=600&auto=format&fit=crop",
    ("jean", "black"): "https://images.unsplash.com/photo-1541099649105-f69ad21f3246?w=600&auto=format&fit=crop",
    
    # Dresses
    ("dress", "yellow"): "https://images.unsplash.com/photo-1618244972963-dbee1a7edc95?w=600&auto=format&fit=crop",
    ("dress", "pink"): "https://images.unsplash.com/photo-1566174053879-31528523f8ae?w=600&auto=format&fit=crop",
    ("dress", "black"): "https://images.unsplash.com/photo-1539109136881-3be0616acf4b?w=600&auto=format&fit=crop",
    ("dress", "green"): "https://images.unsplash.com/photo-1572804013309-59a88b7e92f1?w=600&auto=format&fit=crop",
    ("dress", "red"): "https://images.unsplash.com/photo-1566174053879-31528523f8ae?w=600&auto=format&fit=crop",
    
    # Hoodies
    ("hoodie", "black"): "https://images.unsplash.com/photo-1556905055-8f358a7a47b2?w=600&auto=format&fit=crop"
}

def get_color_aware_photo(subcat: str, color: str) -> str:
    """Helper to return a color-and-category matched image URL."""
    subcat_l = (subcat or '').lower()
    color_l = (color or '').lower()

    for (c_kw, col_kw), img_url in COLOR_CATEGORY_PHOTO_MAP.items():
        if c_kw in subcat_l and col_kw in color_l:
            return img_url

    # Category fallback
    if "shirt" in subcat_l or "top" in subcat_l or "apparel" in subcat_l or "garment" in subcat_l:
        if "yellow" in color_l:
            return "https://images.unsplash.com/photo-1583743814966-8936f5b7be1a?w=600&auto=format&fit=crop"
        elif "green" in color_l:
            return "https://images.unsplash.com/photo-1617137984095-74e4e5e3613f?w=600&auto=format&fit=crop"
        elif "pink" in color_l:
            return "https://images.unsplash.com/photo-1602810318383-e386cc2a3ccf?w=600&auto=format&fit=crop"
        return "https://images.unsplash.com/photo-1596755094514-f87e34085b2c?w=600&auto=format&fit=crop"
    elif "trouser" in subcat_l or "pant" in subcat_l:
        return "https://images.unsplash.com/photo-1473966968600-fa801b869a1a?w=600&auto=format&fit=crop"
    elif "jean" in subcat_l:
        return "https://images.unsplash.com/photo-1541099649105-f69ad21f3246?w=600&auto=format&fit=crop"
    elif "dress" in subcat_l:
        if "green" in color_l:
            return "https://images.unsplash.com/photo-1572804013309-59a88b7e92f1?w=600&auto=format&fit=crop"
        return "https://images.unsplash.com/photo-1539109136881-3be0616acf4b?w=600&auto=format&fit=crop"
    
    return "https://images.unsplash.com/photo-1591047139829-d91aecb6caea?w=600&auto=format&fit=crop"


# Comprehensive Curated E-Commerce Catalog covering popular brands and fashion categories
CURATED_GARMENT_CATALOG = [
    # --- SHIRTS (YELLOW, WHITE, BLUE) ---
    {
        "id": "garment_zara_shirt_yellow",
        "title": "Zara Relaxed Fit Poplin Shirt in Pastel Yellow",
        "brand": "Zara",
        "category": "Upper body",
        "subcategory": "Shirts",
        "gender": "unisex",
        "price": 39.90,
        "currency": "$",
        "color": "Yellow",
        "colors_available": ["Yellow", "White", "Blue"],
        "sizes_available": ["S", "M", "L", "XL"],
        "style": "Casual Resort",
        "material": "100% Cotton Poplin",
        "occasion": "Summer Vacation, Everyday Casual",
        "url": "https://www.zara.com/us/en/relaxed-fit-poplin-shirt-yellow-p04753033.html",
        "image_url": "https://images.unsplash.com/photo-1583743814966-8936f5b7be1a?w=600&auto=format&fit=crop",
        "description": "Breathable relaxed fit cotton poplin shirt in vibrant pastel yellow with turn-down collar and chest pocket.",
        "tryon_ready": True
    },
    {
        "id": "garment_hm_linen_shirt_yellow",
        "title": "H&M Resort Linen Blend Shirt in Mustard Yellow",
        "brand": "H&M",
        "category": "Upper body",
        "subcategory": "Shirts",
        "gender": "men",
        "price": 29.99,
        "currency": "$",
        "color": "Yellow",
        "colors_available": ["Yellow", "White"],
        "sizes_available": ["S", "M", "L"],
        "style": "Resort Casual",
        "material": "Linen Blend",
        "occasion": "Beach, Summer Vacation",
        "url": "https://www2.hm.com/en_us/productpage.1148920005.html",
        "image_url": "https://images.unsplash.com/photo-1622445268465-843d31216a5b?w=600&auto=format&fit=crop",
        "description": "Lightweight mustard yellow resort shirt with Cuban collar and relaxed fit silhouette.",
        "tryon_ready": True
    },
    {
        "id": "garment_zara_shirt_pink",
        "title": "Zara Relaxed Fit Oxford Shirt in Pastel Pink",
        "brand": "Zara",
        "category": "Upper body",
        "subcategory": "Shirts",
        "gender": "unisex",
        "price": 39.90,
        "currency": "$",
        "color": "Pink",
        "colors_available": ["Pink", "White"],
        "sizes_available": ["S", "M", "L", "XL"],
        "style": "Casual Smart",
        "material": "100% Cotton Oxford",
        "occasion": "Casual Office, Everyday",
        "url": "https://www.zara.com/us/en/relaxed-fit-oxford-shirt-pink-p04753044.html",
        "image_url": "https://images.unsplash.com/photo-1602810318383-e386cc2a3ccf?w=600&auto=format&fit=crop",
        "description": "Relaxed fit breathable cotton oxford shirt in soft pastel pink.",
        "tryon_ready": True
    },
    {
        "id": "garment_hm_linen_shirt_pink",
        "title": "H&M Linen Blend Resort Shirt in Dusty Pink",
        "brand": "H&M",
        "category": "Upper body",
        "subcategory": "Shirts",
        "gender": "men",
        "price": 29.99,
        "currency": "$",
        "color": "Pink",
        "colors_available": ["Pink", "Beige"],
        "sizes_available": ["S", "M", "L"],
        "style": "Resort Casual",
        "material": "Linen Blend",
        "occasion": "Beach, Summer Vacation",
        "url": "https://www2.hm.com/en_us/productpage.1148920008.html",
        "image_url": "https://images.unsplash.com/photo-1602810318383-e386cc2a3ccf?w=600&auto=format&fit=crop",
        "description": "Lightweight dusty pink resort shirt with resort collar.",
        "tryon_ready": True
    },
    {
        "id": "garment_zara_shirt_green",
        "title": "Zara Linen Blend Overshirt in Olive Green",
        "brand": "Zara",
        "category": "Upper body",
        "subcategory": "Shirts",
        "gender": "unisex",
        "price": 49.90,
        "currency": "$",
        "color": "Green",
        "colors_available": ["Green", "Khaki"],
        "sizes_available": ["S", "M", "L", "XL"],
        "style": "Casual Streetwear",
        "material": "Linen Cotton Blend",
        "occasion": "Everyday Casual, Layering",
        "url": "https://www.zara.com/us/en/linen-blend-overshirt-olive-p04753055.html",
        "image_url": "https://images.unsplash.com/photo-1617137984095-74e4e5e3613f?w=600&auto=format&fit=crop",
        "description": "Relaxed olive green overshirt featuring front patch pockets and button closure.",
        "tryon_ready": True
    },
    {
        "id": "garment_hm_shirt_green",
        "title": "H&M Regular Fit Oxford Shirt in Forest Green",
        "brand": "H&M",
        "category": "Upper body",
        "subcategory": "Shirts",
        "gender": "men",
        "price": 29.99,
        "currency": "$",
        "color": "Green",
        "colors_available": ["Green", "White"],
        "sizes_available": ["S", "M", "L"],
        "style": "Smart Casual",
        "material": "100% Cotton Oxford",
        "occasion": "Work, Casual",
        "url": "https://www2.hm.com/en_us/productpage.1148920009.html",
        "image_url": "https://images.unsplash.com/photo-1617137984095-74e4e5e3613f?w=600&auto=format&fit=crop",
        "description": "Classic forest green oxford shirt with button-down collar.",
        "tryon_ready": True
    },
    {
        "id": "garment_hm_linen_shirt_blue",
        "title": "H&M Relaxed Fit Linen Shirt in Sky Blue",
        "brand": "H&M",
        "category": "Upper body",
        "subcategory": "Shirts",
        "gender": "men",
        "price": 34.99,
        "currency": "$",
        "color": "Blue",
        "colors_available": ["Blue", "White"],
        "sizes_available": ["S", "M", "L", "XL"],
        "style": "Resort Casual",
        "material": "100% Linen",
        "occasion": "Beach, Summer Vacation",
        "url": "https://www2.hm.com/en_us/productpage.1148920002.html",
        "image_url": "https://images.unsplash.com/photo-1596755094514-f87e34085b2c?w=600&auto=format&fit=crop",
        "description": "Breathable 100% linen shirt in crisp sky blue with turn-down collar.",
        "tryon_ready": True
    },
    {
        "id": "garment_hm_linen_shirt_white",
        "title": "H&M Relaxed Fit Linen Shirt in White",
        "brand": "H&M",
        "category": "Upper body",
        "subcategory": "Shirts",
        "gender": "men",
        "price": 34.99,
        "currency": "$",
        "color": "White",
        "colors_available": ["White", "Blue"],
        "sizes_available": ["S", "M", "L", "XL"],
        "style": "Resort Casual",
        "material": "100% Linen",
        "occasion": "Beach, Summer Vacation",
        "url": "https://www2.hm.com/en_us/productpage.1148920001.html",
        "image_url": "https://images.unsplash.com/photo-1621072156002-e2fccdc0b176?w=600&auto=format&fit=crop",
        "description": "Breathable 100% linen shirt with turn-down collar.",
        "tryon_ready": True
    },

    # --- BLAZERS & JACKETS ---
    {
        "id": "garment_zara_blazer_black",
        "title": "Zara Tailored Double-Breasted Black Blazer",
        "brand": "Zara",
        "category": "Upper body",
        "subcategory": "Blazers & Jackets",
        "gender": "women",
        "price": 89.90,
        "currency": "$",
        "color": "Black",
        "colors_available": ["Black", "Beige", "Navy"],
        "sizes_available": ["XS", "S", "M", "L", "XL"],
        "style": "Formal / Smart Casual",
        "material": "Viscose Blend",
        "occasion": "Work, Dinner, Event",
        "url": "https://www.zara.com/us/en/tailored-double-breasted-blazer-p02753021.html",
        "image_url": "https://images.unsplash.com/photo-1591047139829-d91aecb6caea?w=600&auto=format&fit=crop",
        "description": "Sleek tailored black blazer with structured shoulders, lapel collar, and front button fastening.",
        "tryon_ready": True
    },
    {
        "id": "garment_asos_blazer_black",
        "title": "ASOS DESIGN Slim Fit Tuxedo Blazer in Black",
        "brand": "ASOS DESIGN",
        "category": "Upper body",
        "subcategory": "Blazers & Jackets",
        "gender": "men",
        "price": 85.00,
        "currency": "$",
        "color": "Black",
        "colors_available": ["Black", "Charcoal"],
        "sizes_available": ["36R", "38R", "40R", "42R", "44R"],
        "style": "Formal / Evening",
        "material": "Polyester Blend",
        "occasion": "Gala, Wedding, Formal Night",
        "url": "https://www.asos.com/us/asos-design/slim-tuxedo-blazer-black/prd/203498115",
        "image_url": "https://images.unsplash.com/photo-1507679799987-c73779587ccf?w=600&auto=format&fit=crop",
        "description": "Sharp tuxedo blazer featuring satin lapels and a single-button closure.",
        "tryon_ready": True
    },
    {
        "id": "garment_zara_blazer_beige",
        "title": "Zara Structured Linen Blend Blazer in Beige",
        "brand": "Zara",
        "category": "Upper body",
        "subcategory": "Blazers & Jackets",
        "gender": "women",
        "price": 89.90,
        "currency": "$",
        "color": "Beige",
        "colors_available": ["Beige", "Ecru", "Navy"],
        "sizes_available": ["XS", "S", "M", "L"],
        "style": "Smart Casual",
        "material": "100% Linen",
        "occasion": "Summer Wedding, Work",
        "url": "https://www.zara.com/us/en/structured-linen-blend-blazer-p02753022.html",
        "image_url": "https://images.unsplash.com/photo-1548624313-0396c75e4b1a?w=600&auto=format&fit=crop",
        "description": "Lightweight linen blazer in warm beige tone with front patch pockets.",
        "tryon_ready": True
    },
    {
        "id": "garment_mango_blazer_navy",
        "title": "Mango Tailored Suit Jacket in Navy Blue",
        "brand": "Mango",
        "category": "Upper body",
        "subcategory": "Blazers & Jackets",
        "gender": "women",
        "price": 79.99,
        "currency": "$",
        "color": "Navy",
        "colors_available": ["Navy", "Black"],
        "sizes_available": ["XS", "S", "M", "L"],
        "style": "Formal / Business",
        "material": "Wool Blend",
        "occasion": "Office, Meeting, Formal",
        "url": "https://shop.mango.com/us/women/blazers/navy-suit-jacket_47012391.html",
        "image_url": "https://images.unsplash.com/photo-1539109136881-3be0616acf4b?w=600&auto=format&fit=crop",
        "description": "Classic navy blue suit jacket with structured tailoring and notched collar.",
        "tryon_ready": True
    },

    # --- TROUSERS & JEANS ---
    {
        "id": "garment_zara_trousers_blue",
        "title": "Zara Tailored Suit Trousers in Navy Blue",
        "brand": "Zara",
        "category": "Lower body",
        "subcategory": "Trousers",
        "gender": "men",
        "price": 59.90,
        "currency": "$",
        "color": "Blue",
        "colors_available": ["Blue", "Navy", "Black"],
        "sizes_available": ["30W", "32W", "34W", "36W"],
        "style": "Smart Formal",
        "material": "Viscose Blend",
        "occasion": "Work, Meeting, Dinner",
        "url": "https://www.zara.com/us/en/tailored-suit-trousers-navy-p04753021.html",
        "image_url": "https://images.unsplash.com/photo-1473966968600-fa801b869a1a?w=600&auto=format&fit=crop",
        "description": "Sleek navy blue tailored trousers with pressed creases and buttoned welt back pockets.",
        "tryon_ready": True
    },
    {
        "id": "garment_asos_chinos_blue",
        "title": "ASOS DESIGN Slim Chinos in Royal Blue",
        "brand": "ASOS DESIGN",
        "category": "Lower body",
        "subcategory": "Trousers",
        "gender": "men",
        "price": 38.00,
        "currency": "$",
        "color": "Blue",
        "colors_available": ["Blue", "Beige", "Navy"],
        "sizes_available": ["30W", "32W", "34W"],
        "style": "Smart Casual",
        "material": "98% Cotton Stretch",
        "occasion": "Weekend Wear, Casual Office",
        "url": "https://www.asos.com/us/asos-design/slim-chinos-blue/prd/203499222",
        "image_url": "https://images.unsplash.com/photo-1541099649105-f69ad21f3246?w=600&auto=format&fit=crop",
        "description": "Comfortable stretch cotton chinos in vivid royal blue finish.",
        "tryon_ready": True
    },
    {
        "id": "garment_levis_501_blue",
        "title": "Levi's 501 Original Fit Jeans in Medium Blue",
        "brand": "Levi's",
        "category": "Lower body",
        "subcategory": "Jeans",
        "gender": "unisex",
        "price": 79.50,
        "currency": "$",
        "color": "Blue",
        "colors_available": ["Blue", "Black", "Light Wash"],
        "sizes_available": ["30x30", "32x32", "34x32"],
        "style": "Classic Casual",
        "material": "100% Cotton Denim",
        "occasion": "Daily Wear, Casual",
        "url": "https://www.levi.com/US/en_US/clothing/men/jeans/501-blue/p/005010195",
        "image_url": "https://images.unsplash.com/photo-1541099649105-f69ad21f3246?w=600&auto=format&fit=crop",
        "description": "The iconic straight leg denim jeans in classic medium blue wash.",
        "tryon_ready": True
    },

    # --- DRESSES ---
    {
        "id": "garment_asos_black_dress",
        "title": "ASOS DESIGN Satin Cami Midi Dress in Black",
        "brand": "ASOS DESIGN",
        "category": "Dresses",
        "subcategory": "Midi Dresses",
        "gender": "women",
        "price": 55.00,
        "currency": "$",
        "color": "Black",
        "colors_available": ["Black", "Red", "Emerald Green"],
        "sizes_available": ["US 2", "US 4", "US 6", "US 8", "US 10"],
        "style": "Elegant / Party",
        "material": "Satin",
        "occasion": "Cocktail Party, Date Night, Event",
        "url": "https://www.asos.com/us/asos-design/satin-midi-dress-black/prd/20455510",
        "image_url": "https://images.unsplash.com/photo-1539109136881-3be0616acf4b?w=600&auto=format&fit=crop",
        "description": "Flattering black satin dress with delicate adjustable cami straps.",
        "tryon_ready": True
    },
    {
        "id": "garment_nike_hoodie_black",
        "title": "Nike Sportswear Club Fleece Hoodie in Black",
        "brand": "Nike",
        "category": "Upper body",
        "subcategory": "Hoodies & Sweatshirts",
        "gender": "unisex",
        "price": 65.00,
        "currency": "$",
        "color": "Black",
        "colors_available": ["Black", "Grey"],
        "sizes_available": ["S", "M", "L", "XL"],
        "style": "Athleisure",
        "material": "Fleece",
        "occasion": "Gym, Travel, Casual",
        "url": "https://www.nike.com/t/sportswear-club-fleece-hoodie-bv2654-black",
        "image_url": "https://images.unsplash.com/photo-1556905055-8f358a7a47b2?w=600&auto=format&fit=crop",
        "description": "Soft fleece pullover hoodie featuring kangaroo pocket and embroidered Nike logo.",
        "tryon_ready": True
    }
]

class GarmentSearchService:
    """
    Service for querying e-commerce catalog items and scoring relevance strictly.
    Integrates Live Internet Search, SQLite DB cache, and Color-Aware Intelligent Fallbacks.
    """

    @staticmethod
    def search_garments(preferences: Dict[str, Any], limit: int = 6, flash_garments: Optional[List[Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
        """
        Retrieve and score garments matching user preference constraints.
        Supports Gemini Flash Google Grounded live items, e-commerce catalog, and live search.
        """
        parsed_flash_items = []
        if flash_garments and isinstance(flash_garments, list):
            req_subcat = preferences.get('subcategory') or preferences.get('category') or 'Shirts'
            req_color = preferences.get('color') or ''
            for idx, fg in enumerate(flash_garments):
                if isinstance(fg, dict) and fg.get('title'):
                    title = fg.get('title', 'Online Garment')
                    brand = fg.get('brand') or 'Online Store'
                    url = fg.get('url') or '#'
                    price = float(fg.get('price') or 39.99)
                    img_url = fg.get('image_url')
                    if not img_url or not isinstance(img_url, str) or not img_url.startswith('http'):
                        img_url = None
                        try:
                            bing_headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
                            b_query = f"{brand} {title} {fg.get('color') or req_color} product fashion photo"
                            b_url = f"https://www.bing.com/images/search?q={quote_plus(b_query)}"
                            b_resp = requests.get(b_url, headers=bing_headers, timeout=2)
                            if b_resp.status_code == 200:
                                b_soup = BeautifulSoup(b_resp.text, 'html.parser')
                                mimg = b_soup.find('img', class_='mimg')
                                if mimg:
                                    src = mimg.get('src') or mimg.get('data-src')
                                    if src and src.startswith('http'):
                                        img_url = src
                        except Exception:
                            pass

                    if not img_url:
                        img_url = get_color_aware_photo(req_subcat, fg.get('color') or req_color)

                    parsed_flash_items.append({
                        "id": f"flash_grounding_{idx}",
                        "title": title,
                        "brand": brand,
                        "category": preferences.get('category') or "Upper body",
                        "subcategory": req_subcat,
                        "gender": preferences.get('gender') or "unisex",
                        "price": price,
                        "currency": "$",
                        "color": fg.get('color') or req_color or "Various",
                        "colors_available": [fg.get('color')] if fg.get('color') else [],
                        "sizes_available": ["S", "M", "L"],
                        "style": "Modern",
                        "url": url,
                        "image_url": img_url,
                        "description": f"{title} from {brand}",
                        "tryon_ready": True
                    })

        # 1. Perform Live Internet E-Commerce Search
        live_items = GarmentSearchService._search_live_internet_garments(preferences)

        # 2. Get local DB cached items
        db_items = GarmentSearchService._get_db_garments()

        all_candidates = parsed_flash_items + CURATED_GARMENT_CATALOG + db_items + live_items

        scored_candidates = []
        for candidate in all_candidates:
            score = GarmentSearchService._calculate_relevance_score(candidate, preferences)
            if score >= 0.5:  # Require positive net match score
                candidate_copy = dict(candidate)
                candidate_copy['relevance_score'] = round(score, 2)
                scored_candidates.append(candidate_copy)

        # Sort candidates by relevance score descending
        scored_candidates.sort(key=lambda x: x['relevance_score'], reverse=True)
        
        # Deduplicate candidates strictly by normalized brand & title prefix
        unique_results = []
        seen_keys = set()
        for item in scored_candidates:
            raw_title = item.get('title', '').lower()
            norm_key = re.sub(r'[\s\W_]+', '', raw_title[:18])
            if norm_key not in seen_keys:
                seen_keys.add(norm_key)
                unique_results.append(item)
                if len(unique_results) >= limit:
                    break

        # Intelligent Fallback Engine if strict filters yielded no match
        if not unique_results:
            req_subcat = (preferences.get('subcategory') or preferences.get('category') or '').lower()
            req_color = (preferences.get('color') or '').lower()

            # Fallback 1: Match by Category + Color
            for item in CURATED_GARMENT_CATALOG:
                item_sub = (item.get('subcategory', '') + " " + item.get('title', '')).lower()
                item_col = (item.get('color') or '').lower()
                
                cat_match = any(w in item_sub for w in req_subcat.split()) if req_subcat else True
                col_match = (req_color == item_col) if req_color else True

                if cat_match and col_match:
                    item_copy = dict(item)
                    item_copy['relevance_score'] = 0.5
                    norm_k = re.sub(r'[\s\W_]+', '', item_copy['title'].lower()[:18])
                    if norm_k not in seen_keys:
                        seen_keys.add(norm_k)
                        unique_results.append(item_copy)
                        if len(unique_results) >= limit:
                            break

            # Fallback 2: Match by Category alone
            if len(unique_results) < limit and req_subcat:
                for item in CURATED_GARMENT_CATALOG:
                    item_sub = (item.get('subcategory', '') + " " + item.get('title', '')).lower()
                    if any(w in item_sub for w in req_subcat.split()):
                        item_copy = dict(item)
                        item_copy['relevance_score'] = 0.4
                        norm_k = re.sub(r'[\s\W_]+', '', item_copy['title'].lower()[:18])
                        if norm_k not in seen_keys:
                            seen_keys.add(norm_k)
                            unique_results.append(item_copy)
                            if len(unique_results) >= limit:
                                break

            # Fallback 3: General Top Garments
            if not unique_results:
                for item in CURATED_GARMENT_CATALOG[:limit]:
                    item_copy = dict(item)
                    item_copy['relevance_score'] = 0.3
                    unique_results.append(item_copy)

        return unique_results

    @staticmethod
    def _search_live_internet_garments(preferences: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Perform a live web search for garments matching user preference constraints.
        Supports Google Custom Search API and open live web search.
        """
        color = (preferences.get('color') or '').strip()
        brand = (preferences.get('brand') or '').strip()
        subcat = (preferences.get('subcategory') or preferences.get('category') or '').strip()
        gender = (preferences.get('gender') or '').strip()
        occasion = (preferences.get('occasion') or '').strip()

        raw_parts = [color, brand, subcat, gender, occasion]
        clean_parts = [p for p in raw_parts if p and str(p).lower() != 'none']
        query = f"buy {' '.join(clean_parts)}".strip()
        print(f"[GarmentDiscovery][LiveSearch] Query constructed: '{query}'")
        if not query or query == "buy":
            return []

        results = []

        # 1. Google Custom Search API (if configured in environment with CSE ID)
        google_api_key = os.environ.get('GOOGLE_SEARCH_API_KEY') or os.environ.get('GOOGLE_API_KEY')
        google_cse_id = os.environ.get('GOOGLE_CSE_ID') or os.environ.get('GOOGLE_SEARCH_ENGINE_ID')

        if google_api_key and google_cse_id:
            try:
                endpoint = f"https://www.googleapis.com/customsearch/v1?key={google_api_key}&cx={google_cse_id}&q={quote_plus(query)}&num=8"
                resp = requests.get(endpoint, timeout=4)
                if resp.status_code == 200:
                    data = resp.json()
                    items = data.get('items', [])
                    for i, item in enumerate(items):
                        pagemap = item.get('pagemap', {})
                        image_url = None
                        if pagemap.get('cse_image'):
                            image_url = pagemap['cse_image'][0].get('src')
                        elif pagemap.get('metatags'):
                            image_url = pagemap['metatags'][0].get('og:image')

                        # Try to fetch actual image from Bing Image Search first if Google didn't return one
                        if not image_url:
                            try:
                                bing_headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
                                bing_url = f"https://www.bing.com/images/search?q={quote_plus(item.get('title', ''))}"
                                bing_resp = requests.get(bing_url, headers=bing_headers, timeout=2)
                                if bing_resp.status_code == 200:
                                    bing_soup = BeautifulSoup(bing_resp.text, 'html.parser')
                                    mimg_elem = bing_soup.find('img', class_='mimg')
                                    if mimg_elem:
                                        src = mimg_elem.get('src') or mimg_elem.get('data-src')
                                        if src and src.startswith('http'):
                                            image_url = src
                            except Exception:
                                pass

                        if not image_url:
                            image_url = get_color_aware_photo(subcat, color)

                        title = item.get('title', 'Online Garment')
                        link = item.get('link', '')
                        snippet = item.get('snippet', '')

                        price = 49.99
                        price_match = re.search(r'\$\s*(\d+(?:\.\d{2})?)', snippet + " " + title)
                        if price_match:
                            try:
                                price = float(price_match.group(1))
                            except ValueError:
                                pass

                        cat_res = categorize_garment(title=title)

                        results.append({
                            "id": f"live_gsearch_{i}",
                            "title": title,
                            "brand": brand or "Online Store",
                            "category": cat_res.get('category') or "Upper body",
                            "subcategory": cat_res.get('type') or subcat or "Shirts",
                            "gender": gender or "unisex",
                            "price": price,
                            "currency": "$",
                            "color": color or "Various",
                            "colors_available": [color] if color else [],
                            "sizes_available": ["S", "M", "L"],
                            "style": "Modern",
                            "url": link,
                            "image_url": image_url,
                            "description": snippet[:150],
                            "tryon_ready": True
                        })
            except Exception as e:
                print(f"[GarmentDiscovery][LiveSearch] Google Custom Search warning: {e}")

        # 2. Open Live Web Search Fallback
        if not results:
            try:
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.9"
                }
                search_url = f"https://html.duckduckgo.com/html/?q={quote_plus(query + ' fashion clothing store -amazon -site:amazon.com')}"
                resp = requests.get(search_url, headers=headers, timeout=1.5)
                if resp.status_code == 200:
                    soup = BeautifulSoup(resp.text, 'html.parser')
                    title_links = soup.find_all('a', class_='result__a', limit=10)
                    snippet_elems = soup.find_all('td', class_='result__snippet', limit=10)

                    for idx in range(min(len(title_links), 10)):
                        t_elem = title_links[idx]
                        raw_title = t_elem.get_text().strip()
                        clean_title = re.sub(r'\s*[\|-].*$', '', raw_title)
                        raw_href = t_elem.get('href', '')
                        
                        # Clean duckduckgo redirect link to store URL
                        actual_url = raw_href
                        if 'duckduckgo.com' in raw_href or 'uddg=' in raw_href or 'u3=' in raw_href:
                            parsed = parse_qs(urlparse(raw_href).query)
                            for k in ['url', 'uddg', 'u3', 'u']:
                                if k in parsed:
                                    val = parsed[k][0]
                                    if val.startswith('http') and 'duckduckgo.com' not in val and 'bing.com' not in val:
                                        actual_url = val
                                        break
                                    elif 'url=' in val:
                                        sub_p = parse_qs(urlparse(val).query)
                                        if 'url' in sub_p and sub_p['url'][0].startswith('http'):
                                            actual_url = sub_p['url'][0]
                                            break

                        # Exclude Amazon links and marketplace non-clothing results
                        if 'amazon.com' in actual_url.lower() or 'amazon' in raw_title.lower() or 'amazon' in clean_title.lower():
                            continue

                        # Exclude non-apparel terms (refrigerators, pencil cases, toys, etc.)
                        non_fashion_kw = ['fridge', 'refrigerator', 'case', 'pencil', 'toy', 'electronics', 'phone', 'building', 'fortress', 'castle', 'decor', 'gowns', 'mortarboard', 'hat', 'beach', 'sunset', 'ideas', 'shop all', 'target', 'brandy melville']
                        if any(kw in clean_title.lower() for kw in non_fashion_kw):
                            continue

                        snip_text = snippet_elems[idx].get_text().strip() if idx < len(snippet_elems) else ""

                        price = 49.99
                        price_match = re.search(r'\$\s*(\d+(?:\.\d{2})?)', snip_text + " " + clean_title)
                        if price_match:
                            try:
                                price = float(price_match.group(1))
                            except ValueError:
                                pass

                        cat_res = categorize_garment(title=clean_title)
                        
                        # Try to fetch actual image from Bing Image Search (enforcing fashion model context)
                        img_url = None
                        try:
                            bing_headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
                            bing_query = f"{clean_title} {color} {subcat} fashion clothing wear"
                            bing_url = f"https://www.bing.com/images/search?q={quote_plus(bing_query)}"
                            bing_resp = requests.get(bing_url, headers=bing_headers, timeout=2)
                            if bing_resp.status_code == 200:
                                bing_soup = BeautifulSoup(bing_resp.text, 'html.parser')
                                mimg_elem = bing_soup.find('img', class_='mimg')
                                if mimg_elem:
                                    src = mimg_elem.get('src') or mimg_elem.get('data-src')
                                    if src and src.startswith('http'):
                                        img_url = src
                        except Exception:
                            pass
                            
                        if not img_url:
                            img_url = get_color_aware_photo(subcat, color)

                        results.append({
                            "id": f"live_web_{idx}",
                            "title": clean_title or "E-Commerce Garment",
                            "brand": brand or "Online Store",
                            "category": cat_res.get('category') or "Upper body",
                            "subcategory": cat_res.get('type') or subcat or "Shirts",
                            "gender": gender or "unisex",
                            "price": price,
                            "currency": "$",
                            "color": color or "Various",
                            "colors_available": [color] if color else [],
                            "sizes_available": ["S", "M", "L"],
                            "style": "Modern",
                            "url": actual_url,
                            "image_url": img_url,
                            "description": snip_text[:150],
                            "tryon_ready": True
                        })
            except Exception as e:
                print(f"[GarmentDiscovery][LiveSearch] Open Web Search warning: {e}")

        # Cache discovered items into SQLite database table 'garment_metadata'
        for res in results:
            try:
                db_manager.execute_query(
                    """INSERT OR REPLACE INTO garment_metadata 
                       (url, title, price, images, sizes, colors, brand, scraped_at, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)""",
                    (res['url'], res['title'], str(res['price']),
                     json.dumps([res['image_url']]),
                     json.dumps(res['sizes_available']),
                     json.dumps(res['colors_available']),
                     res['brand'])
                )
            except Exception:
                pass

        return results

    @staticmethod
    def _calculate_relevance_score(item: Dict[str, Any], prefs: Dict[str, Any]) -> float:
        """
        Calculate strict matching score based on user preference slots.
        """
        score = 0.5  # Base match score

        req_cat = (prefs.get('category') or '').lower()
        req_subcat = (prefs.get('subcategory') or '').lower()

        item_cat = (item.get('category') or '').lower()
        item_subcat = (item.get('subcategory') or '').lower()
        item_title = (item.get('title') or '').lower()

        # 1. Subcategory / Specific Item Type Matching (STRICT)
        if req_subcat:
            if req_subcat in item_subcat or req_subcat in item_title or item_subcat in req_subcat:
                score += 0.6
            elif "blazer" in req_subcat and ("blazer" in item_title or "suit jacket" in item_title):
                score += 0.6
            elif "trouser" in req_subcat and ("trouser" in item_title or "pant" in item_title or "chino" in item_title or "pant" in item_subcat):
                score += 0.6
            elif "shirt" in req_subcat and ("shirt" in item_title or "button-down" in item_title or "shirt" in item_subcat):
                score += 0.6
            else:
                score -= 0.8  # Heavy penalty for wrong garment type
        elif req_cat:
            if req_cat in item_cat:
                score += 0.3
            else:
                score -= 0.4

        # 2. Color Match & Color Exclusions
        req_color = (prefs.get('color') or '').lower()
        excluded_colors = [c.lower() for c in prefs.get('excluded_colors', [])]
        item_color = (item.get('color') or '').lower()

        # Check if color is explicitly excluded
        if item_color in excluded_colors:
            return 0.0  # Immediately drop excluded colors
        elif excluded_colors and item_color not in excluded_colors:
            score += 0.4  # Bonus for picking a non-excluded color

        if req_color:
            if req_color == item_color or req_color in item_color or req_color in item_title:
                score += 0.6
            else:
                score -= 0.8  # Penalty for non-matching primary color when color is requested

        # 3. Price Budget Filter
        max_price = prefs.get('max_price')
        item_price = float(item.get('price') or 0)
        if max_price is not None:
            try:
                max_p = float(max_price)
                if item_price <= max_p:
                    score += 0.3
                else:
                    score -= 1.0  # Exceeding budget drops item
            except ValueError:
                pass

        # 4. Gender Filter
        req_gender = (prefs.get('gender') or '').lower()
        item_gender = (item.get('gender') or '').lower()
        if req_gender and req_gender != 'all':
            if item_gender == 'unisex' or item_gender == req_gender or req_gender in item_gender:
                score += 0.2
            else:
                score -= 0.4

        # 5. Brand Filter
        req_brand = (prefs.get('brand') or '').lower()
        item_brand = (item.get('brand') or '').lower()
        if req_brand:
            if req_brand in item_brand or item_brand in req_brand:
                score += 0.4
            else:
                score -= 0.2

        # 6. Keywords matching in title/description (style, material, occasion)
        search_text = f"{item_title} {item.get('description', '')} {item.get('style', '')} {item.get('material', '')} {item.get('occasion', '')}".lower()
        
        occasion = (prefs.get('occasion') or '').lower()
        if occasion and occasion in search_text:
            score += 0.2

        material = (prefs.get('material') or '').lower()
        if material and material in search_text:
            score += 0.2

        style = (prefs.get('style') or '').lower()
        if style and style in search_text:
            score += 0.2

        return max(0.01, score)

    @staticmethod
    def _get_db_garments() -> List[Dict[str, Any]]:
        """
        Fetch cached garment metadata from database.
        """
        try:
            rows = db_manager.execute_query(
                "SELECT * FROM garment_metadata ORDER BY id DESC LIMIT 25",
                fetch_all=True
            )
            items = []
            for r in (rows or []):
                try:
                    imgs = json.loads(r.get('images') or '[]')
                    img_url = imgs[0] if imgs else "https://images.unsplash.com/photo-1591047139829-d91aecb6caea?w=600&auto=format&fit=crop"
                except Exception:
                    img_url = "https://images.unsplash.com/photo-1591047139829-d91aecb6caea?w=600&auto=format&fit=crop"

                price_str = str(r.get('price') or '49.99')
                price_match = re.search(r'[\d\.]+', price_str)
                price_val = float(price_match.group(0)) if price_match else 49.99

                title = r.get('title') or "E-Commerce Garment"
                color = "Black" if "black" in title.lower() else ("Yellow" if "yellow" in title.lower() else ("Blue" if "blue" in title.lower() else ("White" if "white" in title.lower() else "Beige")))
                cat_res = categorize_garment(title=title)

                items.append({
                    "id": f"db_{r.get('id')}",
                    "title": title,
                    "brand": r.get('brand') or "Fashion Brand",
                    "category": cat_res.get('category') or r.get('category') or "Upper body",
                    "subcategory": cat_res.get('type') or r.get('type') or "Shirts",
                    "gender": "unisex",
                    "price": price_val,
                    "currency": "$",
                    "color": color,
                    "colors_available": [color],
                    "sizes_available": ["S", "M", "L"],
                    "style": "Modern",
                    "url": r.get('url'),
                    "image_url": img_url,
                    "description": f"Available from {r.get('brand') or 'Online Store'}",
                    "tryon_ready": True
                })
            return items
        except Exception:
            return []
