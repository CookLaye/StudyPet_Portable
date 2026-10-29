"""
Pure logic for Pomodoro focus tracking. No cv2, no mediapipe, no Tk, no camera: everything here is unit-testable.

Pipeline (the other modules only feed this one):
    camera frame -> FocusAnalyzer (focus_tracker.py) -> observation dict
    observation + calibration -> classify() -> a STATE
    STATE stream -> FocusEngine.update() -> strike events

Observation dict (one per analysed frame):
    {"face": bool, "yaw": float|None, "pitch": float|None,   # head_ratios() of the face landmarks
     "eyes_closed": float 0..1,                               # mean eyeBlinkLeft/Right blendshape
     "body": bool,                                            # pose landmarker sees shoulders / nose
     "dark": bool}                                            # frame too dark to judge

States:
    AT_SCREEN    facing the screen
    DOWN         head tilted down, or face lost while the body is still in view (reading / writing in a
                 notebook). FORGIVEN ON PURPOSE - a webcam cannot tell a notebook from a phone in the lap
                 (documented limitation in README.md). Never causes a strike.
    AWAY         head turned sideways or up
    ABSENT       no face and no body
    EYES_CLOSED  eyes closed while the head is NOT tilted down (looking down also lowers the eyelids)
    UNSURE       too dark / analysis failed: the engine freezes instead of judging
"""

from collections import deque
from statistics import median

# ---- states -----------------------------------------------------------------------------------------------
AT_SCREEN = "at_screen"
DOWN = "down"
AWAY = "away"
ABSENT = "absent"
EYES_CLOSED = "eyes_closed"
UNSURE = "unsure"

GOOD_STATES = (AT_SCREEN, DOWN)

# ---- tunables (starting values: verify with the on-screen signals line and adjust) ------------------------
ALLOWANCE = {AWAY: 12.0, ABSENT: 15.0, EYES_CLOSED: 10.0}   # seconds of CONTINUOUS distraction before a strike
COOLDOWN_SECONDS = 45.0          # minimum gap between two strikes (a distraction that continues strikes again after this)
GOOD_RESET_SECONDS = 2.0         # this long back on task forgets the running distraction timer
CALIBRATION_SECONDS = 12.0       # look at the screen this long at the start; no strikes during it
MIN_CALIBRATION_SAMPLES = 8
YAW_AWAY = 0.12                  # |yaw_ratio - calibrated|  above this -> AWAY
PITCH_UP = 0.10                  # pitch_ratio below calibrated by more than this (looking up) -> AWAY
PITCH_DOWN = 0.08                # pitch_ratio above calibrated by at least this (looking down) -> DOWN
EYES_CLOSED_SCORE = 0.60         # mean eyeBlink blendshape at/above this counts as closed
DARK_MEAN = 45.0                 # frame mean brightness (0-255) below this -> UNSURE
ATTENTION_WINDOW = 60.0          # seconds used for the rolling attention percentage
MIN_STRIKES = 3
MINUTES_PER_STRIKE = 5
MAX_GAP_SECONDS = 2.0            # a longer gap between updates is ignored (camera stall, pause) instead of counted

# MediaPipe face-mesh landmark indices used for the head ratios.
NOSE, CHEEK_L, CHEEK_R, EYE_L, EYE_R, FOREHEAD, CHIN = 1, 234, 454, 33, 263, 10, 152
# MediaPipe pose landmark indices.
POSE_NOSE, POSE_SHOULDER_L, POSE_SHOULDER_R = 0, 11, 12


