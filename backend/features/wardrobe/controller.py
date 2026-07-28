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
from shared.response import success_response, error_response_from_string, server_error_response
from shared.middleware import require_auth
from shared.validators import validate_public_url as validate_url
from shared.errors import ValidationError, NotFoundError
from shared.logger import logger
import base64
import json
import time
from io import BytesIO

wardrobe_bp = Blueprint('wardrobe', __name__, url_prefix='/api/wardrobe')


# ===== METADATA & OPTIONS =====

@wardrobe_bp.route('/options', methods=['GET'])
@require_auth  # JWT decorator validates token and sets request.user_id from token
def get_wardrobe_options():
    """
    Get available options for wardrobe item fields
    Returns fabric types and care instructions that frontend can use for dropdowns
    user_id is extracted from JWT token by @require_auth decorator
    """
    # user_id comes from JWT token via @require_auth decorator
    user_id = request.user_id
    logger.info(f"get_wardrobe_options: ENTRY - user_id={user_id} (from JWT)")
    
    try:
        # Available fabric types (based on UI requirements)
        fabric_types = [
            {"name": "cotton", "display_name": "Cotton"},
            {"name": "polyester", "display_name": "Polyester"},
            {"name": "elasthan", "display_name": "Elasthan"},
            {"name": "wool", "display_name": "Wool"},
            {"name": "cashmere", "display_name": "Cashmere"},
            {"name": "viscose", "display_name": "Viscose"},
            {"name": "lyocell", "display_name": "Lyocell"},
            {"name": "silk", "display_name": "Silk"},
            {"name": "other", "display_name": "Other"}
        ]
        
        # Available care instructions (based on UI requirements)
        care_instructions = [
            {"id": "machine_wash_30", "label": "Machine wash at 30°C", "icon": "washing-machine", "category": "washing"},
            {"id": "machine_wash_40", "label": "Machine wash at 40°C", "icon": "washing-machine", "category": "washing"},
            {"id": "machine_wash_60", "label": "Machine wash at 60°C", "icon": "washing-machine", "category": "washing"},
            {"id": "machine_wash_95", "label": "Machine wash at 95°C", "icon": "washing-machine", "category": "washing"},
            {"id": "hand_wash", "label": "Hand wash", "icon": "hand", "category": "washing"},
            {"id": "tumble_dry_low", "label": "Tumble dry at low temp.", "icon": "dryer", "category": "drying"},
            {"id": "tumble_dry_medium", "label": "Tumble dry at medium temp.", "icon": "dryer", "category": "drying"},
            {"id": "tumble_dry_high", "label": "Tumble dry at high temp.", "icon": "dryer", "category": "drying"},
            {"id": "do_not_tumble_dry", "label": "Do not tumble dry", "icon": "dryer", "category": "drying"},
            {"id": "do_not_iron", "label": "Do not iron", "icon": "iron", "category": "ironing"},
            {"id": "do_not_steam", "label": "Do not steam", "icon": "steam", "category": "ironing"},
            {"id": "iron_low", "label": "Iron at low temp.", "icon": "iron", "category": "ironing"},
            {"id": "iron_medium", "label": "Iron at medium temp.", "icon": "iron", "category": "ironing"},
            {"id": "iron_high", "label": "Iron at high temp.", "icon": "iron", "category": "ironing"},
            {"id": "do_not_dry_clean", "label": "Do not dry clean", "icon": "dry-clean", "category": "cleaning"},
            {"id": "do_not_bleach", "label": "Do not bleach", "icon": "bleach", "category": "cleaning"}
        ]
        
        logger.info(f"get_wardrobe_options: EXIT - Returning options for user_id={user_id}")
        return success_response(data={
            'fabric_types': fabric_types,
            'care_instructions': care_instructions
        })
        
    except Exception as e:
        logger.exception(f"get_wardrobe_options: EXIT - Error: {str(e)}")
        return server_error_response(e, context='Server error', status_code=500)


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
        # Handle JSON requests safely
        content_type = request.content_type or ''
        if 'application/json' in content_type:
            data = request.get_json(silent=True, force=False) or {}
        else:
            data = {}
        
        if not data:
            return error_response_from_string('No data provided', 400, 'VALIDATION_ERROR')
        
        name = (data.get('name') or '').strip()
        if not name:
            return error_response_from_string('Category name is required', 400, 'VALIDATION_ERROR')

        # Validate category_section (required)
        category_section = (data.get('category_section') or '').strip()
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
            description=(data.get('description') or '').strip(),
            category_section=category_section
        )
        category.save()
        
        logger.info(f"create_category: EXIT - Category created: {name}")
        return success_response(data=category.to_dict(), status_code=201)
        
    except Exception as e:
        logger.exception(f"create_category: EXIT - Error: {str(e)}")
        return server_error_response(e, context='Server error', status_code=500)


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
        return server_error_response(e, context='Server error', status_code=500)


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
        return server_error_response(e, context='Server error', status_code=500)


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
        # Handle JSON requests safely
        content_type = request.content_type or ''
        if 'application/json' in content_type:
            data = request.get_json(silent=True, force=False) or {}
        else:
            data = {}
        
        if not data:
            return error_response_from_string('No data provided', 400, 'VALIDATION_ERROR')
        
        name = (data.get('name') or '').strip()
        if not name:
            return error_response_from_string('Section name is required', 400, 'VALIDATION_ERROR')

        display_name = (data.get('display_name') or '').strip()
        if not display_name:
            display_name = name  # Use name as display_name if not provided

        description = (data.get('description') or '').strip()
        icon_name = (data.get('icon_name') or '').strip()  # Icon identifier (e.g., 'custom_section_1')
        icon_url = (data.get('icon_url') or '').strip()  # Optional icon URL
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
        return server_error_response(e, context='Server error', status_code=500)


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
        return server_error_response(e, context='Server error', status_code=500)


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
        # Handle JSON requests safely
        content_type = request.content_type or ''
        if 'application/json' in content_type:
            data = request.get_json(silent=True, force=False) or {}
        else:
            data = {}
        
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
        return server_error_response(e, context='Server error', status_code=500)


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
        return server_error_response(e, context='Server error', status_code=500)


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
        
        # Get data from form or JSON (handle both multipart/form-data and application/json)
        # Check content type first to avoid Flask raising 415 error
        content_type = request.content_type or ''
        if 'application/json' in content_type:
            data = request.get_json(silent=True, force=False) or {}
        else:
            data = {}
        form_data = request.form
        
        # Method 1: Direct image upload
        if 'garment_image' in request.files:
            garment_image = request.files['garment_image'].read()
            garment_image = preprocess_image(garment_image, resize=True, normalize=True)
        
        # Method 2: Extract from URL
        elif 'garment_url' in form_data or data.get('garment_url'):
            garment_url = validate_url(
                form_data.get('garment_url') or data.get('garment_url')
            )
            
            # Use brand-specific extractor
            try:
                extractor = BrandExtractorFactory.get_extractor(garment_url)
                product_info = extractor.extract_product_info(garment_url)
            except Exception as e:
                logger.warning(f"add_garment: BrandExtractor failed for URL {garment_url}: {str(e)}")
                product_info = None

            provided_image_url = form_data.get('image_url') or data.get('image_url')
            
            # Fetch first image from extracted images or fallback to provided image_url
            if product_info and product_info.get('images'):
                try:
                    garment_image = fetch_image_from_url(product_info['images'][0])
                    garment_image = preprocess_image(garment_image, resize=True, normalize=True)
                except Exception as e:
                    logger.warning(f"add_garment: Failed to fetch image from extracted URL: {str(e)}")
                    if provided_image_url:
                        try:
                            garment_image = fetch_image_from_url(provided_image_url)
                            garment_image = preprocess_image(garment_image, resize=True, normalize=True)
                        except Exception as ex:
                            return error_response_from_string(f'Failed to fetch image from URL: {str(ex)}', 400, 'VALIDATION_ERROR')
                    else:
                        return error_response_from_string(f'Failed to fetch image from URL: {str(e)}', 400, 'VALIDATION_ERROR')
            elif provided_image_url:
                try:
                    garment_image = fetch_image_from_url(provided_image_url)
                    garment_image = preprocess_image(garment_image, resize=True, normalize=True)
                except Exception as e:
                    return error_response_from_string(f'Failed to fetch provided image_url: {str(e)}', 400, 'VALIDATION_ERROR')
            else:
                return error_response_from_string('No images found in product URL', 400, 'VALIDATION_ERROR')

        # Method 3: Direct image URL
        elif 'image_url' in form_data or data.get('image_url'):
            provided_image_url = form_data.get('image_url') or data.get('image_url')
            try:
                garment_image = fetch_image_from_url(provided_image_url)
                garment_image = preprocess_image(garment_image, resize=True, normalize=True)
            except Exception as e:
                return error_response_from_string(f'Failed to fetch image_url: {str(e)}', 400, 'VALIDATION_ERROR')
        
        if not garment_image:
            return error_response_from_string('garment_image or garment_url required', 400, 'VALIDATION_ERROR')
        
        # Get category information - support both category_section (new) and category (legacy)
        category_section = form_data.get('category_section') or data.get('category_section')
        category = form_data.get('category') or data.get('category')
        custom_category_name = form_data.get('custom_category_name') or data.get('custom_category_name')
        category_id_raw = form_data.get('category_id') or data.get('category_id')
        category_id = None
        if category_id_raw is not None and str(category_id_raw).strip().lower() not in ('null', 'undefined', ''):
            try:
                category_id = int(category_id_raw)
            except (ValueError, TypeError):
                category_id = None
        
        # Validate category_section if provided
        if category_section:
            valid_sections = ['upper_body', 'lower_body', 'accessoires', 'wishlist']
            if category_section not in valid_sections:
                # Check if it's a user-created section
                section = WardrobeCategory.get_section_by_name(category_section, user_id)
                if not section:
                    return error_response_from_string(
                        f'Invalid category_section: {category_section}. Must be one of {valid_sections} or a user-created section.',
                        400,
                        'VALIDATION_ERROR'
                    )
        
        # Map category_section to legacy category if needed
        if category_section and not category:
            # Map new category_section to legacy category
            section_to_category = {
                'upper_body': 'upper',
                'lower_body': 'lower',
                'accessoires': None,  # These don't map to legacy categories
                'wishlist': None
            }
            category = section_to_category.get(category_section)
            # If category_section is not recognized (user-created), default to 'upper'
            if category is None and category_section not in ['accessoires', 'wishlist']:
                category = 'upper'
        
        # Default to 'upper' if no category specified and not using custom category
        if not category and not custom_category_name and not category_section:
            category = 'upper'
        
        # Validate category
        if custom_category_name:
            # Verify custom category exists
            if category_id is not None:
                cat = WardrobeCategory.get_by_id(category_id, user_id)
                if not cat:
                    return error_response_from_string('Category not found', 404, 'NOT_FOUND')
        elif category is not None and category not in ['upper', 'lower']:
            return error_response_from_string('Category must be "upper" or "lower" if not using custom category', 400, 'VALIDATION_ERROR')
        
        # Auto-categorize if not provided
        # User form_data takes priority over scraped product_info
        form_title = (form_data.get('title') or data.get('title') or '').strip()
        scraped_title = (product_info.get('title') or '').strip() if product_info else ''
        title = form_title if form_title else (scraped_title if scraped_title else None)

        if not category or category == 'upper':  # Default categorization
            categorization = categorize_garment(title=title)
            category = categorization['category']
            garment_type = categorization['type']
        else:
            garment_type = form_data.get('garment_type') or data.get('garment_type')
        
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
        elif product_info and product_info.get('fabric'):
            import json
            fabric = json.dumps(product_info.get('fabric'))
        
        # Get care_instructions, size, description, url
        care_instructions = form_data.get('care_instructions') or data.get('care_instructions')
        size = form_data.get('size') or data.get('size')
        description = form_data.get('description') or data.get('description')
        url = form_data.get('url') or data.get('url') or garment_url

        form_brand = (form_data.get('brand') or data.get('brand') or '').strip()
        scraped_brand = (product_info.get('brand') or '').strip() if product_info else ''
        brand = form_brand if form_brand else (scraped_brand if scraped_brand else None)

        form_color = (form_data.get('color') or data.get('color') or '').strip()
        scraped_color = (product_info.get('colors', [None])[0] or '').strip() if product_info and product_info.get('colors') else ''
        color = form_color if form_color else (scraped_color if scraped_color else None)

        # Check for duplicate URL in same category_section
        if url:
            existing_item = WardrobeItem.get_by_url(user_id, url, category_section)
            if existing_item:
                logger.info(f"add_garment: EXIT - Duplicate item found, id={existing_item.id}")
                result = existing_item.to_dict()
                if result.get('image_path'):
                    from shared.url_utils import to_absolute_url
                    result['image_url'] = to_absolute_url(result['image_path'])
                return success_response(
                    data=result,
                    status_code=200,
                    message='Item already exists in your wardrobe'
                )

        # Create wardrobe item
        wardrobe_item = WardrobeItem(
            user_id=user_id,
            image_path=image_url,
            category=category if not custom_category_name else None,
            custom_category_name=custom_category_name,
            category_id=category_id,
            category_section=category_section,
            garment_category_type=garment_type,
            brand=brand,
            color=color,
            is_external=bool(garment_url),
            title=title,
            fabric=fabric,
            care_instructions=care_instructions,
            size=size,
            description=description,
            url=url
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
        return server_error_response(e, context='Server error', status_code=500)


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
        category_id = request.args.get('category_id')  # Platform or user category ID
        category_section = request.args.get('category_section')  # 'upper_body', 'lower_body', 'accessoires', 'wishlist'
        item_id = request.args.get('item_id') or request.args.get('id')  # Support both 'item_id' and 'id'
        search = request.args.get('search', '').strip()
        
        # Get items
        # Parse category_id if provided
        category_id_int = None
        platform_category_name = None
        if category_id:
            try:
                category_id_int = int(category_id)
                # Check if it's a user-created category
                custom_cat = WardrobeCategory.get_by_id(category_id_int, user_id)
                if custom_cat:
                    logger.info(f"get_wardrobe_items: Filtering by user category ID {category_id_int}: {custom_cat.name}")
                else:
                    # Check if it's a platform category
                    from shared.database import db_manager
                    platform_cat = db_manager.execute_query(
                        "SELECT name FROM platform_categories WHERE id = ?",
                        (category_id_int,),
                        fetch_one=True
                    )
                    if platform_cat:
                        platform_category_name = platform_cat['name']
                        logger.info(f"get_wardrobe_items: Filtering by platform category ID {category_id_int}: {platform_category_name}")
                    else:
                        logger.warning(f"get_wardrobe_items: Category ID {category_id_int} not found in platform or user categories - will still filter by category_id")
            except (ValueError, TypeError) as e:
                logger.warning(f"get_wardrobe_items: Invalid category_id: {category_id}, error: {str(e)}")
        
        # Parse item_id if provided
        item_id_int = None
        if item_id:
            try:
                item_id_int = int(item_id)
                logger.info(f"get_wardrobe_items: Filtering by item ID {item_id_int}")
            except (ValueError, TypeError) as e:
                logger.warning(f"get_wardrobe_items: Invalid item_id: {item_id}, error: {str(e)}")
        
        items = WardrobeItem.get_by_user(
            user_id=user_id,
            category=category,
            category_id=category_id_int,
            platform_category_name=platform_category_name,  # For platform categories, also filter by garment_category_type
            item_id=item_id_int,
            category_section=category_section,
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
        return server_error_response(e, context='Server error', status_code=500)


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
        return server_error_response(e, context='Server error', status_code=500)


@wardrobe_bp.route('/items/<int:item_id>', methods=['PUT'])
@require_auth  # JWT decorator validates token and sets request.user_id from token
def update_wardrobe_item(item_id: int):
    """
    Update a wardrobe item
    Supports:
    - JSON requests for updating metadata
    - Multipart/form-data for updating image and/or metadata
    Uses WardrobeItem model
    user_id is extracted from JWT token by @require_auth decorator
    """
    # user_id comes from JWT token via @require_auth decorator
    user_id = request.user_id
    logger.info(f"update_wardrobe_item: ENTRY - item_id={item_id}, user_id={user_id} (from JWT)")
    
    try:
        # Get item first to check if it exists
        item = WardrobeItem.get_by_id(item_id, user_id)
        if not item:
            return error_response_from_string('Wardrobe item not found', 404, 'NOT_FOUND')
        
        # Handle both JSON and multipart/form-data requests
        content_type = request.content_type or ''
        if 'application/json' in content_type:
            data = request.get_json(silent=True, force=False) or {}
        else:
            data = {}
        form_data = request.form
        
        # Check if we have any data to update
        has_data = bool(data) or bool(form_data) or 'garment_image' in request.files
        if not has_data:
            return error_response_from_string('No data provided', 400, 'VALIDATION_ERROR')
        
        # Handle image upload if provided (multipart/form-data)
        if 'garment_image' in request.files:
            garment_file = request.files['garment_image']
            if garment_file and garment_file.filename:
                try:
                    garment_image = garment_file.read()
                    garment_image = preprocess_image(garment_image, resize=True, normalize=True)
                    
                    # Generate new storage path (keep same garment_id if exists, or generate new)
                    import uuid
                    import os
                    if item.image_path:
                        # Extract garment_id from existing path or generate new
                        existing_path = item.image_path
                        # Path format: wardrobe/{user_id}/{garment_id}.png
                        if '/wardrobe/' in existing_path:
                            garment_id = os.path.splitext(os.path.basename(existing_path))[0]
                        else:
                            garment_id = str(uuid.uuid4())
                    else:
                        garment_id = str(uuid.uuid4())
                    
                    storage_path = f"wardrobe/{user_id}/{garment_id}.png"
                    
                    storage_service = get_storage_service()
                    image_url = storage_service.upload_image(
                        garment_image,
                        storage_path,
                        content_type='image/png'
                    )
                    
                    item.image_path = image_url
                    logger.info(f"update_wardrobe_item: Image updated for item {item_id}")
                except Exception as e:
                    logger.exception(f"update_wardrobe_item: Error processing image: {str(e)}")
                    return error_response_from_string(f'Error processing image: {str(e)}', 400, 'VALIDATION_ERROR')
        
        # Update fields from form_data or data (form_data takes precedence for multipart)
        if 'category' in form_data or 'category' in data:
            item.category = form_data.get('category') or data.get('category')
        if 'custom_category_name' in form_data or 'custom_category_name' in data:
            item.custom_category_name = form_data.get('custom_category_name') or data.get('custom_category_name')
        if 'category_id' in form_data or 'category_id' in data:
            category_id_val = form_data.get('category_id') or data.get('category_id')
            if category_id_val:
                try:
                    item.category_id = int(category_id_val)
                except (ValueError, TypeError):
                    return error_response_from_string('Invalid category_id', 400, 'VALIDATION_ERROR')
        if 'category_section' in form_data or 'category_section' in data:
            new_section = form_data.get('category_section') or data.get('category_section')
            # Validate category_section
            if new_section:
                valid_sections = ['upper_body', 'lower_body', 'accessoires', 'wishlist']
                if new_section not in valid_sections:
                    # Check if it's a user-created section
                    section = WardrobeCategory.get_section_by_name(new_section, user_id)
                    if not section:
                        return error_response_from_string(
                            f'Invalid category_section: {new_section}. Must be one of {valid_sections} or a user-created section.',
                            400,
                            'VALIDATION_ERROR'
                        )
            item.category_section = new_section
        if 'garment_category_type' in form_data or 'garment_category_type' in data:
            item.garment_category_type = form_data.get('garment_category_type') or data.get('garment_category_type')
        if 'brand' in form_data or 'brand' in data:
            item.brand = form_data.get('brand') or data.get('brand')
        if 'color' in form_data or 'color' in data:
            item.color = form_data.get('color') or data.get('color')
        if 'title' in form_data or 'title' in data:
            item.title = form_data.get('title') or data.get('title')
        
        # Update new fields with validation
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
            else:
                fabric = None
            item.fabric = fabric
        
        if 'care_instructions' in form_data or 'care_instructions' in data:
            item.care_instructions = form_data.get('care_instructions') or data.get('care_instructions')
        if 'size' in form_data or 'size' in data:
            item.size = form_data.get('size') or data.get('size')
        if 'description' in form_data or 'description' in data:
            item.description = form_data.get('description') or data.get('description')
        if 'url' in form_data or 'url' in data:
            item.url = form_data.get('url') or data.get('url')

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
        return server_error_response(e, context='Server error', status_code=500)


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
        return server_error_response(e, context='Server error', status_code=500)


@wardrobe_bp.route('/wishlist/<int:item_id>', methods=['DELETE'])
@require_auth
def remove_from_wishlist(item_id: int):
    """
    Remove an item from wishlist (deletes the item completely).

    For moving item to wardrobe instead of deleting, use PUT /items/<id>
    with category_section='upper_body' or 'lower_body'.
    """
    user_id = request.user_id
    logger.info(f"remove_from_wishlist: ENTRY - item_id={item_id}, user_id={user_id}")

    try:
        item = WardrobeItem.get_by_id(item_id, user_id)
        if not item:
            return error_response_from_string('Wishlist item not found', 404, 'NOT_FOUND')

        # Verify it's actually in wishlist
        if item.category_section != 'wishlist':
            return error_response_from_string(
                'Item is not in wishlist',
                400,
                'INVALID_OPERATION'
            )

        # Delete image from storage if needed
        if item.image_path:
            try:
                storage_service = get_storage_service()
                if item.image_path.startswith('/images/'):
                    path = item.image_path.replace('/images/', '')
                    storage_service.delete_image(path)
            except Exception as e:
                logger.warning(f"remove_from_wishlist: Failed to delete image: {str(e)}")

        item.delete()

        logger.info(f"remove_from_wishlist: EXIT - Item removed from wishlist")
        return success_response(data={'message': 'Item removed from wishlist'})

    except Exception as e:
        logger.exception(f"remove_from_wishlist: EXIT - Error: {str(e)}")
        return server_error_response(e, context='Server error', status_code=500)


@wardrobe_bp.route('/wishlist/<int:item_id>/move-to-wardrobe', methods=['POST'])
@require_auth
def move_from_wishlist_to_wardrobe(item_id: int):
    """
    Move an item from wishlist to wardrobe (changes category_section).

    Optional body params:
    - category_section: 'upper_body' or 'lower_body' (default: auto-detect from garment type)
    """
    user_id = request.user_id
    logger.info(f"move_from_wishlist_to_wardrobe: ENTRY - item_id={item_id}, user_id={user_id}")

    try:
        item = WardrobeItem.get_by_id(item_id, user_id)
        if not item:
            return error_response_from_string('Wishlist item not found', 404, 'NOT_FOUND')

        # Verify it's actually in wishlist
        if item.category_section != 'wishlist':
            return error_response_from_string(
                'Item is not in wishlist',
                400,
                'INVALID_OPERATION'
            )

        # Get target section from request or auto-detect
        data = request.get_json(silent=True) or {}
        target_section = data.get('category_section')

        if not target_section:
            # Auto-detect from garment type or category
            if item.category == 'lower' or item.garment_category_type in ['pants', 'jeans', 'shorts', 'skirt', 'trousers']:
                target_section = 'lower_body'
            else:
                target_section = 'upper_body'

        # Validate target section
        if target_section not in ['upper_body', 'lower_body', 'accessoires']:
            return error_response_from_string(
                'Invalid category_section. Use upper_body, lower_body, or accessoires',
                400,
                'VALIDATION_ERROR'
            )

        # Update item
        item.category_section = target_section
        if target_section == 'upper_body':
            item.category = 'upper'
        elif target_section == 'lower_body':
            item.category = 'lower'

        item.save()

        logger.info(f"move_from_wishlist_to_wardrobe: EXIT - Moved to {target_section}")
        return success_response(data={
            'message': f'Item moved to {target_section}',
            'item': item.to_dict()
        })

    except Exception as e:
        logger.exception(f"move_from_wishlist_to_wardrobe: EXIT - Error: {str(e)}")
        return server_error_response(e, context='Server error', status_code=500)


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
        url = validate_url((data.get('url') or '').strip())
        
        # Check cache first
        from shared.database import db_manager
        cached = db_manager.execute_query(
            "SELECT * FROM garment_metadata WHERE url = ?",
            (url,),
            fetch_one=True
        )
        
        if cached:
            # Safely convert cached row to dict, filtering out non-serializable values
            import json
            cached_dict = {}
            for k, v in dict(cached).items():
                if isinstance(v, bytes):
                    continue
                try:
                    json.dumps(v)
                    cached_dict[k] = v
                except (TypeError, ValueError):
                    if hasattr(v, 'isoformat'):
                        cached_dict[k] = v.isoformat()
                    else:
                        continue
            if cached_dict.get('images'):
                cached_dict['images'] = json.loads(cached_dict['images'])
            if cached_dict.get('sizes'):
                cached_dict['sizes'] = json.loads(cached_dict['sizes'])
            if cached_dict.get('colors'):
                cached_dict['colors'] = json.loads(cached_dict['colors'])
            if cached_dict.get('fabric'):
                cached_dict['fabric'] = json.loads(cached_dict['fabric'])
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
                """INSERT INTO garment_metadata (url, title, price, images, sizes, colors, brand, fabric)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (url, product_info.get('title'), product_info.get('price'),
                 json.dumps(product_info.get('images', [])),
                 json.dumps(product_info.get('sizes', [])),
                 json.dumps(product_info.get('colors', [])),
                 product_info.get('brand'),
                 json.dumps(product_info.get('fabric')) if product_info.get('fabric') else None)
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
        return server_error_response(e, context='Server error', status_code=500)


# ===== EXTENSION SPECIFIC ENDPOINTS =====

@wardrobe_bp.route('/save-extracted', methods=['POST'])
@require_auth  # JWT decorator validates token and sets request.user_id from token
def save_extracted_garment():
    """
    Save a garment extracted from web pages directly to wardrobe
    Specifically designed for Chrome extension use
    Accepts base64 image data without URL validation
    Saves image as base64 in description field (or could be stored as file)
    
    Request JSON:
    {
        "garment_image": "data:image/jpeg;base64,...",  # Data URL or base64 string
        "garment_type": "upper" or "lower",
        "garment_id": "optional_unique_id"
    }
    """
    user_id = request.user_id
    logger.info(f"save_extracted_garment: ENTRY - user_id={user_id}")
    
    try:
        data = request.get_json(silent=True) or {}
        
        # Validate required fields
        garment_image_data = data.get('garment_image')
        garment_type = data.get('garment_type', 'upper').lower()
        garment_id = data.get('garment_id', f'extracted_{user_id}_{int(time.time() * 1000)}')
        
        if not garment_image_data:
            logger.warning("save_extracted_garment: Missing garment_image")
            return error_response_from_string('garment_image is required', 400, 'VALIDATION_ERROR')
        
        # Validate garment type
        if garment_type not in ['upper', 'lower']:
            logger.warning(f"save_extracted_garment: Invalid garment_type: {garment_type}")
            return error_response_from_string('garment_type must be "upper" or "lower"', 400, 'VALIDATION_ERROR')
        
        # Convert data URL to base64 if needed
        if garment_image_data.startswith('data:'):
            # Extract base64 part from data URL
            try:
                base64_str = garment_image_data.split(',')[1]
                garment_image_bytes = base64.b64decode(base64_str)
            except (IndexError, ValueError) as e:
                logger.warning(f"save_extracted_garment: Invalid data URL format: {str(e)}")
                return error_response_from_string('Invalid image data URL format', 400, 'VALIDATION_ERROR')
        else:
            # Assume it's already base64
            try:
                garment_image_bytes = base64.b64decode(garment_image_data)
            except ValueError as e:
                logger.warning(f"save_extracted_garment: Invalid base64 string: {str(e)}")
                return error_response_from_string('Invalid base64 image data', 400, 'VALIDATION_ERROR')
        
        # Validate and preprocess image
        try:
            garment_image = preprocess_image(garment_image_bytes, resize=True, normalize=True)
        except Exception as e:
            logger.warning(f"save_extracted_garment: Image validation failed: {str(e)}")
            return error_response_from_string(f'Invalid image: {str(e)}', 400, 'VALIDATION_ERROR')
        
        # Save image to storage and get the path
        try:
            image_path = get_storage_service().save_garment_image(garment_image, user_id, garment_id)
            logger.info(f"save_extracted_garment: Image saved to {image_path}")
        except Exception as e:
            logger.warning(f"save_extracted_garment: Failed to save image: {str(e)}")
            return error_response_from_string(f'Failed to save image: {str(e)}', 400, 'VALIDATION_ERROR')
        
        # Create wardrobe item using the WardrobeItem model
        # The model uses image_path (file path) instead of garment_image (BLOB)
        wardrobe_item = WardrobeItem(
            user_id=user_id,
            image_path=image_path,
            category=garment_type,  # 'upper' or 'lower'
            is_external=False,  # Not from external URL
            title=f"Extracted Garment - {garment_type.capitalize()}",
            description=f"Extracted from web page on {time.strftime('%Y-%m-%d %H:%M:%S')}"
        )
        
        # Save to database
        wardrobe_item.save()
        
        logger.info(f"save_extracted_garment: EXIT - Successfully saved garment {garment_id} to wardrobe for user {user_id}")
        
        return success_response(
            data={
                'id': wardrobe_item.id,
                'image_path': wardrobe_item.image_path,
                'category': wardrobe_item.category,
                'title': wardrobe_item.title
            },
            message='Garment saved to wardrobe successfully'
        )
        
    except Exception as e:
        logger.exception(f"save_extracted_garment: EXIT - Error: {str(e)}")
        return server_error_response(e, context='Failed to save garment', status_code=500)


# ===== SEARCH =====

@wardrobe_bp.route('/search', methods=['GET'])
@require_auth
def search_garments():
    """
    Search/extract garment info for try-on.

    Query params:
        url: Product URL to extract info from (optional)
        gender: Filter default garments by gender (optional)
        category: Filter by 'top' or 'bottom' (optional)

    Behavior:
        - If URL provided: Extract product info from URL
        - If no URL: Return default garments catalog

    Returns items with:
        garmentURL, name, brand, imageURL, category, isRecent
    """
    url = request.args.get('url', '').strip()
    gender = request.args.get('gender', '').strip()
    category_filter = request.args.get('category', '').strip().lower()

    logger.info(f"search_garments: ENTRY - url={url[:50] if url else 'none'}, gender={gender}")

    try:
        results = []

        if url:
            # Extract product info from URL
            from shared.validators import validate_public_url as validate_url
            validated_url = validate_url(url)

            extractor = BrandExtractorFactory.get_extractor(validated_url)
            product_info = extractor.extract_product_info(validated_url)

            # Get first image URL
            image_url = product_info.get('images', [None])[0] if product_info.get('images') else None

            # Determine category from title
            title = product_info.get('title', '')
            categorization = categorize_garment(title=title)
            cat = categorization.get('category', 'upper')
            category = 'top' if cat == 'upper' else 'bottom'

            results.append({
                'garmentURL': validated_url,
                'name': product_info.get('title'),
                'brand': product_info.get('brand'),
                'imageURL': image_url,
                'category': category,
                'fabric': product_info.get('fabric'),
                'isRecent': False
            })

            logger.info(f"search_garments: EXIT - Extracted product from URL")
        else:
            # Return default garments
            from shared.default_garments import get_default_garments

            default_garments = get_default_garments(gender if gender else None)

            for g in default_garments:
                # Normalize category
                cat = g.get('category', '').lower()
                if cat in ['upper', 'top', 'shirt', 'jacket', 'sweater', 'blouse', 'coat', 'outerwear']:
                    category = 'top'
                elif cat in ['lower', 'bottom', 'pants', 'skirt', 'shorts', 'jeans']:
                    category = 'bottom'
                else:
                    category = cat or 'top'

                # Apply category filter if provided
                if category_filter and category != category_filter:
                    continue

                results.append({
                    'garmentURL': g.get('url'),
                    'name': g.get('name'),
                    'brand': g.get('brand'),
                    'imageURL': g.get('imageURL') or g.get('image_url'),
                    'category': category,
                    'isRecent': False
                })

            logger.info(f"search_garments: EXIT - Returned {len(results)} default garments")

        return success_response(data=results)

    except Exception as e:
        logger.exception(f"search_garments: EXIT - Error: {str(e)}")
        return server_error_response(e, context='Search failed', status_code=500)
