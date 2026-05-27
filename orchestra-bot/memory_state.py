"""
memory_state.py — Hybrid State Reader (Memory + Vision Fallback)

Menggabungkan memory hacking (Opsi B) dengan vision (Opsi A):
1. Coba baca dari memory dulu (gratis, < 1ms)
2. Kalo gagal / data gak lengkap → fallback ke vision
3. Vision cuma dipanggil kalo memory gagal atau state kartu berubah

Ini adalah kunci Opsi B: mengurangi ~70% panggilan vision.
"""

import logging
import time
from typing import Optional

import memory_reader as mem
import vision

logger = logging.getLogger("orchestra.memory_state")

# Vision cost tracking
_vision_calls_saved = 0
_vision_calls_made = 0
_total_checks = 0


def get_stats() -> dict:
    """Return statistics about memory vs vision usage."""
    global _vision_calls_saved, _vision_calls_made, _total_checks
    return {
        "total_checks": _total_checks,
        "vision_calls_saved": _vision_calls_saved,
        "vision_calls_made": _vision_calls_made,
        "savings_pct": round(
            _vision_calls_saved / max(_total_checks, 1) * 100, 1
        ),
    }


# ── LP ──

def read_lp(player: int = 0) -> Optional[int]:
    """
    Read LP dari memory. None = gagal.

    Player: 0 = kita, 1 = lawan
    """
    return mem.read_lp(player)


def get_lp_safe(player: int = 0, screenshot=None) -> int:
    """
    Get LP — memory first, vision fallback.

    Returns LP value (default 8000 if all methods fail).
    """
    global _total_checks
    _total_checks += 1

    # Memory path
    lp = mem.read_lp(player)
    if lp is not None and 0 <= lp <= 99999:
        global _vision_calls_saved
        _vision_calls_saved += 1
        return lp

    # Vision fallback
    if screenshot is not None:
        global _vision_calls_made
        _vision_calls_made += 1
        state = vision.get_board_state(screenshot)
        if state:
            key = "MY_LP" if player == 0 else "OPPONENT_LP"
            return int(state.get(key, 8000))

    return 8000


# ── Phase ──

def read_phase() -> Optional[int]:
    """
    Read phase dari memory.
    Return: 0=Draw, 1=Standby, 2=Main1, 3=Battle, 4=Main2, 5=End
    None = memory gagal
    """
    return mem.read_phase()


PHASE_NAMES = {0: "Draw", 1: "Standby", 2: "Main1", 3: "Battle", 4: "Main2", 5: "End", 7: "Null"}


def get_phase_safe(screenshot=None) -> int:
    """
    Get phase — memory first, vision fallback.
    Return Phase enum value (default Main1=2).
    """
    global _total_checks
    _total_checks += 1

    # Memory path
    phase = mem.read_phase()
    if phase is not None and 0 <= phase <= 7:
        global _vision_calls_saved
        _vision_calls_saved += 1
        return phase

    # Vision fallback
    if screenshot is not None:
        global _vision_calls_made
        _vision_calls_made += 1
        state = vision.get_board_state(screenshot)
        if state:
            phase_str = (state.get("CURRENT_PHASE", "") or "").lower().strip()
            phase_map = {
                "draw": 0, "standby": 1,
                "main 1": 2, "main1": 2, "main phase 1": 2,
                "battle": 3,
                "main 2": 4, "main2": 4, "main phase 2": 4,
                "end": 5,
            }
            return phase_map.get(phase_str, 2)

    return 2  # Default Main1


# ── Turn ──

def read_is_my_turn() -> Optional[bool]:
    """Check turn dari memory. None = gagal."""
    return mem.read_is_my_turn()


def is_my_turn_safe(screenshot=None) -> bool:
    """
    Check turn — memory first, vision fallback.
    Default: True (our turn).
    """
    global _total_checks
    _total_checks += 1

    turn = mem.read_is_my_turn()
    if turn is not None:
        global _vision_calls_saved
        _vision_calls_saved += 1
        return turn

    if screenshot is not None:
        global _vision_calls_made
        _vision_calls_made += 1
        state = vision.get_board_state(screenshot)
        if state:
            return bool(state.get("IS_MY_TURN", True))

    return True


# ── Hand Count ──

def read_hand_count() -> Optional[int]:
    """Read hand count dari memory. None = gagal."""
    return mem.read_hand_count()


# ── Duel Status ──

