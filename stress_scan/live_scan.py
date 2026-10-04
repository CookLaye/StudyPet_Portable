"""
Live (in-app) facial stress scan.

Why this file exists
--------------------
stress_scan/test_stress_scan.py is a command-line tool: it opens OpenCV windows,
prints, and calls sys.exit() on errors. None of that is allowed inside the
Tkinter app (sys.exit in a worker thread silently kills the thread, cv2.imshow
fights with Tk). This module re-uses the SAME perception / scoring / baseline /
config code, but:

  * runs the scan in a background thread (Tk main thread is never blocked),
  * never prints-and-exits: problems become a result dict with status "error"
    or "unreliable",
  * exposes a thread-safe snapshot() the Tk window polls with after(),
  * can be stopped at any time (close button) and always releases the camera.

Nothing outside this file is modified by it. Tk is NOT imported here.

Usage from Tk (main thread)
---------------------------
    scanner = LiveScanner()
    scanner.start()
    ...every ~66 ms:  snap = scanner.snapshot()
        snap["phase"]      "idle" | "loading" | "scanning" | "done" | "error" | "stopped"
        snap["message"]    short human text for the current phase
        snap["time_left"]  int seconds left (only meaningful while scanning)
        snap["face_found"] bool
        snap["frame_rgb"]  numpy HxWx3 uint8 (already mirrored, preview-sized) or None
        snap["result"]     None until phase is "done"/"error", then a dict (below)
    ...on close:      scanner.stop()

Result dict
-----------
    {"status": "ok",         "score": 0-100 int, "band": "Calm|Tense|Stressed",
     "confidence": float, "face_ratio": float, "emotion_samples": int,
     "calibrated": bool, "top_cues": [...], "features": {...}}
    {"status": "unreliable", "reason": str, "face_ratio": float, "emotion_samples": int}
    {"status": "error",      "error_kind": "camera"|"models"|"exception", "message": str}
"""

import os
import sys
import threading
import time

# STUDYPET-LAUNCHER-FIX
# Must be set BEFORE cv2 is imported anywhere in the process. With Windows' Media Foundation camera
# backend, "hardware transforms" can make opening a webcam take 30+ seconds or fail on some laptops.
os.environ.setdefault("OPENCV_VIDEOIO_MSMF_ENABLE_HW_TRANSFORMS", "0")

from . import config

PREVIEW_SIZE = (640, 480)   # (width, height) of the frames handed to the UI (4:3, = a typical webcam frame)

OPEN_READ_TRIES = 20        # frames to try (0.1 s apart) before a camera/backend is declared dead
BLACK_FRAME_MEAN = 1.0      # a frame whose average brightness (0-255) is below this counts as black
MAX_FAILED_READS = 20       # consecutive failed reads during a scan before giving up (about 1 s)


class CameraUnavailableError(Exception):
    """No webcam could be opened / read."""


class ModelsMissingError(Exception):
    """A model file is missing and could not be downloaded."""


# --------------------------------------------------------------------------
# Models
# --------------------------------------------------------------------------

def _model_files():
    return {
        "face_landmarker.task": config.FACE_LANDMARKER_URL,
        "enet_b0_8_va_mtl.onnx": config.EMOTION_MODEL_URL,
    }


def models_ready():
    return all(
        os.path.exists(os.path.join(config.MODELS_DIR, name)) for name in _model_files()
    )


def _download(url, dest):
    """Download url to dest. Uses `requests` (own CA bundle, so HTTPS also works on macOS Pythons that
    have no system certificates); falls back to urllib if requests is missing."""
    try:
        import requests
    except ImportError:
        requests = None
    if requests is not None:
        headers = {"User-Agent": "StudyPet-setup", "Accept-Encoding": "identity"}
        with requests.get(url, stream=True, timeout=(15, 60), headers=headers) as response:
            response.raise_for_status()
            with open(dest, "wb") as out:
                for chunk in response.iter_content(256 * 1024):
                    if chunk:
                        out.write(chunk)
    else:
        import urllib.request
        urllib.request.urlretrieve(url, dest)


def ensure_models():
    """Download any missing model file. Raises ModelsMissingError on failure."""
    import urllib.request

    os.makedirs(config.MODELS_DIR, exist_ok=True)
    for name, url in _model_files().items():
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
        except Exception as e:  # network down, 404, disk full ...
            raise ModelsMissingError(f"Could not download {name}: {e}")
        finally:
            if os.path.exists(tmp):
                try:
                    os.remove(tmp)
                except OSError:
                    pass


# --------------------------------------------------------------------------
# Webcam
# --------------------------------------------------------------------------

def _backend_plan():
    """(name, OpenCV backend id) pairs to try on this OS, best first."""
    import cv2

    if os.name == "nt":
        # DirectShow opens fast and works for most cameras; Media Foundation rescues the cameras
        # DirectShow cannot open (and the other way round). Neither is reliable alone.
        return [("DSHOW", cv2.CAP_DSHOW), ("MSMF", cv2.CAP_MSMF), ("ANY", cv2.CAP_ANY)]
    if sys.platform == "darwin":
        return [("AVFOUNDATION", cv2.CAP_AVFOUNDATION), ("ANY", cv2.CAP_ANY)]
    return [("ANY", cv2.CAP_ANY)]


