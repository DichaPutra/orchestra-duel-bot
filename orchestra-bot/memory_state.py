"""
memory_state.py — Pure Memory State Reader (No Vision Fallback)
"""

import logging
import time
from typing import Optional

import memory_reader as mem

logger = logging.getLogger("orchestra.memory_state")


def read_lp(player: int = 0) -> Optional[int]:
    """
    Read LP dari memory. None = gagal.
    Player: 0 = kita, 1 = lawan
    """
    return mem.read_lp(player)


def read_phase() -> Optional[int]:
    """
    Read phase dari memory.
    Return: 0=Draw, 1=Standby, 2=Main1, 3=Battle, 4=Main2, 5=End
    None = memory gagal
    """
    return mem.read_phase()


def read_is_my_turn() -> Optional[bool]:
    """Check turn dari memory. None = gagal."""
    return mem.read_is_my_turn()


def read_hand_count() -> Optional[int]:
    """Read hand count dari memory. None = gagal."""
    return mem.read_hand_count()


def try_init_memory():
    """
    Coba init memory reader.
    Return True kalo memory reader siap, False kalo gagal.
    """
    if not mem.is_available():
        logger.info("Memory reader not available on this system.")
        return False

    success = mem.init()
    if success:
        logger.info("✅ Memory reader successfully initialized!")
    else:
        logger.info("Memory reader initialization failed.")
    return success

def refresh_memory() -> bool:
    """Force a full memory rescan via the underlying memory_reader.
    Returns True if the rescan succeeded and LP address is known.
    """
    return mem.refresh_memory()


def init_memory_with_retry(max_retries: int = 3, delay: float = 2.0) -> bool:
    """
    Init memory reader dengan retry.
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
