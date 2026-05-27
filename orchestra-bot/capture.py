"""
Capture — screenshot game window.
Windows: DXCam / Fallback: mss
macOS: screencapture CLI / mss
"""
import sys
import logging
from typing import Optional
from PIL import Image

logger = logging.getLogger("orchestra.capture")


def capture_window(rect: tuple) -> Optional[Image.Image]:
    """
    Screenshot jendela game.
    rect = (left, top, width, height)
    Return PIL Image atau None.
    """
    left, top, width, height = rect
    if width < 100 or height < 100:
        logger.warning("Window too small: %dx%d", width, height)
        return None

    if sys.platform == "win32":
        return _capture_win32(left, top, width, height)
    return _capture_mss(left, top, width, height)


def _capture_win32(left, top, width, height):
    try:
        import dxcam
        camera = dxcam.create()
        frame = camera.grab(region=(left, top, left + width, top + height))
        if frame is not None:
            return Image.fromarray(frame[:, :, :3])
    except Exception:
        pass
    return _capture_mss(left, top, width, height)


def _capture_mss(left, top, width, height):
    try:
        import mss
        with mss.mss() as sct:
            mon = {"left": left, "top": top,
                   "width": width, "height": height}
            sct_img = sct.grab(mon)
            return Image.frombytes("RGB", sct_img.size, sct_img.rgb)
    except Exception as e:
        logger.error("MSS capture failed: %s", e)
        return None


def save_debug_screenshot(img: Image.Image, path: str):
    """Simpan screenshot untuk debugging."""
    img.save(path)
    logger.info("Screenshot saved: %s", path)
