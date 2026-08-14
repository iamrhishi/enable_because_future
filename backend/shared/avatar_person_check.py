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
# Raised from 0.0009 after a real wood-grain pattern (wooden chairs, no person in frame)
# cleared the old floor at ratio 0.00122 and was accepted via the small-face-ratio
# full-body bypass below. 0.003 sits well clear of that false hit while staying under
# every real distant-face ratio observed in production (0.006 and up).
_FACE_MIN_AREA_RATIO = 0.003
# Ignore tiny detections typical of JPEG noise while keeping toddlers / webcam shots usable.
_ABS_MIN_FACE_PX = 22

# If face occupies LESS than this ratio, it's clearly a full-body shot (not a selfie/head crop)
# This bypasses HOG body requirement since small face = far away = full body visible
# Increased to 10% to handle crossed-arms poses where HOG fails
_FACE_FULLBODY_THRESHOLD = 0.10

# Default HOG people detector - loosened for varied poses (crossed arms, walking, angled)
# Used only where a face was also detected (some corroborating signal already exists).
_HOG_WEIGHT_MIN = 0.35
_HOG_MIN_AREA_RATIO = 0.04

# Stricter HOG bar used when body detection is the ONLY signal (zero faces found at all).
# HOG alone is known to false-positive on non-human shapes (a real webpage screenshot
# cleared the old bodies>=1 fallback at weight=0.66/area=0.06 with no face anywhere in
# frame). Requires meaningfully stronger confidence before accepting on body alone.
_HOG_WEIGHT_MIN_SOLE = 0.80
_HOG_MIN_AREA_RATIO_SOLE = 0.08


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

    # Decode via PIL, not cv2.imdecode - confirmed via a real rejected upload
    # (an otherwise completely normal full-body iPhone photo) that cv2.imdecode
    # can decode certain JPEGs into the wrong pixel-grid orientation entirely,
    # not just "ignoring EXIF rotation" but genuinely transposed relative to
    # what every other viewer (Photos, WhatsApp, PIL itself) shows - causing
    # 0 face/body detections on a photo a human would immediately recognize as
    # fine. PIL's raw decode (deliberately *without* applying exif_transpose -
    # tested against the same real file, which showed the opposite problem:
    # its EXIF orientation tag is stale and applying it rotates an
    # already-correct image into the wrong orientation) matched what every
    # other viewer shows.
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

    def _merge_overlapping_boxes(boxes, iou_threshold=0.3):
        """Deduplicate face detection boxes across frontal and profile cascades using IoU."""
        if boxes is None or len(boxes) == 0:
            return []
        box_list = [tuple(b) for b in boxes]
        box_list = sorted(box_list, key=lambda b: b[2] * b[3], reverse=True)
        merged = []
        for box in box_list:
            x1, y1, w1, h1 = box
            area1 = w1 * h1
            if area1 / img_area < _FACE_MIN_AREA_RATIO:
                continue
            duplicate = False
            for mbox in merged:
                mx, my, mw, mh = mbox
                marea = mw * mh
                ix = max(0, min(x1 + w1, mx + mw) - max(x1, mx))
                iy = max(0, min(y1 + h1, my + mh) - max(y1, my))
                inter = ix * iy
                union = area1 + marea - inter
                if union > 0 and (inter / union) > iou_threshold:
                    duplicate = True
                    break
            if not duplicate:
                merged.append(box)
        return merged

    # Detect faces. minNeighbors=5 (was 4) - confirmed via a real false-positive
    # report that 4 lets weak single-window detections through on background
    # clutter (e.g. a shelving unit's grid pattern triggered a spurious profile-
    # face hit); 5 requires more agreeing detection windows and eliminated it
    # without affecting the real face, which both cascades detect confidently.
    #
    # Profile cascade specifically uses minNeighbors=8 (not 5): a second real
    # false-positive report (an A-frame sign, caught by the profile cascade at
    # roughly the same size as the real face - a relative-size filter alone
    # couldn't distinguish them) confirmed the profile cascade is the noisier
    # of the two and needs a stricter threshold. 7 wasn't quite enough - the
    # same sign still triggered a false hit once the client-side compressed
    # version of the exact same photo was tested (different resize/JPEG
    # artifacts at a different source resolution changed the cascade's
    # response); 8 clears it while the real face's own profile-cascade
    # detection in the other report survives even up to minNeighbors=12,
    # since a genuine confident detection is far more robust than a weak
    # clutter-triggered one. Frontal stays at 5 since it has been reliable
    # and still finds the real face confidently at that level.
    raw_faces_f = frontal.detectMultiScale(gray, scaleFactor=1.08, minNeighbors=5, minSize=min_size)
    raw_faces_p = profile.detectMultiScale(gray, scaleFactor=1.08, minNeighbors=8, minSize=min_size)

    all_raw_faces = []
    if raw_faces_f is not None and len(raw_faces_f) > 0:
        all_raw_faces.extend(raw_faces_f)
    if raw_faces_p is not None and len(raw_faces_p) > 0:
        all_raw_faces.extend(raw_faces_p)

    # A real human face cannot appear in the bottom ~20% of a photo of a
    # standing person (that's floor/shoe territory) - the same real-world
    # report also showed a false-positive detection there (confirmed via the
    # actual reported image: a confident false hit at floor level survived
    # even minNeighbors=8, so raising the threshold alone wasn't enough).
    # A second real person's face in an actual group photo would be at
    # roughly the same height as the first, never down at floor level, so
    # this doesn't weaken the multi-person check itself.
    max_face_center_y = h * 0.80
    all_raw_faces = [
        (x, y, fw, fh) for (x, y, fw, fh) in all_raw_faces
        if (y + fh / 2.0) < max_face_center_y
    ]

    unique_faces = _merge_overlapping_boxes(all_raw_faces, iou_threshold=0.3)

    # Drop any candidate much smaller than the largest one found (confirmed via
    # the same false-positive report: a ceiling-mounted smoke detector was
    # picked up by the frontal cascade at ~15% of the real face's area). A
    # genuine second person's face - even one standing further back - is very
    # unlikely to be under a fifth the size of the main subject's in a normal
    # avatar photo, while tiny background fixtures/icons commonly are.
    if unique_faces:
        max_area = max(fw * fh for (_, _, fw, fh) in unique_faces)
        unique_faces = [
            (x, y, fw, fh) for (x, y, fw, fh) in unique_faces
            if (fw * fh) >= max_area * 0.20
        ]

    total_faces = len(unique_faces)
    max_face_ratio = 0.0
    for (_, _, fw, fh) in unique_faces:
        ratio = (fw * fh) / img_area
        max_face_ratio = max(max_face_ratio, ratio)

    # Detect full bodies via HOG
    hog = cv2.HOGDescriptor()
    hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())
    rects, weights = hog.detectMultiScale(img, winStride=(8, 8), padding=(24, 24), scale=1.035)

    valid_bodies = 0
    valid_bodies_sole = 0
    if weights is not None and len(rects) > 0:
        flat = weights.flatten().tolist()
        for rect, wt in zip(rects, flat):
            _, _, rw, rh = rect
            area_ratio = (rw * rh) / img_area
            if wt >= _HOG_WEIGHT_MIN and area_ratio >= _HOG_MIN_AREA_RATIO:
                valid_bodies += 1
            if wt >= _HOG_WEIGHT_MIN_SOLE and area_ratio >= _HOG_MIN_AREA_RATIO_SOLE:
                valid_bodies_sole += 1

    logger.info(
        f'avatar_person_check: unique_faces={total_faces}, max_face_ratio={max_face_ratio:.3f}, '
        f'bodies={valid_bodies}, bodies_sole={valid_bodies_sole}'
    )

    # IMPORTANT: Check multiple FACES first - face detection is reliable
    # Reject multiple faces regardless of size - even small faces in background count
    # This catches cases where second person is far away (small face)
    if total_faces > 1:
        return _result(
            'Please upload a photo with only one person. '
            'Collages, group photos, or composite images containing multiple faces cannot be used as avatars.',
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

    # Accept: has body, no face at all - HOG is the only signal here, so require the
    # stricter sole-signal bar (see _HOG_WEIGHT_MIN_SOLE / _HOG_MIN_AREA_RATIO_SOLE above)
    if valid_bodies_sole >= 1:
        return _result(None, None)

    # No face and no body detected
    return _result(
        'Please upload a clear photo showing your full figure. '
        'Images of objects, pets, screenshots, or text cannot be saved as avatars.',
        AvatarRejectionCode.NO_PERSON
    )
