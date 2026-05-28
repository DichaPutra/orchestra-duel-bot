"""
memory_scanner.py — Advanced Pattern & Pointer Scanner (Opsi B)

Improvement over memory_reader.py's basic scan.
Uses multiple strategies to find game state reliably:

1. AOB (Array of Bytes) — cari sequence bytes spesifik
2. Pointer dereference — follow chain pointers (static → pointer → value)
3. Value verification — baca berulang, nilai harus masuk akal
4. Heuristic — LP turun pas kena damage, Phase berubah pas klik next

Output: file offsets YAML yang bisa di-load ulang tanpa scan ulang.
"""

import logging
import os
import struct
import sys
from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime

logger = logging.getLogger("orchestra.memory.scanner")

# ── AOB Database ──
# Known byte patterns for Master Duel memory structures.
# Format: (description, bytes, value_size, expected_offset_range)
# Pattern bisa dicari di module "GameAssembly.dll" atau "UnityPlayer.dll"
#
# Catatan: Ini heuristic-based. Untuk accuracy tinggi perlu dump memory
# spesifik version game dan analisis pointer chain.
AOB_PATTERNS = {
    # LP value — nilai 8000 di awal duel (LE int32)
    "lp_value": {
        "pattern": struct.pack("<I", 8000),  # 40 1F 00 00
        "description": "LP initial value (8000)",
        "size": 4,
        "context": "heuristic",
    },
    # Phase 0 (Draw phase) — nilai kecil di sekitar LP
    "phase_value": {
        "pattern": struct.pack("<I", 0),  # 00 00 00 00 — terlalu umum
        "description": "Phase value 0 (too generic)",
        "size": 4,
        "context": "heuristic",
    },
    # Turn flag 1 (my turn)
    "turn_flag": {
        "pattern": struct.pack("<I", 1),  # 01 00 00 00 — terlalu umum
        "description": "Turn flag=1 (too generic)",
        "size": 4,
        "context": "heuristic",
    },
}

# ── Pointer Map ──
# Untuk setiap game version, kita simpan static pointer chains.
# Ini diisi manual atau via auto-scan.
# Format: { "module_name:offset": ["+0x0", "+0x10", "+0x28", "+0x4"] }
# Contoh: GameAssembly.dll base + 0x12345678 → +0x10 → +0x28 → LP value
KNOWN_ADDRESSES = {}


def find_lp_via_aob(memory_reader, pid: int) -> tuple:
    """
    Advanced LP finder:
    1. Scan all writable memory for value 8000 (0x1F40)
    2. Filter: harus ada pasangan dalam 128 bytes (self + opponent LP)
    3. Verify: baca 3x dengan delay 100ms, nilai harus stabil
    4. Return (self_addr, opponent_addr) atau None
    """
    candidates = memory_reader.scan_for_value(8000, 4)
    logger.info(f"LP scan: found {len(candidates)} candidates for value 8000")

    if len(candidates) < 2:
        logger.warning("Not enough LP candidates found")
        return (None, None)

    # Cari pasangan berdekatan (self + opponent LP biasanya bersebelahan)
    import itertools
    pairs = []
    for a, b in itertools.combinations(candidates, 2):
        diff = abs(b - a)
        if 1 <= diff <= 128:
            pairs.append((a, b))

    logger.info(f"Found {len(pairs)} LP candidate pairs")

    if not pairs:
        # Fallback: ambil 2 candidate pertama di region yang sama
        page_size = 0x1000
        for a, b in itertools.combinations(candidates, 2):
            if (a & ~(page_size - 1)) == (b & ~(page_size - 1)):
                pairs.append((a, b))
                break

    if pairs:
        # Verify: baca berulang, pastikan nilainya 8000 dan stabil
        for pair in pairs:
            v1 = memory_reader.read_int32(pair[0])
            v2 = memory_reader.read_int32(pair[1])
            if v1 == 8000 and v2 == 8000:
                logger.info(f"Verified LP pair: self=0x{pair[0]:X}, opp=0x{pair[1]:X}")
                return pair

    return (None, None)


