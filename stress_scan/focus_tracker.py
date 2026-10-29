"""
Camera side of Pomodoro focus tracking: a background thread that reads the webcam, turns frames into
observations (focus_logic), classifies them and feeds the FocusEngine.

Light by design: the preview is updated ~10x/second but the models only run ~4x/second, and the (cheap) pose
model only runs when no face is found. No emotion model. Nothing is recorded or saved.

Tests use fakes: frame_source / analyzer_factory can be injected, so no webcam or mediapipe is needed.
"""

import os
import threading
import time

from . import config
from . import focus_logic as F

PROCESS_FPS = 4.0
PREVIEW_FPS = 10.0
WARMUP_FRAMES = 5
MAX_FAILED_READS = 20

POSE_LANDMARKER_URL = getattr(
    config, "POSE_LANDMARKER_URL",
    "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/1/pose_landmarker_lite.task")


def focus_model_files():
    return {"face_landmarker.task": config.FACE_LANDMARKER_URL,
            "pose_landmarker_lite.task": POSE_LANDMARKER_URL}


def focus_models_ready():
    return all(os.path.exists(os.path.join(config.MODELS_DIR, n)) for n in focus_model_files())


def ensure_focus_models():
    """Download the face + pose landmarker files if missing (same mechanism as the stress scan models)."""
    from .live_scan import _download, ModelsMissingError
    os.makedirs(config.MODELS_DIR, exist_ok=True)
    for name, url in focus_model_files().items():
        path = os.path.join(config.MODELS_DIR, name)
        if os.path.exists(path):
            continue
        tmp = path + ".part"
        try:
            _download(url, tmp)
            if os.path.getsize(tmp) < 1_000_000:
                raise ModelsMissingError(f"Downloaded {name} is too small")
            os.replace(tmp, path)
        except ModelsMissingError:
            raise
        except Exception as e:
            raise ModelsMissingError(f"Could not download {name}: {e}")
        finally:
            if os.path.exists(tmp):
                try:
                    os.remove(tmp)
                except OSError:
                    pass


# --------------------------------------------------------------------------------------------------------------
# Real analyzer (needs cv2 + mediapipe; imported lazily so the rest of the module stays testable)
# --------------------------------------------------------------------------------------------------------------
class FocusAnalyzer:
    def __init__(self):
        import cv2
        import mediapipe as mp
        from mediapipe.tasks import python
        from mediapipe.tasks.python import vision
        self._cv2, self._mp = cv2, mp
        face_opts = vision.FaceLandmarkerOptions(
            base_options=python.BaseOptions(model_asset_path=os.path.join(config.MODELS_DIR, "face_landmarker.task")),
            num_faces=1, output_face_blendshapes=True)
        pose_opts = vision.PoseLandmarkerOptions(
            base_options=python.BaseOptions(model_asset_path=os.path.join(config.MODELS_DIR, "pose_landmarker_lite.task")),
            num_poses=1)
        self._face = vision.FaceLandmarker.create_from_options(face_opts)
        self._pose = vision.PoseLandmarker.create_from_options(pose_opts)

    def analyze(self, frame_bgr):
        cv2, mp = self._cv2, self._mp
        dark = float(frame_bgr.mean()) < F.DARK_MEAN
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        result = self._face.detect(image)
        if result.face_landmarks:
            ratios = F.head_ratios(result.face_landmarks[0])
            if ratios is not None:
                bs = {b.category_name: b.score for b in (result.face_blendshapes[0] if result.face_blendshapes else [])}
                eyes = (bs.get("eyeBlinkLeft", 0.0) + bs.get("eyeBlinkRight", 0.0)) / 2.0
                return {"face": True, "yaw": ratios[0], "pitch": ratios[1], "eyes_closed": eyes,
                        "body": True, "dark": dark}
        pose = self._pose.detect(image)                       # no face: is the body still at the desk?
        body = bool(pose.pose_landmarks) and F.body_present(pose.pose_landmarks[0])
        return {"face": False, "yaw": None, "pitch": None, "eyes_closed": 0.0, "body": body, "dark": dark}

    def close(self):
        for m in (self._face, self._pose):
            try:
                m.close()
            except Exception:
                pass


def webcam_stream(stop_event):
    """Yield (monotonic_time, mirrored_bgr_frame) until stop_event is set. Always releases the camera."""
    import cv2
    from .live_scan import open_webcam
    cap = open_webcam()                                       # may raise CameraUnavailableError
    try:
        for _ in range(WARMUP_FRAMES):
            cap.read()
        failed = 0
        while not stop_event.is_set():
            ok, frame = cap.read()
            if not ok or frame is None:
                failed += 1
                if failed > MAX_FAILED_READS:
                    return
                time.sleep(0.05)
                continue
            failed = 0
            yield (time.monotonic(), cv2.flip(frame, 1))
    finally:
        cap.release()


