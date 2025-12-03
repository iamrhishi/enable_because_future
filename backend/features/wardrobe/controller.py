"""
Wardrobe Management API endpoints
CRUD operations for wardrobe items and categories
Uses WardrobeItem and WardrobeCategory models
JWT authentication via @require_auth decorator extracts user_id from token
"""

from flask import Blueprint, request
from features.wardrobe.model import WardrobeItem
from features.wardrobe.category_model import WardrobeCategory
from shared.storage import get_storage_service
from features.wardrobe.extractors import BrandExtractorFactory
from shared.garment_utils import categorize_garment
from shared.image_processing import preprocess_image, fetch_image_from_url, validate_image
from shared.response import success_response, error_response_from_string
from shared.middleware import require_auth
from shared.validators import validate_url
from shared.errors import ValidationError, NotFoundError
from shared.logger import logger
import base64
import json
from io import BytesIO

wardrobe_bp = Blueprint('wardrobe', __name__, url_prefix='/api/wardrobe')


# ===== CATEGORY MANAGEMENT =====

@wardrobe_bp.route('/categories', methods=['POST'])
@require_auth  # JWT decorator validates token and sets request.user_id from token
def create_category():
    """
    Create a new wardrobe category
    Uses WardrobeCategory model
    user_id is extracted from JWT token by @require_auth decorator
    """
    # user_id comes from JWT token via @require_auth decorator
    user_id = request.user_id
    logger.info(f"create_category: ENTRY - user_id={user_id} (from JWT)")
    
    try:
        data = request.get_json()
        if not data:
            return error_response_from_string('No data provided', 400, 'VALIDATION_ERROR')
        
        name = data.get('name', '').strip()
        if not name:
            return error_response_from_string('Category name is required', 400, 'VALIDATION_ERROR')
        
        # Validate category_section (required)
        category_section = data.get('category_section', '').strip()
        if not category_section:
            return error_response_from_string('Category section is required', 400, 'VALIDATION_ERROR')
        
        # Check if section exists (platform or user-created)
        section = WardrobeCategory.get_section_by_name(category_section, user_id)
        if not section:
            return error_response_from_string(
                f'Category section "{category_section}" does not exist. Please create the section first.',
                400,
                'VALIDATION_ERROR'
            )
        
        # Check if category already exists for this user and section
        existing = WardrobeCategory.get_by_name(name, user_id)
        if existing and existing.category_section == category_section:
            return error_response_from_string(f'Category "{name}" already exists in this section', 400, 'VALIDATION_ERROR')
        
        # Create category
        category = WardrobeCategory(
            user_id=user_id,
            name=name,
            description=data.get('description', '').strip(),
            category_section=category_section
        )
        category.save()
        
        logger.info(f"create_category: EXIT - Category created: {name}")
        return success_response(data=category.to_dict(), status_code=201)
        
    except Exception as e:
        logger.exception(f"create_category: EXIT - Error: {str(e)}")
        return error_response_from_string(f'Server error: {str(e)}', 500)


