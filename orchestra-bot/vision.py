"""
Vision — baca state game dari screenshot pake LLM Vision.
"""
import base64
import io
import logging
from typing import Optional
from PIL import Image

logger = logging.getLogger("orchestra.vision")

# Default Gemini (gratis 1500 req/hari)
GEMINI_KEY = ""
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"


def set_api_key(key: str):
    global GEMINI_KEY
    GEMINI_KEY = key


def get_board_state(screenshot: Image.Image) -> Optional[dict]:
    """
    Kirim screenshot ke Gemini Vision.
    Return dict: {hand, field_monsters, field_spells, gy, lp, phase, enemy}
    Atau None kalo gagal.
    """
    if not GEMINI_KEY:
        logger.error("Gemini API key not set. Call vision.set_api_key() first.")
        return None

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
        "Example: {\"CARDS_IN_HAND\": [\"Maxx C\", \"Ash Blossom\"], "
        "\"MY_MONSTERS\": [], \"MY_SPELLS_TRAPS\": [], "
        "\"MY_GRAVEYARD\": [], \"MY_LP\": 8000, "
        "\"OPPONENT_LP\": 8000, \"OPPONENT_MONSTERS\": 0, "
        "\"OPPONENT_SPELLS_TRAPS\": 0, \"CURRENT_PHASE\": \"Main 1\", "
        "\"IS_MY_TURN\": true, \"DUEL_ENDED\": false}"
    )

    url = f"{GEMINI_URL}?key={GEMINI_KEY}"
    import requests
    try:
        resp = requests.post(url, json={
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
        }, timeout=15)
        data = resp.json()
        text = data["candidates"][0]["content"]["parts"][0]["text"]
        import json
        return json.loads(text)
    except Exception as e:
        logger.error("Vision LLM error: %s", e)
        return None
