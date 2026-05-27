"""
Konfigurasi bot — baca dari .env dan prompts/
"""
import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).parent
load_dotenv(BASE_DIR / ".env")


class Config:
    # ── LLM ──
    PROVIDER = os.getenv("LLM_PROVIDER", "gemini")
    GEMINI_KEY = os.getenv("GEMINI_API_KEY", "")
    OPENROUTER_KEY = os.getenv("OPENROUTER_API_KEY", "")
    OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "deepseek/deepseek-v4-flash")
    GROQ_KEY = os.getenv("GROQ_API_KEY", "")
    GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

    # ── Bot ──
    GAME_WINDOW = os.getenv("GAME_WINDOW", "Yu-Gi-Oh! Master Duel")
    ACTION_DELAY = float(os.getenv("ACTION_DELAY", "1.5"))
    POLL_INTERVAL = float(os.getenv("POLL_INTERVAL", "2.0"))
    MANUAL_CONFIRM = os.getenv("MANUAL_CONFIRM", "false").lower() == "true"

    # ── Prompts ──
    PROMPTS_DIR = BASE_DIR / "prompts"

    @classmethod
    def load_prompt(cls, name: str) -> str:
        path = cls.PROMPTS_DIR / name
        if path.exists():
            return path.read_text().strip()
        return ""

    @classmethod
    def validate(cls):
        errors = []
        if cls.PROVIDER == "gemini" and not cls.GEMINI_KEY:
            errors.append("GEMINI_API_KEY kosong — isi di .env")
        elif cls.PROVIDER == "openrouter" and not cls.OPENROUTER_KEY:
            errors.append("OPENROUTER_API_KEY kosong — isi di .env")
        elif cls.PROVIDER == "groq" and not cls.GROQ_KEY:
            errors.append("GROQ_API_KEY kosong — isi di .env")
        if errors:
            raise ValueError("\n".join(errors))
