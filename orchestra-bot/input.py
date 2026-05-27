"""
Input — simulasi klik mouse di koordinat game (1280x720).
Semua koordinat dalam resolusi game, auto-dioffset ke posisi window.
"""
import logging
import time
import sys
from typing import Optional

logger = logging.getLogger("orchestra.input")

# Default layout untuk 1280x720 (resolusi wajib Master Duel bot)
# Semua koordinat (x, y) dalam ruang game 1280x720
LAYOUT_1280x720 = {
    # Hand — 5 kartu
    "hand": [(236, 624), (320, 624), (404, 624), (488, 624), (572, 624)],

    # Monster zones (kiri ke kanan)
    "monster_zones": [(118, 384), (234, 384), (350, 384), (466, 384), (582, 384)],

    # Spell/trap zones
    "spell_zones": [(118, 456), (234, 456), (350, 456), (466, 456), (582, 456)],

    # Extra monster zones
    "extra_monster_zones": [(350, 296)],

    # Field spell zone
    "field_zone": (640, 296),

    # GY (kanan bawah)
    "gy": (1160, 528),

    # Graveyard detail - klik kalo perlu lihat isi
    "gy_detail": (1050, 200),

    # Phase buttons
    "end_turn": (1220, 660),
    "battle_phase": (1180, 616),
    "main_phase_2": (1180, 616),

    # Confirm / Yes / No
    "confirm": (640, 416),
    "chain_yes": (556, 428),
    "chain_no": (724, 428),

    # Draw phase — klik tengah layar
    "draw": (640, 360),

    # Duel end — OK button
    "duel_end_ok": (680, 620),

    # Cancel activation toggle
    "cancel": (120, 680),

    # Surrender
    "surrender_confirm": (640, 416),
}

_rect = None  # (left, top, width, height)


def set_window_rect(rect: tuple):
    """Set posisi window buat offset klik."""
    global _rect
    _rect = rect
    logger.info("Window rect set: %s", rect)


def _game_to_screen(game_x: int, game_y: int) -> tuple:
    """Convert koordinat game (1280x720) ke koordinat layar."""
    if _rect is None:
        return (game_x, game_y)
    left, top, width, height = _rect
    # Scale kalo resolusi beda
    scale_x = width / 1280.0
    scale_y = height / 720.0
    return (int(left + game_x * scale_x), int(top + game_y * scale_y))


def click(zone: str, index: int = 0):
    """Klik di zona tertentu."""
    import pyautogui

    if zone in LAYOUT_1280x720:
        pos = LAYOUT_1280x720[zone]
        if isinstance(pos, list):
            x, y = pos[index] if index < len(pos) else pos[-1]
        else:
            x, y = pos
    else:
        logger.warning("Unknown zone: %s", zone)
        return

    screen_x, screen_y = _game_to_screen(x, y)
    pyautogui.click(screen_x, screen_y)
    logger.debug("Clicked %s[%d] → screen(%d, %d)", zone, index, screen_x, screen_y)


def click_hand_card(index: int):
    """Klik kartu di hand berdasarkan index (0=most left)."""
    click("hand", index)


def click_monster_zone(index: int):
    """Klik monster zone. index 0-4."""
    click("monster_zones", index)


def click_spell_zone(index: int):
    """Klik spell/trap zone. index 0-4."""
    click("spell_zones", index)


def click_extra_monster_zone(index: int = 0):
    """Klik extra monster zone."""
    click("extra_monster_zones", index)


def draw_phase():
    """Klik tengah layar buat draw."""
    click("draw")


def end_turn():
    """Klik End Turn button."""
    click("end_turn")


def battle_phase():
    """Klik Battle Phase button."""
    click("battle_phase")


def confirm():
    """Klik confirm/OK."""
    click("confirm")


def chain_yes():
    """Klik YES saat chain prompt."""
    click("chain_yes")


def chain_no():
    """Klik NO saat chain prompt."""
    click("chain_no")


def cancel_prompts():
    """Cancel activation prompts (ESC atau klik cancel)."""
    import pyautogui
    pyautogui.press("esc")
    time.sleep(0.3)


def exit_duel():
    """Klik OK di layar hasil duel."""
    click("duel_end_ok")
