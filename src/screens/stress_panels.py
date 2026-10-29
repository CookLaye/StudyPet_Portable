"""
Shared building blocks of the stress check-in.

Each panel fills a container Frame, so the SAME code runs inside a pop-up window
(top-bar Diagnosis / Mailbox) and inside the full-screen start-up gate:

    ScanPanel    webcam face scan (button starts it; no skip/cancel)
    QuizPanel    the 7 DASS-21 questions (question + chosen answer in bold)
    LetterPanel  write a letter, feed it to the pet, "thinking" pause

Every panel has destroy() (stops timers / camera) and reports back through a callback.
"""

import tkinter as tk
from tkinter import ttk

from stress_scan.live_readout import format_headline, format_detail, bar_rows
from utils.stress_diagnosis import (
    score_facial_scan,
    score_quiz,
    QUIZ_QUESTIONS,
    QUIZ_RESPONSE_LABELS,
    EMOTION_SCALE,
    score_emotion
)

# ----------------------------- tunables ---------------------------------------
POLL_MS = 66                  # scan UI refresh (~15 fps)
SCAN_MAX_ATTEMPTS = 3         # after this many failed scans, continue without the face score
SCAN_SUCCESS_PAUSE_MS = 900
SCAN_GIVE_UP_PAUSE_MS = 2800
DEFAULT_PREVIEW = (640, 480)  # used before live_scan reports its own PREVIEW_SIZE
SHOW_MODEL_READOUT = True      # live "what the model predicts right now" panel under the camera preview
READOUT_RESERVE_PX = 120       # vertical space (before self.s()) the read-out needs; used by the layout maths
READOUT_BAR_H = 44             # height of the 8 mini bars (before self.s())

# --- Letter-feeding animation timing (milliseconds) - tune here ---
FEED_FLIGHT_MS = 2400         # how long the envelope takes to reach the pet
FEED_FRAME_MS = 30            # delay between animation frames
FEED_STEPS = FEED_FLIGHT_MS // FEED_FRAME_MS
FEED_CHOMP_MS = 450           # how long the pet stays 'big' after the letter arrives
THINK_MS = 2000               # "Thinking it over..." pause before the result

# --- Mailbox look (tune here) ---
TEXT_WIDTH_FRACTION = 0.55
LETTER_BG = "#F6D58E"            # paper colour of the flying letter (must differ from every theme's bg_main)
LETTER_BORDER = "#8A5A14"        # outline of the letter
LETTER_BORDER_PX = 3
LETTER_ICON_SIZE = 44            # font size of the envelope emoji inside the letter (was 20)
LETTER_PAD_X = 22                # padding around the emoji, in px before self.s()
LETTER_PAD_Y = 14
PET_SIZE_FACTOR = 0.95           # pet may use up to this share of the right-hand area's width...
PET_HEIGHT_FACTOR = 0.92         # ...and of the container's height
PET_BASE_PX_WINDOW = 420         # default pet size in the pop-up window (was 180)
CHOMP_SCALE = 1.1                # unchanged behaviour: pet grows 10% when the letter lands
# Where the letter should land on the pet, as a fraction of the pet image (x, y).
# (0.5, 0.5) = centre. Measured by eye on the 500x500 Axolotl Mouth_Open art:
MOUTH_TARGET = {
    ("axolotl", 2): (0.47, 0.54),   # Baby
    ("axolotl", 3): (0.39, 0.54),   # Child
    ("axolotl", 4): (0.42, 0.41),   # Grown
}


