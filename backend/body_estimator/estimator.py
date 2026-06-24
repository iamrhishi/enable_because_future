import numpy as np
import cv2
from typing import Optional, Dict, Tuple, Any

from body_estimator.models import BodyMeasurements, EstimationResponse
from body_estimator.detector import MediaPipeDetector
from body_estimator.utils import (
    calculate_distance,
    calculate_pixel_distance,
    clamp,
    get_largest_connected_component,
    ellipse_circumference
)

def scan_torso_width(mask: np.ndarray, y: int, x_center: int, left_limit: int, right_limit: int) -> int:
    """
    Scans the width of the foreground silhouette in a single row `y` of the binary mask,
    starting from the center column `x_center` and searching outwards.
    Constrained by left_limit and right_limit to avoid bleeding into arms.
    """
    h, w = mask.shape
    if y < 0 or y >= h:
        return 0
    
    # Clamp x_center within limits
    x_center = int(max(left_limit, min(x_center, right_limit)))
    
    # If starting column is background, look for closest foreground in row within limits
    if mask[y, x_center] == 0:
        fg_indices = np.where(mask[y, left_limit:right_limit+1] > 0)[0]
        if len(fg_indices) == 0:
            return 0
        # Convert index back to global coordinate
        fg_indices = fg_indices + left_limit
        x_center = int(fg_indices[np.argmin(np.abs(fg_indices - x_center))])
        
    # Scan left
    x_left = x_center
    while x_left > left_limit and mask[y, x_left - 1] > 0:
        x_left -= 1
        
    # Scan right
    x_right = x_center
    while x_right < right_limit and mask[y, x_right + 1] > 0:
        x_right += 1
        
    return x_right - x_left

