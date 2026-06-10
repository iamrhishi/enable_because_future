"""
Heuristic check that an uploaded image likely contains a human (avatar), not only objects.

Uses OpenCV Haar cascades for faces and HOG detectors for upright people when no face passes.
Runs on raw upload bytes before rembg (face must be visible in the photo).
"""

from __future__ import annotations

from io import BytesIO
from typing import Optional

import numpy as np

from shared.logger import logger


# Face box must occupy at least this fraction of the image area (handles distant selfies).
_FACE_MIN_AREA_RATIO = 0.0009
# Ignore tiny detections typical of JPEG noise while keeping toddlers / webcam shots usable.
_ABS_MIN_FACE_PX = 22

# Default HOG people detector expects an upright pedestrian; loosen score for mirror / crop shots.
_HOG_WEIGHT_MIN = 0.52
_HOG_MIN_AREA_RATIO = 0.10


def reject_message_if_avatar_not_person(image_bytes: bytes, enabled: Optional[bool] = None) -> Optional[str]:
    """
    Returns None when the upload is acceptable as a person's photo.
    Returns a human-readable error string otherwise.

    Args:
        image_bytes: Original file bytes before background removal.
        enabled: Override config (default reads Config.AVATAR_PERSON_CHECK_ENABLED).
    """
    if enabled is False:
        return None

    if enabled is None:
        try:
            from config import Config
            enabled = Config.AVATAR_PERSON_CHECK_ENABLED
        except Exception:
            enabled = True

    if not enabled:
        return None

    try:
        import cv2  # type: ignore
    except ImportError:
        logger.warning(
            'avatar_person_check: OpenCV not installed — skipping person check. '
            'Install opencv-python-headless to enforce, or set AVATAR_PERSON_CHECK_ENABLED=false.',
        )
        return None

    img = cv2.imdecode(np.frombuffer(image_bytes, dtype=np.uint8), cv2.IMREAD_COLOR)
    if img is None or img.size == 0:
        try:
            from PIL import Image
            pil = Image.open(BytesIO(image_bytes))
            pil = pil.convert('RGB')
            rgb = np.asarray(pil)
            img = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
        except Exception as ex:
            logger.warning(f'avatar_person_check: decode failed: {ex}')
            return 'Could not read this image file. Upload a JPG, PNG, or WEBP photo.'

    h0, w0 = img.shape[:2]

    max_dim = 960
    if max(h0, w0) > max_dim:
        scale = max_dim / max(h0, w0)
        img = cv2.resize(
            img,
            (max(1, int(w0 * scale)), max(1, int(h0 * scale))),
            interpolation=cv2.INTER_AREA,
        )
    h, w = img.shape[:2]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    frontal_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
    frontal = cv2.CascadeClassifier(frontal_path)

    profile_path = cv2.data.haarcascades + 'haarcascade_profileface.xml'
    profile = cv2.CascadeClassifier(profile_path)

    if frontal.empty() or profile.empty():
        logger.error('avatar_person_check: cascades failed to load')
        return 'Avatar validation is misconfigured. Please contact support.'

    min_size = (
        max(_ABS_MIN_FACE_PX, min(w, h) // 55),
        max(_ABS_MIN_FACE_PX, min(w, h) // 55),
    )

    def _count_meaningful_faces(faces) -> int:
        if faces is None or len(faces) == 0:
            return 0
        img_area = float(w * h)
        count = 0
        for (_, _, fw, fh) in faces:
            if fw * fh / img_area >= _FACE_MIN_AREA_RATIO:
                count += 1
        return count

    # Detect faces
    faces_f = frontal.detectMultiScale(gray, scaleFactor=1.08, minNeighbors=4, minSize=min_size)
    faces_p = profile.detectMultiScale(gray, scaleFactor=1.08, minNeighbors=4, minSize=min_size)
    total_faces = _count_meaningful_faces(faces_f) + _count_meaningful_faces(faces_p)

    # Detect full bodies via HOG
    hog = cv2.HOGDescriptor()
    hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())
    rects, weights = hog.detectMultiScale(img, winStride=(8, 8), padding=(24, 24), scale=1.035)

    valid_bodies = 0
    if weights is not None and len(rects) > 0:
        flat = weights.flatten().tolist()
        img_area_f = float(w * h)
        for rect, wt in zip(rects, flat):
            if wt < _HOG_WEIGHT_MIN:
                continue
            rx, ry, rw, rh = rect
            if rw * rh / img_area_f < _HOG_MIN_AREA_RATIO:
                continue
            valid_bodies += 1

    logger.info(f'avatar_person_check: faces={total_faces}, bodies={valid_bodies}')

    # Reject multiple people (collage/group photo)
    if total_faces > 1 or valid_bodies > 1:
        return (
            'Please upload a photo with only one person. '
            'Collages, group photos, or composite images cannot be used as avatars.'
        )

    # Reject head-only (face detected but no body)
    if total_faces >= 1 and valid_bodies == 0:
        return (
            'Please upload a full-body photo, not just your face. '
            'Try-on requires seeing your full figure to dress you virtually.'
        )

    # Accept: has body (with or without visible face)
    if valid_bodies == 1:
        return None

    # No face and no body detected
    return (
        'Please upload a clear photo showing your full figure. '
        'Images of objects, pets, screenshots, or text cannot be saved as avatars.'
    )