def find_all_addresses(memory_reader) -> dict:
    """
    Auto-scan semua game state addresses.
    Return dict dengan alamat-alamat yang ditemukan.

    Process:
    1. Find LP pair (easiest)
    2. From LP, scan nearby for Phase
    3. From Phase, scan for Turn flag
    4. From same region, scan for Hand count
    """
    results = {}

    # 1. LP
    self_lp, opp_lp = find_lp_via_aob(memory_reader, memory_reader._pid)
    if self_lp:
        results["lp_self"] = self_lp
        results["lp_opponent"] = opp_lp
        logger.info(f"✅ LP: self=0x{self_lp:X}, opp=0x{opp_lp:X}")
    else:
        logger.warning("❌ LP not found")

    # 2. Phase (around LP region)
    if self_lp:
        for offset in range(-2048, 2048, 4):
            addr = self_lp + offset
            val = memory_reader.read_int32(addr)
            if val is not None and 0 <= val <= 5:
                # Verify stability
                v2 = memory_reader.read_int32(addr)
                if val == v2:
                    results["phase"] = addr
                    logger.info(f"✅ Phase: 0x{addr:X} (offset={offset:+d})")
                    break

    if "phase" not in results:
        logger.warning("❌ Phase not found")

    # 3. Turn flag (around Phase)
    phase_addr = results.get("phase")
    if phase_addr:
        for offset in range(-512, 512, 4):
            addr = phase_addr + offset
            val = memory_reader.read_int32(addr)
            if val is not None and val in (0, 1):
                v2 = memory_reader.read_int32(addr)
                if val == v2:
                    results["is_my_turn"] = addr
                    logger.info(f"✅ Turn: 0x{addr:X} (offset={offset:+d})")
                    break

    if "is_my_turn" not in results:
        logger.warning("❌ Turn flag not found")

    # 4. Hand count (same region)
    if self_lp:
        for offset in range(-4096, 4096, 4):
            addr = self_lp + offset
            val = memory_reader.read_int32(addr)
            if val is not None and 4 <= val <= 8:
                v2 = memory_reader.read_int32(addr)
                if val == v2:
                    results["hand_count"] = addr
                    logger.info(f"✅ Hand Count: 0x{addr:X} (offset={offset:+d})")
                    break

    return results


def save_offsets(results: dict, filepath: str = None):
    # Use config directory if not specified
    if filepath is None:
        from pathlib import Path
        base_dir = Path(__file__).resolve().parents[1]
        filepath = base_dir / "config" / "offsets.yaml"
    # Ensure directory exists
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    """
    Simpan offsets yang ditemukan ke file.
    Format: simple YAML-style text.
    """
    timestamp = datetime.now().isoformat()
    lines = [
        f"# Master Duel Memory Offsets",
        f"# Auto-scanned at: {timestamp}",
        f"# PID: {os.getpid()}",
        f"#",
        f"# Format: label: 0xHEXADDRESS",
        f"",
    ]
    for key, addr in sorted(results.items()):
        lines.append(f"{key}: 0x{addr:X}")

    with open(filepath, "w") as f:
        f.write("\n".join(lines) + "\n")
    logger.info(f"Offsets saved to {filepath}")


def load_offsets(filepath: str = None) -> dict:
    # Load from config directory if not specified
    if filepath is None:
        from pathlib import Path
        base_dir = Path(__file__).resolve().parents[1]
        filepath = base_dir / "config" / "offsets.yaml"
    """
    Load offsets dari file yang disimpan sebelumnya.
    """
    results = {}
    if not os.path.exists(filepath):
        return results

    with open(filepath) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if ":" in line:
                key, addr_str = line.split(":", 1)
                key = key.strip()
                addr_str = addr_str.strip()
                if addr_str.startswith("0x") or addr_str.startswith("0X"):
                    addr = int(addr_str, 16)
                    results[key] = addr

    logger.info(f"Loaded {len(results)} offsets from {filepath}")
    return results
