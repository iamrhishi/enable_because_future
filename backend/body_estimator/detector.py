import os
import cv2
import numpy as np
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

class MediaPipeDetector:
    def __init__(self, models_dir: str = None):
        if models_dir is None:
            models_dir = os.environ.get("BODY_ESTIMATOR_MODELS_DIR")
            if not models_dir:
                # Default to backend/models directory
                models_dir = os.path.abspath(
                    os.path.join(os.path.dirname(os.path.dirname(__file__)), "models")
                )
        
        pose_path = os.path.join(models_dir, "pose_landmarker.task")
        seg_path = os.path.join(models_dir, "selfie_segmenter.tflite")
        
        if not os.path.exists(pose_path) or not os.path.exists(seg_path):
            raise FileNotFoundError(
                f"Model files not found in {models_dir}. "
                f"Ensure pose_landmarker.task and selfie_segmenter.tflite are present."
            )
        
        # Initialize Pose Landmarker options
        base_options_pose = python.BaseOptions(model_asset_path=pose_path)
        options_pose = vision.PoseLandmarkerOptions(
            base_options=base_options_pose,
            running_mode=vision.RunningMode.IMAGE,
            output_segmentation_masks=False
        )
        self.pose_landmarker = vision.PoseLandmarker.create_from_options(options_pose)
        
        # Initialize Image Segmenter options
        base_options_seg = python.BaseOptions(model_asset_path=seg_path)
        options_seg = vision.ImageSegmenterOptions(
            base_options=base_options_seg,
            running_mode=vision.RunningMode.IMAGE,
            output_category_mask=True
        )
        self.image_segmenter = vision.ImageSegmenter.create_from_options(options_seg)

    def detect(self, image_np: np.ndarray):
        """
        Runs pose landmarking and selfie segmentation on the input BGR image.
        Returns:
            pose_landmarks: MediaPipe normalized landmarks list (or None if not detected)
            segmentation_mask: uint8 binary mask (255 for person, 0 for background)
            visibility_scores: list of landmark visibilities (empty if no pose)
        """
        # Ensure contiguous array in RGB format
        rgb_image = cv2.cvtColor(image_np, cv2.COLOR_BGR2RGB)
        rgb_image = np.ascontiguousarray(rgb_image)
        
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_image)
        
        # 1. Pose Landmark Detection
        pose_result = self.pose_landmarker.detect(mp_image)
        pose_landmarks = None
        visibility_scores = []
        if pose_result.pose_landmarks:
            pose_landmarks = pose_result.pose_landmarks[0]
            # Key landmarks for measurement
            visibility_scores = [lm.visibility for lm in pose_landmarks]
            
        # 2. Image Segmentation
        seg_result = self.image_segmenter.segment(mp_image)
        category_mask = seg_result.category_mask.numpy_view()
        
        # Convert category mask to binary mask (255 for foreground person, 0 for background)
        # In this environment, the person is labeled as index 0 and the background is 255.
        binary_mask = (category_mask == 0).astype(np.uint8) * 255
        
        # Post-process mask: close holes and remove small noise
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        binary_mask = cv2.morphologyEx(binary_mask, cv2.MORPH_CLOSE, kernel)
        binary_mask = cv2.morphologyEx(binary_mask, cv2.MORPH_OPEN, kernel)
        
        return pose_landmarks, binary_mask, visibility_scores

    def close(self):
        """Close the landmarker and segmenter to release resources."""
        self.pose_landmarker.close()
        self.image_segmenter.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