class _PanelBase:
    def __init__(self, container, colors, s, font_scale=1.0):
        self.container = container
        self.colors = colors
        self.s = s
        self.fs = font_scale
        self._after_ids = []
        self._destroyed = False

    # font tuple helper: size is in points before font_scale
    def f(self, size, bold=False, italic=False):
        style = " ".join(x for x in (("bold" if bold else ""), ("italic" if italic else "")) if x)
        size = max(7, int(round(size * self.fs)))
        return ("Arial", size, style) if style else ("Arial", size)

    def alive(self):
        if self._destroyed:
            return False
        try:
            return bool(self.container.winfo_exists())
        except Exception:
            return False

    def after(self, ms, fn):
        try:
            aid = self.container.after(ms, fn)
            self._after_ids.append(aid)
            return aid
        except Exception:
            return None

    def cancel_timers(self):
        for aid in self._after_ids:
            try:
                self.container.after_cancel(aid)
            except Exception:
                pass
        self._after_ids = []

    def clear(self):
        for w in list(self.container.winfo_children()):
            try:
                w.destroy()
            except Exception:
                pass

    def button(self, parent, text, command, primary=True, **pack_kw):
        btn = tk.Button(
            parent, text=text, command=command,
            bg=self.colors.get("accent", "#4CAF50") if primary else self.colors["bg_secondary"],
            fg="white" if primary else self.colors["text_dark"],
            font=self.f(11, bold=True), relief="flat",
            padx=self.s(int(22 * self.fs)), pady=self.s(int(8 * self.fs)), cursor="hand2",
        )
        if pack_kw is not None:
            btn.pack(**pack_kw)
        return btn

    def label(self, parent, text, size=11, bold=False, italic=False, color=None, wrap=None, justify="center"):
        kw = dict(text=text, font=self.f(size, bold, italic), bg=self.colors["bg_main"],
                  fg=color or self.colors["text_dark"], justify=justify)
        if wrap:
            kw["wraplength"] = wrap
        return tk.Label(parent, **kw)

    def destroy(self):
        self._destroyed = True
        self.cancel_timers()


