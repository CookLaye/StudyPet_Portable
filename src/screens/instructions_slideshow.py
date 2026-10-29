"""
Instructions slideshow - first-run tutorial shown when the user presses START
on the greeting screen and has no pet yet (AppState.is_first_time_user()).

Slides are the numbered images in <app root>/assets/instructions/ (1.png, 2.png, ...).
They are shown in NUMERIC order (so 10.png comes after 9.png, not after 1.png).

Public API:
    get_instructions_dir()            -> absolute path of assets/instructions
    find_slide_paths(directory)       -> sorted list of slide image paths ([] if none)
    SlideNavigator(total)             -> pure-Python paging logic (unit-testable, no Tk)
    InstructionsSlideshow(parent, on_finish, slide_paths=None)
        Modal Toplevel. Calls on_finish() exactly once when the user finishes
        the last slide, presses Skip, presses Esc, or closes the window.
"""

import os
import re
import tkinter as tk

SLIDE_NAME_RE = re.compile(r"^(\d+)\.(png|jpg|jpeg)$", re.IGNORECASE)
SLIDE_ASPECT = 16 / 9            # slides are 1920x1080


# --------------------------------------------------------------------------- paths
def get_instructions_dir() -> str:
    """<app root>/assets/instructions  (this file lives in <app root>/src/screens/)."""
    here = os.path.dirname(os.path.abspath(__file__))
    root = os.path.dirname(os.path.dirname(here))
    return os.path.join(root, "assets", "instructions")


def find_slide_paths(directory: str) -> list:
    """Return slide image paths sorted by their leading number. [] if folder missing/empty."""
    try:
        names = os.listdir(directory)
    except OSError:
        return []
    found = []
    for name in names:
        m = SLIDE_NAME_RE.match(name)
        if m:
            found.append((int(m.group(1)), os.path.join(directory, name)))
    found.sort(key=lambda t: t[0])
    return [p for _, p in found]


# --------------------------------------------------------------------------- pure logic
class SlideNavigator:
    """Paging state only - no Tk, so it can be unit-tested headlessly."""

    def __init__(self, total: int):
        self.total = max(0, int(total))
        self.index = 0
        self.finished = False

    @property
    def is_first(self) -> bool:
        return self.index <= 0

    @property
    def is_last(self) -> bool:
        return self.index >= self.total - 1

    def next(self) -> bool:
        """Advance. On the last slide this finishes instead. Returns True if finished now."""
        if self.finished:
            return False
        if self.is_last:
            self.finished = True
            return True
        self.index += 1
        return False

    def prev(self) -> None:
        if not self.finished and self.index > 0:
            self.index -= 1

    def skip(self) -> bool:
        """Finish immediately. Returns True only the first time (guards double callbacks)."""
        if self.finished:
            return False
        self.finished = True
        return True

    def label(self) -> str:
        return f"{self.index + 1} / {self.total}"


