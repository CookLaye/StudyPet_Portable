import tkinter as tk
from datetime import datetime, date
import calendar

class DatePicker(tk.Toplevel):
    """
    A calendar date picker dialog.
    When a date is selected, it updates the target entry field and destroys itself.
    """
    def __init__(self, parent, target_entry, initial=None):
        super().__init__(parent)
        self.title("Pick a date")
        self.configure(bg="#FFFFFF")
        self.resizable(False, False)
        self.target = target_entry

        # Set initial view date
        today = date.today()
        if initial:
            try:
                # Attempt to parse YYYY-MM-DD
                self._cur = datetime.strptime(initial, "%Y-%m-%d").date().replace(day=1)
            except (ValueError, TypeError):
                self._cur = today.replace(day=1)
        else:
            self._cur = today.replace(day=1)

        self._build_ui()
        self._render_calendar()

        # Make it modal
        self.update_idletasks()
        self.grab_set()

    def _build_ui(self):
        # Navigation bar
        nav = tk.Frame(self, bg="#FFFFFF")
        nav.pack(fill="x", padx=8, pady=(10, 0))

        tk.Button(nav, text="←", font=("Arial", 12), bg="#F3F4F6", fg="#374151",
                  relief="flat", bd=0, cursor="hand2", width=3,
                  command=self._prev_month).pack(side="left")

        self.month_lbl = tk.Label(nav, text="", font=("Arial", 12, "bold"),
                                   bg="#FFFFFF", fg="#111827", width=16, anchor="center")
        self.month_lbl.pack(side="left", expand=True)

        tk.Button(nav, text="→", font=("Arial", 12), bg="#F3F4F6", fg="#374151",
                  relief="flat", bd=0, cursor="hand2", width=3,
                  command=self._next_month).pack(side="right")

        # Day of week header
        dow = tk.Frame(self, bg="#FFFFFF")
        dow.pack(fill="x", padx=14, pady=(8, 0))
        for name in ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]:
            tk.Label(dow, text=name, font=("Arial", 10), bg="#FFFFFF", fg="#9CA3AF",
                     width=5, anchor="center").pack(side="left")

        # Calendar grid
        self.grid_frame = tk.Frame(self, bg="#FFFFFF")
        self.grid_frame.pack(padx=14, pady=(4, 16))

    def _render_calendar(self):
        # Clear previous grid
        for w in self.grid_frame.winfo_children():
            w.destroy()

        self.month_lbl.configure(text=self._cur.strftime("%B %Y"))
        today = date.today()

        # Get month calendar as a list of weeks
        month_cal = calendar.monthcalendar(self._cur.year, self._cur.month)

        for week in month_cal:
            row = tk.Frame(self.grid_frame, bg="#FFFFFF")
            row.pack(anchor="w")
            for day in week:
                if day == 0:
                    # Empty cell for padding
                    tk.Label(row, text="", bg="#FFFFFF", width=5, height=2).pack(side="left", padx=2, pady=2)
                else:
                    d = date(self._cur.year, self._cur.month, day)
                    is_today = (d == today)

                    btn = tk.Button(
                        row, text=str(day),
                        font=("Arial", 10, "bold" if is_today else "normal"),
                        bg="#2563EB" if is_today else "#F9FAFB",
                        fg="#FFFFFF" if is_today else "#111827",
                        activebackground="#BFDBFE", activeforeground="#111827",
                        relief="flat", bd=0, cursor="hand2", width=5, height=2,
                        command=lambda dv=d: self._pick(dv)
                    )
                    btn.pack(side="left", padx=2, pady=2)

    def _prev_month(self):
        m, y = self._cur.month - 1, self._cur.year
        if m == 0:
            m, y = 12, y - 1
        self._cur = self._cur.replace(year=y, month=m, day=1)
        self._render_calendar()

    def _next_month(self):
        m, y = self._cur.month + 1, self._cur.year
        if m == 13:
            m, y = 1, y + 1
        self._cur = self._cur.replace(year=y, month=m, day=1)
        self._render_calendar()

    def _pick(self, d):
        # Update the target entry and close dialog
        self.target.delete(0, "end")
        self.target.insert(0, d.strftime("%Y-%m-%d"))
        self.destroy()
