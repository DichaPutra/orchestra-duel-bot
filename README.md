# Yu-Gi-Oh! Master Duel Bot — Hybrid Memory + LLM Vision

Bot untuk farming solo mode (vs AI) di Yu-Gi-Oh! Master Duel.
Decision making pakai LLM (Gemini / OpenRouter).

> ⚠️ Peringatan: Bot ini cuma untuk solo mode / vs AI. Resiko sendiri kalo dipake di Ranked/PvP.

---

## Cara Kerja

Bot baca state game lewat **2 cara:**

1. **Memory** (Windows) — baca LP, Phase, Turn langsung dari RAM game. Gratis, kenceng, aman.
2. **Vision** (Gemini AI) — screenshot layar, AI bacain kartu apa aja yang ada di hand/field.

Memory diprioritaskan. Vision cuma dipanggil kalo ada perubahan (kartu dimainkan, dll).
**Hasil: ~70% lebih hemat panggilan AI → bot 2-3x lebih cepat.**

### Fitur Optimasi Memory (Terbaru)
- **Persistent Offset Caching**: Offset alamat RAM hasil kalibrasi akan disimpan secara lokal di `config/offsets.yaml`. Saat bot dijalankan kembali, ia akan langsung memuat cache ini tanpa perlu melakukan scan memori dari awal.
- **Auto-Rescan Pintar**: Jika pembacaan memori (LP) gagal 3 kali berturut-turut (misal karena state duel berubah), bot secara otomatis melakukan pemindaian memori (rescan) ulang di latar belakang untuk menyinkronkan kembali alamat memori.
- **Manual/RPC Trigger**: Modul memori menyediakan API `refresh_memory()` yang dapat dipanggil oleh ZMQ Client via server RPC command `refreshMemory` untuk memaksa rescan alamat RAM kapan saja.

```
┌─────────────────────────┐
│  Baca Memory (gratis)   │ ← LP, Phase, Turn
└────────┬────────────────┘
         │ kalo ada perubahan
         ▼
┌─────────────────────────┐
│  Screenshot → Gemini AI │ ← Baca kartu di hand/field/GY
└────────┬────────────────┘
         ▼
┌─────────────────────────┐
│  LLM ambil keputusan    │ ← "Main kartu apa?"
└────────┬────────────────┘
         ▼
┌─────────────────────────┐
│  Klik mouse otomatis    │ ← Eksekusi
└─────────────────────────┘
```

---

## Panduan Instalasi Windows (Langkah demi Langkah)

Ini panduan buat yang pertama kali. Gak perlu pengalaman coding.

### Yang perlu disiapkan

