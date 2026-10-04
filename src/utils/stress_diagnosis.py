"""
Stress diagnosis: shared state, scoring, and the DASS-21 severity bands.

Every component score lives on the DASS-21 STRESS-subscale scale, 0-42:
  * quiz      -> sum of the 7 answers (0-3 each) x 2          (official DASS-21 rule)
  * face scan -> stress_scan score (0-100) mapped linearly to 0-42
  * mailbox   -> keyword score from utils.stress_keywords (already 0-42)

The final diagnosis = average of whichever components were collected, rounded to
the nearest whole number (half rounds up), then looked up in STRESS_LEVELS.
"""

import tkinter as tk
from collections import namedtuple

from utils.stress_keywords import analyze_text as _analyze_mailbox_text

SCORE_SCALE_MAX = 42

# Bảng phân loại mức độ Stress (DASS-21, stress subscale x2)
StressLevel = namedtuple("StressLevel", "key min_score max_score label_vi label_en color")
STRESS_LEVELS = [
    StressLevel("normal",           0, 14, "Bình thường",      "Normal",           "#2E9E5B"),
    StressLevel("mild",            15, 18, "Nhẹ",              "Mild",             "#8BB82E"),
    StressLevel("moderate",        19, 25, "Vừa (Trung bình)", "Moderate",         "#E0A100"),
    StressLevel("severe",          26, 33, "Nặng",             "Severe",           "#E06A1F"),
    StressLevel("extremely_severe", 34, 42, "Rất nặng",        "Extremely severe", "#D03030"),
]

# A rounded score at or above this recommends a stress-relief session
# (= the bottom of the "Mild" band). Anything below suggests a study/work session.
STRESS_RELIEF_THRESHOLD = 15

# ---- Start-up gate policy -----------------------------------------------------
# After a stressed start-up diagnosis the user does a breathing exercise and is
# re-diagnosed. The second result decides what the main screen offers:
#   normal                          -> "full"       (everything, like today)
#   improved but still stressed     -> "full" if IMPROVED_UNLOCKS_FULL_ACCESS else "restricted"
#   same band or worse              -> "restricted" (calm features only)
IMPROVED_UNLOCKS_FULL_ACCESS = True


def level_index(score):
    """0 (Bình thường) .. 4 (Rất nặng) for any 0-42 score."""
    key = classify_stress(score).key
    return [lvl.key for lvl in STRESS_LEVELS].index(key)


def decide_access(first_score, second_score):
    """'full' or 'restricted' from the start-up score and the re-diagnosis score."""
    if round_score(second_score) < STRESS_RELIEF_THRESHOLD:
        return "full"
    if IMPROVED_UNLOCKS_FULL_ACCESS and level_index(second_score) < level_index(first_score):
        return "full"
    return "restricted"


# The 7 DASS-21 stress-subscale items (as provided), 0-3 each.
QUIZ_QUESTIONS = [
    "Tôi nhận thấy bản thân khó mà nghỉ ngơi",
    "Tôi đã phản ứng cách quá lố khi có những sự việc xảy ra",
    "Tôi thấy mình đã dùng quá nhiều năng lực vào việc lo lắng",
    "Tôi thấy bồn chồn",
    "Tôi thấy khó mà thư giãn",
    "Tôi thấy thiếu kiên nhẫn với những điều cản trở việc tôi đang làm",
    "Tôi thấy mình rất dễ nhạy cảm",
]

# Generic 0-3 response labels (placeholder wording - swap in the official
# DASS-21 anchor phrasing later if Rilay wants the exact standard wording).
QUIZ_RESPONSE_LABELS = [
    (0, "Không đúng với tôi"),
    (1, "Thỉnh thoảng đúng"),
    (2, "Thường xuyên đúng"),
    (3, "Hầu như luôn đúng"),
]


# --------------------------------------------------------------------------
# Scoring helpers (all return floats on the 0-42 scale, or None for "no score")
# --------------------------------------------------------------------------

def round_score(value):
    """Round a 0-42 score to a whole number (x.5 rounds UP) and clamp to 0..42."""
    return max(0, min(SCORE_SCALE_MAX, int(value + 0.5)))


