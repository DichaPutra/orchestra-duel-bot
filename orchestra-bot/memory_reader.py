"""
memory_reader.py — Memory Hacking Engine (Opsi B)

Read game state (LP, Phase, Turn) langsung dari memory process Master Duel.
Windows-only (ReadProcessMemory). Fallback ke vision kalo gagal.

Approach:
  1. Cari process "MasterDuel.exe"
  2. Pattern scan: cari LP (int32 = 8000), Phase (int32 = 0-5)
  3. Cache alamat yang ditemukan biar gak scan ulang tiap kali
  4. Baca value langsung pake ReadProcessMemory

Reduce vision calls ~70% karena LP + Phase + Turn dibaca dari memory (gratis).
Vision dipanggil cuma pas state kartu berubah.
"""
import ctypes
import ctypes.wintypes
import logging
import struct
import sys
from typing import Optional

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

# AOB patterns (little-endian int32)
LP_START_VALUE = 8000       # 0x1F40
LP_PACKED = struct.pack("<I", LP_START_VALUE)  # bytes: 40 1F 00 00


class WinMemoryReader:
    """
    Windows memory reader via ReadProcessMemory.
    Only works on Windows with MasterDuel.exe running.
    """

    def __init__(self):
        self._handle = None
        self._pid = None
        self._gameassembly_base = None

        # Cached addresses (found via pattern scan, persisted per session)
        self._lp_self_addr = None
        self._lp_opponent_addr = None
        self._phase_addr = None
        self._turn_addr = None
        self._hand_count_addr = None

        # Service module handle (kernel32)
        self._kernel32 = ctypes.windll.kernel32 if sys.platform == "win32" else None

    def is_available(self) -> bool:
        """Check if memory reader is available (Windows + process found)."""
        if sys.platform != "win32":
            return False
        if self._handle is not None:
            return True
        return self._find_process() is not None

    # ── Process Management ──

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
        """Open handle ke Master Duel process."""
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
        """Read a 32-bit signed integer from process memory."""
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
        """Read a 16-bit signed integer."""
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
                    # Extract base address from the map entry
                    addr_str = mmap.addr.split("-")[0] if "-" in mmap.addr else mmap.addr
                    return int(addr_str, 16)
        except Exception as e:
            logger.debug(f"Module base lookup error: {e}")
        return None

    # ── Pattern Scanner ──

    def scan_for_value(self, value: int, value_size: int = 4) -> list[int]:
        """
        Scan seluruh process memory untuk mencari nilai tertentu.
        Return list alamat yang cocok.

        value_size: 1, 2, atau 4 bytes
        """
        if not self._handle:
            return []

        packed = struct.pack(f"<{'I' if value_size == 4 else 'H' if value_size == 2 else 'B'}", value)
        results = []

        try:
            import psutil
            proc = psutil.Process(self._pid)
            for mmap in proc.memory_maps(grouped=False):
                try:
                    addr_start = int(mmap.addr.split("-")[0], 16)
                    addr_end = int(mmap.addr.split("-")[1], 16)
                    size = addr_end - addr_start

                    # Skip tiny regions
                    if size < 4096 or size > 10 * 1024 * 1024:
                        continue

                    # Skip non-readable/guard pages
                    perms = (mmap.perms or "").lower()
                    if "r" not in perms or "g" in perms or "w" not in perms:
                        continue

                    buf = self.read_bytes(addr_start, min(size, 256 * 1024))
                    if buf is None:
                        continue

                    # Search for pattern
                    offset = 0
                    while True:
                        pos = buf.find(packed, offset)
                        if pos == -1:
                            break
                        results.append(addr_start + pos)
                        offset = pos + value_size

                except (ValueError, OverflowError):
                    continue
        except Exception as e:
            logger.debug(f"Memory scan error: {e}")

        return results

    def _scan_regions_for_lp(self) -> tuple:
        """
        Scan memory untuk mencari nilai LP (8000).
        Return (self_addr, opponent_addr) atau None.

        Strategi: cari pasangan nilai 8000 yang berdekatan (< 64 bytes apart).
        """
        candidates = self.scan_for_value(LP_START_VALUE, 4)

        # Filter pasangan yang berdekatan (self + opponent LP biasanya bersebelahan)
        pairs = []
        for i, addr in enumerate(candidates):
            for j in range(i + 1, len(candidates)):
                diff = abs(candidates[j] - addr)
                if 1 <= diff <= 128:
                    pairs.append((addr, candidates[j]))

        if pairs:
            # Ambil pasangan pertama (most likely correct)
            return pairs[0]
        return (None, None)

    # ── High-Level State Readers ──

    def get_lp(self, player: int = 0) -> Optional[int]:
        """Get LP untuk player (0=self, 1=opponent). Return None kalo gagal."""
        if not self._handle:
            return None

        # Auto-scan kalo belum punya alamat
        if self._lp_self_addr is None:
            self._lp_self_addr, self._lp_opponent_addr = self._scan_regions_for_lp()
            if self._lp_self_addr is not None:
                # Verify: baca lagi dan pastikan nilainya 8000 (valid)
                v = self.read_int32(self._lp_self_addr)
                if v == LP_START_VALUE:
                    logger.info(f"Found LP addresses: self=0x{self._lp_self_addr:X}, "
                                f"opponent=0x{self._lp_opponent_addr:X}")
                else:
                    self._lp_self_addr = None
                    self._lp_opponent_addr = None

        addr = self._lp_self_addr if player == 0 else self._lp_opponent_addr
        if addr:
            return self.read_int32(addr)
        return None

    def get_phase(self) -> Optional[int]:
        """
        Get current phase dari memory.
        Return Phase enum value (0-5) atau None.

        Phase enum: Draw=0, Standby=1, Main1=2, Battle=3, Main2=4, End=5
        """
        if not self._handle:
            return None

        if self._phase_addr is None:
            self._phase_addr = self._find_phase_address()

        if self._phase_addr:
            val = self.read_int32(self._phase_addr)
            if val is not None and 0 <= val <= 7:
                return val
        return None

    def _find_phase_address(self) -> Optional[int]:
        """
        Cari alamat Phase di memory.

        Strategi: setelah LP ditemukan, scanning area sekitarnya untuk nilai 0-5.
        Phase biasanya berada di offset tertentu dari DuelManager struct.
        """
        if self._lp_self_addr is None:
            self.get_lp()  # Trigger scan

        if self._lp_self_addr:
            # Phase biasanya ~100-500 bytes dari LP addr
            # Coba scan di sekitar LP
            for offset in range(-512, 512, 4):
                addr = self._lp_self_addr + offset
                val = self.read_int32(addr)
                if val is not None and 0 <= val <= 5:
                    # Verifikasi: baca 2x untuk mastiin stabil
                    val2 = self.read_int32(addr)
                    if val == val2 and val >= 0:
                        logger.info(f"Found Phase address: 0x{addr:X} (offset={offset:+d})")
                        return addr

        return None

    def is_my_turn(self) -> Optional[bool]:
        """Check apakah giliran kita."""
        if not self._handle:
            return None

        if self._turn_addr is None:
            self._turn_addr = self._find_turn_address()

        if self._turn_addr:
            val = self.read_int32(self._turn_addr)
            if val is not None:
                return val != 0
        return None

    def _find_turn_address(self) -> Optional[int]:
        """
        Cari alamat Turn flag.

        Turn flag biasanya di sekitar Phase address.
        Nilai: 0 = opponent, 1 = self.
        """
        if self._phase_addr is None:
            self.get_phase()

        if self._phase_addr:
            for offset in range(-256, 256, 4):
                addr = self._phase_addr + offset
                val = self.read_int32(addr)
                if val is not None and val in (0, 1):
                    # Verifikasi konsistensi
                    val2 = self.read_int32(addr)
                    if val == val2:
                        logger.info(f"Found Turn address: 0x{addr:X} (offset={offset:+d})")
                        return addr

        return None

    def get_hand_count(self) -> Optional[int]:
        """
        Get jumlah kartu di hand kita.
        Kurang reliable via memory — fallback tetap vision kalo gagal.
        """
        if not self._handle:
            return None

        if self._hand_count_addr is None:
            self._hand_count_addr = self._find_hand_count_address()

        if self._hand_count_addr:
            val = self.read_int32(self._hand_count_addr)
            if val is not None and 0 <= val <= 15:
                return val
        return None

    def _find_hand_count_address(self) -> Optional[int]:
        """
        Cari hand count address.

        Hand count biasanya di area yang sama dengan LP/Phase.
        Nilai biasanya 5-6 di awal duel.
        """
        if self._lp_self_addr is None:
            self.get_lp()

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


# ── Singleton ──
_reader = None


def get_reader() -> WinMemoryReader:
    """Dapatkan singleton memory reader."""
    global _reader
    if _reader is None:
        _reader = WinMemoryReader()
    return _reader


def init() -> bool:
    """Initialize memory reader. Cari proses dan open handle."""
    reader = get_reader()
    if reader._handle:
        return True
    return reader.open()


def read_lp(player: int = 0) -> Optional[int]:
    """Read LP player tertentu dari memory. None = gagal."""
    reader = get_reader()
    return reader.get_lp(player)


def read_phase() -> Optional[int]:
    """Read current phase dari memory. None = gagal."""
    reader = get_reader()
    return reader.get_phase()


def read_is_my_turn() -> Optional[bool]:
    """Read turn flag. None = gagal."""
    reader = get_reader()
    return reader.is_my_turn()


def read_hand_count() -> Optional[int]:
    """Read hand count. None = gagal."""
    reader = get_reader()
    return reader.get_hand_count()


def is_available() -> bool:
    """Check apakah memory reader tersedia (Windows + process running)."""
    reader = get_reader()
    return reader.is_available()
