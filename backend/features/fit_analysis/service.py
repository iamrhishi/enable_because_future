"""
Fit Analysis Service
Compares body measurements with garment measurements to determine fit
"""

from typing import Dict, List, Any, Tuple
from dataclasses import dataclass
from shared.logger import logger


@dataclass
class FitResult:
    """Represents a single fit comparison result"""
    metric: str
    body_value: float
    garment_value: float
    fit_status: str  # "good fit" or "bad fit"
    difference: float  # body_value - garment_value


class FitAnalysisService:
    """Service for analyzing garment fit against body measurements"""
    
    # Measurement categorization
    UPPER_MEASUREMENTS = {
        'shoulder_circumference',
        'arm_length',
        'biceps_circumference',
        'breast_circumference',
        'under_breast_circumference',
        'collarbone_to_belly_button_length'
    }
    
    LOWER_MEASUREMENTS = {
        'waist_circumference',
        'hip_circumference',
        'upper_thigh_circumference',
        'waist_to_crotch_front_length',
        'waist_to_crotch_back_length',
        'inner_leg_length',
        'foot_length',
        'foot_width'
    }
    
    # Measurement transformations for comparison
    # Format: (garment_key, body_key, transformation_function)
    MEASUREMENT_MAPPINGS = {
        # Upper garment measurements
        'breast_width': ('breast_circumference', lambda val: val / 2),  # garment uses half circumference
        'arm_width': ('biceps_circumference', lambda val: val / 2),
        'shirt_length': ('collarbone_to_belly_button_length', lambda val: val),
        'arm_length': ('arm_length', lambda val: val),
        'shoulder_width': ('shoulder_circumference', lambda val: val / 2),
        
        # Lower garment measurements
        'waist': ('waist_circumference', lambda val: val / 2),  # garment uses half circumference
        'hip': ('hip_circumference', lambda val: val / 2),
        'leg_length': ('inner_leg_length', lambda val: val),
        'front_rise': ('waist_to_crotch_front_length', lambda val: val),
        'inseam': ('inner_leg_length', lambda val: val),
        'thigh': ('upper_thigh_circumference', lambda val: val / 2),
    }
    
    @staticmethod
    def get_applicable_measurements(garment_type: str) -> set:
        """
        Get applicable measurements for a garment type
        
        Args:
            garment_type: 'upper' or 'lower'
            
        Returns:
            Set of applicable measurement keys
        """
        if garment_type.lower() == 'upper':
            return FitAnalysisService.UPPER_MEASUREMENTS
        elif garment_type.lower() == 'lower':
            return FitAnalysisService.LOWER_MEASUREMENTS
        else:
            return set()
    
    @staticmethod
    def analyze_fit(
        garment_type: str,
        body_measurements: Dict[str, Any],
        garment_measurements: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Analyze how well a garment fits based on body measurements
        
        Args:
            garment_type: 'upper' or 'lower'
            body_measurements: User's body measurements
            garment_measurements: Garment measurements for selected size
            
        Returns:
            Dictionary with fit analysis results
        """
        logger.info(f"FitAnalysisService: analyze_fit ENTRY - garment_type={garment_type}")
        
        results = []
        
        # Determine which measurements to compare based on garment type
        applicable_measurements = FitAnalysisService.get_applicable_measurements(garment_type)
        
        logger.info(f"FitAnalysisService: Applicable measurements: {applicable_measurements}")
        
        # Compare relevant measurements
        for garment_key, garment_value in garment_measurements.items():
            if not garment_value:
                continue
            
            try:
                # Find corresponding body measurement
                body_key = FitAnalysisService._find_body_measurement(garment_key)
                
                if not body_key or body_key not in body_measurements:
                    logger.info(f"FitAnalysisService: Skipping garment_key={garment_key}, no body measurement")
                    continue
                
                body_value = body_measurements[body_key]
                if not body_value:
                    continue
                
                # Apply transformation to body measurement for comparison
                transformed_body_value = FitAnalysisService._transform_measurement(
                    body_key, body_value
                )
                
                # Calculate difference (positive = body bigger, negative = body smaller)
                difference = float(transformed_body_value) - float(garment_value)
                
                # Sophisticated fit determination logic
                # - If exact match (within 0.1cm tolerance): "body fit"
                # - If within 2cm difference: "good fit"
                # - If within 2-4cm difference: "loose fit"
                # - If body > garment: "tight"
                # - If body much smaller (>4cm): "loose fit"
                
                abs_difference = abs(difference)
                
                if abs_difference < 0.1:
                    fit_status = "body fit"  # Perfect match
                elif abs_difference < 2:
                    fit_status = "good fit"  # Within 2cm - comfortable
                elif abs_difference < 4:
                    fit_status = "loose fit"  # Within 2-4cm difference
                elif difference > 0:
                    fit_status = "tight"  # Body bigger than garment - too tight
                else:  # difference <= -4
                    fit_status = "loose fit"  # Body much smaller - too loose
                
                result = FitResult(
                    metric=garment_key,
                    body_value=float(transformed_body_value),
                    garment_value=float(garment_value),
                    fit_status=fit_status,
                    difference=difference
                )
                results.append(result)
                
                logger.info(
                    f"FitAnalysisService: {garment_key} - "
                    f"body={transformed_body_value:.2f}, garment={garment_value:.2f}, "
                    f"diff={difference:.2f}cm, fit={fit_status}"
                )
                
            except Exception as e:
                logger.warning(f"FitAnalysisService: Error processing {garment_key}: {str(e)}")
                continue
        
        # Calculate overall fit based on new fit statuses
        if results:
            # Count fit statuses
            body_fit_count = sum(1 for r in results if r.fit_status == "body fit")
            good_fit_count = sum(1 for r in results if r.fit_status == "good fit")
            loose_fit_count = sum(1 for r in results if r.fit_status == "loose fit")
            tight_count = sum(1 for r in results if r.fit_status == "tight")
            
            # Determine overall fit: prioritize tight status, then loose, then good
            if tight_count > 0:
                overall_fit = "tight"
            elif loose_fit_count > 0 and good_fit_count == 0 and body_fit_count == 0:
                overall_fit = "loose fit"
            elif body_fit_count == len(results):
                overall_fit = "body fit"
            else:
                overall_fit = "good fit"
        else:
            body_fit_count = 0
            good_fit_count = 0
            loose_fit_count = 0
            tight_count = 0
            overall_fit = "insufficient data"
        
        fit_analysis = {
            'garment_type': garment_type,
            'overall_fit': overall_fit,
            'good_fits': good_fit_count,
            'bad_fits': tight_count,  # Keep backward compatibility
            'body_fit_count': body_fit_count,
            'loose_fit_count': loose_fit_count,
            'tight_count': tight_count,
            'measurements': [
                {
                    'metric': r.metric,
                    'body_value': round(r.body_value, 2),
                    'garment_value': round(r.garment_value, 2),
                    'fit_status': r.fit_status,
                    'difference': round(r.difference, 2)
                }
                for r in results
            ]
        }
        
        logger.info(f"FitAnalysisService: EXIT - overall_fit={overall_fit}, "
                   f"body_fit={body_fit_count}, good_fit={good_fit_count}, "
                   f"loose_fit={loose_fit_count}, tight={tight_count}")
        
        return fit_analysis
    
    @staticmethod
    def _find_body_measurement(garment_key: str) -> str:
        """
        Find the corresponding body measurement key for a garment measurement
        
        Args:
            garment_key: Garment measurement key
            
        Returns:
            Body measurement key or None
        """
        # Direct mappings
        mapping = {
            'breast_width': 'breast_circumference',
            'arm_width': 'biceps_circumference',
            'shirt_length': 'collarbone_to_belly_button_length',
            'arm_length': 'arm_length',
            'shoulder_width': 'shoulder_circumference',
            'waist': 'waist_circumference',
            'hip': 'hip_circumference',
            'leg_length': 'inner_leg_length',
            'front_rise': 'waist_to_crotch_front_length',
            'inseam': 'inner_leg_length',
            'thigh': 'upper_thigh_circumference',
        }
        
        return mapping.get(garment_key)
    
    @staticmethod
    def _transform_measurement(body_key: str, value: float) -> float:
        """
        Transform body measurement for comparison with garment measurements
        
        Args:
            body_key: Body measurement key
            value: Measurement value
            
        Returns:
            Transformed value
        """
        # Measurements that need to be halved for comparison
        half_measurements = {
            'breast_circumference',
            'biceps_circumference',
            'waist_circumference',
            'hip_circumference',
            'upper_thigh_circumference',
            'shoulder_circumference'
        }
        
        if body_key in half_measurements:
            return value / 2
        else:
            return value