# --------------------------------------------------------------------------------------------------------------
# Tracker thread
# --------------------------------------------------------------------------------------------------------------
class FocusTracker:
    """One tracking segment (between a Start/Resume and a Pause/Stop).

    engine       FocusEngine shared across segments (strikes survive pause/resume)
    calib_holder dict {"calib": (yaw0, pitch0) | None} shared across segments (no recalibration after a pause)
    frame_source callable(stop_event) -> iterator of (t_seconds, frame_bgr). Default: the webcam.
    analyzer_factory callable() -> object with analyze(frame_bgr)->obs and close(). Default: FocusAnalyzer.
    """

    def __init__(self, engine, calib_holder, frame_source=None, analyzer_factory=None):
        self.engine = engine
        self.calib_holder = calib_holder
        self._frame_source = frame_source or webcam_stream
        self._analyzer_factory = analyzer_factory
        self._stop = threading.Event()
        self._recalibrate = threading.Event()
        self._lock = threading.Lock()
        self._thread = None
        self._events = []
        self._state = {"phase": "idle", "message": "", "frame_rgb": None, "state": None, "attention": None,
                       "strikes": engine.strikes, "max_strikes": engine.max_strikes, "calib_progress": 0.0,
                       "signals": {}}

    # ---- public ----
    def start(self):
        if self._thread is None:
            self._thread = threading.Thread(target=self._run, name="FocusTracker", daemon=True)
            self._thread.start()

    def stop(self, timeout=3.0):
        self._stop.set()
        t = self._thread
        if t is not None and t.is_alive() and t is not threading.current_thread():
            t.join(timeout)

    def request_recalibration(self):
        self._recalibrate.set()

    def snapshot(self):
        with self._lock:
            return dict(self._state)

    def pop_events(self):
        with self._lock:
            ev, self._events = self._events, []
        return ev

    # ---- internals ----
    def _set(self, **kw):
        with self._lock:
            self._state.update(kw)

    def _fail(self, message):
        self._set(phase="error", message=message)

    def _run(self):
        analyzer = None
        try:
            if self._analyzer_factory is None and not focus_models_ready():
                self._set(phase="loading", message="Downloading focus models (first time only)...")
                ensure_focus_models()
            if self._stop.is_set():
                return self._set(phase="stopped")
            self._set(phase="starting", message="Starting camera...")
            analyzer = (self._analyzer_factory or FocusAnalyzer)()
            self._loop(analyzer)
        except Exception as e:                       # camera busy / models missing / anything else
            self._fail(str(e) or e.__class__.__name__)
        finally:
            if analyzer is not None:
                try:
                    analyzer.close()
                except Exception:
                    pass
            if self._state.get("phase") != "error":
                self._set(phase="stopped")

    def _loop(self, analyzer):
        calibrator = F.Calibrator()
        calib_started = None
        last_analysis = 0.0
        last_preview = 0.0
        self.engine.resume(time.monotonic())
        if self.calib_holder.get("calib") is None:
            self._set(phase="calibrating", message="Look at your screen so I can calibrate...")

        for t, frame in self._frame_source(self._stop):
            if self._stop.is_set():
                break
            if t - last_preview >= 1.0 / PREVIEW_FPS:
                last_preview = t
                self._set(frame_rgb=frame[:, :, ::-1].copy())
            if t - last_analysis < 1.0 / PROCESS_FPS:
                continue
            last_analysis = t

            if self._recalibrate.is_set():
                self._recalibrate.clear()
                self.calib_holder["calib"] = None
                calibrator, calib_started = F.Calibrator(), None
                self._set(phase="calibrating", message="Look at your screen so I can calibrate...", calib_progress=0.0)

            try:
                obs = analyzer.analyze(frame)
            except Exception:
                obs = {"dark": True}                 # an analysis failure freezes the engine instead of striking

            calib = self.calib_holder.get("calib")
            if calib is None:                        # ---- calibration: no judging, no strikes
                if obs.get("face") and obs.get("yaw") is not None:
                    if calib_started is None:
                        calib_started = t
                    calibrator.add(obs["yaw"], obs["pitch"])
                progress = 0.0 if calib_started is None else min(1.0, (t - calib_started) / F.CALIBRATION_SECONDS)
                self._set(calib_progress=progress, signals={"face": bool(obs.get("face"))})
                if calib_started is not None and (t - calib_started) >= F.CALIBRATION_SECONDS and calibrator.ready:
                    self.calib_holder["calib"] = calibrator.result()
                    self.engine.resume(time.monotonic())
                    self._set(phase="tracking", message="", calib_progress=1.0)
                continue

            state = F.classify(obs, calib)
            events = self.engine.update(time.monotonic(), state)
            signals = {"face": bool(obs.get("face")), "body": bool(obs.get("body")), "dark": bool(obs.get("dark")),
                       "eyes": round(float(obs.get("eyes_closed", 0.0)), 2)}
            if obs.get("face") and obs.get("yaw") is not None:
                signals["dyaw"] = round(obs["yaw"] - calib[0], 3)
                signals["dpitch"] = round(obs["pitch"] - calib[1], 3)
            with self._lock:
                self._state.update(phase="tracking", state=state, attention=self.engine.attention_pct(),
                                   strikes=self.engine.strikes, signals=signals)
                self._events.extend(events)
            if self.engine.ended:
                break
