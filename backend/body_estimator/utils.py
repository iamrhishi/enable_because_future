import numpy as np
import cv2

def calculate_distance(pt1, pt2):
    """Calculate Euclidean distance between two points (each has .x and .y)."""
    return np.sqrt((pt1.x - pt2.x) ** 2 + (pt1.y - pt2.y) ** 2)

def calculate_pixel_distance(pt1, pt2, w: int, h: int) -> float:
    """Calculate Euclidean distance between two normalized points in pixel coordinates."""
    x1, y1 = pt1.x * w, pt1.y * h
    x2, y2 = pt2.x * w, pt2.y * h
    return float(np.sqrt((x1 - x2) ** 2 + (y1 - y2) ** 2))

def clamp(val, min_val, max_val):
    """Clamp value between min_val and max_val."""
    return max(min_val, min(val, max_val))

def get_largest_connected_component(mask: np.ndarray) -> np.ndarray:
    """
    Extracts the single largest foreground component from the binary mask.
    This eliminates any segmented background objects or floating noise.
    """
    num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(mask)
    if num_labels <= 1:
        return mask
    # Stat index for CC_STAT_AREA is 4. Find the largest component excluding background (0)
    largest_label = 1 + np.argmax(stats[1:, cv2.CC_STAT_AREA])
    largest_mask = (labels == largest_label).astype(np.uint8) * 255
    return largest_mask

def ellipse_circumference(width: float, depth: float) -> float:
    """
    Calculates the circumference of an ellipse using Ramanujan's first approximation.
    a = semi-major axis (width / 2)
    b = semi-minor axis (depth / 2)
    """
    a = width / 2.0
    b = depth / 2.0
    if a <= 0 or b <= 0:
        return 0.0
    # Ramanujan's formula
    term = 3.0 * (a + b) - np.sqrt((3.0 * a + b) * (a + 3.0 * b))
    return np.pi * term
