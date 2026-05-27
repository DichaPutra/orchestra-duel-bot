"""
Decision — kirim state ke LLM, terima action.

Mendukung provider:
- Google Gemini (default)
- OpenRouter
- Groq
"""
import json
import logging
from typing import Optional
import requests

from config import Config

logger = logging.getLogger("md_bot.decision")


def build_prompt(state_text: str) -> str:
    """Gabung system prompt + state terkini."""
    system = Config.load_prompt("system.txt")
    examples = Config.load_prompt("examples.txt")

    parts = []
    if system:
        parts.append(system)
    if examples:
        parts.append(f"\n\n## Contoh\n{examples}")
    parts.append(f"\n\n## STATE SEKARANG\n{state_text}")
    parts.append("\n\nJawab STRICT JSON sesuai format di atas. Gak boleh teks lain.")
    return "\n".join(parts)


def decide_action(state_text: str) -> Optional[dict]:
    """
    Kirim state ke LLM. Return parsed JSON action atau None.
    """
    provider = Config.PROVIDER
    prompt = build_prompt(state_text)

    logger.info("── Decision ──")
    logger.info("State: %s...", state_text[:120])

    if provider == "gemini":
        result = _ask_gemini(prompt)
    elif provider == "openrouter":
        result = _ask_openrouter(prompt)
    elif provider == "groq":
        result = _ask_groq(prompt)
    else:
        logger.error("Provider '%s' gak dikenal", provider)
        return None

    if result is None:
        return None

    return _parse_action(result)


def _ask_gemini(prompt: str) -> Optional[str]:
    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
    payload = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.1,
            "response_mime_type": "application/json",
        }
    }
    try:
        resp = requests.post(url, params={"key": Config.GEMINI_KEY}, json=payload, timeout=15)
        data = resp.json()
        return data["candidates"][0]["content"]["parts"][0]["text"]
    except Exception as e:
        logger.error("Gemini error: %s", e)
        return None


def _ask_openrouter(prompt: str) -> Optional[str]:
    try:
        resp = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {Config.OPENROUTER_KEY}"},
            json={
                "model": Config.OPENROUTER_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.1,
            },
            timeout=15,
        )
        return resp.json()["choices"][0]["message"]["content"]
    except Exception as e:
        logger.error("OpenRouter error: %s", e)
        return None


def _ask_groq(prompt: str) -> Optional[str]:
    try:
        resp = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {Config.GROQ_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": Config.GROQ_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.1,
                "response_format": {"type": "json_object"},
            },
            timeout=15,
        )
        return resp.json()["choices"][0]["message"]["content"]
    except Exception as e:
        logger.error("Groq error: %s", e)
        return None


def _parse_action(raw: str) -> Optional[dict]:
    """Parse JSON dari response LLM. Bersihin noise kalo ada."""
    try:
        # Coba parse langsung
        return json.loads(raw)
    except json.JSONDecodeError:
        # Cari JSON di dalam teks (kalo ada markdown wrapper)
        import re
        match = re.search(r"\{[^}]+\}", raw, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
        logger.error("Gagal parse action: %s", raw[:200])
        return None
