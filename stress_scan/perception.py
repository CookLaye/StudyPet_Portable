import cv2
import numpy as np
import onnxruntime as ort
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
from typing import Dict, List, Tuple, Optional, Any

# Spec Step 5: Perception logic
class StressPerception:
    def __init__(self, landmarker_path: str, emotion_model_path: str, debug: bool = False):
        self.debug = debug

        # Initialize MediaPipe Face Landmarker
        base_options = python.BaseOptions(model_asset_path=landmarker_path)
        options = vision.FaceLandmarkerOptions(
            base_options=base_options,
            num_faces=1,
            output_face_blendshapes=True
        )
        self.landmarker = vision.FaceLandmarker.create_from_options(options)

        # Initialize Emotion ONNX model
        self.emotion_session = ort.InferenceSession(emotion_model_path, providers=['CPUExecutionProvider'])
        self.input_name = self.emotion_session.get_inputs()[0].name

        # Spec Step 2: Preprocessing constants
        self.img_size = 224
        self.mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
        self.std = np.array([0.229, 0.224, 0.225], dtype=np.float32)

        # Emotion classes from spec
        self.emotion_labels = [
            "Anger", "Contempt", "Disgust", "Fear",
            "Happiness", "Neutral", "Sadness", "Surprise"
        ]

    def preprocess_emotion(self, face_crop: np.ndarray) -> np.ndarray:
        # Spec Step 2: Preprocessing
        img = cv2.resize(face_crop, (self.img_size, self.img_size))
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        img = img.astype(np.float32) / 255.0
        img = (img - self.mean) / self.std
        img = img.transpose(2, 0, 1)
        img = np.expand_dims(img, axis=0)
        return img

    def run_emotion(self, face_crop: np.ndarray) -> Dict[str, Any]:
        """
        Runs the emotion model on a face crop and returns the processed results.
        """
        emotion_input = self.preprocess_emotion(face_crop)
        outputs = self.emotion_session.run(None, {self.input_name: emotion_input})[0]

        # The output shape is (1, 10). Take the first row.
        row = outputs[0]

        # Softmax over the first 8 emotion logits
        logits = row[:8]
        exp_logits = np.exp(logits - np.max(logits))
        probs = exp_logits / np.sum(exp_logits)

        # Return as plain Python floats
        return {
            "probs": [float(p) for p in probs],
            "valence": float(row[8]),
            "arousal": float(row[9])
        }

    def process_frame(self, frame_bgr: np.ndarray) -> Tuple[Optional[Dict], Optional[List], Optional[Tuple[int, int, int, int]], Optional[np.ndarray]]:
        """
        Processes a single frame to get landmarks, face box, and emotion sample.
        """
        frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame_rgb)
        result = self.landmarker.detect(mp_image)

        landmarks = None
        face_box = None
        sample = None

        if result.face_landmarks:
            face_lms = result.face_landmarks[0]
            landmarks = face_lms

            xs = [lm.x for lm in face_lms]
            ys = [lm.y for lm in face_lms]
            min_x, max_x = min(xs), max(xs)
            min_y, max_y = min(ys), max(ys)

            width = max_x - min_x
            height = max_y - min_y

            from . import config
            pad = config.FACE_PADDING
            min_x -= width * pad
            max_x += width * pad
            min_y -= height * pad
            max_y += height * pad

            min_x = max(0, min_x)
            max_x = min(1, max_x)
            min_y = max(0, min_y)
            max_y = min(1, max_y)

            h, w = frame_bgr.shape[:2]
            face_box = (int(min_x * w), int(min_y * h), int(max_x * w), int(max_y * h))

            blendshapes = result.face_blendshapes[0] if result.face_blendshapes else []
            bs_dict = {bs.category_name: bs.score for bs in blendshapes}

            def get_avg(left, right):
                return (bs_dict.get(left, 0.0) + bs_dict.get(right, 0.0)) / 2.0

            sample = {
                "brow_down": get_avg("browDownLeft", "browDownRight"),
                "eye_squint": get_avg("eyeSquintLeft", "eyeSquintRight"),
                "mouth_press": get_avg("mouthPressLeft", "mouthPressRight"),
                "mouth_frown": get_avg("mouthFrownLeft", "mouthFrownRight"),
                "blendshapes": bs_dict
            }

        return sample, landmarks, face_box, None
