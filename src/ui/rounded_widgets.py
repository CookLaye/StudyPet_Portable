import tkinter as tk
from tkinter import font as tkfont

class RoundedButton(tk.Frame):
    def __init__(self, parent, text="", command=None, radius=20, bg="#4A90E2", fg="#FFFFFF", hover_bg=None, active_bg=None, padding=(14, 8), font=("Segoe UI", 11, "bold")):
        try:
            surface_bg = parent.cget("bg")
        except Exception:
            surface_bg = "#FFFFFF"

        super().__init__(parent, bg=surface_bg)
        self.command = command
        self.radius = radius
        self.bg_normal = bg
        self.bg_hover = hover_bg or bg
        self.bg_active = active_bg or self.bg_hover
        self.fg = fg
        self.surface_bg = surface_bg
        self.padding = padding
        self.text = text
        self.font = tkfont.Font(self, font=font)
        self.canvas = tk.Canvas(self, highlightthickness=0, bd=0, bg=surface_bg)
        self.canvas.pack(fill="both", expand=True)
        self.state = "normal"
        self.enabled = True
        self._saved_command = command
        self.bind_events()
        self.draw()

    def bind_events(self):
        self.canvas.bind("<Enter>", lambda e: self.set_state("hover"))
        self.canvas.bind("<Leave>", lambda e: self.set_state("normal"))
        self.canvas.bind("<ButtonPress-1>", lambda e: self.set_state("active"))
        self.canvas.bind("<ButtonRelease-1>", self._on_click)
        self.bind("<Configure>", lambda e: self.draw())

    def set_state(self, st):
        self.state = st
        self.draw()

    def _on_click(self, e):
        self.set_state("hover")
        if not self.enabled:
            return
        if callable(self.command):
            try:
                self.command()
            except Exception:
                pass

    def draw_round_rect(self, x1, y1, x2, y2, r, **kwargs):
        points = [
            x1+r, y1,
            x2-r, y1,
            x2, y1,
            x2, y1+r,
            x2, y2-r,
            x2, y2,
            x2-r, y2,
            x1+r, y2,
            x1, y2,
            x1, y2-r,
            x1, y1+r,
            x1, y1,
        ]
        return self.canvas.create_polygon(points, smooth=True, **kwargs)

    def draw(self):
        self.canvas.delete("all")
        px, py = self.padding
        txt_w = self.font.measure(self.text)
        txt_h = self.font.metrics("linespace")
        w = txt_w + px * 2
        h = txt_h + py * 2
        self.canvas.config(width=w, height=h)

        try:
            self.canvas.configure(bg=self.surface_bg)
        except Exception:
            pass

        if not self.enabled:
            fill = "#CCCCCC"
            text_color = "#666666"
        elif self.state == "active":
            fill = self.bg_active
            text_color = self.fg
        elif self.state == "hover":
            fill = self.bg_hover
            text_color = self.fg
        else:
            fill = self.bg_normal
            text_color = self.fg

        # Clamp radius so it fits the button dimensions
        r = min(self.radius, w // 2, h // 2)

        # Derive a subtle border: slightly darker than the fill so the shape
        # is always readable regardless of parent background color.
        try:
            r_val = int(fill[1:3], 16)
            g_val = int(fill[3:5], 16)
            b_val = int(fill[5:7], 16)
            border = "#{:02x}{:02x}{:02x}".format(
                max(0, r_val - 30),
                max(0, g_val - 30),
                max(0, b_val - 30),
            )
        except Exception:
            border = "#CCCCCC"

        self.draw_round_rect(1, 1, w - 1, h - 1, r, fill=fill, outline=border, width=1)
        self.canvas.create_text(w // 2, h // 2, text=self.text, font=self.font, fill=text_color)
        self.update_idletasks()

    def set_text(self, text: str):
        self.text = text
        self.draw()

    def set_enabled(self, enabled: bool):
        self.enabled = bool(enabled)
        if self.enabled:
            self.command = self._saved_command
        self.draw()

class RoundedPanel(tk.Frame):
    def __init__(self, parent, radius=20, bg="#FAFAFA", padding=8, fit_content=True):
        super().__init__(parent, bg=parent.cget("bg"), bd=0, highlightthickness=0)
        self.radius = radius
        # Ensure padding is at least equal to radius to prevent content from
        # overlapping the rounded corners of the background.
        self.padding = max(padding, radius)
        self.bg_color = bg
        self.fit_content = fit_content
        # Optional minimum size hints (content can exceed these)
        self._min_width = None
        self._min_height = None
        self.canvas = tk.Canvas(self, highlightthickness=0, bd=0, bg=self.cget("bg"))
        self.canvas.pack(fill="both", expand=True)
        self.inner = tk.Frame(self.canvas, bg=self.bg_color, highlightthickness=0, bd=0)
        self.inner.pack_propagate(False)
        self._win_id = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self._bg_id = None
        self.bind("<Configure>", self._on_frame_configure)
        self.inner.bind("<Configure>", self._on_inner_configure)
        self._draw_scheduled = False
        self.draw()

    def set_padding(self, padding: int):
        """Update internal padding while keeping content visible."""
        self.padding = padding
        self._schedule_draw()

    def _schedule_draw(self, event=None):
        if not self._draw_scheduled:
            self._draw_scheduled = True
            self.after_idle(lambda: self.draw(event))

    def _on_frame_configure(self, event=None):
        self._schedule_draw(event)

    def _on_inner_configure(self, event=None):
        self._schedule_draw()

    def set_min_size(self, width: int | None = None, height: int | None = None):
        """Set minimum content area size (excluding padding)."""
        if width is not None:
            self._min_width = int(width)
        if height is not None:
            self._min_height = int(height)
        self._schedule_draw()

    def draw_round_rect(self, x1, y1, x2, y2, r, **kwargs):
        points = [
            x1+r, y1,
            x2-r, y1,
            x2, y1,
            x2, y1+r,
            x2, y2-r,
            x2, y2,
            x2-r, y2,
            x1+r, y2,
            x1, y2,
            x1, y2-r,
            x1, y1+r,
            x1, y1,
        ]
        return self.canvas.create_polygon(points, smooth=True, **kwargs)

    def draw(self, event=None):
        self._draw_scheduled = False
        self.update_idletasks()

        # Use event dimensions if available, otherwise use winfo
        if event:
            frame_w = event.width
            frame_h = event.height
        else:
            frame_w = self.winfo_width()
            frame_h = self.winfo_height()

        # Measure content including requested size, border, and internal padding
        req_w = self.inner.winfo_reqwidth()
        req_h = self.inner.winfo_reqheight()
        # Available size based on outer widget
        avail_w = max(1, frame_w - self.padding * 2)
        avail_h = max(1, frame_h - self.padding * 2)

        if self.fit_content:
            # Expand to fit content if it's larger than available space
            width = max(req_w, avail_w)
            height = max(req_h, avail_h)
        else:
            # Constrain to available space to allow internal scrolling
            # If we're not yet mapped, avail_w/h will be 1. Use req_w/h as fallback.
            if self.winfo_ismapped():
                width = avail_w
                height = avail_h
            else:
                width = req_w
                height = req_h

        # Apply minimum size hints (give priority when larger than content)
        if self._min_width is not None:
            width = max(width, self._min_width)
        if self._min_height is not None:
            height = max(height, self._min_height)

        # Final total dimensions
        total_w = width + self.padding * 2
        total_h = height + self.padding * 2

        # Hard cap to actual frame dimensions for constrained panels
        if not self.fit_content:
            total_w = min(total_w, max(1, frame_w))
            total_h = min(total_h, max(1, frame_h))

        total_w = max(total_w, 20)
        total_h = max(total_h, 20)

        # Update canvas size and final dimensions
        try:
            self.canvas.config(width=total_w, height=total_h)
        except Exception:
            pass



        r = min(self.radius, total_w // 2, total_h // 2)
        if self._bg_id is not None:
            try:
                self.canvas.delete(self._bg_id)
            except Exception:
                pass
        self._bg_id = self.draw_round_rect(2, 2, total_w - 2, total_h - 2, r, fill=self.bg_color, outline="")

        # Position inner frame and ensure it has the measured width/height
        self.canvas.coords(self._win_id, self.padding, self.padding)
        try:
            self.inner.config(width=width, height=height)
            self.canvas.itemconfigure(self._win_id, width=width, height=height)
            # Crucially, if we are not fitting content, we want the canvas NOT to scroll
            # so that the internal widget handles it.
            self.canvas.configure(scrollregion=(0, 0, total_w, total_h))
        except Exception:
            pass
