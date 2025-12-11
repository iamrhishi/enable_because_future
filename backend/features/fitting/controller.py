"""
Fitting and sizing API endpoints
Uses BodyMeasurements model for data operations
JWT authentication via @require_auth decorator extracts user_id from token
"""

from flask import Blueprint, request
import json
from features.body_measurements.model import BodyMeasurements
from shared.database import db_manager
from shared.response import success_response, error_response_from_string
from shared.middleware import require_auth
from shared.logger import logger

fitting_bp = Blueprint('fitting', __name__, url_prefix='/api/fitting')


def calculate_fit(user_measurements: dict, garment_size_chart: dict, size: str) -> dict:
    """
    Calculate if garment fits user
    
    Returns:
        dict with fits, recommended_size, fit_analysis, areas, reasoning
    """
    if not user_measurements or not garment_size_chart:
        return {
            'fits': False,
            'recommended_size': None,
            'fit_analysis': {},
            'areas': [],
            'reasoning': 'Missing measurements or size chart'
        }
    
    # Parse size chart if it's a JSON string
    if isinstance(garment_size_chart, str):
        try:
            garment_size_chart = json.loads(garment_size_chart)
        except:
            garment_size_chart = {}
    
    # Get size measurements
    size_measurements = garment_size_chart.get(size, {})
    if not size_measurements:
        return {
            'fits': False,
            'recommended_size': None,
            'fit_analysis': {},
            'areas': [],
            'reasoning': f'Size {size} not found in size chart'
        }
    
    # Compare measurements
    fit_analysis = {}
    areas = []
    fits = True
    
    # Check chest/chest
    if 'chest' in user_measurements and 'chest' in size_measurements:
        user_chest = float(user_measurements['chest'])
        garment_chest = float(size_measurements['chest'])
        diff = garment_chest - user_chest
        fit_analysis['chest'] = {
            'user': user_chest,
            'garment': garment_chest,
            'difference': diff,
            'fits': -2 <= diff <= 5  # Allow 2cm smaller to 5cm larger
        }
        if not fit_analysis['chest']['fits']:
            fits = False
            areas.append('chest')
    
    # Check waist
    if 'waist' in user_measurements and 'waist' in size_measurements:
        user_waist = float(user_measurements['waist'])
        garment_waist = float(size_measurements['waist'])
        diff = garment_waist - user_waist
        fit_analysis['waist'] = {
            'user': user_waist,
            'garment': garment_waist,
            'difference': diff,
            'fits': -2 <= diff <= 5
        }
        if not fit_analysis['waist']['fits']:
            fits = False
            areas.append('waist')
    
    # Check hips
    if 'hips' in user_measurements and 'hips' in size_measurements:
        user_hips = float(user_measurements['hips'])
        garment_hips = float(size_measurements['hips'])
        diff = garment_hips - user_hips
        fit_analysis['hips'] = {
            'user': user_hips,
            'garment': garment_hips,
            'difference': diff,
            'fits': -2 <= diff <= 5
        }
        if not fit_analysis['hips']['fits']:
            fits = False
            areas.append('hips')
    
    # Find recommended size
    recommended_size = size
    if not fits and garment_size_chart:
        # Try to find better fitting size
        best_size = None
        best_score = float('inf')
        
        for sz, measurements in garment_size_chart.items():
            score = 0
            if 'chest' in user_measurements and 'chest' in measurements:
                score += abs(float(measurements['chest']) - float(user_measurements['chest']))
            if 'waist' in user_measurements and 'waist' in measurements:
                score += abs(float(measurements['waist']) - float(user_measurements['waist']))
            if 'hips' in user_measurements and 'hips' in measurements:
                score += abs(float(measurements['hips']) - float(user_measurements['hips']))
            
            if score < best_score:
                best_score = score
                best_size = sz
        
        if best_size:
            recommended_size = best_size
    
    reasoning = f"Size {size} {'fits' if fits else 'does not fit'} based on measurements"
    if areas:
        reasoning += f". Issues in: {', '.join(areas)}"
    if recommended_size != size:
        reasoning += f". Recommended size: {recommended_size}"
    
    return {
        'fits': fits,
        'recommended_size': recommended_size,
        'fit_analysis': fit_analysis,
        'areas': areas,
        'reasoning': reasoning
    }


