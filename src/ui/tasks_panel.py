import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime, date, timedelta
from ui.rounded_widgets import RoundedPanel
from ui.simple_theme import simple_theme, create_rounded_button
from ui.date_picker import DatePicker
from utils.notifications import NotificationManager

class TasksPanel(RoundedPanel):
    """
    A panel for managing study tasks, featuring a visual timeline
    of timed tasks and a list of daily habits.
    """
    def __init__(self, parent, app_state, main_game_screen=None, **kwargs):
        # Extract defaults from kwargs or use fallbacks to avoid "multiple values for keyword argument"
        radius = kwargs.pop('radius', 15)
        bg = kwargs.pop('bg', simple_theme.get_color("bg_main"))
        padding = kwargs.pop('padding', 15)

        super().__init__(parent, radius=radius, bg=bg, padding=padding, **kwargs)

        self.app_state = app_state
        self.main_game_screen = main_game_screen
        self.colors = simple_theme.colors
        self.font = ("Arial", 11)

        # View settings
        self.view_days = 7
        self.view_start = date.today() - timedelta(days=2)
        self._add_vis = False
        self._bars = []
        self._daily_vis = True # Default open

        self._build_ui()
        self.after(100, self._render_timeline)
        self.after(100, self._render_daily)
        self.after(100, self._render_planned_list)

    def _build_ui(self):
        # --- Main Layout Container ---
        self.main_container = tk.Frame(self.inner, bg=self.colors["bg_main"])
        self.main_container.pack(fill="both", expand=True)
        self.main_container.grid_columnconfigure(0, weight=1)
        self.main_container.grid_rowconfigure(2, weight=6, minsize=300) # Calendar gets more space
        self.main_container.grid_rowconfigure(3, weight=2, minsize=100) # Daily habits
        self.main_container.grid_rowconfigure(4, weight=2, minsize=100) # Planned tasks

        # --- Top Navigation Bar ---
        top = tk.Frame(self.main_container, bg=self.colors["bg_main"])
        top.grid(row=0, column=0, sticky="ew", pady=(0, 10))

        nav = tk.Frame(top, bg=self.colors["bg_main"])
        nav.pack(side="left")

        create_rounded_button(nav, "←", command=self._prev_period, style="accent", radius=10, padding=(8, 4), font=("Arial", 10)).pack(side="left", padx=2)
        create_rounded_button(nav, "Go to Today", command=self._go_today, style="accent", radius=10, padding=(8, 4), font=("Arial", 10)).pack(side="left", padx=5)
        create_rounded_button(nav, "→", command=self._next_period, style="accent", radius=10, padding=(8, 4), font=("Arial", 10)).pack(side="left", padx=2)

        self.range_lbl = tk.Label(top, text="", font=("Arial", 11, "bold"), bg=self.colors["bg_main"], fg=self.colors["text_dark"])
        self.range_lbl.pack(side="left", padx=15)

        right = tk.Frame(top, bg=self.colors["bg_main"])
        right.pack(side="right")

        create_rounded_button(right, "+ Add Task", command=self._toggle_add_panel, style="accent", radius=10, padding=(12, 6), font=("Arial", 11, "bold")).pack(side="right")

        # --- Add Task Panel (initially hidden) ---
        self.add_panel = tk.Frame(self.main_container, bg=self.colors["bg_secondary"])
        # Positioned in row 1, visibility handled by _toggle_add_panel

        add_row = tk.Frame(self.add_panel, bg=self.colors["bg_secondary"])
        add_row.pack(fill="x", padx=10, pady=10)

        self.f_title = tk.Entry(add_row, font=self.font)
        self.f_title.insert(0, "Task title...")
        self.f_title.pack(side="left", fill="x", expand=True, padx=(0, 8))

        # Start date
        start_wrap = tk.Frame(add_row, bg=self.colors["bg_secondary"])
        start_wrap.pack(side="left", padx=(0, 8))
        self.f_start = tk.Entry(start_wrap, font=self.font, width=12)
        self.f_start.insert(0, str(date.today()))
        self.f_start.pack(side="left")
        create_rounded_button(start_wrap, "📅", command=lambda: DatePicker(self, self.f_start, self.f_start.get() or None), style="accent", radius=5, padding=(4, 2)).pack(side="left", padx=2)

        # Due date
        due_wrap = tk.Frame(add_row, bg=self.colors["bg_secondary"])
        due_wrap.pack(side="left", padx=(0, 8))
        self.f_due = tk.Entry(due_wrap, font=self.font, width=12)
        self.f_due.pack(side="left")
        create_rounded_button(due_wrap, "📅", command=lambda: DatePicker(self, self.f_due, self.f_due.get() or None), style="accent", radius=5, padding=(4, 2)).pack(side="left", padx=2)

        # Priority
        self.f_prio = tk.StringVar(value="Medium")
        prio_menu = ttk.Combobox(add_row, textvariable=self.f_prio, values=["High", "Medium", "Low"], width=10, state="readonly")
        prio_menu.pack(side="left", padx=(0, 8))

        create_rounded_button(add_row, "Add", command=self._add_task, style="accent", radius=10, padding=(10, 4), font=("Arial", 10, "bold")).pack(side="left", padx=2)
        create_rounded_button(add_row, "✕", command=self._toggle_add_panel, style="accent", radius=10, padding=(10, 4), font=("Arial", 10)).pack(side="left", padx=2)

        # --- Section 1: Calendar (Scrollable) ---
        timeline_container = tk.Frame(self.main_container, bg=self.colors["bg_main"])
        timeline_container.grid(row=2, column=0, sticky="nsew", padx=10, pady=10)

        tk.Label(timeline_container, text="📅 Calendar", font=("Arial", 11, "bold"), bg=self.colors["bg_main"], fg=self.colors["text_dark"]).pack(anchor="w", pady=(0, 5))

        self.timeline_canvas = tk.Canvas(timeline_container, bg="#FFFFFF", highlightthickness=1, highlightbackground="#E5E7EB")
        self.timeline_vsb = tk.Scrollbar(timeline_container, orient="vertical", command=self.timeline_canvas.yview)
        self.timeline_canvas.configure(yscrollcommand=self.timeline_vsb.set)

        self.timeline_canvas.pack(side="left", fill="both", expand=True)
        self.timeline_vsb.pack(side="right", fill="y")

        self.timeline_canvas.bind("<Configure>", lambda e: self._render_timeline())
        self.timeline_canvas.bind("<Button-1>", self._on_timeline_click)
        self.timeline_canvas.bind("<Button-3>", self._on_timeline_right_click)

        # --- Section 2: Daily Tasks (Scrollable) ---
        daily_container = tk.Frame(self.main_container, bg=self.colors["bg_main"])
        daily_container.grid(row=3, column=0, sticky="nsew", padx=10, pady=(0, 10))

        tk.Label(daily_container, text="✅ Daily Habits", font=("Arial", 11, "bold"), bg=self.colors["bg_main"], fg=self.colors["text_dark"]).pack(anchor="w", pady=(0, 5))

        self.daily_canvas = tk.Canvas(daily_container, bg=self.colors["bg_secondary"], highlightthickness=0)
        self.daily_vsb = tk.Scrollbar(daily_container, orient="vertical", command=self.daily_canvas.yview)
        self.daily_canvas.configure(yscrollcommand=self.daily_vsb.set)

        self.daily_scroll_frame = tk.Frame(self.daily_canvas, bg=self.colors["bg_secondary"])
        self.daily_scroll_frame.bind(
            "<Configure>",
            lambda e: self.daily_canvas.configure(scrollregion=self.daily_canvas.bbox("all"))
        )
        self.daily_canvas.create_window((0, 0), window=self.daily_scroll_frame, anchor="nw")

        self.daily_canvas.pack(side="left", fill="both", expand=True)
        self.daily_vsb.pack(side="right", fill="y")

        # --- Section 3: Planned Tasks (Scrollable List) ---
        planned_container = tk.Frame(self.main_container, bg=self.colors["bg_main"])
        planned_container.grid(row=4, column=0, sticky="nsew", padx=10, pady=(0, 10))

        tk.Label(planned_container, text="📅 Planned", font=("Arial", 11, "bold"), bg=self.colors["bg_main"], fg=self.colors["text_dark"]).pack(anchor="w", pady=(0, 5))

        self.planned_canvas = tk.Canvas(planned_container, bg=self.colors["bg_secondary"], highlightthickness=0)
        self.planned_vsb = tk.Scrollbar(planned_container, orient="vertical", command=self.planned_canvas.yview)
        self.planned_canvas.configure(yscrollcommand=self.planned_vsb.set)

        self.planned_scroll_frame = tk.Frame(self.planned_canvas, bg=self.colors["bg_secondary"])
        self.planned_scroll_frame.bind(
            "<Configure>",
            lambda e: self.planned_canvas.configure(scrollregion=self.planned_canvas.bbox("all"))
        )
        self.planned_canvas.create_window((0, 0), window=self.planned_scroll_frame, anchor="nw")

        self.planned_canvas.pack(side="left", fill="both", expand=True)
        self.planned_vsb.pack(side="right", fill="y")

    def _toggle_add_panel(self):
        self._add_vis = not self._add_vis
        if self._add_vis:
            self.add_panel.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        else:
            self.add_panel.grid_forget()
            self.f_due.delete(0, "end")

    def _prev_period(self):
        self.view_start -= timedelta(days=self.view_days)
        self._render_timeline()

    def _next_period(self):
        self.view_start += timedelta(days=self.view_days)
        self._render_timeline()

    def _go_today(self):
        self.view_start = date.today() - timedelta(days=2)
        self._render_timeline()

    def _add_task(self):
        print("[REPRO] TasksPanel._add_task called")
        try:
            title = self.f_title.get().strip()
            start_s = self.f_start.get().strip()
            due_s = self.f_due.get().strip()

            if not title or title == "Task title...":
                print("[REPRO] _add_task: Missing or default title")
                messagebox.showwarning("Missing title", "Please enter a task title.")
                return

            notification_msg = ""
            # If due date is blank, it's a daily task
            if not due_s:
                new_task = {
                    "title": title,
                    "priority": self.f_prio.get(),
                    "done": False,
                    "daily": True,
                    "last_reset": str(date.today()),
                    "pomo_count": 0
                }
                notification_msg = f'"{title}" added to Daily Habits (no due date provided).'
            else:
                try:
                    due_date = datetime.strptime(due_s, "%Y-%m-%d").date()
                except ValueError:
                    print(f"[REPRO] _add_task: Invalid due date format: {due_s}")
                    messagebox.showerror("Invalid date", "Use YYYY-MM-DD for due date.")
                    return

                if not start_s:
                    print("[REPRO] _add_task: Missing start date")
                    messagebox.showerror("Invalid date", "Please enter a start date for timed tasks.")
                    return

                try:
                    start_date = datetime.strptime(start_s, "%Y-%m-%d").date()
                except ValueError:
                    print(f"[REPRO] _add_task: Invalid start date format: {start_s}")
                    messagebox.showerror("Invalid date", "Use YYYY-MM-DD for start date.")
                    return

                if due_date < start_date:
                    print("[REPRO] _add_task: Due date before start date")
                    messagebox.showerror("Invalid dates", "Due date cannot be before start date.")
                    return

                new_task = {
                    "title": title,
                    "start": str(start_date),
                    "due": str(due_date),
                    "priority": self.f_prio.get(),
                    "done": False,
                    "pomo_count": 0
                }
                notification_msg = f'"{title}" added to Planned Tasks.'

            print(f"[REPRO] _add_task: Appending task: {title}")
            self.app_state.tasks.append(new_task)
            print(f"[REPRO] _add_task: Current tasks count: {len(self.app_state.tasks)}")

            if self.app_state.save_tasks():
                print("[REPRO] _add_task: save_tasks succeeded")
                NotificationManager.notify("Task Added", notification_msg)
            else:
                print("[REPRO] _add_task: save_tasks failed")

            # --- RENDER FIRST (to ensure it happens even if cleanup fails) ---
            try:
                print("[REPRO] _add_task: Rendering views...")
                self._render_timeline()
                self._render_daily()
                self._render_planned_list()
                print("[REPRO] _add_task: Rendering complete")
            except Exception as render_e:
                print(f"[REPRO] _add_task: Rendering error: {render_e}")
                import traceback
                traceback.print_exc()

            # Sync with Study Timer panel if available
            if self.main_game_screen and hasattr(self.main_game_screen, 'update_task_selector_list'):
                self.main_game_screen.update_task_selector_list()

            # --- CLEANUP LAST ---
            try:
                print("[REPRO] _add_task: Starting UI cleanup...")
                self.f_title.delete(0, "end")
                self.f_due.delete(0, "end")
                self._toggle_add_panel()
                print("[REPRO] _add_task: UI cleanup complete")
            except Exception as cleanup_e:
                print(f"[REPRO] _add_task: UI cleanup error: {cleanup_e}")
                import traceback
                traceback.print_exc()

        except Exception as e:
            print(f"[REPRO] _add_task: FATAL EXCEPTION: {e}")
            import traceback
            traceback.print_exc()

    def _render_timeline(self):
        self.timeline_canvas.delete("all")
        self._bars = []

        w = self.timeline_canvas.winfo_width()
        if w <= 1: return

        today = date.today()
        view_end = self.view_start + timedelta(days=self.view_days - 1)
        col_w = w / self.view_days

        self.range_lbl.configure(text=f"{self.view_start.strftime('%b %d')} – {view_end.strftime('%b %d, %Y')}")

        # Draw day columns
        for i in range(self.view_days):
            d = self.view_start + timedelta(days=i)
            x0, x1 = i*col_w, (i+1)*col_w

            # Weekend coloring
            if d.weekday() >= 5:
                self.timeline_canvas.create_rectangle(x0, 0, x1, 9999, fill="#F9FAFB", outline="")

            # Today coloring
            if d == today:
                self.timeline_canvas.create_rectangle(x0, 0, x1, 9999, fill="#EFF6FF", outline="")

            # Day lines
            self.timeline_canvas.create_line(i*col_w, 0, i*col_w, 9999, fill="#E5E7EB", width=1)

        # Header line - increased height to prevent overlap
        self.timeline_canvas.create_line(0, 65, w, 65, fill="#D1D5DB", width=1)

        # Draw day labels
        for i in range(self.view_days):
            d = self.view_start + timedelta(days=i)
            cx = i*col_w + col_w/2
            day_col = "#2563EB" if d == today else ("#9CA3AF" if d.weekday() >= 5 else "#6B7280")
            self.timeline_canvas.create_text(cx, 20, text=d.strftime("%a").upper(), font=("Arial", 9), fill=day_col)

            if d == today:
                r = 10
                self.timeline_canvas.create_oval(cx-r, 30-r, cx+r, 30+r, fill="#2563EB", outline="")
                self.timeline_canvas.create_text(cx, 30, text=str(d.day), font=("Arial", 10, "bold"), fill="#FFFFFF")
            else:
                self.timeline_canvas.create_text(cx, 30, text=str(d.day), font=("Arial", 10, "bold"), fill=day_col)

        # Filter and place tasks
        visible = []
        for idx, task in enumerate(self.app_state.tasks):
            if task.get("daily"): continue
            raw_s = task.get("start")
            raw_e = task.get("due")
            if not raw_s or not raw_e: continue

            try:
                s = date.fromisoformat(raw_s)
                e = date.fromisoformat(raw_e)
                if s > view_end or e < self.view_start: continue
                visible.append({**task, "_s": s, "_e": e, "_idx": idx})
            except ValueError: continue

        visible.sort(key=lambda t: (t["_s"], t["_e"]))

        # Simple row packing - reduced row height from 30 to 25
        row_ends = []
        for task in visible:
            placed = False
            for i, end in enumerate(row_ends):
                if end < task["_s"]:
                    row_ends[i] = task["_e"]
                    task["_row"] = i
                    placed = True
                    break
            if not placed:
                task["_row"] = len(row_ends)
                row_ends.append(task["_e"])

        # Render task bars
        for task in visible:
            row = task["_row"]
            y0 = 45 + row*25 + 5
            y1 = y0 + 20

            cs = max(task["_s"], self.view_start)
            ce = min(task["_e"], view_end)
            x0 = (cs - self.view_start).days * col_w + 5
            x1 = ((ce - self.view_start).days + 1) * col_w - 5

            # Priority colors
            prio = task.get("priority", "Medium")
            clr = "#EF4444" if prio == "High" else ("#F59E0B" if prio == "Medium" else "#22C55E")
            if task["done"]: clr = "#D1D5DB"

            self._draw_rounded_rect(x0, y0, x1, y1, r=6, fill=clr)

            bar_w = x1 - x0
            label = task["title"] + (f" 🍅{task.get('pomo_count', 0)}" if task.get('pomo_count', 0) > 0 else "")
            if bar_w > 20:
                self.timeline_canvas.create_text((x0+x1)/2, (y0+y1)/2, text=label, font=("Arial", 9, "bold" if not task["done"] else ""),
                                        fill="#FFFFFF" if not task["done"] else "#6B7280", width=max(bar_w-10, 1), anchor="center")

            self._bars.append((x0, y0, x1, y1, task["_idx"]))

        self.timeline_canvas.configure(scrollregion=(0, 0, w, 40 + len(row_ends)*25 + 40))

    def _draw_rounded_rect(self, x0, y0, x1, y1, r=6, fill="#000"):
        # Standard Tkinter rounded rect approximation
        self.timeline_canvas.create_rectangle(x0+r, y0, x1-r, y1, fill=fill, outline="")
        self.timeline_canvas.create_rectangle(x0, y0+r, x1, y1-r, fill=fill, outline="")
        self.timeline_canvas.create_oval(x0, y0, x0+2*r, y0+2*r, fill=fill, outline="")
        self.timeline_canvas.create_oval(x1-2*r, y0, x1, y0+2*r, fill=fill, outline="")
        self.timeline_canvas.create_oval(x0, y1-2*r, x0+2*r, y1, fill=fill, outline="")
        self.timeline_canvas.create_oval(x1-2*r, y1-2*r, x1, y1, fill=fill, outline="")

    def _on_timeline_click(self, event):
        cx, cy = event.x, self.timeline_canvas.canvasy(event.y)
        for x0, y0, x1, y1, idx in self._bars:
            if x0 <= cx <= x1 and y0 <= cy <= y1:
                self._open_task_dialog(idx)
                break

    def _on_timeline_right_click(self, event):
        cx, cy = event.x, self.timeline_canvas.canvasy(event.y)
        for x0, y0, x1, y1, idx in self._bars:
            if x0 <= cx <= x1 and y0 <= cy <= y1:
                if messagebox.askyesno("Delete task", f'Delete "{self.app_state.tasks[idx]["title"]}"?'):
                    self.app_state.tasks.pop(idx)
                    if self.app_state.save_data():
                        NotificationManager.notify("Task Deleted", "Task removed successfully.")
                    self._render_timeline()
                    self._render_planned_list()
                break

    def _open_task_dialog(self, idx):
        task = self.app_state.tasks[idx]
        is_daily = task.get("daily", False)
        dlg = tk.Toplevel(self)
        dlg.title("Edit Task")
        dlg.place(relwidth=0.4, relheight=0.3)
        dlg.resizable(False, False)
        dlg.grab_set()

        # UI similar to todo_app.pyw but using simple_theme/standard tk
        frame = tk.Frame(dlg, padx=20, pady=20)
        frame.pack(fill="both", expand=True)

        tk.Label(frame, text="Edit Task", font=("Arial", 14, "bold")).pack(pady=(0, 10))

        t_row = tk.Frame(frame)
        t_row.pack(fill="x", pady=5)
        tk.Label(t_row, text="Title:").pack(side="left")
        title_e = tk.Entry(t_row)
        title_e.insert(0, task["title"])
        title_e.pack(side="left", fill="x", expand=True, padx=5)

        p_row = tk.Frame(frame)
        p_row.pack(fill="x", pady=5)
        tk.Label(p_row, text="Priority:").pack(side="left")
        prio_var = tk.StringVar(value=task["priority"])
        prio_menu = ttk.Combobox(p_row, textvariable=prio_var, values=["High", "Medium", "Low"], state="readonly")
        prio_menu.pack(side="left", padx=5)

        def apply():
            new_title = title_e.get().strip()
            if not new_title: return
            task["title"] = new_title
            task["priority"] = prio_var.get()
            if self.app_state.save_tasks():
                NotificationManager.notify("Task Updated", "Changes saved successfully.")
            self._render_timeline()
            self._render_daily()
            self._render_planned_list()
            dlg.destroy()

        def toggle_done():
            task["done"] = not task["done"]
            if self.app_state.save_tasks():
                NotificationManager.notify("Task Updated", "Status updated successfully.")
            self._render_timeline()
            self._render_daily()
            self._render_planned_list()
            dlg.destroy()

        def delete_task():
            if messagebox.askyesno("Delete Task", f'Delete "{task["title"]}"?'):
                self.app_state.tasks.pop(idx)
                if self.app_state.save_tasks():
                    NotificationManager.notify("Task Deleted", "Task removed successfully.")
                self._render_timeline()
                self._render_daily()
                self._render_planned_list()
                dlg.destroy()

        btn_row = tk.Frame(frame)
        btn_row.pack(pady=20)
        create_rounded_button(btn_row, "Save", command=apply, style="accent", radius=5).pack(side="left", padx=5)
        create_rounded_button(btn_row, "Mark Done", command=toggle_done, style="accent", radius=5).pack(side="left", padx=5)
        create_rounded_button(btn_row, "Focus", command=lambda: self._focus_task(idx, dlg), style="accent", radius=5).pack(side="left", padx=5)
        create_rounded_button(btn_row, "Delete", command=delete_task, style="accent", radius=5).pack(side="left", padx=5)
        create_rounded_button(btn_row, "Close", command=dlg.destroy, style="accent", radius=5).pack(side="left", padx=5)

    def _focus_task(self, idx, dlg):
        """Links the current study session to this task and closes the dialog."""
        if self.main_game_screen:
            self.main_game_screen.select_task_for_session(idx)
        else:
            messagebox.showerror("Error", "Main game screen not linked.")
        dlg.destroy()

    def _render_daily(self):
        for w in self.daily_scroll_frame.winfo_children():
            w.destroy()

        today = str(date.today())
        daily_tasks = [(i, t) for i, t in enumerate(self.app_state.tasks) if t.get("daily")]

        if not daily_tasks:
            tk.Label(self.daily_scroll_frame, text="No daily tasks yet.", bg=self.colors["bg_secondary"], fg=self.colors["text_dark"]).pack(pady=10)
        else:
            for idx, task in daily_tasks:
                if task.get("last_reset") != today:
                    task["done"] = False
                    task["last_reset"] = today
                    self.app_state.save_data()

                row = tk.Frame(self.daily_scroll_frame, bg=self.colors["bg_secondary"])
                row.pack(fill="x", padx=5, pady=2)

                var = tk.BooleanVar(value=task["done"])
                chk = tk.Checkbutton(row, variable=var, bg=self.colors["bg_secondary"],
                                     command=lambda i=idx, v=var: self._toggle_daily(i, v))
                chk.pack(side="left")

                tk.Label(row, text=task["title"], bg=self.colors["bg_secondary"],
                         fg=self.colors["text_dark"], font=("Arial", 10)).pack(side="left", padx=5)

                create_rounded_button(row, "✕", command=lambda i=idx: self._delete_task(i),
                                      style="accent", radius=5, padding=(4, 2)).pack(side="right")

        # Explicitly update scrollregion after adding widgets
        self.daily_canvas.update_idletasks()
        self.daily_canvas.configure(scrollregion=self.daily_canvas.bbox("all"))

    def _render_planned_list(self):
        """Renders a scrollable list of non-daily tasks sorted by due date."""
        for w in self.planned_scroll_frame.winfo_children():
            w.destroy()

        # Filter and sort non-daily tasks that have a due date
        planned_tasks = []
        for i, t in enumerate(self.app_state.tasks):
            if not t.get("daily") and t.get("due"):
                planned_tasks.append((i, t))

        # Sort by due date ascending
        planned_tasks.sort(key=lambda x: x[1].get("due", "9999-12-31"))

        if not planned_tasks:
            tk.Label(self.planned_scroll_frame, text="No planned tasks.", bg=self.colors["bg_secondary"], fg=self.colors["text_dark"]).pack(pady=10)
        else:
            for idx, task in planned_tasks:
                row = tk.Frame(self.planned_scroll_frame, bg=self.colors["bg_secondary"])
                row.pack(fill="x", padx=5, pady=2)

                var = tk.BooleanVar(value=task["done"])
                chk = tk.Checkbutton(row, variable=var, bg=self.colors["bg_secondary"],
                                     command=lambda i=idx, v=var: self._toggle_planned(i, v))
                chk.pack(side="left")

                tk.Label(row, text=task["title"], bg=self.colors["bg_secondary"],
                         fg=self.colors["text_dark"], font=("Arial", 10), width=20, anchor="w").pack(side="left", padx=5)

                tk.Label(row, text=task["due"], bg=self.colors["bg_secondary"],
                         fg=self.colors["text_medium"], font=("Arial", 9), width=12).pack(side="left", padx=5)

                tk.Label(row, text=task["priority"], bg=self.colors["bg_secondary"],
                         fg=self.colors["text_dark"], font=("Arial", 9), width=8).pack(side="left", padx=5)

                create_rounded_button(row, "✕", command=lambda i=idx: self._delete_planned(i),
                                      style="accent", radius=5, padding=(4, 2)).pack(side="right")

        self.planned_canvas.update_idletasks()
        self.planned_canvas.configure(scrollregion=self.planned_canvas.bbox("all"))

    def _toggle_planned(self, idx, var):
        self.app_state.tasks[idx]["done"] = var.get()
        if self.app_state.save_tasks():
            NotificationManager.notify("Task Updated", "Status updated successfully.")
        self._render_planned_list()
        self._render_timeline()

    def _delete_planned(self, idx):
        if messagebox.askyesno("Delete Task", f"Delete '{self.app_state.tasks[idx]['title']}'?"):
            self.app_state.tasks.pop(idx)
            if self.app_state.save_tasks():
                NotificationManager.notify("Task Deleted", "Task removed successfully.")
            self._render_planned_list()
            self._render_timeline()

    def _toggle_daily(self, idx, var):
        self.app_state.tasks[idx]["done"] = var.get()
        if self.app_state.save_tasks():
            NotificationManager.notify("Habit Updated", "Status updated successfully.")
        self._render_daily()

    def _delete_task(self, idx):
        if messagebox.askyesno("Delete Task", f"Delete '{self.app_state.tasks[idx]['title']}'?"):
            self.app_state.tasks.pop(idx)
            if self.app_state.save_tasks():
                NotificationManager.notify("Habit Deleted", "Habit removed successfully.")
            self._render_daily()
            self._render_timeline()
            self._render_planned_list()
