# memory_reader.py — Enhanced Memory Hacking Engine (Option B)
"""
Memory reader for Master Duel on Windows. Provides fast access to LP, phase, turn flag, and hand count.
Features:
- Loads cached offsets from `config/offsets.yaml` if present.
- Automatically rescans memory after consecutive read failures.
- Exposes `refresh_memory()` RPC for LLM bot to force a full rescan.
- Uses `memory_scanner` for advanced address discovery.
"""

import ctypes
import ctypes.wintypes
import logging
import struct
import sys
import os
import json
from pathlib import Path
from typing import Optional

# Import the advanced scanner utilities
try:
    import memory_scanner
except ImportError:
    from . import memory_scanner

logger = logging.getLogger("orchestra.memory")

# ── Constants ──
PROCESS_VM_READ = 0x0010
PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_ALL_ACCESS = 0x1F0FFF

# Phase enum values
PHASE_DRAW = 0
PHASE_STANDBY = 1
PHASE_MAIN1 = 2
PHASE_BATTLE = 3
PHASE_MAIN2 = 4
PHASE_END = 5

# AOB patterns
LP_START_VALUE = 8000  # 0x1F40
LP_PACKED = struct.pack("<I", LP_START_VALUE)  # bytes: 40 1F 00 00


class WinMemoryReader:
    """Windows memory reader via ReadProcessMemory.
    Only works on Windows with MasterDuel.exe running.
    """

    def __init__(self):
        # Process handle / PID
        self._handle = None
        self._pid = None
        self._gameassembly_base = None

        # Cached addresses (loaded from config/offsets.yaml if present)
        self._lp_self_addr = None
        self._lp_opponent_addr = None
        self._phase_addr = None
        self._turn_addr = None
        self._hand_count_addr = None

        # Failure counters for auto‑rescan
        self._read_failures = 0
        self._max_failures = 3

        # Service module handle (kernel32)
        self._kernel32 = ctypes.windll.kernel32 if sys.platform == "win32" else None

    # ── Process Management ──
    def is_available(self) -> bool:
        """Check if memory reader is available (Windows + process found)."""
        if sys.platform != "win32":
            return False
        if self._handle is not None:
            return True
        return self._find_process() is not None

    def _find_process(self) -> Optional[int]:
        """Find MasterDuel.exe PID."""
        try:
            import psutil
            for proc in psutil.process_iter(["pid", "name"]):
                name = proc.info["name"] or ""
                if "masterduel" in name.lower() or "yu-gi-oh" in name.lower():
                    pid = proc.info["pid"]
                    logger.info(f"Found Master Duel process: PID={pid}, name={name}")
                    return pid
        except ImportError:
            logger.warning("psutil not installed, can't find process")
        except Exception as e:
            logger.debug(f"Process search error: {e}")
        return None

    def open(self, pid: Optional[int] = None) -> bool:
        """Open a handle to Master Duel process and load cached offsets if available."""
        if sys.platform != "win32":
            logger.warning("Memory reader only works on Windows")
            return False

        if pid is None:
            pid = self._find_process()
        if pid is None:
            logger.warning("Master Duel process not found")
            return False

        self._pid = pid
        self._handle = self._kernel32.OpenProcess(
            PROCESS_VM_READ | PROCESS_QUERY_INFORMATION,
            False, pid
        )
        if not self._handle:
            err = ctypes.get_last_error()
            logger.error(f"OpenProcess failed: error {err}")
            self._handle = None
            return False

        logger.info(f"Opened handle to PID {pid} (handle={self._handle})")
        # Load any previously saved offsets
        self._load_cached_offsets()
        return True

    def close(self):
        """Close process handle."""
        if self._handle:
            self._kernel32.CloseHandle(self._handle)
            self._handle = None
            self._pid = None
            logger.info("Process handle closed")

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    # ── Core Memory Operations ──
    def read_int32(self, address: int) -> Optional[int]:
        """Read a 32‑bit signed integer from process memory."""
        if not self._handle:
            return None
        buf = ctypes.create_string_buffer(4)
        bytes_read = ctypes.c_size_t(0)
        success = self._kernel32.ReadProcessMemory(
            self._handle, ctypes.c_void_p(address),
            buf, 4, ctypes.byref(bytes_read)
        )
        if success and bytes_read.value == 4:
            return struct.unpack("<i", buf.raw)[0]
        return None

    def read_int16(self, address: int) -> Optional[int]:
        """Read a 16‑bit signed integer."""
        if not self._handle:
            return None
        buf = ctypes.create_string_buffer(2)
        bytes_read = ctypes.c_size_t(0)
        success = self._kernel32.ReadProcessMemory(
            self._handle, ctypes.c_void_p(address),
            buf, 2, ctypes.byref(bytes_read)
        )
        if success and bytes_read.value == 2:
            return struct.unpack("<h", buf.raw)[0]
        return None

    def read_bool(self, address: int) -> Optional[bool]:
        """Read a boolean (1 byte)."""
        if not self._handle:
            return None
        val = self.read_int32(address)
        if val is not None:
            return bool(val & 0xFF)
        return None

    def read_bytes(self, address: int, size: int) -> Optional[bytes]:
        """Read raw bytes from process memory."""
        if not self._handle:
            return None
        buf = ctypes.create_string_buffer(size)
        bytes_read = ctypes.c_size_t(0)
        success = self._kernel32.ReadProcessMemory(
            self._handle, ctypes.c_void_p(address),
            buf, size, ctypes.byref(bytes_read)
        )
        if success and bytes_read.value == size:
            return buf.raw[:bytes_read.value]
        return None

    # ── Module Info ──
    def _get_module_base(self, module_name: str) -> Optional[int]:
        """Get base address of a module in the target process (via psutil)."""
        try:
            import psutil
            proc = psutil.Process(self._pid)
            for mmap in proc.memory_maps(grouped=False):
                path = mmap.path or ""
                if module_name.lower() in path.lower():
                    addr_str = mmap.addr.split("-")[0] if "-" in mmap.addr else mmap.addr
                    return int(addr_str, 16)
        except Exception as e:
            logger.debug(f"Module base lookup error: {e}")
        return None

    # ── Pattern Scanner ── (delegates to memory_scanner for heavy lifting)
    def scan_for_value(self, value: int, value_size: int = 4) -> list[int]:
        """Scan entire process memory for a given integer value.
        Returns a list of matching addresses.
        """
        if not self._handle:
            return []
        packed = struct.pack(f"<{'I' if value_size == 4 else 'H' if value_size == 2 else 'B'}", value)
        results = []
        try:
            is_64bit = sys.maxsize > 2**32
            if is_64bit:
                class MEMORY_BASIC_INFORMATION(ctypes.Structure):
                    _fields_ = [
                        ("BaseAddress", ctypes.c_ulonglong),
                        ("AllocationBase", ctypes.c_ulonglong),
                        ("AllocationProtect", ctypes.wintypes.DWORD),
                        ("alignment1", ctypes.wintypes.DWORD),
                        ("RegionSize", ctypes.c_ulonglong),
                        ("State", ctypes.wintypes.DWORD),
                        ("Protect", ctypes.wintypes.DWORD),
                        ("Type", ctypes.wintypes.DWORD),
                        ("alignment2", ctypes.wintypes.DWORD),
                    ]
            else:
                class MEMORY_BASIC_INFORMATION(ctypes.Structure):
                    _fields_ = [
                        ("BaseAddress", ctypes.c_ulong),
                        ("AllocationBase", ctypes.c_ulong),
                        ("AllocationProtect", ctypes.wintypes.DWORD),
                        ("RegionSize", ctypes.c_ulong),
                        ("State", ctypes.wintypes.DWORD),
                        ("Protect", ctypes.wintypes.DWORD),
                        ("Type", ctypes.wintypes.DWORD),
                    ]

            mbi = MEMORY_BASIC_INFORMATION()
            addr = 0
            
            PAGE_NOACCESS = 0x01
            PAGE_GUARD = 0x100
            MEM_COMMIT = 0x1000
            WRITABLE_MASK = 0x04 | 0x08 | 0x40 | 0x80

            VirtualQueryEx = self._kernel32.VirtualQueryEx
            VirtualQueryEx.argtypes = [
                ctypes.c_void_p,
                ctypes.c_void_p,
                ctypes.POINTER(MEMORY_BASIC_INFORMATION),
                ctypes.c_size_t
            ]
            VirtualQueryEx.restype = ctypes.c_size_t

            while True:
                res = VirtualQueryEx(
                    self._handle,
                    ctypes.c_void_p(addr),
                    ctypes.byref(mbi),
                    ctypes.sizeof(mbi)
                )
                if res == 0:
                    break
                
                is_committed = mbi.State == MEM_COMMIT
                is_writable = (mbi.Protect & WRITABLE_MASK) != 0
                is_guarded = (mbi.Protect & PAGE_GUARD) != 0
                is_noaccess = (mbi.Protect & PAGE_NOACCESS) != 0
                
                if is_committed and is_writable and not is_guarded and not is_noaccess:
                    reg_addr = mbi.BaseAddress
                    reg_size = mbi.RegionSize
                    
                    # Read memory in chunks to avoid massive allocations
                    chunk_size = 10 * 1024 * 1024
                    offset = 0
                    while offset < reg_size:
                        read_size = min(chunk_size, reg_size - offset)
                        buf = self.read_bytes(reg_addr + offset, read_size)
                        if buf:
                            pos = 0
                            while True:
                                pos = buf.find(packed, pos)
                                if pos == -1:
                                    break
                                results.append(reg_addr + offset + pos)
                                pos += value_size
                        offset += read_size
                
                addr = mbi.BaseAddress + mbi.RegionSize
        except Exception as e:
            logger.error(f"Memory scan error: {e}")
        return results

    # ── Cached Offset Helpers ──
    def _load_cached_offsets(self):
        """Load saved offsets from `config/offsets.yaml` if the file exists."""
        try:
            cfg_path = Path(__file__).resolve().parents[1] / "config" / "offsets.yaml"
            if cfg_path.exists():
                with open(cfg_path, "r") as f:
                    data = json.load(f)
                self._lp_self_addr = data.get("lp_self")
                self._lp_opponent_addr = data.get("lp_opponent")
                self._phase_addr = data.get("phase")
                self._turn_addr = data.get("is_my_turn")
                self._hand_count_addr = data.get("hand_count")
                logger.info(f"Loaded cached memory offsets from {cfg_path}")
        except Exception as e:
            logger.debug(f"Failed to load cached offsets: {e}")

    def _apply_scanner_results(self, results: dict):
        """Persist addresses discovered by `memory_scanner` and update internal fields."""
        self._lp_self_addr = results.get("lp_self")
        self._lp_opponent_addr = results.get("lp_opponent")
        self._phase_addr = results.get("phase")
        self._turn_addr = results.get("is_my_turn")
        self._hand_count_addr = results.get("hand_count")
        cfg_path = Path(__file__).resolve().parents[1] / "config" / "offsets.yaml"
        os.makedirs(os.path.dirname(cfg_path), exist_ok=True)
        with open(cfg_path, "w") as f:
            json.dump({
                "lp_self": self._lp_self_addr,
                "lp_opponent": self._lp_opponent_addr,
                "phase": self._phase_addr,
                "is_my_turn": self._turn_addr,
                "hand_count": self._hand_count_addr,
            }, f, indent=2)
        logger.info(f"Saved discovered offsets to {cfg_path}")

    def _rescan_all(self):
        """Run the full advanced scanner and refresh cached addresses."""
        try:
            results = memory_scanner.find_all_addresses(self)
            if results:
                self._apply_scanner_results(results)
                logger.info("Memory addresses rescanned and updated.")
            else:
                logger.warning("Rescan did not find any addresses.")
        except Exception as e:
            logger.error(f"Rescan failed: {e}")
        return self

    def refresh_memory(self) -> bool:
        """Public API to force a full scan of memory addresses. Returns True on success."""
        if not self.is_available():
            return False
        self._rescan_all()
        return self._lp_self_addr is not None

    # ── High‑Level State Readers ──
    def _scan_regions_for_lp(self) -> tuple:
        """Legacy scan used only when cache is missing. Delegates to memory_scanner for consistency."""
        candidates = self.scan_for_value(LP_START_VALUE, 4)
        pairs = []
        for i, addr in enumerate(candidates):
            for j in range(i + 1, len(candidates)):
                diff = abs(candidates[j] - addr)
                if 1 <= diff <= 128:
                    pairs.append((addr, candidates[j]))
        if pairs:
            return pairs[0]
        return (None, None)

    def _find_phase_address(self) -> Optional[int]:
        """Find Phase address based on cached LP address or full scan if needed."""
        if self._lp_self_addr is None:
            self._load_cached_offsets()
            if self._lp_self_addr is None:
                results = memory_scanner.find_all_addresses(self)
                self._apply_scanner_results(results)
        if self._lp_self_addr:
            for offset in range(-512, 512, 4):
                addr = self._lp_self_addr + offset
                val = self.read_int32(addr)
                if val is not None and 0 <= val <= 5:
                    val2 = self.read_int32(addr)
                    if val == val2 and val >= 0:
                        logger.info(f"Found Phase address: 0x{addr:X} (offset={offset:+d})")
                        return addr
        return None

    def _find_turn_address(self) -> Optional[int]:
        """Find Turn flag address; reuse Phase address if possible."""
        if self._phase_addr is None:
            self._phase_addr = self._find_phase_address()
        if self._phase_addr:
            for offset in range(-256, 256, 4):
                addr = self._phase_addr + offset
                val = self.read_int32(addr)
                if val is not None and val in (0, 1):
                    val2 = self.read_int32(addr)
                    if val == val2:
                        logger.info(f"Found Turn address: 0x{addr:X} (offset={offset:+d})")
                        return addr
        return None

    def _find_hand_count_address(self) -> Optional[int]:
        """Find hand‑count address using LP as anchor."""
        if self._lp_self_addr is None:
            self._lp_self_addr, _ = self._scan_regions_for_lp()
        if self._lp_self_addr:
            for offset in range(-1024, 1024, 4):
                addr = self._lp_self_addr + offset
                val = self.read_int32(addr)
                if val is not None and 4 <= val <= 8:
                    val2 = self.read_int32(addr)
                    if val == val2:
                        logger.info(f"Found Hand Count address: 0x{addr:X}")
                        return addr
        return None

    def get_lp(self, player: int = 0) -> Optional[int]:
        """Get LP for a player, trigger auto‑rescan on repeated failures."""
        if not self._handle:
            return None
        if self._lp_self_addr is None:
            self._lp_self_addr, self._lp_opponent_addr = self._scan_regions_for_lp()
        addr = self._lp_self_addr if player == 0 else self._lp_opponent_addr
        val = self.read_int32(addr) if addr else None
        if val is None:
            self._read_failures += 1
            if self._read_failures >= self._max_failures:
                logger.warning("LP read failed multiple times; attempting full rescan.")
                self._rescan_all()
                self._read_failures = 0
        else:
            self._read_failures = 0
        return val

    def get_phase(self) -> Optional[int]:
        if not self._handle:
            return None
        if self._phase_addr is None:
            self._phase_addr = self._find_phase_address()
        if self._phase_addr:
            val = self.read_int32(self._phase_addr)
            if val is not None:
                return val
        self._rescan_all()
        return None

    def is_my_turn(self) -> Optional[bool]:
        if not self._handle:
            return None
        if self._turn_addr is None:
            self._turn_addr = self._find_turn_address()
        if self._turn_addr:
            val = self.read_int32(self._turn_addr)
            if val is not None:
                return val != 0
        self._rescan_all()
        return None

    def get_hand_count(self) -> Optional[int]:
        if not self._handle:
            return None
        if self._hand_count_addr is None:
            self._hand_count_addr = self._find_hand_count_address()
        if self._hand_count_addr:
            val = self.read_int32(self._hand_count_addr)
            if val is not None and 0 <= val <= 15:
                return val
        self._rescan_all()
        return None

# ── Singleton ──
_reader = None

def get_reader() -> WinMemoryReader:
    """Get the singleton memory reader instance."""
    global _reader
    if _reader is None:
        _reader = WinMemoryReader()
    return _reader

def init() -> bool:
    """Initialize memory reader. Find process and open handle."""
    reader = get_reader()
    if reader._handle:
        return True
    return reader.open()

def read_lp(player: int = 0) -> Optional[int]:
    """Read LP for a given player (0=self, 1=opponent)."""
    return get_reader().get_lp(player)

def read_phase() -> Optional[int]:
    """Read current game phase."""
    return get_reader().get_phase()

def read_is_my_turn() -> Optional[bool]:
    """Read whether it is our turn."""
    return get_reader().is_my_turn()

def read_hand_count() -> Optional[int]:
    """Read hand count."""
    return get_reader().get_hand_count()

def is_available() -> bool:
    """Check whether the memory reader is ready for use."""
    return get_reader().is_available()