def open_webcam(log=None):
    """Open the first working camera. Raises CameraUnavailableError.

    Tries every backend for this OS with camera indexes 0, 1, 2. A camera only counts as working once it
    has delivered a real (not black) frame: many webcams "open" fine and then deliver nothing for the
    first second or two, which is what made the old single-read check unreliable.
    `log` is an optional print-like function that receives one line per attempt (used by camera_check).
    """
    import cv2

    def say(message):
        if log:
            log(message)

    saw_black = False
    for name, backend in _backend_plan():
        for idx in (0, 1, 2):
            cap = cv2.VideoCapture(idx, backend)
            if not cap.isOpened():
                cap.release()
                say(f"  {name:13s} index {idx}: could not open")
                continue
            if name == "DSHOW":
                # MJPG avoids the slow / black-frame behaviour many USB cameras show in their default mode.
                cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

            got_frame = False
            for _ in range(OPEN_READ_TRIES):
                ok, frame = cap.read()
                if ok and frame is not None and frame.size:
                    got_frame = True
                    if float(frame.mean()) > BLACK_FRAME_MEAN:
                        say(f"  {name:13s} index {idx}: OK")
                        return cap
                time.sleep(0.1)
            cap.release()
            if got_frame:
                saw_black = True
                say(f"  {name:13s} index {idx}: opened, but only black frames")
            else:
                say(f"  {name:13s} index {idx}: opened, but delivered no frames")

    if saw_black:
        raise CameraUnavailableError(
            "The camera opens but shows a black picture. Check that its cover / privacy shutter is open, "
            "there is some light, and no other app (Zoom, Teams, a browser tab) is using it.")
    if os.name == "nt":
        hint = ("Windows: Settings -> Privacy & security -> Camera (allow desktop apps), "
                "and close any other app that uses the camera.")
    else:
        hint = ("macOS: System Settings -> Privacy & Security -> Camera (allow Terminal), "
                "and close any other app that uses the camera.")
    raise CameraUnavailableError("Could not open the camera. " + hint)


def webcam_frames(stop_event, scan_seconds, process_fps):
    """Yield (seconds_since_start, frame_bgr_mirrored) for scan_seconds. Releases camera on exit."""
    import cv2

    cap = open_webcam()          # may raise CameraUnavailableError
    try:
        for _ in range(config.WARMUP_FRAMES):   # let auto-exposure settle
            cap.read()
        interval = 1.0 / process_fps
        start = time.time()                     # timer starts AFTER warm-up
        failed_reads = 0
        while not stop_event.is_set() and (time.time() - start) < scan_seconds:
            loop_start = time.time()
            ok, frame = cap.read()
            if not ok or frame is None:
                # One dropped frame must not end the scan; only a camera that really stopped does.
                failed_reads += 1
                if failed_reads > MAX_FAILED_READS:
                    break
                time.sleep(0.05)
                continue
            failed_reads = 0
            frame = cv2.flip(frame, 1)          # mirror, like a mirror
            yield (time.time() - start, frame)
            spare = interval - (time.time() - loop_start)
            if spare > 0:
                time.sleep(spare)
    finally:
        cap.release()


# --------------------------------------------------------------------------
# Scanner
# --------------------------------------------------------------------------

