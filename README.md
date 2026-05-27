# Yu-Gi-Oh! Master Duel Bot — Hybrid Memory + LLM Vision

Bot untuk farming solo mode (vs AI) di Yu-Gi-Oh! Master Duel.
Decision making pakai LLM (Gemini / OpenRouter).

> ⚠️ Peringatan: Bot ini cuma untuk solo mode / vs AI. Resiko sendiri kalo dipake di Ranked/PvP.

---

## Arsitektur

**Dua opsi approach:**

### Opsi A — Vision-only (cross-platform)
Baca state game dari screenshot pake Gemini Vision API.
Klik mouse di koordinat yang sudah ditentukan.
Work di Windows & macOS.

### Opsi B — Memory Hacking (Windows, recommended)
Baca LP, Phase, Turn langsung dari memory game process via `ReadProcessMemory`.
Vision cuma dipanggil pas ada perubahan state kartu (bukan tiap iterasi).
**~70% lebih sedikit vision calls → 2-3x lebih cepat.**

```
┌─────────────────────┐
│  Memory Reader      │ ← LP, Phase, Turn (gratis, < 1ms)
│  (ReadProcessMemory)│
└────────┬────────────┘
         │ cuma kalo state berubah
         ▼
┌─────────────────────┐
│  Vision (Gemini)    │ ← Baca state kartu (hand, field, GY)
└────────┬────────────┘
         ▼
┌─────────────────────┐
│  LLM Decision       │ ← Action JSON
└────────┬────────────┘
         ▼
┌─────────────────────┐
│  Input (Click)      │ ← Mouse click simulation
└─────────────────────┘
```

### ZMQ Server Architecture

Bot punya ZMQ server (port 5555) yang kompatibel dengan protocol JDuelBotClient.
Bisa dipake dari script Python terpisah, atau jalan standalone dengan bot built-in.

---

## Quick Start (Windows)

```bash
# Masuk ke folder orchestra-bot
cd orchestra-bot

# Install dependencies
pip install -r requirements.txt

# Setup API key
cp .env.example .env
# Isi GEMINI_API_KEY di .env

# Buka Master Duel (1280x720, window mode, dalam duel)
# Auto-calibrate memory addresses (sekali aja)
python auto_calibrate.py --save

# Jalanin bot
python main.py

# Atau double-click run_bot.bat
```

## Quick Start (macOS — vision only)

```bash
cd orchestra-bot
pip install -r requirements.txt
cp .env.example .env
# Isi GEMINI_API_KEY
python main.py
```

---

## Project Structure

```
yugioh-md-bot/
├── orchestra-bot/           # ← Actual bot code
│   ├── main.py              # Entry point (server / standalone)
│   ├── orchestra_server.py  # ZMQ server (hybrid memory + vision)
│   ├── memory_reader.py     # Opsi B: Windows memory reader
│   ├── memory_scanner.py    # Opsi B: AOB pattern scanner
│   ├── memory_state.py      # Opsi B: Hybrid state reader
│   ├── capture.py           # Screenshot (DXCam/mss)
│   ├── vision.py            # Gemini Vision API
│   ├── input.py             # Mouse click simulation
│   ├── window.py            # Window finder (cross-platform)
│   ├── auto_calibrate.py    # One-click memory calibration
│   ├── jduel_bot/           # JDuelBotClient (opensource)
│   ├── bots/
│   │   ├── self_burn.py     # Example bot: activate burn + end turn
│   │   └── ...              # Add your own bot scripts
│   ├── .env.example
│   ├── requirements.txt
│   └── run_bot.bat          # Double-click to run (Windows)
├── README.md
├── .gitignore
└── ...old skeleton files
```

---

## Opsi LLM Provider

| Provider | Model | Setup |
|----------|-------|-------|
| Google Gemini | `gemini-2.5-flash` | API Key dari Google AI Studio (gratis 1.500 req/hari) |
| OpenRouter | `deepseek/deepseek-v4-flash` | API Key + top up minimal $1 |

---

## Memory Hacking (Opsi B) Details

- **Teknik:** `ReadProcessMemory` via ctypes — read-only, no injection
- **Data yang dibaca:** LP (self+opponent), Phase, Turn flag, Hand count
- **Pattern scanning:** Cari nilai 8000 (LP awal) di process memory → cari Phase & Turn di sekitarnya
- **Fallback:** Otomatis pindah ke vision-only kalo memory gagal
- **Anti-cheat:** Aman — gak inject, gak write memory, gak touch game code

Jalanin `python auto_calibrate.py` sekali setelah update game untuk scan ulang offsets.

---

## Konfigurasi Deck

Edit `prompts/system.txt` di repo root — deskripsi deck, kombo utama, strategi.

Contoh:
```
Deck: Tenpai Dragon
Goal: OTK di Battle Phase
Kombo: Sangen Summoning → Genroku → Kaimen → Seals → Transcendent → battle
Prioritas: Jangan pernah negasi Maxx C sendiri
```

---

## Catatan

- **Bot ini membaca layar (vision) + memory (read-only)** — gak nyentuh game code.
  Resiko banned minimal untuk solo farming.
- **10.000+ kartu** — LLM butuh deskripsi deck yang jelas.
  Semakin detail system prompt, semakin bagus keputusan LLM.
- **Chain timing** — Bot detect chain prompt via mouse click positions,
  bukan fitur anti-cheat memory.
