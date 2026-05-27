"""
Game Window Finder — cross-platform (Windows + macOS)
"""
import sys
import logging
from typing import Optional

logger = logging.getLogger("orchestra.window")


def find_window_rect(window_title: str) -> Optional[tuple]:
    """
    Cari posisi & ukuran jendela game.
    Return (left, top, width, height) atau None.
    """
    if sys.platform == "win32":
        return _find_win32(window_title)
    elif sys.platform == "darwin":
        return _find_darwin(window_title)
    return None


def _find_win32(title: str) -> Optional[tuple]:
    try:
        import pygetwindow as gw
        wins = gw.getWindowsWithTitle(title)
        if not wins:
            return None
        w = wins[0]
        if w.isMinimized:
            w.restore()
        w.activate()
        return (w.left, w.top, w.width, w.height)
    except Exception as e:
        logger.debug("pygetwindow error: %s", e)
        return None


def _find_darwin(title: str) -> Optional[tuple]:
    try:
        from Quartz import (
            CGWindowListCopyWindowInfo,
            kCGWindowListOptionOnScreenOnly,
            kCGNullWindowID,
        )
        wins = CGWindowListCopyWindowInfo(
            kCGWindowListOptionOnScreenOnly, kCGNullWindowID)
        for win in wins:
            name = win.get("kCGWindowName", "") or ""
            owner = win.get("kCGWindowOwnerName", "") or ""
            if title.lower() in (name + owner).lower():
                b = win.get("kCGWindowBounds", {})
                return (int(b["X"]), int(b["Y"]),
                        int(b["Width"]), int(b["Height"]))
    except Exception as e:
        logger.debug("Quartz error: %s", e)
    return None


def get_game_resolution(rect: tuple) -> tuple:
    """Return (width, height) dari window rect."""
    return (rect[2], rect[3])