def max_strikes(session_minutes):
    """Warnings allowed in a work session: minutes / 5, never fewer than 3. The last one ends the session."""
    try:
        minutes = int(session_minutes)
    except (TypeError, ValueError):
        minutes = 25
    return max(MIN_STRIKES, minutes // MINUTES_PER_STRIKE)


# ---- geometry ---------------------------------------------------------------------------------------------
def head_ratios(landmarks):
    """(yaw_ratio, pitch_ratio) from face-mesh landmarks (objects with .x/.y), or None if unusable.

    yaw_ratio   0 = nose midway between the cheeks; moves as the head turns sideways (sign not important,
                only the distance from the calibrated value is used).
    pitch_ratio nose height relative to the eye line, divided by face height; GROWS when looking down.
    Both are measured relative to the user's own calibration, so camera angle does not matter.
    """
    try:
        if len(landmarks) <= CHEEK_R:
            return None
        width = landmarks[CHEEK_R].x - landmarks[CHEEK_L].x
        height = landmarks[CHIN].y - landmarks[FOREHEAD].y
        if abs(width) < 1e-6 or abs(height) < 1e-6:
            return None
        mid_x = (landmarks[CHEEK_L].x + landmarks[CHEEK_R].x) / 2.0
        eye_y = (landmarks[EYE_L].y + landmarks[EYE_R].y) / 2.0
        return ((landmarks[NOSE].x - mid_x) / width, (landmarks[NOSE].y - eye_y) / height)
    except Exception:
        return None


def body_present(pose_landmarks, min_visibility=0.5):
    """True if the pose model sees a person: both shoulders, or the nose plus one shoulder."""
    try:
        def seen(i):
            lm = pose_landmarks[i]
            vis = getattr(lm, "visibility", 1.0)
            return (vis is None or vis >= min_visibility) and -0.05 <= lm.x <= 1.05 and -0.05 <= lm.y <= 1.05
        shoulders = [seen(POSE_SHOULDER_L), seen(POSE_SHOULDER_R)]
        return all(shoulders) or (seen(POSE_NOSE) and any(shoulders))
    except Exception:
        return False


# ---- calibration ------------------------------------------------------------------------------------------
class Calibrator:
    """Collects the user's neutral head pose while they look at the screen."""

    def __init__(self):
        self._yaw, self._pitch = [], []

    def add(self, yaw, pitch):
        if yaw is not None and pitch is not None:
            self._yaw.append(float(yaw))
            self._pitch.append(float(pitch))

    @property
    def samples(self):
        return len(self._yaw)

    @property
    def ready(self):
        return self.samples >= MIN_CALIBRATION_SAMPLES

    def result(self):
        """(yaw0, pitch0) medians (robust to a stray glance), or None while not ready."""
        if not self.ready:
            return None
        return (median(self._yaw), median(self._pitch))


# ---- classification ---------------------------------------------------------------------------------------
def classify(obs, calib):
    """Observation + calibration (yaw0, pitch0) -> state. See the module docstring."""
    if obs.get("dark"):
        return UNSURE
    if obs.get("face") and obs.get("yaw") is not None and obs.get("pitch") is not None:
        dyaw = abs(obs["yaw"] - calib[0])
        dpitch = obs["pitch"] - calib[1]
        if dpitch >= PITCH_DOWN:
            return DOWN                                   # forgiven on purpose (notebook)
        if dyaw > YAW_AWAY or dpitch <= -PITCH_UP:
            return AWAY
        if obs.get("eyes_closed", 0.0) >= EYES_CLOSED_SCORE and dpitch < PITCH_DOWN * 0.6:
            return EYES_CLOSED
        return AT_SCREEN
    # no usable face: is there still a body at the desk (head tilted down / turned)?
    return DOWN if obs.get("body") else ABSENT


# ---- strike engine ----------------------------------------------------------------------------------------
class FocusEngine:
    """Turns the state stream into strikes. Owns strike count, rolling attention and per-state seconds.

    update(t, state) returns a list of events (usually empty). A strike event is:
        {"type": "strike", "n": 2, "max": 5, "reason": AWAY, "final_warning": False, "end": False}
    "final_warning" is True on the strike before the last one; "end" is True on the last strike, after which
    the engine ignores further updates (the caller ends the session without rewards).
    """

    def __init__(self, session_minutes, now=0.0):
        self.max_strikes = max_strikes(session_minutes)
        self.strikes = 0
        self.ended = False
        self.seconds = {s: 0.0 for s in (AT_SCREEN, DOWN, AWAY, ABSENT, EYES_CLOSED, UNSURE)}
        self._last_t = now
        self._bad_since = None
        self._good_since = None
        self._last_strike_t = None
        self._history = deque()          # (t, dt, good) for the rolling attention percentage

    def resume(self, t):
        """Call when tracking restarts after a pause / recalibration: forget running timers, never punish the gap."""
        self._last_t = t
        self._bad_since = None
        self._good_since = None

    def update(self, t, state):
        if self.ended:
            return []
        dt = t - self._last_t
        self._last_t = t
        if dt < 0 or dt > MAX_GAP_SECONDS:      # camera stall / pause: do not count it, do not punish it
            dt = 0.0
            self._bad_since = None
            self._good_since = None
        self.seconds[state] = self.seconds.get(state, 0.0) + dt

        if state == UNSURE:                       # cannot judge: freeze (do not let the bad timer grow)
            if self._bad_since is not None:
                self._bad_since += dt
            return []

        good = state in GOOD_STATES
        self._history.append((t, dt, good))
        while self._history and t - self._history[0][0] > ATTENTION_WINDOW:
            self._history.popleft()

        if good:
            if self._good_since is None:
                self._good_since = t
            if t - self._good_since >= GOOD_RESET_SECONDS:
                self._bad_since = None
            return []

        self._good_since = None
        if self._bad_since is None:
            self._bad_since = t
        if t - self._bad_since < ALLOWANCE.get(state, ALLOWANCE[AWAY]):
            return []
        if self._last_strike_t is not None and t - self._last_strike_t < COOLDOWN_SECONDS:
            return []

        self.strikes += 1
        self._last_strike_t = t
        end = self.strikes >= self.max_strikes
        if end:
            self.ended = True
        return [{"type": "strike", "n": self.strikes, "max": self.max_strikes, "reason": state,
                 "final_warning": (self.strikes == self.max_strikes - 1), "end": end}]

    def attention_pct(self):
        """Rolling % of the last minute spent on task (AT_SCREEN or DOWN); None until ~5 s of data."""
        total = sum(dt for _, dt, _ in self._history)
        if total < 5.0:
            return None
        good = sum(dt for _, dt, g in self._history if g)
        return int(round(100.0 * good / total))


# ---- pet scolding text ------------------------------------------------------------------------------------
_REASON_LINES = {
    AWAY: ["{pet} saw you looking away from the screen!", "Eyes back on the screen, please!", "{pet} is watching... stay with it!"],
    ABSENT: ["{pet} can't see you at your desk!", "Hello? Where did you go? {pet} is waiting."],
    EYES_CLOSED: ["No napping! {pet} saw your eyes close.", "{pet} thinks you are falling asleep!"],
}


def scold_message(pet_name, event):
    """(title, message) for the Windows notification / speech bubble for one strike event."""
    pet = pet_name or "Your pet"
    n, total = event["n"], event["max"]
    if event.get("end"):
        return (f"{pet}: session ended ({n}/{total})",
                f"Too many distractions, so this session ends now and earns no points. Try again when you are ready!")
    lines = _REASON_LINES.get(event.get("reason"), _REASON_LINES[AWAY])
    line = lines[(n - 1) % len(lines)].format(pet=pet)
    if event.get("final_warning"):
        return (f"{pet}: LAST warning ({n}/{total})", line + " One more and the session ends with no points!")
    return (f"{pet}: focus! ({n}/{total})", line)
