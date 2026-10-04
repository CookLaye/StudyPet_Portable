import os

# Spec Step 3: All constants
# Paths
BASE_STUDYPET_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MODELS_DIR = os.path.join(BASE_STUDYPET_DIR, "assets", "models", "stress")
BASELINE_PATH = os.path.join(MODELS_DIR, "baseline.json")


# Model URLs
# Spec Step 7: Use versioned URL since it returns 200
FACE_LANDMARKER_URL = "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task"
EMOTION_MODEL_URL = "https://raw.githubusercontent.com/sb-ai-lab/EmotiEffLib/main/models/affectnet_emotions/onnx/enet_b0_8_va_mtl.onnx"

# Durations and rates
SCAN_SECONDS = 12
CALIBRATE_SECONDS = 5
PROCESS_FPS = 15
EMOTION_EVERY_N = 3

# Thresholds and Weights
BLINK_THRESHOLD = 0.5
# Component divisors (Spec Step 6)
DIV_NEGEMO = 0.6
DIV_VALENCE = 0.5
DIV_AROUSAL = 0.5
DIV_BROW = 0.3
DIV_SQUINT = 0.3
DIV_PRESS = 0.3
DIV_FROWN = 0.3
DIV_BLINK = 15.0

# Reliability thresholds (Spec Step 6)
MIN_FACE_RATIO = 0.5
MIN_EMOTION_SAMPLES = 10
SAMPLE_FACTOR_DIV = 20.0

# Band cutoffs (Spec Step 6)
BAND_CALM_MAX = 33
BAND_TENSE_MAX = 66

# Face box padding (Spec Step 5)
FACE_PADDING = 0.15

# Warm-up frames (Follow-up task)
WARMUP_FRAMES = 10

DEFAULT_BASELINE = {

    "neg_emotion": 0.0,
    "valence": 0.0,
    "arousal": 0.0,
    "brow_down": 0.0,
    "eye_squint": 0.0,
    "mouth_press": 0.0,
    "mouth_frown": 0.0,
    "blink_rate": 12.0
}

WEIGHTS = {
    "negemo": 0.20,
    "valence": 0.15,
    "arousal": 0.15,
    "brow": 0.15,
    "squint": 0.05,
    "press": 0.10,
    "frown": 0.10,
    "blink": 0.10
}
