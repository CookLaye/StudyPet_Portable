#!/usr/bin/env python3
"""
StudyPet ChatBot - supportive companion client for the local llama.cpp server.

* Bilingual (English / Vietnamese): replies in the user's language (see persona.py).
* Optional stress context and "safety mode" are added to the system prompt (persona.py).
* predict() returns the whole reply; predict_stream() delivers it token by token.
"""

import json
import urllib.error
import urllib.request

try:
    from . import persona
except ImportError:          # imported as a plain module (script directory on sys.path)
    import persona

CHAT_TEMPERATURE = 0.6
CHAT_TOP_P = 0.9
CHAT_MAX_TOKENS = 160
MAX_HISTORY_TURNS = 10
REQUEST_TIMEOUT = 180


class ChatBot:
    def __init__(self, server_url=None, pet_name="StudyPet"):
        self.server_url = server_url or "http://127.0.0.1:8080"
        self.pet_name = pet_name
        self.history = []                  # [{"role": "user"|"assistant", "content": ...}], clean text only
        self.max_history = MAX_HISTORY_TURNS
        self.stress_level = None           # "normal" | "mild" | "moderate" | "severe" | "extremely_severe" | None
        self.safety_mode = False           # True after the user expressed self-harm thoughts (this session)
        self.language = None               # last detected language of the user ("en" / "vi")

    # ---- configuration -------------------------------------------------------
    @property
    def system_prompt(self):
        return persona.build_system_prompt(self.pet_name, self.stress_level, self.safety_mode)

    def update_pet_name(self, new_name):
        if new_name:
            self.pet_name = new_name

    def set_stress_level(self, level_key):
        self.stress_level = level_key

    def set_safety_mode(self, enabled=True):
        self.safety_mode = bool(enabled)

    # ---- internals -----------------------------------------------------------
    def _prepare(self, input_text):
        lang = persona.detect_language(input_text, self.language)
        self.language = lang
        messages = [{"role": "system", "content": self.system_prompt}]
        messages.extend(self.history)
        messages.append({"role": "user", "content": f"{input_text}\n{persona.language_hint(lang)}"})
        return messages, lang

    def _payload(self, messages, temperature, max_tokens, stream=False):
        payload = {
            "messages": messages,
            "temperature": CHAT_TEMPERATURE if temperature is None else temperature,
            "top_p": CHAT_TOP_P,
            "max_tokens": CHAT_MAX_TOKENS if max_tokens is None else max_tokens,
            "cache_prompt": True,
            "stop": ["\nUser:"],
        }
        if stream:
            payload["stream"] = True
        return payload

    def _remember(self, input_text, reply):
        self.history.append({"role": "user", "content": input_text})
        self.history.append({"role": "assistant", "content": reply})
        limit = self.max_history * 2
        if len(self.history) > limit:
            self.history = self.history[-limit:]

    def _request(self, payload, headers=None):
        return urllib.request.Request(
            f"{self.server_url}/v1/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers=headers or {"Content-Type": "application/json"},
        )

    # ---- public API ----------------------------------------------------------
    def predict(self, input_text, temperature=None, max_tokens=None):
        """Whole reply as a string. Never raises for connection problems (returns a friendly message)."""
        messages, lang = self._prepare(input_text)
        try:
            with urllib.request.urlopen(self._request(self._payload(messages, temperature, max_tokens)),
                                        timeout=REQUEST_TIMEOUT) as resp:
                result = json.loads(resp.read().decode("utf-8"))
            reply = persona.clean_reply(result["choices"][0]["message"]["content"])
        except Exception as e:
            print(f"[ChatBot] request failed: {type(e).__name__}")
            return persona.message("offline", lang)
        if not reply:
            return persona.message("empty", lang)
        self._remember(input_text, reply)
        return reply

    def predict_stream(self, input_text, on_token, cancel=None, temperature=None, max_tokens=None):
        """
        Stream the reply: on_token(text_piece) is called from THIS (worker) thread for each piece.
        `cancel` is an optional threading.Event. Returns the final cleaned reply (also stored in history).
        If streaming cannot start, falls back to predict() and delivers the whole reply in one piece.
        """
        messages, lang = self._prepare(input_text)
        pieces = []
        try:
            req = self._request(self._payload(messages, temperature, max_tokens, stream=True),
                                {"Content-Type": "application/json", "Accept": "text/event-stream"})
            with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
                for raw in resp:
                    if cancel is not None and cancel.is_set():
                        break
                    line = raw.decode("utf-8", "ignore").strip()
                    if not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if data == "[DONE]":
                        break
                    try:
                        delta = json.loads(data)["choices"][0].get("delta", {}).get("content")
                    except Exception:
                        continue
                    if delta:
                        pieces.append(delta)
                        try:
                            on_token(delta)
                        except Exception:
                            pass
        except Exception as e:
            print(f"[ChatBot] stream failed: {type(e).__name__}")
            if not pieces:
                reply = self.predict(input_text, temperature, max_tokens)
                try:
                    on_token(reply)
                except Exception:
                    pass
                return reply
        if cancel is not None and cancel.is_set():
            return persona.clean_reply("".join(pieces))
        reply = persona.clean_reply("".join(pieces))
        if not reply:
            return persona.message("empty", lang)
        self._remember(input_text, reply)
        return reply
