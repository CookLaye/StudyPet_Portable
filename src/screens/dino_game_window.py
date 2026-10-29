"""
Pet Runner - a tiny dinosaur-style minigame in its own small window.

The player's own pet (same type / stage as in the main screen) is the "dinosaur":
SPACE / UP arrow / mouse click = jump over the obstacles.

Every DAY_NIGHT_EVERY points (utils/dino_logic.py) the scenery fades between day and night.
When a run ends, two buttons appear: [Continue] (new run) and [End game] (close the window).
Choose with the mouse (hover + click) or LEFT / RIGHT arrows, confirm with Enter / Space / click.
Esc closes the window at any time.

    DinoGameWindow(parent, colors, s, current_pet, pet_graphics, on_finish=callback, rewarded_fn=callable)

on_finish(score) is called ONCE PER RUN when it ends (crash, or closing the window mid-run).
rewarded_fn() is called at the start of every run and returns True if that run can pay affection;
it only changes the on-screen text - the caller does the actual paying in on_finish.

The window opens in the CENTRE OF THE SCREEN, fixed size, a wide short rectangle. All text sizes are in
PIXELS (negative Tk font size) so the window's own scale factor is the only scaling that applies.
"""

import time
import tkinter as tk

from utils import dino_logic as L

FRAME_MS = 16                 # ~60 fps
INPUT_LOCK_AFTER_OVER = 0.6   # seconds: ignore "confirm" right after a crash so key-mashing cannot skip the result
READY_LOCK = 0.25             # seconds after Continue before SPACE can start the next run (key-repeat safety)
MAX_WIDTH_FRACTION = 0.40     # window is never wider than this fraction of the screen
MAX_HEIGHT_FRACTION = 0.35

PET_DRAW_DY = 4               # logical units: draw the picture slightly lower so the feet touch the ground line

# day palette comes from the app theme; night palette is fixed
NIGHT_BG = "#1c1b2e"
NIGHT_INK = "#f1eef8"
NIGHT_SOFT = "#9893b8"
MOON_COLOR = "#f4efd0"
STAR_COLOR = "#ffffff"
FADE_SECONDS = 0.9
STARS = [(55, 30), (140, 64), (235, 24), (345, 20), (440, 28), (560, 92), (610, 34), (100, 96)]   # kept clear of the centre text
MOON = (575, 50, 12)          # x, y, radius

BTN_W, BTN_H, BTN_GAP, BTN_Y = 118, 30, 22, 128   # logical units


def _pet_fields(pet):
    pet_type = pet.pet_type.value if hasattr(pet.pet_type, "value") else str(pet.pet_type)
    stage = pet.stage.value if hasattr(pet.stage, "value") else int(pet.stage)
    return str(pet_type).lower(), int(stage)


def _blend(c1, c2, t):
    t = max(0.0, min(1.0, t))
    return "#%02x%02x%02x" % tuple(int(round(a + (b - a) * t)) for a, b in zip(c1, c2))


