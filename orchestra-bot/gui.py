"""
Orchestra Duel Bot GUI Manager
Premium Tkinter-based Windows desktop manager for Orchestra Duel Bot.

Modified to include comprehensive Cheats tab mirroring JMaster Duel Bot features.
"""

import os
import sys
import re
import time
import queue
import threading
import subprocess
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk

# ── Design Colors ──
BG_MAIN = "#1e1e24"
BG_PANEL = "#2b2b36"
BG_INPUT = "#141416"
FG_TEXT = "#ffffff"
FG_MUTED = "#a0a0ab"
ACCENT_GREEN = "#10b981"
ACCENT_RED = "#ef4444"
ACCENT_BLUE = "#3b82f6"
ACCENT_PURPLE = "#8b5cf6"
ACCENT_ORANGE = "#f59e0b"
ACCENT_CYAN = "#06b6d4"
CONSOLE_BG = "#0f0f12"
CONSOLE_FG = "#34d399"
DISABLED_BG = "#2a2a35"
DISABLED_FG = "#6b6b7a"


class OrchestraGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Orchestra Duel Bot Manager")
        self.root.geometry("1280x800")
        self.root.configure(bg=BG_MAIN)
        self.root.minsize(1100, 700)

        # State
        self.running_process = None
        self.log_queue = queue.Queue()
        self.show_keys = {}
        self.active_tab = "config"

        # Load injector module (will fail gracefully on macOS)
        self.injector = None
        self._load_injector()

        self.setup_styles()
        self.create_layout()
        self.load_settings()
        self.root.after(100, self.poll_logs)

    def _load_injector(self):
        """Try to load memory injector. Returns silently on macOS."""
        try:
            import memory_injector
            self.injector = memory_injector
        except Exception:
            self.injector = None

    def setup_styles(self):
        self.style = ttk.Style()
        self.style.theme_use("clam")
        self.style.configure(".", background=BG_MAIN, foreground=FG_TEXT)
        self.style.configure("TFrame", background=BG_MAIN)
        self.style.configure("TLabel", background=BG_MAIN, foreground=FG_TEXT, font=("Segoe UI", 10))
        self.style.configure("Panel.TFrame", background=BG_PANEL)
        self.style.configure("TCombobox", fieldbackground=BG_INPUT, background=BG_PANEL,
                             foreground=FG_TEXT, arrowcolor=FG_TEXT)
        self.root.option_add("*TCombobox*Listbox.background", BG_INPUT)
        self.root.option_add("*TCombobox*Listbox.foreground", FG_TEXT)
        self.root.option_add("*TCombobox*Listbox.selectBackground", ACCENT_BLUE)

    def create_layout(self):
        # Top Warning Bar
        self.warning_bar = tk.Frame(self.root, bg=ACCENT_PURPLE, height=30)
        self.warning_bar.pack(side="top", fill="x")
        self.warning_bar.pack_propagate(False)
        warning_label = tk.Label(self.warning_bar,
            text="⚠️ JALANKAN SEBAGAI ADMINISTRATOR jika Master Duel dijalankan sebagai Administrator. "
                 "Fitur Write Memory/Inject membutuhkan akses penuh ke process game.",
            fg="#ffffff", bg=ACCENT_PURPLE, font=("Segoe UI", 9, "bold"))
        warning_label.pack(expand=True)

        # Container
        self.container = tk.Frame(self.root, bg=BG_MAIN)
        self.container.pack(fill="both", expand=True, padx=10, pady=10)

        # ── SIDEBAR ──
        self.sidebar = tk.Frame(self.container, bg=BG_PANEL, width=240)
        self.sidebar.pack(side="left", fill="y", padx=(0, 10))
        self.sidebar.pack_propagate(False)

        tk.Label(self.sidebar, text="ORCHESTRA BOT", fg=ACCENT_GREEN, bg=BG_PANEL,
                 font=("Segoe UI", 16, "bold")).pack(pady=(20, 5))
        tk.Label(self.sidebar, text="Yu-Gi-Oh! Duel Manager", fg=FG_MUTED, bg=BG_PANEL,
                 font=("Segoe UI", 9, "italic")).pack(pady=(0, 20))

        # Status Box
        self.status_box = tk.Frame(self.sidebar, bg="#1a1a24", height=70, bd=1, relief="solid")
        self.status_box.pack(fill="x", padx=15, pady=10)
        self.status_box.pack_propagate(False)
        tk.Label(self.status_box, text="STATUS SISTEM", fg=FG_MUTED, bg="#1a1a24",
                 font=("Segoe UI", 8)).pack(pady=(8, 2))
        self.status_lbl = tk.Label(self.status_box, text="STOPPED", fg=ACCENT_RED, bg="#1a1a24",
                                   font=("Segoe UI", 14, "bold"))
        self.status_lbl.pack()

        # Control Buttons
        btn_frame = tk.Frame(self.sidebar, bg=BG_PANEL)
        btn_frame.pack(fill="both", expand=True, padx=15, pady=20)

        self.start_btn = self._make_btn(btn_frame, "▶ MULAI DUEL BOT", ACCENT_GREEN, self.start_bot)
        self.start_btn.pack(fill="x", pady=4, ipady=6)

        self.stop_btn = self._make_btn(btn_frame, "⏹ HENTIKAN BOT", ACCENT_RED, self.stop_process, state="disabled")
        self.stop_btn.pack(fill="x", pady=4, ipady=6)

        self.calibrate_btn = self._make_btn(btn_frame, "⚙ KALIBRASI MEMORI", ACCENT_PURPLE, self.run_calibration)
        self.calibrate_btn.pack(fill="x", pady=4, ipady=6)

        self.clear_btn = self._make_btn(btn_frame, "🗑 BERSIHKAN LOGS", "#4b5563", self.clear_logs)
        self.clear_btn.pack(fill="x", pady=4, ipady=6)

        tk.Label(self.sidebar, text="v2.0 - Cheats Edition", fg=FG_MUTED, bg=BG_PANEL,
                 font=("Segoe UI", 8)).pack(side="bottom", pady=10)

        # ── MAIN PANEL ──
        self.main_panel = tk.Frame(self.container, bg=BG_MAIN)
        self.main_panel.pack(side="right", fill="both", expand=True)

        # Tab Headers
        self.tabs_header = tk.Frame(self.main_panel, bg=BG_MAIN)
        self.tabs_header.pack(fill="x", pady=(0, 10))

        self._tab_buttons = {}
        tab_defs = [
            ("⚙ Konfigurasi", "config"),
            ("🖥 Terminal", "logs"),
            ("⚡ Cheats", "cheats"),
        ]
        for text, name in tab_defs:
            btn = tk.Button(self.tabs_header, text=text, bg=BG_MAIN if name != "config" else BG_PANEL,
                          fg=FG_MUTED if name != "config" else FG_TEXT, relief="flat",
                          font=("Segoe UI", 10, "bold"),
                          command=lambda n=name: self.switch_tab(n), padx=15, pady=5)
            btn.pack(side="left", padx=(0, 5))
            self._tab_buttons[name] = btn

        # Tab Content
        self.tab_content = tk.Frame(self.main_panel, bg=BG_PANEL, bd=1, relief="solid",
                                    highlightbackground="#3e3e4a")
        self.tab_content.pack(fill="both", expand=True)

        # Build all tabs
        self._build_config_tab()
        self._build_logs_tab()
        self._build_cheats_tab()

        # Show config by default
        self._show_frame("config")

    def _make_btn(self, parent, text, bg, cmd, state="normal"):
        return tk.Button(parent, text=text, bg=bg, fg="#ffffff",
                        activebackground=bg, activeforeground="#ffffff",
                        font=("Segoe UI", 10, "bold"), relief="flat", bd=0,
                        command=cmd, state=state)

    # ═══════════════════════════════════════════
    # TAB 1: CONFIG
    # ═══════════════════════════════════════════

    def _build_config_tab(self):
        self.config_frame = tk.Frame(self.tab_content, bg=BG_PANEL, padx=20, pady=20)

        # Scroll
        self.config_canvas = tk.Canvas(self.config_frame, bg=BG_PANEL, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self.config_frame, orient="vertical", command=self.config_canvas.yview)
        self.scrollable_config = tk.Frame(self.config_canvas, bg=BG_PANEL)
        self.scrollable_config.bind("<Configure>",
            lambda e: self.config_canvas.configure(scrollregion=self.config_canvas.bbox("all")))
        self.config_canvas.create_window((0, 0), window=self.scrollable_config, anchor="nw")
        self.config_canvas.configure(yscrollcommand=scrollbar.set)
        self.config_canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self._build_config_form(self.scrollable_config)

    def _build_config_form(self, parent):
        p = parent
        tk.Label(p, text="PENGATURAN MODE & PROVIDER", fg=ACCENT_GREEN, bg=BG_PANEL,
                 font=("Segoe UI", 11, "bold")).grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 15))

        # Bot Mode
        tk.Label(p, text="Bot Mode:", bg=BG_PANEL).grid(row=1, column=0, sticky="w", pady=6)
        self.bot_mode_val = tk.StringVar(value="hybrid")
        self.bot_mode_combo = ttk.Combobox(p, textvariable=self.bot_mode_val,
            values=["hybrid", "memory_only", "cheats_only"], state="readonly", width=25)
        self.bot_mode_combo.grid(row=1, column=1, sticky="w", pady=6, padx=(10, 0))
        tk.Label(p, text="hybrid (RAM + Vision) | memory_only | cheats_only", fg=FG_MUTED, bg=BG_PANEL,
                 font=("Segoe UI", 8)).grid(row=1, column=2, sticky="w", padx=(10, 0))

        # LLM Provider
        tk.Label(p, text="LLM Provider:", bg=BG_PANEL).grid(row=2, column=0, sticky="w", pady=6)
        self.llm_provider_val = tk.StringVar(value="gemini")
        ttk.Combobox(p, textvariable=self.llm_provider_val,
            values=["gemini", "openai", "openrouter", "groq", "deepseek"],
            state="readonly", width=25).grid(row=2, column=1, sticky="w", pady=6, padx=(10, 0))
        tk.Label(p, text="Provider untuk Text Decision Maker bot", fg=FG_MUTED, bg=BG_PANEL,
                 font=("Segoe UI", 8)).grid(row=2, column=2, sticky="w", padx=(10, 0))

        ttk.Separator(p, orient="horizontal").grid(row=3, column=0, columnspan=3, sticky="we", pady=15)
        tk.Label(p, text="API KEYS & MODEL SETTINGS", fg=ACCENT_GREEN, bg=BG_PANEL,
                 font=("Segoe UI", 11, "bold")).grid(row=4, column=0, columnspan=3, sticky="w", pady=(0, 10))

        self.key_entries = {}
        self.model_entries = {}

        providers = [
            ("GEMINI", "Gemini API Key:", "GEMINI_API_KEY", "GEMINI_MODEL", "gemini-2.5-flash"),
            ("OPENAI", "OpenAI API Key:", "OPENAI_API_KEY", "OPENAI_MODEL", "gpt-4o-mini"),
            ("OPENROUTER", "OpenRouter Key:", "OPENROUTER_API_KEY", "OPENROUTER_MODEL", "google/gemini-2.5-flash"),
            ("GROQ", "Groq API Key:", "GROQ_API_KEY", "GROQ_MODEL", "llama3-70b-8192"),
            ("DEEPSEEK", "DeepSeek API Key:", "DEEPSEEK_API_KEY", "DEEPSEEK_MODEL", "deepseek-chat"),
        ]

        row = 5
        for prefix, label, env_key, env_model, default_model in providers:
            tk.Label(p, text=label, bg=BG_PANEL).grid(row=row, column=0, sticky="w", pady=5)
            key_var = tk.StringVar()
            entry = tk.Entry(p, textvariable=key_var, show="*", bg=BG_INPUT, fg=FG_TEXT,
                            insertbackground="#ffffff", relief="flat", width=35)
            entry.grid(row=row, column=1, sticky="w", pady=5, padx=(10, 0))
            self.key_entries[env_key] = key_var
            self.show_keys[env_key] = False

            toggle_btn = tk.Button(p, text="👁", bg=BG_PANEL, fg=FG_TEXT, relief="flat", bd=0,
                                 activebackground=BG_PANEL, activeforeground=ACCENT_BLUE,
                                 command=lambda k=env_key, e=entry: self._toggle_key(k, e))
            toggle_btn.grid(row=row, column=1, sticky="e", pady=5)

            tk.Label(p, text="Model Override:", bg=BG_PANEL, fg=FG_MUTED,
                     font=("Segoe UI", 9)).grid(row=row+1, column=0, sticky="w", padx=(20, 0), pady=(0, 8))
            model_var = tk.StringVar()
            tk.Entry(p, textvariable=model_var, bg=BG_INPUT, fg=FG_TEXT,
                    insertbackground="#ffffff", relief="flat", width=35).grid(
                    row=row+1, column=1, sticky="w", pady=(0, 8), padx=(10, 0))
            self.model_entries[env_model] = model_var
            tk.Label(p, text=f"Bawaan: {default_model}", fg=FG_MUTED, bg=BG_PANEL,
                     font=("Segoe UI", 8, "italic")).grid(row=row+1, column=2, sticky="w", padx=(10, 0), pady=(0, 8))
            row += 2

        ttk.Separator(p, orient="horizontal").grid(row=row, column=0, columnspan=3, sticky="we", pady=15)
        btn_frame = tk.Frame(p, bg=BG_PANEL)
        btn_frame.grid(row=row+1, column=0, columnspan=3, sticky="w", pady=(5, 20), padx=(10, 0))

        self.save_btn = self._make_btn(btn_frame, "💾 SIMPAN KONFIGURASI", ACCENT_BLUE, self.save_settings)
        self.save_btn.pack(side="left", padx=(0, 10), ipady=6)

        self.test_btn = self._make_btn(btn_frame, "🧪 TEST KONEKSI LLM", ACCENT_PURPLE, self.test_llm_connection)
        self.test_btn.pack(side="left", ipady=6)

    def _toggle_key(self, env_key, entry_widget):
        is_visible = self.show_keys[env_key]
        entry_widget.configure(show="" if is_visible else "*")
        self.show_keys[env_key] = not is_visible

    # ═══════════════════════════════════════════
    # TAB 2: LOGS
    # ═══════════════════════════════════════════

    def _build_logs_tab(self):
        self.logs_frame = tk.Frame(self.tab_content, bg=CONSOLE_BG, padx=10, pady=10)
        self.log_text = tk.Text(self.logs_frame, bg=CONSOLE_BG, fg=CONSOLE_FG,
                               insertbackground="#ffffff", font=("Consolas", 10),
                               relief="flat", wrap="word", state="disabled")
        scroll = ttk.Scrollbar(self.logs_frame, orient="vertical", command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scroll.set)
        self.log_text.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        self.append_log("[GUI] Orchestra Duel Bot GUI Manager siap.\n[GUI] Konfigurasi `.env` dimuat.\n\n")

    # ═══════════════════════════════════════════
    # TAB 3: CHEATS (Full JMaster-style)
    # ═══════════════════════════════════════════

    def _build_cheats_tab(self):
        """Build the Cheats tab mirroring JMaster Duel Bot v1.431 layout."""
        self.cheats_frame = tk.Frame(self.tab_content, bg=BG_PANEL, padx=15, pady=15)
        self.cheat_vars = {}  # Store checkbox variables

        # ── TOP BUTTONS: Quit/Restart/Pause/Resume ──
        top_btn_frame = tk.Frame(self.cheats_frame, bg=BG_PANEL)
        top_btn_frame.pack(fill="x", pady=(0, 15))

        # Row 1: Quit Game | Restart Game
        row1 = tk.Frame(top_btn_frame, bg=BG_PANEL)
        row1.pack(fill="x", pady=2)
        self._make_top_btn(row1, "⛔ QUIT GAME", ACCENT_RED, self._cheat_quit_game).pack(
            side="left", fill="x", expand=True, padx=(0, 5), ipady=8)
        self._make_top_btn(row1, "🔄 RESTART GAME", ACCENT_ORANGE, self._cheat_restart_game).pack(
            side="left", fill="x", expand=True, padx=(5, 0), ipady=8)

        # Row 2: Pause Game | Resume Game
        row2 = tk.Frame(top_btn_frame, bg=BG_PANEL)
        row2.pack(fill="x", pady=2)
        self._make_top_btn(row2, "⏸ PAUSE GAME", "#6366f1", self._cheat_pause_game).pack(
            side="left", fill="x", expand=True, padx=(0, 5), ipady=8)
        self._make_top_btn(row2, "▶ RESUME GAME", ACCENT_GREEN, self._cheat_resume_game).pack(
            side="left", fill="x", expand=True, padx=(5, 0), ipady=8)

        # ── MAIN CHEAT CONTENT (Scrollable) ──
        canvas = tk.Canvas(self.cheats_frame, bg=BG_PANEL, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self.cheats_frame, orient="vertical", command=canvas.yview)
        self.cheat_content = tk.Frame(canvas, bg=BG_PANEL)
        self.cheat_content.bind("<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=self.cheat_content, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # ── SECTION: SOLO ──
        self._cheat_section("Solo:", ACCENT_GREEN)

        # Solo features in columns
        solo_frame = tk.Frame(self.cheat_content, bg=BG_PANEL)
        solo_frame.pack(fill="x", pady=(0, 15))

        solo_left = tk.Frame(solo_frame, bg=BG_PANEL)
        solo_left.pack(side="left", fill="both", expand=True, padx=(0, 10))

        solo_mid = tk.Frame(solo_frame, bg=BG_PANEL)
        solo_mid.pack(side="left", fill="both", expand=True, padx=(5, 10))

        solo_right = tk.Frame(solo_frame, bg=BG_PANEL)
        solo_right.pack(side="left", fill="both", expand=True, padx=(5, 0))

        # Left column
        self._cheat_check(solo_left, "Instant Win", "cheat_instant_win",
                         "Set opponent LP to 0", ACCENT_GREEN)
        self._cheat_check(solo_left, "Force Auto Dueling", "cheat_force_auto",
                         "Click Auto Duel button")
        self._cheat_check(solo_left, "Duel Skipper", "cheat_skipper",
                         "DONATOR ONLY — Skip to end screen", donator=True)

        # Duel Result row
        result_frame = tk.Frame(solo_left, bg=BG_PANEL)
        result_frame.pack(fill="x", pady=3)
        self.cheat_vars["cheat_duel_result"] = tk.BooleanVar(value=False)
        tk.Checkbutton(result_frame, text="Duel Result:", variable=self.cheat_vars["cheat_duel_result"],
                      bg=BG_PANEL, fg=FG_TEXT, selectcolor=BG_PANEL,
                      font=("Segoe UI", 10)).pack(side="left")
        self.cheat_duel_result_combo = ttk.Combobox(result_frame, values=["Win", "Lose", "Draw"],
            state="readonly", width=8)
        self.cheat_duel_result_combo.set("Win")
        self.cheat_duel_result_combo.pack(side="left", padx=(5, 0))

        # Your LP row
        lp_frame = tk.Frame(solo_left, bg=BG_PANEL)
        lp_frame.pack(fill="x", pady=3)
        tk.Label(lp_frame, text="Your LP:", bg=BG_PANEL, fg=FG_TEXT,
                font=("Segoe UI", 10)).pack(side="left")
        self.cheat_lp_var = tk.StringVar(value="8000")
        tk.Entry(lp_frame, textvariable=self.cheat_lp_var, bg=BG_INPUT, fg=FG_TEXT,
                insertbackground="#ffffff", relief="flat", width=8).pack(side="left", padx=(5, 5))
        self._make_small_btn(lp_frame, "Set", ACCENT_BLUE, self._cheat_set_lp).pack(side="left")

        # Middle column
        self._cheat_check(solo_mid, "Disable Deck Shuffling", "cheat_no_shuffle",
                         "Requires DLL injection")
        self._cheat_check(solo_mid, "Play Speed Duels", "cheat_speed_duel",
                         "Requires DLL injection")
        self._cheat_check(solo_mid, "Disable Card Animations", "cheat_no_animation",
                         "Hentikan animasi kartu (skippable via click)")

        # Right column
        self._cheat_check(solo_right, "Reveal Cards", "cheat_reveal",
                         "Tampilkan kartu lawan")
        self._cheat_check(solo_right, "Allow Illegal Decks", "cheat_illegal_deck",
                         "DONATOR ONLY", donator=True)
        self._cheat_check(solo_right, "Force Deckout Win", "cheat_deckout",
                         "Atur deck count lawan ke 0", ACCENT_CYAN)
        self._cheat_check(solo_right, "Play with Reversed Decks", "cheat_reverse_deck",
                         "Requires DLL injection")
        self._cheat_check(solo_right, "Disable Camera Shaking", "cheat_no_shake",
                         "Matikan efek kamera gemerincing")

        # ── SECTION: PvP ──
        self._cheat_section("PvP:", ACCENT_RED)

        pvp_frame = tk.Frame(self.cheat_content, bg=BG_PANEL)
        pvp_frame.pack(fill="x", pady=(0, 15))

        pvp_left = tk.Frame(pvp_frame, bg=BG_PANEL)
        pvp_left.pack(side="left", fill="both", expand=True, padx=(0, 10))
        pvp_right = tk.Frame(pvp_frame, bg=BG_PANEL)
        pvp_right.pack(side="left", fill="both", expand=True, padx=(5, 0))

        self._cheat_check(pvp_left, "PvP See Own Top Deck [patched]", "cheat_pvp_topdeck",
                         "PATCHED — TIDAK BERFUNGSI", patched=True)
        self._cheat_check(pvp_left, "Room Freezer", "cheat_room_freeze",
                         "DONATOR ONLY", donator=True)
        self._cheat_check(pvp_right, "Duel Crasher [patched]", "cheat_crasher",
                         "PATCHED — TIDAK BERFUNGSI", patched=True)
        self._cheat_check(pvp_right, "Coin Toss Exploit [patched]", "cheat_cointoss",
                         "PATCHED — TIDAK BERFUNGSI", patched=True)
        self._cheat_check(pvp_frame, "PvP Spectator Mode Reveal Cards [patched]", "cheat_spectator",
                         "PATCHED — TIDAK BERFUNGSI", patched=True, full_width=True)

        # ── SECTION: Universal ──
        self._cheat_section("Universal (Solo + PvP):", ACCENT_BLUE)

        univ_frame = tk.Frame(self.cheat_content, bg=BG_PANEL)
        univ_frame.pack(fill="x", pady=(0, 15))

        univ_left = tk.Frame(univ_frame, bg=BG_PANEL)
        univ_left.pack(side="left", fill="both", expand=True, padx=(0, 10))
        univ_right = tk.Frame(univ_frame, bg=BG_PANEL)
        univ_right.pack(side="left", fill="both", expand=True, padx=(5, 0))

        self._cheat_check(univ_left, "Disable Battle Damage Animation", "cheat_no_dmg_anim")
        self._cheat_check(univ_left, "Invalidate Losses [patched]", "cheat_no_loss",
                         "PATCHED", patched=True)
        self._cheat_check(univ_left, "Force Replay Controls", "cheat_replay",
                         "DONATOR ONLY", donator=True)
        self._cheat_check(univ_right, "Force Fastest Duel Speed", "cheat_fast_speed")
        self._cheat_check(univ_right, "Disconnect Duel [Patched]", "cheat_disconnect",
                         "PATCHED — TIDAK BERFUNGSI", patched=True)

        # Card Rarity
        rarity_frame = tk.Frame(self.cheat_content, bg=BG_PANEL)
        rarity_frame.pack(fill="x", pady=3)
        self.cheat_vars["cheat_card_rarity"] = tk.BooleanVar(value=False)
        tk.Checkbutton(rarity_frame, text="Card Rarity:",
                      variable=self.cheat_vars["cheat_card_rarity"],
                      bg=BG_PANEL, fg=FG_TEXT, selectcolor=BG_PANEL,
                      font=("Segoe UI", 10)).pack(side="left")
        self.cheat_rarity_combo = ttk.Combobox(rarity_frame,
            values=["Basic", "Rare", "Super Rare", "Ultra Rare", "Royal"],
            state="readonly", width=12)
        self.cheat_rarity_combo.set("Basic")
        self.cheat_rarity_combo.pack(side="left", padx=(5, 0))

        # Usage Tutorial
        tutorial_frame = tk.Frame(self.cheat_content, bg=BG_PANEL)
        tutorial_frame.pack(fill="x", pady=3)
        self._make_small_btn(tutorial_frame, "📖 Usage Tutorial", ACCENT_PURPLE,
                           self._cheat_tutorial).pack(side="left", padx=(10, 0))

        # ── SECTION: Speed Hack ──
        self._cheat_section("Speed Hack:", ACCENT_ORANGE)

        speed_frame = tk.Frame(self.cheat_content, bg=BG_PANEL)
        speed_frame.pack(fill="x", pady=(0, 10))

        tk.Label(speed_frame, text="Speed Multiplier:", bg=BG_PANEL, fg=FG_TEXT,
                font=("Segoe UI", 10)).pack(side="left")
        self.speed_val = tk.StringVar(value="3")
        tk.Spinbox(speed_frame, from_=1, to=20, textvariable=self.speed_val,
                  bg=BG_INPUT, fg=FG_TEXT, buttonbackground=BG_PANEL,
                  relief="flat", width=5).pack(side="left", padx=(5, 10))

        self._make_small_btn(speed_frame, "🚀 Inject Speed Hack", ACCENT_ORANGE,
                           self._cheat_speed_inject).pack(side="left", padx=(5, 0))
        self._make_small_btn(speed_frame, "⏹ Unload", ACCENT_RED,
                           self._cheat_speed_unload).pack(side="left", padx=(5, 0))

        self._cheat_check(self.cheat_content, "Automatically Inject Speed Hack", "cheat_auto_speed",
                         "DONATOR ONLY — Inject otomatis saat duel dimulai", donator=True, full_width=True)

        # ── SECTION: Game Title ──
        title_frame = tk.Frame(self.cheat_content, bg=BG_PANEL)
        title_frame.pack(fill="x", pady=10)

        self.cheat_vars["cheat_set_title"] = tk.BooleanVar(value=True)
        tk.Checkbutton(title_frame, text="Set Game Title Text:", variable=self.cheat_vars["cheat_set_title"],
                      bg=BG_PANEL, fg=FG_TEXT, selectcolor=BG_PANEL,
                      font=("Segoe UI", 10)).pack(side="left")
        self.cheat_title_var = tk.StringVar(value="Yu-Gi-Oh! Master Duel")
        tk.Entry(title_frame, textvariable=self.cheat_title_var, bg=BG_INPUT, fg=FG_TEXT,
                insertbackground="#ffffff", relief="flat", width=30).pack(side="left", padx=(5, 5))
        self._make_small_btn(title_frame, "Set Title", ACCENT_BLUE,
                           self._cheat_set_title).pack(side="left")

        # ── SECTION: Player Name ──
        name_frame = tk.Frame(self.cheat_content, bg=BG_PANEL)
        name_frame.pack(fill="x", pady=5)

        tk.Label(name_frame, text="Player Name:", bg=BG_PANEL, fg=FG_TEXT,
                font=("Segoe UI", 10)).pack(side="left")
        self.cheat_name_var = tk.StringVar(value="OrchestraBot")
        tk.Entry(name_frame, textvariable=self.cheat_name_var, bg=BG_INPUT, fg=FG_TEXT,
                insertbackground="#ffffff", relief="flat", width=25).pack(side="left", padx=(5, 5))
        self._make_small_btn(name_frame, "Set Name", ACCENT_BLUE,
                           self._cheat_set_name).pack(side="left", padx=(5, 0))

        self._cheat_check(self.cheat_content, "Automatically Set Name", "cheat_auto_name",
                         "Set nama player otomatis setiap duel", full_width=True)

        # ── INJECTION CONTROLS ──
        ttk.Separator(self.cheat_content, orient="horizontal").pack(fill="x", pady=15)

        inj_frame = tk.Frame(self.cheat_content, bg=BG_PANEL)
        inj_frame.pack(fill="x", pady=5)

        tk.Label(inj_frame, text="DLL Injection:", bg=BG_PANEL, fg=ACCENT_PURPLE,
                font=("Segoe UI", 10, "bold")).pack(side="left", padx=(0, 10))

        self.inject_path_var = tk.StringVar(value="OrchestraHelper.dll")
        tk.Entry(inj_frame, textvariable=self.inject_path_var, bg=BG_INPUT, fg=FG_TEXT,
                insertbackground="#ffffff", relief="flat", width=35).pack(side="left", padx=(5, 5))
        self._make_small_btn(inj_frame, "💉 Inject DLL", ACCENT_PURPLE,
                           self._cheat_inject_dll).pack(side="left", padx=(5, 5))
        self._make_small_btn(inj_frame, "📁 Browse", "#4b5563",
                           self._cheat_browse_dll).pack(side="left")

        # ── APPLY ALL BUTTON ──
        ttk.Separator(self.cheat_content, orient="horizontal").pack(fill="x", pady=15)

        apply_frame = tk.Frame(self.cheat_content, bg=BG_PANEL)
        apply_frame.pack(fill="x", pady=10)

        self._make_btn(apply_frame, "⚡ APPLY ALL CHEATS", ACCENT_PURPLE,
                      self._cheat_apply_all).pack(side="left", ipady=8, padx=(0, 10))
        self._make_btn(apply_frame, "🔄 Reset All", "#4b5563",
                      self._cheat_reset_all).pack(side="left", ipady=8)

    def _cheat_section(self, title, color):
        """Add a section header."""
        f = tk.Frame(self.cheat_content, bg=BG_PANEL)
        f.pack(fill="x", pady=(15, 5))
        tk.Label(f, text=title, fg=color, bg=BG_PANEL,
                font=("Segoe UI", 12, "bold")).pack(anchor="w", padx=5)

    def _cheat_check(self, parent, text, var_name, tooltip="", color=None, donator=False, patched=False, full_width=False):
        """Add a checkbox with optional status indicators."""
        f = parent if full_width else tk.Frame(parent, bg=BG_PANEL)
        if not full_width:
            f.pack(fill="x", pady=2, anchor="w")

        var = tk.BooleanVar(value=False)
        self.cheat_vars[var_name] = var

        # Determine label style
        fg = FG_TEXT
        if donator:
            fg = ACCENT_ORANGE
            text += " 👑"
        if patched:
            fg = ACCENT_RED
            text += " 🔴"

        cb = tk.Checkbutton(f, text=text, variable=var, bg=BG_PANEL, fg=fg,
                           selectcolor=BG_PANEL, activebackground=BG_PANEL,
                           activeforeground=fg, font=("Segoe UI", 10))
        cb.pack(side="left" if not full_width else "left")

        if tooltip:
            # Add tooltip label
            hint = tk.Label(f, text=f"— {tooltip}", fg=FG_MUTED, bg=BG_PANEL,
                          font=("Segoe UI", 8, "italic"))
            hint.pack(side="left", padx=(5, 0))

        return f

    def _make_top_btn(self, parent, text, bg, cmd):
        return tk.Button(parent, text=text, bg=bg, fg="#ffffff",
                        activebackground=bg, activeforeground="#ffffff",
                        font=("Segoe UI", 10, "bold"), relief="flat", bd=0,
                        command=cmd)

    def _make_small_btn(self, parent, text, bg, cmd):
        return tk.Button(parent, text=text, bg=bg, fg="#ffffff",
                        activebackground=bg, activeforeground="#ffffff",
                        font=("Segoe UI", 9, "bold"), relief="flat", bd=0,
                        padx=8, pady=2, command=cmd)

    # ═══════════════════════════════════════════
    # CHEAT ACTIONS
    # ═══════════════════════════════════════════

    def _cheat_quit_game(self):
        """Quit Master Duel process."""
        self.append_log("[CHEAT] ⛔ Quitting Master Duel...\n")
        import psutil
        for proc in psutil.process_iter(['pid', 'name']):
            if 'masterduel' in proc.info['name'].lower():
                proc.terminate()
                self.append_log(f"[CHEAT] ✅ Master Duel terminated (PID {proc.info['pid']})\n")
                return
        self.append_log("[CHEAT] ❌ Master Duel process not found\n")

    def _cheat_restart_game(self):
        """Restart Master Duel."""
        self._cheat_quit_game()
        time.sleep(2)
        import subprocess as sp
        try:
            # Find steam or direct executable
            paths = [
                r"C:\Program Files\Steam\steamapps\common\Master Duel\MasterDuel.exe",
                r"C:\Program Files (x86)\Steam\steamapps\common\Master Duel\MasterDuel.exe",
            ]
            for p in paths:
                if os.path.exists(p):
                    sp.Popen([p])
                    self.append_log(f"[CHEAT] 🔄 Restarting Master Duel...\n")
                    return
            self.append_log("[CHEAT] ❌ Master Duel executable not found\n")
        except Exception as e:
            self.append_log(f"[CHEAT ERROR] {e}\n")

    def _cheat_pause_game(self):
        """Pause game via NtSuspendProcess."""
        if self.injector:
            if self.injector.pause_game():
                self.append_log("[CHEAT] ⏸️ Game paused\n")
                return
        self.append_log("[CHEAT] ❌ Pause failed. Run as Admin.\n")

    def _cheat_resume_game(self):
        """Resume game."""
        if self.injector:
            if self.injector.resume_game():
                self.append_log("[CHEAT] ▶️ Game resumed\n")
                return
        self.append_log("[CHEAT] ❌ Resume failed. Run as Admin.\n")

    def _cheat_set_lp(self):
        """Set LP via WriteProcessMemory."""
        try:
            value = int(self.cheat_lp_var.get())
            if self.injector and self.injector.set_lp(0, value):
                self.append_log(f"[CHEAT] ✅ LP set to {value}\n")
            else:
                self.append_log("[CHEAT] ❌ Set LP failed. Run calibrate first.\n")
        except ValueError:
            self.append_log("[CHEAT] ❌ Invalid LP value\n")

    def _cheat_set_title(self):
        """Set window title via SetWindowText."""
        title = self.cheat_title_var.get()
        if self.injector and self.injector.set_game_title(title):
            self.append_log(f"[CHEAT] ✅ Window title set to: {title}\n")
        else:
            self.append_log("[CHEAT] ❌ Set title failed. Run as Admin.\n")

    def _cheat_set_name(self):
        """Set player name (cosmetic only — changes window title, not game data)."""
        name = self.cheat_name_var.get()
        # This changes the game window title as a cosmetic effect
        new_title = f"Yu-Gi-Oh! Master Duel — {name}"
        if self.injector and self.injector.set_game_title(new_title):
            self.append_log(f"[CHEAT] ✅ Display name set to: {name}\n")
        else:
            self.append_log("[CHEAT] ❌ Set name failed\n")

    def _cheat_speed_inject(self):
        """Inject speed hack (requires helper DLL)."""
        self.append_log("[CHEAT] 🚀 Speed hack requires a helper DLL with timer modification.\n")
        self.append_log("[CHEAT]    Function: NtQueryPerformanceCounter hook\n")
        self.append_log("[CHEAT]    Not implemented yet — needs custom DLL\n")

    def _cheat_speed_unload(self):
        """Unload speed hack."""
        self.append_log("[CHEAT] ⏹ Speed hack unloaded (placeholder)\n")

    def _cheat_inject_dll(self):
        """Inject DLL into game process."""
        dll_path = self.inject_path_var.get()
        if not os.path.exists(dll_path):
            self.append_log(f"[CHEAT] ❌ DLL not found: {dll_path}\n")
            return
        if self.injector and self.injector.inject_dll(dll_path):
            self.append_log(f"[CHEAT] ✅ DLL injected: {dll_path}\n")
        else:
            self.append_log("[CHEAT] ❌ DLL injection failed. Run as Admin.\n")

    def _cheat_browse_dll(self):
        """Browse for DLL file."""
        from tkinter import filedialog
        path = filedialog.askopenfilename(filetypes=[("DLL files", "*.dll"), ("All files", "*.*")])
        if path:
            self.inject_path_var.set(path)

    def _cheat_tutorial(self):
        """Show usage tutorial."""
        messagebox.showinfo("Orchestra Duel Bot — Usage Tutorial",
            "ORCHESTRA DUEL BOT — CHEAT FEATURES\n\n"
            "✅ Instant Win → Set opponent LP to 0 via WriteProcessMemory\n"
            "✅ Set LP → Write LP value langsung ke memory game\n"
            "✅ Pause/Resume → Suspend/Resume process threads\n"
            "✅ Set Title → Ubah window title game\n"
            "✅ Auto Dueling → Click UI button otomatis\n\n"
            "⚠️ Fitur DONATOR ONLY → Membutuhkan DLL injection\n"
            "   untuk akses penuh ke GameAssembly.dll\n\n"
            "🔴 PATCHED → Fitur sudah tidak berfungsi di versi\n"
            "   Master Duel terbaru (di-patch oleh Konami)\n\n"
            "💡 Jalankan sebagai ADMINISTRATOR untuk hasil maksimal\n"
        )

    def _cheat_apply_all(self):
        """Apply all checked cheat features."""
        self.append_log("[CHEAT] ⚡ Applying all checked cheats...\n")
        
        # Instant Win
        if self.cheat_vars.get("cheat_instant_win", tk.BooleanVar()).get():
            self._cheat_instant_win_action()
        
        # Set LP
        if self.cheat_vars.get("cheat_duel_result", tk.BooleanVar()).get():
            result = self.cheat_duel_result_combo.get()
            if result == "Win":
                self._cheat_instant_win_action()
            self.append_log(f"[CHEAT] Duel Result set to: {result}\n")

        # Other cheats (log only for unimplemented)
        implemented = ["cheat_instant_win", "cheat_duel_result"]
        for var_name, var in self.cheat_vars.items():
            if var.get() and var_name not in implemented:
                self.append_log(f"[CHEAT] ⏳ {var_name} — not yet implemented via memory\n")
        
        self.append_log("[CHEAT] ✅ Apply complete\n")

    def _cheat_instant_win_action(self):
        """Execute instant win."""
        if self.injector and self.injector.instant_win():
            self.append_log("[CHEAT] 💥 INSTANT WIN executed!\n")
        else:
            self.append_log("[CHEAT] ❌ Instant Win failed. Run calibrate + Admin.\n")

    def _cheat_reset_all(self):
        """Reset all checkboxes."""
        for var in self.cheat_vars.values():
            var.set(False)
        self.cheat_lp_var.set("8000")
        self.cheat_duel_result_combo.set("Win")
        self.cheat_rarity_combo.set("Basic")
        self.cheat_title_var.set("Yu-Gi-Oh! Master Duel")
        self.cheat_name_var.set("OrchestraBot")
        self.speed_val.set("3")
        self.append_log("[CHEAT] 🔄 All cheats reset\n")

    # ═══════════════════════════════════════════
    # TAB SWITCHING
    # ═══════════════════════════════════════════

    def switch_tab(self, tab_name):
        self._show_frame(tab_name)
        for name, btn in self._tab_buttons.items():
            is_active = (name == tab_name)
            btn.configure(bg=BG_PANEL if is_active else BG_MAIN,
                         fg=FG_TEXT if is_active else FG_MUTED)

    def _show_frame(self, name):
        """Show the requested frame, hide others."""
        frames = {
            "config": self.config_frame if hasattr(self, 'config_frame') else None,
            "logs": self.logs_frame if hasattr(self, 'logs_frame') else None,
            "cheats": self.cheats_frame if hasattr(self, 'cheats_frame') else None,
        }
        for n, f in frames.items():
            if f:
                try:
                    f.pack_forget()
                except Exception:
                    pass
        target = frames.get(name)
        if target:
            target.pack(fill="both", expand=True)
        self.active_tab = name

    # ═══════════════════════════════════════════
    # SETTINGS I/O
    # ═══════════════════════════════════════════

    def load_settings(self):
        env_path = Path(__file__).parent / ".env"
        if not env_path.exists():
            example = Path(__file__).parent / ".env.example"
            if example.exists():
                import shutil
                shutil.copy(example, env_path)
                self.append_log("[GUI] File `.env` baru dibuat dari `.env.example`.\n")

        settings = {}
        if env_path.exists():
            try:
                for line in env_path.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        settings[k.strip()] = v.strip()
            except Exception as e:
                self.append_log(f"[GUI ERROR] Gagal membaca .env: {e}\n")

        self.bot_mode_val.set(settings.get("BOT_MODE", "hybrid"))
        self.llm_provider_val.set(settings.get("LLM_PROVIDER", "gemini"))
        for env_key, var in self.key_entries.items():
            var.set(settings.get(env_key, ""))
        for env_model, var in self.model_entries.items():
            var.set(settings.get(env_model, ""))

    def save_settings(self):
        env_path = Path(__file__).parent / ".env"
        lines = []
        if env_path.exists():
            try:
                lines = env_path.read_text(encoding="utf-8").splitlines()
            except:
                pass

        updates = {
            "BOT_MODE": self.bot_mode_val.get(),
            "LLM_PROVIDER": self.llm_provider_val.get()
        }
        for env_key, var in self.key_entries.items():
            updates[env_key] = var.get().strip()
        for env_model, var in self.model_entries.items():
            updates[env_model] = var.get().strip()

        key_line_index = {}
        for idx, line in enumerate(lines):
            s = line.strip()
            if s and not s.startswith("#") and "=" in line:
                key = line.split("=", 1)[0].strip()
                key_line_index[key] = idx

        for key, val in updates.items():
            line_str = f"{key}={val}"
            if key in key_line_index:
                lines[key_line_index[key]] = line_str
            else:
                lines.append(line_str)

        try:
            env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            self.append_log("[GUI] ✅ Konfigurasi `.env` disimpan.\n")
            messagebox.showinfo("Sukses", "Konfigurasi `.env` berhasil disimpan!")
        except Exception as e:
            self.append_log(f"[GUI ERROR] Gagal menulis .env: {e}\n")
            messagebox.showerror("Error", f"Gagal menyimpan: {e}")

    # ═══════════════════════════════════════════
    # LLM TEST
    # ═══════════════════════════════════════════

    def test_llm_connection(self):
        provider = self.llm_provider_val.get().strip().lower()
        key = ""
        model = ""
        defaults = {
            "gemini": ("GEMINI_API_KEY", "GEMINI_MODEL", "gemini-2.5-flash"),
            "openai": ("OPENAI_API_KEY", "OPENAI_MODEL", "gpt-4o-mini"),
            "openrouter": ("OPENROUTER_API_KEY", "OPENROUTER_MODEL", "google/gemini-2.5-flash"),
            "groq": ("GROQ_API_KEY", "GROQ_MODEL", "llama3-70b-8192"),
            "deepseek": ("DEEPSEEK_API_KEY", "DEEPSEEK_MODEL", "deepseek-chat"),
        }
        if provider not in defaults:
            messagebox.showerror("Error", f"Provider tidak dikenal: {provider}")
            return

        key_env, model_env, default_model = defaults[provider]
        key = self.key_entries.get(key_env, tk.StringVar()).get().strip()
        model = self.model_entries.get(model_env, tk.StringVar()).get().strip() or default_model

        if not key:
            messagebox.showerror("Error", f"API Key untuk {provider.upper()} masih kosong!")
            return

        self.test_btn.configure(state="disabled", text="⏳ TESTING...")
        self.append_log(f"[GUI] Testing LLM: {provider.upper()} / {model}...\n")
        threading.Thread(target=self._run_llm_test, args=(provider, key, model), daemon=True).start()

    def _run_llm_test(self, provider, key, model):
        import requests
        success = False
        message = ""
        try:
            if provider == "gemini":
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
                resp = requests.post(url, json={
                    "contents": [{"parts": [{"text": "Respond: OK"}]}]
                }, timeout=15)
                if resp.status_code == 200:
                    success = True
                    message = f"✅ Gemini OK — {resp.json()['candidates'][0]['content']['parts'][0]['text'].strip()}"
                else:
                    message = f"❌ Gemini {resp.status_code}: {resp.text[:200]}"
            else:
                endpoints = {
                    "openai": "https://api.openai.com/v1/chat/completions",
                    "deepseek": "https://api.deepseek.com/chat/completions",
                    "openrouter": "https://openrouter.ai/api/v1/chat/completions",
                    "groq": "https://api.groq.com/openai/v1/chat/completions",
                }
                url = endpoints[provider]
                resp = requests.post(url, headers={
                    "Authorization": f"Bearer {key}",
                    "Content-Type": "application/json"
                }, json={
                    "model": model,
                    "messages": [{"role": "user", "content": "Respond: OK"}],
                    "temperature": 0.2
                }, timeout=15)
                if resp.status_code == 200:
                    success = True
                    message = f"✅ {provider.upper()} OK"
                else:
                    message = f"❌ {provider.upper()} {resp.status_code}"
        except Exception as e:
            message = f"❌ Error: {e}"

        self.root.after(0, self._on_llm_test_done, success, message)

    def _on_llm_test_done(self, success, message):
        self.test_btn.configure(state="normal", text="🧪 TEST KONEKSI LLM")
        self.append_log(f"[GUI] {message}\n")
        if success:
            messagebox.showinfo("Sukses", message)
        else:
            messagebox.showerror("Gagal", message)

    # ═══════════════════════════════════════════
    # LOGGING / PROCESS MGMT
    # ═══════════════════════════════════════════

    def append_log(self, text):
        self.log_text.configure(state="normal")
        self.log_text.insert(tk.END, text)
        self.log_text.see(tk.END)
        self.log_text.configure(state="disabled")

    def clear_logs(self):
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", tk.END)
        self.log_text.configure(state="disabled")

    def poll_logs(self):
        while not self.log_queue.empty():
            try:
                line = self.log_queue.get_nowait()
                self.append_log(line)
            except queue.Empty:
                break

        if self.running_process:
            self.status_lbl.configure(text="RUNNING", fg=ACCENT_GREEN)
            self.start_btn.configure(state="disabled")
            self.calibrate_btn.configure(state="disabled")
            self.stop_btn.configure(state="normal")
        else:
            self.status_lbl.configure(text="STOPPED", fg=ACCENT_RED)
            self.start_btn.configure(state="normal")
            self.calibrate_btn.configure(state="normal")
            self.stop_btn.configure(state="disabled")

        self.root.after(100, self.poll_logs)

    def start_bot(self):
        if self.running_process:
            return
        self.switch_tab("logs")
        self.clear_logs()
        self.append_log("[GUI] Menyimpan konfigurasi...\n")
        self.save_settings()
        cmd = [sys.executable, "main.py"]
        self.append_log(f"[GUI] Menjalankan: {' '.join(cmd)}\n")
        self._spawn_process(cmd, "Duel Bot")

    def run_calibration(self):
        if self.running_process:
            return
        if not messagebox.askyesno("Kalibrasi", "Master Duel harus sudah terbuka dan dalam duel.\nLanjutkan?"):
            return
        self.switch_tab("logs")
        self.clear_logs()
        self._spawn_process([sys.executable, "auto_calibrate.py", "--save"], "Auto Calibrator")

    def _spawn_process(self, cmd, label):
        creation_flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        try:
            self.running_process = subprocess.Popen(cmd,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding="utf-8", errors="replace",
                creationflags=creation_flags, env=env, bufsize=1)
            threading.Thread(target=self._read_output, args=(label,), daemon=True).start()
        except Exception as e:
            self.append_log(f"[GUI ERROR] {e}\n")

    def _read_output(self, label):
        for line in self.running_process.stdout:
            clean = re.sub(r'\x1b\[[0-9;]*[mK]', '', line)
            self.log_queue.put(clean)
        self.running_process.wait()
        ret = self.running_process.returncode
        self.log_queue.put(f"\n[GUI] {label} selesai (Exit: {ret})\n")
        self.running_process = None

    def stop_process(self):
        if not self.running_process:
            return
        self.append_log("[GUI] Menghentikan proses...\n")
        self.running_process.terminate()

        def force_kill():
            time.sleep(2)
            if self.running_process:
                try:
                    self.running_process.kill()
                except:
                    pass

        threading.Thread(target=force_kill, daemon=True).start()


if __name__ == "__main__":
    root = tk.Tk()
    app = OrchestraGUI(root)
    root.mainloop()
