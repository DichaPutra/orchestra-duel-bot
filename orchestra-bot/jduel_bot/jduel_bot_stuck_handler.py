import hashlib
from time import sleep

import win32con
import win32gui
import win32ui
from PIL import Image

from jduel_bot.jduel_bot_handler import *
from jduel_bot.jduel_bot_logger import *


def screenshot_window(window_title: str, output_file_path: str):
    """
    Take a screenshot of the specified window by title and save it to a file.
    """
    hwnd = win32gui.FindWindow(None, window_title)
    if not hwnd:
        raise Exception(f"Window not found: {window_title}")

    left, top, right, bottom = win32gui.GetWindowRect(hwnd)
    width, height = right - left, bottom - top

    # Get device contexts
    window_device_context = win32gui.GetWindowDC(hwnd)
    try:
        source_device_context = win32ui.CreateDCFromHandle(window_device_context)
        compatible_device_context = source_device_context.CreateCompatibleDC()
        bitmap = None
        try:
            bitmap = win32ui.CreateBitmap()
            bitmap.CreateCompatibleBitmap(source_device_context, width, height)
            compatible_device_context.SelectObject(bitmap)

            # Copy the window content into the bitmap
            compatible_device_context.BitBlt((0, 0), (width, height),
                                             source_device_context, (0, 0), win32con.SRCCOPY)

            # Convert raw bitmap data to a PIL Image
            signed_ints_array = bitmap.GetBitmapBits(True)
            image = Image.frombuffer('RGB', (width, height), signed_ints_array,
                                     'raw', 'BGRX', 0, 1)

            image.save(output_file_path)
            logger.info(f"Screenshot successfully saved as: {output_file_path}")
        finally:
            # Clean up device contexts and GDI objects to avoid leaks
            compatible_device_context.DeleteDC()
            source_device_context.DeleteDC()
            if bitmap is not None:
                win32gui.DeleteObject(bitmap.GetHandle())
    finally:
        win32gui.ReleaseDC(hwnd, window_device_context)


class StuckHandler:
    def __init__(self,
                 duel_bot_client: JDuelBotClient,
                 script_name: str = "",
                 stuck_timeout_seconds: int = 300):
        self.duel_bot_client = duel_bot_client
        self.last_log_hash = ""
        self.last_update_time = time.time()
        self.script_name = script_name
        self.stuck_timeout_seconds = stuck_timeout_seconds

    def _get_current_log_hash(self) -> str:
        """Calculates a hash of the entire duel log."""
        try:
            duel_log = self.duel_bot_client.get_duel_log()
            log_string = "".join(str(duel_log_entry) for duel_log_entry in duel_log)
            return hashlib.sha256(log_string.encode('utf-8')).hexdigest()
        except Exception as exception:
            logger.error(f"Error retrieving duel log for hash check: {exception}")
            return ""

    def _handle_stuck_action(self):
        """Executes actions when a stuck state is detected (e.g., screenshot)."""
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        root_directory = Path("")
        screenshots_directory = root_directory / "stuck-handler-screenshots"
        screenshots_directory.mkdir(parents=True, exist_ok=True)  # Create if missing

        output_file_path = screenshots_directory / f"{self.script_name}-{timestamp}.png"

        logger.info(f"Creating stuck screenshot: {output_file_path}")
        try:
            window_title = self.get_window_title()
            screenshot_window(window_title=window_title, output_file_path=str(output_file_path))
        except Exception as exception:
            logger.error(f"ERROR creating screenshot: {exception}")
        logger.info("Exiting the duel...")
        self.duel_bot_client.set_duel_step(DuelStep.DuelEnd)

    def get_window_title(self) -> str:
        if self.duel_bot_client.address == master_duel_connection_address:
            window_title = "Yu-Gi-Oh! Master Duel"
        elif self.duel_bot_client.address == duel_links_connection_address:
            window_title = "Yu-Gi-Oh! DUEL LINKS"
        else:
            raise Exception(f"Windows title not implemented for {self.duel_bot_client.address}")
        return window_title

    def _check_for_stuck_state(self) -> None:
        """Checks if the bot is stuck."""
        current_hash = self._get_current_log_hash()
        current_time = time.time()

        if current_hash != self.last_log_hash:
            self.last_log_hash = current_hash
            self.last_update_time = current_time
            return

        time_elapsed = current_time - self.last_update_time

        if time_elapsed >= self.stuck_timeout_seconds:
            logger.error(f"STUCK DETECTED! Duel log has not changed for {time_elapsed:.2f} seconds.")
            self._handle_stuck_action()
            self.last_update_time = current_time

    def run(self):
        logger.info("Stuck handler initialized...")
        while True:
            while self.duel_bot_client.is_dueling():
                # Only check if we're stuck when we're required to input
                if self.duel_bot_client.is_inputting():
                    self._check_for_stuck_state()
                sleep(1)

            self.last_log_hash = ""
            self.last_update_time = time.time()
            sleep(1)
