"""
memory_injector.py — Memory Write Operations & DLL Injection (Opsi B+)

Memperluas memory_reader.py dengan kemampuan WRITE ke memory game.

Fitur:
  1. WriteProcessMemory — tulis nilai ke memory game (LP, dll)
  2. CreateRemoteThread — eksekusi fungsi di process game
  3. DLL Injection — LoadLibrary remote thread
  4. Game state manipulation — instant win, set LP, dll

CATATAN PENTING:
  - Write operations detected by anti-cheat (EAC/BE). Risiko sendiri.
  - Hanya jalan di Windows.
  - Untuk solo mode, resiko sangat rendah (EAC gak aktif).
"""

import ctypes
import ctypes.wintypes
import logging
import struct
import sys
import time
from pathlib import Path
from typing import Optional

logger = logging.getLogger("orchestra.injector")

# ── Windows Constants ──
PROCESS_CREATE_THREAD = 0x0002
PROCESS_VM_OPERATION = 0x0008
PROCESS_VM_WRITE = 0x0020
PROCESS_VM_READ = 0x0010
PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_SUSPEND_RESUME = 0x0800
PROCESS_ALL_ACCESS = 0x1F0FFF

MEM_COMMIT = 0x00001000
MEM_RESERVE = 0x00002000
PAGE_READWRITE = 0x04
PAGE_EXECUTE_READWRITE = 0x40

# ── Load memory reader for shared state ──
try:
    import memory_reader as mem
except ImportError:
    from . import memory_reader as mem

# ── JNA-style Windows API via ctypes ──

