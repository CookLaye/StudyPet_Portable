"""
Pure logic for the "Encouragement Burst" minigame (click -> hearts/stars fly out + a message floats up).

No Tkinter, no images, no file access in here, so it can be unit-tested on any machine.
The window (screens/burst_window.py) only draws what BurstWorld says and forwards left-clicks to click().

COORDINATES: canvas pixels, x to the right, y DOWNWARD (like the Tk canvas). BurstWorld(scale=k) multiplies
speeds / sizes by one scale factor. There is NO score and NO fail state: every click is a success.

TUNING: every number is a constant below - change a number, nothing else.
"""

import math
import random

# ------------------------------ particles ----------------------------------
PARTICLES_MIN = 14             # particles per click: random between MIN and MAX
PARTICLES_MAX = 22
SPEED_MIN = 170.0              # launch speed, units / s
SPEED_MAX = 430.0
DRAG = 3.0                     # velocity damping: v *= exp(-DRAG * dt)  (bigger = stops sooner)
GRAVITY = 90.0                 # tiny downward pull, units / s^2 (0 = pure outward burst)
LIFE_MIN = 0.9                 # seconds a particle lives
LIFE_MAX = 1.5
SIZE_MIN = 9.0                 # particle radius in units
SIZE_MAX = 17.0
SHAPES = ("heart", "heart", "star")        # weighted pick: hearts twice as likely as stars
DEFAULT_PALETTE = ("#ff6b9d", "#ff8fb1", "#ffb347", "#ffd166", "#c77dff", "#7bdff2", "#95e06c")

def theme_palette(colors):
    """Build palette from theme colours, falling back to default if too few valid hex colours found."""
    res = []
    for key in ("accent", "bg_primary_hover", "bg_primary_active"):
        val = colors.get(key)
        if val and val.startswith("#") and len(val) == 7 and all(c in "0123456789abcdefABCDEF" for c in val[1:]):
            res.append(val)
    res.extend(("#ffffff", "#ffd166"))
    return tuple(res) if len(res) >= 3 else DEFAULT_PALETTE
MAX_PARTICLES = 260            # hard cap so spam-clicking can never slow the app down
FADE_START = 0.55              # fraction of life after which colour fades into the background
SHRINK_END = 0.35              # at the end of life a particle is this fraction of its size (0.35 = 35%)

# ------------------------------ message ------------------------------------
MESSAGES = [
    "You're doing great!",
    "Proud of you!",
    "One step at a time.",
    "You've got this!",
    "Take a breath - you're fine.",
    "Small steps still count!",
    "Look at you go!",
    "Be kind to yourself today.",
    "Nice work, keep it up!",
    "You deserve a break!",
]
MESSAGE_POP_TIME = 0.18        # seconds for the "pop": text grows from MESSAGE_POP_FROM to full size
MESSAGE_POP_FROM = 0.55        # starting size as a fraction of full size
MESSAGE_EDGE_X = 210.0         # keep the message this far from the left/right edge (units, times scale) so it is never cut off
MESSAGE_EDGE_Y = 50.0          # ... and this far from the top/bottom edge
MESSAGE_LIFE = 2.0             # seconds the message is visible
MESSAGE_RISE_SPEED = 38.0      # units / s the message floats upward
MESSAGE_FADE_IN = 0.15         # seconds to fade in
MESSAGE_FADE_OUT_FROM = 0.55   # fraction of life after which it fades out
MESSAGE_COOLDOWN = 0.7         # a new message only appears if the newest one is at least this old (seconds)
MESSAGE_MAX = 3                # at most this many messages on screen at once

# ------------------------------ helpers ------------------------------------

def heart_points(n=24):
    """Unit heart outline: n (x, y) pairs, roughly within -1..1 (y grows downward, tip points down)."""
    pts = []
    for i in range(n):
        t = 2 * math.pi * i / n
        x = 16 * math.sin(t) ** 3
        y = -(13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t))
        pts.append((x / 17.0, y / 17.0))
    return pts


def star_points(spikes=5, inner=0.45):
    """Unit star outline: 2*spikes (x, y) pairs, one spike pointing up."""
    pts = []
    for i in range(spikes * 2):
        r = 1.0 if i % 2 == 0 else inner
        a = -math.pi / 2 + math.pi * i / spikes
        pts.append((r * math.cos(a), r * math.sin(a)))
    return pts


