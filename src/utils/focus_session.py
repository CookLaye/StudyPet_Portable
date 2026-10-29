"""
Glue between the Pomodoro timer and the focus tracker (kept out of main_game_screen.py on purpose).

The timer screen calls sync() about once per second with the timer's state; everything else (starting and
stopping the camera, the small window, strikes, scolding, ending the session) happens here.

Rules:
    - Only runs when focus tracking is enabled in settings AND the timer runs a WORK phase.
    - Paused  -> camera released and the window is hidden (like its X button); strikes and calibration are kept.
    Resume   -> the window is shown again immediately and the camera restarts.
    - BREAK / stopped / finished / disabled -> session over: camera released, window closed, strikes forgotten.
    - A camera or model failure never blocks the timer: the window shows the problem, nothing strikes.
    - A strike scolds through NotificationManager (Windows toast) AND the pet speech bubble AND a window flash,
      because Windows Focus Assist can silence toasts. The last strike calls on_session_end("distraction").
"""

from stress_scan import focus_logic as F


class FocusSessionController:
    POLL_MS = 250

    def __init__(self, parent, tracker_factory, window_factory, is_enabled, get_pet_name,
                 notify, speak, on_session_end):
        """
        parent           widget with after()/after_cancel()
        tracker_factory  callable(engine, calib_holder) -> tracker  (start/stop/snapshot/pop_events/request_recalibration)
        window_factory   callable(on_recalibrate) -> window         (update(snapshot, paused)/flash()/close())
        is_enabled       callable() -> bool       (the opt-in setting)
        get_pet_name     callable() -> str|None
        notify           callable(title, message) (NotificationManager.notify)
        speak            callable(message)        (pet speech bubble)
        on_session_end   callable(reason)         (main screen aborts the timer WITHOUT rewards)
        """
        self.parent = parent
        self._tracker_factory = tracker_factory
        self._window_factory = window_factory
        self._is_enabled = is_enabled
        self._get_pet_name = get_pet_name
        self._notify = notify
        self._speak = speak
        self._on_session_end = on_session_end

        self._calib_holder = {"calib": None}     # kept for the whole app run; the Recalibrate button resets it
        self._engine = None
        self._tracker = None
        self._window = None
        self._after_id = None
        self._failed = False
        self._paused = False

    # ---- public ----
    @property
    def active(self):
        return self._engine is not None

    def sync(self, timer_running, paused, phase, total_minutes):
        """Idempotent: call as often as you like (the timer calls it every second)."""
        try:
            want_session = bool(self._is_enabled()) and bool(timer_running) and phase == "WORK"
            if not want_session:
                if self._engine is not None:
                    self._end_session()
                return
            if self._engine is None:
                self._engine = F.FocusEngine(total_minutes)
                self._failed = False
                self._paused = False
                self._window = self._window_factory(self._recalibrate)
            if paused != self._paused:                  # only on a change: hide on pause, show again on resume
                self._paused = bool(paused)
                self._call(self._window, "set_paused", self._paused)
            if paused:
                self._stop_tracker()
                self._call(self._window, "update", {"phase": "paused", "message": "Paused"}, True)
            elif self._tracker is None and not self._failed:
                self._tracker = self._tracker_factory(self._engine, self._calib_holder)
                self._tracker.start()
            self._schedule_poll()
        except Exception as e:                    # focus tracking must never break the timer
            print(f"[FocusSession] sync error: {e}")

    def shutdown(self):
        self._end_session()

    # ---- internals ----
    def _recalibrate(self):
        if self._tracker is not None:
            self._tracker.request_recalibration()

    def _schedule_poll(self):
        if self._after_id is None:
            self._after_id = self.parent.after(self.POLL_MS, self._poll)

    def _poll(self):
        self._after_id = None
        if self._engine is None:
            return
        try:
            if self._tracker is not None:
                snap = self._tracker.snapshot()
                self._call(self._window, "update", snap, False)
                if snap.get("phase") == "error":
                    self._failed = True           # show the message, never retry in a loop, never strike
                    self._stop_tracker(keep_window=True)
                for ev in self._tracker.pop_events() if self._tracker is not None else []:
                    if self._handle_strike(ev):
                        return
        except Exception as e:
            print(f"[FocusSession] poll error: {e}")
        if self._engine is not None:
            self._schedule_poll()

    def _handle_strike(self, ev):
        """Scold. Returns True if this strike ended the session."""
        title, message = F.scold_message(self._get_pet_name(), ev)
        self._call(self, "_safe_notify", title, message)
        self._call(self, "_safe_speak", message)
        self._call(self._window, "flash")
        if ev.get("end"):
            self._end_session()
            self._call(self, "_safe_end", "distraction")
            return True
        return False

    def _safe_notify(self, title, message):
        self._notify(title, message)

    def _safe_speak(self, message):
        self._speak(message)

    def _safe_end(self, reason):
        self._on_session_end(reason)

    def _stop_tracker(self, keep_window=True):
        tracker, self._tracker = self._tracker, None
        if tracker is not None:
            try:
                tracker.stop(timeout=2.0)
            except Exception as e:
                print(f"[FocusSession] tracker stop error: {e}")

    def _end_session(self):
        if self._after_id is not None:
            try:
                self.parent.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None
        self._stop_tracker()
        window, self._window = self._window, None
        self._call(window, "close")
        self._engine = None
        self._failed = False
        self._paused = False

    @staticmethod
    def _call(obj, name, *args):
        if obj is None:
            return
        try:
            getattr(obj, name)(*args)
        except Exception as e:
            print(f"[FocusSession] {name} failed: {e}")