# =============================================================================
# Face scan
# =============================================================================
class ScanPanel(_PanelBase):
    def __init__(self, container, colors, s, on_done, title="Facial Scan",
                 font_scale=1.0, preview_scale=1.0, max_attempts=SCAN_MAX_ATTEMPTS,
                 scanner_factory=None):
        """
        on_done(score): score is 0-42 (float) or None when the face scan could not be done
                        (after max_attempts failures) - the diagnosis then uses the other parts.
        scanner_factory: optional callable returning an object like LiveScanner (for tests).
        """
        super().__init__(container, colors, s, font_scale)
        self.on_done = on_done
        self.title = title
        self.preview_scale = preview_scale
        self.max_attempts = max_attempts
        self.scanner_factory = scanner_factory
        self.attempts = 0
        self._scanner = None
        self._poll_id = None
        self._photo = None
        self._last_frame_id = None
        self._finished = False
        self._preview_size = DEFAULT_PREVIEW
        self._show_intro()

    # ------------------------------------------------------------ intro
    def _show_intro(self, note=None):
        self._stop_scanner()
        self.clear()
        self.label(self.container, self.title, 16, bold=True).pack(pady=(0, self.s(14)))
        text = (
            "We'll use your webcam for about 12 seconds to estimate how tense your face looks.\n\n"
            "• Sit facing the camera in good light\n"
            "• Keep your face fully visible and look at the screen\n"
            "• Nothing is recorded or saved - video is processed on this computer only"
        )
        self.label(self.container, text, 11, justify="left", wrap=self.s(int(520 * self.fs))).pack(pady=self.s(8))
        if note:
            self.label(self.container, note, 10, bold=True, color="#D03030",
                       wrap=self.s(int(520 * self.fs))).pack(pady=(0, self.s(8)))
        self.button(self.container, "Try again" if note else "Start scan", self._start, pady=self.s(10))

    # ------------------------------------------------------------ scanning
    def _start(self):
        try:
            if self.scanner_factory is not None:
                self._scanner = self.scanner_factory()
            else:
                from stress_scan.live_scan import LiveScanner, PREVIEW_SIZE
                self._preview_size = PREVIEW_SIZE
                self._scanner = LiveScanner()
        except Exception as e:
            self._fail(f"The scan is not available: {type(e).__name__}: {e}")
            return

        self.clear()
        self.label(self.container, self.title, 16, bold=True).pack(pady=(0, self.s(8)))

        pw = int(self._preview_size[0] * self.preview_scale)
        ph = int(self._preview_size[1] * self.preview_scale)
        box = tk.Frame(self.container, width=pw, height=ph, bg=self.colors["bg_secondary"])
        box.pack(pady=self.s(6))
        box.pack_propagate(False)
        self._preview_lbl = tk.Label(box, bg=self.colors["bg_secondary"], text="Starting camera…",
                                     fg=self.colors["text_medium"], font=self.f(11, italic=True))
        self._preview_lbl.pack(expand=True, fill="both")

        self._status_lbl = self.label(self.container, "Preparing the scan…", 12,
                                      wrap=self.s(int(560 * self.fs)))
        self._status_lbl.pack(pady=(self.s(6), self.s(4)))
        if SHOW_MODEL_READOUT:
            self._readout_head = self.label(self.container, "Model: waiting for the first reading...", 12, bold=True)
            self._readout_head.pack(pady=(self.s(2), 0))
            self._readout_detail = self.label(self.container, "", 9, color=self.colors["text_medium"],
                                           wrap=self.s(int(700 * self.fs)))
            self._readout_detail.pack(pady=(0, self.s(2)))
            self._readout_canvas = tk.Canvas(self.container, width=pw, height=self.s(int(READOUT_BAR_H * self.fs)),
                                            bg=self.colors["bg_main"], highlightthickness=0)
            self._readout_canvas.pack(pady=(0, self.s(4)))
            self._last_live_id = None
            self._last_face_state = None
        self._progress = ttk.Progressbar(self.container, mode="determinate",
                                         length=self.s(int(340 * self.fs)), maximum=100)
        self._progress.pack(pady=self.s(8))


        self._last_frame_id = None
        self._scanner.start()
        self._poll_id = self.after(POLL_MS, self._poll)

    def _update_readout(self, snap):
        if not SHOW_MODEL_READOUT or not hasattr(self, "_readout_head"):
            return
        live = snap.get("live")
        face = bool(snap.get("face_found"))
        if id(live) == self._last_live_id and face == self._last_face_state:
            return                                   # nothing new -> no redraw
        self._last_live_id, self._last_face_state = id(live), face
        try:
            self._readout_head.config(text=format_headline(live, face))
            self._readout_detail.config(text=format_detail(live))
            cv = self._readout_canvas
            cv.delete("all")
            rows = bar_rows(live)
            if not rows:
                return
            w = int(cv.cget("width")); h = int(cv.cget("height"))
            label_h = self.s(int(13 * self.fs))
            slot = w / len(rows)
            bar_w = slot * 0.6
            for i, (name, prob, is_top) in enumerate(rows):
                x0 = i * slot + (slot - bar_w) / 2
                top = (h - label_h) * (1.0 - max(0.0, min(1.0, prob)))
                if not face:
                    fill = self.colors["bg_secondary"]
                else:
                    fill = self.colors.get("accent", "#4CAF50") if is_top else self.colors["text_medium"]
                cv.create_rectangle(x0, top, x0 + bar_w, h - label_h, fill=fill, outline="")
                cv.create_text(x0 + bar_w / 2, h - label_h / 2, text=name, fill=self.colors["text_dark"],
                               font=self.f(8))
        except Exception:
            pass                                     # diagnostics must never break the scan

    def _poll(self):
        self._poll_id = None
        if not self.alive() or self._scanner is None:
            return
        snap = self._scanner.snapshot()
        phase = snap["phase"]

        frame = snap.get("frame_rgb")
        if frame is not None and id(frame) != self._last_frame_id:
            self._last_frame_id = id(frame)
            try:
                from PIL import Image, ImageTk
                img = Image.fromarray(frame)
                if self.preview_scale != 1.0:
                    img = img.resize((int(img.width * self.preview_scale), int(img.height * self.preview_scale)))
                self._photo = ImageTk.PhotoImage(img)
                self._preview_lbl.config(image=self._photo, text="")
            except Exception:
                pass

        self._update_readout(snap)
        if phase in ("loading", "scanning"):
            if phase == "scanning":
                total = self._scanner.scan_seconds
                left = snap.get("time_left", total)
                self._progress["value"] = max(0, min(100, (total - left) / total * 100))
                face_txt = "" if snap.get("face_found") else "  (can't see your face - move into view)"
                self._status_lbl.config(text=f"Scanning… {left}s left{face_txt}")
            else:
                self._status_lbl.config(text=snap.get("message", "Preparing the scan…"))
            self._poll_id = self.after(POLL_MS, self._poll)
            return

        result = snap.get("result")
        self._stop_scanner()
        if phase == "done" and result and result.get("status") == "ok":
            self._progress["value"] = 100
            self._status_lbl.config(text="✓ Scan complete")
            score = score_facial_scan(result)
            self.after(SCAN_SUCCESS_PAUSE_MS, lambda: self._finish(score))
            return

        if result and result.get("status") == "unreliable":
            note = f"The scan wasn't reliable ({result.get('reason', 'unknown reason')})."
        elif result and result.get("status") == "error":
            note = result.get("message", "The scan failed.")
        else:
            note = "The scan was interrupted."
        self._fail(note)

    def _fail(self, note):
        self.attempts += 1
        if self.attempts >= self.max_attempts:
            self.clear()
            self.label(self.container, self.title, 16, bold=True).pack(pady=(0, self.s(14)))
            self.label(self.container,
                       f"{note}\n\nThe face scan couldn't be completed, so your check-in will "
                       "continue with the other parts.", 11, wrap=self.s(int(520 * self.fs))).pack(pady=self.s(10))
            self.after(SCAN_GIVE_UP_PAUSE_MS, lambda: self._finish(None))
        else:
            self._show_intro(note=f"{note} Please try again (attempt {self.attempts} of {self.max_attempts}).")

    def _finish(self, score):
        if self._finished or not self.alive():
            return
        self._finished = True
        self.on_done(score)

    def _stop_scanner(self):
        if self._scanner is not None:
            try:
                self._scanner.stop()
            except Exception:
                pass
            self._scanner = None

    def destroy(self):
        self._stop_scanner()
        super().destroy()


