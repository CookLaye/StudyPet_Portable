"""
Quiz generation from pasted study material (pure logic + one HTTP helper, no Tkinter).

How it works
------------
1. The text is cleaned and cut into chunks small enough for the local model (context is only 4096 tokens).
2. Chunks are spread evenly over the text and ONE multiple-choice question is requested per call
   (small models are far more reliable with one small JSON answer than with a whole quiz at once).
3. The model returns {question, correct_answer, wrong_answers[3], explanation}. The code validates it,
   rejects questions that are not grounded in the chunk, and SHUFFLES the options itself
   (so the correct answer is never biased to a position by the model).
4. Finished quizzes can be kept in the save file through AppState.settings under one key: "quiz_library".

generate_quiz() BLOCKS: call it from a background thread, never from the Tk thread.
"""

import json
import random
import re
import time
import unicodedata
import urllib.request
import uuid
from datetime import datetime

# ---- tunables ---------------------------------------------------------------
MIN_INPUT_CHARS = 300          # shorter text cannot make a meaningful quiz
MAX_INPUT_CHARS = 60000        # refuse bigger pastes (UI shows the counter)
CHUNK_MAX_CHARS = 2400         # ~600 tokens English, ~1600 Vietnamese: fits 4096 ctx with prompt + answer
MIN_CHUNK_CHARS = 150          # tiny leftovers are merged into the previous chunk
QUESTION_CHOICES = (5, 8, 10)
DEFAULT_QUESTIONS = 5
MAX_TOKENS = 320               # one question in JSON (Vietnamese needs the room)
TEMPERATURE = 0.4
RETRIES_PER_QUESTION = 2       # extra tries after the first failed/rejected answer
REQUEST_TIMEOUT_SECONDS = 90   # one question
WAIT_READY_SECONDS = 45        # waiting for a still-loading server
MAX_LIBRARY = 10               # saved quizzes kept in the save file (oldest dropped)
SETTINGS_KEY = "quiz_library"
GROUNDING_MIN_RATIO = 0.5      # share of the correct answer's words that must appear in the chunk

_LANG_NAME = {"en": "English", "vi": "Vietnamese (with full accents)"}

SYSTEM_PROMPT = (
    "You write ONE multiple-choice quiz question from a passage for a student. "
    "Use ONLY facts that are stated in the passage. "
    "Ask about a specific fact, definition, cause, step or relationship. "
    "Write the question, the answers and the explanation in {language}. "
    "Reply with JSON only, in exactly this form: "
    "{{\"question\": \"...\", \"correct_answer\": \"...\", \"wrong_answers\": [\"...\", \"...\", \"...\"], "
    "\"explanation\": \"...\"}}. "
    "The 3 wrong answers must be plausible, similar in length and style to the correct answer, "
    "and clearly wrong according to the passage. "
    "Never use \"all of the above\" or \"none of the above\". "
    "The explanation is one short sentence that says why the correct answer is right."
)

SCHEMA = {
    "type": "object",
    "properties": {
        "question": {"type": "string"},
        "correct_answer": {"type": "string"},
        "wrong_answers": {"type": "array", "items": {"type": "string"}, "minItems": 3, "maxItems": 3},
        "explanation": {"type": "string"},
    },
    "required": ["question", "correct_answer", "wrong_answers", "explanation"],
    "additionalProperties": False,
}

_BAD_OPTION = re.compile(r"\b(all|none) of the above\b|tất cả (các )?(đáp án|ý) (trên|đều)|không (có )?đáp án nào", re.I)
_WORD = re.compile(r"\w+", re.UNICODE)


# =============================================================================
# Text preparation
# =============================================================================
def clean_source(text):
    t = (text or "").replace("\r\n", "\n").replace("\r", "\n").replace("\u00a0", " ")
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()


