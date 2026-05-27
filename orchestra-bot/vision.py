"""
vision.py — Multi-provider LLM Vision helper.
Supports: Gemini, OpenAI, OpenRouter, and Groq.
"""
import base64
import io
import json
import logging
import re
from typing import Optional
import requests
from PIL import Image

logger = logging.getLogger("orchestra.vision")

# API Keys and configuration
_config = {
    "provider": "gemini",
    "gemini_key": "",
    "openai_key": "",
    "openrouter_key": "",
    "groq_key": "",
    "gemini_model": "gemini-2.5-flash",
    "openai_model": "gpt-4o-mini",
    "openrouter_model": "google/gemini-2.5-flash",
    "groq_model": "llama-3.2-11b-vision-preview",
}


def configure(provider: str, keys: dict, models: dict = None):
    """Set LLM provider, keys, and model overrides."""
    global _config
    _config["provider"] = provider.lower()
    _config.update(keys)
    if models:
        _config.update(models)
    logger.info("Vision configured with provider: %s", _config["provider"])


def get_board_state(screenshot: Image.Image) -> Optional[dict]:
    """
    Send game screenshot to the selected LLM Vision provider to extract board state.
    Returns: dict with board info or None if failed.
    """
    provider = _config["provider"]

    # Convert PIL Image to base64
    buf = io.BytesIO()
    screenshot.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode()

    prompt = (
        "You are a Yu-Gi-Oh! Master Duel state reader. "
        "Read this screenshot and extract the game state.\n\n"
        "Extract:\n"
        "- CARDS_IN_HAND: list of card names I can see in my hand (bottom)\n"
        "- MY_MONSTERS: list of monsters I control with position (face-up/face-down) and ATK/DEF\n"
        "- MY_SPELLS_TRAPS: list of face-up/face-down spell/trap cards I control\n"
        "- MY_GRAVEYARD: list of card names in my GY (bottom-right)\n"
        "- MY_LP: my life points\n"
        "- OPPONENT_LP: opponent's life points\n"
        "- OPPONENT_MONSTERS: number of monsters opponent has + positions\n"
        "- OPPONENT_SPELLS_TRAPS: number of set cards opponent has\n"
        "- CURRENT_PHASE: current phase\n"
        "- IS_MY_TURN: true/false\n"
        "- DUEL_ENDED: true/false (check for win/lose screen)\n\n"
        "Respond with ONLY a JSON object. No other text.\n"
        "Example:\n"
        "{\n"
        "  \"CARDS_IN_HAND\": [\"Maxx C\", \"Ash Blossom\"],\n"
        "  \"MY_MONSTERS\": [],\n"
        "  \"MY_SPELLS_TRAPS\": [],\n"
        "  \"MY_GRAVEYARD\": [],\n"
        "  \"MY_LP\": 8000,\n"
        "  \"OPPONENT_LP\": 8000,\n"
        "  \"OPPONENT_MONSTERS\": 0,\n"
        "  \"OPPONENT_SPELLS_TRAPS\": 0,\n"
        "  \"CURRENT_PHASE\": \"Main 1\",\n"
        "  \"IS_MY_TURN\": true,\n"
        "  \"DUEL_ENDED\": false\n"
        "}"
    )

    if provider == "gemini":
        return _call_gemini(b64, prompt)
    elif provider == "openai":
        return _call_openai(b64, prompt)
    elif provider == "openrouter":
        return _call_openrouter(b64, prompt)
    elif provider == "groq":
        return _call_groq(b64, prompt)
    elif provider == "deepseek":
        logger.error("DeepSeek official API does not support vision (multimodal). "
                     "Please use openrouter, gemini, or openai.")
        return None
    else:
        logger.error("Unsupported vision provider: %s", provider)
        return None


def _clean_json_response(text: str) -> Optional[dict]:
    """Parse JSON and strip any markdown wraps."""
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Try regex search for block in case LLM wrapped it in ```json ... ```
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
        logger.error("Failed to parse JSON response: %s", text[:200])
        return None


def _call_gemini(b64: str, prompt: str) -> Optional[dict]:
    key = _config["gemini_key"]
    model = _config["gemini_model"] or "gemini-2.5-flash"
    if not key:
        logger.error("GEMINI_API_KEY is not set.")
        return None

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
    payload = {
        "contents": [{
            "role": "user",
            "parts": [
                {"inline_data": {"mime_type": "image/png", "data": b64}},
                {"text": prompt}
            ]
        }],
        "generationConfig": {
            "temperature": 0.0,
            "response_mime_type": "application/json"
        }
    }
    try:
        resp = requests.post(url, json=payload, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        text = data["candidates"][0]["content"]["parts"][0]["text"]
        return _clean_json_response(text)
    except Exception as e:
        logger.error("Gemini Vision API error: %s", e)
        return None


def _call_openai(b64: str, prompt: str) -> Optional[dict]:
    key = _config["openai_key"]
    model = _config["openai_model"] or "gpt-4o-mini"
    if not key:
        logger.error("OPENAI_API_KEY is not set.")
        return None

    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": model,
        "response_format": {"type": "json_object"},
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}}
                ]
            }
        ],
        "temperature": 0.0
    }
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        text = data["choices"][0]["message"]["content"]
        return _clean_json_response(text)
    except Exception as e:
        logger.error("OpenAI Vision API error: %s", e)
        return None


def _call_openrouter(b64: str, prompt: str) -> Optional[dict]:
    key = _config["openrouter_key"]
    model = _config["openrouter_model"] or "google/gemini-2.5-flash"
    if not key:
        logger.error("OPENROUTER_API_KEY is not set.")
        return None

    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": model,
        "response_format": {"type": "json_object"},
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}}
                ]
            }
        ],
        "temperature": 0.0
    }
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        text = data["choices"][0]["message"]["content"]
        return _clean_json_response(text)
    except Exception as e:
        logger.error("OpenRouter Vision API error: %s", e)
        return None


def _call_groq(b64: str, prompt: str) -> Optional[dict]:
    key = _config["groq_key"]
    model = _config["groq_model"] or "llama-3.2-11b-vision-preview"
    if not key:
        logger.error("GROQ_API_KEY is not set.")
        return None

    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": model,
        "response_format": {"type": "json_object"},
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}}
                ]
            }
        ],
        "temperature": 0.0
    }
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        text = data["choices"][0]["message"]["content"]
        return _clean_json_response(text)
    except Exception as e:
        logger.error("Groq Vision API error: %s", e)
        return None