@wardrobe_bp.route('/categories', methods=['GET'])
@require_auth  # JWT decorator validates token and sets request.user_id from token
def get_categories():
    """
    Get all wardrobe categories for authenticated user
    Uses WardrobeCategory model
    user_id is extracted from JWT token by @require_auth decorator
    """
    # user_id comes from JWT token via @require_auth decorator
    user_id = request.user_id
    logger.info(f"get_categories: ENTRY - user_id={user_id} (from JWT)")
    
    try:
        search = request.args.get('search', '').strip()
        category_section = request.args.get('category_section', '').strip()  # Optional filter by section
        
        # Get all sections (platform + user-created)
        all_sections = WardrobeCategory.get_all_sections(user_id)
        
        # Get platform categories (grouped by section)
        platform_categories = {}
        for section in all_sections:
            section_name = section['name']
            if not category_section or category_section == section_name:
                # Only get platform categories for platform sections
                if section.get('user_id') is None:
                    platform_categories[section_name] = WardrobeCategory.get_platform_categories(section_name)
                else:
                    platform_categories[section_name] = []  # User sections don't have platform categories
        
        # Get user-created categories
        user_categories = WardrobeCategory.get_all_by_user(
            user_id, 
            search=search if search else None,
            category_section=category_section if category_section else None
        )
        
        # Group user categories by section
        user_categories_by_section = {}
        for cat in user_categories:
            section_name = cat.category_section or 'uncategorized'
            if section_name not in user_categories_by_section:
                user_categories_by_section[section_name] = []
            user_categories_by_section[section_name].append(cat.to_dict())
        
        # Build response grouped by section
        result = {
            'sections': all_sections,  # All sections (platform + user-created)
            'categories_by_section': {}
        }
        
        for section in all_sections:
            section_name = section['name']
            result['categories_by_section'][section_name] = {
                'platform_categories': platform_categories.get(section_name, []),
                'user_categories': user_categories_by_section.get(section_name, [])
            }
        
        logger.info(f"get_categories: EXIT - Found {len(user_categories)} user categories")
        return success_response(data=result)
        
    except Exception as e:
        logger.exception(f"get_categories: EXIT - Error: {str(e)}")
        return error_response_from_string(f'Server error: {str(e)}', 500)


@wardrobe_bp.route('/category-sections', methods=['GET'])
@require_auth  # JWT decorator validates token and sets request.user_id from token
def get_category_sections():
    """
    Get all available category sections (platform + user-created)
    user_id is extracted from JWT token by @require_auth decorator
    """
    # user_id comes from JWT token via @require_auth decorator
    user_id = request.user_id
    logger.info(f"get_category_sections: ENTRY - user_id={user_id} (from JWT)")
    
    try:
        sections = WardrobeCategory.get_all_sections(user_id)
        logger.info(f"get_category_sections: EXIT - Found {len(sections)} sections")
        return success_response(data=sections)
        
    except Exception as e:
        logger.exception(f"get_category_sections: EXIT - Error: {str(e)}")
        return error_response_from_string(f'Server error: {str(e)}', 500)


@wardrobe_bp.route('/category-sections', methods=['POST'])
@require_auth  # JWT decorator validates token and sets request.user_id from token
def create_category_section():
    """
    Create a new user-specific category section
    user_id is extracted from JWT token by @require_auth decorator
    """
    # user_id comes from JWT token via @require_auth decorator
    user_id = request.user_id
    logger.info(f"create_category_section: ENTRY - user_id={user_id} (from JWT)")
    
    try:
        data = request.get_json()
        if not data:
            return error_response_from_string('No data provided', 400, 'VALIDATION_ERROR')
        
        name = data.get('name', '').strip()
        if not name:
            return error_response_from_string('Section name is required', 400, 'VALIDATION_ERROR')
        
        display_name = data.get('display_name', '').strip()
        if not display_name:
            display_name = name  # Use name as display_name if not provided
        
        description = data.get('description', '').strip()
        icon_name = data.get('icon_name', '').strip()  # Icon identifier (e.g., 'custom_section_1')
        icon_url = data.get('icon_url', '').strip()  # Optional icon URL
        sort_order = data.get('sort_order', 999)
        
        # Create user section
        section = WardrobeCategory.create_user_section(
            user_id=user_id,
            name=name,
            display_name=display_name,
            description=description,
            icon_name=icon_name if icon_name else None,
            icon_url=icon_url if icon_url else None,
            sort_order=sort_order
        )
        
        logger.info(f"create_category_section: EXIT - Section created: {name}")
        return success_response(data=section, status_code=201)
        
    except ValueError as e:
        logger.warning(f"create_category_section: EXIT - Validation error: {str(e)}")
        return error_response_from_string(str(e), 400, 'VALIDATION_ERROR')
    except Exception as e:
        logger.exception(f"create_category_section: EXIT - Error: {str(e)}")
        return error_response_from_string(f'Server error: {str(e)}', 500)


