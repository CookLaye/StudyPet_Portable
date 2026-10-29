"""
Minigame chooser: the main-screen "🎮 Minigame" button opens this small centred window.

To add another minigame later: append one tuple to MINIGAMES and handle its key in
MainGameScreen._launch_minigame().      (key, button title, one-line description)
"""

import tkinter as tk

from ui.simple_theme import create_rounded_button

MINIGAMES = [
    ("circles", "🟡 Eat the Circles", "Click the circles on the playground - your pet runs over and eats them."),
    ("runner", "🦖 Pet Runner", "Your pet runs by itself. Jump over the obstacles for as long as you can!"),
    ("burst", "💖 Encouragement Burst", "Just click! Hearts and kind words pop up. No score, no pressure."),
]


class MinigamePicker:
    def __init__(self, parent, colors, s, on_choose, on_cancel=None, rewards_left=None, rewards_limit=None):
        """on_choose(key) is called after the window has closed. on_cancel() if the user backs out.
        rewards_left / rewards_limit (optional): shows how many affection-paying plays remain today."""
        self.parent, self.colors, self.s = parent, colors, s
        self.on_choose, self.on_cancel = on_choose, on_cancel
        self._done = False

        self.window = tk.Toplevel(parent)
        self.window.title("🎮 Choose a minigame")
        self.window.resizable(False, False)
        self.window.config(bg=colors["bg_main"])
        w, h = s(460), s(140 + 96 * len(MINIGAMES))
        sw, sh = parent.winfo_screenwidth(), parent.winfo_screenheight()
        self.window.geometry(f"{w}x{h}+{(sw - w) // 2}+{(sh - h) // 2}")
        try:
            self.window.transient(parent)
            self.window.grab_set()
        except Exception:
            pass
        self.window.protocol("WM_DELETE_WINDOW", self._cancel)
        self.window.bind("<Escape>", lambda e: self._cancel())

        tk.Label(self.window, text="Which minigame do you want to play?", bg=colors["bg_main"],
                 fg=colors["text_dark"], font=("Arial", 13, "bold")).pack(pady=(s(16), s(8)))

        if rewards_left is not None and rewards_limit:
            if rewards_left > 0:
                note = f"Affection plays left today: {rewards_left}/{rewards_limit}"
            else:
                note = "Today's affection plays are used up - you can still play for fun!"
            tk.Label(self.window, text=note, bg=colors["bg_main"], fg=colors.get("text_medium", "#666666"),
                     font=("Arial", 10)).pack(pady=(0, s(4)))

        for key, title, desc in MINIGAMES:
            row = tk.Frame(self.window, bg=colors["bg_main"])
            row.pack(fill="x", padx=s(24), pady=s(5))
            btn = create_rounded_button(row, text=title, command=lambda k=key: self._choose(k),
                                        style="accent", radius=18, padding=(14, 8), font=("Arial", 12, "bold"))
            btn.pack(anchor="w")
            tk.Label(row, text=desc, bg=colors["bg_main"], fg=colors.get("text_medium", "#666666"),
                     font=("Arial", 10), wraplength=w - s(60), justify="left").pack(anchor="w", pady=(s(2), 0))

        cancel = create_rounded_button(self.window, text="Cancel", command=self._cancel,
                                       style="secondary", radius=16, padding=(12, 6), font=("Arial", 10, "bold"))
        cancel.pack(pady=(s(8), s(10)))

    def _close_window(self):
        try:
            self.window.grab_release()
        except Exception:
            pass
        try:
            self.window.destroy()
        except Exception:
            pass

    def _choose(self, key):
        if self._done:
            return
        self._done = True
        self._close_window()
        self.on_choose(key)

    def _cancel(self):
        if self._done:
            return
        self._done = True
        self._close_window()
        if self.on_cancel:
            self.on_cancel()