class LiveScanner:
    def __init__(self, scan_seconds=None, frame_source=None):
        """
        scan_seconds: defaults to config.SCAN_SECONDS (12).
        frame_source: optional callable (stop_event, scan_seconds, process_fps)
                      -> iterator of (timestamp, frame_bgr). Defaults to the webcam.
                      Used by tests to feed an image/video instead of a camera.
        """
        self.scan_seconds = scan_seconds if scan_seconds is not None else config.SCAN_SECONDS
        self._frame_source = frame_source or webcam_frames
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._thread = None
        self._state = {
            "phase": "idle", "message": "", "time_left": int(self.scan_seconds),
            "face_found": False, "frame_rgb": None, "result": None,
        }

    # ---- public --------------------------------------------------------
    def start(self):
        if self._thread is not None:
            return
        self._thread = threading.Thread(target=self._run, name="LiveScanner", daemon=True)
        self._thread.start()

    def stop(self, timeout=3.0):
        """Ask the worker to stop and wait briefly. Safe to call many times / before start."""
        self._stop.set()
        t = self._thread
        if t is not None and t.is_alive() and t is not threading.current_thread():
            t.join(timeout)

    def snapshot(self):
        with self._lock:
            return dict(self._state)

    # ---- internals -----------------------------------------------------
    def _set(self, **kw):
        with self._lock:
            self._state.update(kw)

    def _fail(self, kind, message):
        self._set(phase="error", message=message,
                  result={"status": "error", "error_kind": kind, "message": message})

    def _run(self):
        perception = None
        frames = None
        try:
            # 1) models
            self._set(phase="loading", message="Preparing the scan...")
            if not models_ready():
                self._set(message="Downloading scan models (first time only)...")
                ensure_models()
            if self._stop.is_set():
                return self._set(phase="stopped")

            # 2) heavy imports + model load (done HERE, in the worker thread)
            import cv2
            import numpy as np
            from .perception import StressPerception
            from .scoring import aggregate_features, calculate_score, compute_confidence
            from .baseline import load_baseline

            perception = StressPerception(
                landmarker_path=os.path.join(config.MODELS_DIR, "face_landmarker.task"),
                emotion_model_path=os.path.join(config.MODELS_DIR, "enet_b0_8_va_mtl.onnx"),
                debug=False,
            )
            if self._stop.is_set():
                return self._set(phase="stopped")

            # 3) scan loop (same maths as test_stress_scan.run_scan)
            self._set(phase="scanning", message="Look at the camera and relax your face.")
            samples = []
            blink_count = 0
            last_blink = 0.0
            frames_processed = 0
            frames_with_face = 0
            first_face_t = None
            last_face_t = None

            frames = self._frame_source(self._stop, self.scan_seconds, config.PROCESS_FPS)
            for timestamp, frame in frames:
                if self._stop.is_set():
                    break
                frames_processed += 1
                sample, landmarks, face_box, _ = perception.process_frame(frame)

                if landmarks:
                    frames_with_face += 1
                    if first_face_t is None:
                        first_face_t = timestamp
                    last_face_t = timestamp

                    bs = sample.get("blendshapes", {})
                    blink_val = (bs.get("eyeBlinkLeft", 0.0) + bs.get("eyeBlinkRight", 0.0)) / 2.0
                    if blink_val > config.BLINK_THRESHOLD and last_blink <= config.BLINK_THRESHOLD:
                        blink_count += 1
                    last_blink = blink_val

                    if frames_processed % config.EMOTION_EVERY_N == 0:
                        x1, y1, x2, y2 = face_box
                        crop = frame[y1:y2, x1:x2]
                        if crop.size > 0:
                            emo = perception.run_emotion(crop)
                            p = emo["probs"]
                            sample["neg_emotion"] = p[0] + p[3] + p[6] + p[2]
                            sample["valence"] = emo["valence"]
                            sample["arousal"] = emo["arousal"]
                            samples.append(sample)
                else:
                    last_blink = 0.0

                # preview frame for the UI (RGB, small, with a thin face box)
                view = frame.copy()
                if face_box:
                    x1, y1, x2, y2 = face_box
                    cv2.rectangle(view, (x1, y1), (x2, y2), (255, 160, 0), 2)
                view = cv2.resize(view, PREVIEW_SIZE)
                view = cv2.cvtColor(view, cv2.COLOR_BGR2RGB)
                self._set(
                    frame_rgb=view,
                    face_found=bool(landmarks),
                    time_left=max(0, int(self.scan_seconds - timestamp + 0.999)),
                )

            if self._stop.is_set():
                return self._set(phase="stopped")
            if frames_processed == 0:
                return self._fail("camera", "The camera did not deliver any frames.")

            # 4) result (same rules as the CLI)
            face_duration = 0.0
            if first_face_t is not None and last_face_t is not None:
                face_duration = last_face_t - first_face_t
            blink_rate = (blink_count / (face_duration / 60.0)) if face_duration > 0 else 0.0
            features = aggregate_features(samples, blink_rate)

            face_ratio = frames_with_face / frames_processed
            baseline = load_baseline(config.BASELINE_PATH)
            conf, reason = compute_confidence(face_ratio, len(samples), baseline is not None)

            if reason:
                result = {"status": "unreliable", "reason": reason,
                          "face_ratio": face_ratio, "emotion_samples": len(samples)}
                return self._set(phase="done", message="Scan unreliable", result=result)

            res = calculate_score(features, baseline, config.DEFAULT_BASELINE, config.WEIGHTS)
            result = {
                "status": "ok",
                "score": res["score"], "band": res["band"],
                "confidence": conf, "face_ratio": face_ratio,
                "emotion_samples": len(samples),
                "calibrated": res["calibrated"], "top_cues": res["top_cues"],
                "features": features,
            }
            self._set(phase="done", message="Scan complete", result=result)

        except CameraUnavailableError as e:
            self._fail("camera", str(e))
        except ModelsMissingError as e:
            self._fail("models", str(e))
        except Exception as e:  # never let the worker die silently
            self._fail("exception", f"{type(e).__name__}: {e}")
        finally:
            if frames is not None and hasattr(frames, "close"):
                try:
                    frames.close()          # runs webcam_frames' finally -> cap.release()
                except Exception:
                    pass
            if perception is not None:
                try:
                    perception.landmarker.close()
                except Exception:
                    pass
