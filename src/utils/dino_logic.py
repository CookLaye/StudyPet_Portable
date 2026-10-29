"""
Pure game logic for the "Pet Runner" (dinosaur-style) minigame.

No Tkinter, no images, no file access in here - so it can be unit-tested on any machine.
The window (screens/dino_game_window.py) only draws what this class says and forwards
key presses / clicks to jump().

COORDINATES ("logical units")
    The world is WORLD_W x WORLD_H logical units. x grows to the right, y grows DOWNWARD
    (like Tk canvas). The ground surface is at y = GROUND_Y. The window multiplies every
    number by one scale factor when drawing, so nothing here knows about real pixels.

TUNING: every gameplay number is a constant below - change a number, nothing else.
"""

import math
import random

# ------------------------------ world --------------------------------------
WORLD_W = 640
WORLD_H = 220
GROUND_Y = 180                 # y of the ground line (feet of the pet / bottom of cacti)

# ------------------------------ pet ----------------------------------------
PET_SIZE = 56                  # the pet picture is drawn PET_SIZE x PET_SIZE
PET_X = 70                     # left edge of the pet (it never moves sideways)
HITBOX_SHRINK = 0.20           # each side of the pet box is shrunk by this fraction (forgiving)

# ------------------------------ physics ------------------------------------
GRAVITY = 2600.0               # units / s^2   (downward)
JUMP_SPEED = 800.0             # units / s     (upward launch speed)
# airtime = 2 * JUMP_SPEED / GRAVITY  (~0.62 s), peak height = JUMP_SPEED^2 / (2 * GRAVITY) (~123 units)

# ------------------------------ speed --------------------------------------
START_SPEED = 260.0            # world scroll speed in units / s
MAX_SPEED = 560.0
SPEED_UP_PER_SEC = 9.0         # speed gained per second of running

# ------------------------------ obstacles ----------------------------------
OBSTACLE_MIN_W = 16
OBSTACLE_MAX_W = 34
OBSTACLE_MIN_H = 30
OBSTACLE_MAX_H = 58            # must stay well below the jump peak (~123)
GAP_SAFETY = 1.15              # multiplier on the distance travelled during one jump
GAP_EXTRA_MIN = 70             # extra units of free space on top of the jump distance...
GAP_EXTRA_MAX = 260            # ...randomly up to this much
FIRST_OBSTACLE_X = WORLD_W + 120

# ------------------------------ day / night ---------------------------------
DAY_NIGHT_EVERY = 20           # score points between day <-> night switches (0-19 day, 20-39 night, ...)


def phase_for_score(score):
    """'day' or 'night' for a given score (starts as day, flips every DAY_NIGHT_EVERY points)."""
    return "night" if (max(0, int(score)) // DAY_NIGHT_EVERY) % 2 == 1 else "day"


# ------------------------------ reward -------------------------------------
REWARD_STEP = 10               # same rule as the circle game: every started 10 points = +10 affection


def reward_for_score(score):
    """Affection reward: ceil(score / 10) * 10  (0 points -> 0 affection)."""
    score = max(0, int(score))
    return int(math.ceil(score / float(REWARD_STEP))) * REWARD_STEP


class Obstacle:
    __slots__ = ("x", "w", "h", "passed")

    def __init__(self, x, w, h):
        self.x = float(x)       # left edge
        self.w = int(w)
        self.h = int(h)
        self.passed = False

    @property
    def rect(self):
        """(left, top, right, bottom) in logical units."""
        return (self.x, GROUND_Y - self.h, self.x + self.w, GROUND_Y)


class DinoGame:
    READY, RUNNING, OVER = "ready", "running", "over"

    def __init__(self, rng=None):
        self.rng = rng if rng is not None else random.Random()
        self.reset()

    # --------------------------------------------------------------- state
    def reset(self):
        self.state = self.READY
        self.speed = START_SPEED
        self.score = 0                 # obstacles jumped over
        self.elapsed = 0.0
        self.pet_y = float(GROUND_Y - PET_SIZE)   # TOP of the pet box
        self.vy = 0.0
        self.on_ground = True
        self.obstacles = []
        self._next_spawn_x = FIRST_OBSTACLE_X
        self._spawn_until(WORLD_W + 400)

    def start(self):
        if self.state == self.READY:
            self.state = self.RUNNING

    @property
    def running(self):
        return self.state == self.RUNNING

    @property
    def over(self):
        return self.state == self.OVER

    # --------------------------------------------------------------- input
    def jump(self):
        """Space / Up / click. First press starts the game; later presses jump if on the ground."""
        if self.state == self.READY:
            self.start()
        if self.state == self.RUNNING and self.on_ground:
            self.vy = -JUMP_SPEED
            self.on_ground = False

    # --------------------------------------------------------------- hitbox
    def pet_rect(self):
        """Forgiving collision box of the pet (left, top, right, bottom)."""
        pad = PET_SIZE * HITBOX_SHRINK
        return (PET_X + pad, self.pet_y + pad, PET_X + PET_SIZE - pad, self.pet_y + PET_SIZE - pad)

    # --------------------------------------------------------------- update
    def step(self, dt):
        """Advance the world by dt seconds (dt is clamped so a lag spike cannot teleport the pet)."""
        if self.state != self.RUNNING:
            return
        dt = max(0.0, min(float(dt), 0.05))
        if dt == 0.0:
            return

        self.elapsed += dt
        self.speed = min(MAX_SPEED, self.speed + SPEED_UP_PER_SEC * dt)

        # pet physics
        if not self.on_ground:
            self.vy += GRAVITY * dt
            self.pet_y += self.vy * dt
            floor_top = GROUND_Y - PET_SIZE
            if self.pet_y >= floor_top:
                self.pet_y = float(floor_top)
                self.vy = 0.0
                self.on_ground = True

        # scroll obstacles
        dx = self.speed * dt
        for ob in self.obstacles:
            ob.x -= dx
        self._next_spawn_x -= dx

        # scoring: an obstacle counts once its right edge is left of the pet
        for ob in self.obstacles:
            if not ob.passed and ob.x + ob.w < PET_X:
                ob.passed = True
                self.score += 1

        # drop obstacles that left the screen, add new ones on the right
        self.obstacles = [o for o in self.obstacles if o.x + o.w > -10]
        self._spawn_until(WORLD_W + 400)

        # collision
        pl, pt, pr, pb = self.pet_rect()
        for ob in self.obstacles:
            ol, ot, orr, ob_ = ob.rect
            if pl < orr and pr > ol and pt < ob_ and pb > ot:
                self.state = self.OVER
                return

    # --------------------------------------------------------------- spawning
    def _min_gap(self):
        airtime = 2.0 * JUMP_SPEED / GRAVITY
        return self.speed * airtime * GAP_SAFETY

    def _spawn_until(self, x_limit):
        """Keep obstacles queued until the spawn cursor passes x_limit."""
        while self._next_spawn_x < x_limit:
            w = self.rng.randint(OBSTACLE_MIN_W, OBSTACLE_MAX_W)
            h = self.rng.randint(OBSTACLE_MIN_H, OBSTACLE_MAX_H)
            self.obstacles.append(Obstacle(self._next_spawn_x, w, h))
            gap = self._min_gap() + self.rng.uniform(GAP_EXTRA_MIN, GAP_EXTRA_MAX)
            self._next_spawn_x += w + gap
