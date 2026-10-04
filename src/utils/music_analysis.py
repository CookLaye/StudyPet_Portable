"""
Music analysis — cheap, pure-Python audio "intensity" features.
(see spec) No third-party imports at module level.
"""

import json
import math
import os
import time
from array import array

# ---------------------------------------------------------------- constants
ANALYSIS_VERSION = 1            # bump if the maths below changes -> cache is rebuilt
SEGMENT_SECONDS = 12            # length of each analysed excerpt
SEGMENT_POSITIONS = (0.2, 0.5, 0.8)   # where in the track the excerpts start (fraction)
ENV_HOP = 512                   # samples per loudness-envelope frame
BPM_MIN, BPM_MAX = 60, 180
MAX_ANALYSIS_FILE_BYTES = 16 * 1024 * 1024   # bigger files are skipped (RAM safety)

# Starting guesses only. Tune with:  python src/utils/music_analysis.py
BRIGHTNESS_THRESHOLD = 0.03     # ~ energy-weighted mean frequency of about 1.2 kHz
FAST_BPM_THRESHOLD = 125
MIN_PULSE_RATIO = 0.01          # below this the audio has no onsets (steady tone/pad): no BPM
MIN_TEMPO_STRENGTH = 0.30       # ignore the BPM figure if the beat is not clear
LOUDNESS_THRESHOLD_DBFS = -10.0 # RMS level; very loud masters


def _yield():
    """Give the Tk main thread a slice of the GIL."""
    time.sleep(0.02)


def _segment_to_mono(raw, frame_start, frame_end, channels):
    bytes_per_frame = 2 * channels
    chunk = raw[frame_start * bytes_per_frame: frame_end * bytes_per_frame]
    a = array('h')
    a.frombytes(chunk[: len(chunk) - (len(chunk) % bytes_per_frame)])
    if channels == 1:
        return a
    if channels == 2:
        return array('h', [(x + y) >> 1 for x, y in zip(a[0::2], a[1::2])])
    return a[0::channels]