class DinoGameWindow:
    def __init__(self, parent, colors, s, current_pet, pet_graphics, on_finish=None, rng=None, rewarded_fn=None):
        self.parent = parent
        self.colors = colors
        self.s = s
        self.pet_graphics = pet_graphics
        self.on_finish = on_finish
        self.rewarded_fn = rewarded_fn
        self.game = L.DinoGame(rng)
        self.rewarded = self._query_rewarded()
        self._finished = False
        self._after_id = None
        self._last_t = None
        self._over_at = None
        self._ready_at = time.perf_counter()
        self._images = {}            # emotion -> PhotoImage (keeps references alive)
        self._cur_emotion = None
        self._ob_items = {}          # Obstacle -> canvas item id
        self._btns = {}              # key -> {"rect","text","box"}
        self._hint_item = None
        self._sel = "continue"
        self._closed = False
        self._night_t = 0.0          # 0 = full day, 1 = full night

        try:
            self.pet_type, self.stage = _pet_fields(current_pet)
        except Exception:
            self.pet_type, self.stage = "cat", 2

        # ---- window: fixed small rectangle, centred on the SCREEN ----
        self.window = tk.Toplevel(parent)
        self.window.title("🦖 Pet Runner")
        self.window.resizable(False, False)
        screen_w = parent.winfo_screenwidth()
        screen_h = parent.winfo_screenheight()
        k = max(0.8, self.s(100) / 100.0)
        k = min(k, (screen_w * MAX_WIDTH_FRACTION) / L.WORLD_W, (screen_h * MAX_HEIGHT_FRACTION) / L.WORLD_H)
        self.k = k
        self.win_w = int(L.WORLD_W * k)
        self.win_h = int(L.WORLD_H * k)
        x = (screen_w - self.win_w) // 2
        y = (screen_h - self.win_h) // 2
        self.window.geometry(f"{self.win_w}x{self.win_h}+{x}+{y}")
        try:
            self.window.transient(parent)
        except Exception:
            pass
        self.window.protocol("WM_DELETE_WINDOW", self.close)

        self._day = (self._rgb(colors["bg_main"]), self._rgb(colors.get("text_dark", "#000000")),
                     self._rgb(colors.get("text_medium", "#666666")))
        self._night = (self._rgb(NIGHT_BG), self._rgb(NIGHT_INK), self._rgb(NIGHT_SOFT))
        bg, ink, soft = (_blend(c, c, 0) for c in self._day)

        self.canvas = tk.Canvas(self.window, width=self.win_w, height=self.win_h, bg=bg, highlightthickness=0, bd=0)
        self.canvas.pack(fill="both", expand=True)
        try:
            self.window.config(bg=bg)
        except Exception:
            pass

        # sky (behind everything else): stars + moon (invisible by day: same colour as the background)
        self._stars = []
        for sx, sy in STARS:
            r = max(1, int(1.6 * k))
            self._stars.append(self.canvas.create_oval(sx * k - r, sy * k - r, sx * k + r, sy * k + r, fill=bg, outline=""))
        mx, my, mr = MOON
        self._moon = self.canvas.create_oval((mx - mr) * k, (my - mr) * k, (mx + mr) * k, (my + mr) * k, fill=bg, outline="")
        self._moon_mask = self.canvas.create_oval((mx - mr + 7) * k, (my - mr - 4) * k, (mx + mr + 7) * k, (my + mr - 4) * k,
                                                  fill=bg, outline="")

        gy = L.GROUND_Y * k
        self._ground = self.canvas.create_line(0, gy, self.win_w, gy, fill=ink, width=max(2, int(2 * k)))
        self._specks = []
        for i in range(0, L.WORLD_W, 90):                       # little ground specks
            self._specks.append(self.canvas.create_line(i * k + 20 * k, gy + 10 * k, i * k + 34 * k, gy + 10 * k, fill=soft))

        size = int(L.PET_SIZE * k)
        self._pet_item = None
        img = self._image_for("Happy")
        if img is not None:
            self._pet_item = self.canvas.create_image(L.PET_X * k, (self.game.pet_y + PET_DRAW_DY) * k, image=img, anchor="nw")
        else:                                                   # no picture found: a plain box so the game still works
            self._pet_item = self.canvas.create_rectangle(L.PET_X * k, self.game.pet_y * k,
                                                          L.PET_X * k + size, self.game.pet_y * k + size,
                                                          fill=soft, outline=ink)

        self._score_item = self.canvas.create_text(self.win_w - 14 * k, 10 * k, anchor="ne", fill=ink,
                                                   font=("Arial", -max(11, int(13 * k)), "bold"), text="Score: 0")
        self._msg_item = self.canvas.create_text(self.win_w / 2, 68 * k, anchor="center", fill=ink, justify="center",
                                                 font=("Arial", -max(11, int(14 * k)), "bold"), text=self._ready_text())

        # ---- input ----
        for seq in ("<space>", "<Up>", "<Return>"):
            self.window.bind(seq, self._on_input)
        self.window.bind("<Left>", lambda e: self._select("continue"))
        self.window.bind("<Right>", lambda e: self._select("end"))
        self.canvas.bind("<Button-1>", self._on_click)
        self.canvas.bind("<Motion>", self._on_motion)
        self.window.bind("<Escape>", lambda e: self.close())

        try:
            self.window.grab_set()
        except Exception:
            pass
        try:
            self.window.focus_force()
        except Exception:
            pass

        self._apply_theme()
        self._after_id = self.window.after(FRAME_MS, self._tick)

    # ------------------------------------------------------------------ helpers
    def _rgb(self, color):
        c = str(color)
        if c.startswith("#"):
            h = c[1:]
            if len(h) == 3:
                h = "".join(ch * 2 for ch in h)
            if len(h) == 6:
                try:
                    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
                except ValueError:
                    pass
        try:
            r, g, b = self.parent.winfo_rgb(c)
            return (r // 257, g // 257, b // 257)
        except Exception:
            return (255, 255, 255)

    def _query_rewarded(self):
        if self.rewarded_fn is None:
            return True
        try:
            return bool(self.rewarded_fn())
        except Exception:
            return False

    def _ready_text(self):
        text = "Press SPACE, ↑ or click to start\nJump over the obstacles!"
        if not self.rewarded:
            text += "\n(practice run - no affection today)"
        return text

    # ------------------------------------------------------------------ day / night
    def _palette(self):
        t = self._night_t
        return tuple(_blend(d, n, t) for d, n in zip(self._day, self._night))

    def _apply_theme(self):
        bg, ink, soft = self._palette()
        c, t = self.canvas, self._night_t
        c.config(bg=bg)
        try:
            self.window.config(bg=bg)
        except Exception:
            pass
        c.itemconfig(self._ground, fill=ink)
        for sp in self._specks:
            c.itemconfig(sp, fill=soft)
        c.itemconfig(self._score_item, fill=ink)
        c.itemconfig(self._msg_item, fill=ink)
        star = _blend(self._rgb(bg), self._rgb(STAR_COLOR), t)
        for st in self._stars:
            c.itemconfig(st, fill=star)
        c.itemconfig(self._moon, fill=_blend(self._rgb(bg), self._rgb(MOON_COLOR), t))
        c.itemconfig(self._moon_mask, fill=bg)
        for ob_item in self._ob_items.values():
            c.itemconfig(ob_item, fill=ink, outline=ink)
        if self._pet_item is not None and not self._is_image_item():
            c.itemconfig(self._pet_item, fill=soft, outline=ink)
        self._style_buttons()

    def _update_day_night(self, dt):
        target = 1.0 if L.phase_for_score(self.game.score) == "night" else 0.0
        if self._night_t == target:
            return
        step = dt / FADE_SECONDS
        if self._night_t < target:
            self._night_t = min(target, self._night_t + step)
        else:
            self._night_t = max(target, self._night_t - step)
        self._apply_theme()

    # ------------------------------------------------------------------ images
    def _image_for(self, emotion):
        if emotion in self._images:
            return self._images[emotion]
        img = None
        size = int(L.PET_SIZE * self.k)
        try:
            if hasattr(self.pet_graphics, "get_pet_image_with_fallback"):
                img = self.pet_graphics.get_pet_image_with_fallback(
                    self.pet_type, self.stage, emotion, "Happy", (size, size))
            else:
                img = self.pet_graphics.get_pet_image(self.pet_type, self.stage, emotion, (size, size))
        except Exception:
            img = None
        self._images[emotion] = img
        return img

    def _set_emotion(self, emotion):
        if emotion == self._cur_emotion:
            return
        self._cur_emotion = emotion
        img = self._image_for(emotion)
        if img is not None and self._pet_item is not None:
            try:
                self.canvas.itemconfig(self._pet_item, image=img)
            except Exception:
                pass

    # ------------------------------------------------------------------ input
    def _on_input(self, event=None):
        """SPACE / UP / ENTER: jump (or confirm the selected button after a crash)."""
        g = self.game
        if g.over:
            self._confirm()
            return
        if g.state == L.DinoGame.READY:
            if time.perf_counter() - self._ready_at < READY_LOCK:
                return
            self.canvas.itemconfig(self._msg_item, text="")
        g.jump()

    def _on_click(self, event):
        if self.game.over:
            key = self._button_at(event.x, event.y)
            if key:
                self._sel = key
                self._style_buttons()
                self._confirm()
            return
        self._on_input()

    def _on_motion(self, event):
        if self.game.over:
            key = self._button_at(event.x, event.y)
            if key and key != self._sel:
                self._select(key)

    def _select(self, key):
        if self.game.over and key in self._btns and key != self._sel:
            self._sel = key
            self._style_buttons()

    def _button_at(self, x, y):
        for key, b in self._btns.items():
            x1, y1, x2, y2 = b["box"]
            if x1 <= x <= x2 and y1 <= y <= y2:
                return key
        return None

    def _confirm(self):
        if self._over_at is None or time.perf_counter() - self._over_at < INPUT_LOCK_AFTER_OVER:
            return
        if self._sel == "end":
            self.close()
        else:
            self._new_run()

    # ------------------------------------------------------------------ runs
    def _new_run(self):
        for item in self._ob_items.values():
            self.canvas.delete(item)
        self._ob_items.clear()
        self._delete_buttons()
        self.game.reset()
        self._finished = False
        self._over_at = None
        self._last_t = None
        self._ready_at = time.perf_counter()
        self.rewarded = self._query_rewarded()
        self._set_emotion("Happy")
        self.canvas.itemconfig(self._msg_item, text=self._ready_text())
        self.canvas.itemconfig(self._score_item, text="Score: 0")

    def _tick(self):
        self._after_id = None
        if self._closed:
            return
        now = time.perf_counter()
        dt = 0.0 if self._last_t is None else min(now - self._last_t, 0.05)
        self._last_t = now

        g = self.game
        g.step(dt)
        self._draw()
        self._update_day_night(dt)

        if g.over and self._over_at is None:
            self._over_at = now
            self._show_game_over()
            self._finish()           # reward is handled immediately; choosing Continue/End later changes nothing
        try:
            self._after_id = self.window.after(FRAME_MS, self._tick)
        except Exception:
            self._after_id = None

    def _draw(self):
        g, k, c = self.game, self.k, self.canvas
        if self._is_image_item():
            c.coords(self._pet_item, L.PET_X * k, (g.pet_y + PET_DRAW_DY) * k)
        else:
            c.coords(self._pet_item, L.PET_X * k, g.pet_y * k, L.PET_X * k + L.PET_SIZE * k, g.pet_y * k + L.PET_SIZE * k)
        if g.over:
            self._set_emotion("Sad")
        elif not g.on_ground:
            self._set_emotion("Mouth_Open")
        else:
            self._set_emotion("Happy")

        ink = self._palette()[1]
        alive = set()
        for ob in g.obstacles:
            if g.over and ob.x > L.PET_X + L.PET_SIZE + 30:
                continue                     # after a crash only the cactus that was hit stays; the rest would sit behind the buttons
            alive.add(ob)
            l, t, r, b = ob.rect
            coords = (l * k, t * k, r * k, b * k)
            item = self._ob_items.get(ob)
            if item is None:
                if r * k < 0 or l * k > self.win_w + 5:
                    continue
                self._ob_items[ob] = c.create_rectangle(*coords, fill=ink, outline=ink)
            else:
                c.coords(item, *coords)
        for ob in [x for x in self._ob_items if x not in alive]:
            c.delete(self._ob_items.pop(ob))

        c.itemconfig(self._score_item, text=f"Score: {g.score}")

    def _is_image_item(self):
        try:
            return self.canvas.type(self._pet_item) == "image"
        except Exception:
            return True

    # ------------------------------------------------------------------ game over: result + buttons
    def _show_game_over(self):
        reward = L.reward_for_score(self.game.score) if self.rewarded else 0
        text = f"Game over!  Score: {self.game.score}"
        if not self.rewarded:
            text += "\nPractice run - today's affection limit is used up"
        else:
            text += f"\n+{reward} affection" if reward else "\nNo reward this time - try again!"
        self.canvas.itemconfig(self._msg_item, text=text)
        self._make_buttons()

    def _make_buttons(self):
        self._delete_buttons()
        k, c = self.k, self.canvas
        x0 = (L.WORLD_W - (2 * BTN_W + BTN_GAP)) / 2
        font = ("Arial", -max(11, int(13 * k)), "bold")
        for i, (key, label) in enumerate((("continue", "Continue"), ("end", "End game"))):
            x1 = (x0 + i * (BTN_W + BTN_GAP)) * k
            y1 = (BTN_Y - BTN_H / 2) * k
            x2, y2 = x1 + BTN_W * k, y1 + BTN_H * k
            rect = c.create_rectangle(x1, y1, x2, y2, width=max(2, int(2 * k)))
            text = c.create_text((x1 + x2) / 2, (y1 + y2) / 2, text=label, font=font)
            self._btns[key] = {"rect": rect, "text": text, "box": (x1, y1, x2, y2)}
        self._hint_item = c.create_text(self.win_w / 2, (BTN_Y + BTN_H / 2 + 16) * k, text="←  →  choose      Enter / click  confirm",
                                        font=("Arial", -max(10, int(11 * k))))
        self._sel = "continue"
        self._style_buttons()

    def _delete_buttons(self):
        for b in self._btns.values():
            self.canvas.delete(b["rect"])
            self.canvas.delete(b["text"])
        self._btns = {}
        if self._hint_item is not None:
            self.canvas.delete(self._hint_item)
            self._hint_item = None

    def _style_buttons(self):
        if not self._btns:
            return
        bg, ink, soft = self._palette()
        for key, b in self._btns.items():
            if key == self._sel:
                self.canvas.itemconfig(b["rect"], fill=ink, outline=ink)
                self.canvas.itemconfig(b["text"], fill=bg)
            else:
                self.canvas.itemconfig(b["rect"], fill=bg, outline=ink)
                self.canvas.itemconfig(b["text"], fill=ink)
        if self._hint_item is not None:
            self.canvas.itemconfig(self._hint_item, fill=soft)

    # ------------------------------------------------------------------ finish / close
    def _finish(self):
        """Call on_finish(score) exactly once per run."""
        if self._finished:
            return
        self._finished = True
        if self.on_finish:
            try:
                self.on_finish(self.game.score)
            except Exception as e:
                print(f"[PetRunner] on_finish failed: {type(e).__name__}: {e}")

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
        if self.game.running:                # closing mid-run = game over with the current score
            self._finish()
        try:
            self.window.grab_release()
        except Exception:
            pass
        try:
            self.window.destroy()
        except Exception:
            pass
