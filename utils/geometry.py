"""
Kalkulasi posisi kartu & zona di layar berdasarkan resolusi window.

Semua koordinat relatif terhadap window game (bukan layar penuh).
Butuh kalibrasi manual — setiap resolusi beda.

Cara kalibrasi: aktifkan "Show card positions" di main.py,
nanti bot print koordinat yang diklik + label.
"""
from dataclasses import dataclass


@dataclass
class Layout:
    """Posisi zona utama di board. Semua dalam koordinat window (x, y)."""

    # Hand — 5-6 kartu di baris bawah
    hand_y: int = 0      # Y position
    hand_x_start: int = 0
    hand_x_step: int = 0  # Jarak antar kartu di hand

    # Field — monster & spell/trap zone
    field_monster_y: int = 0
    field_spell_y: int = 0
    field_x_start: int = 0
    field_x_step: int = 0

    # Extra monster zone
    extra_zone_y: int = 0

    # GY / Banished
    gy_x: int = 0
    gy_y: int = 0

    # Phase buttons (Main Phase, Battle, End Turn)
    end_turn_x: int = 0
    end_turn_y: int = 0
    battle_phase_x: int = 0
    battle_phase_y: int = 0

    # Yes/No/OK buttons
    confirm_x: int = 0
    confirm_y: int = 0

    # Chain response
    chain_yes_x: int = 0
    chain_yes_y: int = 0
    chain_no_x: int = 0
    chain_no_y: int = 0

    @classmethod
    def detect(cls, width: int, height: int) -> "Layout":
        """
        Auto-detect layout berdasarkan resolusi.
        Fallback: 1920x1080 (default Master Duel fullscreen).

        TODO: Ukur posisi aktual kartu di resolusi lo.
        Buka setting → display → set ke resolusi yang dipake.
        """
        # 1920x1080 — default layout Master Duel fullscreen
        if (width, height) == (1920, 1080):
            return cls(
                hand_y=950,
                hand_x_start=580,
                hand_x_step=130,
                field_monster_y=600,
                field_spell_y=700,
                field_x_start=680,
                field_x_step=120,
                extra_zone_y=480,
                gy_x=1680,
                gy_y=800,
                end_turn_x=1820,
                end_turn_y=980,
                battle_phase_x=1750,
                battle_phase_y=920,
                confirm_x=960,
                confirm_y=620,
                chain_yes_x=830,
                chain_yes_y=660,
                chain_no_x=1090,
                chain_no_y=660,
            )
        # 1280x720 — windowed mode
        if (width, height) == (1280, 720):
            return cls(
                hand_y=630,
                hand_x_start=380,
                hand_x_step=86,
                field_monster_y=400,
                field_spell_y=460,
                field_x_start=450,
                field_x_step=80,
                extra_zone_y=320,
                gy_x=1120,
                gy_y=530,
                end_turn_x=1210,
                end_turn_y=650,
                battle_phase_x=1160,
                battle_phase_y=610,
                confirm_x=640,
                confirm_y=410,
                chain_yes_x=550,
                chain_yes_y=440,
                chain_no_x=730,
                chain_no_y=440,
            )
        # Unknown — return kosong, perlu kalibrasi manual
        return cls()


def get_card_position(layout: Layout, zone: str, index: int = 0) -> tuple:
    """
    Dapetin (x, y) klik berdasarkan zona & index.

    zone:
      - "hand": index 0-4 (kiri ke kanan)
      - "field_monster": index 0-4 (kiri ke kanan)
      - "field_spell": index 0-4
      - "extra_zone": index 0-0
      - "gy", "end_turn", "battle_phase", "confirm"
      - "chain_yes", "chain_no"
    """
    mapping = {
        "hand": (layout.field_x_start, layout.hand_y,
                 layout.hand_x_step, False),
        "field_monster": (layout.field_x_start, layout.field_monster_y,
                          layout.field_x_step, False),
        "field_spell": (layout.field_x_start, layout.field_spell_y,
                        layout.field_x_step, False),
        "extra_zone": (layout.field_x_start, layout.extra_zone_y,
                       0, False),
        "gy": (layout.gy_x, layout.gy_y, 0, False),
        "end_turn": (layout.end_turn_x, layout.end_turn_y, 0, False),
        "battle_phase": (layout.battle_phase_x, layout.battle_phase_y,
                         0, False),
        "confirm": (layout.confirm_x, layout.confirm_y, 0, False),
        "chain_yes": (layout.chain_yes_x, layout.chain_yes_y, 0, False),
        "chain_no": (layout.chain_no_x, layout.chain_no_y, 0, False),
    }
    if zone not in mapping:
        raise ValueError(f"Unknown zone: {zone}")
    x_base, y, step, _ = mapping[zone]
    x = x_base + (index * step)
    return (int(x), int(y))
