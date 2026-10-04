"""
Full-screen start-up gate: the main screen stays hidden until this check-in is done.

Flow
----
 Round 1  face scan -> quiz -> letter to the pet -> result (average of the three, 0-42)
    normal   -> main screen, full access
    stressed -> breathing exercise (required) -> Round 2 (same steps) -> result
                 decide_access(round 1, round 2):
                     full       -> main screen like it is today
                     restricted -> main screen with only the calm features + a relax prompt

There are no skip / cancel buttons. (The only automatic exception: if the camera cannot
be used after SCAN_MAX_ATTEMPTS tries, that check-in continues without the face score.)

The screen is a plain Frame filling the root window, like the other screens, so the
controller can cleanup()/destroy() it. It reports through on_finished(access_mode).
"""

import tkinter as tk

from ui.simple_theme import simple_theme
from ui.pet_theme import apply_pet_theme
from graphics.pet_graphics import pet_graphics
from utils.stress_diagnosis import (
    StressDiagnosisState, render_result_panel, decide_access, analyze_mailbox,
)
from screens.stress_panels import ScanPanel, QuizPanel, LetterPanel
from screens.breathing_exercise import BreathingPanel

# Which parts each round contains (order matters). Remove "letter" from STEPS_SECOND
# if the re-check should be shorter.
STEPS_FIRST = ("scan", "quiz", "letter")
STEPS_SECOND = ("scan", "quiz", "letter")

FONT_SCALE = 1.3        # everything on this screen is bigger than in the pop-up windows

STEP_TITLES = {"scan": "Face scan", "quiz": "Quick check-in", "letter": "Letter to your pet"}

NOTE_NEED_BREATHING = ("Let's take a few minutes to breathe together with your pet "
                       "before you start. Then we'll check in again.")
NOTE_BETTER = "You're feeling calmer - nice work. Enjoy your time!"
NOTE_STILL_STRESSED = ("Your stress hasn't come down much yet, and that's okay. "
                       "Today, just stay with your pet, relax and take it easy. "
                       "You can run a new Diagnosis whenever you feel calmer.")


