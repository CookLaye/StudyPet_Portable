"""
"Before you go" prompt: a small modal window with the four pet-emotion faces, shown when the
user closes the app. It re-uses EmotionScalePanel (the same faces/captions as the weekly
emotion check-in) and NEVER shows a score.

    ExitEmotionPrompt(root, colors, s, pet, pet_graphics, on_done)

on_done(emotion_key | None) is called exactly once:
  * "Happy" | "Worried" | "Sad" | "Angry"  after the user picks a face and presses Submit
  * None                                  if the user closes this little window with its own X
There is no Skip button. Either way the caller then quits the app.
"""

import tkinter as tk

from screens.stress_panels import EmotionScalePanel

PROMPT_W = 760          # px before s()
PROMPT_H = 680
FONT_SCALE = 1.1


class ExitEmotionPrompt:
    def __init__(self, root, colors, s, pet, pet_graphics, on_done):
        self.root = root
        self.on_done = on_done
        self._done = False
        self.panel = None

        self.win = tk.Toplevel(root)
        self.win.title("Before you go")
        self.win.configure(bg=colors["bg_main"])
        self.win.transient(root)
        self.win.resizable(False, False)

        w, h = s(PROMPT_W), s(PROMPT_H)
        # Cap height to screen size minus margin
        try:
            screen_h = self.root.winfo_screenheight()
            h = min(h, screen_h - s(80))
        except Exception:
            pass
        try:
            root.update_idletasks()
            x = root.winfo_rootx() + (root.winfo_width() - w) // 2
            y = root.winfo_rooty() + (root.winfo_height() - h) // 2
            x = max(0, x); y = max(0, y)
        except Exception:
            x, y = 100, 100
        self.win.geometry(f"{w}x{h}+{x}+{y}")

        holder = tk.Frame(self.win, bg=colors["bg_main"])
        holder.pack(fill="both", expand=True, padx=s(24), pady=s(20))
        self.win.update_idletasks()

        self.panel = EmotionScalePanel(
            holder, colors, s, pet, pet_graphics,
            on_submit=self._submitted,
            title="Before you go - how are you feeling now?",
            font_scale=FONT_SCALE, face_px=120)

        self.win.protocol("WM_DELETE_WINDOW", lambda: self._finish(None))
        try:
            self.win.lift()
            self.win.focus_force()
            self.win.grab_set()          # modal: the main window can't be used meanwhile
        except Exception:
            pass

    def _submitted(self, _score):
        # The panel keeps the chosen face in .selected_key; the caller turns it into a score.
        self._finish(getattr(self.panel, "selected_key", None))

    def _finish(self, emotion_key):
        if self._done:
            return
        self._done = True
        try:
            self.win.grab_release()
        except Exception:
            pass
        try:
            if self.panel is not None:
                self.panel.destroy()
        except Exception:
            pass
        try:
            self.win.destroy()
        except Exception:
            pass
        try:
            self.on_done(emotion_key)
        except Exception as e:
            print(f"[ExitEmotionPrompt] on_done failed: {type(e).__name__}: {e}")
