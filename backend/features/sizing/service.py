"""
Sizing algorithm service
Fetches garment data from Lovable DB and compares with user measurements
"""

import requests
from typing import Dict, List, Optional, Any
from shared.logger import logger
from config import Config

# Lovable/Supabase API configuration (loaded from Config/environment)
# Set LOVABLE_API_KEY in .env file


def fetch_garment_from_lovable(url: str = None, garment_id: str = None, sku: str = None) -> Optional[Dict]:
    """
    Fetch garment data from Lovable DB (Supabase)

    Args:
        url: Product page URL
        garment_id: Garment UUID
        sku: Garment SKU

    Returns:
        Garment data dict or None if not found
    """
    logger.info(f"fetch_garment_from_lovable: ENTRY - url={url}, id={garment_id}, sku={sku}")

    # Build query parameter
    if url:
        param = f"url={requests.utils.quote(url, safe='')}"
    elif garment_id:
        param = f"id={garment_id}"
    elif sku:
        param = f"sku={sku}"
    else:
        logger.warning("fetch_garment_from_lovable: No identifier provided")
        return None

    try:
        response = requests.get(
            f"{Config.LOVABLE_API_BASE}/get-garment?{param}",
            headers={
                "apikey": Config.LOVABLE_API_KEY,
                "Content-Type": "application/json"
            },
            timeout=30
        )

        if response.status_code == 200:
            data = response.json()
            logger.info(f"fetch_garment_from_lovable: EXIT - Found garment: {data.get('name')}")
            return data
        elif response.status_code == 404:
            logger.info("fetch_garment_from_lovable: EXIT - Garment not found in Lovable DB")
            return None
        else:
            logger.warning(f"fetch_garment_from_lovable: EXIT - API error {response.status_code}: {response.text}")
            return None

    except Exception as e:
        logger.exception(f"fetch_garment_from_lovable: EXIT - Error: {str(e)}")
        return None