@wardrobe_bp.route('/categories/<int:category_id>', methods=['GET'])
@require_auth  # JWT decorator validates token and sets request.user_id from token
def get_category(category_id: int):
    """
    Get a specific category by ID
    Uses WardrobeCategory model
    user_id is extracted from JWT token by @require_auth decorator
    """
    # user_id comes from JWT token via @require_auth decorator
    user_id = request.user_id
    logger.info(f"get_category: ENTRY - category_id={category_id}, user_id={user_id} (from JWT)")
    
    try:
        category = WardrobeCategory.get_by_id(category_id, user_id)
        if not category:
            return error_response_from_string('Category not found', 404, 'NOT_FOUND')
        
        logger.info(f"get_category: EXIT - Category found")
        return success_response(data=category.to_dict())
        
    except Exception as e:
        logger.exception(f"get_category: EXIT - Error: {str(e)}")
        return error_response_from_string(f'Server error: {str(e)}', 500)


@wardrobe_bp.route('/categories/<int:category_id>', methods=['PUT'])
@require_auth  # JWT decorator validates token and sets request.user_id from token
def update_category(category_id: int):
    """
    Update a category
    Uses WardrobeCategory model
    user_id is extracted from JWT token by @require_auth decorator
    """
    # user_id comes from JWT token via @require_auth decorator
    user_id = request.user_id
    logger.info(f"update_category: ENTRY - category_id={category_id}, user_id={user_id} (from JWT)")
    
    try:
        data = request.get_json()
        if not data:
            return error_response_from_string('No data provided', 400, 'VALIDATION_ERROR')
        
        category = WardrobeCategory.get_by_id(category_id, user_id)
        if not category:
            return error_response_from_string('Category not found', 404, 'NOT_FOUND')
        
        # Update fields
        if 'name' in data:
            new_name = data['name'].strip()
            if new_name and new_name != category.name:
                # Check if new name already exists
                existing = WardrobeCategory.get_by_name(new_name, user_id)
                if existing and existing.id != category_id:
                    return error_response_from_string(f'Category "{new_name}" already exists', 400, 'VALIDATION_ERROR')
                category.name = new_name
        
        if 'description' in data:
            category.description = data['description'].strip()
        
        category.save()
        
        logger.info(f"update_category: EXIT - Category updated")
        return success_response(data=category.to_dict())
        
    except Exception as e:
        logger.exception(f"update_category: EXIT - Error: {str(e)}")
        return error_response_from_string(f'Server error: {str(e)}', 500)


@wardrobe_bp.route('/categories/<int:category_id>', methods=['DELETE'])
@require_auth  # JWT decorator validates token and sets request.user_id from token
def delete_category(category_id: int):
    """
    Delete a category
    Uses WardrobeCategory model
    user_id is extracted from JWT token by @require_auth decorator
    """
    # user_id comes from JWT token via @require_auth decorator
    user_id = request.user_id
    logger.info(f"delete_category: ENTRY - category_id={category_id}, user_id={user_id} (from JWT)")
    
    try:
        category = WardrobeCategory.get_by_id(category_id, user_id)
        if not category:
            return error_response_from_string('Category not found', 404, 'NOT_FOUND')
        
        category.delete()
        
        logger.info(f"delete_category: EXIT - Category deleted")
        return success_response(data={'message': 'Category deleted successfully'})
        
    except Exception as e:
        logger.exception(f"delete_category: EXIT - Error: {str(e)}")
        return error_response_from_string(f'Server error: {str(e)}', 500)


# ===== GARMENT MANAGEMENT =====