@fitting_bp.route('/check', methods=['POST'])
@require_auth  # JWT decorator validates token and sets request.user_id from token
def check_fit():
    """
    Check if garment fits user
    Uses BodyMeasurements model
    user_id is extracted from JWT token by @require_auth decorator
    """
    # user_id comes from JWT token via @require_auth decorator
    user_id = request.user_id
    logger.info(f"check_fit: ENTRY - user_id={user_id} (from JWT)")
    
    try:
        data = request.get_json()
        if not data:
            return error_response_from_string('No data provided', 400, 'VALIDATION_ERROR')
        
        # Get user measurements using BodyMeasurements model
        measurements_obj = BodyMeasurements.get_by_user(user_id)
        if not measurements_obj:
            logger.warning(f"check_fit: Body measurements not found for user_id={user_id}")
            return error_response_from_string('Body measurements not found. Please add measurements first.', 404, 'NOT_FOUND')
        
        measurements = measurements_obj.to_dict()
        
        # Get garment size chart
        garment_id = data.get('garment_id')
        size = data.get('size', 'M')
        size_chart = data.get('size_chart')
        
        if not size_chart:
            # Try to get from garment_metadata
            if garment_id:
                garment = db_manager.execute_query(
                    "SELECT size_chart FROM garment_metadata WHERE url LIKE ?",
                    (f'%{garment_id}%',),
                    fetch_one=True
                )
                if garment and garment.get('size_chart'):
                    size_chart = garment['size_chart']
        
        if not size_chart:
            return error_response_from_string('Size chart not provided', 400, 'VALIDATION_ERROR')
        
        # Calculate fit
        fit_result = calculate_fit(measurements, size_chart, size)
        
        logger.info(f"check_fit: EXIT - Fit calculated for user_id={user_id}")
        return success_response(data=fit_result)
        
    except Exception as e:
        logger.exception(f"check_fit: EXIT - Error: {str(e)}")
        return error_response_from_string(f'Server error: {str(e)}', 500)


@fitting_bp.route('/size-recommendation', methods=['GET'])
@require_auth  # JWT decorator validates token and sets request.user_id from token
def get_size_recommendation():
    """
    Get size recommendation for user
    Uses BodyMeasurements model
    user_id is extracted from JWT token by @require_auth decorator
    """
    # user_id comes from JWT token via @require_auth decorator
    user_id = request.user_id
    logger.info(f"get_size_recommendation: ENTRY - user_id={user_id} (from JWT)")
    
    try:
        # Get user measurements using BodyMeasurements model
        measurements_obj = BodyMeasurements.get_by_user(user_id)
        if not measurements_obj:
            logger.warning(f"get_size_recommendation: Body measurements not found for user_id={user_id}")
            return error_response_from_string('Body measurements not found', 404, 'NOT_FOUND')
        
        measurements = measurements_obj.to_dict()
        
        # Get garment info from query params
        garment_id = request.args.get('garment_id')
        size_chart_str = request.args.get('size_chart')
        brand = request.args.get('brand', '')
        
        if not size_chart_str:
            return error_response_from_string('size_chart parameter required', 400, 'VALIDATION_ERROR')
        
        try:
            size_chart = json.loads(size_chart_str)
        except Exception as e:
            logger.warning(f"get_size_recommendation: Invalid size_chart format: {str(e)}")
            return error_response_from_string('Invalid size_chart format', 400, 'VALIDATION_ERROR')
        
        # Find best matching size
        best_size = None
        best_score = float('inf')
        confidence = 0.0
        
        for size, size_measurements in size_chart.items():
            score = 0
            count = 0
            
            if 'chest' in measurements and 'chest' in size_measurements:
                diff = abs(float(size_measurements['chest']) - float(measurements['chest']))
                score += diff
                count += 1
            
            if 'waist' in measurements and 'waist' in size_measurements:
                diff = abs(float(size_measurements['waist']) - float(measurements['waist']))
                score += diff
                count += 1
            
            if 'hips' in measurements and 'hips' in size_measurements:
                diff = abs(float(size_measurements['hips']) - float(measurements['hips']))
                score += diff
                count += 1
            
            if count > 0:
                avg_score = score / count
                if avg_score < best_score:
                    best_score = avg_score
                    best_size = size
        
        # Calculate confidence (lower score = higher confidence)
        if best_score < 2:
            confidence = 0.9
        elif best_score < 5:
            confidence = 0.7
        elif best_score < 10:
            confidence = 0.5
        else:
            confidence = 0.3
        
        reasoning = f"Based on your measurements, size {best_size} is recommended"
        if brand:
            reasoning += f" for {brand}"
        
        logger.info(f"get_size_recommendation: EXIT - Recommended size {best_size} for user_id={user_id}")
        return success_response(data={
            'recommended_size': best_size,
            'confidence': confidence,
            'reasoning': reasoning
        })
        
    except Exception as e:
        logger.exception(f"get_size_recommendation: EXIT - Error: {str(e)}")
        return error_response_from_string(f'Server error: {str(e)}', 500)


