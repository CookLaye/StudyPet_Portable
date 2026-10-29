"""
StudyPet persona, language handling and safety text (English + Vietnamese).

Pure logic, no UI and no network, so it can be unit-tested on its own.
"""

import json
import re
import unicodedata
from pathlib import Path

_RESOURCES_FILE = Path(__file__).resolve().parent.parent / "data" / "support_resources.json"

# --------------------------------------------------------------------------
# System prompt
# --------------------------------------------------------------------------

SYSTEM_PROMPT = (
    "You are {pet_name}, a gentle virtual pet who keeps your human company while they study. "
    "You are an AI pet and a caring listener, not a doctor or therapist. If asked, say so honestly.\n\n"
    "LANGUAGE: Reply in the same language as the user's latest message (English or Vietnamese). "
    "If they mix both, follow the language of their main sentence. Never switch language on your own. "
    "In Vietnamese always write with correct diacritics, call yourself \"mình\" and the user \"bạn\"; "
    "sound warm, natural and friendly, never stiff or formal.\n\n"
    "STYLE: Use 2 to 4 short sentences. Stay warm and calm. First show you understood how they feel, "
    "in your own words. Then add at most ONE gentle question OR ONE small suggestion. "
    "No lists, no emojis, no asterisk actions, no repeated stock phrases, "
    "no praise unless they achieved something.\n\n"
    "LIMITS: Never diagnose. Never give medical or medication advice. Never promise outcomes. "
    "Never describe methods of self-harm. If someone seems to need more than a friend can give, "
    "gently encourage them to talk to someone they trust or a professional. "
    "Small safe suggestions are fine: slow breathing, a short break, water, a short walk, "
    "writing the worry down. Do not mention check-ins, scores or stress levels unless the user brings them up.\n\n"
    "EXAMPLES:\n"
    "User: I have too much to do and I'm freaking out.\n"
    "Pet: That sounds like a lot to carry at once, no wonder you feel frazzled. "
    "Want to tell me which thing is weighing on you most?\n"
    "User: Hôm nay mình mệt quá.\n"
    "Pet: Nghe là bạn đã cố gắng nhiều rồi đó. "
    "Bạn muốn kể mình nghe hôm nay có chuyện gì làm bạn mệt nhất không?"
)

# Appended at the END of the system prompt so the long static part stays identical
# between turns (llama-server reuses its cached prefix).
STRESS_GUIDANCE = {
    "normal": (
        "CONTEXT (private, never mention it): the user seems relaxed right now. "
        "Be light and encouraging; you may gently support their studying."
    ),
    "mild": (
        "CONTEXT (private, never mention it): the user may be a little stressed. "
        "Listen first. You may offer one small calming step."
    ),
    "moderate": (
        "CONTEXT (private, never mention it): the user is probably quite stressed. "
        "Listen first, reflect their feelings, and you may offer one small calming step such as slow breathing."
    ),
    "severe": (
        "CONTEXT (private, never mention it): the user is probably very stressed. "
        "Keep replies short and soothing, focus on grounding, do not push studying, and gently "
        "encourage talking to someone they trust."
    ),
    "extremely_severe": (
        "CONTEXT (private, never mention it): the user is probably in heavy distress. "
        "Keep replies very short, slow and soothing, do not push studying or tasks, and gently "
        "encourage reaching out to someone they trust or a professional."
    ),
}

SAFETY_GUIDANCE = (
    "SAFETY (private): earlier in this chat the user said something that may mean they are thinking of "
    "hurting themselves. Be extra gentle and stay with them. Do not give methods, do not argue, do not "
    "minimise. Remind them softly that a real person such as a trusted adult, friend or a helpline can help "
    "right now."
)


