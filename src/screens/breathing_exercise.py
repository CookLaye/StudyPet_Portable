"""
Breathing exercise window: the pet guides "box breathing" (4 : 4 : 4 : 4).

    breathe IN (4 s)  ->  HOLD full (4 s)  ->  breathe OUT (4 s)  ->  HOLD empty (4 s)  ->  repeat

ALL TIMING LIVES IN THE CONSTANTS BELOW - change a number, nothing else.

Pet pictures
------------
Looks for three pictures per pet (PNG, any size, transparent background is best):

    assets/img/Breathing/<Pet>_Breathe_In.png
    assets/img/Breathing/<Pet>_Hold.png
    assets/img/Breathing/<Pet>_Breathe_Out.png

<Pet> is the pet's folder name: Cat, Dog, Axolotl, Raccoon, Penguin.
It also accepts the same file names inside assets/img/<Pet>/ and, as a shared
fallback for all pets, assets/img/Breathing/Breathe_In.png (etc.).

Any picture that is missing falls back to the pet's normal picture, which then
"breathes" by growing on the in-breath and shrinking on the out-breath, so the
window works before any breathing art exists.

Use from other screens:  open_breathing_exercise(parent, colors, s, pet, pet_graphics)

The exercise itself is BreathingPanel, which fills any Frame (pop-up window OR the
full-screen start-up gate). With required=True there is no "Not now" / "Stop":
the user breathes through all rounds, then presses Continue (on_finished is called).
"""

import math
import os
import time
import tkinter as tk
from pathlib import Path

# =============================== TIMING (seconds) ===============================
BREATH_IN_SEC = 4       # breathe in
HOLD_FULL_SEC = 4       # hold, lungs full
BREATH_OUT_SEC = 4      # breathe out
HOLD_EMPTY_SEC = 4      # hold, lungs empty
TOTAL_ROUNDS = 6        # one round = one in/hold/out/hold  (6 rounds = 96 s)
TICK_MS = 100           # how often the screen refreshes (does not affect timing)

# =============================== LOOK & TEXT ===================================
IMAGE_BOX = 300         # pet picture is fitted into a square of this many pixels (before scaling)
FALLBACK_MIN_SCALE = 0.80   # size of the normal pet picture when "empty" (fallback mode only)

# (phase key, seconds, picture key, English text, Vietnamese text)
PHASES = [
    ("in",         BREATH_IN_SEC,   "Breathe_In",  "Breathe in",  "Hít vào"),
    ("hold_full",  HOLD_FULL_SEC,   "Hold",        "Hold",        "Giữ hơi"),
    ("out",        BREATH_OUT_SEC,  "Breathe_Out", "Breathe out", "Thở ra"),
    ("hold_empty", HOLD_EMPTY_SEC,  "Breathe_Out", "Hold",        "Giữ hơi"),
]
# The second "Hold" (lungs empty) reuses the Breathe_Out picture because only three
# pictures exist. Give it its own picture later by changing "Breathe_Out" -> "Hold_Empty".

INTRO_TEXT = (
    "Let's breathe together.\n\n"
    "Follow your pet: breathe in, hold, breathe out, hold - four seconds each.\n"
    "Breathe slowly through your nose if you can, and let your shoulders drop."
)
DONE_TEXT = "Nice work! Take a moment - how do you feel now?"


# ============================ timing logic (no Tk) ==============================

def cycle_length(phases=None):
    return sum(p[1] for p in (phases or PHASES))


def total_seconds(rounds=None, phases=None):
    return cycle_length(phases) * (TOTAL_ROUNDS if rounds is None else rounds)


