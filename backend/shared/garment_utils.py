"""
Shared garment categorization utilities
Used by multiple features (garments, wardrobe, tryon)
"""

from shared.logger import logger


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