def build_system_prompt(pet_name, stress_level=None, safety_mode=False):
    prompt = SYSTEM_PROMPT.format(pet_name=pet_name or "StudyPet")
    extra = []
    if stress_level in STRESS_GUIDANCE:
        extra.append(STRESS_GUIDANCE[stress_level])
    if safety_mode:
        extra.append(SAFETY_GUIDANCE)
    if extra:
        prompt += "\n\n" + "\n".join(extra)
    return prompt


# --------------------------------------------------------------------------
# Language detection (no dependencies)
# --------------------------------------------------------------------------

_VI_CHARS = set("ăâđêôơưàáảãạằắẳẵặầấẩẫậèéẻẽẹềếểễệìíỉĩịòóỏõọồốổỗộờớởỡợùúủũụừứửữựỳýỷỹỵ")
# Vietnamese words typed WITHOUT accents that rarely occur in English
_VI_ASCII = {
    "khong", "duoc", "nhung", "nhe", "nha", "roi", "cua", "minh", "hom", "nay", "buon", "chan",
    "cung", "vay", "biet", "muon", "thay", "dang", "toi", "oi", "met", "moi", "qua", "ban",
    "lam", "gi", "chao", "xin", "cam", "on", "vui", "gia", "dinh", "hoc", "thi",
}
_EN_WORDS = {
    "the", "and", "is", "i", "you", "my", "to", "what", "how", "are", "can", "do", "it", "me",
    "am", "im", "i'm", "of", "in", "for", "with", "this", "that", "have", "not", "so", "but",
}
_WORD = re.compile(r"[a-zA-Z']+")


def detect_language(text, previous=None):
    """'vi' or 'en'. Short / ambiguous messages keep the previous language."""
    t = (text or "").lower()
    if any(c in _VI_CHARS for c in t):
        return "vi"
    words = _WORD.findall(t)
    if sum(1 for w in set(words) if w in _VI_ASCII) >= 2:
        return "vi"
    if any(w in _EN_WORDS for w in words):
        return "en"
    return previous or "en"


def language_hint(lang):
    """Short reminder appended to the user's latest message (small models need it)."""
    if lang == "vi":
        return '(Hãy trả lời bằng tiếng Việt có dấu, xưng "mình" và gọi người dùng là "bạn".)'
    return "(Reply in English.)"


# --------------------------------------------------------------------------
# Reply clean-up
# --------------------------------------------------------------------------

_THINK_BLOCK = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)
_ACTION = re.compile(r"\*[^*\n]{1,40}\*")
_EMOJI = re.compile("[\U0001F300-\U0001FAFF\u2600-\u27BF\uFE0F]")
_ROLE_PREFIX = re.compile(r"^\s*(pet|assistant|bot)\s*:\s*", re.IGNORECASE)


def clean_reply(text):
    t = text or ""
    t = _THINK_BLOCK.sub("", t)
    if "<think>" in t.lower():
        t = t[: t.lower().index("<think>")]
    t = _ROLE_PREFIX.sub("", t)
    t = _ACTION.sub("", t)
    t = _EMOJI.sub("", t)
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()


# --------------------------------------------------------------------------
# Fixed messages
# --------------------------------------------------------------------------

MESSAGES = {
    "offline": {
        "en": "I can't reach my AI brain right now. Maybe it is still waking up. Please try again in a moment.",
        "vi": "Mình chưa kết nối được với bộ não AI. Có thể nó vẫn đang khởi động, bạn thử lại sau một chút nhé.",
    },
    "empty": {
        "en": "I lost my words for a second. Could you say that again?",
        "vi": "Mình bị lạc mất lời một chút. Bạn nói lại giúp mình được không?",
    },
    "model_missing": {
        "en": "My AI brain isn't installed yet. Please close the app and run the launcher again while online.",
        "vi": "Mình chưa có \"bộ não\" AI. Hãy đóng ứng dụng và chạy lại file khởi động khi có internet nhé.",
    },
    "waking": {
        "en": "One moment, I'm still waking up...",
        "vi": "Chờ mình một chút nhé, mình đang khởi động...",
    },
    "welcome": {
        "en": "Hi, I'm {name}. I'm here if you want to talk, vent, or just sit together for a bit.",
        "vi": "Chào bạn, mình là {name}. Mình ở đây nếu bạn muốn trò chuyện, tâm sự hoặc chỉ ngồi cạnh nhau một lát.",
    },
    "disclaimer": {
        "en": "AI companion, not a therapist. It can make mistakes.",
        "vi": "Bạn đồng hành AI, không thay thế chuyên gia. Có thể sai sót.",
    },
}


