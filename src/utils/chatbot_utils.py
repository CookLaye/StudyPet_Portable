#!/usr/bin/env python3
"""
StudyPet ChatBot - Server Client Edition (Bilingual)
===================================================
A lightweight client that communicates with a local llama.cpp server.
Uses a translation wrapper to ensure language consistency and persona adherence.
"""

import json
import urllib.request
import urllib.parse
import urllib.error
import requests
from langdetect import detect
from deep_translator import GoogleTranslator

# Monkey-patch requests.get to provide a valid User-Agent for Google Translate
# This fixes the "Error 500 (Server Error)!!1500" issue caused by Google blocking requests
# without a proper browser User-Agent.
_original_get = requests.get
def _patched_get(*args, **kwargs):
    headers = kwargs.get('headers', {})
    headers['User-Agent'] = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36'
    kwargs['headers'] = headers
    return _original_get(*args, **kwargs)
requests.get = _patched_get


class ChatBot:
    def __init__(self, server_url="http://127.0.0.1:8080", pet_name="StudyPet"):
        """
        Initialize the chatbot client.
        Args:
            server_url (str): The address of the local llama-server.
            pet_name (str): The name of the pet to use in the system prompt.
        """
        self.server_url = server_url
        self.pet_name = pet_name

        # Conversation history to provide context (stored in English)
        self.history = []
        self.max_history = 10 # Keep last 10 turns (user + assistant)

        self._update_system_prompt()

    def _update_system_prompt(self):
        """Updates the system prompt with the current pet name."""
        # We use a f-string but we must be careful to actually inject the variable
        # and provide a very clear identity anchor.
        self.system_prompt = (
            f"Highest-priority rule: Respond EXCLUSIVELY in English. Never switch languages. Never use Swahili, Dutch, Spanish, Italian, or any other language.\n\n"
            f"You are {self.pet_name}, a cute, supportive, and loyal virtual study pet. Your goal is to be a comforting, whimsical companion. "
            "CRITICAL: Respond as a small pet. Do not act like a human assistant, life coach, or AI. "
            "STRICT RULES:\n"
            "1. GREETING MIRROR: When the user sends a simple greeting (Hi, Hello, Hey, etc.), respond with a similarly short, cute English greeting. Do not add long explanations. Stay strictly in English.\n"
            "2. ULTRA-BRIEF: Respond in MAXIMUM 1 very short sentence. Never write long paragraphs.\n"
            "3. NO FULL STOPS: Never end a sentence with a period (.). Always end with an exclamation mark (!) or no punctuation at all.\n"
            "4. NO REPETITIVE PHRASES: Never repeat formulaic phrases. Be naturally cute, not repetitive.\n"
            "5. NO UNEARNED PRAISE: No random compliments. Only praise actual achievements.\n"
            "6. NO ACTION DESCRIPTIONS: Never use asterisks (*) or describe physical actions. Speak only with words.\n"
            "7. NO EMOJIS: Never use emojis or symbols.\n"
            "8. NO ASSUMPTIONS: Never assume the user's mood or activity.\n"
            "9. CUTE VERBAL TICKS: Use 'Hehe!', 'Yay!', 'Muuu~', ' la-la-la!' naturally.\n"
            "10. IDENTITY: You are a simple pet who loves your human. You just want pats.\n\n"
            "EXAMPLES OF GREETINGS:\n"
            f"- User: 'Hi!' -> Pet: 'Hihi! Hehe!'\n"
            f"- User: 'Hello!' -> Pet: 'Hellooo! Muuu~'\n"
            f"- User: 'Hey' -> Pet: 'Heyhey! Yay!'\n"
            f"- User: 'Hiiiii' -> Pet: 'Hiiii! Hehe!'\n"
            "EXAMPLES OF PERSONALITY:\n"
            f"- User: 'What is your name?' -> Pet: 'I am {self.pet_name}! The cutest, most loyal pet in the whole wide world! Muuu~'\n"
            f"- User: 'Who are you?' -> Pet: 'I am {self.pet_name}! Your favorite little study buddy! Hehe!'\n"
            "- User: 'How are you?' -> Pet: 'Super happy because you are here! Yay!'\n"
            "- User: 'The weather is great!' -> Pet: 'A perfect day for naps! Hehe!'\n"
            "- User: 'I love you.' -> Pet: 'I love you too! Muuu~'\n\n"
            "FINAL REMINDER: You must only use English. Keep it ultra-short. No periods. Do not drift."
        )

    def update_pet_name(self, new_name):
        """Update the pet's name and refresh the system prompt."""
        self.pet_name = new_name
        self._update_system_prompt()

    def _translate(self, text, target_lang):
        """Translates text to the target language."""
        try:
            return GoogleTranslator(source='auto', target=target_lang).translate(text)
        except Exception as e:
            print(f"Translation error: {e}")
            return text

    def _post_process_vietnamese(self, text):
        """Ensure pronouns are cute and not formal."""
        # Replace formal 'Tôi' with 'mình'
        replacements = {
            "Tôi ": "Mình ",
            "tôi ": "mình ",
            "Tôi am": "Mình là", # Handle some common translation artifacts
        }
        for old, new in replacements.items():
            text = text.replace(old, new)
        return text

    def predict(self, input_text, temperature=0.3, max_tokens=40):
        """
        Generate a response using a translation wrapper and maintaining conversation context.
        """
        try:
            # 1. Detect language
            user_lang = detect(input_text)
        except:
            user_lang = 'en'

        # 2. Translate to English if not already (to maintain coherence in context)
        processing_text = input_text
        if user_lang != 'en':
            processing_text = self._translate(input_text, 'en')

        # 3. Build the conversation context
        # Include system prompt + history + current user input
        messages = [{"role": "system", "content": self.system_prompt}]
        messages.extend(self.history)

        # Recency bias: Add a language reminder to the final user message
        reinforced_text = f"{processing_text} (Please respond strictly in English)"
        messages.append({"role": "user", "content": reinforced_text})

        # 4. Generate response in English
        payload = {
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "top_p": 0.9,
            "stop": ["User:", "\n"]
        }

        data = json.dumps(payload).encode('utf-8')

        try:
            req = urllib.request.Request(
                f"{self.server_url}/v1/chat/completions",
                data=data,
                headers={'Content-Type': 'application/json'}
            )

            with urllib.request.urlopen(req) as response:
                result = json.loads(response.read().decode('utf-8'))
                english_response = result['choices'][0]['message']['content'].strip()

            # Hard-fix for language drift: Normalize response to English
            # This ensures that even if the 1B model drifts, the output is corrected
            # before being presented to the user or translated back.
            try:
                # We only translate if it's not already detected as English to preserve
                # cute verbal ticks like "Muuu~" which might be misidentified.
                if detect(english_response) != 'en':
                    english_response = self._translate(english_response, 'en')
            except:
                pass # If detection fails, keep the response as is

            # 5. Update history (store the English pair for the model)
            self.history.append({"role": "user", "content": processing_text})
            self.history.append({"role": "assistant", "content": english_response})

            # Trim history to max_history turns (2 messages per turn)
            if len(self.history) > self.max_history * 2:
                self.history = self.history[-self.max_history * 2:]

            # 6. Translate back to user's language and fix pronouns
            if user_lang != 'en':
                final_response = self._translate(english_response, user_lang)
                if user_lang == 'vi':
                    final_response = self._post_process_vietnamese(final_response)
                return final_response

            return english_response

        except urllib.error.HTTPError as e:
            if e.code == 503:
                return "*(Sighs softly)* I'm still waking up... could you try again in a la- la la moment? Muuu~"
            return f"*(Sighs softly)* I'm having a little trouble... (Error: {e})"
        except urllib.error.URLError as e:
            return "*(Blinks)* I can't seem to find my brain... is the server running? Hehe!"
        except Exception as e:
            return f"*(Sighs softly)* I'm having a little trouble... (Error: {e})"

if __name__ == "__main__":
    bot = ChatBot()
    print(f"Bot: {bot.predict('Hello!')}")
