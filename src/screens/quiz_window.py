import tkinter as tk
from tkinter import ttk, filedialog, messagebox, font as tkfont
import threading
import time
import math
from utils import quiz_gen
from utils.notifications import NotificationManager
from ui.simple_theme import create_rounded_button
from screens.stress_panels import _pet_fields

# Constants
QUIZ_AFFECTION_PER_CORRECT = 2
QUIZ_AFFECTION_CAP = 20
CONTENT_ALIGN = "center"
PARAGRAPH_MIN_LINES = 3


class _WrapLabel(tk.Label):
    """Label that ALWAYS stretches horizontally (fill='x') so it is as wide as its container.
    Its wraplength is set by StudyQuizWindow._rewrap from the CONTAINER width - never from its own width."""

    def pack(self, cnf=None, **kw):
        if cnf:
            kw.update(cnf)
        kw["fill"] = "x"
        px = kw.get("padx", 0)
        self._wrap_padx = sum(px) if isinstance(px, (tuple, list)) else int(px or 0)
        super().pack(**kw)
        try:
            self._owner._schedule_rewrap()
        except Exception:
            pass

class StudyQuizWindow:
    def __init__(self, parent, colors, s, app_state, pet, pet_graphics, model_manager, on_reward=None, on_close=None):
        self.parent = parent
        self.colors = colors
        self.s = s
        self.app_state = app_state
        self.pet = pet
        self.pet_graphics = pet_graphics
        self.model_manager = model_manager
        self.on_reward = on_reward
        self.on_close = on_close

        self.window = tk.Toplevel(parent)
        self.window.title("📝 Study Quiz")

        # Step 1: Window Size
        self.window.update_idletasks()
        sw = self.window.winfo_screenwidth()
        sh = self.window.winfo_screenheight()
        def clamp(n, smallest, largest): return max(smallest, min(n, largest))
        self.ww = clamp(int(0.50 * sw), 640, 1000)
        self.wh = clamp(int(0.72 * sh), 520, 820)
        self.ww = min(self.ww, int(0.95 * sw))
        self.wh = min(self.wh, int(0.92 * sh))
        cx, cy = (sw // 2) - (self.ww // 2), (sh // 2) - (self.wh // 2)
        self.window.geometry(f"{self.ww}x{self.wh}+{cx}+{cy}")
        self.window.configure(bg=colors["bg_main"])
        self.window.minsize(560, 460)
        self.window.resizable(True, True)

        # State
        self.current_quiz_id = None
        self.current_questions = []
        self.current_answers = []
        self.current_q_idx = 0
        self.gen_id = 0
        self.cancel_event = threading.Event()
        self._closed = False
        self.saved_text, self.saved_title, self.saved_count = "", "", quiz_gen.DEFAULT_QUESTIONS

        # Fonts
        self._wrap_labels = []
        self._rewrap_job = None
        self._resize_job = None
        self._last_size = (0, 0)
        self.fonts = {}
        self._setup_fonts()
        self.window.bind("<Configure>", self._on_resize)

        # Layout
        self.window.columnconfigure(0, weight=1)
        self.window.rowconfigure(1, weight=1)
        self.header_frame = tk.Frame(self.window, bg=colors["bg_main"])
        self.header_frame.grid(row=0, column=0, sticky="ew", padx=20, pady=(20, 0))
        self.body_frame = tk.Frame(self.window, bg=colors["bg_main"])
        self.body_frame.grid(row=1, column=0, sticky="nsew", padx=20, pady=10)
        self.footer_frame = tk.Frame(self.window, bg=colors["bg_main"])
        self.footer_frame.grid(row=2, column=0, sticky="ew", padx=20, pady=(0, 20))

        self.window.protocol("WM_DELETE_WINDOW", self.close)
        self.switch_view("input")

    def _setup_fonts(self):
        bases = {
            "f_title": (16, "bold", "roman"),
            "f_head": (13, "bold", "roman"),
            "f_body": (11, "normal", "roman"),
            "f_small": (9, "normal", "roman"),
            "f_button": (10, "bold", "roman"),
            "f_score": (24, "bold", "roman"),
            "f_body_bold": (11, "bold", "roman"),
            "f_small_italic": (9, "normal", "italic"),
        }
        # Initial scale
        type_scale = max(0.85, min(min(self.ww / 820, self.wh / 620), 1.5))
        for name, (size, weight, slant) in bases.items():
            self.fonts[name] = tkfont.Font(root=self.window, family="Arial", size=max(8, round(size * type_scale)), weight=weight, slant=slant)

    def _on_resize(self, event):
        if event.widget is not self.window:
            return
        w, h = event.width, event.height
        if abs(w - self._last_size[0]) < 4 and abs(h - self._last_size[1]) < 4:
            return
        self._last_size = (w, h)
        if self._resize_job is not None:
            try: self.window.after_cancel(self._resize_job)
            except Exception: pass
        self._resize_job = self.window.after(80, self._apply_resize)

    def _apply_resize(self):
        self._resize_job = None
        if self._closed or not self.window.winfo_exists():
            return
        w, h = self.window.winfo_width(), self.window.winfo_height()
        type_scale = max(0.85, min(min(w / 820, h / 620), 1.5))
        bases = {"f_title": 16, "f_head": 13, "f_body": 11, "f_small": 9,
                 "f_button": 10, "f_score": 24, "f_body_bold": 11, "f_small_italic": 9}
        for name, base in bases.items():
            self.fonts[name].configure(size=max(8, round(base * type_scale)))
        def update_btn_fonts(parent):
            for wd in parent.winfo_children():
                if hasattr(wd, "font") and isinstance(wd.font, tkfont.Font):
                    wd.font.configure(size=max(8, round(10 * type_scale)))
                    if hasattr(wd, "draw"): wd.draw()
                if wd.winfo_children(): update_btn_fonts(wd)
        update_btn_fonts(self.window)
        pad = max(self.s(20), (w - self.s(900)) // 2)
        self.header_frame.grid_configure(padx=pad)
        self.body_frame.grid_configure(padx=pad)
        self._schedule_rewrap()

    def _wrap_label(self, parent, text, font, kind="auto", **kw):
        """Wrapping label. It packs itself with fill='x' (callers may still call .pack(pady=...), which keeps fill='x').
        kind: 'short' = always centred; 'paragraph' = always left; 'auto' = centred up to 2 lines, left from PARAGRAPH_MIN_LINES."""
        lbl = _WrapLabel(parent, text=text, font=font, bg=self.colors["bg_main"], fg=self.colors["text_dark"],
                         justify="center", anchor="center", wraplength=300, **kw)
        lbl._wrap_kind, lbl._wrap_padx, lbl._owner = kind, 0, self
        self._wrap_labels.append(lbl)
        lbl.bind("<Destroy>", lambda e, l=lbl: self._forget_wrap_label(l) if e.widget is l else None)
        return lbl

    def _inner_width(self, w):
        """Width usable by children of container w: outer width minus border, highlight and internal padx on both sides."""
        try:
            total = w.winfo_width()
            if total <= 1:
                return total
            extra = 0
            for opt in ("bd", "highlightthickness", "padx"):
                try:
                    extra += int(w.winfo_pixels(w.cget(opt)))
                except Exception:
                    pass
            return total - 2 * extra
        except Exception:
            return 0

    def _forget_wrap_label(self, lbl):
        try: self._wrap_labels.remove(lbl)
        except ValueError: pass

    def _schedule_rewrap(self):
        if self._closed:
            return
        if self._rewrap_job is not None:
            try: self.window.after_cancel(self._rewrap_job)
            except Exception: pass
        try:
            self._rewrap_job = self.window.after(30, self._rewrap)
        except Exception:
            self._rewrap_job = None

    def _rewrap(self):
        """Set every label's wraplength from its CONTAINER width, then pick the alignment from the line count."""
        self._rewrap_job = None
        if self._closed:
            return
        try:
            if not self.window.winfo_exists():
                return
        except Exception:
            return
        for lbl in list(self._wrap_labels):
            try:
                if not lbl.winfo_exists():
                    continue
                cw = self._inner_width(lbl.master)
                if cw <= 1:
                    continue                      # not mapped yet; _schedule_rewrap is called again later
                avail = max(120, cw - 2 * lbl._wrap_padx - 8)
                fnt = tkfont.nametofont(lbl.cget("font"))
                if int(float(lbl.cget("wraplength"))) != avail:
                    lbl.config(wraplength=avail)
                lbl.update_idletasks()
                lines = max(1, round(lbl.winfo_reqheight() / max(1, fnt.metrics("linespace"))))  # real line count
                kind = lbl._wrap_kind
                if kind == "short":
                    align = "center"
                elif kind == "paragraph":
                    align = "left"
                else:
                    align = "center" if lines < PARAGRAPH_MIN_LINES else "left"
                anchor = "center" if align == "center" else "w"
                if int(float(lbl.cget("wraplength"))) != avail:
                    lbl.config(wraplength=avail)
                if str(lbl.cget("justify")) != align or str(lbl.cget("anchor")) != anchor:
                    lbl.config(justify=align, anchor=anchor)
            except Exception:
                continue
        for btn in getattr(self, "opt_btns", []):
            try:
                if btn.winfo_exists():
                    cw = self._inner_width(btn.master)
                    if cw > 1:
                        wl = max(120, cw - 40)
                        if int(float(btn.cget("wraplength"))) != wl:
                            btn.config(wraplength=wl)
            except Exception:
                continue
        self._fit_input_view()

    def _fit_input_view(self):
        """Input view only: hide the optional small print when the fixed widgets + a 3-line text box do not fit."""
        opt = getattr(self, "_in_optional", None)
        txt = getattr(self, "_in_txt_frame", None)
        if not opt or txt is None:
            return
        try:
            if not txt.winfo_exists():
                return
            avail = self.body_frame.winfo_height()
            if avail <= 1:
                return
            self.window.update_idletasks()
            fnt = tkfont.nametofont(self.input_text.cget("font"))
            min_text = 3 * fnt.metrics("linespace") + 8
            def need():
                return self.body_frame.winfo_reqheight() - txt.winfo_reqheight() + min_text
            for w, before, pady in opt:                       # hide, lowest priority first
                if w.winfo_manager() and need() > avail:
                    w.pack_forget()
                    self.window.update_idletasks()
            for w, before, pady in reversed(opt):             # show again, highest priority first, with a margin
                if not w.winfo_manager():
                    if need() + w.winfo_reqheight() + 2 * pady + self.s(4) <= avail:
                        w.pack(side="bottom", before=before, pady=pady)
                        self.window.update_idletasks()
        except Exception:
            pass

    def switch_view(self, view_id, clear=False):
        if clear:
            self.saved_text, self.saved_title, self.saved_count = "", "", quiz_gen.DEFAULT_QUESTIONS
        self._in_optional = []
        for f in [self.header_frame, self.body_frame, self.footer_frame]:
            for w in f.winfo_children(): w.destroy()
        if view_id == "input": self._build_input_view()
        elif view_id == "generating": self._build_generating_view()
        elif view_id == "taking": self._build_taking_view()
        elif view_id == "results": self._build_results_view()
        elif view_id == "library": self._build_library_view()
        self._schedule_rewrap()
        try: self.window.after(150, self._schedule_rewrap)
        except Exception: pass

    def _btn_set_enabled(self, btn, enabled):
        if hasattr(btn, "set_enabled"):
            btn.set_enabled(enabled)
        else:
            try: btn.config(state="normal" if enabled else "disabled")
            except: pass

    def _build_input_view(self):
        bg, fg = self.colors["bg_main"], self.colors["text_dark"]
        self._wrap_label(self.header_frame, "\U0001F4DD Make a quiz from your notes", self.fonts["f_title"], kind="short").pack()
        # Fixed widgets are packed FIRST with side="bottom" (reverse visual order); the expanding Text is packed LAST,
        # so when the window is short the Text shrinks instead of the widgets below it being clipped.
        self._in_disclaimer = self._wrap_label(self.body_frame, "Questions are written by the pet's local AI. It can make mistakes, so check anything important against your source.", self.fonts["f_small"])
        self._in_disclaimer.pack(side="bottom", pady=self.s(3))
        q_frame = tk.Frame(self.body_frame, bg=bg)
        q_frame.pack(side="bottom", pady=self.s(3))
        self.q_count_var = tk.IntVar(value=self.saved_count)
        for count in quiz_gen.QUESTION_CHOICES:
            rb = tk.Radiobutton(q_frame, text=str(count), variable=self.q_count_var, value=count,
                                font=self.fonts["f_body"], bg=bg, fg=fg,
                                selectcolor=bg, activeforeground=fg)
            rb.pack(side="left", padx=10)
        title_frame = tk.Frame(self.body_frame, bg=bg)
        title_frame.pack(side="bottom", pady=self.s(3))
        tk.Label(title_frame, text="Quiz Title (Optional):", font=self.fonts["f_body"], bg=bg, fg=fg).pack(side="left")
        self.title_entry = tk.Entry(title_frame, font=self.fonts["f_body"])
        self.title_entry.pack(side="left", padx=10)
        self.title_entry.insert(0, self.saved_title)
        self._in_note = self._wrap_label(self.body_frame, "Plain text files only. For PDFs, copy and paste the text.", self.fonts["f_small"])
        self._in_note.pack(side="bottom")
        load_btn = create_rounded_button(self.body_frame, "\U0001F4C2 Load .txt / .md file", self._load_file,
                                         style="accent", radius=20, padding=(self.s(12), self.s(6)), font=self.fonts["f_button"])
        load_btn.pack(side="bottom", pady=self.s(2))
        self.char_label = self._wrap_label(self.body_frame, "0 / 60,000 characters", self.fonts["f_body_bold"], kind="short")
        self.char_label.pack(side="bottom", pady=self.s(2))
        txt_frame = tk.Frame(self.body_frame, bg=bg)
        txt_frame.pack(side="top", expand=True, fill="both")
        self._in_txt_frame = txt_frame
        # (widget, widget it must stay in front of, pady) - hidden first-to-last when the window is too short
        self._in_optional = [(self._in_note, load_btn, 0), (self._in_disclaimer, q_frame, self.s(3))]
        self.input_text = tk.Text(txt_frame, font=self.fonts["f_body"], wrap="word", undo=True, height=1)
        self.input_text.pack(expand=True, fill="both", side="left")
        self.input_text.insert("1.0", self.saved_text)
        scrollbar = ttk.Scrollbar(txt_frame, command=self.input_text.yview)
        scrollbar.pack(side="right", fill="y")
        self.input_text.config(yscrollcommand=scrollbar.set)
        def update_counter(event=None):
            try:
                text = self.input_text.get("1.0", "end-1c")
                count = len(text)
                self.char_label.config(text=f"{count:,} / {quiz_gen.MAX_INPUT_CHARS:,} characters")
                ok, reason = quiz_gen.check_source(text)
                if not ok:
                    if reason == "too_short": self.char_label.config(text=f"{count:,} / {quiz_gen.MAX_INPUT_CHARS:,} characters \u2014 Add a bit more text")
                    elif reason == "too_long": self.char_label.config(text=f"{count:,} / {quiz_gen.MAX_INPUT_CHARS:,} characters \u2014 Too long")
                self._btn_set_enabled(self.gen_btn, ok)
                self._schedule_rewrap()
            except: pass
        self.input_text.bind("<<Modified>>", lambda e: [update_counter(), self.input_text.edit_modified(False)])
        self.window.after(10, update_counter)
        bar = tk.Frame(self.footer_frame, bg=bg)
        bar.pack(anchor="center")
        self.gen_btn = create_rounded_button(bar, "Generate quiz", self._start_generation,
                                             style="accent", radius=20, padding=(self.s(12), self.s(6)), font=self.fonts["f_button"])
        self.gen_btn.pack(side="left", padx=self.s(10))
        lib_btn = create_rounded_button(bar, "\U0001F4DA My quizzes", lambda: self.switch_view("library"),
                                        style="accent", radius=20, padding=(self.s(12), self.s(6)), font=self.fonts["f_button"])
        lib_btn.pack(side="left", padx=self.s(10))

    def _load_file(self):
        path = filedialog.askopenfilename(filetypes=[("Text files", "*.txt *.md")])
        if not path: return
        content = None
        for enc in ["utf-8", "utf-8-sig", "cp1252"]:
            try:
                with open(path, "r", encoding=enc) as f: content = f.read(); break
            except: continue
        if content is None:
            messagebox.showerror("Error", "Could not read file.")
            return
        self.input_text.delete("1.0", "end")
        self.input_text.insert("1.0", content)
        self.input_text.edit_modified(True)
        self.window.after(0, lambda: self.input_text.event_generate("<<Modified>>"))

    def _start_generation(self):
        text = self.input_text.get("1.0", "end-1c")
        n = self.q_count_var.get()
        title = self.title_entry.get().strip()
        self.saved_text, self.saved_title, self.saved_count = text, title, n
        self.switch_view("generating")
        self.gen_id += 1
        this_gen_id = self.gen_id
        self.cancel_event = threading.Event()
        threading.Thread(target=self._generation_worker, args=(this_gen_id, text, n, title), daemon=True).start()

    def _build_generating_view(self):
        try:
            pet_type, stage, emotion = _pet_fields(self.pet)
            size_px = self.s(max(70, min(int(self.wh * 0.18), 150)))
            img = self.pet_graphics.get_pet_image(pet_type, stage, "happy", size=(size_px, size_px))
            img_lbl = tk.Label(self.body_frame, image=img, bg=self.colors["bg_main"])
            img_lbl.image = img
            img_lbl.pack(pady=20)
        except Exception as e: print(f"[Quiz] Image failed: {e}")
        self.gen_text = self._wrap_label(self.body_frame, "Reading your notes...", self.fonts["f_body"])
        self.gen_text.pack(pady=10)
        self.progress = ttk.Progressbar(self.body_frame, orient="horizontal", mode="determinate")
        self.progress.pack(pady=10, padx=self.s(40), fill="x")
        bar = tk.Frame(self.footer_frame, bg=self.colors["bg_main"])
        bar.pack(anchor="center")
        cancel_btn = create_rounded_button(bar, "Cancel", self._cancel_generation,
                                          style="accent", radius=20, padding=(self.s(12), self.s(6)), font=self.fonts["f_button"])
        cancel_btn.pack(side="left", padx=self.s(10))
        self._wrap_label(self.body_frame, "This can take a minute. Pet chat may answer slowly meanwhile.", self.fonts["f_small"]).pack(pady=10)

    def _cancel_generation(self):
        self.cancel_event.set()
        self.gen_id += 1
        self.switch_view("input")

    def _generation_worker(self, gid, text, n, title):
        def on_progress(done, total):
            try: self.window.after(0, self._update_progress, gid, done, total)
            except: pass
        try:
            if self.model_manager is None or getattr(self.model_manager, "ai_unavailable", False):
                self.window.after(0, self._generation_failed, gid, "AI helper unavailable.")
                return
            if not self.model_manager.wait_until_ready(quiz_gen.WAIT_READY_SECONDS, abort=self.cancel_event.is_set):
                self.window.after(0, self._generation_failed, gid, "AI is waking up...")
                return
            questions, info = quiz_gen.generate_quiz(self.model_manager.port, text, n, cancel=self.cancel_event, on_progress=on_progress)
            if self._closed or gid != self.gen_id: return
            if info.get("cancelled"): return
            if not questions:
                self.window.after(0, self._generation_failed, gid, "Couldn't make good questions.")
            else:
                self.window.after(0, self._generation_success, gid, text, questions, info, title)
        except Exception as e:
            print(f"[Quiz] Worker error: {e}")
            try: self.window.after(0, self._generation_failed, gid, "Unexpected error.")
            except: pass

    def _update_progress(self, gid, done, total):
        if gid != self.gen_id: return
        self.progress["maximum"] = total
        self.progress["value"] = done
        self.gen_text.config(text=f"Reading your notes and writing question {done} of {total}...")

    def _generation_failed(self, gid, msg):
        if gid != self.gen_id: return
        self.switch_view("input")
        messagebox.showinfo("Quiz Gen", msg)

    def _generation_success(self, gid, text, questions, info, title):
        if gid != self.gen_id: return
        title_final = quiz_gen.make_title(title, text)
        self.current_quiz_id = quiz_gen.add_to_library(self.app_state.settings, self.app_state.set_setting, title_final, questions, info["lang"])
        self.current_questions = questions
        self.current_answers, self.current_q_idx = [], 0
        self.switch_view("taking")
        self.partial_note = f"I could only make {info['made']} of {info['requested']} questions." if info["made"] < info["requested"] else None

    def _build_taking_view(self):
        q_idx = self.current_q_idx
        q_data = self.current_questions[q_idx]
        self.canvas = tk.Canvas(self.body_frame, bg=self.colors["bg_main"], highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(self.body_frame, orient="vertical", command=self.canvas.yview)
        self.scroll_content = tk.Frame(self.canvas, bg=self.colors["bg_main"])
        self.scroll_content.bind("<Configure>", lambda e: (self.canvas.configure(scrollregion=self.canvas.bbox("all")), self._schedule_rewrap()))
        window_id = self.canvas.create_window((0, 0), window=self.scroll_content, anchor="nw")
        self.canvas.bind("<Configure>", lambda e: (self.canvas.itemconfigure(window_id, width=e.width), self._schedule_rewrap()))
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.bind("<Enter>", lambda e: self.canvas.bind_all("<MouseWheel>", self._on_mousewheel))
        self.canvas.bind("<Leave>", lambda e: self.canvas.unbind_all("<MouseWheel>"))
        self.canvas.pack(side="left", expand=True, fill="both")
        self.scrollbar.pack(side="right", fill="y")
        header = self._wrap_label(self.scroll_content, f"Question {q_idx+1} of {len(self.current_questions)}", self.fonts["f_head"])
        header.pack(pady=(0, 10))
        if hasattr(self, "partial_note") and self.partial_note and q_idx == 0:
            note = self._wrap_label(self.scroll_content, self.partial_note, self.fonts["f_small_italic"])
            note.pack(pady=(0, 10))
        q_text = self._wrap_label(self.scroll_content, q_data["q"], self.fonts["f_body_bold"])
        q_text.pack(pady=20)
        self.opt_btns = []
        for i, opt in enumerate(q_data["options"]):
            btn = tk.Button(self.scroll_content, text=f"{chr(65+i)}) {opt}", font=self.fonts["f_body"],
                            bg=self.colors["bg_main"], fg=self.colors["text_dark"],
                            command=lambda idx=i: self._select_option(idx), relief="flat", anchor="center", justify="center")
            btn.pack(fill="x", pady=5)
            self.opt_btns.append(btn)
        self.explanation_lbl = self._wrap_label(self.scroll_content, "", self.fonts["f_body"])
        self.explanation_lbl.pack(pady=20)
        bar = tk.Frame(self.footer_frame, bg=self.colors["bg_main"])
        bar.pack(anchor="center")
        self.next_btn = create_rounded_button(bar, "Next" if q_idx < len(self.current_questions)-1 else "See results",
                                             self._next_question, style="accent", radius=20, padding=(self.s(12), self.s(6)), font=self.fonts["f_button"])
        self.next_btn.pack(side="left", padx=self.s(10))
        self._btn_set_enabled(self.next_btn, False)

    def _on_mousewheel(self, event):
        self.canvas.yview_scroll(int(-1*(event.delta/120)), "units")

    def _select_option(self, idx):
        q_data = self.current_questions[self.current_q_idx]
        correct_idx = q_data["answer"]
        self.current_answers.append(idx)
        for i, btn in enumerate(self.opt_btns):
            self._btn_set_enabled(btn, False)
            if i == correct_idx: btn.config(text=f"✓ {btn['text']}", font=self.fonts["f_body_bold"])
            elif i == idx and idx != correct_idx: btn.config(text=f"✗ {btn['text']}", font=self.fonts["f_body_bold"])
        self.explanation_lbl.config(text=q_data.get("explanation", ""))
        self._btn_set_enabled(self.next_btn, True)

    def _next_question(self):
        if len(self.current_answers) <= self.current_q_idx: return
        self.current_q_idx += 1
        if self.current_q_idx < len(self.current_questions): self.switch_view("taking")
        else: self.switch_view("results")

    def _build_results_view(self):
        correct, total = quiz_gen.score_quiz(self.current_questions, self.current_answers)
        score_lbl = tk.Label(self.header_frame, text=f"{correct} / {total}",
                             font=self.fonts["f_score"], bg=self.colors["bg_main"], fg=self.colors["text_dark"])
        score_lbl.pack(pady=10)
        pct = correct / total if total > 0 else 0
        msg = "Perfect!" if pct == 1 else "Mostly correct!" if pct >= 0.7 else "Keep going!" if pct >= 0.4 else "A bit tough, keep studying!"
        feedback = self._wrap_label(self.header_frame, msg, self.fonts["f_body"])
        feedback.pack(pady=(0, 10))
        self.canvas = tk.Canvas(self.body_frame, bg=self.colors["bg_main"], highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(self.body_frame, orient="vertical", command=self.canvas.yview)
        self.scroll_content = tk.Frame(self.canvas, bg=self.colors["bg_main"])
        self.scroll_content.bind("<Configure>", lambda e: (self.canvas.configure(scrollregion=self.canvas.bbox("all")), self._schedule_rewrap()))
        window_id = self.canvas.create_window((0, 0), window=self.scroll_content, anchor="nw")
        self.canvas.bind("<Configure>", lambda e: (self.canvas.itemconfigure(window_id, width=e.width), self._schedule_rewrap()))
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.pack(side="left", expand=True, fill="both")
        self.scrollbar.pack(side="right", fill="y")
        self.canvas.bind("<Enter>", lambda e: self.canvas.bind_all("<MouseWheel>", self._on_mousewheel))
        self.canvas.bind("<Leave>", lambda e: self.canvas.unbind_all("<MouseWheel>"))
        for i, q in enumerate(self.current_questions):
            f = tk.Frame(self.scroll_content, bg=self.colors["bg_main"], pady=10)
            f.pack(fill="x", expand=True)
            q_lbl = self._wrap_label(f, f"Q{i+1}: {q['q']}", self.fonts["f_body_bold"])
            q_lbl.pack(pady=(0, 5))
            user_ans = self.current_answers[i] if i < len(self.current_answers) else None
            correct_ans = q["answer"]
            u_text = f"Your answer: {q['options'][user_ans]}" if user_ans is not None else "No answer"
            c_text = f"Correct answer: {q['options'][correct_ans]}"
            ans_lbl = self._wrap_label(f, f"{'✓' if user_ans == correct_ans else '✗'} {u_text}\n{c_text}", self.fonts["f_body"])
            ans_lbl.pack()
            expl = self._wrap_label(f, f"Note: {q.get('explanation', '')}", self.fonts["f_small"])
            expl.pack(pady=(0, 10))
            tk.Frame(f, height=1, bg=self.colors["text_dark"]).pack(fill="x", pady=10)
        bar = tk.Frame(self.footer_frame, bg=self.colors["bg_main"])
        bar.pack(anchor="center")
        create_rounded_button(bar, "Try again", self._try_again, style="accent", radius=20, padding=(self.s(12), self.s(6)), font=self.fonts["f_button"]).pack(side="left", padx=self.s(10))
        create_rounded_button(bar, "New quiz", lambda: self.switch_view("input", clear=True), style="accent", radius=20, padding=(self.s(12), self.s(6)), font=self.fonts["f_button"]).pack(side="left", padx=self.s(10))
        create_rounded_button(bar, "My quizzes", lambda: self.switch_view("library"), style="accent", radius=20, padding=(self.s(12), self.s(6)), font=self.fonts["f_button"]).pack(side="left", padx=self.s(10))
        create_rounded_button(bar, "Close", self.close, style="accent", radius=20, padding=(self.s(12), self.s(6)), font=self.fonts["f_button"]).pack(side="left", padx=self.s(10))
        self._handle_results_reward(correct, total)

    def _handle_results_reward(self, correct, total):
        try:
            lib = quiz_gen.get_library(self.app_state.settings)
            record = next((item for item in lib if item["id"] == self.current_quiz_id), None)
            attempts = record["attempts"] if record else 0
            quiz_gen.record_attempt(self.app_state.settings, self.app_state.set_setting, self.current_quiz_id, correct, total)
            if attempts == 0:
                affection = min(correct * QUIZ_AFFECTION_PER_CORRECT, QUIZ_AFFECTION_CAP)
                if affection > 0:
                    self.app_state.affection += affection
                    if self.on_reward: self.on_reward()
                    NotificationManager.notify("Nice work!", f"+{affection} Affection for your quiz!")
            if self.app_state.user:
                self.app_state.user.add_questions_answered(total, correct)
                self.app_state.save_data()
        except Exception as e: print(f"[Quiz] Reward error: {e}")

    def _try_again(self):
        self.current_questions = quiz_gen.reshuffle_quiz(self.current_questions)
        self.current_answers, self.current_q_idx = [], 0
        self.switch_view("taking")

    def _build_library_view(self):
        title = self._wrap_label(self.header_frame, "📚 My Quizzes", self.fonts["f_title"])
        title.pack(pady=(0, 10))
        lib = quiz_gen.get_library(self.app_state.settings)
        if not lib:
            empty = self._wrap_label(self.body_frame, "No saved quizzes yet.", self.fonts["f_body"])
            empty.pack(pady=40)
            bar = tk.Frame(self.footer_frame, bg=self.colors["bg_main"])
            bar.pack(anchor="center")
            create_rounded_button(bar, "Back", lambda: self.switch_view("input"), style="accent", radius=20, padding=(self.s(12), self.s(6)), font=self.fonts["f_button"]).pack(side="left", padx=self.s(10))
            return
        self._wrap_label(self.body_frame, "The 10 newest quizzes are kept.", self.fonts["f_small"], kind="short").pack(side="bottom", pady=10)
        self.canvas = tk.Canvas(self.body_frame, bg=self.colors["bg_main"], highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(self.body_frame, orient="vertical", command=self.canvas.yview)
        self.scroll_content = tk.Frame(self.canvas, bg=self.colors["bg_main"])
        self.scroll_content.bind("<Configure>", lambda e: (self.canvas.configure(scrollregion=self.canvas.bbox("all")), self._schedule_rewrap()))
        window_id = self.canvas.create_window((0, 0), window=self.scroll_content, anchor="nw")
        self.canvas.bind("<Configure>", lambda e: (self.canvas.itemconfigure(window_id, width=e.width), self._schedule_rewrap()))
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.pack(side="left", expand=True, fill="both")
        self.scrollbar.pack(side="right", fill="y")
        self.canvas.bind("<Enter>", lambda e: self.canvas.bind_all("<MouseWheel>", self._on_mousewheel))
        self.canvas.bind("<Leave>", lambda e: self.canvas.unbind_all("<MouseWheel>"))
        for item in reversed(lib):
            card = tk.Frame(self.scroll_content, bg=self.colors["bg_main"], highlightbackground=self.colors["text_dark"], highlightthickness=1, pady=10, padx=10)
            card.pack(fill="x", expand=True, pady=5, padx=20)
            q_count = len(item["questions"])
            attempts = item.get("attempts", 0)
            best_score = f"Best {item['best_score']}/{item.get('total', q_count)}" if attempts > 0 else "Not taken yet"
            info_text = f"{item['title']} | {q_count} questions | {best_score} | {attempts} attempts"
            lbl = self._wrap_label(card, info_text, self.fonts["f_body"])
            lbl.pack(pady=(0, 10))
            btn_row = tk.Frame(card, bg=self.colors["bg_main"])
            btn_row.pack(anchor="center")
            create_rounded_button(btn_row, "Play", lambda q=item: self._play_from_lib(q), style="accent", radius=20, padding=(self.s(12), self.s(6)), font=self.fonts["f_button"]).pack(side="left", padx=self.s(10))
            create_rounded_button(btn_row, "Delete", lambda q=item: self._delete_quiz(q), style="accent", radius=20, padding=(self.s(12), self.s(6)), font=self.fonts["f_button"]).pack(side="left", padx=self.s(10))
        bar = tk.Frame(self.footer_frame, bg=self.colors["bg_main"])
        bar.pack(anchor="center")
        create_rounded_button(bar, "Back", lambda: self.switch_view("input"), style="accent", radius=20, padding=(self.s(12), self.s(6)), font=self.fonts["f_button"]).pack(side="left", padx=self.s(10))

    def _play_from_lib(self, quiz_item):
        self.current_quiz_id = quiz_item["id"]
        self.current_questions = quiz_gen.reshuffle_quiz(quiz_item["questions"])
        self.current_answers, self.current_q_idx = [], 0
        self.switch_view("taking")

    def _delete_quiz(self, quiz_item):
        if messagebox.askyesno("Delete Quiz", f"Are you sure you want to delete '{quiz_item['title']}'?"):
            quiz_gen.delete_from_library(self.app_state.settings, self.app_state.set_setting, quiz_item["id"])
            self.switch_view("library")

    def close(self):
        if self._closed: return
        self._closed = True
        for _j in (self._rewrap_job, self._resize_job):
            if _j is not None:
                try: self.window.after_cancel(_j)
                except Exception: pass
        self.cancel_event.set()
        self.gen_id += 1
        if self.window.winfo_exists(): self.window.destroy()
        if self.on_close: self.on_close()
