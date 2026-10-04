import numpy as np
from typing import Dict, List, Tuple, Optional, Any
from . import config

# Spec Step 6: Scoring logic (pure functions)

def aggregate_features(samples: List[Dict[str, float]], blink_rate: float) -> Dict[str, float]:
    """
    Take the median over all samples in the window.
    """
    if not samples:
        return {}

    # Extract all keys except 'blendshapes'
    keys = [k for k in samples[0].keys() if k != 'blendshapes']
    aggregated = {}
    for key in keys:
        values = [s[key] for s in samples]
        aggregated[key] = float(np.median(values))

    aggregated['blink_rate'] = blink_rate
    return aggregated

def calculate_score(
    features: Dict[str, float],
    baseline: Optional[Dict[str, float]],
    default_baseline: Dict[str, float] = config.DEFAULT_BASELINE,
    weights: Dict[str, float] = config.WEIGHTS
) -> Dict[str, Any]:
    """
    Turns aggregated features into a tension score (0-100), band, and confidence.
    """
    if not features:
        # Return minimal dict without 'calibrated' to avoid KeyError in caller
        return {"band": "UNRELIABLE", "score": None}

    # Spec Step 6: Baseline delta
    calibrated = baseline is not None
    base = baseline if calibrated else default_baseline

    deltas = {}
    for key, val in features.items():
        base_val = base.get(key, 0.0)
        deltas[key] = val - base_val

    # Spec Step 6: Components (clipped 0..1)
    c_negemo = np.clip(deltas.get('neg_emotion', 0.0) / config.DIV_NEGEMO, 0, 1)
    c_valence = np.clip(-deltas.get('valence', 0.0) / config.DIV_VALENCE, 0, 1)
    c_arousal = np.clip(deltas.get('arousal', 0.0) / config.DIV_AROUSAL, 0, 1)
    c_brow = np.clip(deltas.get('brow_down', 0.0) / config.DIV_BROW, 0, 1)
    c_squint = np.clip(deltas.get('eye_squint', 0.0) / config.DIV_SQUINT, 0, 1)
    c_press = np.clip(deltas.get('mouth_press', 0.0) / config.DIV_PRESS, 0, 1)
    c_frown = np.clip(deltas.get('mouth_frown', 0.0) / config.DIV_FROWN, 0, 1)
    c_blink = np.clip(deltas.get('blink_rate', 0.0) / config.DIV_BLINK, 0, 1)

    components = {
        "negemo": c_negemo,
        "valence": c_valence,
        "arousal": c_arousal,
        "brow": c_brow,
        "squint": c_squint,
        "press": c_press,
        "frown": c_frown,
        "blink": c_blink
    }

    # Spec Step 6: Weighted Score
    score_val = sum(weights[name] * components[name] for name in weights)
    final_score = int(round(100 * score_val))

    # Spec Step 6: Bands
    if final_score <= config.BAND_CALM_MAX:
        band = "Calm"
    elif final_score <= config.BAND_TENSE_MAX:
        band = "Tense"
    else:
        band = "Stressed"

    # Top cues: components with value > 0, top 2
    weighted_comps = {name: weights[name] * components[name] for name in weights}
    # Only include those with value > 0
    positive_cues = {k: v for k, v in weighted_comps.items() if v > 0}
    top_cues = sorted(positive_cues, key=positive_cues.get, reverse=True)[:2]

    return {
        "score": final_score,
        "band": band,
        "components": components,
        "top_cues": top_cues,
        "calibrated": calibrated
    }

def compute_confidence(face_ratio: float, emotion_samples: int, calibrated: bool) -> Tuple[float, Optional[str]]:
    """
    Spec Step 6: Confidence and Reliability rules.
    """
    if face_ratio < config.MIN_FACE_RATIO or emotion_samples < config.MIN_EMOTION_SAMPLES:
        reason = f"face visible in only {int(face_ratio*100)}% of frames" if face_ratio < config.MIN_FACE_RATIO else f"only {emotion_samples} emotion samples"
        return 0.0, reason

    sample_factor = min(1.0, emotion_samples / config.SAMPLE_FACTOR_DIV)
    confidence = min(face_ratio, sample_factor) * (1.0 if calibrated else 0.7)

    return confidence, None
