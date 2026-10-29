"""Decide which quick-action buttons to offer under a pet reply (pure logic, no UI)."""

import re
import unicodedata

ACTION_LABELS = {
    "breathing": {"en": "Breathe together", "vi": "Hít thở cùng nhau"},
    "mailbox": {"en": "Write a letter", "vi": "Viết thư tâm sự"},
    "music": {"en": "Calming music", "vi": "Nhạc thư giãn"},
}
PRIORITY = ["breathing", "mailbox", "music"]
MAX_ACTIONS = 2

# Patterns with accents are matched on the lower-cased text.
# ASCII patterns are matched only when the user typed WITHOUT accents (so "hoàng" never matches "hoang").
_PATTERNS = {
    "breathing": {
        "accent": [r"hoảng", r"lo lắng", r"căng thẳng", r"áp lực", r"tim đập nhanh", r"không thở nổi",
                   r"run tay", r"bình tĩnh", r"hít thở", r"quá tải", r"stress"],
        "ascii": [r"hoang\b", r"lo lang", r"cang thang", r"ap luc", r"tim dap nhanh", r"khong tho noi",
                  r"run tay", r"binh tinh", r"hit tho", r"qua tai"],
        "en": [r"overwhelm", r"panic", r"anxious", r"anxiety", r"can'?t breathe", r"heart (is )?racing",
               r"shaking", r"freaking out", r"calm (me )?down", r"stressed", r"on edge"],
    },
    "mailbox": {
        "accent": [r"tâm sự", r"xả stress", r"không có ai để nói", r"không ai nghe", r"muốn viết", r"trút bầu tâm sự"],
        "ascii": [r"tam su", r"xa stress", r"khong co ai de noi", r"khong ai nghe"],
        "en": [r"\bvent\b", r"get it off my chest", r"nobody to talk to", r"no one to talk to",
               r"write (it|this) down", r"need to let it out"],
    },
    "music": {
        "accent": [r"mất ngủ", r"thư giãn", r"nhạc", r"kiệt sức", r"mệt mỏi", r"khó ngủ"],
        "ascii": [r"mat ngu", r"thu gian", r"kho ngu"],
        "en": [r"can'?t sleep", r"insomnia", r"relax", r"\bmusic\b", r"exhausted", r"so tired", r"burn(ed|t)? out"],
    },
}


def _fold(s):
    s = s.replace("đ", "d").replace("Đ", "D")
    return "".join(c for c in unicodedata.normalize("NFD", s) if not unicodedata.combining(c))


def suggest_actions(user_text, recent=()):
    """Return up to MAX_ACTIONS action ids, skipping any in `recent` (shown in the last few replies)."""
    raw = (user_text or "").lower()
    if not raw.strip():
        return []
    typed_without_accents = (raw == _fold(raw))
    hits = []
    for action in PRIORITY:
        pats = _PATTERNS[action]
        candidates = pats["en"] + pats["accent"] + (pats["ascii"] if typed_without_accents else [])
        if any(re.search(p, raw) for p in candidates):
            hits.append(action)
    hits = [a for a in hits if a not in set(recent)]
    return hits[:MAX_ACTIONS]


def label(action, lang="en"):
    return ACTION_LABELS[action].get(lang) or ACTION_LABELS[action]["en"]
