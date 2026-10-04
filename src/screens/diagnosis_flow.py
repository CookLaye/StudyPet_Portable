"""
Diagnosis wizard (pop-up window, opened from the top bar).

Step 1: live facial scan   Step 2: 7-question DASS-21 check-in   Step 3: result

There is no skip or cancel button anywhere in the flow. The scan only continues
without a face score if the camera really cannot be used (see SCAN_MAX_ATTEMPTS in
stress_panels.py). Closing the window with the title-bar X abandons the check-in.

The score of this wizard is independent: it only contains this wizard's own scan and
quiz (the caller passes a fresh StressDiagnosisState each time).
"""

import tkinter as tk

from utils.stress_diagnosis import render_result_panel
from screens.stress_panels import ScanPanel, QuizPanel


class DiagnosisWizard:
    def __init__(self, parent, colors, s, stress_state, current_pet,
                 on_complete=None, on_result=None, pet_graphics=None):
        """
        Args:
            parent: root window.   colors / s: theme colours and scaling function.
            stress_state: a FRESH StressDiagnosisState (scan + quiz are stored in it).
            current_pet: current pet object (used by the breathing exercise).
            on_complete: called when the window is closed.
            on_result: called (no args) when the result is shown.
        """
        self.parent = parent
        self.colors = colors
        self.s = s
        self.stress_state = stress_state
        self.current_pet = current_pet
        self.on_complete = on_complete
        self.on_result = on_result
        self.pet_graphics = pet_graphics
        self._panel = None
        self._closed = False

        self.window = tk.Toplevel(parent)
        self.window.title("Stress Diagnosis")

        screen_w = self.window.winfo_screenwidth()
        screen_h = self.window.winfo_screenheight()
        win_w = min(screen_w - self.s(40), max(self.s(780), int(parent.winfo_width() * 0.55)))
        win_h = min(screen_h - self.s(80), self.s(860))
        pos_x = max(0, (screen_w - win_w) // 2)
        pos_y = max(0, (screen_h - win_h) // 2 - self.s(20))
        self.window.geometry(f"{win_w}x{win_h}+{pos_x}+{pos_y}")
        self.window.resizable(False, False)
        self.window.config(bg=self.colors["bg_main"])
        self.window.grab_set()
        self.window.protocol("WM_DELETE_WINDOW", self.close_wizard)

        self.content_frame = tk.Frame(self.window, bg=self.colors["bg_main"])
        self.content_frame.pack(fill="both", expand=True, padx=self.s(20), pady=self.s(20))

        # preview scaled so scan panel (title + preview + status + bar) fits the window height
        avail = win_h - self.s(40) - self.s(190)
        self._preview_scale = max(0.5, min(1.0, avail / 480.0))
        self._start_scan()

    # ---------------------------------------------------------------- helpers
    def _alive(self):
        return (not self._closed) and self.window.winfo_exists()

    def _swap_panel(self, panel_factory):
        if self._panel is not None:
            self._panel.destroy()
            self._panel = None
        for w in self.content_frame.winfo_children():
            w.destroy()
        self._panel = panel_factory()

    # ---------------------------------------------------------------- step 1: scan
    def _start_scan(self):
        self._swap_panel(lambda: ScanPanel(
            self.content_frame, self.colors, self.s, on_done=self._scan_done,
            title="Step 1 of 2 — Facial Scan", preview_scale=self._preview_scale))

    def _scan_done(self, score):
        self.stress_state.facial_scan_score = score      # None = scan impossible
        self.window.after(50, self._start_quiz)

    # ---------------------------------------------------------------- step 2: quiz
    def _start_quiz(self):
        if not self._alive():
            return
        self._swap_panel(lambda: QuizPanel(
            self.content_frame, self.colors, self.s, on_submit=self._quiz_done,
            title="Step 2 of 2 — Quick Check-in"))

    def _quiz_done(self, score):
        self.stress_state.quiz_score = score
        self.window.after(50, self._show_result)

    # ---------------------------------------------------------------- step 3: result
    def _show_result(self):
        if not self._alive():
            return
        if self._panel is not None:
            self._panel.destroy()
            self._panel = None
        for w in self.content_frame.winfo_children():
            w.destroy()
        result_frame = tk.Frame(self.content_frame, bg=self.colors["bg_main"])
        result_frame.pack(expand=True, fill="both")
        render_result_panel(
            result_frame, self.colors, self.s, self.stress_state,
            on_close=self.close_wizard,
            on_breathing=self._open_breathing,
            font_scale=1.15,
        )
        if self.on_result:
            try:
                self.on_result()
            except Exception as e:
                print(f"Error in diagnosis on_result callback: {e}")

    def _open_breathing(self):
        """Close the wizard and open the (optional) pet breathing exercise."""
        parent, colors, s, pet = self.parent, self.colors, self.s, self.current_pet
        pg = self.pet_graphics
        self.close_wizard()
        from screens.breathing_exercise import open_breathing_exercise
        if pg is None:
            from graphics.pet_graphics import pet_graphics as pg
        open_breathing_exercise(parent, colors, s, pet, pg)

    # ---------------------------------------------------------------- closing
    def close_wizard(self):
        if self._closed:
            return
        self._closed = True
        if self._panel is not None:
            try:
                self._panel.destroy()          # stops the scanner / releases the camera
            except Exception:
                pass
            self._panel = None
        try:
            self.window.destroy()
        except Exception:
            pass
        if self.on_complete:
            try:
                self.on_complete()
            except Exception as e:
                print(f"Error in diagnosis on_complete callback: {e}")