# --------------------------------------------------------------------------- window
class InstructionsSlideshow:
    def __init__(self, parent, on_finish, slide_paths=None, colors=None):
        from PIL import Image, ImageTk              # Pillow is already an app dependency
        from src.ui.simple_theme import simple_theme, create_rounded_button

        self._Image, self._ImageTk = Image, ImageTk
        self.parent = parent
        self.on_finish = on_finish
        self.paths = list(slide_paths) if slide_paths is not None else find_slide_paths(get_instructions_dir())
        self.nav = SlideNavigator(len(self.paths))
        self.colors = colors or simple_theme.colors
        self._cache = {}                            # index -> PhotoImage (keeps refs alive)
        self._closed = False

        bg = self.colors.get("bg_main", "#F5F5F5")
        self.window = tk.Toplevel(parent)
        self.window.title("How to use StudyPet")
        self.window.configure(bg=bg)
        self.window.resizable(False, False)
        try:
            self.window.transient(parent)
        except tk.TclError:
            pass

        # ---- size: as large as comfortably fits the screen, keeping 16:9 slides
        try:
            ui = parent.winfo_fpixels("1i") / 96.0
        except Exception:
            ui = 1.0
        s = lambda px: max(1, round(px * ui))
        sw, sh = self.window.winfo_screenwidth(), self.window.winfo_screenheight()
        bar_h = s(70)                                # room for the button bar
        max_w, max_h = int(sw * 0.85), int(sh * 0.85) - bar_h
        self.img_w = min(max_w, int(max_h * SLIDE_ASPECT))
        self.img_h = int(self.img_w / SLIDE_ASPECT)
        win_w, win_h = self.img_w, self.img_h + bar_h
        self.window.geometry(f"{win_w}x{win_h}+{max(0,(sw-win_w)//2)}+{max(0,(sh-win_h)//2 - s(20))}")

        # ---- widgets
        self.image_label = tk.Label(self.window, bg=bg, bd=0)
        self.image_label.pack(side="top")

        bar = tk.Frame(self.window, bg=bg, height=bar_h)
        bar.pack(side="bottom", fill="x")
        bar.pack_propagate(False)
        bar.columnconfigure(1, weight=1)

        self.prev_btn = create_rounded_button(bar, "◀ Previous", command=self._on_prev, style="secondary")
        self.prev_btn.grid(row=0, column=0, padx=s(14), pady=s(12), sticky="w")

        mid = tk.Frame(bar, bg=bg)
        mid.grid(row=0, column=1)
        self.counter = tk.Label(mid, text="", bg=bg, fg=self.colors.get("text_dark", "#333333"),
                                font=("Segoe UI", 11, "bold"))
        self.counter.pack()
        skip = tk.Label(mid, text="Skip tutorial", bg=bg, fg=self.colors.get("text_pink", "#888888"),
                        font=("Segoe UI", 9, "underline"), cursor="hand2")
        skip.pack()
        skip.bind("<Button-1>", lambda e: self._on_skip())

        self.next_btn = create_rounded_button(bar, "Next ▶", command=self._on_next, style="primary")
        self.next_btn.grid(row=0, column=2, padx=s(14), pady=s(12), sticky="e")

        # ---- keys / close
        for seq in ("<Right>", "<Return>", "<space>"):
            self.window.bind(seq, lambda e: self._on_next())
        self.window.bind("<Left>", lambda e: self._on_prev())
        self.window.bind("<Escape>", lambda e: self._on_skip())
        self.window.protocol("WM_DELETE_WINDOW", self._on_skip)

        if self.nav.total == 0:                      # nothing to show -> behave as finished
            self.window.after_idle(self._finish)
            return

        self.window.update_idletasks()
        try:
            self.window.grab_set()
            self.window.focus_force()
        except tk.TclError:
            pass
        self._render()

    # ---- rendering
    def _load(self, index):
        if index in self._cache:
            return self._cache[index]
        img = self._Image.open(self.paths[index]).convert("RGB")
        resample = getattr(getattr(self._Image, "Resampling", self._Image), "LANCZOS")
        img = img.resize((self.img_w, self.img_h), resample)
        photo = self._ImageTk.PhotoImage(img, master=self.window)
        self._cache[index] = photo
        return photo

    def _render(self):
        if self._closed:
            return
        i = self.nav.index
        try:
            photo = self._load(i)
            self.image_label.configure(image=photo, text="")
            self.image_label.image = photo
        except Exception as e:                       # unreadable slide: show a message, keep going
            print(f"Warning: could not load slide {self.paths[i]}: {e}")
            self.image_label.configure(image="", text="(slide could not be loaded)")
        self.counter.configure(text=self.nav.label())
        self._set_button_text(self.next_btn, "Let's go! ✔" if self.nav.is_last else "Next ▶")
        self._set_button_state(self.prev_btn, not self.nav.is_first)
        # keep memory bounded: only current +/-1 stay cached
        for k in list(self._cache):
            if abs(k - i) > 1:
                del self._cache[k]
        # preload the next slide shortly after showing this one
        if i + 1 < self.nav.total:
            self.window.after(60, lambda n=i + 1: (not self._closed) and self._safe_load(n))

    def _safe_load(self, index):
        try:
            self._load(index)
        except Exception:
            pass

    # ---- button helpers (rounded buttons are Canvas based; text/state API varies, so be defensive)
    @staticmethod
    def _set_button_text(btn, text):
        # RoundedButton (src/ui/rounded_widgets.py) keeps its label in .text and repaints via .draw()
        try:
            btn.text = text
            btn.draw()
        except Exception as e:
            print(f"Warning: could not update button text: {e}")

    @staticmethod
    def _set_button_state(btn, enabled):
        try:
            if enabled:
                btn.grid()
            else:
                btn.grid_remove()                    # hide "Previous" on the first slide
        except Exception:
            pass

    # ---- actions
    def _on_next(self):
        if self._closed:
            return
        if self.nav.next():
            self._finish()
        else:
            self._render()

    def _on_prev(self):
        if self._closed:
            return
        self.nav.prev()
        self._render()

    def _on_skip(self):
        if self.nav.skip():
            self._finish()

    def _finish(self):
        if self._closed:
            return
        self._closed = True
        self.nav.finished = True
        try:
            self.window.grab_release()
        except Exception:
            pass
        try:
            self.window.destroy()
        except Exception:
            pass
        self._cache.clear()
        if callable(self.on_finish):
            self.on_finish()