def check_source(text):
    """Return (ok, reason) where reason is 'empty' | 'too_short' | 'too_long' | None."""
    t = clean_source(text)
    if not t:
        return False, "empty"
    if len(t) < MIN_INPUT_CHARS:
        return False, "too_short"
    if len(t) > MAX_INPUT_CHARS:
        return False, "too_long"
    return True, None


def _split_long(paragraph, max_chars):
    """Cut an over-long paragraph at sentence ends (hard cut as a last resort)."""
    sentences = re.split(r"(?<=[.!?。])\s+", paragraph)
    out, cur = [], ""
    for s in sentences:
        while len(s) > max_chars:                       # one monster sentence
            if cur:
                out.append(cur)
                cur = ""
            out.append(s[:max_chars])
            s = s[max_chars:]
        if cur and len(cur) + 1 + len(s) > max_chars:
            out.append(cur)
            cur = s
        else:
            cur = (cur + " " + s).strip()
    if cur:
        out.append(cur)
    return out


def split_chunks(text, max_chars=CHUNK_MAX_CHARS, min_chars=MIN_CHUNK_CHARS):
    """Pack paragraphs into chunks of at most max_chars. Order is preserved."""
    text = clean_source(text)
    if not text:
        return []
    pieces = []
    for p in re.split(r"\n\s*\n", text):
        p = p.strip()
        if not p:
            continue
        pieces.extend(_split_long(p, max_chars) if len(p) > max_chars else [p])
    chunks, cur = [], ""
    for p in pieces:
        if cur and len(cur) + 2 + len(p) > max_chars:
            chunks.append(cur)
            cur = p
        else:
            cur = (cur + "\n\n" + p).strip()
    if cur:
        chunks.append(cur)
    if len(chunks) > 1 and len(chunks[-1]) < min_chars and len(chunks[-2]) + 2 + len(chunks[-1]) <= max_chars:
        chunks[-2] = chunks[-2] + "\n\n" + chunks[-1]
        chunks.pop()
    return chunks


def plan_chunks(n_chunks, n_questions):
    """
    One chunk index per question, spread over the whole text and in text order.
    More questions than chunks -> chunks are reused (the 'avoid' list keeps the questions different).
    """
    if n_chunks <= 0 or n_questions <= 0:
        return []
    if n_questions >= n_chunks:
        base = list(range(n_chunks))
        plan = [base[i % n_chunks] for i in range(n_questions)]
        return sorted(plan)
    step = n_chunks / n_questions
    return [min(n_chunks - 1, int(i * step + step / 2)) for i in range(n_questions)]


def detect_language(text):
    """'vi' or 'en' (same rule the chat uses)."""
    try:
        from utils import persona
    except Exception:
        try:
            import persona
        except Exception:
            persona = None
    if persona is not None:
        return persona.detect_language(text[:3000], None)
    return "vi" if re.search(r"[ăâêôơưđ]", (text or "").lower()) else "en"


# =============================================================================
# Prompt / parsing / validation
# =============================================================================
def build_messages(chunk, lang, avoid=()):
    avoid_txt = ""
    if avoid:
        avoid_txt = ("Questions already written (ask about something different):\n"
                     + "\n".join(f"- {q}" for q in list(avoid)[-6:]) + "\n\n")
    system = SYSTEM_PROMPT.format(language=_LANG_NAME.get(lang, "English"))
    user = f"Passage:\n{chunk}\n\n{avoid_txt}Write the question now."
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def parse_question(content):
    """Pull the JSON object out of the model text. Returns a raw dict or None."""
    if not content:
        return None
    m = re.search(r"\{.*\}", content, re.DOTALL)
    if not m:
        return None
    try:
        data = json.loads(m.group(0))
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    wrong = data.get("wrong_answers")
    if not (isinstance(wrong, list) and len(wrong) == 3):
        return None
    try:
        return {
            "question": str(data["question"]).strip(),
            "correct_answer": str(data["correct_answer"]).strip(),
            "wrong_answers": [str(w).strip() for w in wrong],
            "explanation": str(data.get("explanation", "")).strip(),
        }
    except Exception:
        return None


