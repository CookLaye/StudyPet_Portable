"""
Weekly schedule for the DASS-21 quiz (pure logic, no Tkinter, easy to unit-test).

Rule
----
* The first time the stress check-in ever runs, today's date is stored as the
  "start-using date" (the anchor).
* Time is cut into 7-day weeks counted from that anchor:
      week 0 = anchor .. anchor+6,  week 1 = anchor+7 .. anchor+13, ...
* The DASS-21 quiz is due on the FIRST check-in of each week. Once the user has
  SUBMITTED it, it is not offered again until the next week begins.
  (Quitting in the middle of the quiz does not count - it is offered again.)
* Every other check-in uses the emotion scale instead.

Everything is stored inside the existing save file through
AppState.settings / AppState.set_setting(), under one key: "dass21_schedule".
"""

from datetime import date, datetime

SETTINGS_KEY = "dass21_schedule"
WEEK_DAYS = 7


def _today(today=None):
    if today is None:
        return date.today()
    return today.date() if isinstance(today, datetime) else today


def _parse(iso):
    try:
        return date.fromisoformat(str(iso)[:10])
    except Exception:
        return None


def get_schedule(settings):
    """Return the stored schedule dict ({} if none / corrupt)."""
    data = settings.get(SETTINGS_KEY) if isinstance(settings, dict) else None
    return data if isinstance(data, dict) else {}


def week_index(anchor, today=None):
    """0-based week number of `today` counted from `anchor` (never negative)."""
    return max(0, (_today(today) - anchor).days // WEEK_DAYS)


def ensure_anchor(settings, set_setting, today=None):
    """Make sure the start-using date exists; returns it as a date.
    set_setting(key, value) is AppState.set_setting (it also saves the file)."""
    sched = dict(get_schedule(settings))
    anchor = _parse(sched.get("anchor_date"))
    if anchor is None:
        anchor = _today(today)
        sched["anchor_date"] = anchor.isoformat()
        sched.setdefault("last_completed_week", None)
        set_setting(SETTINGS_KEY, sched)
    return anchor


def is_dass_due(settings, today=None):
    """True if the DASS-21 quiz should be offered now.
    Does not write anything (an unseen anchor means 'first ever check-in' -> due)."""
    sched = get_schedule(settings)
    anchor = _parse(sched.get("anchor_date"))
    if anchor is None:
        return True
    last = sched.get("last_completed_week")
    if not isinstance(last, int):
        return True
    return week_index(anchor, today) > last


def mark_dass_completed(settings, set_setting, today=None, score=None):
    """Call right after the user SUBMITS the DASS-21 quiz.
    If `score` (0-42) is given it is also written to the weekly DASS-21 history (progress_log)."""
    anchor = ensure_anchor(settings, set_setting, today)
    sched = dict(get_schedule(settings))
    sched["anchor_date"] = anchor.isoformat()
    sched["last_completed_week"] = week_index(anchor, today)
    sched["last_completed_on"] = _today(today).isoformat()
    set_setting(SETTINGS_KEY, sched)
    if score is not None:
        try:
            from datetime import datetime as _dt
            from utils.progress_log import log_dass
            log_dass(settings, set_setting, score, now=_dt.combine(_today(today), _dt.now().time()))
        except Exception as e:
            print(f"[weekly_checkin] could not log DASS-21 score: {e}")