def get_phase(elapsed, rounds=None, phases=None):
    """
    Where are we after `elapsed` seconds?

    Returns None when the exercise is finished, otherwise a dict:
        round        1-based round number
        index        index into PHASES
        key          "in" | "hold_full" | "out" | "hold_empty"
        seconds_left whole seconds left in this phase, counting DOWN (4,3,2,1)
        fraction     0.0 -> 1.0 progress inside this phase
    """
    phases = phases or PHASES
    rounds = TOTAL_ROUNDS if rounds is None else rounds
    cycle = cycle_length(phases)
    if cycle <= 0:
        return None
    elapsed = max(0.0, elapsed)
    if elapsed >= cycle * rounds:
        return None
    round_idx = int(elapsed // cycle)
    pos = elapsed - round_idx * cycle
    for idx, (key, length, _pic, _en, _vi) in enumerate(phases):
        if pos < length:
            left = max(1, min(length, int(math.ceil(length - pos))))
            return {"round": round_idx + 1, "index": idx, "key": key,
                    "seconds_left": left, "fraction": pos / length}
        pos -= length
    return None  # unreachable


def fallback_scale(info):
    """Size factor (FALLBACK_MIN_SCALE..1.0) for the normal pet picture in fallback mode."""
    key, f = info["key"], info["fraction"]
    lo = FALLBACK_MIN_SCALE
    if key == "in":
        return lo + (1.0 - lo) * f
    if key == "hold_full":
        return 1.0
    if key == "out":
        return 1.0 - (1.0 - lo) * f
    return lo   # hold_empty


# ================================ pet helpers ===================================

def _pet_fields(pet):
    pet_type = pet.pet_type.value if hasattr(pet.pet_type, "value") else str(pet.pet_type)
    stage = pet.stage.value if hasattr(pet.stage, "value") else int(pet.stage)
    emotion = pet.emotion.name.lower() if hasattr(pet.emotion, "name") else str(pet.emotion).lower()
    return str(pet_type).lower(), stage, emotion


def _find_breathing_file(img_root, pet_folder, pic_key):
    candidates = [
        os.path.join(img_root, "Breathing", f"{pet_folder}_{pic_key}.png"),
        os.path.join(img_root, pet_folder, f"{pet_folder}_{pic_key}.png"),
        os.path.join(img_root, "Breathing", f"{pic_key}.png"),
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    return None


# ================================== panel =======================================

class BreathingPanel:
    def __init__(self, container, colors, s, current_pet, pet_graphics,
                 on_finished=None, required=False, font_scale=1.0, auto_begin=False):
        """
        container:   Frame to fill
        on_finished: called with True when all rounds were completed and the user pressed
                     the final button, or False when the user left early (optional mode only)
        required:    True = no 'Not now' / 'Stop'; the final button is 'Continue'
        auto_begin:  skip the intro screen and start breathing immediately
        """
        self.container = container
        self.colors = colors
        self.s = s
        self.pet = current_pet
        self.pet_graphics = pet_graphics
        self.on_finished = on_finished
        self.required = required
        self.fs = font_scale

        self._after_id = None
        self._start_time = None
        self._destroyed = False
        self._reported = False
        self._photo_cache = {}       # picture key / size -> PhotoImage (keeps references alive)

        self.pet_type, self.stage, self.emotion = _pet_fields(current_pet)
        self.pet_folder = pet_graphics._get_pet_folder(self.pet_type) if hasattr(pet_graphics, "_get_pet_folder") else self.pet_type.title()
        self.img_root = getattr(pet_graphics, "img_base_path", None) or str(Path(__file__).parent.parent.parent / "assets" / "img")

        if auto_begin:
            self._begin()
        else:
            self._show_intro()

    # ---------------------------------------------------------------- helpers
    def _f(self, size, bold=False):
        size = max(7, int(round(size * self.fs)))
        return ("Arial", size, "bold") if bold else ("Arial", size)

    def _alive(self):
        if self._destroyed:
            return False
        try:
            return bool(self.container.winfo_exists())
        except Exception:
            return False

    def _clear(self):
        for w in list(self.container.winfo_children()):
            w.destroy()

    def _button(self, parent, text, command, primary=True):
        return tk.Button(
            parent, text=text, command=command,
            bg=self.colors.get("accent", "#4CAF50") if primary else self.colors["bg_secondary"],
            fg="white" if primary else self.colors["text_dark"],
            font=self._f(11, True), relief="flat",
            padx=self.s(int(22 * self.fs)), pady=self.s(int(8 * self.fs)), cursor="hand2",
        )

    def _cancel_timer(self):
        if self._after_id is not None:
            try:
                self.container.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None

    def _report(self, completed):
        if self._reported:
            return
        self._reported = True
        if self.on_finished:
            try:
                self.on_finished(completed)
            except Exception as e:
                print(f"Error in breathing on_finished callback: {e}")

    # ---------------------------------------------------------------- pictures
    def _box(self):
        return int(self.s(IMAGE_BOX) * self.fs)

    def _load_breathing_photo(self, pic_key):
        """PhotoImage for a breathing picture, or None if that picture does not exist."""
        cache_key = ("pic", pic_key)
        if cache_key in self._photo_cache:
            return self._photo_cache[cache_key]
        photo = None
        path = _find_breathing_file(self.img_root, self.pet_folder, pic_key)
        if path:
            try:
                from PIL import Image, ImageTk
                img = Image.open(path).convert("RGBA")
                box = self._box()
                img.thumbnail((box, box), Image.LANCZOS)
                photo = ImageTk.PhotoImage(img)
            except Exception as e:
                print(f"Breathing picture failed to load ({path}): {e}")
        self._photo_cache[cache_key] = photo
        return photo

    def _normal_pet_photo(self, scale):
        """Normal pet picture at a quantised size (fallback mode)."""
        size = int(self._box() * scale)
        size = max(32, (size // 8) * 8)           # 8 px steps keep the cache small
        cache_key = ("pet", size)
        if cache_key not in self._photo_cache:
            self._photo_cache[cache_key] = self.pet_graphics.get_pet_image(
                self.pet_type, self.stage, self.emotion, size=(size, size))
        return self._photo_cache[cache_key]

    def _set_picture(self, info):
        """Show the right picture for this phase (real art if present, else the scaling pet)."""
        pic_key = PHASES[info["index"]][2]
        photo = self._load_breathing_photo(pic_key)
        if photo is None:                         # fallback: normal pet, breathing by size
            photo = self._normal_pet_photo(fallback_scale(info))
        if photo is not None:
            self.pet_lbl.config(image=photo, text="")
            self.pet_lbl.image = photo
        else:                                     # even the normal picture is missing
            emoji = self.pet_graphics.get_fallback_emoji(self.pet_type) if hasattr(self.pet_graphics, "get_fallback_emoji") else "🐾"
            self.pet_lbl.config(image="", text=emoji, font=("Arial", 96))

    # ---------------------------------------------------------------- screens
    def _show_intro(self):
        self._cancel_timer()
        self._clear()
        tk.Label(
            self.container, text="Breathing Exercise", font=self._f(16, True),
            bg=self.colors["bg_main"], fg=self.colors["text_dark"],
        ).pack(pady=(self.s(10), self.s(14)))

        self.pet_lbl = tk.Label(self.container, bg=self.colors["bg_main"])
        self.pet_lbl.pack(pady=self.s(6))
        self._set_picture({"index": 0, "key": "hold_empty", "fraction": 0.0})  # calm starting picture

        tk.Label(
            self.container, text=INTRO_TEXT, font=self._f(11), justify="center",
            bg=self.colors["bg_main"], fg=self.colors["text_dark"], wraplength=self.s(int(440 * self.fs)),
        ).pack(pady=self.s(14))

        row = tk.Frame(self.container, bg=self.colors["bg_main"])
        row.pack(pady=self.s(8))
        self._button(row, "Begin", self._begin).pack(side="left", padx=self.s(6))
        if not self.required:
            self._button(row, "Not now", self._leave, primary=False).pack(side="left", padx=self.s(6))

    def _begin(self):
        self._clear()
        tk.Label(
            self.container, text="Breathing Exercise", font=self._f(14, True),
            bg=self.colors["bg_main"], fg=self.colors["text_dark"],
        ).pack(pady=(self.s(4), self.s(8)))

        # fixed-size box so the layout does not jump when the picture changes size
        box = tk.Frame(self.container, width=self._box() + 20,
                       height=self._box() + 20, bg=self.colors["bg_main"])
        box.pack(pady=self.s(4))
        box.pack_propagate(False)
        self.pet_lbl = tk.Label(box, bg=self.colors["bg_main"])
        self.pet_lbl.pack(expand=True)

        self.phase_lbl = tk.Label(
            self.container, text="", font=self._f(26, True),
            bg=self.colors["bg_main"], fg=self.colors["text_dark"])
        self.phase_lbl.pack(pady=(self.s(6), 0))
        self.phase_vi_lbl = tk.Label(
            self.container, text="", font=self._f(12),
            bg=self.colors["bg_main"], fg=self.colors["text_medium"])
        self.phase_vi_lbl.pack()
        self.count_lbl = tk.Label(
            self.container, text="", font=self._f(40, True),
            bg=self.colors["bg_main"], fg=self.colors.get("accent", "#4CAF50"))
        self.count_lbl.pack(pady=self.s(2))
        self.round_lbl = tk.Label(
            self.container, text="", font=self._f(10),
            bg=self.colors["bg_main"], fg=self.colors["text_medium"])
        self.round_lbl.pack(pady=(0, self.s(8)))

        if not self.required:
            self._button(self.container, "Stop", self._leave, primary=False).pack()

        self._start_time = time.monotonic()
        self._tick()

    def _tick(self):
        self._after_id = None
        if not self._alive():
            return
        elapsed = time.monotonic() - self._start_time
        info = get_phase(elapsed)
        if info is None:
            self._show_done()
            return

        _key, _secs, _pic, en, vi = PHASES[info["index"]]
        self.phase_lbl.config(text=en)
        self.phase_vi_lbl.config(text=vi)
        self.count_lbl.config(text=str(info["seconds_left"]))
        self.round_lbl.config(text=f"Round {info['round']} of {TOTAL_ROUNDS}")
        self._set_picture(info)
        self._after_id = self.container.after(TICK_MS, self._tick)

    def _show_done(self):
        self._cancel_timer()
        self._clear()
        tk.Label(
            self.container, text="Breathing Exercise", font=self._f(16, True),
            bg=self.colors["bg_main"], fg=self.colors["text_dark"],
        ).pack(pady=(self.s(10), self.s(14)))
        self.pet_lbl = tk.Label(self.container, bg=self.colors["bg_main"])
        self.pet_lbl.pack(pady=self.s(6))
        self._set_picture({"index": 0, "key": "hold_empty", "fraction": 0.0})
        tk.Label(
            self.container, text=DONE_TEXT, font=self._f(12), justify="center",
            bg=self.colors["bg_main"], fg=self.colors["text_dark"], wraplength=self.s(int(440 * self.fs)),
        ).pack(pady=self.s(14))
        row = tk.Frame(self.container, bg=self.colors["bg_main"])
        row.pack(pady=self.s(8))
        if self.required:
            self._button(row, "Continue", lambda: self._report(True)).pack(side="left", padx=self.s(6))
        else:
            self._button(row, "Done", lambda: self._report(True)).pack(side="left", padx=self.s(6))
            self._button(row, "Another round", self._begin, primary=False).pack(side="left", padx=self.s(6))

    def _leave(self):
        self._report(False)

    def destroy(self):
        self._destroyed = True
        self._cancel_timer()


# ================================== window ======================================

class BreathingExerciseWindow:
    """Pop-up window that hosts a BreathingPanel (optional mode: Not now / Stop / Done)."""

    def __init__(self, parent, colors, s, current_pet, pet_graphics, on_close=None):
        self.parent = parent
        self.on_close = on_close
        self._closed = False

        self.window = tk.Toplevel(parent)
        self.window.title("Breathing Exercise")
        win_w, win_h = s(560), s(700)
        screen_w, screen_h = self.window.winfo_screenwidth(), self.window.winfo_screenheight()
        win_h = min(win_h, screen_h - s(80))
        x = max(0, (screen_w - win_w) // 2)
        y = max(0, (screen_h - win_h) // 2 - s(20))
        self.window.geometry(f"{win_w}x{win_h}+{x}+{y}")
        self.window.resizable(False, False)
        self.window.config(bg=colors["bg_main"])
        self.window.grab_set()
        self.window.protocol("WM_DELETE_WINDOW", self.close)

        self.container = tk.Frame(self.window, bg=colors["bg_main"])
        self.container.pack(fill="both", expand=True, padx=s(20), pady=s(20))
        self.panel = BreathingPanel(
            self.container, colors, s, current_pet, pet_graphics,
            on_finished=lambda completed: self.close(), required=False)

    def close(self):
        if self._closed:
            return
        self._closed = True
        try:
            self.panel.destroy()
        except Exception:
            pass
        try:
            self.window.destroy()
        except Exception:
            pass
        if self.on_close:
            try:
                self.on_close()
            except Exception as e:
                print(f"Error in breathing on_close callback: {e}")


def open_breathing_exercise(parent, colors, s, current_pet, pet_graphics, on_close=None):
    """Open the breathing exercise window (returns the window object)."""
    return BreathingExerciseWindow(parent, colors, s, current_pet, pet_graphics, on_close=on_close)
