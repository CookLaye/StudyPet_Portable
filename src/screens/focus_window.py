"""
Small always-on-top window shown during a Pomodoro work session when focus tracking is on:
camera preview + what the tracker thinks right now + warnings used. Display only; all logic lives in
stress_scan/focus_logic.py and src/utils/focus_session.py.

- Never steals keyboard focus (focus is handed straight back to the main window).
- The window's X button MINIMISES it; tracking continues (closing must not be a way to dodge warnings).
- Pausing the timer hides it, and resuming shows it again immediately: set_paused().
  It really closes when the session ends (break / stop / finish) or tracking is switched off.
"""

import sys
import tkinter as tk

SHOW_FOCUS_SIGNALS = True          # small grey line with the raw signals (dyaw / dpitch / eyes), to verify it works
# The preview scales with the screen: PREVIEW_SCREEN_FRACTION of the screen width, kept between MIN and MAX
# (about 410 px on a 1366-wide laptop, 576 px on 1920). Change these three numbers to make it bigger or smaller.
PREVIEW_SCREEN_FRACTION = 0.30
PREVIEW_MIN_W = 400
PREVIEW_MAX_W = 640

STATE_TEXT = {
    "at_screen": ("Focused", "ok"),
    "down": ("Looking down (reading / writing) - OK", "ok"),
    "away": ("Looking away", "bad"),
    "absent": ("Not at the desk", "bad"),
    "eyes_closed": ("Eyes closed", "bad"),
    "unsure": ("Can't see you well - not counted", "warn"),
}
COLORS = {"ok": "#2e7d32", "bad": "#c62828", "warn": "#ef6c00", "info": "#444444"}