def _fold(s):
    s = (s or "").replace("đ", "d").replace("Đ", "D")
    s = unicodedata.normalize("NFD", s.lower())
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


def _tokens(s):
    return _WORD.findall(_fold(s))


def is_grounded(q, chunk, min_ratio=GROUNDING_MIN_RATIO):
    """Cheap anti-hallucination test: the correct answer's content must appear in the passage."""
    chunk_tokens = set(_tokens(chunk))
    ans = _tokens(q["correct_answer"])
    nums = [t for t in ans if t.isdigit()]
    if any(n not in chunk_tokens for n in nums):
        return False
    words = [t for t in ans if len(t) >= 3 and not t.isdigit()]
    if not words:                                   # e.g. a short number/symbol answer
        return bool(nums) or _fold(q["correct_answer"]) in _fold(chunk)
    hit = sum(1 for t in words if t in chunk_tokens)
    return hit / len(words) >= min_ratio


def validate_question(q, chunk):
    """Return a cleaned raw dict, or None if it must be rejected."""
    if not q:
        return None
    question = q["question"].strip()
    options = [q["correct_answer"].strip()] + [w.strip() for w in q["wrong_answers"]]
    if not (8 <= len(question) <= 300):
        return None
    if any(not (1 <= len(o) <= 160) for o in options):
        return None
    folded = [_fold(o).strip() for o in options]
    if len(set(folded)) != 4:                       # duplicates / wrong answer equals the right one
        return None
    if any(_BAD_OPTION.search(o) for o in options):
        return None
    if not is_grounded(q, chunk):
        return None
    return {"question": question, "correct_answer": options[0], "wrong_answers": options[1:],
            "explanation": q.get("explanation", "")[:300]}


def finalize_question(q, rng=None):
    """Shuffle the 4 options; the stored question knows the index of the right one."""
    rng = rng or random
    options = [q["correct_answer"]] + list(q["wrong_answers"])
    order = list(range(4))
    rng.shuffle(order)
    shuffled = [options[i] for i in order]
    return {"q": q["question"], "options": shuffled, "answer": order.index(0),
            "explanation": q["explanation"]}


def reshuffle_quiz(questions, rng=None):
    """For 'Try again': same questions, new option order."""
    rng = rng or random
    out = []
    for item in questions:
        right = item["options"][item["answer"]]
        opts = list(item["options"])
        rng.shuffle(opts)
        out.append({"q": item["q"], "options": opts, "answer": opts.index(right),
                    "explanation": item.get("explanation", "")})
    return out


# =============================================================================
# Talking to the local llama-server
# =============================================================================
_working_method = {"name": None}      # remembers which JSON-constraint style the server accepts


def _post(port, payload, timeout):
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def request_question(port, chunk, lang, avoid=(), timeout=REQUEST_TIMEOUT_SECONDS, temperature=TEMPERATURE):
    """One model call -> raw parsed dict (not yet validated) or None. Never raises."""
    base = {"messages": build_messages(chunk, lang, avoid), "temperature": temperature,
            "max_tokens": MAX_TOKENS, "cache_prompt": True}
    attempts = [
        ("response_format", {"response_format": {"type": "json_schema",
                                                 "json_schema": {"name": "quiz_item", "schema": SCHEMA}}}),
        ("json_schema", {"json_schema": SCHEMA}),
        ("unconstrained", {}),
    ]
    if _working_method["name"]:                      # try the style that worked before first
        attempts.sort(key=lambda a: a[0] != _working_method["name"])
    for name, extra in attempts:
        try:
            res = _post(port, {**base, **extra}, timeout)
            content = res["choices"][0]["message"]["content"]
        except Exception:
            continue
        parsed = parse_question(content)
        if parsed:
            _working_method["name"] = name
            return parsed
    return None