def calculate_size_recommendation(
    user_measurements: Dict[str, float],
    garment_data: Dict
) -> Dict[str, Any]:
    """
    Calculate size recommendation by comparing user measurements with garment measurements

    IMPORTANT: Garment measurements are ONE-WAY (half circumference).
    User measurements are FULL circumference, so we divide by 2 for comparison.

    Args:
        user_measurements: User's body measurements (from BodyMeasurements model)
        garment_data: Garment data from Lovable DB

    Returns:
        Dict with recommendation, fit_analysis, and details
    """
    logger.info(f"calculate_size_recommendation: ENTRY - garment={garment_data.get('name')}")

    category = garment_data.get('category', '').lower()
    garment_measurements = garment_data.get('garment_measurements', [])
    fit_type = garment_data.get('fit_type', 'regular')
    material_stretch = garment_data.get('material_stretch', 'none')

    # Convert garment measurements list to dict
    garment_dict = {}
    for m in garment_measurements:
        garment_dict[m['measurement_type']] = m['value_cm']

    # Fit analysis results
    fit_analysis = []
    overall_fit = "good"
    confidence = 0.0
    total_checks = 0
    passed_checks = 0

    # Ease allowance based on fit type (in cm, one-way)
    ease_allowances = {
        'fitted': 1,      # 1cm ease (tight fit)
        'slim': 2,        # 2cm ease
        'regular': 3,     # 3cm ease (standard)
        'oversized': 5,   # 5cm ease (loose)
        'wide': 6         # 6cm ease (very loose)
    }
    ease = ease_allowances.get(fit_type, 3)

    # Stretch factor (allows more tolerance)
    stretch_factors = {
        'none': 1.0,
        'slight': 1.05,      # 5% stretch tolerance
        'very_stretchy': 1.15  # 15% stretch tolerance
    }
    stretch = stretch_factors.get(material_stretch, 1.0)

    if category == 'top':
        # === TOP MEASUREMENTS ===

        # 1. Breast/Chest comparison
        user_breast = user_measurements.get('breast_circumference')
        garment_breast = garment_dict.get('breast_width')

        if user_breast and garment_breast:
            total_checks += 1
            # User circumference / 2 = one-way measurement
            user_half = user_breast / 2
            # Required garment width = user half + ease
            required_width = user_half + ease

            # With stretch allowance
            max_garment = garment_breast * stretch

            diff = garment_breast - user_half

            if diff >= ease:
                fit_analysis.append({
                    'area': 'chest',
                    'status': 'good',
                    'message': f'Good fit with {diff:.1f}cm ease',
                    'user_value': user_half,
                    'garment_value': garment_breast,
                    'difference': diff
                })
                passed_checks += 1
            elif diff >= 0 and max_garment >= required_width:
                fit_analysis.append({
                    'area': 'chest',
                    'status': 'tight',
                    'message': f'Slightly tight but stretch allows fit ({diff:.1f}cm ease)',
                    'user_value': user_half,
                    'garment_value': garment_breast,
                    'difference': diff
                })
                passed_checks += 0.7
            elif diff < 0:
                fit_analysis.append({
                    'area': 'chest',
                    'status': 'too_small',
                    'message': f'Too small by {abs(diff):.1f}cm',
                    'user_value': user_half,
                    'garment_value': garment_breast,
                    'difference': diff
                })
                overall_fit = "too_small"
            else:
                fit_analysis.append({
                    'area': 'chest',
                    'status': 'tight',
                    'message': f'May be tight ({diff:.1f}cm ease)',
                    'user_value': user_half,
                    'garment_value': garment_breast,
                    'difference': diff
                })
                passed_checks += 0.5

        # 2. Arm length comparison
        user_arm = user_measurements.get('arm_length')
        garment_arm = garment_dict.get('arm_length')

        if user_arm and garment_arm:
            total_checks += 1
            diff = garment_arm - user_arm

            if abs(diff) <= 3:  # Within 3cm is good
                fit_analysis.append({
                    'area': 'sleeve_length',
                    'status': 'good',
                    'message': f'Good sleeve length (diff: {diff:+.1f}cm)',
                    'user_value': user_arm,
                    'garment_value': garment_arm,
                    'difference': diff
                })
                passed_checks += 1
            elif diff > 3:
                fit_analysis.append({
                    'area': 'sleeve_length',
                    'status': 'long',
                    'message': f'Sleeves may be {diff:.1f}cm too long',
                    'user_value': user_arm,
                    'garment_value': garment_arm,
                    'difference': diff
                })
                passed_checks += 0.7
            else:
                fit_analysis.append({
                    'area': 'sleeve_length',
                    'status': 'short',
                    'message': f'Sleeves may be {abs(diff):.1f}cm too short',
                    'user_value': user_arm,
                    'garment_value': garment_arm,
                    'difference': diff
                })
                passed_checks += 0.5

        # 3. Biceps/arm width comparison
        user_biceps = user_measurements.get('biceps_circumference')
        garment_arm_width = garment_dict.get('arm_width')

        if user_biceps and garment_arm_width:
            total_checks += 1
            user_half = user_biceps / 2
            diff = garment_arm_width - user_half

            if diff >= 1:  # At least 1cm ease
                fit_analysis.append({
                    'area': 'sleeve_width',
                    'status': 'good',
                    'message': f'Good sleeve width ({diff:.1f}cm ease)',
                    'user_value': user_half,
                    'garment_value': garment_arm_width,
                    'difference': diff
                })
                passed_checks += 1
            elif diff >= 0:
                fit_analysis.append({
                    'area': 'sleeve_width',
                    'status': 'snug',
                    'message': 'Sleeves may be snug',
                    'user_value': user_half,
                    'garment_value': garment_arm_width,
                    'difference': diff
                })
                passed_checks += 0.7
            else:
                fit_analysis.append({
                    'area': 'sleeve_width',
                    'status': 'tight',
                    'message': f'Sleeves may be tight by {abs(diff):.1f}cm',
                    'user_value': user_half,
                    'garment_value': garment_arm_width,
                    'difference': diff
                })
                passed_checks += 0.3

    elif category == 'bottom':
        # === BOTTOM MEASUREMENTS ===

        # 1. Waist comparison
        user_waist = user_measurements.get('waist_circumference')
        garment_waist = garment_dict.get('waist')

        if user_waist and garment_waist:
            total_checks += 1
            user_half = user_waist / 2
            diff = garment_waist - user_half

            if diff >= ease:
                fit_analysis.append({
                    'area': 'waist',
                    'status': 'good',
                    'message': f'Good waist fit ({diff:.1f}cm ease)',
                    'user_value': user_half,
                    'garment_value': garment_waist,
                    'difference': diff
                })
                passed_checks += 1
            elif diff >= 0:
                fit_analysis.append({
                    'area': 'waist',
                    'status': 'snug',
                    'message': f'Waist may be snug ({diff:.1f}cm ease)',
                    'user_value': user_half,
                    'garment_value': garment_waist,
                    'difference': diff
                })
                passed_checks += 0.7
            else:
                fit_analysis.append({
                    'area': 'waist',
                    'status': 'too_small',
                    'message': f'Waist too small by {abs(diff):.1f}cm',
                    'user_value': user_half,
                    'garment_value': garment_waist,
                    'difference': diff
                })
                overall_fit = "too_small"

        # 2. Hip comparison
        user_hip = user_measurements.get('hip_circumference')
        garment_hip = garment_dict.get('hip')

        if user_hip and garment_hip:
            total_checks += 1
            user_half = user_hip / 2
            diff = garment_hip - user_half

            if diff >= ease:
                fit_analysis.append({
                    'area': 'hip',
                    'status': 'good',
                    'message': f'Good hip fit ({diff:.1f}cm ease)',
                    'user_value': user_half,
                    'garment_value': garment_hip,
                    'difference': diff
                })
                passed_checks += 1
            elif diff >= 0:
                fit_analysis.append({
                    'area': 'hip',
                    'status': 'snug',
                    'message': f'Hips may be snug ({diff:.1f}cm ease)',
                    'user_value': user_half,
                    'garment_value': garment_hip,
                    'difference': diff
                })
                passed_checks += 0.7
            else:
                fit_analysis.append({
                    'area': 'hip',
                    'status': 'too_small',
                    'message': f'Hips too small by {abs(diff):.1f}cm',
                    'user_value': user_half,
                    'garment_value': garment_hip,
                    'difference': diff
                })
                overall_fit = "too_small"

        # 3. Thigh comparison
        user_thigh = user_measurements.get('upper_thigh_circumference')
        garment_thigh = garment_dict.get('thigh')

        if user_thigh and garment_thigh:
            total_checks += 1
            user_half = user_thigh / 2
            diff = garment_thigh - user_half

            if diff >= 1:
                fit_analysis.append({
                    'area': 'thigh',
                    'status': 'good',
                    'message': f'Good thigh fit ({diff:.1f}cm ease)',
                    'user_value': user_half,
                    'garment_value': garment_thigh,
                    'difference': diff
                })
                passed_checks += 1
            elif diff >= 0:
                fit_analysis.append({
                    'area': 'thigh',
                    'status': 'snug',
                    'message': 'Thighs may be snug',
                    'user_value': user_half,
                    'garment_value': garment_thigh,
                    'difference': diff
                })
                passed_checks += 0.7
            else:
                fit_analysis.append({
                    'area': 'thigh',
                    'status': 'tight',
                    'message': f'Thighs may be tight by {abs(diff):.1f}cm',
                    'user_value': user_half,
                    'garment_value': garment_thigh,
                    'difference': diff
                })
                passed_checks += 0.3

        # 4. Inseam/inner leg length comparison
        user_inseam = user_measurements.get('inner_leg_length')
        garment_inseam = garment_dict.get('inner_leg_length')

        if user_inseam and garment_inseam:
            total_checks += 1
            diff = garment_inseam - user_inseam

            if abs(diff) <= 3:
                fit_analysis.append({
                    'area': 'inseam',
                    'status': 'good',
                    'message': f'Good length (diff: {diff:+.1f}cm)',
                    'user_value': user_inseam,
                    'garment_value': garment_inseam,
                    'difference': diff
                })
                passed_checks += 1
            elif diff > 3:
                fit_analysis.append({
                    'area': 'inseam',
                    'status': 'long',
                    'message': f'May be {diff:.1f}cm too long',
                    'user_value': user_inseam,
                    'garment_value': garment_inseam,
                    'difference': diff
                })
                passed_checks += 0.7
            else:
                fit_analysis.append({
                    'area': 'inseam',
                    'status': 'short',
                    'message': f'May be {abs(diff):.1f}cm too short',
                    'user_value': user_inseam,
                    'garment_value': garment_inseam,
                    'difference': diff
                })
                passed_checks += 0.5

        # 5. Front crotch comparison
        user_crotch = user_measurements.get('waist_to_crotch_front_length')
        garment_crotch = garment_dict.get('front_crotch')

        if user_crotch and garment_crotch:
            total_checks += 1
            diff = garment_crotch - user_crotch

            if diff >= 0 and diff <= 3:
                fit_analysis.append({
                    'area': 'rise',
                    'status': 'good',
                    'message': f'Good rise ({diff:+.1f}cm)',
                    'user_value': user_crotch,
                    'garment_value': garment_crotch,
                    'difference': diff
                })
                passed_checks += 1
            elif diff > 3:
                fit_analysis.append({
                    'area': 'rise',
                    'status': 'high',
                    'message': f'Higher rise by {diff:.1f}cm',
                    'user_value': user_crotch,
                    'garment_value': garment_crotch,
                    'difference': diff
                })
                passed_checks += 0.8
            else:
                fit_analysis.append({
                    'area': 'rise',
                    'status': 'low',
                    'message': f'Lower rise by {abs(diff):.1f}cm',
                    'user_value': user_crotch,
                    'garment_value': garment_crotch,
                    'difference': diff
                })
                passed_checks += 0.6

    # Calculate confidence score
    if total_checks > 0:
        confidence = (passed_checks / total_checks) * 100

    # Determine recommendation
    if overall_fit == "too_small":
        recommendation = "NOT_RECOMMENDED"
        recommendation_message = "This garment is likely too small based on your measurements."
    elif confidence >= 80:
        recommendation = "RECOMMENDED"
        recommendation_message = "This garment should fit you well."
    elif confidence >= 60:
        recommendation = "LIKELY_FIT"
        recommendation_message = "This garment will likely fit, but some areas may be snug."
    elif confidence >= 40:
        recommendation = "UNCERTAIN"
        recommendation_message = "Fit is uncertain. Check individual measurements."
    else:
        recommendation = "NOT_RECOMMENDED"
        recommendation_message = "This garment may not fit well."

    result = {
        'recommendation': recommendation,
        'recommendation_message': recommendation_message,
        'confidence': round(confidence, 1),
        'overall_fit': overall_fit,
        'fit_type': fit_type,
        'material_stretch': material_stretch,
        'category': category,
        'garment_name': garment_data.get('name'),
        'available_sizes': garment_data.get('size_label'),
        'fit_analysis': fit_analysis,
        'checks_performed': total_checks,
        'checks_passed': round(passed_checks, 1)
    }

    logger.info(f"calculate_size_recommendation: EXIT - recommendation={recommendation}, confidence={confidence:.1f}%")
    return result