class StressGateScreen:
    def __init__(self, parent, app_state, music_player, on_finished):
        self.parent = parent
        self.app_state = app_state
        self.music_player = music_player
        self.on_finished = on_finished
        self._panel = None
        self._destroyed = False
        self._finished = False

        try:
            self.ui_scale = parent.winfo_fpixels('1i') / 96.0
        except Exception:
            self.ui_scale = 1.0
        self.s = lambda px: max(1, round(px * self.ui_scale))

        apply_pet_theme(app_state=app_state)
        self.colors = simple_theme.colors
        self.pet = app_state.get_current_pet()

        self.first_state = None
        self.state = None
        self.round_no = 0
        self.steps_total = 0
        self.steps_done = 0
        self.steps = []

        self.frame = tk.Frame(parent, bg=self.colors["bg_main"])
        self.frame.pack(fill="both", expand=True)

        self.header = tk.Label(
            self.frame, text="", font=("Arial", int(14 * FONT_SCALE), "bold"),
            bg=self.colors["bg_main"], fg=self.colors["text_medium"])
        self.header.pack(side="top", pady=(self.s(24), self.s(6)))

        self.body = tk.Frame(self.frame, bg=self.colors["bg_main"])
        self.body.pack(side="top", fill="both", expand=True,
                       padx=self.s(80), pady=(0, self.s(30)))

        self.frame.update_idletasks()
        self._start_round(1)

    # ------------------------------------------------------------------ plumbing
    def _alive(self):
        if self._destroyed:
            return False
        try:
            return bool(self.frame.winfo_exists())
        except Exception:
            return False

    def _clear_body(self):
        if self._panel is not None:
            try:
                self._panel.destroy()
            except Exception:
                pass
            self._panel = None
        for w in list(self.body.winfo_children()):
            try:
                w.destroy()
            except Exception:
                pass

    def _set_header(self, text):
        self.header.config(text=text)

    # ------------------------------------------------------------------ rounds
    def _start_round(self, round_no):
        self.round_no = round_no
        self.state = StressDiagnosisState()          # every round scores on its own
        self.steps = list(STEPS_FIRST if round_no == 1 else STEPS_SECOND)
        self.steps_total = len(self.steps)
        self.steps_done = 0
        self._next_step()

    def _next_step(self):
        if not self._alive():
            return
        self._clear_body()
        if not self.steps:
            self._show_round_result()
            return
        step = self.steps.pop(0)
        self.steps_done += 1
        label = "Check-in" if self.round_no == 1 else "Second check-in"
        self._set_header(f"{label} · step {self.steps_done} of {self.steps_total} · {STEP_TITLES[step]}")

        if step == "scan":
            # preview as large as the screen allows (4:3), never more than 1.6x
            avail_h = max(300, self.parent.winfo_height() - self.s(380))
            scale = max(0.8, min(1.6, avail_h / 480.0))
            self._panel = ScanPanel(
                self.body, self.colors, self.s, on_done=self._scan_done,
                title="Facial Scan", font_scale=FONT_SCALE, preview_scale=scale)
        elif step == "quiz":
            self._panel = QuizPanel(
                self.body, self.colors, self.s, on_submit=self._quiz_done,
                title="Quick Check-in", font_scale=FONT_SCALE,
                wrap=self.s(int(700 * FONT_SCALE)))
        else:
            self._panel = LetterPanel(
                self.body, self.colors, self.s, self.pet, pet_graphics,
                on_done=self._letter_done, font_scale=FONT_SCALE, pet_px=200)

    def _scan_done(self, score):
        self.state.facial_scan_score = score          # None if the camera could not be used
        self.frame.after(50, self._next_step)

    def _quiz_done(self, score):
        self.state.quiz_score = score
        self.frame.after(50, self._next_step)

    def _letter_done(self, letter_text):
        (self.state.mailbox_score, self.state.mailbox_crisis) = analyze_mailbox(letter_text)
        self.frame.after(50, self._next_step)

    # ------------------------------------------------------------------ results
    def _apply_music(self, stressed):
        try:
            self.music_player.set_stress_mode(bool(stressed))
        except Exception as e:
            print(f"Could not apply stress state to the music player: {e}")

    def _show_result(self, note, button_text, on_button):
        self._clear_body()
        self._set_header("Your result")
        holder = tk.Frame(self.body, bg=self.colors["bg_main"])
        holder.place(relx=0.5, rely=0.45, anchor="center")
        render_result_panel(
            holder, self.colors, self.s, self.state,
            on_close=on_button, close_text=button_text,
            note_text=note, font_scale=FONT_SCALE,
        )

    def _show_round_result(self):
        stressed = self.state.is_stressed()
        self._apply_music(stressed)                  # music filter follows every result

        if self.round_no == 1:
            self.first_state = self.state
            if not stressed:
                self._show_result(None, "Continue", lambda: self._finish("full"))
            else:
                self._show_result(NOTE_NEED_BREATHING, "Start breathing", self._start_breathing)
        else:
            access = decide_access(self.first_state.average(), self.state.average())
            if access == "full":
                self._show_result(NOTE_BETTER, "Continue", lambda: self._finish("full"))
            else:
                self._show_result(NOTE_STILL_STRESSED, "Continue", lambda: self._finish("restricted"))

    # ------------------------------------------------------------------ breathing
    def _start_breathing(self):
        self._clear_body()
        self._set_header("Breathe with your pet")
        self._panel = BreathingPanel(
            self.body, self.colors, self.s, self.pet, pet_graphics,
            on_finished=self._breathing_done, required=True, font_scale=FONT_SCALE)

    def _breathing_done(self, completed):
        self.frame.after(50, lambda: self._start_round(2))

    # ------------------------------------------------------------------ finish / cleanup
    def _finish(self, access_mode):
        if self._finished:
            return
        self._finished = True
        try:
            self.on_finished(access_mode)
        except Exception as e:
            print(f"Error in stress gate on_finished: {e}")
            import traceback
            traceback.print_exc()

    def cleanup(self):
        self._destroyed = True
        if self._panel is not None:
            try:
                self._panel.destroy()          # stops the scanner / releases the camera
            except Exception:
                pass
            self._panel = None

    def destroy(self):
        self.cleanup()
        try:
            self.frame.destroy()
        except Exception:
            pass
