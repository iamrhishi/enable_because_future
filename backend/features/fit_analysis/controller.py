"""
Fit Analysis Controller
REST API endpoints for garment fit analysis
"""

from flask import Blueprint, request, jsonify
import logging
from shared.middleware import require_auth
from shared.errors import ValidationError, NotFoundError, BecauseFutureError
from features.body_measurements.model import BodyMeasurements
from .service import FitAnalysisService
from shared.logger import logger

# Create blueprint
fit_analysis_bp = Blueprint('fit_analysis', __name__, url_prefix='/api')


@fit_analysis_bp.route('/fit-analysis', methods=['POST'])
@require_auth
def analyze_fit():
    """
    Analyze garment fit against body measurements
    
    Request body:
    {
        "garment_type": "upper" or "lower",
        "garment_measurements": {
            "breast_width": 50,
            "arm_length": 65,
            ...
        },
        "garment_size": "M"  (for reference)
    }
    
    Response:
    {
        "garment_type": "upper",
        "overall_fit": "good fit" or "bad fit",
        "good_fits": 4,
        "bad_fits": 2,
        "garment_size": "M",
        "measurements": [
            {
                "metric": "breast_width",
                "body_value": 48.5,
                "garment_value": 50,
                "fit_status": "good fit",
                "difference": -1.5
            },
            ...
        ]
    }
    """
    try:
        # user_id is extracted from JWT token by @require_auth decorator
        user_id = request.user_id
        logger.info(f"FitAnalysis: POST /fit-analysis ENTRY - user_id={user_id}")
        
        # Parse request
        data = request.get_json()
        if not data:
            logger.warning("FitAnalysis: Missing request body")
            raise ValidationError("Request body is required")
        
        logger.info(f"FitAnalysis: Request data received: {data}")
        
        # Validate required fields
        garment_type = data.get('garment_type', '').lower()
        if garment_type not in ['upper', 'lower']:
            logger.warning(f"FitAnalysis: Invalid garment_type: {garment_type}")
            raise ValidationError("garment_type must be 'upper' or 'lower'")
        
        garment_measurements = data.get('garment_measurements', {})
        if not garment_measurements or not isinstance(garment_measurements, dict):
            logger.warning("FitAnalysis: Missing or invalid garment_measurements")
            raise ValidationError("garment_measurements must be a non-empty object")
        
        garment_size = data.get('garment_size', '')
        
        logger.info(f"FitAnalysis: garment_type={garment_type}, garment_size={garment_size}")
        logger.info(f"FitAnalysis: garment_measurements keys: {list(garment_measurements.keys())}")
        
        # Retrieve user's body measurements
        logger.info(f"FitAnalysis: Retrieving body measurements for user_id={user_id}")
        body_measurements_record = BodyMeasurements.get_by_user(user_id)
        
        if not body_measurements_record:
            logger.warning(f"FitAnalysis: No body measurements found for user_id={user_id}")
            raise NotFoundError("No body measurements found for this user")
        
        body_measurements = body_measurements_record.to_dict()
        logger.info(f"FitAnalysis: Body measurements retrieved: {list(body_measurements.keys())}")
        
        # Perform fit analysis
        logger.info(f"FitAnalysis: Calling FitAnalysisService.analyze_fit")
        fit_analysis_result = FitAnalysisService.analyze_fit(
            garment_type=garment_type,
            body_measurements=body_measurements,
            garment_measurements=garment_measurements
        )
        
        # Add garment size to response
        fit_analysis_result['garment_size'] = garment_size
        
        logger.info(f"FitAnalysis: Analysis complete - overall_fit={fit_analysis_result.get('overall_fit')}")
        
        return jsonify(fit_analysis_result), 200
        
    except (ValidationError, NotFoundError) as e:
        logger.warning(f"FitAnalysis: {e.__class__.__name__} - {e.message}")
        return jsonify({'error': e.message}), e.status_code
    except BecauseFutureError as e:
        logger.error(f"FitAnalysis: BecauseFutureError - {e.message}")
        return jsonify({'error': e.message}), e.status_code
    except Exception as e:
        logger.error(f"FitAnalysis: Unexpected error - {str(e)}", exc_info=True)
        return jsonify({'error': 'Internal server error'}), 500
