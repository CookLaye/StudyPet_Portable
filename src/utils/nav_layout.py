"""
Pure sizing logic for the main top bar (no Tkinter in here, so it is unit-tested headless).

The top bar has up to 8 rounded buttons. choose() picks the LARGEST size (font + padding + gaps, all scaled
together) at which every visible button fits in the bar's current width AND height, between MIN_SCALE and
MAX_SCALE:
    * narrow window  -> buttons shrink so Settings and Breathe are never cut off
    * wide window    -> buttons grow a little (up to MAX_SCALE) so the bar does not look tiny

TUNING: MIN_SCALE / MAX_SCALE below, and the BASE_* numbers (the size at scale 1.0 = the old fixed look).
"""
from collections import namedtuple

MIN_SCALE = 0.60
MAX_SCALE = 1.20
STEP = 0.05

BASE_FONT = 10        # pt, bold Arial (the old fixed font)
BASE_PAD_X = 12       # px inside a button, left/right   (before DPI scaling)
BASE_PAD_Y = 6        # px inside a button, top/bottom
BASE_GAP_X = 8        # px between buttons
BASE_GAP_Y = 6        # px above/below buttons

Metrics = namedtuple("Metrics", "font pad_x pad_y gap_x gap_y")


def metrics_for(scale, px_scale=1.0):
    """Button metrics at a given scale. px_scale = the display DPI factor (self.ui_scale)."""
    return Metrics(
        font=max(7, int(round(BASE_FONT * scale))),
        pad_x=max(4, int(round(BASE_PAD_X * px_scale * scale))),
        pad_y=max(2, int(round(BASE_PAD_Y * px_scale * scale))),
        gap_x=max(2, int(round(BASE_GAP_X * px_scale * scale))),
        gap_y=max(2, int(round(BASE_GAP_Y * px_scale * scale))),
    )


def needed_size(texts, m, measure, linespace):
    """(total width, bar height) needed by these button labels at metrics m."""
    w = sum(measure(t, m.font) + 2 * m.pad_x + 2 * m.gap_x for t in texts)
    h = linespace(m.font) + 2 * m.pad_y + 2 * m.gap_y
    return w, h


def choose(texts, avail_w, avail_h, measure, linespace, px_scale=1.0, margin=12):
    """Return (scale, Metrics): the largest scale whose buttons fit; MIN_SCALE if nothing fits.
    measure(text, font_size) -> px width, linespace(font_size) -> px height are supplied by the caller."""
    n_steps = int(round((MAX_SCALE - MIN_SCALE) / STEP))
    for i in range(n_steps + 1):
        scale = round(MAX_SCALE - i * STEP, 2)
        m = metrics_for(scale, px_scale)
        w, h = needed_size(texts, m, measure, linespace)
        if w + margin <= avail_w and h <= avail_h:
            return scale, m
    return MIN_SCALE, metrics_for(MIN_SCALE, px_scale)
