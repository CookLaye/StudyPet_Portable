"""
Hatch Screen - Interactive click-to-hatch transition for new pets.
"""

import tkinter as tk
from tkinter import font
import traceback
from graphics.pet_graphics import pet_graphics
from utils.notifications import NotificationManager

# Tunable constants
HATCH_BG        = "#F2F2F2"   # light gray
HATCH_FLASH_BG  = "#FFFFFF"   # brief flash at the moment of hatching
TEXT_DARK       = "#4A4A4A"
TEXT_MUTED      = "#8A8A8A"
EGG_SIZE_PX     = 320         # multiply by self.ui_scale
IDLE_WOBBLE_MS  = 3000        # egg wiggles every 3 s until clicked
WOBBLE_STEP_MS  = 40
WOBBLE_OFFSETS  = [-10, 10, -8, 8, -6, 6, -4, 4, -2, 2, 0]   # px, x-shift per step
FLASH_MS        = 150
REVEAL_HOLD_MS  = 1400        # how long the baby stays on screen before jumping

class HatchScreen:
    def __init__(self, parent, app_state, on_hatched_callback):
        self.parent = parent
        self.app_state = app_state
        self.on_hatched_callback = on_hatched_callback

        # UI Scale setup
        try:
            self.ui_scale = parent.winfo_fpixels('1i') / 96.0
        except Exception:
            self.ui_scale = 1.0

        self._hatching = False
        self._finished = False
        self._after_ids = set()

        # State
        self.frame = None
        self.setup_ui()
        self.start_idle_wobble()

    def s(self, px):
        """Scale pixel value."""
        return int(px * self.ui_scale)

    def setup_ui(self):
        self.frame = tk.Frame(self.parent, bg=HATCH_BG)
        self.frame.pack(fill="both", expand=True)
        self.frame.focus_set()

        # Title
        self.title_label = tk.Label(
            self.frame,
            text="Something is stirring inside...",
            font=("Arial", int(18 * self.ui_scale), "bold"),
            fg=TEXT_DARK,
            bg=HATCH_BG
        )
        self.title_label.place(relx=0.5, rely=0.14, anchor="center")

        # Pet Image / Egg
        pet_type = getattr(self.app_state.pet_type, "value", self.app_state.pet_type)
        size = (self.s(EGG_SIZE_PX), self.s(EGG_SIZE_PX))

        self.egg_photo = pet_graphics.get_pet_image(pet_type, 1, None, size)
        self.baby_photo = pet_graphics.get_pet_image(pet_type, 2, "Happy", size)

        # Image fallback handler
        self.use_emoji = False
        if self.egg_photo is None or self.baby_photo is None:
            self.use_emoji = True

        if self.use_emoji:
            self.egg_label = tk.Label(
                self.frame,
                text="🥚",
                font=("Arial", int(96 * self.ui_scale)),
                bg=HATCH_BG,
                cursor="hand2"
            )
        else:
            self.egg_label = tk.Label(
                self.frame,
                image=self.egg_photo,
                bg=HATCH_BG,
                bd=0,
                highlightthickness=0,
                cursor="hand2"
            )

        self.egg_label.place(relx=0.5, rely=0.48, anchor="center")
        self.egg_label.bind("<Button-1>", self._on_egg_click)

        # Hint
        self.hint_label = tk.Label(
            self.frame,
            text="Click the egg to hatch it!",
            font=("Arial", int(14 * self.ui_scale)),
            fg=TEXT_MUTED,
            bg=HATCH_BG
        )
        self.hint_label.place(relx=0.5, rely=0.84, anchor="center")

        # Accessibility
        self.frame.bind("<Return>", lambda e: self._on_egg_click(e))
        self.frame.bind("<space>", lambda e: self._on_egg_click(e))

    def _on_egg_click(self, event):
        if self._hatching:
            return

        self._hatching = True
        # Stop idle timer by clearing the set (though _later handles it,
        # we just want to ensure no new idle wobbles start)
        self.hint_label.place_forget()
        self.title_label.config(text="It's hatching!")

        self._run_hatch_sequence()

    def _run_hatch_sequence(self):
        # 1. Wobble
        self._do_wobble(step_idx=0)

    def _do_wobble(self, step_idx):
        if step_idx >= len(WOBBLE_OFFSETS):
            # End of wobble, go to flash
            self._do_flash()
            return

        offset = WOBBLE_OFFSETS[step_idx]
        self.egg_label.place_configure(x=self.s(offset))

        self._later(WOBBLE_STEP_MS, lambda: self._do_wobble(step_idx + 1))

    def _do_flash(self):
        # Flash background
        self.frame.config(bg=HATCH_FLASH_BG)
        self.title_label.config(bg=HATCH_FLASH_BG)
        self.egg_label.config(bg=HATCH_FLASH_BG)

        self._later(FLASH_MS, self._do_reveal)

    def _do_reveal(self):
        # Back to normal BG
        self.frame.config(bg=HATCH_BG)
        self.title_label.config(bg=HATCH_BG)
        self.egg_label.config(bg=HATCH_BG)

        # Swap to baby
        pet_name = self.app_state.pet_name
        self.title_label.config(text=f"{pet_name} hatched!")

        if self.use_emoji:
            self.egg_label.config(text="🐣")
        else:
            self.egg_label.config(image=self.baby_photo)

        self._later(REVEAL_HOLD_MS, self._finish)

    def _finish(self):
        if self._finished:
            return
        self._finished = True

        try:
            if not self.app_state.hatch_pet():
                # If it didn't actually hatch (e.g. already Baby), just continue
                pass
        except Exception as e:
            traceback.print_exc()
            NotificationManager.error("Hatch failed", str(e))
            self._finished = False
            self._hatching = False
            return

        self.on_hatched_callback()

    def start_idle_wobble(self):
        def wobble():
            if not self._hatching:
                self._do_wobble(step_idx=0)
                self._later(IDLE_WOBBLE_MS, wobble)

        self._later(IDLE_WOBBLE_MS, wobble)

    def _later(self, ms, fn):
        def run():
            self._after_ids.discard(aid)
            if self._alive():
                fn()
        aid = self.parent.after(ms, run)
        self._after_ids.add(aid)
        return aid

    def _alive(self):
        try:
            return self.frame is not None and self.frame.winfo_exists()
        except tk.TclError:
            return False

    def destroy(self):
        for aid in list(self._after_ids):
            try:
                self.parent.after_cancel(aid)
            except Exception:
                pass
        self._after_ids.clear()
        if self.frame is not None:
            try:
                self.frame.destroy()
            except tk.TclError:
                pass
            self.frame = None