@wardrobe_bp.route('/items', methods=['POST'])
@require_auth  # JWT decorator validates token and sets request.user_id from token
def add_garment():
    """
    Add a garment to wardrobe
    Supports:
    - Image upload from gallery
    - URL extraction (scrapes product page and extracts images)
    Uses WardrobeItem model
    user_id is extracted from JWT token by @require_auth decorator
    """
    # user_id comes from JWT token via @require_auth decorator
    user_id = request.user_id
    logger.info(f"add_garment: ENTRY - user_id={user_id} (from JWT)")
    
    try:
        garment_image = None
        garment_url = None
        product_info = None
        
        # Method 1: Direct image upload
        if 'garment_image' in request.files:
            garment_image = request.files['garment_image'].read()
            garment_image = preprocess_image(garment_image, resize=True, normalize=True)
        
        # Method 2: Extract from URL
        elif 'garment_url' in request.form or (request.is_json and request.get_json().get('garment_url')):
            garment_url = validate_url(
                request.form.get('garment_url') or request.get_json().get('garment_url')
            )
            
            # Use brand-specific extractor
            extractor = BrandExtractorFactory.get_extractor(garment_url)
            product_info = extractor.extract_product_info(garment_url)
            
            # Fetch first image from extracted images
            if product_info.get('images'):
                try:
                    garment_image = fetch_image_from_url(product_info['images'][0])
                    garment_image = preprocess_image(garment_image, resize=True, normalize=True)
                except Exception as e:
                    logger.warning(f"add_garment: Failed to fetch image from URL: {str(e)}")
                    return error_response_from_string(f'Failed to fetch image from URL: {str(e)}', 400, 'VALIDATION_ERROR')
            else:
                return error_response_from_string('No images found in product URL', 400, 'VALIDATION_ERROR')
        
        if not garment_image:
            return error_response_from_string('garment_image or garment_url required', 400, 'VALIDATION_ERROR')
        
        # Get category information
        category = request.form.get('category') or (request.get_json() or {}).get('category', 'upper')
        custom_category_name = request.form.get('custom_category_name') or (request.get_json() or {}).get('custom_category_name')
        category_id = request.form.get('category_id') or (request.get_json() or {}).get('category_id')
        
        # Validate category
        if custom_category_name:
            # Verify custom category exists
            if category_id:
                cat = WardrobeCategory.get_by_id(int(category_id), user_id)
                if not cat:
                    return error_response_from_string('Category not found', 404, 'NOT_FOUND')
        elif category not in ['upper', 'lower']:
            return error_response_from_string('Category must be "upper" or "lower" if not using custom category', 400, 'VALIDATION_ERROR')
        
        # Auto-categorize if not provided
        title = product_info.get('title') if product_info else request.form.get('title') or (request.get_json() or {}).get('title')
        if not category or category == 'upper':  # Default categorization
            categorization = categorize_garment(title=title)
            category = categorization['category']
            garment_type = categorization['type']
        else:
            garment_type = request.form.get('garment_type') or (request.get_json() or {}).get('garment_type')
        
        # Save image to local storage
        import uuid
        garment_id = str(uuid.uuid4())
        storage_path = f"wardrobe/{user_id}/{garment_id}.png"
        
        storage_service = get_storage_service()
        image_url = storage_service.upload_image(
            garment_image,
            storage_path,
            content_type='image/png'
        )
        
        # Get new fields from request
        data = request.get_json() if request.is_json else {}
        form_data = request.form
        
        # Parse fabric (JSON array or string)
        fabric = None
        if 'fabric' in form_data or 'fabric' in data:
            fabric_input = form_data.get('fabric') or data.get('fabric')
            if isinstance(fabric_input, str):
                try:
                    import json
                    fabric = json.dumps(json.loads(fabric_input))  # Validate and re-stringify
                except json.JSONDecodeError:
                    return error_response_from_string('Invalid fabric format. Expected JSON array.', 400, 'VALIDATION_ERROR')
            elif isinstance(fabric_input, list):
                import json
                # Validate fabric percentages sum to 100
                total_percentage = sum(item.get('percentage', 0) for item in fabric_input if isinstance(item, dict))
                if total_percentage != 100:
                    return error_response_from_string('Fabric percentages must sum to 100%', 400, 'VALIDATION_ERROR')
                fabric = json.dumps(fabric_input)
        
        # Get care_instructions, size, description
        care_instructions = form_data.get('care_instructions') or data.get('care_instructions')
        size = form_data.get('size') or data.get('size')
        description = form_data.get('description') or data.get('description')
        
        # Create wardrobe item
        wardrobe_item = WardrobeItem(
            user_id=user_id,
            image_path=image_url,
            category=category if not custom_category_name else None,
            custom_category_name=custom_category_name,
            category_id=int(category_id) if category_id else None,
            garment_category_type=garment_type,
            brand=product_info.get('brand') if product_info else form_data.get('brand') or data.get('brand'),
            color=product_info.get('colors', [None])[0] if product_info and product_info.get('colors') else form_data.get('color') or data.get('color'),
            is_external=bool(garment_url),
            title=title,
            fabric=fabric,
            care_instructions=care_instructions,
            size=size,
            description=description
        )
        wardrobe_item.save()
        
        # Return product info if extracted from URL
        result = wardrobe_item.to_dict()
        if product_info:
            result['product_info'] = product_info
        
        # Convert image_path to absolute URL for frontend
        if result.get('image_path'):
            from shared.url_utils import to_absolute_url
            result['image_url'] = to_absolute_url(result['image_path'])
        
        logger.info(f"add_garment: EXIT - Garment added: {garment_id}")
        return success_response(data=result, status_code=201)
        
    except ValidationError as e:
        logger.exception(f"add_garment: EXIT - ValidationError: {str(e)}")
        return error_response_from_string(str(e), 400, 'VALIDATION_ERROR')
    except Exception as e:
        logger.exception(f"add_garment: EXIT - Error: {str(e)}")
        return error_response_from_string(f'Server error: {str(e)}', 500)