def classify_stress(score):
    """Map any 0-42 score (float ok) to its StressLevel row."""
    n = round_score(score)
    for level in STRESS_LEVELS:
        if level.min_score <= n <= level.max_score:
            return level
    return STRESS_LEVELS[-1]  # unreachable thanks to the clamp; kept for safety


def score_quiz(answers):
    """answers: list of 7 ints, each 0-3. Official DASS-21 rule: sum x 2 -> 0-42."""
    return float(sum(answers) * 2)


def score_facial_scan(scan_result):
    """
    scan_result: the dict returned by stress_scan.live_scan.LiveScanner
    (keys used: 'status' and 'score'). Returns a float 0-42, or None when the
    scan was unreliable / failed / skipped (None means "not counted in the average").
    """
    if not scan_result or scan_result.get("status") != "ok":
        return None
    raw = scan_result.get("score")  # 0-100 from stress_scan.scoring
    if raw is None:
        return None
    raw = max(0.0, min(100.0, float(raw)))
    return raw / 100.0 * SCORE_SCALE_MAX


def analyze_mailbox(letter_text):
    """Returns (score 0-42, crisis_flag). crisis_flag = a self-harm/suicide phrase was found."""
    result = _analyze_mailbox_text(letter_text)
    return result["score"], bool(result["crisis"])


def score_mailbox(letter_text):
    """Keyword-based score (English + Vietnamese) for the mailbox letter, 0-42."""
    return analyze_mailbox(letter_text)[0]


# --------------------------------------------------------------------------
# Shared state
# --------------------------------------------------------------------------

class StressDiagnosisState:
    """
    Holds whichever component scores have been collected so far this app
    session. Not persisted to disk - recreated each time the app starts.
    """

    def __init__(self):
        self.facial_scan_score = None   # float 0-42 or None
        self.quiz_score = None          # float 0-42 or None
        self.mailbox_score = None       # float 0-42 or None
        self.mailbox_crisis = False     # True if the letter contained a self-harm/suicide phrase

    def components(self):
        """Ordered dict-like list of (name, score) for the components that are set."""
        pairs = [
            ("scan", self.facial_scan_score),
            ("quiz", self.quiz_score),
            ("mailbox", self.mailbox_score),
        ]
        return [(name, v) for name, v in pairs if v is not None]

    def has_any(self):
        return bool(self.components())

    def average(self):
        """Average (0-42, float) of whichever components are set. None if nothing set."""
        present = [v for _, v in self.components()]
        if not present:
            return None
        return sum(present) / len(present)

    def rounded_average(self):
        avg = self.average()
        return None if avg is None else round_score(avg)

    def level(self):
        """StressLevel for the current average, or None if nothing is set."""
        avg = self.average()
        return None if avg is None else classify_stress(avg)

    def is_stressed(self):
        """True when the rounded average is at/above STRESS_RELIEF_THRESHOLD."""
        n = self.rounded_average()
        return n is not None and n >= STRESS_RELIEF_THRESHOLD

    def recommendation(self):
        """Returns 'relief' or 'study', or None if no score yet."""
        n = self.rounded_average()
        if n is None:
            return None
        return "relief" if n >= STRESS_RELIEF_THRESHOLD else "study"


# --------------------------------------------------------------------------
# Shared result UI
# --------------------------------------------------------------------------

_COMPONENT_NAMES = {"scan": "Face scan", "quiz": "Quiz", "mailbox": "Mailbox"}

# Shown (only) when the mailbox letter contained a self-harm / suicide phrase.
# 111 = Vietnam's national child protection hotline (free, 24/7, offers counselling).
SUPPORT_TEXT = (
    "If you ever feel unsafe or think about hurting yourself, please tell a trusted "
    "adult right away. In Vietnam you can also call 111 (free, 24/7)."
)


