"""
Vision — ekstrak state game dari screenshot.

Dua mode:
1. OCR (EasyOCR) — baca nama kartu & LP dari gambar. Gratis, lokal.
2. LLM Vision — kirim screenshot langsung ke Gemini/LLM. Lebih akurat, bayar per request.
"""
import logging
from typing import Optional
from PIL import Image

from config import Config

logger = logging.getLogger("md_bot.vision")


def extract_state(screenshot: Image.Image, use_llm_vision: bool = True) -> str:
    """
    Extract game state dari screenshot.
    Return text state yang siap dikirim ke LLM decision.

    use_llm_vision=True: kirim screenshot ke LLM Vision → dapet state text.
    use_llm_vision=False: pake OCR lokal (EasyOCR) → lebih murah, kurang akurat.
    """
    if use_llm_vision and Config.PROVIDER == "gemini":
        return _vision_gemini(screenshot)
    elif use_llm_vision and Config.PROVIDER == "openrouter":
        return _vision_openrouter(screenshot)

    # Fallback: OCR lokal
    return _ocr_local(screenshot)


def _vision_gemini(screenshot: Image.Image) -> str:
    """Kirim screenshot ke Gemini Vision — return state sebagai text."""
    import base64, io
    from config import Config

    # Convert PIL Image ke base64
    buf = io.BytesIO()
    screenshot.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode()

    prompt = (
        "Baca state duel Yu-Gi-Oh! Master Duel dari screenshot ini.\n"
        "Extract informasi berikut:\n"
        "- Kartu di hand pemain (nama)\n"
        "- Kartu di field pemain (posisi & nama)\n"
        "- GY pemain\n"
        "- LP kedua pemain\n"
        "- Phase saat ini\n"
        "- Kartu di field lawan (jumlah, posisi face-up/down)\n\n"
        "Format jawab:\n"
        "Hand: [nama kartu, dipisah koma]\n"
        "Field: [nama kartu (posisi)]\n"
        "GY: [nama kartu]\n"
        "LP: [LP kita] vs [LP lawan]\n"
        "Phase: [nama phase]\n"
        "Enemy: [jumlah & posisi kartu lawan]\n\n"
        "Jangan tambah teks lain."
    )

    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
    payload = {
        "contents": [{
            "role": "user",
            "parts": [
                {"inline_data": {"mime_type": "image/png", "data": b64}},
                {"text": prompt}
            ]
        }]
    }
    import requests
    resp = requests.post(url, params={"key": Config.GEMINI_KEY}, json=payload)
    data = resp.json()
    try:
        return data["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError):
        logger.error("Gemini vision gagal: %s", data)
        return "ERROR: vision failed"


def _vision_openrouter(screenshot: Image.Image) -> str:
    """Kirim screenshot ke OpenRouter (Gemini/Claude via API)."""
    import base64, io, requests

    buf = io.BytesIO()
    screenshot.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode()

    prompt = (
        "Kamu adalah state reader Yu-Gi-Oh! Master Duel.\n"
        "Baca screenshot dan extract: hand, field, GY, LP, phase, enemy field.\n"
        "Format: Hand: [...], Field: [...], LP: ..., etc.\n"
        "Jawab text doang, gak perlu markdown."
    )

    resp = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {Config.OPENROUTER_KEY}",
        },
        json={
            "model": Config.OPENROUTER_MODEL,
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}}
                ]
            }]
        }
    )
    data = resp.json()
    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError):
        logger.error("OpenRouter vision gagal: %s", data)
        return "ERROR: vision failed"


def _ocr_local(screenshot: Image.Image) -> str:
    """
    OCR lokal pake EasyOCR.
    Baca: LP, nama kartu, tombol phase.

    NOTE: EasyOCR model ~1GB, lambat di cold start.
    Untuk development, lebih praktis pake LLM Vision dulu.
    """
    try:
        import easyocr
        reader = easyocr.Reader(["en"], gpu=False)
        results = reader.readtext(np.array(screenshot))

        # TODO: Parse OCR results jadi structured state
        # Ini perlu disesuaikan sama layout screen
        texts = [r[1] for r in results]
        return "\n".join(texts)
    except Exception as e:
        logger.error("OCR gagal: %s", e)
        return "ERROR: OCR failed"