def blend(c1, c2, t):
    """Mix two '#rrggbb' colours. t=0 -> c1, t=1 -> c2."""
    t = max(0.0, min(1.0, t))
    a = [int(c1[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(c2[i:i + 2], 16) for i in (1, 3, 5)]
    return "#%02x%02x%02x" % tuple(int(round(x + (y - x) * t)) for x, y in zip(a, b))


class Particle:
    __slots__ = ("x", "y", "vx", "vy", "age", "life", "size", "shape", "color")

    def __init__(self, x, y, vx, vy, life, size, shape, color):
        self.x, self.y, self.vx, self.vy = x, y, vx, vy
        self.age, self.life, self.size, self.shape, self.color = 0.0, life, size, shape, color

    @property
    def progress(self):
        return min(1.0, self.age / self.life)

    @property
    def scale(self):
        """Current size in units: shrinks from size to size*SHRINK_END over the life."""
        p = self.progress
        return self.size * (1.0 - (1.0 - SHRINK_END) * p)

    @property
    def fade(self):
        """0 = full colour, 1 = fully faded into the background."""
        p = self.progress
        return 0.0 if p <= FADE_START else (p - FADE_START) / (1.0 - FADE_START)


class FloatingMessage:
    __slots__ = ("text", "x", "y", "age")

    def __init__(self, text, x, y):
        self.text, self.x, self.y, self.age = text, x, y, 0.0

    @property
    def progress(self):
        return min(1.0, self.age / MESSAGE_LIFE)

    @property
    def pop(self):
        """Size factor MESSAGE_POP_FROM..1: the text pops out (ease-out) in the first MESSAGE_POP_TIME seconds."""
        if MESSAGE_POP_TIME <= 0 or self.age >= MESSAGE_POP_TIME:
            return 1.0
        q = 1.0 - self.age / MESSAGE_POP_TIME
        return MESSAGE_POP_FROM + (1.0 - MESSAGE_POP_FROM) * (1.0 - q * q)

    @property
    def opacity(self):
        """0..1: quick fade-in, steady, then fade-out."""
        fade_in = min(1.0, self.age / MESSAGE_FADE_IN) if MESSAGE_FADE_IN > 0 else 1.0
        p = self.progress
        fade_out = 1.0 if p <= MESSAGE_FADE_OUT_FROM else max(0.0, 1.0 - (p - MESSAGE_FADE_OUT_FROM) / (1.0 - MESSAGE_FADE_OUT_FROM))
        return max(0.0, min(fade_in, fade_out))


class BurstWorld:
    def __init__(self, width=640, height=400, rng=None, scale=1.0):
        """width/height/positions are in CANVAS PIXELS. scale multiplies speeds, sizes, gravity and the
        message rise speed (the window passes its DPI/screen scale factor so it looks the same everywhere)."""
        self.width, self.height = float(width), float(height)
        self.scale = float(scale)
        self.rng = rng or random.Random()
        self.particles = []
        self.messages = []
        self.clicks = 0                       # just a counter for tests / the window's first-click hint
        self._last_message = None

    # ---- input ----
    def resize(self, width, height):
        self.width, self.height = float(width), float(height)

    def click(self, x, y, palette=DEFAULT_PALETTE):
        """Left click at (x, y): spawn a burst and (if not on cooldown) a message. Always succeeds."""
        self.clicks += 1
        self.spawn_burst(x, y, palette=palette)
        return self.spawn_message(x, y)

    def spawn_burst(self, x, y, palette=DEFAULT_PALETTE):
        n = self.rng.randint(PARTICLES_MIN, PARTICLES_MAX)
        for _ in range(n):
            if len(self.particles) >= MAX_PARTICLES:
                break
            ang = self.rng.uniform(0.0, 2 * math.pi)
            spd = self.rng.uniform(SPEED_MIN, SPEED_MAX) * self.scale
            self.particles.append(Particle(
                x, y, math.cos(ang) * spd, math.sin(ang) * spd,
                self.rng.uniform(LIFE_MIN, LIFE_MAX), self.rng.uniform(SIZE_MIN, SIZE_MAX) * self.scale,
                self.rng.choice(SHAPES), self.rng.choice(palette)))

    def pick_message(self):
        """Random message, never the same one twice in a row."""
        choices = [m for m in MESSAGES if m != self._last_message] or MESSAGES
        self._last_message = self.rng.choice(choices)
        return self._last_message

    def clamp_message_pos(self, x, y):
        """Keep a message fully inside the canvas (it is centred on its position and can be ~400 px wide)."""
        ex, ey = MESSAGE_EDGE_X * self.scale, MESSAGE_EDGE_Y * self.scale
        x = self.width / 2.0 if self.width <= 2 * ex else max(ex, min(self.width - ex, x))
        y = self.height / 2.0 if self.height <= 2 * ey else max(ey, min(self.height - ey, y))
        return x, y

    def spawn_message(self, x=None, y=None):
        """Message pops out at (x, y) - the centre of the burst (default: canvas centre), nudged inward near the
        edges so it is never cut off. Returns it, or None if on cooldown."""
        if self.messages and self.messages[-1].age < MESSAGE_COOLDOWN:
            return None
        if x is None or y is None:
            x, y = self.width / 2.0, self.height / 2.0
        x, y = self.clamp_message_pos(x, y)
        msg = FloatingMessage(self.pick_message(), x, y)
        self.messages.append(msg)
        while len(self.messages) > MESSAGE_MAX:
            self.messages.pop(0)
        return msg

    # ---- time ----
    def step(self, dt):
        dt = max(0.0, min(dt, 0.1))           # a lag spike must not teleport particles
        damp = math.exp(-DRAG * dt)
        alive = []
        for p in self.particles:
            p.age += dt
            if p.age >= p.life:
                continue
            p.vx *= damp
            p.vy = p.vy * damp + GRAVITY * self.scale * dt
            p.x += p.vx * dt
            p.y += p.vy * dt
            alive.append(p)
        self.particles = alive
        kept = []
        for m in self.messages:
            m.age += dt
            if m.age >= MESSAGE_LIFE:
                continue
            m.y -= MESSAGE_RISE_SPEED * self.scale * dt
            kept.append(m)
        self.messages = kept

    @property
    def idle(self):
        """True when nothing is on screen - the window can stop its frame loop until the next click."""
        return not self.particles and not self.messages