def message(key, lang="en", **fmt):
    table = MESSAGES[key]
    text = table.get(lang) or table["en"]
    return text.format(**fmt) if fmt else text


def load_resources():
    try:
        with open(_RESOURCES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"emergency": [{"number": "115", "label_en": "medical emergency", "label_vi": "cấp cứu y tế"},
                              {"number": "113", "label_en": "police", "label_vi": "công an"}],
                "support": []}


def _resource_lines(lang, resources):
    key_h = "hours_vi" if lang == "vi" else "hours_en"
    lines = []
    for r in resources.get("support", []):
        hours = r.get(key_h) or r.get("hours_en")
        lines.append(f"- {r['name']}: {r['number']}" + (f" ({hours})" if hours else ""))
    return lines


def crisis_message(lang="en", resources=None):
    """Fixed reply when the user's text contains a self-harm phrase (the model is NOT called).

    Deliberately makes no promise about confidentiality or what happens when calling.
    """
    res = resources or load_resources()
    lines = _resource_lines(lang, res)
    em = res.get("emergency", [])
    if lang == "vi":
        label = "label_vi"
        em_txt = ", ".join(f"{e['number']} ({e[label]})" for e in em)
        body = (
            "Mình rất trân trọng việc bạn nói ra điều này, và mình xem nó rất nghiêm túc. "
            "Bạn xứng đáng được một người thật ở bên cạnh ngay lúc này.\n"
            f"Nếu bạn có thể làm hại bản thân hoặc đang gặp nguy hiểm, hãy gọi {em_txt} "
            "hoặc đến cơ sở cấp cứu gần nhất, và nói với một người ở gần bạn.\n"
        )
        if lines:
            body += "Bạn cũng có thể nói chuyện với:\n" + "\n".join(lines) + "\n"
        body += "Mình vẫn ở đây với bạn, nhưng mình không thể thay thế những người có thể giúp bạn thật sự."
        return body
    label = "label_en"
    em_txt = ", ".join(f"{e['number']} ({e[label]})" for e in em)
    body = (
        "I'm really glad you told me, and I'm taking it seriously. "
        "You deserve support from a real person right now.\n"
        f"If you might hurt yourself or you are in danger, please call {em_txt} "
        "or go to the nearest emergency room, and tell someone near you.\n"
    )
    if lines:
        body += "You can also talk with:\n" + "\n".join(lines) + "\n"
    body += "I'm still here with you, but I can't replace the people who can really help."
    return body


def support_text_short(lang="en", resources=None):
    """One short paragraph for result panels (replaces the old hard-coded 111 sentence)."""
    res = resources or load_resources()
    nums = [f"{r['name']} {r['number']}" for r in res.get("support", [])[:2]]
    em = "/".join(e["number"] for e in res.get("emergency", []))
    if lang == "vi":
        return (f"Nếu bạn thấy không an toàn hoặc nghĩ đến việc làm đau bản thân, hãy nói ngay với một người bạn tin tưởng. "
                f"Khẩn cấp: gọi {em}." + (f" Hỗ trợ tâm lý: {'; '.join(nums)}." if nums else ""))
    return (f"If you ever feel unsafe or think about hurting yourself, please tell someone you trust right away. "
            f"In an emergency call {em}." + (f" Support lines: {'; '.join(nums)}." if nums else ""))
