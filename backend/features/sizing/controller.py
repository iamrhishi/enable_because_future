"""
Sizing recommendation API endpoints
"""

from flask import Blueprint, request
from shared.response import success_response, error_response_from_string
from shared.middleware import require_auth
from shared.logger import logger
from features.body_measurements.model import BodyMeasurements
from features.sizing.service import fetch_garment_from_lovable, calculate_size_recommendation

sizing_bp = Blueprint('sizing', __name__, url_prefix='/api/sizing')


@sizing_bp.route('/recommend', methods=['POST'])
@require_auth
def get_size_recommendation():
    """
    Get size recommendation for a garment based on user's body measurements

    Request Body (JSON):
    {
        "url": "https://brand.com/product-page",  // OR
        "garment_id": "uuid",                     // OR
        "sku": "SKU123"
    }

    Provide exactly one identifier: url, garment_id, or sku

    Returns:
    {
        "recommendation": "RECOMMENDED" | "LIKELY_FIT" | "UNCERTAIN" | "NOT_RECOMMENDED",
        "recommendation_message": "This garment should fit you well.",
        "confidence": 85.0,
        "overall_fit": "good" | "too_small",
        "fit_type": "regular",
        "material_stretch": "slight",
        "category": "top" | "bottom",
        "garment_name": "T-shirt",
        "available_sizes": "S, M, L, XL",
        "fit_analysis": [
            {
                "area": "chest",
                "status": "good",
                "message": "Good fit with 4.5cm ease",
                "user_value": 47.5,
                "garment_value": 55,
                "difference": 7.5
            }
        ],
        "checks_performed": 3,
        "checks_passed": 2.7
    }
    """
    user_id = request.user_id
    logger.info(f"get_size_recommendation: ENTRY - user_id={user_id}")

    try:
        data = request.get_json() if request.is_json else {}

        # Get garment identifier
        url = data.get('url')
        garment_id = data.get('garment_id')
        sku = data.get('sku')

        if not url and not garment_id and not sku:
            return error_response_from_string(
                "Provide 'url', 'garment_id', or 'sku' to identify the garment",
                400, 'VALIDATION_ERROR'
            )

        # Fetch user's body measurements
        measurements = BodyMeasurements.get_by_user(user_id)
        if not measurements:
            return error_response_from_string(
                "No body measurements found. Please add your measurements first.",
                404, 'MEASUREMENTS_NOT_FOUND'
            )

        user_measurements = measurements.to_dict()

        # Check if user has essential measurements
        essential_for_tops = ['breast_circumference']
        essential_for_bottoms = ['waist_circumference', 'hip_circumference']

        has_top_measurements = any(user_measurements.get(m) for m in essential_for_tops)
        has_bottom_measurements = any(user_measurements.get(m) for m in essential_for_bottoms)

        if not has_top_measurements and not has_bottom_measurements:
            return error_response_from_string(
                "Insufficient body measurements. Please add breast, waist, or hip measurements.",
                400, 'INSUFFICIENT_MEASUREMENTS'
            )

        # Fetch garment from Lovable DB
        garment_data = fetch_garment_from_lovable(url=url, garment_id=garment_id, sku=sku)

        if not garment_data:
            return error_response_from_string(
                "Garment not found in sizing database. This product may not have sizing data available.",
                404, 'GARMENT_NOT_FOUND'
            )

        # Check if garment has measurements
        if not garment_data.get('garment_measurements'):
            return error_response_from_string(
                "Garment found but no measurements available.",
                400, 'NO_GARMENT_MEASUREMENTS'
            )

        # Calculate size recommendation
        result = calculate_size_recommendation(user_measurements, garment_data)

        logger.info(f"get_size_recommendation: EXIT - recommendation={result['recommendation']}")
        return success_response(data=result)

    except Exception as e:
        logger.exception(f"get_size_recommendation: EXIT - Error: {str(e)}")
        return error_response_from_string(f'Server error: {str(e)}', 500)


@sizing_bp.route('/garment', methods=['GET'])
def get_garment_info():
    """
    Get garment sizing info from Lovable DB (public endpoint)

    Query Parameters (provide exactly one):
    - url: Product page URL
    - id: Garment UUID
    - sku: Garment SKU

    Returns garment data with measurements
    """
    logger.info("get_garment_info: ENTRY")

    try:
        url = request.args.get('url')
        garment_id = request.args.get('id')
        sku = request.args.get('sku')

        if not url and not garment_id and not sku:
            return error_response_from_string(
                "Provide 'url', 'id', or 'sku' query parameter",
                400, 'VALIDATION_ERROR'
            )

        garment_data = fetch_garment_from_lovable(url=url, garment_id=garment_id, sku=sku)

        if not garment_data:
            return error_response_from_string(
                "Garment not found",
                404, 'NOT_FOUND'
            )

        logger.info(f"get_garment_info: EXIT - Found garment: {garment_data.get('name')}")
        return success_response(data=garment_data)

    except Exception as e:
        logger.exception(f"get_garment_info: EXIT - Error: {str(e)}")
        return error_response_from_string(f'Server error: {str(e)}', 500)