def render_result_panel(container, colors, s, stress_state, on_close, on_breathing=None,
                        close_text="Got it", note_text=None, font_scale=1.0):
    """
    Shared result panel used by the pop-up windows and the full-screen start-up gate.

    Args:
        container:    frame to draw into (its children are destroyed first)
        colors:       theme colors dict
        s:            scaling function
        stress_state: StressDiagnosisState (must have at least one score)
        on_close:     callback for the main button
        on_breathing: optional callback; when given AND the recommendation is
                      "relief", a "Breathing exercise" button is shown next to the main button
        close_text:   label of the main button (default "Got it")
        note_text:    optional bold paragraph shown above the buttons (used by the gate)
        font_scale:   1.0 in pop-up windows, larger on the full-screen gate
    """
    for widget in container.winfo_children():
        widget.destroy()
    container.config(bg=colors["bg_main"])

    def fnt(size, bold=False, italic=False):
        style = " ".join(x for x in (("bold" if bold else ""), ("italic" if italic else "")) if x)
        size = max(7, int(round(size * font_scale)))
        return ("Arial", size, style) if style else ("Arial", size)

    wrap = s(int(340 * font_scale))
    score = stress_state.rounded_average()
    level = stress_state.level()
    rec = stress_state.recommendation()
    has_breathing_btn = on_breathing is not None and rec == "relief"

    tk.Label(
        container, text=f"{score} / {SCORE_SCALE_MAX}",
        font=fnt(24, True), bg=colors["bg_main"], fg=colors["text_dark"],
    ).pack(pady=(s(10), s(2)))

    tk.Label(
        container, text=level.label_vi,
        font=fnt(16, True), bg=colors["bg_main"], fg=level.color,
    ).pack()
    tk.Label(
        container, text=f"({level.label_en})",
        font=fnt(10), bg=colors["bg_main"], fg=colors["text_medium"],
    ).pack(pady=(0, s(8)))

    parts = [f"{_COMPONENT_NAMES[name]}: {round_score(v)}" for name, v in stress_state.components()]
    tk.Label(
        container, text="   ·   ".join(parts),
        font=fnt(9), bg=colors["bg_main"], fg=colors["text_medium"],
        wraplength=wrap, justify="center",
    ).pack(pady=(0, s(10)))

    rec_text = (
        "We'd recommend a stress-relief session right now."
        if rec == "relief" else
        "You're in good shape for a study/work session."
    )
    tk.Label(
        container, text=rec_text, font=fnt(12),
        bg=colors["bg_main"], fg=colors["text_dark"],
        wraplength=wrap, justify="center",
    ).pack(pady=(0, s(8)))

    if getattr(stress_state, "mailbox_crisis", False):
        tk.Label(
            container, text=SUPPORT_TEXT, font=fnt(9, True),
            bg=colors["bg_main"], fg="#B03030",
            wraplength=wrap, justify="center",
        ).pack(pady=(0, s(8)))

    if note_text:
        tk.Label(
            container, text=note_text, font=fnt(11, True),
            bg=colors["bg_main"], fg=colors["text_dark"],
            wraplength=s(int(380 * font_scale)), justify="center",
        ).pack(pady=(0, s(10)))

    tk.Label(
        container, text="This is a self-check, not a medical diagnosis.",
        font=fnt(8, italic=True), bg=colors["bg_main"], fg=colors["text_medium"],
        wraplength=wrap, justify="center",
    ).pack(pady=(0, s(12)))

    button_row = tk.Frame(container, bg=colors["bg_main"])
    button_row.pack()

    if has_breathing_btn:
        tk.Button(
            button_row, text="Breathing exercise", command=on_breathing,
            bg=colors.get("accent", "#4CAF50"), fg="white",
            font=fnt(10, True), relief="flat",
            padx=s(16), pady=s(8), cursor="hand2",
        ).pack(side="left", padx=s(6))

    tk.Button(
        button_row, text=close_text, command=on_close,
        bg=colors["bg_secondary"] if has_breathing_btn else colors.get("accent", "#4CAF50"),
        fg=colors["text_dark"] if has_breathing_btn else "white",
        font=fnt(10, True), relief="flat",
        padx=s(20), pady=s(8), cursor="hand2",
    ).pack(side="left", padx=s(6))
