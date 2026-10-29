"""
Progress logs kept inside the save file (pure logic, no Tkinter, easy to unit-test).

Everything is stored through AppState.settings / AppState.set_setting() (which also writes
the save file), under two keys, exactly like weekly_checkin.py does:

  "dass21_history"  list, OLDEST FIRST, at most DASS_HISTORY_MAX (14) entries.
      One entry per DASS-21 quiz the user SUBMITS (the quiz is only offered once a week):
        {"date": "2026-10-29", "time": "14:05", "week": 3,
         "score": 18.0, "level": "mild"}
      score = DASS-21 stress-subscale score 0-42 (sum of the 7 answers x 2)
      level = key of the DASS band ("normal"|"mild"|"moderate"|"severe"|"extremely_severe")
      week  = 0-based week number counted from the start-using date (dass21_schedule anchor)

  "session_log"     list, OLDEST FIRST, at most SESSION_LOG_MAX (28) entries.
      One entry per start-up check-in (= one "session"):
        {"id": 7, "date": "2026-10-29",
         "started_at": "2026-10-29T14:05:11", "ended_at": "2026-10-29T15:40:02" | null,
         "start": {"scan": 12.3|null, "quiz": 18.0|null, "quiz_kind": "dass"|"emotion"|null,
                   "mailbox": 21.0|null, "average": 17.1|null},
         "end":   {"emotion": "Worried"|null, "score": 17.0|null}}
      start.* are the three start-up diagnosis features on the 0-42 scale. "quiz" holds the
      DASS-21 score on the weeks the quiz is due, otherwise the emotion-scale score
      (quiz_kind says which). A feature that was not collected (e.g. camera unusable) is null.
      end.* is the face the user picks when leaving the app (score = hidden 0-42 value).
      ended_at/end stay null if the app was closed some other way (crash, quit during login...).

Nothing here ever raises into the UI: every public function swallows bad data and returns a
harmless value, because logging must never break the app.
"""

from datetime import datetime, date

DASS_KEY = "dass21_history"
SESSION_KEY = "session_log"
DASS_HISTORY_MAX = 14
SESSION_LOG_MAX = 28


# ----------------------------------------------------------------------------- helpers
def _now(now=None):
    return now if isinstance(now, datetime) else datetime.now()


def _list(settings, key):
    data = settings.get(key) if isinstance(settings, dict) else None
    return [x for x in data if isinstance(x, dict)] if isinstance(data, list) else []


def _num(value, nd=1):
    """float rounded to `nd` decimals, or None."""
    try:
        if value is None or isinstance(value, bool):
            return None
        return round(float(value), nd)
    except Exception:
        return None


def append_capped(items, entry, cap):
    """New list = items + [entry], keeping only the newest `cap` entries."""
    out = list(items) + [entry]
    return out[-cap:] if cap > 0 else out


def _week_of(settings, today):
    """0-based week number from the dass21_schedule anchor, or None if there is no anchor."""
    try:
        sched = settings.get("dass21_schedule") if isinstance(settings, dict) else None
        anchor = date.fromisoformat(str(sched.get("anchor_date"))[:10])
        return max(0, (today - anchor).days // 7)
    except Exception:
        return None


# ----------------------------------------------------------------------------- DASS-21 history
def get_dass_history(settings):
    """Stored DASS-21 history (oldest first), [] if none."""
    return _list(settings, DASS_KEY)


def log_dass(settings, set_setting, score, level_key=None, now=None):
    """Record one submitted DASS-21 quiz. Returns the stored entry, or None on failure."""
    try:
        score = _num(score)
        if score is None:
            return None
        n = _now(now)
        if level_key is None:
            try:
                from utils.stress_diagnosis import classify_stress
                level_key = classify_stress(score).key
            except Exception:
                level_key = None
        entry = {
            "date": n.date().isoformat(),
            "time": n.strftime("%H:%M"),
            "week": _week_of(settings, n.date()),
            "score": score,
            "level": level_key,
        }
        set_setting(DASS_KEY, append_capped(get_dass_history(settings), entry, DASS_HISTORY_MAX))
        return entry
    except Exception as e:
        print(f"[progress_log] could not log DASS-21: {type(e).__name__}: {e}")
        return None


# ----------------------------------------------------------------------------- session log
def get_session_log(settings):
    """Stored session log (oldest first), [] if none."""
    return _list(settings, SESSION_KEY)


def begin_session(settings, set_setting, state, now=None):
    """
    Record the START of a session from the start-up check-in's finished first round.
    `state` is a StressDiagnosisState (uses .facial_scan_score, .quiz_score, .emotion_score,
    .mailbox_score and .average()). Returns the new session id (int) or None on failure.
    """
    try:
        n = _now(now)
        log = get_session_log(settings)
        ids = [e.get("id") for e in log if isinstance(e.get("id"), int)]
        new_id = (max(ids) + 1) if ids else 1

        quiz = getattr(state, "quiz_score", None)
        emotion = getattr(state, "emotion_score", None)
        if quiz is not None:
            quiz_val, quiz_kind = quiz, "dass"
        elif emotion is not None:
            quiz_val, quiz_kind = emotion, "emotion"
        else:
            quiz_val, quiz_kind = None, None
        try:
            avg = state.average()
        except Exception:
            avg = None

        entry = {
            "id": new_id,
            "date": n.date().isoformat(),
            "started_at": n.isoformat(timespec="seconds"),
            "ended_at": None,
            "start": {
                "scan": _num(getattr(state, "facial_scan_score", None)),
                "quiz": _num(quiz_val),
                "quiz_kind": quiz_kind,
                "mailbox": _num(getattr(state, "mailbox_score", None)),
                "average": _num(avg),
            },
            "end": {"emotion": None, "score": None},
        }
        set_setting(SESSION_KEY, append_capped(log, entry, SESSION_LOG_MAX))
        return new_id
    except Exception as e:
        print(f"[progress_log] could not start session log: {type(e).__name__}: {e}")
        return None


def end_session(settings, set_setting, session_id, emotion_key, emotion_score, now=None):
    """
    Fill in the END of session `session_id` with the face picked on exit.
    emotion_key: "Happy"|"Worried"|"Sad"|"Angry" (or None if the user closed the prompt);
    emotion_score: the hidden 0-42 value (utils.stress_diagnosis.score_emotion) or None.
    Returns True if an entry was updated.
    """
    try:
        if session_id is None:
            return False
        n = _now(now)
        log = [dict(e) for e in get_session_log(settings)]
        for e in reversed(log):
            if e.get("id") == session_id:
                e["ended_at"] = n.isoformat(timespec="seconds")
                e["end"] = {"emotion": emotion_key if emotion_key else None,
                            "score": _num(emotion_score)}
                set_setting(SESSION_KEY, log)
                return True
        return False
    except Exception as e:
        print(f"[progress_log] could not finish session log: {type(e).__name__}: {e}")
        return False