@wardrobe_bp.route('/items', methods=['GET'])
@require_auth  # JWT decorator validates token and sets request.user_id from token
def get_wardrobe_items():
    """
    Get wardrobe items with search and filter
    Uses WardrobeItem model
    user_id is extracted from JWT token by @require_auth decorator
    """
    # user_id comes from JWT token via @require_auth decorator
    user_id = request.user_id
    logger.info(f"get_wardrobe_items: ENTRY - user_id={user_id} (from JWT)")
    
    try:
        # Get query parameters
        category = request.args.get('category')  # 'upper', 'lower', or custom category name
        custom_category_id = request.args.get('category_id')  # Custom category ID
        search = request.args.get('search', '').strip()
        
        # Get items
        custom_category_name = None
        if custom_category_id:
            # Get custom category name
            custom_cat = WardrobeCategory.get_by_id(int(custom_category_id), user_id)
            if custom_cat:
                custom_category_name = custom_cat.name
        
        items = WardrobeItem.get_by_user(
            user_id=user_id,
            category=category if not custom_category_name else None,
            custom_category_name=custom_category_name,
            search=search if search else None
        )
        
        result = [item.to_dict() for item in items]
        
        # Convert image_path to absolute URLs for frontend
        from shared.url_utils import to_absolute_url
        for item in result:
            if item.get('image_path'):
                item['image_url'] = to_absolute_url(item['image_path'])
        
        logger.info(f"get_wardrobe_items: EXIT - Found {len(result)} items")
        return success_response(data=result)
        
    except Exception as e:
        logger.exception(f"get_wardrobe_items: EXIT - Error: {str(e)}")
        return error_response_from_string(f'Server error: {str(e)}', 500)