# =============================================================================
# Quiz
# =============================================================================
class QuizPanel(_PanelBase):
    def __init__(self, container, colors, s, on_submit, title="Quick Check-in",
                 font_scale=1.0, wrap=None):
        """on_submit(score): score is the DASS-21 stress score 0-42 (sum x 2)."""
        super().__init__(container, colors, s, font_scale)
        self.on_submit = on_submit
        self.wrap = wrap or self.s(int(560 * font_scale))
        self.answers = {}          # question index -> IntVar
        self._radios = {}          # question index -> [(value, Radiobutton)]
        self._canvas = None
        self._build(title)

    def _build(self, title):
        self.label(self.container, title, 16, bold=True).pack(pady=(0, self.s(10)))

        self.submit_btn = self.button(self.container, "Submit", self._submit, side="bottom", pady=self.s(14))
        self.submit_btn.config(state=tk.DISABLED)

        canvas = tk.Canvas(self.container, bg=self.colors["bg_main"], highlightthickness=0)
        self._canvas = canvas
        scrollbar = ttk.Scrollbar(self.container, orient="vertical", command=canvas.yview)
        inner = tk.Frame(canvas, bg=self.colors["bg_main"])
        win_id = canvas.create_window((0, 0), window=inner, anchor="nw")
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(win_id, width=e.width))
        canvas.configure(yscrollcommand=scrollbar.set)

        def _wheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        canvas.bind("<Enter>", lambda e: canvas.bind_all("<MouseWheel>", _wheel))
        canvas.bind("<Leave>", lambda e: canvas.unbind_all("<MouseWheel>"))
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        for i, q_text in enumerate(QUIZ_QUESTIONS):
            q_frame = tk.Frame(inner, bg=self.colors["bg_main"], pady=self.s(10))
            q_frame.pack(fill="x", padx=self.s(10))
            self.label(q_frame, f"{i + 1}. {q_text}", 12, bold=True,       # question: bold
                       wrap=self.wrap, justify="left").pack(anchor="w")
            options = tk.Frame(q_frame, bg=self.colors["bg_main"])
            options.pack(anchor="w", pady=self.s(5))
            var = tk.IntVar(value=-1)
            self.answers[i] = var
            self._radios[i] = []
            for val, label_text in QUIZ_RESPONSE_LABELS:
                rb = tk.Radiobutton(
                    options, text=label_text, variable=var, value=val,
                    bg=self.colors["bg_main"], fg=self.colors["text_dark"],
                    selectcolor=self.colors["bg_main"], font=self.f(11),
                    command=lambda idx=i: self._on_select(idx),
                )
                rb.pack(anchor="w", pady=self.s(2))
                self._radios[i].append((val, rb))

    def _on_select(self, idx):
        chosen = self.answers[idx].get()
        for val, rb in self._radios[idx]:
            rb.config(font=self.f(11, bold=(val == chosen)))       # chosen answer: bold
        if all(v.get() != -1 for v in self.answers.values()):
            self.submit_btn.config(state=tk.NORMAL)

    def _submit(self):
        score = score_quiz([v.get() for v in self.answers.values()])
        self._release_wheel()
        self.on_submit(score)

    def _release_wheel(self):
        if self._canvas is not None:
            try:
                self._canvas.unbind_all("<MouseWheel>")
            except Exception:
                pass

    def destroy(self):
        self._release_wheel()
        super().destroy()



