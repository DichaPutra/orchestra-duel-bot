"""
Yu-Gi-Oh! Master Duel Bot — Main Loop

Flow:
  1. Cari & focus window game
  2. Loop:
     a. Screenshot
     b. Extract state (vision)
     c. Decide action (LLM)
     d. Execute action (mouse click)
     e. Kecilin delay biar gak spam
  3. Detek duel selesai → stop

Usage:
  python main.py                    # Mode normal
  python main.py --dry-run          # Gak klik beneran, cuma print
  python main.py --show-pos         # Kalibrasi: print posisi klik
"""
import argparse
import logging
import sys
import time

from config import Config
from utils.logger import setup_logger

logger = setup_logger()


def find_game_window():
    """Cari window Master Duel, return rect (left, top, width, height) atau None."""
    import capture
    import sys as _sys

    if _sys.platform == "win32":
        try:
            import pygetwindow as gw
            wins = gw.getWindowsWithTitle(Config.GAME_WINDOW)
            if not wins:
                logger.error("Window '%s' gak ketemu. "
                             "Pastikan game jalan.", Config.GAME_WINDOW)
                return None
            w = wins[0]
            if w.isMinimized:
                w.restore()
            w.activate()
            time.sleep(0.5)
            return (w.left, w.top, w.width, w.height)
        except Exception as e:
            logger.error("Gagal detek window: %s", e)
            return None
    else:
        # macOS / fallback
        rect = capture._find_window_rect(Config.GAME_WINDOW)
        if rect:
            logger.info("Window found: %s", rect)
        else:
            logger.warning("Window '%s' gak ketemu. "
                           "Coba pastikan game jalan.", Config.GAME_WINDOW)
        return rect


def duel_loop(dry_run: bool = False):
    """Loop utama duel."""
    import capture
    import vision
    import decision
    import input as inp

    logger.info("─── Starting duel loop ───")

    # Cari window
    rect = find_game_window()
    if rect is None:
        logger.error("Game window not found. Exiting.")
        return

    if not dry_run:
        inp.set_window(rect)

    turn_count = 0
    max_turns = 30  # Safety limit

    while turn_count < max_turns:
        turn_count += 1
        logger.info("═══ Turn %d ═══", turn_count)

        # 1. Capture
        screenshot = capture.capture_window()
        if screenshot is None:
            logger.warning("Screenshot gagal, coba lagi...")
            time.sleep(2)
            continue

        # Simpan screenshot untuk debugging
        screenshot.save(f"screenshots/turn_{turn_count:02d}.png")

        # 2. Vision — extract state
        state_text = vision.extract_state(screenshot, use_llm_vision=True)
        logger.info("State:\n%s", state_text)

        # Cek duel selesai
        if _is_duel_over(state_text):
            logger.info("🏁 Duel selesai!")
            break

        # 3. Decision — LLM milih action
        action = decision.decide_action(state_text)
        if action is None:
            logger.warning("Gak dapet action, coba ulang...")
            time.sleep(2)
            continue

        logger.info("Decided: %s", action)

        # 4. Execute
        if dry_run:
            logger.info("[DRY-RUN] Akan execute: %s", action)
        else:
            # Manual confirm mode
            if Config.MANUAL_CONFIRM:
                inp.execute(action)
            else:
                inp.execute(action)

        # Delay antar move
        time.sleep(Config.ACTION_DELAY)

    logger.info("─── Bot selesai ───")


def _is_duel_over(state_text: str) -> bool:
    """Deteksi kalo duel udah selesai (win/lose screen)."""
    indicators = ["win", "lose", "duel end", "victory", "defeat",
                  "surrender", "result", "rematch", "return to menu"]
    state_lower = state_text.lower()
    for keyword in indicators:
        if keyword in state_lower:
            return True
    return False


def calibrate_positions():
    """Mode kalibrasi — print koordinat tiap zona."""
    import capture
    from utils.geometry import Layout, get_card_position

    print("─── Mode Kalibrasi ───")
    print("Arahkan mouse ke tiap zona yang diminta, lalu tekan Enter.")
    print("Tekan Ctrl+C untuk keluar.\n")

    rect = find_game_window()
    if rect is None:
        print("Window gak ketemu.")
        return

    left, top, width, height = rect
    print(f"Window: {width}x{height} @ ({left}, {top})")
    layout = Layout.detect(width, height)

    zones = [
        "hand_0", "hand_1", "hand_2", "hand_3", "hand_4",
        "field_monster_0", "field_monster_2",
        "field_spell_0", "field_spell_2",
        "gy", "end_turn", "battle_phase", "confirm",
        "chain_yes", "chain_no",
    ]

    import pyautogui
    for zone in zones:
        input(f"  Tekan Enter untuk cek posisi {zone}...")
        x, y = pyautogui.position()
        print(f"  → {zone}: ({x - left}, {y - top})")


def main():
    parser = argparse.ArgumentParser(
        description="Yu-Gi-Oh! Master Duel Bot — LLM-based")
    parser.add_argument("--dry-run", action="store_true",
                        help="Gak klik beneran, cuma simulasi")
    parser.add_argument("--show-pos", action="store_true",
                        help="Mode kalibrasi — cek posisi zona")
    args = parser.parse_args()

    try:
        Config.validate()
    except ValueError as e:
        logger.error("Config error:\n%s", e)
        sys.exit(1)

    if args.show_pos:
        calibrate_positions()
        return

    logger.info("─── Yu-Gi-Oh! Master Duel Bot ───")
    logger.info("Provider: %s", Config.PROVIDER)
    logger.info("Dry-run: %s", args.dry_run)
    logger.info("Manual confirm: %s", Config.MANUAL_CONFIRM)

    duel_loop(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
