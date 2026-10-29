"""
Encouragement Burst - a calm, score-less minigame in its own small resizable window.

LEFT-CLICK anywhere on the canvas: hearts and stars burst out of the pointer, slow down, shrink and fade;
a short encouraging message pops out at the centre of the burst, floats up and fades. No score, no fail state.
Esc (or the window's close button) closes it.

    BurstWindow(parent, colors, s, on_close=callback)

All game numbers live in utils/burst_logic.py. This file only draws. Drawing uses plain Canvas items
(polygons + text); Tk has no transparency, so "fading" = blending the colour toward the background colour.
The frame loop STOPS when nothing is on screen and restarts on the next click (no idle CPU use).
All text sizes are in PIXELS (negative Tk font size) so only the window's own scale factor applies.
"""

import time
import tkinter as tk

from utils import burst_logic as B

FRAME_MS = 16                   # ~60 fps while something is moving
BASE_W, BASE_H = 960, 600       # default window size in logical units (large: lots of room for bursts)
MAX_WIDTH_FRACTION = 0.75       # the window never opens bigger than this fraction of the screen
MAX_HEIGHT_FRACTION = 0.80
MESSAGE_COLOR = "#e0457b"       # message text (readable on light backgrounds)
GLOW_COLOR = "#ffb3d1"          # soft glow drawn behind the message text
GLOW_OFFSETS = ((-2, 0), (2, 0), (0, -2), (0, 2), (-1.5, -1.5), (1.5, 1.5), (-1.5, 1.5), (1.5, -1.5))

_HEART = B.heart_points(24)
_STAR = B.star_points()


class BurstWindow:
    def __init__(self, parent, colors, s, on_close=None, rng=None):
        self.parent, self.colors, self.s, self.on_close = parent, colors, s, on_close
        self._closed = False
        self._after_id = None
        self._last_t = None
        self._p_items = {}          # id(particle) -> canvas item id
        self._m_items = {}          # id(message) -> (list of glow item ids, main item id)
        self._hint_item = None

        self.bg = colors.get("bg_accent", colors.get("bg_main", "#ffffff"))
        self.ink = colors.get("text_dark", "#333333")

        self.window = tk.Toplevel(parent)
        self.window.title("💖 Encouragement Burst")
        screen_w, screen_h = parent.winfo_screenwidth(), parent.winfo_screenheight()
        k = max(0.8, self.s(100) / 100.0)
        k = min(k, (screen_w * MAX_WIDTH_FRACTION) / BASE_W, (screen_h * MAX_HEIGHT_FRACTION) / BASE_H)
        self.k = k
        w, h = int(BASE_W * k), int(BASE_H * k)
        self.window.geometry(f"{w}x{h}+{(screen_w - w) // 2}+{(screen_h - h) // 2}")
        self.window.minsize(int(480 * k), int(300 * k))
        try:
            self.window.transient(parent)
            self.window.config(bg=self.bg)
        except Exception:
            pass
        self.window.protocol("WM_DELETE_WINDOW", self.close)

        self.world = B.BurstWorld(w, h, rng, scale=k)
        self.canvas = tk.Canvas(self.window, width=w, height=h, bg=self.bg, highlightthickness=0, bd=0)
        self.canvas.pack(fill="both", expand=True)
        self._hint_item = self.canvas.create_text(
            w / 2, h / 2, anchor="center", fill=self.ink, justify="center", text="Click anywhere  💖",
            font=("Arial", -max(14, int(20 * k)), "bold"))

        self.canvas.bind("<Button-1>", self._on_click)       # LEFT click only
        self.canvas.bind("<Configure>", self._on_configure)
        self.window.bind("<Escape>", lambda e: self.close())
        try:
            self.window.focus_force()
        except Exception:
            pass

    # ------------------------------------------------------------------ input
    def _on_configure(self, event):
        if self._closed:
            return
        self.world.resize(event.width, event.height)
        if self._hint_item is not None:
            self.canvas.coords(self._hint_item, event.width / 2, event.height / 2)

    def _on_click(self, event):
        if self._closed:
            return
        if self._hint_item is not None:                       # the hint has done its job
            self.canvas.delete(self._hint_item)
            self._hint_item = None
        palette = B.theme_palette(self.colors)
        self.world.click(event.x, event.y, palette=palette)
        if self._after_id is None:                            # restart the frame loop if it had stopped
            self._last_t = time.perf_counter()
            self._after_id = self.window.after(FRAME_MS, self._tick)

    # ------------------------------------------------------------------ frame loop
    def _tick(self):
        self._after_id = None
        if self._closed:
            return
        now = time.perf_counter()
        dt = 1 / 60.0 if self._last_t is None else now - self._last_t
        self._last_t = now
        self.world.step(dt)
        self._draw()
        if not self.world.idle:
            self._after_id = self.window.after(FRAME_MS, self._tick)

    # ------------------------------------------------------------------ drawing
    def _draw(self):
        c, k = self.canvas, self.k
        live = set()
        for p in self.world.particles:
            key = id(p)
            live.add(key)
            unit = _HEART if p.shape == "heart" else _STAR
            r = p.scale                                            # already in pixels (world scale = k)
            flat = []
            for ux, uy in unit:
                flat.append(p.x + ux * r)                   # p.x / p.y are canvas pixels (set from the click)
                flat.append(p.y + uy * r)
            color = B.blend(p.color, self.bg, p.fade)
            item = self._p_items.get(key)
            if item is None:
                self._p_items[key] = c.create_polygon(*flat, fill=color, outline="", smooth=(p.shape == "heart"))
            else:
                c.coords(item, *flat)
                c.itemconfigure(item, fill=color)
        for key in [x for x in self._p_items if x not in live]:
            c.delete(self._p_items.pop(key))

        live_m = set()
        base = max(14, int(26 * k))
        for m in self.world.messages:
            key = id(m)
            live_m.add(key)
            op = m.opacity
            main_color = B.blend(self.bg, self.colors.get("bg_primary_active", MESSAGE_COLOR), op)
            glow_color = B.blend(self.bg, "#ffffff", op * 0.85)
            font = ("Arial", -max(8, int(base * m.pop)), "bold")      # pop: grows to full size in the first moments
            entry = self._m_items.get(key)
            if entry is None:
                glows = [c.create_text(m.x + dx * k, m.y + dy * k, text=m.text, fill=glow_color, anchor="center",
                                       font=font, tags=("msg",)) for dx, dy in GLOW_OFFSETS]
                main = c.create_text(m.x, m.y, text=m.text, fill=main_color, anchor="center", font=font, tags=("msg",))
                self._m_items[key] = (glows, main)
            else:
                glows, main = entry
                popping = m.pop < 1.0
                for (dx, dy), gid in zip(GLOW_OFFSETS, glows):
                    c.coords(gid, m.x + dx * k, m.y + dy * k)
                    c.itemconfigure(gid, fill=glow_color, **({"font": font} if popping else {}))
                c.coords(main, m.x, m.y)
                c.itemconfigure(main, fill=main_color, **({"font": font} if popping else {}))
        for key in [x for x in self._m_items if x not in live_m]:
            glows, main = self._m_items.pop(key)
            for iid in glows + [main]:
                c.delete(iid)
        if self._m_items:
            c.tag_raise("msg")                    # messages always stay on top of the particles

    # ------------------------------------------------------------------ closing
    def close(self):
        if self._closed:
            return
        self._closed = True
        if self._after_id is not None:
            try:
                self.window.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None
        try:
            self.window.destroy()
        except Exception:
            pass
        if self.on_close:
            try:
                self.on_close()
            except Exception:
                pass
