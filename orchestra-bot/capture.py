"""
capture.py — Screenshot helper using DXCAM (fast Windows capture) and MSS fallback.
"""
import logging
import sys
from typing import Optional
from PIL import Image

logger = logging.getLogger("orchestra.capture")

# Global DXCAM instance
_dx_camera = None


def capture_window(rect: Optional[tuple] = None) -> Optional[Image.Image]:
    """
    Capture the game window or a specific region of the screen.
    rect: (left, top, width, height) relative to screen.
    """
    global _dx_camera

    # DXCAM: fastest on Windows
    if sys.platform == "win32":
        try:
            import dxcam
            if _dx_camera is None:
                _dx_camera = dxcam.create()

            if _dx_camera:
                if rect:
                    left, top, width, height = rect
                    right = left + width
                    bottom = top + height
                    # dxcam takes region: (left, top, right, bottom)
                    frame = _dx_camera.grab(region=(left, top, right, bottom))
                else:
                    frame = _dx_camera.grab()

                if frame is not None:
                    return Image.fromarray(frame)
        except Exception as e:
            logger.debug("dxcam capture failed: %s. Falling back to mss.", e)

    # Fallback: MSS (cross-platform, fast)
    try:
        import mss
        with mss.mss() as sct:
            if rect:
                left, top, width, height = rect
                monitor = {"left": left, "top": top, "width": width, "height": height}
                sct_img = sct.grab(monitor)
            else:
                sct_img = sct.grab(sct.monitors[1])

            return Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
    except Exception as e:
        logger.debug("mss capture failed: %s. Falling back to pyautogui.", e)

    # Ultimate fallback: pyautogui
    try:
        import pyautogui
        if rect:
            return pyautogui.screenshot(region=rect)
        return pyautogui.screenshot()
    except Exception as e:
        logger.error("All screenshot methods failed: %s", e)
        return None
