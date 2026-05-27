"""
Input — translate JSON action ke mouse click.

Pake pyautogui buat simulasi mouse.
Ditambah offset window biar klik di koordinat game, bukan layar.
"""
import logging
import time
from typing import Optional

from config import Config
from utils.geometry import Layout, get_card_position

logger = logging.getLogger("md_bot.input")

# Window offset — diset oleh main.py pas window ditemukan
_window_offset = (0, 0)
_layout: Optional[Layout] = None


def set_window(rect: tuple):
    """
    Set posisi window biar klik di koordinat yang benar.
    rect = (left, top, width, height)
    """
    global _window_offset, _layout
    _window_offset = (rect[0], rect[1])
    _layout = Layout.detect(rect[2], rect[3])
    logger.info("Window offset: %s, Layout: %s", _window_offset, _layout)


def execute(action: dict):
    """
    Terjemahin action JSON ke klik mouse.

    action: {"action": "summon", "card": "Genroku", "position": "attack"}
           {"action": "activate", "card": "Sangen Summoning", "zone": "hand"}
           {"action": "end_turn"}
           {"action": "chain_yes", "card": "Maxx C"}
           ...
    """
    import pyautogui
    pyautogui.PAUSE = Config.ACTION_DELAY

    action_type = action.get("action", "")
    logger.info("Action: %s — %s", action_type, action)

    if action_type == "summon":
        zone = "field_monster"
        pos = get_card_position(_layout, zone, _find_empty_slot(zone))
        _click(pos)
        logger.info("  → Normal Summon %s di slot %s", action.get("card"), pos)

    elif action_type == "activate":
        zone = action.get("zone", "hand")
        if zone == "hand":
            idx = action.get("index", 0)
            pos = get_card_position(_layout, "hand", idx)
        else:
            pos = get_card_position(_layout, zone, 0)
        _click(pos)
        logger.info("  → Activate %s", action.get("card"))

    elif action_type == "set":
        zone = action.get("zone", "spell")
        if zone == "monster":
            pos = get_card_position(_layout, "field_monster",
                                    _find_empty_slot("field_monster"))
        else:
            pos = get_card_position(_layout, "field_spell",
                                    _find_empty_slot("field_spell"))
        _click(pos)
        logger.info("  → Set card")

    elif action_type == "attack":
        target = action.get("target", "")
        # Klik monster lawan — perlu mapping target
        _click(get_card_position(_layout, "field_monster", 0))
        logger.info("  → Attack %s", target)

    elif action_type == "direct_attack":
        _click(get_card_position(_layout, "battle_phase"))
        time.sleep(0.5)
        _click(get_card_position(_layout, "confirm"))
        logger.info("  → Direct attack")

    elif action_type == "end_turn":
        _click(get_card_position(_layout, "end_turn"))
        logger.info("  → End turn")

    elif action_type == "chain_yes":
        _click(get_card_position(_layout, "chain_yes"))
        logger.info("  → Chain respond: %s", action.get("card"))

    elif action_type == "chain_no":
        _click(get_card_position(_layout, "chain_no"))
        logger.info("  → Skip chain")

    elif action_type == "confirm":
        _click(get_card_position(_layout, "confirm"))
        logger.info("  → Confirm")

    elif action_type == "wait":
        logger.info("  → Wait...")
        time.sleep(2)

    else:
        logger.warning("Unknown action: %s", action_type)


def _click(pos: tuple):
    """Klik di koordinat tertentu dengan offset window."""
    import pyautogui
    x = pos[0] + _window_offset[0]
    y = pos[1] + _window_offset[1]
    pyautogui.click(x, y)


def _find_empty_slot(zone: str) -> int:
    """
    Cari slot kosong di zone tertentu.
    TODO: Implement state tracking — tahu slot mana yang terisi.
    Sementara return 0 (slot pertama).
    """
    return 0
