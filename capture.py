"""
Capture — screenshot jendela game.

Target: Windows (DXCam) / Fallback: mss (cross-platform).
Development di macOS bisa pake screencapture.
"""
import logging
from typing import Optional
import numpy as np
from PIL import Image

from config import Config

logger = logging.getLogger("md_bot.capture")


def _find_window_rect(window_title: str) -> Optional[tuple]:
    """
    Cari posisi & ukuran jendela game.
    Return (left, top, width, height) atau None kalo gak ketemu.
    """
    import sys
    if sys.platform == "win32":
        try:
            import pygetwindow as gw
            wins = gw.getWindowsWithTitle(window_title)
            if not wins:
                return None
            w = wins[0]
            if w.isMinimized:
                w.restore()
            w.activate()
            return (w.left, w.top, w.width, w.height)
        except Exception:
            return None
    elif sys.platform == "darwin":
        # macOS — cari window via Quartz
        try:
            from Quartz import (
                CGWindowListCopyWindowInfo,
                kCGWindowListOptionOnScreenOnly,
                kCGNullWindowID,
            )
            win_list = CGWindowListCopyWindowInfo(
                kCGWindowListOptionOnScreenOnly, kCGNullWindowID
            )
            for win in win_list:
                name = win.get("kCGWindowName", "") or ""
                owner = win.get("kCGWindowOwnerName", "") or ""
                if window_title.lower() in (name + owner).lower():
                    bounds = win.get("kCGWindowBounds", {})
                    x = int(bounds.get("X", 0))
                    y = int(bounds.get("Y", 0))
                    w = int(bounds.get("Width", 0))
                    h = int(bounds.get("Height", 0))
                    return (x, y, w, h)
        except Exception:
            pass
    return None


def capture_window(window_title: str = None) -> Optional[Image.Image]:
    """
    Screenshot jendela game. Return PIL Image atau None.
    """
    title = window_title or Config.GAME_WINDOW
    rect = _find_window_rect(title)
    if rect is None:
        logger.warning("Window '%s' gak ketemu", title)
        return None

    left, top, width, height = rect
    if width < 100 or height < 100:
        logger.warning("Window terlalu kecil: %dx%d", width, height)
        return None

    import sys
    if sys.platform == "win32":
        try:
            import dxcam
            camera = dxcam.create()
            frame = camera.grab(region=(left, top, left+width, top+height))
            if frame is not None:
                return Image.fromarray(frame)
        except Exception:
            pass

    # Fallback: mss
    try:
        import mss
        with mss.mss() as sct:
            mon = {"left": left, "top": top, "width": width, "height": height}
            sct_img = sct.grab(mon)
            return Image.frombytes("RGB", sct_img.size, sct_img.rgb)
    except Exception as e:
        logger.error("Gagal capture: %s", e)
        return None