@wardrobe_bp.route('/items/<int:item_id>', methods=['GET'])
@require_auth  # JWT decorator validates token and sets request.user_id from token
def get_wardrobe_item(item_id: int):
    """
    Get a specific wardrobe item
    Uses WardrobeItem model
    user_id is extracted from JWT token by @require_auth decorator
    """
    # user_id comes from JWT token via @require_auth decorator
    user_id = request.user_id
    logger.info(f"get_wardrobe_item: ENTRY - item_id={item_id}, user_id={user_id} (from JWT)")
    
    try:
        item = WardrobeItem.get_by_id(item_id, user_id)
        if not item:
            return error_response_from_string('Wardrobe item not found', 404, 'NOT_FOUND')
        
        result = item.to_dict()
        # Convert image_path to absolute URL for frontend
        if result.get('image_path'):
            from shared.url_utils import to_absolute_url
            result['image_url'] = to_absolute_url(result['image_path'])
        
        logger.info(f"get_wardrobe_item: EXIT - Item found")
        return success_response(data=result)
        
    except Exception as e:
        logger.exception(f"get_wardrobe_item: EXIT - Error: {str(e)}")
        return error_response_from_string(f'Server error: {str(e)}', 500)


@wardrobe_bp.route('/items/<int:item_id>', methods=['PUT'])
@require_auth  # JWT decorator validates token and sets request.user_id from token
def update_wardrobe_item(item_id: int):
    """
    Update a wardrobe item
    Uses WardrobeItem model
    user_id is extracted from JWT token by @require_auth decorator
    """
    # user_id comes from JWT token via @require_auth decorator
    user_id = request.user_id
    logger.info(f"update_wardrobe_item: ENTRY - item_id={item_id}, user_id={user_id} (from JWT)")
    
    try:
        data = request.get_json()
        if not data:
            return error_response_from_string('No data provided', 400, 'VALIDATION_ERROR')
        
        item = WardrobeItem.get_by_id(item_id, user_id)
        if not item:
            return error_response_from_string('Wardrobe item not found', 404, 'NOT_FOUND')
        
        # Update fields
        if 'category' in data:
            item.category = data['category']
        if 'custom_category_name' in data:
            item.custom_category_name = data['custom_category_name']
        if 'category_id' in data:
            item.category_id = data['category_id']
        if 'garment_category_type' in data:
            item.garment_category_type = data['garment_category_type']
        if 'brand' in data:
            item.brand = data['brand']
        if 'color' in data:
            item.color = data['color']
        if 'title' in data:
            item.title = data['title']
        
        # Update new fields with validation
        if 'fabric' in data:
            fabric_input = data['fabric']
            if isinstance(fabric_input, str):
                try:
                    import json
                    fabric = json.dumps(json.loads(fabric_input))  # Validate and re-stringify
                except json.JSONDecodeError:
                    return error_response_from_string('Invalid fabric format. Expected JSON array.', 400, 'VALIDATION_ERROR')
            elif isinstance(fabric_input, list):
                import json
                # Validate fabric percentages sum to 100
                total_percentage = sum(item.get('percentage', 0) for item in fabric_input if isinstance(item, dict))
                if total_percentage != 100:
                    return error_response_from_string('Fabric percentages must sum to 100%', 400, 'VALIDATION_ERROR')
                fabric = json.dumps(fabric_input)
            else:
                fabric = None
            item.fabric = fabric
        
        if 'care_instructions' in data:
            item.care_instructions = data['care_instructions']
        if 'size' in data:
            item.size = data['size']
        if 'description' in data:
            item.description = data['description']
        
        item.save()
        
        result = item.to_dict()
        # Convert image_path to absolute URL for frontend
        if result.get('image_path'):
            from shared.url_utils import to_absolute_url
            result['image_url'] = to_absolute_url(result['image_path'])
        
        logger.info(f"update_wardrobe_item: EXIT - Item updated")
        return success_response(data=result)
        
    except Exception as e:
        logger.exception(f"update_wardrobe_item: EXIT - Error: {str(e)}")
        return error_response_from_string(f'Server error: {str(e)}', 500)