| Bahan | Catatan |
|-------|---------|
| **Master Duel** | Udah terinstall di PC, bisa Solo mode |
| **Python 3.11 atau 3.12** | Download dari [python.org](https://www.python.org/downloads/) |
| **Google Gemini API Key** | Daftar gratis di [aistudio.google.com](https://aistudio.google.com/) |
| **Koneksi internet** | Buat panggil Gemini AI |

### Step 1: Install Python

1. Buka https://www.python.org/downloads/
2. Klik download **Python 3.12.x**
3. Pas file installer, **centang** ☑️ "Add Python to PATH"
4. Klik **Install Now**
5. Selesai. Verifikasi: buka **Command Prompt** (Win+R → ketik `cmd`), jalankan:
   ```
   python --version
   ```
   Harus muncul `Python 3.12.x`

### Step 2: Download Bot

1. Buka https://github.com/DichaPutra/orchestra-duel-bot
2. Klik tombol hijau **"Code"** → **"Download ZIP"**
3. Extract ZIP ke folder, misalnya `C:\OrchestraBot`

### Step 3: Dapetin Gemini API Key

1. Buka https://aistudio.google.com/
2. Login pake Google account
3. Klik **"Get API Key"** di kiri atas
4. Klik **"Create API Key"** → pilih project → copy key-nya
5. Simpan key-nya, nanti dipake di Step 5

### Step 4: Install Library

1. Buka folder bot tadi (C:\OrchestraBot)
2. Klik kanan di dalem folder → **"Open in Terminal"** atau buka Command Prompt dan `cd C:\OrchestraBot`
3. Masuk dulu ke folder orchestra-bot:
   ```
   cd orchestra-bot
   ```
4. Jalankan:
   ```
   pip install -r requirements.txt
   ```
   Tunggu sampe selesai. Kalo ada error, coba:
   ```
   python -m pip install -r requirements.txt
   ```

### Step 5: Setup API Key

1. Di folder `orchestra-bot`, cari file **`.env.example`**
2. **Klik kanan → Rename** jadi **`.env`**
3. **Klik kanan → Edit** (pake Notepad)
4. Isi API key lo:
   ```
   GEMINI_API_KEY=isi_api_key_lo_disini
   ```
   Contoh:
   ```
   GEMINI_API_KEY=AIzaSyB4v9Kx8...  (key asli dari Step 3)
   ```
5. **Save** (Ctrl+S)

### Step 6: Siapin Game

1. Buka **Yu-Gi-Oh! Master Duel**
2. Masuk ke **Solo Mode** (bukan Ranked/PvP)
3. Atur resolusi game: **1280x720**, **Window Mode** (bukan Fullscreen)
4. Mulai duel

### Step 7: Jalankan Bot dan Kalibrasi lewat GUI (Sangat Direkomendasikan)

Anda dapat mengelola konfigurasi, melakukan kalibrasi memori, serta menjalankan bot secara visual melalui antarmuka Windows GUI Manager yang modern.

1. Buka folder `orchestra-bot` dan klik ganda pada file **`run_gui.bat`**.
2. Jendela **Orchestra Bot Manager** akan terbuka.
3. Di tab **"Konfigurasi Bot (.env)"**:
   * Atur `Bot Mode` (direkomendasikan `hybrid` agar LLM bisa membaca nama asli kartu).
   * Pilih `LLM Provider` yang ingin digunakan (Gemini, OpenAI, DeepSeek, OpenRouter, atau Groq).
   * Masukkan API Key Anda, lalu klik tombol **"💾 SIMPAN KONFIGURASI"**.
4. Buka game **Yu-Gi-Oh! Master Duel** (atur resolusi **1280x720 Window Mode**) dan masuklah ke dalam duel.
5. Pada sidebar menu GUI, klik **"⚙ KALIBRASI MEMORI"** untuk menemukan alamat RAM otomatis. Anda dapat melihat progress deteksi offset memori langsung di tab **"Konsol Live Terminal"**.
6. Klik **"▶ MULAI DUEL BOT"** untuk meluncurkan server dan bot sekaligus. Pantau jalannya duel dan thought process (pemikiran) LLM di tab konsol log!
7. Klik **"⏹ HENTIKAN BOT"** kapan saja untuk menghentikan bot secara aman.

---

### Cara Alternatif (Manual via Terminal / CLI)

Jika Anda ingin menjalankan bot secara manual tanpa GUI:

**1. Kalibrasi Memori (Dalam Duel):**
Jalankan perintah ini di dalam duel untuk mendeteksi offset memori RAM game. Offset yang ditemukan akan disimpan secara otomatis ke dalam cache `config/offsets.yaml`:
```bash
python auto_calibrate.py --save
```

**2. Jalankan Bot (Gampang):**
Klik ganda file **`run_bot.bat`** di folder `orchestra-bot`.

**3. Jalankan Bot (Manual):**
```bash
python main.py
```
*Gunakan **Ctrl+C** di terminal untuk menghentikan bot.*

---

## Untuk Pengguna macOS

Bot di macOS cuma pake Vision (gak bisa memory hacking).

```bash
cd orchestra-bot
pip install -r requirements.txt
# Setup .env dengan API key
python main.py
```

---

## Project Structure

```
yugioh-md-bot/
├── orchestra-bot/           # ← Kode bot utama
│   ├── main.py              # Entry point
│   ├── gui.py               # Windows GUI Manager desktop (Baru)
│   ├── config/              # Folder konfigurasi
│   │   ├── offsets.yaml     # Cache alamat RAM hasil kalibrasi otomatis
│   │   └── .gitkeep
│   ├── prompts/             # Folder prompt strategi (Baru)
│   │   ├── system.txt       # Instruksi deck & format JSON LLM
│   │   └── examples.txt     # Contoh input-output few-shot LLM
│   ├── orchestra_server.py  # Server ZMQ (terima command dari bot)
│   ├── memory_reader.py     # Baca memory game (Windows)
│   ├── memory_scanner.py    # Scanner alamat memory otomatis
│   ├── memory_state.py      # Gabungan memory + vision
│   ├── capture.py           # Screenshot game
│   ├── vision.py            # Panggil Gemini Vision API
│   ├── input.py             # Klik mouse otomatis
│   ├── window.py            # Cari jendela game
│   ├── auto_calibrate.py    # Setup alamat memory sekali jalan
│   ├── jduel_bot/           # Library komunikasi ZMQ
│   ├── bots/
│   │   ├── llm_bot.py       # Bot berbasis LLM Decision Maker (Bawaan)
│   │   ├── self_burn.py     # Contoh bot statis self-burn
│   │   └── pass_turn.py     # Contoh bot pass turn
│   ├── .env.example
│   ├── requirements.txt
│   ├── run_bot.bat          # Klik 2x buat jalan manual CLI (Windows)
│   └── run_gui.bat          # Klik 2x buat jalan lewat GUI (Windows)
├── README.md                # ← File ini
├── .gitignore
```

---

## Panduan Nambahin Bot / Deck Sendiri

Biar bot main pake deck lo, edit file **`prompts/system.txt`**:

```
Deck: Tenpai Dragon
Goal: OTK di Battle Phase secepatnya
Strategi:
- Pake Sangen Summoning biar bisa attack langsung
- Summon Genroku, cari Kaimen
- Pake Kaimen summon Seals, cari Transcendent
- Battle phase, serang semua
Peringatan: Jangan pernah negasi Maxx C sendiri
```

Makin detail deskripsi deck, makin bagus keputusan LLM-nya.

---

## FAQ

**Q: Apakah bot ini gak ketahuan anti-cheat?**
A: Bot cuma baca memory (read-only, gak nulis) + screenshot layar. Gak inject code apapun. Resiko sangat rendah, apalagi kalo cuma dipake Solo Mode.

**Q: Kenapa bot lemot banget?**
A: Mungkin koneksi Gemini lambat. Cek:
- Kalo vision-mode doang (memory gagal), tiap langkah butuh ~2 detik
- Pastiin Master Duel window mode 1280x720
- Kalo pake OpenRouter, latency bisa lebih tinggi

**Q: Abis update Master Duel atau ganti ronde, bot error. Kenapa?**
A: Alamat memory berubah setiap kali game update atau saat duel baru dimulai jika offset belum stabil. Bot sekarang memiliki mekanisme **Auto-Rescan** otomatis saat pembacaan gagal 3 kali, namun jika Anda ingin melakukan pemindaian paksa/manual, cukup jalankan ulang kalibrasi:
```bash
python auto_calibrate.py --save
```
Atau klik tombol **"Kalibrasi Memori"** di GUI Windows Manager. File offsets baru akan otomatis tertulis di `config/offsets.yaml` dan langsung dimuat oleh bot.

**Q: Kalo di macOS / Linux bisa?**
A: Bisa, tapi cuma pake Vision (gak bisa memory hacking). Jalanin `python main.py` aja.

**Q: Error "Master Duel window not found"?**
A: Pastiin game udah jalan dan di window mode (bukan fullscreen). Coba minimize-restore jendela game.

---

## Lisensi

MIT — bebas dipake, diubah, disebarin.
Bot ini independen dan tidak berafiliasi dengan Konami atau JMaster.
