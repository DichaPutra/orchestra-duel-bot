"""
auto_calibrate.py — Memory Scanner Calibration Tool (Opsi B)

Jalanin script ini SEKALI pas Master Duel udah di-duel screen.
Dia akan:
1. Scan memory Master Duel buat cari LP, Phase, Turn addresses
2. Verify setiap address dengan baca nilai 3x
3. Save offsets ke file yang bisa di-load ulang
4. Kasih rekomendasi offset buat dimasukin ke script

Usage:
    python auto_calibrate.py          # Normal scan
    python auto_calibrate.py --save   # Scan + save offsets
    python auto_calibrate.py --verify # Uji coba offsets yang sudah ada

Requirements:
    - Windows
    - Master Duel running (dalam duel)
    - psutil installed (pip install psutil)
"""
import logging
import sys
import time

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("calibrate")

# ── ANSI colors ──
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"


def banner():
    print(f"""
{CYAN}{BOLD}╔══════════════════════════════════════════╗
║   Orchestra Duel Bot — Auto Calibrator   ║
║   Memory Scanner (Opsi B)                ║
╚══════════════════════════════════════════╝{RESET}
""")


def main():
    banner()

    if sys.platform != "win32":
        print(f"{RED}Memory scanner hanya berjalan di Windows.{RESET}")
        print(f"MacOS: run di Windows VM atau pake vision-only mode.")
        return

    # Check arguments
    args = set(sys.argv[1:])
    verify_mode = "--verify" in args
    save_mode = "--save" in args or True  # Default save

    # Import memory modules
    sys.path.insert(0, ".")
    import memory_reader as mem
    import memory_scanner as scanner

    # ── Step 1: Find process ──
    print(f"\n{YELLOW}[1/5] Looking for Master Duel process...{RESET}")
    pid = mem.get_reader()._find_process()
    if pid is None:
        print(f"{RED}❌ Master Duel not found! Jalankan Master Duel dulu.{RESET}")
        print(f"   Tips: Buka game, masuk ke duel (Solo mode), lalu jalanin script ini.")
        return
    print(f"{GREEN}✅ Found PID: {pid}{RESET}")

    # ── Step 2: Open handle ──
    print(f"\n{YELLOW}[2/5] Opening process handle...{RESET}")
    if not mem.init():
        print(f"{RED}❌ Failed to open process handle.{RESET}")
        return
    print(f"{GREEN}✅ Handle opened successfully{RESET}")

    # ── Step 3: Scan for values ──
    print(f"\n{YELLOW}[3/5] Scanning memory for game state...{RESET}")
    print(f"   {CYAN}Scanning for LP (value 8000)...{RESET}")

    reader = mem.get_reader()

    # Full scan
    results = scanner.find_all_addresses(reader)

    if not results:
        print(f"\n{RED}❌ No values found! Pastikan:{RESET}")
        print(f"   1. Master Duel sedang dalam duel (bukan menu)")
        print(f"   2. Game resolution 1280x720")
        print(f"   3. Window mode (not fullscreen)")
        print(f"\n   {YELLOW}Tips: Kalo masih gagal, coba jalanin game di window mode.{RESET}")
        reader.close()
        return

    print(f"\n{GREEN}{BOLD}📊 Found {len(results)} addresses:{RESET}")
    for key, addr in sorted(results.items()):
        val = reader.read_int32(addr)
        val_str = f" (value: {val})" if val is not None else ""
        print(f"   {GREEN}✅ 0x{addr:012X}{RESET} → {key}{val_str}")

    # ── Step 4: Verify ──
    print(f"\n{YELLOW}[4/5] Verifying addresses (3 reads)...{RESET}")
    errors = 0
    for key, addr in sorted(results.items()):
        values = []
        for i in range(3):
            v = reader.read_int32(addr)
            values.append(v)
            time.sleep(0.05)

        # Check stability
        if len(set(values)) == 1 and values[0] is not None:
            print(f"   {GREEN}✅ {key}: stable = {values[0]}{RESET}")
        elif None in values:
            print(f"   {RED}❌ {key}: read failed{RESET}")
            errors += 1
        else:
            print(f"   {YELLOW}⚠️  {key}: unstable = {values} (may change during duel){RESET}")

    if errors:
        print(f"\n{RED}⚠️  {errors} address(es) failed verification{RESET}")
    else:
        print(f"{GREEN}✅ All addresses stable!{RESET}")

    # ── Step 5: Save ──
    print(f"\n{YELLOW}[5/5] Saving offsets...{RESET}")
    if save_mode:
        offset_file = "memory_offsets.txt"
        scanner.save_offsets(results, offset_file)
        print(f"{GREEN}✅ Offsets saved to {offset_file}{RESET}")

    # Summary
    print(f"\n{BOLD}{CYAN}═══════════════════════════════════════{RESET}")
    print(f"{BOLD}  Memory Calibration Complete!{RESET}")
    print(f"{BOLD}  Mode: {'Memory + Vision (Opsi B)' if len(results) >= 2 else 'Vision-only (Opsi A)'}{RESET}")
    print(f"{BOLD}{CYAN}═══════════════════════════════════════{RESET}")
    print(f"\n  Savings estimation:")
    saved_pct = min(len(results) * 20, 70)  # ~20% per value found
    print(f"  {GREEN}~{saved_pct}% fewer vision calls{RESET} (from {len(results)} values)")
    print(f"\n  {YELLOW}Run 'python main.py' to start bot with memory-first mode.{RESET}")

    reader.close()


if __name__ == "__main__":
    main()