def is_dueling_safe(screenshot=None) -> bool:
    """
    Check apakah duel sedang berlangsung.
    Memory: ada LP = duel. Vision: check DUEL_ENDED flag.
    """
    # Coba memory dulu
    lp = mem.read_lp(0)
    if lp is not None and lp > 0:
        return True

    if screenshot is not None:
        state = vision.get_board_state(screenshot)
        if state:
            return not state.get("DUEL_ENDED", True)

    return False


# ── Auto-Init ──

def try_init_memory():
    """
    Coba init memory reader.
    Return True kalo memory reader siap, False kalo harus pake vision full.
    """
    if not mem.is_available():
        logger.info("Memory reader not available. Will use vision only.")
        return False

    success = mem.init()
    if success:
        logger.info("✅ Memory reader ready! Vision calls will be reduced by ~70%")
    else:
        logger.info("Memory reader init failed. Will use vision only.")
    return success


def init_memory_with_retry(max_retries: int = 3, delay: float = 2.0) -> bool:
    """
    Init memory reader dengan retry.
    Berguna kalo Master Duel baru aja di-launch dan belum siap.
    """
    for attempt in range(1, max_retries + 1):
        logger.info(f"Memory init attempt {attempt}/{max_retries}")
        if try_init_memory():
            return True
        if attempt < max_retries:
            logger.info(f"Retrying in {delay}s...")
            time.sleep(delay)
    logger.warning("Memory init failed after all retries")
    return False


# ── Full State (Combined) ──

def get_full_state(screenshot=None) -> dict:
    """
    Dapatkan full game state:
    - LP, Phase, Turn dari memory (kalo bisa)
    - Card state dari vision (always via vision, karena memory hacking
      untuk card properties jauh lebih kompleks)

    Return dict dengan format:
    {
        "MY_LP": int,
        "OPPONENT_LP": int,
        "CURRENT_PHASE": str,
        "PHASE_VALUE": int,
        "IS_MY_TURN": bool,
        "HAND_COUNT": int,
        "DUEL_ENDED": bool,
        "source": "memory" | "vision" | "hybrid"
    }
    """
    result = {
        "MY_LP": 8000,
        "OPPONENT_LP": 8000,
        "CURRENT_PHASE": "Main 1",
        "PHASE_VALUE": 2,
        "IS_MY_TURN": True,
        "HAND_COUNT": 5,
        "DUEL_ENDED": False,
        "source": "unknown",
    }

    # Memory path
    use_memory = mem.is_available() and mem.get_reader()._handle is not None
    memory_ok = False

    if use_memory:
        my_lp = mem.read_lp(0)
        opp_lp = mem.read_lp(1)
        phase = mem.read_phase()
        turn = mem.read_is_my_turn()
        hand = mem.read_hand_count()

        # Validasi: semua yang dari memory harus masuk akal
        lp_ok = my_lp is not None and 0 <= my_lp <= 99999
        phase_ok = phase is not None and 0 <= phase <= 7

        if lp_ok and phase_ok:
            result["MY_LP"] = my_lp or 8000
            result["OPPONENT_LP"] = opp_lp if opp_lp is not None else 8000
            result["PHASE_VALUE"] = phase or 2
            result["CURRENT_PHASE"] = PHASE_NAMES.get(phase or 2, f"Phase_{phase}")
            result["IS_MY_TURN"] = turn if turn is not None else True
            result["HAND_COUNT"] = hand if hand is not None else 0
            result["source"] = "memory"
            memory_ok = True

    # Vision fallback (for card data + backup)
    if screenshot is not None:
        state = vision.get_board_state(screenshot)
        if state:
            # Override memory values with vision ones for accuracy
            for key in ["MY_LP", "OPPONENT_LP", "CURRENT_PHASE", "IS_MY_TURN", "DUEL_ENDED"]:
                if key in state:
                    result[key] = state[key]

            # Card data always from vision
            result["CARDS_IN_HAND"] = state.get("CARDS_IN_HAND", [])
            result["MY_MONSTERS"] = state.get("MY_MONSTERS", [])
            result["MY_SPELLS_TRAPS"] = state.get("MY_SPELLS_TRAPS", [])
            result["MY_GRAVEYARD"] = state.get("MY_GRAVEYARD", [])
            result["OPPONENT_MONSTERS"] = state.get("OPPONENT_MONSTERS", 0)
            result["OPPONENT_SPELLS_TRAPS"] = state.get("OPPONENT_SPELLS_TRAPS", 0)

            if not memory_ok:
                result["source"] = "vision"
            else:
                result["source"] = "hybrid"

    return result
