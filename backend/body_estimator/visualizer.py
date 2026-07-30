import cv2
import numpy as np
import base64
from typing import List, Tuple

def draw_visual_debug(
    image_np: np.ndarray,
    landmarks,
    mask: np.ndarray,
    side_view: bool = False
) -> str:
    """
    Draws a futuristic scanner overlay on the image and returns it as a base64 encoded PNG.
    Includes:
      - Semi-transparent silhouette mask overlay (Green for front, Cyan for side).
      - Skeleton joint markers and connection lines (Glowing neon colors).
      - Horizontal scanning caliper bars showing where widths/depths were measured.
    """
    h, w, _ = image_np.shape
    overlay = image_np.copy()
    
    # 1. Draw Segmentation Mask Overlay
    color_mask = np.zeros_like(image_np)
    if side_view:
        # Cyan overlay for side profile
        color_mask[mask > 0] = [255, 255, 0] # BGR Cyan
    else:
        # Green overlay for front profile
        color_mask[mask > 0] = [0, 255, 0] # BGR Green
        
    cv2.addWeighted(color_mask, 0.25, overlay, 0.75, 0, overlay)

    # Convert normalized landmark points helper
    def to_px(lm):
        return int(lm.x * w), int(lm.y * h)

    # 2. Draw Torso Levels and Caliper Bars
    if landmarks is not None:
        if not side_view:
            # Front View Specific Scan Lines
            x_sh_l, y_sh_l = to_px(landmarks[11])
            x_sh_r, y_sh_r = to_px(landmarks[12])
            x_hip_l, y_hip_l = to_px(landmarks[23])
            x_hip_r, y_hip_r = to_px(landmarks[24])
            
            y_shoulder = int((y_sh_l + y_sh_r) / 2)
            y_hip = int((y_hip_l + y_hip_r) / 2)
            x_center = int((x_hip_l + x_hip_r) / 2)
            torso_height = float(y_hip - y_shoulder)
            
            w_sh_lm = abs(x_sh_l - x_sh_r)
            w_hip_lm = abs(x_hip_l - x_hip_r)

            def get_limits(y_val: int) -> Tuple[int, int]:
                t_val = (y_val - y_shoulder) / torso_height
                t_val = max(0.0, min(t_val, 1.25))
                w_expected = (1.0 - t_val) * w_sh_lm + t_val * w_hip_lm
                left = int(max(0, x_center - 0.60 * w_expected))
                right = int(min(w - 1, x_center + 0.60 * w_expected))
                return left, right

            # Define levels
            y_chest = int(y_shoulder + 0.30 * torso_height)
            y_under_bust = int(y_shoulder + 0.45 * torso_height)
            y_waist = int(y_shoulder + 0.68 * torso_height) # approx waist level for viz
            y_hip_level = int(y_hip + 0.05 * torso_height) # approx hip level for viz
            
            # Draw Horizontal Caliper Guides
            levels = [
                ("Shoulder", y_shoulder, (255, 0, 0), 0.70), # Blue
                ("Chest/Breast", y_chest, (255, 0, 255), 0.60), # Magenta
                ("Under Breast", y_under_bust, (0, 255, 255), 0.60), # Yellow
                ("Waist", y_waist, (0, 165, 255), 0.60), # Orange
                ("Hip", y_hip_level, (0, 0, 255), 0.60) # Red
            ]
            
            for label, y_level, color, factor in levels:
                if 0 <= y_level < h:
                    if label == "Shoulder":
                        left, right = int(max(0, x_center - factor * w_sh_lm)), int(min(w - 1, x_center + factor * w_sh_lm))
                    else:
                        left, right = get_limits(y_level)
                    
                    # Scan the actual mask width within limits
                    # Start from center and scan out
                    x_left = x_center
                    while x_left > left and mask[y_level, x_left - 1] > 0:
                        x_left -= 1
                    x_right = x_center
                    while x_right < right and mask[y_level, x_right + 1] > 0:
                        x_right += 1
                    
                    # Draw scanned width bar (solid line)
                    cv2.line(overlay, (x_left, y_level), (x_right, y_level), color, 3)
                    # Draw search boundaries (dots or brackets)
                    cv2.circle(overlay, (left, y_level), 4, color, -1)
                    cv2.circle(overlay, (right, y_level), 4, color, -1)
                    # Label
                    cv2.putText(overlay, label, (left - 10 if left > 100 else 10, y_level - 6),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1, cv2.LINE_AA)
        else:
            # Side View Specific scan lines
            # In side view, we measure total thickness (bounding box width of mask at levels)
            # Find levels relative to side landmarks
            x_sh_l, y_sh_l = to_px(landmarks[11])
            x_sh_r, y_sh_r = to_px(landmarks[12])
            x_hip_l, y_hip_l = to_px(landmarks[23])
            x_hip_r, y_hip_r = to_px(landmarks[24])
            y_shoulder_s = int((y_sh_l + y_sh_r) / 2)
            y_hip_s = int((y_hip_l + y_hip_r) / 2)
            torso_height_s = float(y_hip_s - y_shoulder_s)
            
            y_chest_s = int(y_shoulder_s + 0.30 * torso_height_s)
            y_under_bust_s = int(y_shoulder_s + 0.45 * torso_height_s)
            y_waist_s = int(y_shoulder_s + 0.68 * torso_height_s)
            y_hip_s_max = int(y_hip_s + 0.05 * torso_height_s)
            
            levels_side = [
                ("Shoulder Depth", y_shoulder_s, (255, 0, 0)),
                ("Chest Depth", y_chest_s, (255, 0, 255)),
                ("Under Bust Depth", y_under_bust_s, (0, 255, 255)),
                ("Waist Depth", y_waist_s, (0, 165, 255)),
                ("Hip Depth", y_hip_s_max, (0, 0, 255))
            ]
            
            for label, y_level, color in levels_side:
                if 0 <= y_level < h:
                    # Find width of mask at this row
                    cols = np.where(mask[y_level, :] > 0)[0]
                    if len(cols) > 0:
                        x_left, x_right = np.min(cols), np.max(cols)
                        # Draw measured depth bar
                        cv2.line(overlay, (x_left, y_level), (x_right, y_level), color, 3)
                        cv2.circle(overlay, (x_left, y_level), 4, color, -1)
                        cv2.circle(overlay, (x_right, y_level), 4, color, -1)
                        cv2.putText(overlay, label, (x_left - 10 if x_left > 120 else 10, y_level - 6),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1, cv2.LINE_AA)

        # 3. Draw Skeleton Joints and Connections
        # MediaPipe connections for standard body joints
        connections = [
            (11, 12), # Shoulder to Shoulder
            (11, 13), (13, 15), # Left Arm
            (12, 14), (14, 16), # Right Arm
            (11, 23), (12, 24), # Torso sides
            (23, 24), # Hip to Hip
            (23, 25), (25, 27), # Left Leg
            (24, 26), (26, 28)  # Right Leg
        ]
        
        # Draw connection lines
        for start_idx, end_idx in connections:
            if start_idx < len(landmarks) and end_idx < len(landmarks):
                p1 = to_px(landmarks[start_idx])
                p2 = to_px(landmarks[end_idx])
                # Neon cyan skeleton lines
                cv2.line(overlay, p1, p2, (255, 255, 0), 2, cv2.LINE_AA)
                
        # Draw joint circles
        joint_indices = [11, 12, 13, 14, 15, 16, 23, 24, 25, 26, 27, 28]
        for idx in joint_indices:
            if idx < len(landmarks):
                pt = to_px(landmarks[idx])
                # Green glowing joints
                cv2.circle(overlay, pt, 5, (0, 255, 0), -1, cv2.LINE_AA)
                cv2.circle(overlay, pt, 7, (255, 255, 255), 1, cv2.LINE_AA)

    # 4. Encode to Base64 PNG
    _, buffer = cv2.imencode('.png', overlay)
    img_base64 = base64.b64encode(buffer).decode('utf-8')
    return f"data:image/png;base64,{img_base64}"