def _segment_bounds(n_frames, sample_rate):
    seg = int(SEGMENT_SECONDS * sample_rate)
    if n_frames <= seg * len(SEGMENT_POSITIONS):
        return [(0, n_frames)]                      # short track: use all of it
    bounds = []
    for p in SEGMENT_POSITIONS:
        start = max(0, min(int(n_frames * p) - seg // 2, n_frames - seg))
        bounds.append((start, start + seg))
    return bounds


def analyze_pcm(raw, sample_rate, channels):
    """
    raw: bytes of signed 16-bit little-endian PCM (interleaved if stereo).
    Returns a dict of features, or None if the audio is too short/silent.
    """
    n_frames = len(raw) // (2 * channels)
    if n_frames < sample_rate * 2:
        return None

    lag_min = int(round(sample_rate / ENV_HOP * 60.0 / BPM_MAX))
    lag_max = int(round(sample_rate / ENV_HOP * 60.0 / BPM_MIN))
    ac_sum = [0.0] * (lag_max + 1)
    ac_norm = 0.0
    sum_sq = sum_diff_sq = 0.0
    total_samples = 0
    flux_mean_total = env_mean_total = 0.0
    env_segments = 0

    for (s, e) in _segment_bounds(n_frames, sample_rate):
        seg = _segment_to_mono(raw, s, e, channels)
        total_samples += len(seg)
        sum_sq += sum(x * x for x in seg)
        _yield()
        sum_diff_sq += sum((b - a) * (b - a) for a, b in zip(seg, seg[1:]))
        _yield()

        env = []
        for i in range(0, len(seg) - ENV_HOP, ENV_HOP):
            blk = seg[i:i + ENV_HOP]
            env.append(math.sqrt(sum(x * x for x in blk) / ENV_HOP))
        _yield()
        if len(env) < lag_max + 4:
            continue
        flux = [max(0.0, env[i] - env[i - 1]) for i in range(1, len(env))]
        m = sum(flux) / len(flux)
        flux_mean_total += m
        env_mean_total += sum(env) / len(env)
        env_segments += 1
        c = [f - m for f in flux]
        ac_norm += sum(v * v for v in c)
        for lag in range(lag_min, lag_max + 1):
            ac_sum[lag] += sum(c[i] * c[i - lag] for i in range(lag, len(c)))
        _yield()

    if total_samples == 0 or sum_sq == 0:
        return None

    rms = math.sqrt(sum_sq / total_samples)
    result = {
        "brightness": round(sum_diff_sq / sum_sq, 5),
        "loudness_dbfs": round(20 * math.log10(max(rms, 1.0) / 32768.0), 2),
        "bpm": None,
        "tempo_strength": 0.0,
    }
    pulse = (flux_mean_total / env_mean_total) if env_mean_total > 0 else 0.0
    if env_segments and ac_norm > 0 and pulse >= MIN_PULSE_RATIO:
        best = max(range(lag_min, lag_max + 1), key=lambda l: ac_sum[l])
        result["bpm"] = round(60.0 * sample_rate / ENV_HOP / best, 1)
        result["tempo_strength"] = round(ac_sum[best] / ac_norm, 3)
    return result


def is_intense(features):
    """Returns (bool, [reasons])."""
    if not features or features.get("error"):
        return False, []
    reasons = []
    if features["brightness"] >= BRIGHTNESS_THRESHOLD:
        reasons.append("bright")
    if (features.get("bpm") and features["bpm"] >= FAST_BPM_THRESHOLD
            and features["tempo_strength"] >= MIN_TEMPO_STRENGTH):
        reasons.append("fast")
    if features["loudness_dbfs"] >= LOUDNESS_THRESHOLD_DBFS:
        reasons.append("loud")
    return bool(reasons), reasons


# ------------------------------------------------------------ pygame wrapper
def analyze_file(path):
    """
    Decode `path` with pygame and return its feature dict.
    NEVER raises. On failure returns {"error": "<reason>"}.
    """
    try:
        if os.path.getsize(path) > MAX_ANALYSIS_FILE_BYTES:
            return {"error": "too_large"}
        import pygame
        init = pygame.mixer.get_init()
        if not init:
            return {"error": "mixer_not_ready"}
        frequency, fmt, channels = init
        if fmt != -16:
            return {"error": "unsupported_mixer_format"}
        sound = pygame.mixer.Sound(path)   # decodes the whole file to PCM in RAM
        raw = sound.get_raw()
        del sound
        features = analyze_pcm(raw, frequency, channels)
        del raw
        return features if features else {"error": "too_short_or_silent"}
    except Exception as exc:               # pygame.error, MemoryError, OSError ...
        return {"error": f"{type(exc).__name__}: {exc}"}


# ------------------------------------------------------------------- cache
class AnalysisCache:
    """
    JSON cache of raw features (NOT verdicts) so thresholds can be tuned
    without re-analysing. Keyed by file name inside the flat bgm folder.
    Entry is valid only while the file's size and mtime are unchanged.
    """

    def __init__(self, cache_path):
        import threading
        self.cache_path = cache_path
        self._lock = threading.Lock()
        self._tracks = {}
        self._load()

    def _load(self):
        try:
            with open(self.cache_path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            if data.get("version") == ANALYSIS_VERSION:
                self._tracks = data.get("tracks", {})
        except (OSError, ValueError):
            self._tracks = {}

    @staticmethod
    def _signature(path):
        st = os.stat(path)
        return st.st_size, int(st.st_mtime)

    def get(self, path):
        """Cached features for this file, or None if missing/stale."""
        try:
            size, mtime = self._signature(path)
        except OSError:
            return None
        with self._lock:
            entry = self._tracks.get(os.path.basename(path))
        if entry and entry.get("size") == size and entry.get("mtime") == mtime:
            return entry.get("features")
        return None

    def put(self, path, features):
        if features and features.get("error") == "mixer_not_ready":
            return                              # transient: do not cache
        try:
            size, mtime = self._signature(path)
        except OSError:
            return
        with self._lock:
            self._tracks[os.path.basename(path)] = {
                "size": size, "mtime": mtime, "features": features}
            self._save_locked()

    def _save_locked(self):
        tmp = self.cache_path + ".tmp"
        try:
            os.makedirs(os.path.dirname(self.cache_path), exist_ok=True)
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump({"version": ANALYSIS_VERSION, "tracks": self._tracks}, fh, indent=1)
            os.replace(tmp, self.cache_path)
        except OSError:
            pass                                # cache is best-effort


# ---------------------------------------------- calibration report (CLI tool)
if __name__ == "__main__":
    # Usage:  python src/utils/music_analysis.py
    # Prints measured features + verdict for every track in bgm/ so the
    # thresholds above can be tuned against the real library.
    import re
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")   # no sound device needed
    import pygame
    pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=4096)
    bgm = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "bgm"))
    print(f"bgm folder: {bgm}")
    print(f"{'track':38} {'bright':>8} {'bpm':>6} {'beat':>5} {'dBFS':>7}  verdict")
    for name in sorted(os.listdir(bgm)):
        if not name.lower().endswith((".mp3", ".wav", ".ogg", ".m4a")):
            continue
        if re.fullmatch(r"default_[123]", os.path.splitext(name)[0], re.I):
            print(f"{name[:38]:38} (default - never analysed, never hidden)")
            continue
        t0 = time.time()
        f = analyze_file(os.path.join(bgm, name))
        if f.get("error"):
            print(f"{name[:38]:38} ERROR: {f['error']}")
            continue
        bad, why = is_intense(f)
        print(f"{name[:38]:38} {f['brightness']:8.4f} {str(f['bpm']):>6} "
              f"{f['tempo_strength']:5.2f} {f['loudness_dbfs']:7.1f}  "
              f"{'HIDE ' + ','.join(why) if bad else 'keep'}  ({time.time()-t0:.1f}s)")