class _Injector:
    """Windows memory writer + injector via ctypes."""

    def __init__(self):
        self._handle = None
        self._kernel32 = ctypes.windll.kernel32 if sys.platform == "win32" else None
        self._gameassembly_base = None

    def is_available(self) -> bool:
        """Check if injector is available (Windows + process found)."""
        if sys.platform != "win32":
            return False
        if self._handle is not None:
            return True
        return self._get_handle() is not None

    def _get_handle(self, write_access: bool = False) -> Optional[int]:
        """
        Dapatkan handle ke Master Duel dengan akses write.
        Reuse handle dari memory_reader kalo ada.
        """
        # Try to reuse memory_reader handle
        reader = mem.get_reader()
        if reader._handle:
            self._handle = reader._handle
            self._pid = reader._pid
            return self._handle

        # Open new handle with write access
        pid = reader._find_process()
        if pid is None:
            return None

        desired_access = (PROCESS_VM_READ | PROCESS_VM_WRITE |
                          PROCESS_VM_OPERATION | PROCESS_QUERY_INFORMATION |
                          PROCESS_CREATE_THREAD)
        
        self._handle = self._kernel32.OpenProcess(desired_access, False, pid)
        if not self._handle:
            err = ctypes.get_last_error()
            logger.error(f"OpenProcess (write) failed: error {err}")
            logger.warning("Coba jalankan GUI sebagai Administrator!")
            return None

        self._pid = pid
        logger.info(f"Opened WRITE handle to PID {pid}")
        return self._handle

    def close(self):
        """Close handle."""
        if self._handle:
            self._kernel32.CloseHandle(self._handle)
            self._handle = None
            logger.info("Injector handle closed")

    # ── Write Operations ──

    def write_int32(self, address: int, value: int) -> bool:
        """Write a 32-bit integer ke process memory."""
        handle = self._get_handle(write_access=True)
        if not handle:
            return False

        buf = struct.pack("<i", value)
        bytes_written = ctypes.c_size_t(0)
        success = self._kernel32.WriteProcessMemory(
            self._handle, ctypes.c_void_p(address),
            buf, 4, ctypes.byref(bytes_written)
        )
        if success and bytes_written.value == 4:
            logger.info(f"✅ Wrote {value} to 0x{address:X}")
            return True
        logger.error(f"❌ WriteProcessMemory failed at 0x{address:X}")
        return False

    def write_bytes(self, address: int, data: bytes) -> bool:
        """Write arbitrary bytes ke process memory."""
        handle = self._get_handle(write_access=True)
        if not handle:
            return False

        buf = ctypes.create_string_buffer(data)
        bytes_written = ctypes.c_size_t(0)
        size = len(data)
        success = self._kernel32.WriteProcessMemory(
            self._handle, ctypes.c_void_p(address),
            buf, size, ctypes.byref(bytes_written)
        )
        return bool(success and bytes_written.value == size)

    # ── High-Level Cheat Features ──

    def set_lp(self, player: int, value: int) -> bool:
        """
        Set LP player tertentu.
        player: 0=self, 1=opponent
        Cari dulu alamat LP dari memory_reader, lalu write.
        """
        # Get LP address from scanner
        reader = mem.get_reader()
        if not reader._lp_self_addr:
            reader.get_lp(0)  # Trigger scan
            if not reader._lp_self_addr:
                logger.error("LP addresses not found. Run auto_calibrate first.")
                return False

        addr = reader._lp_self_addr if player == 0 else reader._lp_opponent_addr
        if not addr:
            logger.error(f"LP address for player {player} not found")
            return False

        return self.write_int32(addr, value)

    def instant_win(self) -> bool:
        """Set opponent LP to 0 → instant win."""
        logger.info("💥 Executing INSTANT WIN...")
        
        # Method 1: Set opponent LP to 0 (simplest, works 80% of time)
        if self.set_lp(1, 0):
            logger.info("💥 Opponent LP set to 0! Waiting for game to detect...")
            time.sleep(1)
            return True
        
        # Method 2: Set our LP high and opponent LP negative
        self.set_lp(0, 99999)
        return self.set_lp(1, -1)

    def set_game_title(self, title: str) -> bool:
        """
        Set window title Master Duel.
        Pake SetWindowText eksternal, gak perlu write memory.
        """
        handle = self._get_handle()
        if not handle:
            return False

        # Find window by PID
        EnumWindows = self._kernel32.EnumWindows
        EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.c_int)
        
        hwnd = [None]
        
        def callback(hwnd_enum, lparam):
            pid = ctypes.c_ulong()
            self._kernel32.GetWindowThreadProcessId(hwnd_enum, ctypes.byref(pid))
            if pid.value == self._pid:
                hwnd[0] = hwnd_enum
                return False  # Stop enumerating
            return True

        EnumWindows(EnumWindowsProc(callback), 0)
        
        if hwnd[0]:
            result = self._kernel32.SetWindowTextW(hwnd[0], title)
            if result:
                logger.info(f"✅ Window title set to: {title}")
                return True
        
        logger.error("❌ Failed to set window title")
        return False

    def pause_game(self) -> bool:
        """
        Pause game dengan suspend semua thread.
        Ini setara dengan "Pause Game" button JMaster.
        """
        handle = self._get_handle(write_access=True)
        if not handle:
            return False
        
        # Use NtSuspendProcess
        ntdll = ctypes.windll.ntdll
        try:
            result = ntdll.NtSuspendProcess(self._handle)
            if result == 0:
                logger.info("⏸️ Game paused (process suspended)")
                return True
            logger.error(f"NtSuspendProcess failed: {result}")
        except Exception as e:
            logger.error(f"Pause failed: {e}")
        return False

    def resume_game(self) -> bool:
        """Resume game dengan resume all threads."""
        handle = self._get_handle(write_access=True)
        if not handle:
            return False

        ntdll = ctypes.windll.ntdll
        try:
            result = ntdll.NtResumeProcess(self._handle)
            if result == 0:
                logger.info("▶️ Game resumed (process resumed)")
                return True
            logger.error(f"NtResumeProcess failed: {result}")
        except Exception as e:
            logger.error(f"Resume failed: {e}")
        return False

    # ── DLL Injection ──

    def inject_dll(self, dll_path: str) -> bool:
        """
        Inject DLL ke process game via CreateRemoteThread + LoadLibrary.
        Untuk fitur yang butuh akses penuh ke GameAssembly.dll.

        dll_path: absolute path ke DLL yang mau di-inject
        """
        handle = self._get_handle(write_access=True)
        if not handle:
            return False

        if not Path(dll_path).exists():
            logger.error(f"DLL not found: {dll_path}")
            return False

        dll_path_bytes = dll_path.encode("utf-8") + b"\x00"
        path_len = len(dll_path_bytes)

        # 1. Allocate memory in target process for DLL path
        remote_addr = self._kernel32.VirtualAllocEx(
            self._handle, None, path_len,
            MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE
        )
        if not remote_addr:
            logger.error("VirtualAllocEx failed")
            return False

        # 2. Write DLL path to allocated memory
        written = ctypes.c_size_t(0)
        self._kernel32.WriteProcessMemory(
            self._handle, remote_addr, dll_path_bytes, path_len,
            ctypes.byref(written)
        )

        # 3. Get LoadLibraryA address
        kernel32_handle = self._kernel32.GetModuleHandleW("kernel32.dll")
        loadlib_addr = self._kernel32.GetProcAddress(kernel32_handle, b"LoadLibraryA")

        # 4. Create remote thread calling LoadLibraryA(dll_path)
        thread_id = ctypes.c_ulong(0)
        thread = self._kernel32.CreateRemoteThread(
            self._handle, None, 0,
            loadlib_addr, remote_addr,
            0, ctypes.byref(thread_id)
        )

        if thread:
            logger.info(f"✅ DLL injected! Thread ID: {thread_id.value}")
            self._kernel32.WaitForSingleObject(thread, 5000)
            self._kernel32.CloseHandle(thread)
            
            # Clean up allocated memory
            self._kernel32.VirtualFreeEx(self._handle, remote_addr, 0, 0x8000)  # MEM_RELEASE
            return True

        logger.error("❌ CreateRemoteThread failed")
        self._kernel32.VirtualFreeEx(self._handle, remote_addr, 0, 0x8000)
        return False

    def call_game_function(self, function_rva: int, *args) -> bool:
        """
        Call a function in GameAssembly.dll in the game process.
        Uses CreateRemoteThread to execute the function.

        function_rva: RVA offset dari function di GameAssembly.dll
        args: arguments to pass (simplified — complex args need a shellcode approach)
        """
        # This requires shellcode generation which is complex
        # For now, use a simplified approach via LoadLibrary'd helper DLL
        logger.warning("Remote function call requires DLL injection + shellcode")
        logger.warning(f"Target function RVA: 0x{function_rva:X}")
        return False


# ── Singleton ──
_injector = None


def get_injector() -> _Injector:
    global _injector
    if _injector is None:
        _injector = _Injector()
    return _injector


def is_available() -> bool:
    return get_injector().is_available()


def set_lp(player: int, value: int) -> bool:
    """Set LP player. 0=self, 1=opponent."""
    return get_injector().set_lp(player, value)


def instant_win() -> bool:
    """Set opponent LP to 0."""
    return get_injector().instant_win()


def set_game_title(title: str) -> bool:
    """Set window title Master Duel."""
    return get_injector().set_game_title(title)


def pause_game() -> bool:
    """Suspend game process."""
    return get_injector().pause_game()


def resume_game() -> bool:
    """Resume game process."""
    return get_injector().resume_game()


def inject_dll(dll_path: str) -> bool:
    """Inject DLL ke game process."""
    return get_injector().inject_dll(dll_path)