@fitting_bp.route('/analyze-fit', methods=['POST'])
@require_auth  # JWT decorator validates token and sets request.user_id from token
def analyze_fit():
    """
    Intelligent fit analysis using Gemini AI
    Analyzes fit based on user measurements and garment data from database
    Uses prompt engineering for comprehensive fit prediction
    
    Request body:
    {
        "wardrobe_item_id": 123,  // ID of wardrobe item (if garment is in user's wardrobe)
        OR
        "garment_url": "https://www.zara.com/...",  // URL of external product
        "size": "M"  // Optional, defaults to user's typical size or garment's size
    }
    
    Returns:
    {
        "fit_percentage": 60,
        "fit_level": "risky fit",
        "fits": false,
        "recommended_size": "M",
        "warnings": ["This item might be wide around the waist"],
        "fit_analysis": {
            "M": {
                "waist": "wide",
                "hips": "perfect",
                "thighs": "tight",
                "length": "short; 8cm over ankle"
            }
        },
        "reasoning": "Detailed explanation of fit prediction"
    }
    """
    # user_id comes from JWT token via @require_auth decorator
    user_id = request.user_id
    logger.info(f"analyze_fit: ENTRY - user_id={user_id} (from JWT)")
    
    try:
        data = request.get_json()
        if not data:
            return error_response_from_string('No data provided', 400, 'VALIDATION_ERROR')
        
        # Get user measurements using BodyMeasurements model
        measurements_obj = BodyMeasurements.get_by_user(user_id)
        if not measurements_obj:
            logger.warning(f"analyze_fit: Body measurements not found for user_id={user_id}")
            return error_response_from_string('Body measurements not found. Please add measurements first.', 404, 'NOT_FOUND')
        
        measurements = measurements_obj.to_dict()
        
        # Get garment data from database
        wardrobe_item_id = data.get('wardrobe_item_id')
        garment_url = data.get('garment_url')
        size = data.get('size', 'M')
        
        garment_details = {}
        size_chart = None
        scraped_fit_info = ''
        
        # Fetch from wardrobe if wardrobe_item_id provided
        if wardrobe_item_id:
            from features.wardrobe.model import WardrobeItem
            wardrobe_item = WardrobeItem.get_by_id(int(wardrobe_item_id), user_id)
            if not wardrobe_item:
                return error_response_from_string(
                    f'Wardrobe item {wardrobe_item_id} not found or does not belong to user',
                    404,
                    'NOT_FOUND'
                )
            
            # Build garment_details from wardrobe item
            garment_details = {
                'brand': wardrobe_item.brand,
                'category': wardrobe_item.category,
                'title': wardrobe_item.title,
                'color': wardrobe_item.color,
                'garment_category_type': wardrobe_item.garment_category_type,
            }
            
            # Parse fabric if available
            if wardrobe_item.fabric:
                try:
                    fabric_data = json.loads(wardrobe_item.fabric) if isinstance(wardrobe_item.fabric, str) else wardrobe_item.fabric
                    garment_details['fabric'] = fabric_data
                except:
                    pass
            
            # Use wardrobe item size if size not provided
            if not size and wardrobe_item.size:
                size = wardrobe_item.size
            
            # Try to get size chart from garment_metadata if this is an external product
            if wardrobe_item.is_external and wardrobe_item.title:
                # Try to find in garment_metadata by title/brand
                metadata = db_manager.execute_query(
                    "SELECT size_chart FROM garment_metadata WHERE title LIKE ? OR brand = ?",
                    (f'%{wardrobe_item.title}%', wardrobe_item.brand or ''),
                    fetch_one=True
                )
                if metadata and metadata.get('size_chart'):
                    try:
                        size_chart = json.loads(metadata['size_chart']) if isinstance(metadata['size_chart'], str) else metadata['size_chart']
                    except:
                        pass
        
        # Fetch from garment_metadata if garment_url provided
        elif garment_url:
            metadata = db_manager.execute_query(
                "SELECT * FROM garment_metadata WHERE url = ?",
                (garment_url,),
                fetch_one=True
            )
            
            if metadata:
                metadata_dict = dict(metadata)
                garment_details = {
                    'brand': metadata_dict.get('brand'),
                    'title': metadata_dict.get('title'),
                }
                
                # Parse size chart
                if metadata_dict.get('size_chart'):
                    try:
                        size_chart = json.loads(metadata_dict['size_chart']) if isinstance(metadata_dict['size_chart'], str) else metadata_dict['size_chart']
                    except:
                        pass
            else:
                return error_response_from_string(
                    f'Garment not found. Please scrape the product first using /api/garments/scrape',
                    404,
                    'NOT_FOUND'
                )
        else:
            return error_response_from_string('wardrobe_item_id or garment_url is required', 400, 'VALIDATION_ERROR')
        
        # If no size chart found, we can't do detailed analysis
        if not size_chart:
            logger.warning(f"analyze_fit: No size chart available for garment")
            return error_response_from_string(
                'Size chart not available for this garment. Size chart data is required for fit analysis.',
                400,
                'VALIDATION_ERROR'
            )
        
        # Use Gemini for intelligent fit analysis
        try:
            from config import Config
            import requests
            import base64
            
            if not Config.GEMINI_API_KEY:
                logger.error("analyze_fit: Gemini API key not configured")
                return error_response_from_string(
                    'Fit analysis service is not configured. Please contact support.',
                    503,
                    'SERVICE_UNAVAILABLE'
                )
            
            # Build comprehensive prompt for Gemini
            prompt_parts = [
                "You are an expert fashion fit analyst. Analyze how a garment will fit a user based on their body measurements and the garment's size chart.\n\n",
                "USER BODY MEASUREMENTS (all in cm):\n",
                f"Height: {measurements.get('height', 'N/A')} cm\n",
                f"Weight: {measurements.get('weight', 'N/A')} kg\n",
                f"Chest/Breast: {measurements.get('breast_circumference') or measurements.get('chest', 'N/A')} cm\n",
                f"Waist: {measurements.get('waist_circumference') or measurements.get('waist', 'N/A')} cm\n",
                f"Hips: {measurements.get('hip_circumference') or measurements.get('hips', 'N/A')} cm\n",
                f"Shoulder: {measurements.get('shoulder_circumference', 'N/A')} cm\n",
                f"Arm Length: {measurements.get('arm_length', 'N/A')} cm\n",
                f"Inner Leg Length: {measurements.get('inner_leg_length', 'N/A')} cm\n",
                f"Thigh: {measurements.get('upper_thigh_circumference', 'N/A')} cm\n",
                "\nGARMENT SIZE CHART:\n",
                json.dumps(size_chart, indent=2),
                "\n\nGARMENT DETAILS:\n",
                json.dumps(garment_details, indent=2),
            ]
            
            if scraped_fit_info:
                prompt_parts.append(f"\n\nSCRAPED FIT INFO FROM PRODUCT PAGE:\n{scraped_fit_info}")
            
            prompt_parts.extend([
                "\n\nTASK:",
                f"Analyze how size {size} will fit this user. Provide:",
                "1. Fit percentage (0-100%)",
                "2. Fit level: 'perfect fit', 'good fit', 'risky fit', or 'poor fit'",
                "3. Whether it fits (boolean)",
                "4. Recommended size if different",
                "5. Warnings about potential fit issues (array of strings)",
                "6. Detailed fit analysis for the requested size and 1-2 alternative sizes, describing each body area (waist, hips, thighs, length, chest, etc.)",
                "7. Concise reasoning explaining the fit prediction",
                "\n\nReturn your analysis as a JSON object with this exact structure:",
                '{"fit_percentage": 60, "fit_level": "risky fit", "fits": false, "recommended_size": "M", "warnings": ["This item might be wide around the waist"], "fit_analysis": {"M": {"waist": "wide", "hips": "perfect", "thighs": "tight", "length": "short; 8cm over ankle"}}, "reasoning": "..."}'
            ])
            
            prompt = "".join(prompt_parts)
            
            # Call Gemini API
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{Config.GEMINI_MODEL_NAME}:generateContent"
            
            payload = {
                "contents": [{
                    "parts": [{
                        "text": prompt
                    }]
                }]
            }
            
            headers = {
                "Content-Type": "application/json"
            }
            
            params = {
                "key": Config.GEMINI_API_KEY
            }
            
            response = requests.post(url, json=payload, headers=headers, params=params, timeout=30)
            response.raise_for_status()
            
            result = response.json()
            
            # Extract text from Gemini response
            if 'candidates' in result and len(result['candidates']) > 0:
                candidate = result['candidates'][0]
                if 'content' in candidate and 'parts' in candidate['content']:
                    text_response = candidate['content']['parts'][0].get('text', '')
                    
                    # Try to parse JSON from response
                    try:
                        # Extract JSON from markdown code blocks if present
                        import re
                        json_match = re.search(r'```json\s*(\{.*?\})\s*```', text_response, re.DOTALL)
                        if json_match:
                            text_response = json_match.group(1)
                        else:
                            # Try to find JSON object directly
                            json_match = re.search(r'\{.*\}', text_response, re.DOTALL)
                            if json_match:
                                text_response = json_match.group(0)
                        
                        fit_analysis = json.loads(text_response)
                        
                        # Validate and normalize response
                        result_data = {
                            'fit_percentage': fit_analysis.get('fit_percentage', 50),
                            'fit_level': fit_analysis.get('fit_level', 'risky fit'),
                            'fits': fit_analysis.get('fits', False),
                            'recommended_size': fit_analysis.get('recommended_size', size),
                            'warnings': fit_analysis.get('warnings', []),
                            'fit_analysis': fit_analysis.get('fit_analysis', {}),
                            'reasoning': fit_analysis.get('reasoning', 'Fit analysis completed')
                        }
                        
                        logger.info(f"analyze_fit: EXIT - Fit analysis completed for user_id={user_id}, fit_percentage={result_data['fit_percentage']}")
                        return success_response(data=result_data)
                    except json.JSONDecodeError as e:
                        logger.error(f"analyze_fit: Failed to parse Gemini JSON response: {str(e)}, raw response: {text_response[:500]}")
                        return error_response_from_string(
                            'Unable to analyze fit at this time. The fit analysis service returned an invalid response. Please try again later.',
                            503,
                            'SERVICE_UNAVAILABLE'
                        )
            else:
                logger.error("analyze_fit: No candidates in Gemini response")
                return error_response_from_string(
                    'Unable to analyze fit at this time. The fit analysis service is temporarily unavailable. Please try again later.',
                    503,
                    'SERVICE_UNAVAILABLE'
                )
                
        except requests.exceptions.RequestException as e:
            logger.exception(f"analyze_fit: Gemini API request failed: {str(e)}")
            return error_response_from_string(
                'Unable to analyze fit at this time. The fit analysis service is temporarily unavailable. Please try again later.',
                503,
                'SERVICE_UNAVAILABLE'
            )
        except Exception as e:
            logger.exception(f"analyze_fit: Gemini API error: {str(e)}")
            return error_response_from_string(
                'Unable to analyze fit at this time. An error occurred while processing your request. Please try again later.',
                503,
                'SERVICE_UNAVAILABLE'
            )
        
    except Exception as e:
        logger.exception(f"analyze_fit: EXIT - Error: {str(e)}")
        return error_response_from_string(f'Server error: {str(e)}', 500)