@wardrobe_bp.route('/items/<int:item_id>', methods=['DELETE'])
@require_auth  # JWT decorator validates token and sets request.user_id from token
def delete_wardrobe_item(item_id: int):
    """
    Delete a wardrobe item
    Uses WardrobeItem model
    user_id is extracted from JWT token by @require_auth decorator
    """
    # user_id comes from JWT token via @require_auth decorator
    user_id = request.user_id
    logger.info(f"delete_wardrobe_item: ENTRY - item_id={item_id}, user_id={user_id} (from JWT)")
    
    try:
        item = WardrobeItem.get_by_id(item_id, user_id)
        if not item:
            return error_response_from_string('Wardrobe item not found', 404, 'NOT_FOUND')
        
        # Delete image from storage if needed
        if item.image_path:
            try:
                storage_service = get_storage_service()
                # Extract path from URL
                if item.image_path.startswith('/images/'):
                    path = item.image_path.replace('/images/', '')
                    storage_service.delete_image(path)
            except Exception as e:
                logger.warning(f"delete_wardrobe_item: Failed to delete image: {str(e)}")
        
        item.delete()
        
        logger.info(f"delete_wardrobe_item: EXIT - Item deleted")
        return success_response(data={'message': 'Wardrobe item deleted successfully'})
        
    except Exception as e:
        logger.exception(f"delete_wardrobe_item: EXIT - Error: {str(e)}")
        return error_response_from_string(f'Server error: {str(e)}', 500)


# ===== GARMENT EXTRACTION FROM URL =====

@wardrobe_bp.route('/extract-from-url', methods=['POST'])
@require_auth  # JWT decorator validates token and sets request.user_id from token
def extract_garment_from_url():
    """
    Extract garment information and images from URL
    Uses brand-specific extractors (Abstract Factory pattern)
    Returns product info and images for frontend
    user_id is extracted from JWT token by @require_auth decorator
    """
    # user_id comes from JWT token via @require_auth decorator
    user_id = request.user_id
    logger.info(f"extract_garment_from_url: ENTRY - user_id={user_id} (from JWT)")
    
    try:
        data = request.get_json() or request.form
        url = validate_url(data.get('url', '').strip())
        
        # Check cache first
        from shared.database import db_manager
        cached = db_manager.execute_query(
            "SELECT * FROM garment_metadata WHERE url = ?",
            (url,),
            fetch_one=True
        )
        
        if cached:
            cached_dict = dict(cached)
            if cached_dict.get('images'):
                cached_dict['images'] = json.loads(cached_dict['images'])
            if cached_dict.get('sizes'):
                cached_dict['sizes'] = json.loads(cached_dict['sizes'])
            if cached_dict.get('colors'):
                cached_dict['colors'] = json.loads(cached_dict['colors'])
            logger.info(f"extract_garment_from_url: EXIT - Returning cached data")
            return success_response(data=cached_dict)
        
        # Use brand-specific extractor
        extractor = BrandExtractorFactory.get_extractor(url)
        product_info = extractor.extract_product_info(url)
        
        # Auto-categorize
        categorization = categorize_garment(title=product_info.get('title'))
        product_info['category'] = categorization['category']
        product_info['type'] = categorization['type']
        product_info['confidence'] = categorization['confidence']
        
        # Cache the result
        try:
            db_manager.get_lastrowid(
                """INSERT INTO garment_metadata (url, title, price, images, sizes, colors, brand)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (url, product_info.get('title'), product_info.get('price'),
                 json.dumps(product_info.get('images', [])),
                 json.dumps(product_info.get('sizes', [])),
                 json.dumps(product_info.get('colors', [])),
                 product_info.get('brand'))
            )
        except Exception as e:
            logger.warning(f"extract_garment_from_url: Failed to cache: {str(e)}")
        
        logger.info(f"extract_garment_from_url: EXIT - Success, extracted {len(product_info.get('images', []))} images")
        return success_response(data=product_info)
        
    except ValidationError as e:
        logger.exception(f"extract_garment_from_url: EXIT - ValidationError: {str(e)}")
        return error_response_from_string(str(e), 400, 'VALIDATION_ERROR')
    except Exception as e:
        logger.exception(f"extract_garment_from_url: EXIT - Error: {str(e)}")
        return error_response_from_string(f'Server error: {str(e)}', 500)

