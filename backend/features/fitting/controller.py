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