class FocusWindow:
    def __init__(self, parent, colors, scale, on_recalibrate):
        self._root = parent.winfo_toplevel()
        self._colors = colors or {}
        self._on_recalibrate = on_recalibrate
        self._photo = None
        self._paused_hidden = False
        self._last_frame_id = None
        self._last = {"strikes": 0, "max_strikes": 0}
        bg = self._colors.get("bg_main", "#f5f5f5")
        self._bg = bg
        self._fg = self._colors.get("text_dark", "#222222")

        self.win = tk.Toplevel(parent)
        self.win.withdraw()                                   # build first, show later (no flicker, no focus grab)
        self.win.title("StudyPet Focus")
        self.win.configure(bg=bg)
        self.win.resizable(False, False)
        try:
            self.win.attributes("-topmost", True)
            if sys.platform.startswith("win"):
                self.win.attributes("-toolwindow", True)      # small title bar, no taskbar button
        except tk.TclError:
            pass
        self.win.protocol("WM_DELETE_WINDOW", self.win.iconify)

        pad = max(4, int(6 * scale))
        width = int(max(PREVIEW_MIN_W, min(PREVIEW_MAX_W, self.win.winfo_screenwidth() * PREVIEW_SCREEN_FRACTION)) * scale)
        self._size = (width, int(width * 3 / 4))              # 4:3 like the camera
        self._hide_preview = tk.BooleanVar(value=False)
        self._preview = tk.Label(self.win, bg="#000000", width=self._size[0] // 8, height=self._size[1] // 16)
        self._preview.pack(padx=pad, pady=(pad, 2))
        self._state = tk.Label(self.win, text="Starting...", font=("Arial", 13, "bold"), bg=bg, fg=COLORS["info"],
                               wraplength=self._size[0])
        self._state.pack(padx=pad)
        self._attention = tk.Label(self.win, text="", font=("Arial", 10), bg=bg, fg=self._fg)
        self._attention.pack()
        self._warnings = tk.Label(self.win, text="", font=("Arial", 11, "bold"), bg=bg, fg=self._fg)
        self._warnings.pack()
        self._signals = tk.Label(self.win, text="", font=("Arial", 9), bg=bg, fg="#888888", wraplength=self._size[0])
        if SHOW_FOCUS_SIGNALS:
            self._signals.pack()
        row = tk.Frame(self.win, bg=bg)
        row.pack(pady=(2, pad))
        tk.Checkbutton(row, text="Hide preview", variable=self._hide_preview, command=self._toggle_preview,
                       bg=bg, fg=self._fg, selectcolor=bg, activebackground=bg).pack(side="left", padx=4)
        tk.Button(row, text="Recalibrate", command=self._recalibrate, font=("Arial", 9), relief="flat").pack(side="left", padx=4)

        self._place_bottom_right()
        self.win.deiconify()
        try:
            self._root.focus_force()                          # hand keyboard focus straight back
        except tk.TclError:
            pass

    # ---- public ----
    def update(self, snap, paused=False):
        try:
            if not self.win.winfo_exists():
                return
            phase = snap.get("phase")
            if "strikes" in snap:
                self._last = {"strikes": snap.get("strikes", 0), "max_strikes": snap.get("max_strikes", 0)}
            if self._last["max_strikes"]:
                self._warnings.config(text=f"Warnings {self._last['strikes']}/{self._last['max_strikes']}")

            if paused or phase == "paused":
                self._set_state("Paused - camera off", "info")
                self._attention.config(text="")
            elif phase in ("loading", "starting"):
                self._set_state(snap.get("message") or "Starting...", "info")
            elif phase == "calibrating":
                pct = int(100 * snap.get("calib_progress", 0.0))
                self._set_state(f"Calibrating... look at your screen ({pct}%)", "info")
            elif phase == "error":
                self._set_state(snap.get("message") or "Camera unavailable - timer still runs", "warn")
            elif phase == "tracking":
                text, kind = STATE_TEXT.get(snap.get("state"), ("...", "info"))
                self._set_state(text, kind)
                att = snap.get("attention")
                self._attention.config(text="" if att is None else f"Attention (last minute): {att}%")
                sig = snap.get("signals") or {}
                self._signals.config(text="  ".join(f"{k}={v}" for k, v in sig.items()))

            frame = snap.get("frame_rgb")
            if frame is not None and not self._hide_preview.get() and id(frame) != self._last_frame_id:
                self._last_frame_id = id(frame)
                self._show_frame(frame)
        except tk.TclError:
            pass

    def set_paused(self, paused):
        """Timer paused -> hide (minimise) the window like the X button; resumed -> show it again straight away."""
        try:
            if not self.win.winfo_exists():
                return
            if paused:
                self._paused_hidden = True
                self.win.withdraw()                           # fully hidden (a minimised tool window leaves a stray title bar)
            elif self._paused_hidden:
                self._paused_hidden = False
                self.win.deiconify()
                self.win.lift()
                try:
                    self._root.focus_force()                  # never take keyboard focus from what the user is doing
                except tk.TclError:
                    pass
        except tk.TclError:
            pass

    def flash(self):
        """Red flash so a strike is visible even if Windows hides the toast notification."""
        try:
            self.win.deiconify()
            self.win.lift()
            self.win.configure(bg="#c62828")
            self.win.after(700, lambda: self._safe_restore_bg())
        except tk.TclError:
            pass

    def close(self):
        try:
            self.win.destroy()
        except tk.TclError:
            pass

    # ---- internals ----
    def _safe_restore_bg(self):
        try:
            self.win.configure(bg=self._bg)
        except tk.TclError:
            pass

    def _set_state(self, text, kind):
        self._state.config(text=text, fg=COLORS.get(kind, COLORS["info"]))

    def _show_frame(self, frame_rgb):
        from PIL import Image, ImageTk
        img = Image.fromarray(frame_rgb).resize(self._size)
        self._photo = ImageTk.PhotoImage(img)                 # keep a reference or Tk drops the image
        self._preview.config(image=self._photo, width=self._size[0], height=self._size[1])

    def _toggle_preview(self):
        if self._hide_preview.get():
            self._preview.pack_forget()
        else:
            self._preview.pack(before=self._state, padx=6, pady=(6, 2))

    def _recalibrate(self):
        try:
            self._on_recalibrate()
        except Exception as e:
            print(f"[FocusWindow] recalibrate failed: {e}")

    def _place_bottom_right(self):
        self.win.update_idletasks()
        w, h = self.win.winfo_reqwidth(), self.win.winfo_reqheight()
        x = self.win.winfo_screenwidth() - w - 24
        y = self.win.winfo_screenheight() - h - 80            # clear of the Windows taskbar
        self.win.geometry(f"+{max(0, x)}+{max(0, y)}")
