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


# ---------------------------------------------------------------------------
# Rejection codes for structured error handling
# ---------------------------------------------------------------------------
class AvatarRejectionCode:
    HEAD_ONLY = 'HEAD_ONLY'           # Face detected but no visible body
    MULTIPLE_PEOPLE = 'MULTIPLE_PEOPLE'  # More than one person detected
    NO_PERSON = 'NO_PERSON'           # No face or body detected
    INVALID_IMAGE = 'INVALID_IMAGE'   # Could not decode image


# ---------------------------------------------------------------------------
# Detection thresholds
# ---------------------------------------------------------------------------
# Face box must occupy at least this fraction of the image area (handles distant selfies).
_FACE_MIN_AREA_RATIO = 0.0009
# Ignore tiny detections typical of JPEG noise while keeping toddlers / webcam shots usable.
_ABS_MIN_FACE_PX = 22

# If face occupies LESS than this ratio, it's clearly a full-body shot (not a selfie/head crop)
# This bypasses HOG body requirement since small face = far away = full body visible
# Increased to 10% to handle crossed-arms poses where HOG fails
_FACE_FULLBODY_THRESHOLD = 0.10

# Default HOG people detector - loosened for varied poses (crossed arms, walking, angled)
_HOG_WEIGHT_MIN = 0.35
_HOG_MIN_AREA_RATIO = 0.04


def reject_message_if_avatar_not_person(
    image_bytes: bytes,
    enabled: Optional[bool] = None,
    return_code: bool = False
):
    """
    Returns None when the upload is acceptable as a person's photo.
    Returns a human-readable error string otherwise.

    Args:
        image_bytes: Original file bytes before background removal.
        enabled: Override config (default reads Config.AVATAR_PERSON_CHECK_ENABLED).
        return_code: If True, returns (message, code) tuple instead of just message.

    Returns:
        If return_code=False: Optional[str] - error message or None
        If return_code=True: Tuple[Optional[str], Optional[str]] - (message, code) or (None, None)
    """
    def _skip():
        return (None, None) if return_code else None

    if enabled is False:
        return _skip()

    if enabled is None:
        try:
            from config import Config
            enabled = Config.AVATAR_PERSON_CHECK_ENABLED
        except Exception:
            enabled = True

    if not enabled:
        return _skip()

    try:
        import cv2  # type: ignore
    except ImportError:
        logger.warning(
            'avatar_person_check: OpenCV not installed — skipping person check. '
            'Install opencv-python-headless to enforce, or set AVATAR_PERSON_CHECK_ENABLED=false.',
        )
        return _skip()

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
            msg = 'Could not read this image file. Upload a JPG, PNG, or WEBP photo.'
            if return_code:
                return (msg, AvatarRejectionCode.INVALID_IMAGE)
            return msg

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
        # Don't block user, just skip validation
        if return_code:
            return (None, None)
        return None

    min_size = (
        max(_ABS_MIN_FACE_PX, min(w, h) // 55),
        max(_ABS_MIN_FACE_PX, min(w, h) // 55),
    )

    def _result(msg: Optional[str], code: Optional[str] = None):
        """Helper to return result in correct format based on return_code flag."""
        if return_code:
            return (msg, code)
        return msg

    img_area = float(w * h)

    def _analyze_faces(faces):
        """Returns (count, max_area_ratio) for meaningful faces."""
        if faces is None or len(faces) == 0:
            return 0, 0.0
        count = 0
        max_ratio = 0.0
        for (_, _, fw, fh) in faces:
            ratio = (fw * fh) / img_area
            if ratio >= _FACE_MIN_AREA_RATIO:
                count += 1
                max_ratio = max(max_ratio, ratio)
        return count, max_ratio

    # Detect faces
    faces_f = frontal.detectMultiScale(gray, scaleFactor=1.08, minNeighbors=4, minSize=min_size)
    faces_p = profile.detectMultiScale(gray, scaleFactor=1.08, minNeighbors=4, minSize=min_size)

    count_f, max_ratio_f = _analyze_faces(faces_f)
    count_p, max_ratio_p = _analyze_faces(faces_p)
    total_faces = count_f + count_p
    max_face_ratio = max(max_ratio_f, max_ratio_p)

    # Detect full bodies via HOG
    hog = cv2.HOGDescriptor()
    hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())
    rects, weights = hog.detectMultiScale(img, winStride=(8, 8), padding=(24, 24), scale=1.035)

    valid_bodies = 0
    if weights is not None and len(rects) > 0:
        flat = weights.flatten().tolist()
        for rect, wt in zip(rects, flat):
            if wt < _HOG_WEIGHT_MIN:
                continue
            _, _, rw, rh = rect
            if (rw * rh) / img_area < _HOG_MIN_AREA_RATIO:
                continue
            valid_bodies += 1

    logger.info(
        f'avatar_person_check: faces={total_faces}, max_face_ratio={max_face_ratio:.3f}, '
        f'bodies={valid_bodies}'
    )

    # IMPORTANT: Check multiple FACES first - face detection is reliable
    # Reject multiple faces regardless of size - even small faces in background count
    # This catches cases where second person is far away (small face)
    if total_faces > 1:
        return _result(
            'Please upload a photo with only one person. '
            'Collages, group photos, or composite images cannot be used as avatars.',
            AvatarRejectionCode.MULTIPLE_PEOPLE
        )

    # For full-body shots (small face = person far from camera), accept
    # Small face means person is far from camera = full body visible
    # HOG body detector is unreliable (false positives on shadows, patterns, etc.)
    # so we bypass the body check for confirmed single-face full-body shots
    if max_face_ratio > 0 and max_face_ratio < _FACE_FULLBODY_THRESHOLD:
        logger.info(
            f'avatar_person_check: ACCEPTED - single face with small ratio {max_face_ratio:.3f} '
            f'indicates full-body shot (bypassing unreliable body count)'
        )
        return _result(None, None)

    # For close-up shots (large face), check multiple bodies as secondary validation
    # HOG is more reliable when subjects are larger/closer
    if valid_bodies > 1 and max_face_ratio >= _FACE_FULLBODY_THRESHOLD:
        return _result(
            'Please upload a photo with only one person. '
            'Collages, group photos, or composite images cannot be used as avatars.',
            AvatarRejectionCode.MULTIPLE_PEOPLE
        )

    # Face detected - check if it's head-only or full-body
    if total_faces >= 1:
        # If face is small relative to image, it's clearly a full-body shot
        # (selfie/head-only photos have face > 5% of image area)
        if max_face_ratio < _FACE_FULLBODY_THRESHOLD:
            logger.info(
                f'avatar_person_check: ACCEPTED - small face ratio {max_face_ratio:.3f} '
                f'indicates full-body shot'
            )
            return _result(None, None)

        # Large face but body also detected - OK
        if valid_bodies >= 1:
            return _result(None, None)

        # Large face, no body detected - likely head-only selfie
        return _result(
            'Please upload a full-body photo, not just your face. '
            'Try-on requires seeing your full figure to dress you virtually.',
            AvatarRejectionCode.HEAD_ONLY
        )

    # Accept: has body (with or without visible face)
    if valid_bodies >= 1:
        return _result(None, None)

    # No face and no body detected
    return _result(
        'Please upload a clear photo showing your full figure. '
        'Images of objects, pets, screenshots, or text cannot be saved as avatars.',
        AvatarRejectionCode.NO_PERSON
    )
