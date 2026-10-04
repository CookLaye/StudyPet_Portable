"""
Stress-Relief Mailbox window (opened from the top bar).

Write a letter -> it flies to the pet -> "Thinking it over..." -> result.
The writing / feeding animation is shared with the full-screen start-up gate
(screens/stress_panels.py::LetterPanel); the feeding speed constants FEED_* live there.

The score of this window is independent: it only contains the letter's keyword score
(the caller passes a fresh StressDiagnosisState each time).
"""

import tkinter as tk

from utils.stress_diagnosis import analyze_mailbox, render_result_panel
from screens.stress_panels import LetterPanel


class StressMailboxWindow:
    def __init__(self, parent, colors, s, stress_state, current_pet, pet_graphics,
                 on_result=None):
        """
        Args:
            parent: root window.   colors / s: theme colours and scaling function.
            stress_state: a FRESH StressDiagnosisState (only the mailbox score is stored in it).
            current_pet / pet_graphics: the pet and the pet_graphics singleton.
            on_result: called (no args) when the result is shown.
        """
        self.parent = parent
        self.colors = colors
        self.s = s
        self.stress_state = stress_state
        self.current_pet = current_pet
        self.pet_graphics = pet_graphics
        self.on_result = on_result
        self._panel = None

        self.window = tk.Toplevel(parent)
        self.window.title("📮 Stress-Relief Mailbox")

        parent_w = parent.winfo_width()
        parent_h = parent.winfo_height()
        win_w = max(self.s(700), int(parent_w * 0.6))
        win_h = max(self.s(480), int(parent_h * 0.6))
        screen_w = parent.winfo_screenwidth()
        screen_h = parent.winfo_screenheight()
        x = (screen_w - win_w) // 2
        y = (screen_h - win_h) // 2

        self.window.geometry(f"{win_w}x{win_h}+{x}+{y}")
        self.window.resizable(False, False)
        self.window.config(bg=self.colors["bg_main"])
        self.window.grab_set()
        self.window.protocol("WM_DELETE_WINDOW", self._close)

        self.main_container = tk.Frame(self.window, bg=self.colors["bg_main"])
        self.main_container.pack(fill="both", expand=True, padx=self.s(20), pady=self.s(20))

        self._panel = LetterPanel(
            self.main_container, self.colors, self.s, self.current_pet,
            self.pet_graphics, on_done=self._letter_done)

    # ---------------------------------------------------------------- result
    def _letter_done(self, letter_text):
        (self.stress_state.mailbox_score,
         self.stress_state.mailbox_crisis) = analyze_mailbox(letter_text)
        self._panel.remove_status()

        result_frame = tk.Frame(self.main_container, bg=self.colors["bg_main"])
        result_frame.place(relx=0.5, rely=0.7, anchor="center", relwidth=0.8)
        render_result_panel(
            result_frame, self.colors, self.s, self.stress_state,
            on_close=self._close,
            on_breathing=self._open_breathing,
        )
        if self.on_result:
            try:
                self.on_result()
            except Exception as e:
                print(f"Error in mailbox on_result callback: {e}")

    def _open_breathing(self):
        """Close this window and open the (optional) pet breathing exercise."""
        parent, colors, s = self.parent, self.colors, self.s
        pet, pet_graphics = self.current_pet, self.pet_graphics
        self._close()
        from screens.breathing_exercise import open_breathing_exercise
        open_breathing_exercise(parent, colors, s, pet, pet_graphics)

    def _close(self):
        if self._panel is not None:
            try:
                self._panel.destroy()
            except Exception:
                pass
            self._panel = None
        try:
            self.window.destroy()
        except Exception:
            pass
