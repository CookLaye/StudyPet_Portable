"""Pure geometry for the three collapsible panels on the main screen.

No Tk in here on purpose: it is a plain function, so it can be unit-tested
without a display.  MainGameScreen.layout_panels() calls it and hands each
result to the matching CollapsiblePanel.place_at().

Rules (all numbers are in real pixels; `scale` is the DPI factor self.ui_scale):
  * Pet Status sits top-left.
  * Pet Chat sits top-right, flush with the right margin.
  * Study Timer sits immediately LEFT of Pet Chat.
  * Every position is derived from the window size on every call, so nothing
    can drift, overlap or run off-screen after a resize.
  * Panels start below the nav bar (NAV_REL_HEIGHT must match the nav bar's
    relheight in setup_ui).
"""
from dataclasses import dataclass
from typing import Dict, Optional

NAV_REL_HEIGHT = 0.07        # nav_frame.place(..., relheight=0.07)
TASKBAR_REL_HEIGHT = 0.06    # bottom taskbar height as a fraction of window height


@dataclass(frozen=True)
class PanelSlot:
    x: int
    y: int
    w: int
    max_h: int                       # tallest this panel may ever be (never overlaps the taskbar)
    expanded_h: Optional[int] = None  # fixed expanded height; None = follow the content


def _clamp(v: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, v))


def compute_panel_slots(win_w: int, win_h: int, scale: float = 1.0,
                        status_min_w: int = 0) -> Dict[str, PanelSlot]:
    """status_min_w: width (px) the Pet Status content needs right now, measured by the
    caller (e.g. wider while the developer tools are showing). 0 = no extra demand."""
    def s(px: float) -> int:
        return max(1, round(px * scale))

    margin, gap = s(20), s(16)
    top = round(win_h * NAV_REL_HEIGHT) + s(10)
    bottom_limit = win_h - round(win_h * TASKBAR_REL_HEIGHT) - s(10) - s(10)
    max_h = max(s(120), bottom_limit - top)

    status_w = _clamp(round(win_w * 0.15), s(190), s(300))
    # Grow to fit content (dev tools), but never take more than 35% of the window.
    status_w = max(status_w, min(int(status_min_w), round(win_w * 0.35)))
    timer_w = _clamp(round(win_w * 0.23), s(300), s(420))
    chat_w = _clamp(round(win_w * 0.225), s(300), s(420))

    # Right-hand column pair must fit between the status panel and the right margin.
    left_limit = margin + status_w + gap
    available = (win_w - margin) - left_limit
    if timer_w + gap + chat_w > available:
        k = max(0.0, available - gap) / (timer_w + chat_w)
        timer_w = max(s(220), int(timer_w * k))
        chat_w = max(s(220), int(chat_w * k))

    # Absurdly small window for this DPI: the two right panels share the whole width.
    if timer_w + gap + chat_w > win_w - 2 * margin:
        timer_w = chat_w = max(s(100), (win_w - 2 * margin - gap) // 2)

    chat_x = win_w - margin - chat_w
    # Timer and chat never overlap each other. On a window too small for all three
    # (below ~1000 px of DPI-normalised width) the status panel may sit under the timer.
    timer_x = max(0, chat_x - gap - timer_w)

    chat_h = min(max(round(win_h * 0.45), s(260)), max_h)

    return {
        "status": PanelSlot(margin, top, status_w, max_h),
        "timer": PanelSlot(timer_x, top, timer_w, max_h),
        "chat": PanelSlot(chat_x, top, chat_w, max_h, expanded_h=chat_h),
    }
