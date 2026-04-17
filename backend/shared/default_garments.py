"""
Default garments configuration loader
Loads pre-configured garment URLs by gender from config file
"""

import json
import os
from typing import List, Dict, Optional
from shared.logger import logger

# Cache for loaded config
_default_garments_cache: Optional[Dict] = None


def _load_config() -> Dict:
    """Load default garments config from JSON file"""
    global _default_garments_cache

    if _default_garments_cache is not None:
        return _default_garments_cache

    config_path = os.path.join(
        os.path.dirname(__file__),
        '..',
        'config',
        'default_garments.json'
    )

    try:
        with open(config_path, 'r') as f:
            _default_garments_cache = json.load(f)
            logger.info(f"Loaded default garments config from {config_path}")
            return _default_garments_cache
    except FileNotFoundError:
        logger.warning(f"Default garments config not found at {config_path}")
        return {}
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in default garments config: {str(e)}")
        return {}


def get_default_garments(gender: str = None) -> List[Dict]:
    """
    Get default garment URLs by gender

    Args:
        gender: 'men', 'women', 'unisex', or None for all

    Returns:
        List of garment dicts with url, name, category
    """
    config = _load_config()

    # Always include "default" garments (available to all users)
    default_garments = config.get('default', [])

    if not gender:
        # Return default + all gender-specific garments
        all_garments = list(default_garments)
        for g in ['men', 'women', 'unisex']:
            all_garments.extend(config.get(g, []))
        return all_garments

    gender = gender.lower().strip()

    # Normalize gender values
    if gender in ['male', 'm', 'man']:
        gender = 'men'
    elif gender in ['female', 'f', 'woman']:
        gender = 'women'

    # Return default garments + gender-specific garments
    result = list(default_garments)
    result.extend(config.get(gender, []))
    return result


def reload_config():
    """Force reload of config file (useful after updates)"""
    global _default_garments_cache
    _default_garments_cache = None
    return _load_config()
