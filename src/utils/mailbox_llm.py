"""
AI-assisted scoring of a Stress-Mailbox letter.

The local model rates the letter on the 7 DASS-21 stress items (0-3 each, same scale as the quiz);
score = sum * 2 (0-42). That score is BLENDED with the keyword score (default 3:2 keyword:AI).
If the AI is unavailable or returns junk, the keyword score is used alone.
Crisis detection stays with the keyword analyzer (the AI can only ADD a flag, never remove one).
"""

import json
import re
import time
import urllib.error
import urllib.request

# ---- tunables ---------------------------------------------------------------
WEIGHT_KEYWORD = 0.6          # 3 : 2
WEIGHT_AI = 0.4
LETTER_MAX_CHARS = 1200       # longer letters: first 900 + last 300 chars go to the model
AI_CAN_RAISE_CRISIS = True    # model's "self_harm" flag is OR-ed with the keyword flag
WAIT_READY_SECONDS = 45       # how long to wait for a still-loading server
REQUEST_TIMEOUT_SECONDS = 40  # one rating request

SYSTEM_PROMPT = (
    "You read a short personal letter and rate how strongly it shows each of 7 stress signs during the recent past. "
    "Scale for each item: 0 = no sign at all, 1 = a little or sometimes, 2 = often or clearly, 3 = very strongly or almost always. "
    "Rate ONLY what the letter actually expresses and give 0 when there is no evidence. "
    "Everyday tiredness or one busy day is 0 or 1; use 2 or 3 only for clear, repeated or intense distress. "
    "The letter may be in English or Vietnamese, with or without accents. "
    "Set \"self_harm\" to true only if the letter mentions wanting to die or hurting oneself. "
    "Reply with JSON only, in the form {\"items\": [n1, n2, n3, n4, n5, n6, n7], \"self_harm\": false}, "
    "one integer 0-3 per item in this order:\n"
    "1. Found it hard to wind down\n"
    "2. Tended to over-react to situations\n"
    "3. Felt that I was using a lot of nervous energy\n"
    "4. Found myself getting agitated\n"
    "5. Found it difficult to relax\n"
    "6. Was intolerant of anything that kept me from getting on with what I was doing\n"
    "7. Felt that I was rather touchy"
)

SCHEMA = {
    "type": "object",
    "properties": {
        "items": {"type": "array", "items": {"type": "integer", "minimum": 0, "maximum": 3},
                  "minItems": 7, "maxItems": 7},
        "self_harm": {"type": "boolean"},
    },
    "required": ["items", "self_harm"],
    "additionalProperties": False,
}


def prepare_letter(text, max_chars=LETTER_MAX_CHARS):
    t = (text or "").strip()
    if len(t) <= max_chars:
        return t
    head = int(max_chars * 0.75)
    return t[:head] + " ... " + t[-(max_chars - head):]


def _post(port, payload, timeout):
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _parse(content):
    """Extract {"items":[7 ints 0-3], "self_harm": bool} from model text, or None."""
    if not content:
        return None
    m = re.search(r"\{.*\}", content, re.DOTALL)
    if not m:
        return None
    try:
        data = json.loads(m.group(0))
        items = data["items"]
        if not (isinstance(items, list) and len(items) == 7):
            return None
        items = [int(x) for x in items]
        if any(x < 0 or x > 3 for x in items):
            return None
        return {"items": items, "self_harm": bool(data.get("self_harm", False))}
    except Exception:
        return None


def rate_letter(port, letter_text, timeout=REQUEST_TIMEOUT_SECONDS):
    """Ask the local model to rate the letter. Returns a dict or None (never raises)."""
    base = {
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prepare_letter(letter_text)},
        ],
        "temperature": 0,
        "max_tokens": 70,
    }
    attempts = [
        ("response_format", {"response_format": {"type": "json_schema",
                                                 "json_schema": {"name": "rating", "schema": SCHEMA}}}),
        ("json_schema", {"json_schema": SCHEMA}),
        ("unconstrained", {}),
    ]
    for method, extra in attempts:
        try:
            res = _post(port, {**base, **extra}, timeout)
            content = res["choices"][0]["message"]["content"]
        except Exception:
            continue
        parsed = _parse(content)
        if parsed:
            parsed["score"] = float(sum(parsed["items"]) * 2)
            parsed["method"] = method
            return parsed
    return None


def blend_scores(keyword_score, ai_score, keyword_crisis=False,
                 w_kw=WEIGHT_KEYWORD, w_ai=WEIGHT_AI):
    blended = (w_kw * float(keyword_score) + w_ai * float(ai_score)) / (w_kw + w_ai)
    if keyword_crisis:
        blended = max(blended, float(keyword_score))   # the AI can never lower a crisis floor
    return round(max(0.0, min(42.0, blended)), 1)


def analyze_letter(letter_text, keyword_fn, model_manager=None,
                   wait_ready_s=WAIT_READY_SECONDS, request_timeout_s=REQUEST_TIMEOUT_SECONDS):
    """
    keyword_fn(text) -> (score 0-42, crisis_bool)   (stress_diagnosis.analyze_mailbox)
    model_manager: object with .port and .wait_until_ready(timeout); None = keywords only.
    Returns (score, crisis, info). BLOCKING: call from a background thread.
    """
    kw_score, kw_crisis = keyword_fn(letter_text)
    info = {"used_ai": False, "keyword_score": kw_score, "ai_score": None, "reason": None, "seconds": 0.0}
    t0 = time.time()
    try:
        if model_manager is None:
            info["reason"] = "no_ai"
            return kw_score, kw_crisis, info
        if getattr(model_manager, "ai_unavailable", False):
            info["reason"] = "unavailable"
            return kw_score, kw_crisis, info
        if not model_manager.wait_until_ready(wait_ready_s):
            info["reason"] = "not_ready"
            return kw_score, kw_crisis, info
        rated = rate_letter(model_manager.port, letter_text, request_timeout_s)
        if rated is None:
            info["reason"] = "bad_output"
            return kw_score, kw_crisis, info
        info.update(used_ai=True, ai_score=rated["score"], method=rated["method"], items=rated["items"])
        crisis = bool(kw_crisis or (AI_CAN_RAISE_CRISIS and rated["self_harm"]))
        score = blend_scores(kw_score, rated["score"], kw_crisis)
        return score, crisis, info
    except Exception as e:
        info["reason"] = f"error: {type(e).__name__}"
        return kw_score, kw_crisis, info
    finally:
        info["seconds"] = round(time.time() - t0, 1)