# =============================================================================
# Emotion Scale
# =============================================================================
class EmotionScalePanel(_PanelBase):
    def __init__(self, container, colors, s, current_pet, pet_graphics, on_submit, 
                 title="How are you feeling?", font_scale=1.0, face_px=130):
        """on_submit(score): score is float 0-42."""
        super().__init__(container, colors, s, font_scale)
        self.on_submit = on_submit
        self.current_pet = current_pet
        self.pet_graphics = pet_graphics
        self.title = title
        self.face_px = int(face_px * self.fs)
        self.selected_key = None
        self.cells = []
        self._build()

    def _build(self):
        self.label(self.container, self.title, 16, bold=True).pack(pady=(0, self.s(10)))
        self.label(self.container, "Tap the face that is closest to how you feel right now.", 
                   11, wrap=self.s(int(520 * self.fs))).pack(pady=(0, self.s(14)))

        # Container for the 4 faces (2x2 grid)
        grid_frame = tk.Frame(self.container, bg=self.colors["bg_main"])
        grid_frame.pack(expand=True)
        grid_frame.columnconfigure(0, weight=1)
        grid_frame.columnconfigure(1, weight=1)

        # Dynamic face size calculation
        self.container.update_idletasks()
        avail_w = self.container.winfo_width()
        avail_h = self.container.winfo_height()
        
        if avail_w > 1:
            reserved = self.s(90) + self.s(70) + (2 * self.s(55 * self.fs))
            face_px = min((avail_w // 2) - self.s(40), (avail_h - reserved) // 2)
            face_px = max(int(110 * self.fs), min(face_px, int(300 * self.fs)))
        else:
            face_px = int(self.face_px * 1.6 * self.fs)
        self.face_px = face_px

        for i, (emotion_name, score, en_cap, vi_cap) in enumerate(EMOTION_SCALE):
            r, c = divmod(i, 2)
            cell = tk.Frame(grid_frame, bg=self.colors["bg_main"], 
                            highlightthickness=3, highlightbackground=self.colors["bg_main"],
                            cursor="hand2")
            cell.grid(row=r, column=c, padx=self.s(10), pady=self.s(6), sticky="n")
            
            # Pet image
            pet_type, stage, _ = _pet_fields(self.current_pet)
            # Spec: if stage < 2 use 2
            actual_stage = max(2, stage)
            img = self.pet_graphics.get_pet_image(pet_type, actual_stage, emotion_name, size=(self.face_px, self.face_px))
            
            img_lbl = tk.Label(cell, bg=self.colors["bg_main"])
            if img:
                img_lbl.config(image=img)
                img_lbl.image = img
            else:
                # Fallback emojis
                emojis = {"Happy": "😊", "Worried": "😟", "Sad": "😢", "Angry": "😠"}
                img_lbl.config(text=emojis.get(emotion_name, "❓"), font=self.f(40))
            
            img_lbl.pack(pady=(self.s(5), 0))
            img_lbl.bind("<Button-1>", lambda e, k=emotion_name: self._select(k))

            # Captions
            en_lbl = self.label(cell, en_cap, 10, justify="center")
            en_lbl.pack()
            vi_lbl = self.label(cell, vi_cap, 8, italic=True, justify="center")
            vi_lbl.pack()
            vi_lbl.bind("<Button-1>", lambda e, k=emotion_name: self._select(k))
            en_lbl.bind("<Button-1>", lambda e, k=emotion_name: self._select(k))
            
            # Bind the cell frame itself
            cell.bind("<Button-1>", lambda e, k=emotion_name: self._select(k))
            
            self.cells.append({"key": emotion_name, "frame": cell, "en": en_lbl, "vi": vi_lbl})

        self.submit_btn = self.button(self.container, "Submit", self._submit, side="bottom", pady=self.s(14))
        self.submit_btn.config(state=tk.DISABLED)

    def _select(self, key):
        self.selected_key = key
        accent = self.colors.get("accent", "#4CAF50")
        bg_main = self.colors["bg_main"]

        for cell_data in self.cells:
            is_sel = (cell_data["key"] == key)
            cell_data["frame"].config(
                highlightbackground=accent if is_sel else bg_main
            )
            cell_data["en"].config(font=self.f(10, bold=is_sel))
            cell_data["vi"].config(font=self.f(8, italic=True, bold=is_sel))

        self.submit_btn.config(state=tk.NORMAL)

    def _submit(self):
        score = score_emotion(self.selected_key)
        self.on_submit(score)

    def destroy(self):
        super().destroy()

# =============================================================================
# Mailbox letter
# =============================================================================
def _pet_fields(pet):
    pet_type = pet.pet_type.value if hasattr(pet.pet_type, "value") else str(pet.pet_type)
    stage = pet.stage.value if hasattr(pet.stage, "value") else int(pet.stage)
    emotion = pet.emotion.name.lower() if hasattr(pet.emotion, "name") else str(pet.emotion).lower()
    return pet_type, stage, emotion


import os
from PIL import Image, ImageTk

ENVELOPE_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "assets", "img", "envelope.png")
ENVELOPE_CACHE = {}
 
def _load_envelope(width_px):
    """Return an ImageTk.PhotoImage of the envelope cropped to its drawn area, or None if the file is missing."""
    if width_px in ENVELOPE_CACHE: return ENVELOPE_CACHE[width_px]
    try:
        with Image.open(ENVELOPE_PATH) as im:
            im = im.convert("RGBA")
            bbox = im.getchannel("A").getbbox()
            if bbox:
                im = im.crop(bbox)
            aspect = im.height / im.width
            h = int(width_px * aspect)
            im = im.resize((width_px, h), Image.LANCZOS)
            photo = ImageTk.PhotoImage(im)
            ENVELOPE_CACHE[width_px] = photo
            return photo
    except Exception:
        return None

class LetterPanel(_PanelBase):
    def __init__(self, container, colors, s, current_pet, pet_graphics, on_done,
                 font_scale=1.0, pet_px=PET_BASE_PX_WINDOW):
        """
        Write -> Send -> envelope flies to the pet -> pet 'eats' it -> pet moves to the
        centre with 'Thinking it over...' -> on_done(letter_text).
        After on_done the centred pet and the status label are still on screen:
        call remove_status() before drawing a result underneath (window mode).
        """
        super().__init__(container, colors, s, font_scale)
        self.pet = current_pet
        self.pet_graphics = pet_graphics
        self.on_done = on_done
        self.pet_px = int(pet_px * font_scale)
        self.status_lbl = None
        self.centered_pet_lbl = None
        self.letter_text = ""
        self._setup_writing_stage()

    def _pet_image(self, px, open_mouth=False):
        pet_type, stage, emotion = _pet_fields(self.pet)
        if open_mouth:
            return self.pet_graphics.get_pet_image_with_fallback(
                pet_type, stage, "Mouth_Open", emotion, (px, px))
        return self.pet_graphics.get_pet_image(pet_type, stage, emotion, size=(px, px))

    def _setup_writing_stage(self):
        self.writing_frame = tk.Frame(self.container, bg=self.colors["bg_main"])
        self.writing_frame.pack(fill="both", expand=True)

        self.left_frame = tk.Frame(self.writing_frame, bg=self.colors["bg_main"])
        self.left_frame.place(relx=0, rely=0, relwidth=TEXT_WIDTH_FRACTION, relheight=1.0)

        self.text_box = tk.Text(
            self.left_frame, wrap="word", font=self.f(12),
            bg=self.colors["bg_secondary"], fg=self.colors["text_dark"],
            padx=self.s(10), pady=self.s(10), relief="flat", bd=0,
        )
        self.send_btn = tk.Button(
            self.left_frame, text="Send", command=self.handle_send,
            bg=self.colors.get("accent", "#4CAF50"), fg="white",
            font=self.f(10, bold=True), relief="flat",
            padx=self.s(20), pady=self.s(8), cursor="hand2",
        )
        self.send_btn.pack(side="bottom", anchor="center")
        self.text_box.pack(fill="both", expand=True, pady=(0, self.s(15)))

        self.placeholder_text = "Write whatever's on your mind…"
        self.text_box.insert("1.0", self.placeholder_text)
        self.text_box.config(foreground="gray")

        def on_focus_in(event):
            if self.text_box.get("1.0", tk.END).strip() == self.placeholder_text:
                self.text_box.delete("1.0", tk.END)
                self.text_box.config(foreground=self.colors["text_dark"])

        def on_focus_out(event):
            if not self.text_box.get("1.0", tk.END).strip():
                self.text_box.insert("1.0", self.placeholder_text)
                self.text_box.config(foreground="gray")

        self.text_box.bind("<FocusIn>", on_focus_in)
        self.text_box.bind("<FocusOut>", on_focus_out)
        self.send_btn.config(state=tk.DISABLED)
        self.text_box.bind("<KeyRelease>", self._validate_send)

        self.right_frame = tk.Frame(self.writing_frame, bg=self.colors["bg_main"])
        self.right_frame.place(relx=TEXT_WIDTH_FRACTION, rely=0, relwidth=1.0 - TEXT_WIDTH_FRACTION, relheight=1.0)
        self.pet_image_lbl = tk.Label(self.right_frame, bg=self.colors["bg_main"])
        self.pet_image_lbl.pack(expand=True)
        self.container.update_idletasks()
        rw = self.right_frame.winfo_width()
        ch = self.container.winfo_height()
        if rw > 1 and ch > 1:
            limit = int(min(rw * PET_SIZE_FACTOR, ch * PET_HEIGHT_FACTOR) / CHOMP_SCALE)
            self.pet_px = max(160, min(self.pet_px, limit))
        self._set_pet_image(self.pet_image_lbl, self.pet_px, open_mouth=True)

    def _set_pet_image(self, lbl, px, open_mouth=False):
        img = self._pet_image(px, open_mouth=open_mouth)
        lbl.config(image=img)
        lbl.image = img

    def _validate_send(self, event=None):
        content = self.text_box.get("1.0", tk.END).strip()
        ok = bool(content) and content != self.placeholder_text
        self.send_btn.config(state=tk.NORMAL if ok else tk.DISABLED)

    def handle_send(self):
        self.letter_text = self.text_box.get("1.0", tk.END).strip()
        self.text_box.config(state=tk.DISABLED)
        self.send_btn.config(state=tk.DISABLED)
        self._animate_consume()

    def _animate_consume(self):
        """Envelope glides from the text box to the pet (slow start, slow landing)."""
        cont = self.container
        cont.update_idletasks()
        
        def centre_of(widget):
            return (widget.winfo_rootx() - cont.winfo_rootx() + widget.winfo_width() // 2,
                    widget.winfo_rooty() - cont.winfo_rooty() + widget.winfo_height() // 2)
        
        sx, sy = centre_of(self.text_box)
        
        pet_type, stage, _ = _pet_fields(self.pet)
        fx, fy = MOUTH_TARGET.get((str(pet_type).lower(), int(stage)), (0.5, 0.5))
        lbl = self.pet_image_lbl
        img = lbl.image
        iw, ih = (img.width(), img.height()) if img else (lbl.winfo_width(), lbl.winfo_height())
        left = lbl.winfo_rootx() - cont.winfo_rootx() + (lbl.winfo_width() - iw) // 2
        top  = lbl.winfo_rooty() - cont.winfo_rooty() + (lbl.winfo_height() - ih) // 2
        ex, ey = left + int(iw * fx), top + int(ih * fy)
        
        self.text_box.pack_forget()
        self.send_btn.pack_forget()
        
        env_w = max(self.s(110), int(cont.winfo_width() * 0.16))
        img = _load_envelope(env_w)
        if img is not None:
            letter = tk.Label(cont, image=img, bg=self.colors["bg_main"], bd=0, highlightthickness=0)
            letter.image = img
        else:
            letter = tk.Frame(cont, bg=LETTER_BG, highlightbackground=LETTER_BORDER, highlightcolor=LETTER_BORDER, highlightthickness=LETTER_BORDER_PX)
            tk.Label(letter, text="✉️", font=self.f(LETTER_ICON_SIZE), bg=LETTER_BG, padx=self.s(LETTER_PAD_X), pady=self.s(LETTER_PAD_Y)).pack()
        
        letter.place(x=sx, y=sy, anchor="center")
        letter.lift()
        steps = FEED_STEPS

        def move_step(step):
            if not self.alive(): return
            if step <= steps:
                t = step / steps
                t = t * t * (3 - 2 * t)
                letter.place(x=sx + (ex - sx) * t, y=sy + (ey - sy) * t, anchor="center")
                self.after(FEED_FRAME_MS, lambda: move_step(step + 1))
            else:
                letter.destroy()
                self._pet_bounce()

        move_step(0)
    def _pet_bounce(self):
        self._set_pet_image(self.pet_image_lbl, int(self.pet_px * 1.1), open_mouth=True)
        self.after(FEED_CHOMP_MS, self._return_pet_size)

    def _return_pet_size(self):
        self._set_pet_image(self.pet_image_lbl, self.pet_px, open_mouth=True)
        self._pet_to_centre()

    def _pet_to_centre(self):
        self.writing_frame.pack_forget()
        self.container.update_idletasks()
        centre_px = min(self.pet_px, int(self.container.winfo_height() * 0.42))
        self.centered_pet_lbl = tk.Label(self.container, bg=self.colors["bg_main"])
        self.centered_pet_lbl.place(relx=0.5, rely=0.36, anchor="center")
        self._set_pet_image(self.centered_pet_lbl, centre_px)
        self.status_lbl = tk.Label(
            self.container, text="Thinking it over...", font=self.f(12, italic=True),
            bg=self.colors["bg_main"], fg=self.colors["text_medium"],
        )
        self.status_lbl.place(relx=0.5, rely=0.36 + (centre_px / 2) / self.container.winfo_height() + 0.07, anchor="center")
        self.after(THINK_MS, self._finish)

    def _finish(self):
        if self.alive():
            self.on_done(self.letter_text)

    def remove_status(self):
        if self.status_lbl is not None:
            try:
                self.status_lbl.destroy()
            except Exception:
                pass
            self.status_lbl = None