def generate_quiz(port, text, n_questions=DEFAULT_QUESTIONS, lang=None, cancel=None,
                  on_progress=None, rng=None, timeout=REQUEST_TIMEOUT_SECONDS):
    """
    BLOCKING. Returns (questions, info).
      questions: list of {"q", "options"[4], "answer"(0-3), "explanation"}
      info: {"lang", "requested", "made", "skipped", "cancelled", "seconds"}
    on_progress(done, total) is called from this thread after every finished question
    (use window.after(0, ...) inside it). `cancel` is a threading.Event.
    """
    t0 = time.time()
    rng = rng or random.Random()
    text = clean_source(text)
    lang = lang or detect_language(text)
    chunks = split_chunks(text)
    plan = plan_chunks(len(chunks), n_questions)
    info = {"lang": lang, "requested": len(plan), "made": 0, "skipped": 0, "cancelled": False, "seconds": 0.0}
    questions, asked = [], []
    for i, ci in enumerate(plan):
        if cancel is not None and cancel.is_set():
            info["cancelled"] = True
            break
        chunk = chunks[ci]
        item = None
        for attempt in range(1 + RETRIES_PER_QUESTION):
            if cancel is not None and cancel.is_set():
                info["cancelled"] = True
                break
            temp = TEMPERATURE + 0.2 * attempt            # a little more variety on retries
            raw = request_question(port, chunk, lang, avoid=asked, timeout=timeout, temperature=temp)
            good = validate_question(raw, chunk)
            if good and _fold(good["question"]) not in {_fold(a) for a in asked}:
                item = good
                break
        if info["cancelled"]:
            break
        if item is None:
            info["skipped"] += 1
        else:
            asked.append(item["question"])
            questions.append(finalize_question(item, rng))
        if on_progress:
            try:
                on_progress(i + 1, len(plan))
            except Exception:
                pass
    info["made"] = len(questions)
    info["seconds"] = round(time.time() - t0, 1)
    return questions, info


# =============================================================================
# Scoring + save-file library (stored in AppState.settings, like weekly_checkin)
# =============================================================================
def score_quiz(questions, answers):
    """answers: list of chosen option indices (None = unanswered). Returns (correct, total)."""
    correct = sum(1 for q, a in zip(questions, answers) if a is not None and a == q["answer"])
    return correct, len(questions)


def get_library(settings):
    data = settings.get(SETTINGS_KEY) if isinstance(settings, dict) else None
    return [r for r in data if isinstance(r, dict) and r.get("questions")] if isinstance(data, list) else []


def make_title(user_title, text):
    t = (user_title or "").strip()
    if not t:
        first = clean_source(text).split("\n", 1)[0]
        t = first[:40].rstrip(" .,;:-") or "Untitled quiz"
    return t[:60]


def add_to_library(settings, set_setting, title, questions, lang, now=None):
    """Save a quiz; returns its id. set_setting(key, value) is AppState.set_setting (it also saves the file)."""
    lib = get_library(settings)
    rec = {"id": uuid.uuid4().hex[:10], "title": title, "lang": lang,
           "created": (now or datetime.now()).strftime("%Y-%m-%d"),
           "questions": questions, "best_score": None, "attempts": 0}
    lib.append(rec)
    lib = lib[-MAX_LIBRARY:]
    set_setting(SETTINGS_KEY, lib)
    return rec["id"]


def record_attempt(settings, set_setting, quiz_id, correct, total):
    lib = get_library(settings)
    for r in lib:
        if r["id"] == quiz_id:
            r["attempts"] = int(r.get("attempts", 0)) + 1
            best = r.get("best_score")
            r["best_score"] = correct if best is None else max(int(best), correct)
            r["total"] = total
            set_setting(SETTINGS_KEY, lib)
            return True
    return False


def delete_from_library(settings, set_setting, quiz_id):
    lib = get_library(settings)
    new = [r for r in lib if r["id"] != quiz_id]
    if len(new) != len(lib):
        set_setting(SETTINGS_KEY, new)
        return True
    return False
