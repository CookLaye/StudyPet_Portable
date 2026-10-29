"""
Pure helpers for the "what is the model predicting right now?" read-out.

No cv2, no Tk, no camera: only plain Python + stress_scan.scoring, so everything here is unit-testable
without a webcam. live_scan.py builds a reading with build_live_reading() after every emotion-model run and
publishes it in snapshot()["live"]; stress_panels.ScanPanel draws it with the format_* helpers.

A "reading" is a plain dict (never mutated after creation - the scanner replaces it as a whole):

    {"labels": [8 names], "probs": [8 floats, sum ~1], "top_label": str, "top_prob": float 0-1,
     "valence": float, "arousal": float,
     "running_score": int 0-100 | None, "running_band": "Calm|Tense|Stressed" | None,
     "inferences": int,          # how many times the emotion model has run so far in this scan
     "samples": int}             # how many of those became scoring samples
"""

from . import config
from .scoring import aggregate_features, calculate_score

# Same order as perception.StressPerception.emotion_labels (the model's output order).
EMOTION_LABELS = ["Anger", "Contempt", "Disgust", "Fear", "Happiness", "Neutral", "Sadness", "Surprise"]

RUNNING_WINDOW = 15          # the running score uses only the most recent N samples (about 3 s of data)
RUNNING_MIN_SAMPLES = 3      # no running score before this many samples
BLINK_MIN_SECONDS = 3.0      # before this much face time the blink rate is too noisy -> use the default


def build_live_reading(probs, valence, arousal, inferences, samples, blink_rate, baseline):
    """Turn one emotion-model output into a reading dict. Never raises on odd input."""
    probs = [float(p) for p in probs]
    top = max(range(len(probs)), key=lambda i: probs[i])
    labels = EMOTION_LABELS if len(probs) == len(EMOTION_LABELS) else [str(i) for i in range(len(probs))]

    running_score = None
    running_band = None
    if len(samples) >= RUNNING_MIN_SAMPLES:
        try:
            feats = aggregate_features(samples[-RUNNING_WINDOW:], blink_rate)
            res = calculate_score(feats, baseline, config.DEFAULT_BASELINE, config.WEIGHTS)
            if res.get("score") is not None:
                running_score = int(res["score"])
                running_band = res["band"]
        except Exception:
            pass          # the read-out is diagnostics only; it must never break a scan

    return {
        "labels": list(labels), "probs": probs,
        "top_label": labels[top], "top_prob": probs[top],
        "valence": float(valence), "arousal": float(arousal),
        "running_score": running_score, "running_band": running_band,
        "inferences": int(inferences), "samples": len(samples),
    }


def running_blink_rate(blink_count, first_face_t, now_t):
    """Blinks per minute so far; falls back to the default baseline while there is too little face time."""
    if first_face_t is None:
        return config.DEFAULT_BASELINE["blink_rate"]
    seconds = now_t - first_face_t
    if seconds < BLINK_MIN_SECONDS:
        return config.DEFAULT_BASELINE["blink_rate"]
    return blink_count / (seconds / 60.0)


def format_headline(reading, face_found=True):
    """One line: what the model sees right now."""
    if reading is None:
        return "Model: waiting for the first reading..." if face_found else "Model: no face detected"
    line = f"Model sees: {reading['top_label']} {reading['top_prob'] * 100:.0f}%"
    if not face_found:
        line += "   (last reading - no face in view now)"
    return line


def format_detail(reading):
    """Second line: valence / arousal / running tension estimate / counters."""
    if reading is None:
        return ""
    if reading["running_score"] is None:
        running = "tension so far: collecting..."
    else:
        running = f"tension so far: {reading['running_score']}/100 ({reading['running_band']})"
    return (f"valence {reading['valence']:+.2f}  arousal {reading['arousal']:+.2f}  |  {running}  |  "
            f"model runs: {reading['inferences']}")


def bar_rows(reading):
    """[(short_label, prob 0-1, is_top)] for the 8 mini bars; [] when there is no reading."""
    if reading is None:
        return []
    return [(name[:3], p, name == reading["top_label"]) for name, p in zip(reading["labels"], reading["probs"])]
