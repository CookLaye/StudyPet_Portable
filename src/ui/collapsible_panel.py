"""One reusable collapsible panel (header + body) for the main screen.

Single source of truth
----------------------
* `expanded` lives ONLY in this object.  Nothing else stores a copy.
* Height is never hard-coded: collapsed = header height, expanded = header +
  body content (or a fixed height supplied by the layout, used by Pet Chat).
* Every geometry option is absolute (x, y, width, height).  No relheight,
  no relx/x mixing, so Tk's "height + relheight are added together" rule can
  never bite.
* Hiding (restricted mode) is separate from collapsing, so hiding a panel
  never changes whether it is open.
"""
import tkinter as tk

from ui.rounded_widgets import RoundedPanel


class CollapsiblePanel:
    ARROW_CLOSED = "\u25BC"   # down triangle
    ARROW_OPEN = "\u25B2"     # up triangle

    def __init__(self, parent, title, colors, scale=1.0, radius=15, on_change=None):
        self._title = title
        self._on_change = on_change
        self._expanded = False
        self._visible = True
        self._slot = None            # (x, y, w, max_h, expanded_h) from the layout
        self._refit_job = None
        self._pad_top = max(1, round(6 * scale))
        header_pady = max(1, round(2 * scale))
        bg = colors["bg_secondary"]

        self.container = RoundedPanel(parent, radius=radius, bg=colors["bg_main"], fit_content=False)
        inner = self.container.inner

        self.header = tk.Frame(inner, bg=bg, bd=0, relief="flat", cursor="hand2")
        self.header.pack(fill="x")
        self.header_label = tk.Label(
            self.header, text=self._header_text(), font=("Arial", 10, "bold"),
            bg=bg, fg=colors["text_dark"], cursor="hand2",
        )
        self.header_label.pack(pady=header_pady)
        for widget in (self.header, self.header_label):
            widget.bind("<Button-1>", self._on_click)

        # Build all panel content inside `body`.  It is packed only while expanded.
        self.body = tk.Frame(inner, bg=bg)

    # ---- state -----------------------------------------------------------
    @property
    def expanded(self):
        return self._expanded

    @property
    def visible(self):
        return self._visible

    def toggle(self):
        self.set_expanded(not self._expanded)

    def expand(self):
        self.set_expanded(True)

    def collapse(self):
        self.set_expanded(False)

    def set_expanded(self, value):
        """Idempotent: asking for the state it is already in does nothing."""
        value = bool(value)
        if value == self._expanded:
            return
        self._expanded = value
        if value:
            self.body.pack(fill="both", expand=True, pady=(self._pad_top, 0))
        else:
            self.body.pack_forget()
        self.header_label.config(text=self._header_text())
        self._apply_height()
        if self._on_change:
            self._on_change(self)

    def set_visible(self, value):
        """Show/hide without touching expanded/collapsed."""
        self._visible = bool(value)
        if not self._visible:
            self.container.place_forget()
        else:
            self._apply_geometry()

    # ---- geometry --------------------------------------------------------
    def place_at(self, x, y, width, max_height, expanded_height=None):
        """Called by MainGameScreen.layout_panels() - the only caller of place()."""
        self._slot = (int(x), int(y), int(width), int(max_height), expanded_height)
        self._apply_geometry()

    def refit(self):
        """Call after the body's content changed size (e.g. dev tools shown).
        Safe to call many times in a row; they are coalesced into one update."""
        if self._refit_job is None:
            try:
                self._refit_job = self.container.after_idle(self._run_refit)
            except tk.TclError:
                self._refit_job = None

    def required_width(self):
        """Width this panel needs to show its content un-clipped (0 while collapsed,
        because a collapsed panel only needs its header)."""
        if not self._expanded:
            return 0
        self.body.update_idletasks()
        return max(self.header.winfo_reqwidth(), self.body.winfo_reqwidth()) + 2 * self.container.padding

    def target_height(self):
        collapsed = self.header.winfo_reqheight() + 2 * self.container.padding
        if not self._expanded:
            return collapsed
        max_h = self._slot[3] if self._slot else 10 ** 6
        fixed = self._slot[4] if self._slot else None
        if fixed is not None:
            height = fixed
        else:
            self.body.update_idletasks()
            height = collapsed + self._pad_top + self.body.winfo_reqheight()
        return max(collapsed, min(height, max_h))

    # ---- internals -------------------------------------------------------
    def _header_text(self):
        arrow = self.ARROW_OPEN if self._expanded else self.ARROW_CLOSED
        return f"{self._title} {arrow}"

    def _on_click(self, _event=None):
        self.toggle()

    def _run_refit(self):
        self._refit_job = None
        try:
            self._apply_height()
        except tk.TclError:
            pass  # widget destroyed while the job was pending

    def _apply_geometry(self):
        if not self._visible or self._slot is None:
            return
        x, y, w, _max_h, _fixed = self._slot
        self.container.place(x=x, y=y, width=w, height=self.target_height())

    def _apply_height(self):
        if self._visible and self._slot is not None:
            self.container.place_configure(height=self.target_height())