def estimate_body_measurements(
    front_img_np: np.ndarray,
    height_cm: float,
    weight_kg: float,
    side_img_np: Optional[np.ndarray] = None,
    detector: Optional[MediaPipeDetector] = None
) -> Dict[str, Any]:
    """
    Estimates body measurements from a front-facing image, height, weight, and optional side-view image.
    """
    h_front, w_front, _ = front_img_np.shape
    
    # Initialize detector if not provided
    created_detector = False
    if detector is None:
        detector = MediaPipeDetector()
        created_detector = True
        
    try:
        # 1. Run Detector on Front Image
        landmarks_front, mask_front, vis_scores_front = detector.detect(front_img_np)
        
        if landmarks_front is None:
            raise ValueError("No pose landmarks detected in the front-facing image. Please ensure the whole body is visible.")
            
        # Clean mask
        mask_front = get_largest_connected_component(mask_front)
        
        # 2. Run Detector on Side Image (if provided)
        landmarks_side = None
        mask_side = None
        vis_scores_side = []
        if side_img_np is not None:
            h_side, w_side, _ = side_img_np.shape
            landmarks_side, mask_side, vis_scores_side = detector.detect(side_img_np)
            if landmarks_side is not None:
                mask_side = get_largest_connected_component(mask_side)
                
    finally:
        if created_detector:
            detector.close()

    # --- Step 3: Scale Calibration ---
    # Find topmost and bottommost foreground pixels of the silhouette in the front image
    y_indices_front = np.where(mask_front > 0)[0]
    if len(y_indices_front) == 0:
        raise ValueError("Empty segmentation mask in the front-facing image.")
        
    y_top_front = np.min(y_indices_front)
    y_bottom_front = np.max(y_indices_front)
    H_front_pixels = float(y_bottom_front - y_top_front)
    scale_front = height_cm / H_front_pixels

    # Scale Calibration for Side Image (if available)
    scale_side = None
    if mask_side is not None:
        y_indices_side = np.where(mask_side > 0)[0]
        if len(y_indices_side) > 0:
            y_top_side = np.min(y_indices_side)
            y_bottom_side = np.max(y_indices_side)
            H_side_pixels = float(y_bottom_side - y_top_side)
            scale_side = height_cm / H_side_pixels

    # --- Step 4: Define Torso Landmarks & Levels ---
    # Landmarks map (pixel coordinates)
    def to_pixels(lm, w, h):
        return int(lm.x * w), int(lm.y * h)

    # Front Landmarks
    x_sh_l, y_sh_l = to_pixels(landmarks_front[11], w_front, h_front)
    x_sh_r, y_sh_r = to_pixels(landmarks_front[12], w_front, h_front)
    x_hip_l, y_hip_l = to_pixels(landmarks_front[23], w_front, h_front)
    x_hip_r, y_hip_r = to_pixels(landmarks_front[24], w_front, h_front)
    
    y_shoulder = int((y_sh_l + y_sh_r) / 2)
    y_hip = int((y_hip_l + y_hip_r) / 2)
    x_center = int((x_hip_l + x_hip_r) / 2)
    
    torso_height = float(y_hip - y_shoulder)
    if torso_height <= 0:
        raise ValueError("Invalid torso coordinates detected in the front image.")

    # Dynamic landmark-guided scan boundaries to prevent bleeding into arms
    w_sh_lm = abs(x_sh_l - x_sh_r)
    w_hip_lm = abs(x_hip_l - x_hip_r)

    def get_limits(y_val: int) -> Tuple[int, int]:
        t_val = (y_val - y_shoulder) / torso_height
        t_val = max(0.0, min(t_val, 1.25)) # Clamp interpolation factor
        w_expected = (1.0 - t_val) * w_sh_lm + t_val * w_hip_lm
        left = int(max(0, x_center - 0.60 * w_expected))
        right = int(min(w_front - 1, x_center + 0.60 * w_expected))
        return left, right

    # Define vertical levels (front)
    y_chest = int(y_shoulder + 0.30 * torso_height)
    y_under_bust = int(y_shoulder + 0.45 * torso_height)
    
    # Narrowest search for waist
    waist_search_start = int(y_shoulder + 0.50 * torso_height)
    waist_search_end = int(y_hip)
    y_waist = waist_search_start
    min_waist_w = float('inf')
    for y in range(waist_search_start, waist_search_end + 1):
        left_lim_y, right_lim_y = get_limits(y)
        w_pixels = scan_torso_width(mask_front, y, x_center, left_lim_y, right_lim_y)
        if 0 < w_pixels < min_waist_w:
            min_waist_w = w_pixels
            y_waist = y

    # Widest search for hips (pelvic region)
    ankle_l = landmarks_front[27]
    ankle_r = landmarks_front[28]
    y_ankle = int((ankle_l.y + ankle_r.y) / 2 * h_front)
    leg_length = float(y_ankle - y_hip)
    
    hip_search_start = int(y_hip - 0.10 * torso_height)
    hip_search_end = int(y_hip + 0.20 * leg_length)
    y_hip_max = y_hip
    max_hip_w = 0
    for y in range(hip_search_start, hip_search_end + 1):
        left_lim_y, right_lim_y = get_limits(y)
        w_pixels = scan_torso_width(mask_front, y, x_center, left_lim_y, right_lim_y)
        if w_pixels > max_hip_w:
            max_hip_w = w_pixels
            y_hip_max = y

    # --- Step 5: Width Measurements (Front) ---
    # Shoulder Width: Silhouette width at shoulder level, or landmark distance, whichever is larger
    shoulder_landmark_width = calculate_pixel_distance(landmarks_front[11], landmarks_front[12], w_front, h_front) * scale_front
    left_sh_lim = int(max(0, x_center - 0.70 * w_sh_lm))
    right_sh_lim = int(min(w_front - 1, x_center + 0.70 * w_sh_lm))
    shoulder_sil_width = scan_torso_width(mask_front, y_shoulder, x_center, left_sh_lim, right_sh_lim) * scale_front
    shoulder_width_cm = max(shoulder_landmark_width, shoulder_sil_width)
    
    left_chest_lim, right_chest_lim = get_limits(y_chest)
    chest_width_cm = scan_torso_width(mask_front, y_chest, x_center, left_chest_lim, right_chest_lim) * scale_front
    
    left_ub_lim, right_ub_lim = get_limits(y_under_bust)
    under_bust_width_cm = scan_torso_width(mask_front, y_under_bust, x_center, left_ub_lim, right_ub_lim) * scale_front
    
    waist_width_cm = min_waist_w * scale_front
    hip_width_cm = max_hip_w * scale_front

    # Thigh Level Width
    y_thigh = int(y_hip + 0.15 * leg_length)
    x_thigh_l = int((landmarks_front[23].x + landmarks_front[25].x) / 2 * w_front)
    x_thigh_r = int((landmarks_front[24].x + landmarks_front[26].x) / 2 * w_front)
    x_mid = (x_thigh_l + x_thigh_r) // 2
    
    left_thigh_lim, right_thigh_lim = get_limits(y_thigh)
    thigh_l_w = scan_torso_width(mask_front, y_thigh, x_thigh_l, left_thigh_lim, x_mid)
    thigh_r_w = scan_torso_width(mask_front, y_thigh, x_thigh_r, x_mid, right_thigh_lim)
    thigh_width_cm = ((thigh_l_w + thigh_r_w) / 2.0) * scale_front

    # --- Step 6: Expected Depths from Regression (BMI based) ---
    BMI = weight_kg / ((height_cm / 100.0) ** 2)
    # Scale aspect ratio based on BMI relative to normal (22.0)
    bmi_factor = (BMI / 22.0) ** 0.3
    
    expected_shoulder_depth = (0.12 * height_cm + 0.10 * weight_kg)
    expected_chest_depth = (0.10 * height_cm + 0.15 * weight_kg)
    expected_under_bust_depth = (0.08 * height_cm + 0.16 * weight_kg)
    expected_waist_depth = (0.06 * height_cm + 0.22 * weight_kg)
    expected_hip_depth = (0.07 * height_cm + 0.20 * weight_kg)
    expected_thigh_depth = (0.05 * height_cm + 0.18 * weight_kg)

    # --- Step 7: Depth Estimation (Side View) ---
    if landmarks_side is not None and mask_side is not None and scale_side is not None:
        h_side, w_side, _ = side_img_np.shape
        x_sh_l_s, y_sh_l_s = to_pixels(landmarks_side[11], w_side, h_side)
        x_sh_r_s, y_sh_r_s = to_pixels(landmarks_side[12], w_side, h_side)
        x_hip_l_s, y_hip_l_s = to_pixels(landmarks_side[23], w_side, h_side)
        x_hip_r_s, y_hip_r_s = to_pixels(landmarks_side[24], w_side, h_side)
        
        y_shoulder_s = int((y_sh_l_s + y_sh_r_s) / 2)
        y_hip_s = int((y_hip_l_s + y_hip_r_s) / 2)
        torso_height_s = float(y_hip_s - y_shoulder_s)
        
        y_chest_s = int(y_shoulder_s + 0.30 * torso_height_s)
        y_under_bust_s = int(y_shoulder_s + 0.45 * torso_height_s)
        
        # Search narrowest for waist in side view
        waist_s_start = int(y_shoulder_s + 0.50 * torso_height_s)
        waist_s_end = int(y_hip_s)
        y_waist_s = waist_s_start
        min_waist_side_w = float('inf')
        for y in range(waist_s_start, waist_s_end + 1):
            w_pixels = np.sum(mask_side[y, :] > 0)
            if 0 < w_pixels < min_waist_side_w:
                min_waist_side_w = w_pixels
                y_waist_s = y

        # Search widest for hips in side view
        ankle_l_s = landmarks_side[27]
        ankle_r_s = landmarks_side[28]
        y_ankle_s = int((ankle_l_s.y + ankle_r_s.y) / 2 * h_side)
        leg_length_s = float(y_ankle_s - y_hip_s)
        
        hip_s_start = int(y_hip_s - 0.10 * torso_height_s)
        hip_s_end = int(y_hip_s + 0.20 * leg_length_s)
        y_hip_s_max = y_hip_s
        max_hip_side_w = 0
        for y in range(hip_s_start, hip_s_end + 1):
            w_pixels = np.sum(mask_side[y, :] > 0)
            if w_pixels > max_hip_side_w:
                max_hip_side_w = w_pixels
                y_hip_s_max = y
                
        y_thigh_s = int(y_hip_s + 0.15 * leg_length_s)

        # Helper to get side width in cm
        def get_side_depth(y_val, expected_val):
            if 0 <= y_val < h_side:
                # Sum of foreground pixels represents body depth in side profile
                depth_pix = np.sum(mask_side[y_val, :] > 0)
                depth_val_cm = depth_pix * scale_side
                # Clamp to guard against arm obstruction and noise
                return clamp(depth_val_cm, 0.85 * expected_val, 1.15 * expected_val)
            return expected_val

        shoulder_depth = get_side_depth(y_shoulder_s, expected_shoulder_depth)
        chest_depth = get_side_depth(y_chest_s, expected_chest_depth)
        under_bust_depth = get_side_depth(y_under_bust_s, expected_under_bust_depth)
        waist_depth = get_side_depth(y_waist_s, expected_waist_depth)
        hip_depth = get_side_depth(y_hip_s_max, expected_hip_depth)
        thigh_depth = get_side_depth(y_thigh_s, expected_thigh_depth)
    else:
        # Fall back to regression-derived expected depths
        shoulder_depth = expected_shoulder_depth
        chest_depth = expected_chest_depth
        under_bust_depth = expected_under_bust_depth
        waist_depth = expected_waist_depth
        hip_depth = expected_hip_depth
        thigh_depth = expected_thigh_depth

    # --- Step 8: Circumference Estimation ---
    # Apply Ramanujan formula + local tuning multipliers
    shoulder_circ = ellipse_circumference(shoulder_width_cm, shoulder_depth) * 0.96
    breast_circ = ellipse_circumference(chest_width_cm, chest_depth) * 1.02
    under_breast_circ = ellipse_circumference(under_bust_width_cm, under_bust_depth) * 1.00
    waist_circ = ellipse_circumference(waist_width_cm, waist_depth) * 0.98
    hip_circ = ellipse_circumference(hip_width_cm, hip_depth) * 1.01
    thigh_circ = ellipse_circumference(thigh_width_cm, thigh_depth) * 1.00

    # --- Step 9: Length Measurements ---
    # Arm length: average of both arms (Shoulder -> Elbow -> Wrist)
    left_arm = calculate_pixel_distance(landmarks_front[11], landmarks_front[13], w_front, h_front) + \
               calculate_pixel_distance(landmarks_front[13], landmarks_front[15], w_front, h_front)
    right_arm = calculate_pixel_distance(landmarks_front[12], landmarks_front[14], w_front, h_front) + \
                calculate_pixel_distance(landmarks_front[14], landmarks_front[16], w_front, h_front)
    arm_length = ((left_arm + right_arm) / 2.0) * scale_front

    # Inner leg length (inseam): Hip -> Knee -> Ankle, scaled and adjusted for crotch position
    left_leg = calculate_pixel_distance(landmarks_front[23], landmarks_front[25], w_front, h_front) + \
               calculate_pixel_distance(landmarks_front[25], landmarks_front[27], w_front, h_front)
    right_leg = calculate_pixel_distance(landmarks_front[24], landmarks_front[26], w_front, h_front) + \
                calculate_pixel_distance(landmarks_front[26], landmarks_front[28], w_front, h_front)
    leg_length_pix = (left_leg + right_leg) / 2.0
    inner_leg_length = (leg_length_pix * scale_front) * 0.88 - 3.0

    # --- Step 10: Derived Measurements ---
    # Biceps: anthropometric regression based on weight, height, and thigh circ
    biceps_expected = 0.15 * weight_kg + 0.06 * height_cm + 5.0
    biceps_circ = 0.7 * biceps_expected + 0.3 * (0.52 * thigh_circ + 1.5)
    
    # Collarbone to belly button length
    collarbone_to_belly_button = (torso_height * scale_front) * 0.65
    
    # Feet
    foot_length = height_cm * 0.147
    foot_width = foot_length * 0.38
    
    # Waist to crotch rises
    waist_to_crotch_front = 0.25 * hip_circ + 0.05 * height_cm - 8.0
    waist_to_crotch_back = waist_to_crotch_front + 0.05 * hip_circ + 1.0

    # --- Step 11: Confidence Scoring ---
    confidence = 1.0
    
    # Penalty if side profile is missing
    if side_img_np is None or landmarks_side is None:
        confidence -= 0.15
        
    # Penalty for low resolution (less than 640px height)
    min_res = min(h_front, w_front)
    if min_res < 640:
        confidence -= 0.10 * (1.0 - min_res / 640.0)
        
    # Penalty for uncertain pose visibility
    key_lm_indices = [11, 12, 13, 14, 15, 16, 23, 24, 25, 26, 27, 28]
    front_visibilities = [landmarks_front[idx].visibility for idx in key_lm_indices]
    avg_vis_front = np.mean(front_visibilities)
    if avg_vis_front < 0.90:
        confidence -= (0.90 - avg_vis_front) * 0.5
        
    if landmarks_side is not None:
        side_visibilities = [landmarks_side[idx].visibility for idx in key_lm_indices]
        avg_vis_side = np.mean(side_visibilities)
        if avg_vis_side < 0.85:
            confidence -= (0.85 - avg_vis_side) * 0.3
            
    # Penalty for partial body cut-off (if landmarks are too close to image boundary)
    cutoff_penalty = 0.0
    for idx in key_lm_indices:
        lm = landmarks_front[idx]
        if lm.x < 0.02 or lm.x > 0.98 or lm.y < 0.02 or lm.y > 0.98:
            cutoff_penalty += 0.05
    confidence -= min(0.20, cutoff_penalty)

    # Penalty for loose clothing detection
    # If the waist width is larger than expected relative to chest and BMI
    expected_waist_circ = 1.0 * weight_kg + 0.1 * height_cm
    clothing_ratio = waist_circ / expected_waist_circ
    if clothing_ratio > 1.25:
        confidence -= min(0.30, (clothing_ratio - 1.25) * 0.8)

    confidence = clamp(confidence, 0.10, 1.00)

    # Build final Response dict
    measurements = {
        "shoulderCircumference": round(shoulder_circ, 1),
        "armLength": round(arm_length, 1),
        "breastCircumference": round(breast_circ, 1),
        "underBreastCircumference": round(under_breast_circ, 1),
        "innerLegLength": round(inner_leg_length, 1),
        "waistCircumference": round(waist_circ, 1),
        "hipCircumference": round(hip_circ, 1),
        "upperThighCircumference": round(thigh_circ, 1),
        "bicepsCircumference": round(biceps_circ, 1),
        "collarboneToBellyButtonLength": round(collarbone_to_belly_button, 1),
        "footLength": round(foot_length, 1),
        "footWidth": round(foot_width, 1),
        "waistToCrotchFrontLength": round(waist_to_crotch_front, 1),
        "waistToCrotchBackLength": round(waist_to_crotch_back, 1)
    }

    return {
        "measurements": measurements,
        "confidence": round(confidence, 2)
    }
