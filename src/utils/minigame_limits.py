"""
Daily limit for minigame AFFECTION rewards. Minigames themselves are always playable.

Rule: the first DAILY_REWARDED_PLAYS runs per calendar day (local time, resets at midnight) that
score something pay affection. Further runs are "practice runs": same game, no affection.

Pure functions only (no Tk, no files) so they are easy to test. AppState keeps the two stored values
(`minigame_rewards_date`, `minigame_rewards_used`) and calls these.
"""

from datetime import datetime

DAILY_REWARDED_PLAYS = 3       # <- the only number to change to make it 2 / 5 / ...


def today_str(now=None):
    return (now or datetime.now()).strftime("%Y-%m-%d")


def normalize(day, used, today):
    """Return a clean (day, used). A different/invalid day, or a bad count, starts a fresh day at 0."""
    try:
        used = int(used)
    except (TypeError, ValueError):
        used = 0
    if day != today or used < 0:
        return today, 0
    return day, used


def rewards_left(day, used, today):
    day, used = normalize(day, used, today)
    return max(0, DAILY_REWARDED_PLAYS - used)


def claim(day, used, today):
    """Try to use one rewarded play. Returns (ok, day, used)."""
    day, used = normalize(day, used, today)
    if used >= DAILY_REWARDED_PLAYS:
        return False, day, used
    return True, day, used + 1
