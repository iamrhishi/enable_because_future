"""
Shared garment categorization utilities
Used by multiple features (garments, wardrobe, tryon)
"""

from shared.logger import logger


import re


def categorize_garment(image_url: str = None, image_data: bytes = None, title: str = None, url: str = None) -> dict:
    """
    Categorize garment using weighted rule-based classification across title, product URL, and image URL.

    Returns:
        dict with category ('upper'/'lower'), type ('shirt', 'polo', 'pants', etc.), confidence
    """
    logger.info(f"categorize_garment: ENTRY - title={title[:50] if title else None}, url={url[:50] if url else None}")

    try:
        title_text = (title or '').lower()
        product_url_text = (url or '').lower()
        image_url_text = (image_url or '').lower()

        # Dictionary of upper body sub-types and their associated keywords
        upper_keywords = {
            'polo': ['polo', 'polos', 'polo-shirt', 'polo-tshirt'],
            'shirt': ['shirt', 'shirts', 'blouse', 'blouses', 'top', 'tops', 'tee', 'tees', 't-shirt', 'tshirt', 'tank', 'tanktop', 'cami', 'henley', 'tunics', 'tunic'],
            'jacket': ['jacket', 'jackets', 'coat', 'coats', 'blazer', 'blazers', 'cardigan', 'hoodie', 'hoodies', 'sweater', 'sweaters', 'vest', 'vests', 'pullover', 'parka', 'trench', 'windbreaker', 'fleece', 'puffer', 'anorak', 'overshirt', 'shacket', 'knitwear', 'knit', 'outerwear'],
            'crop': ['crop', 'croptop', 'corset', 'bustier', 'halter', 'bandeau', 'camisole'],
            'dress': ['dress', 'dresses', 'gown', 'gowns', 'frock', 'jumpsuit', 'romper', 'bodysuit'],
        }

        # Dictionary of lower body sub-types and their associated keywords
        lower_keywords = {
            'pants': ['pants', 'trousers', 'jeans', 'slacks', 'sweatpants', 'joggers', 'chinos', 'cargo', 'culottes', 'palazzo', 'bottom', 'bottoms'],
            'shorts': ['shorts', 'bermuda', 'bikershorts', 'trunks'],
            'skirt': ['skirt', 'skirts', 'miniskirt', 'midiskirt', 'maxiskirt'],
            'leggings': ['leggings', 'tights']
        }

        # URL path category signals (e.g. /men-clothing-shirts-polos/)
        upper_url_signals = ['/upper', '/tops', '/top', '/shirts', '/shirt', '/polos', '/polo', '/jackets', '/jacket', '/outerwear', '/sweaters', '/knitwear', '/hoodies']
        lower_url_signals = ['/lower', '/bottoms', '/bottom', '/pants', '/jeans', '/trousers', '/shorts', '/skirts', '/skirt', '/leggings']

        upper_score = 0
        lower_score = 0
        best_upper_type = 'top'
        best_lower_type = 'pants'

        def matches_word(kw, text):
            escaped = re.escape(kw)
            return bool(re.search(r'(?:^|[\s/_\-\.,])' + escaped + r'(?:$|[\s/_\-\.,])', text))

        # 1. Title matching (highest weight)
        for gtype, keywords in upper_keywords.items():
            for kw in keywords:
                if matches_word(kw, title_text):
                    upper_score += 10
                    best_upper_type = gtype

        for gtype, keywords in lower_keywords.items():
            for kw in keywords:
                if matches_word(kw, title_text):
                    lower_score += 10
                    best_lower_type = gtype

        # 2. Product URL path signals (high weight)
        for signal in upper_url_signals:
            if signal in product_url_text or signal in image_url_text:
                upper_score += 8
        for signal in lower_url_signals:
            if signal in product_url_text or signal in image_url_text:
                lower_score += 8

        # 3. Substring URL fallback (medium weight)
        if upper_score == 0 and lower_score == 0:
            for gtype, keywords in upper_keywords.items():
                for kw in keywords:
                    if kw in product_url_text or kw in image_url_text:
                        upper_score += 5
                        best_upper_type = gtype
            for gtype, keywords in lower_keywords.items():
                for kw in keywords:
                    if kw in product_url_text or kw in image_url_text:
                        lower_score += 5
                        best_lower_type = gtype

        # Decision based on score
        if upper_score > lower_score:
            category = 'upper'
            garment_type = best_upper_type
            confidence = min(0.95, 0.6 + (upper_score * 0.02))
        elif lower_score > upper_score:
            category = 'lower'
            garment_type = best_lower_type
            confidence = min(0.95, 0.6 + (lower_score * 0.02))
        else:
            category = 'upper'
            garment_type = 'top'
            confidence = 0.4

        result = {
            'category': category,
            'type': garment_type,
            'confidence': round(confidence, 2)
        }
        logger.info(f"categorize_garment: EXIT - result={result} (scores: upper={upper_score}, lower={lower_score})")
        return result
    except Exception as e:
        logger.exception(f"categorize_garment: EXIT - Error: {str(e)}")
        raise


