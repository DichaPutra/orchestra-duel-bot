"""
Orchestra Duel Bot GUI Manager
A premium Tkinter-based Windows desktop manager for Orchestra Duel Bot.
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
from tkinter import messagebox
from tkinter import ttk

# Constants for design colors
BG_MAIN = "#1e1e24"       # Sleek dark background
BG_PANEL = "#2b2b36"      # Panel background
BG_INPUT = "#141416"      # Input field background
FG_TEXT = "#ffffff"       # White text
FG_MUTED = "#a0a0ab"      # Gray text
ACCENT_GREEN = "#10b981"  # Emerald Green (Start / Success)
ACCENT_RED = "#ef4444"    # Crimson Red (Stop / Alert)
ACCENT_BLUE = "#3b82f6"   # Cobalt Blue (Info / Save)
ACCENT_PURPLE = "#8b5cf6" # Royal Purple (Calibrate)
CONSOLE_BG = "#0f0f12"    # Dark console background
CONSOLE_FG = "#34d399"    # Vibrant terminal green text

class OrchestraGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Orchestra Duel Bot Manager")
        self.root.geometry("950x700")
        self.root.configure(bg=BG_MAIN)
        self.root.minsize(900, 600)

        # State Variables
        self.running_process = None
        self.log_queue = queue.Queue()
        self.show_keys = {}  # Tracks visibility of each API key (True/False)
        self.active_tab = "config"

        # Apply dark theme styling defaults
        self.setup_styles()

        # Build UI layout
        self.create_layout()

        # Load environment keys
        self.load_settings()

        # Start periodic log checking
        self.root.after(100, self.poll_logs)

    def setup_styles(self):
        """Set up Tkinter style overrides."""
        self.style = ttk.Style()
        self.style.theme_use("clam")
        
        # Configure Notebook / Tab styles
        self.style.configure(".", background=BG_MAIN, foreground=FG_TEXT)
        self.style.configure("TFrame", background=BG_MAIN)
        self.style.configure("TLabel", background=BG_MAIN, foreground=FG_TEXT, font=("Segoe UI", 10))
        self.style.configure("Panel.TFrame", background=BG_PANEL)
        
        # Combobox styling
        self.style.configure("TCombobox", fieldbackground=BG_INPUT, background=BG_PANEL, foreground=FG_TEXT, arrowcolor=FG_TEXT)
        self.root.option_add("*TCombobox*Listbox.background", BG_INPUT)
        self.root.option_add("*TCombobox*Listbox.foreground", FG_TEXT)
        self.root.option_add("*TCombobox*Listbox.selectBackground", ACCENT_BLUE)

    def create_layout(self):
        """Build the split layout: left sidebar and right main panel."""
        # Top Admin Warning Bar
        self.warning_bar = tk.Frame(self.root, bg=ACCENT_PURPLE, height=30)
        self.warning_bar.pack(side="top", fill="x")
        self.warning_bar.pack_propagate(False)
        
        warning_label = tk.Label(
            self.warning_bar,
            text="⚠️ PENTING: Jalankan GUI ini sebagai Administrator jika Master Duel dijalankan sebagai Administrator agar pembacaan RAM & klik berfungsi.",
            fg="#ffffff",
            bg=ACCENT_PURPLE,
            font=("Segoe UI", 9, "bold")
        )
        warning_label.pack(expand=True)

        # Container Frame
        self.container = tk.Frame(self.root, bg=BG_MAIN)
        self.container.pack(fill="both", expand=True, padx=10, pady=10)

        # ── LEFT SIDEBAR (Controls) ──
        self.sidebar = tk.Frame(self.container, bg=BG_PANEL, width=240)
        self.sidebar.pack(side="left", fill="y", padx=(0, 10))
        self.sidebar.pack_propagate(False)

        # App Title
        title_label = tk.Label(
            self.sidebar,
            text="ORCHESTRA BOT",
            fg=ACCENT_GREEN,
            bg=BG_PANEL,
            font=("Segoe UI", 16, "bold")
        )
        title_label.pack(pady=(20, 5))

        subtitle_label = tk.Label(
            self.sidebar,
            text="Yu-Gi-Oh! Duel Manager",
            fg=FG_MUTED,
            bg=BG_PANEL,
            font=("Segoe UI", 9, "italic")
        )
        subtitle_label.pack(pady=(0, 20))

        # Status Indicator Box
        self.status_box = tk.Frame(self.sidebar, bg="#1a1a24", height=70, bd=1, relief="solid")
        self.status_box.pack(fill="x", padx=15, pady=10)
        self.status_box.pack_propagate(False)

        status_title = tk.Label(self.status_box, text="STATUS SISTEM", fg=FG_MUTED, bg="#1a1a24", font=("Segoe UI", 8))
        status_title.pack(pady=(8, 2))

        self.status_lbl = tk.Label(self.status_box, text="STOPPED", fg=ACCENT_RED, bg="#1a1a24", font=("Segoe UI", 14, "bold"))
        self.status_lbl.pack()

        # Control Buttons
        btn_frame = tk.Frame(self.sidebar, bg=BG_PANEL)
        btn_frame.pack(fill="both", expand=True, padx=15, pady=20)

        # Start Bot Button
        self.start_btn = tk.Button(
            btn_frame,
            text="▶ MULAI DUEL BOT",
            bg=ACCENT_GREEN,
            fg="#ffffff",
            activebackground="#059669",
            activeforeground="#ffffff",
            font=("Segoe UI", 10, "bold"),
            relief="flat",
            bd=0,
            command=self.start_bot
        )
        self.start_btn.pack(fill="x", pady=6, ipady=6)

        # Stop Bot Button
        self.stop_btn = tk.Button(
            btn_frame,
            text="⏹ HENTIKAN BOT",
            bg=ACCENT_RED,
            fg="#ffffff",
            activebackground="#dc2626",
            activeforeground="#ffffff",
            font=("Segoe UI", 10, "bold"),
            relief="flat",
            bd=0,
            state="disabled",
            command=self.stop_process
        )
        self.stop_btn.pack(fill="x", pady=6, ipady=6)

        # Calibrate Memory Button
        self.calibrate_btn = tk.Button(
            btn_frame,
            text="⚙ KALIBRASI MEMORI",
            bg=ACCENT_PURPLE,
            fg="#ffffff",
            activebackground="#7c3aed",
            activeforeground="#ffffff",
            font=("Segoe UI", 10, "bold"),
            relief="flat",
            bd=0,
            command=self.run_calibration
        )
        self.calibrate_btn.pack(fill="x", pady=6, ipady=6)

        # Clear Logs Button
        self.clear_btn = tk.Button(
            btn_frame,
            text="🗑 BERSIHKAN LOGS",
            bg="#4b5563",
            fg="#ffffff",
            activebackground="#374151",
            activeforeground="#ffffff",
            font=("Segoe UI", 10, "bold"),
            relief="flat",
            bd=0,
            command=self.clear_logs
        )
        self.clear_btn.pack(fill="x", pady=6, ipady=6)

        # Version stamp
        ver_lbl = tk.Label(self.sidebar, text="v1.2.0 - Hybrid Edition", fg=FG_MUTED, bg=BG_PANEL, font=("Segoe UI", 8))
        ver_lbl.pack(side="bottom", pady=10)


        # ── RIGHT MAIN PANEL (Tabs Content) ──
        self.main_panel = tk.Frame(self.container, bg=BG_MAIN)
        self.main_panel.pack(side="right", fill="both", expand=True)

        # Custom Tab Headers Frame
        self.tabs_header = tk.Frame(self.main_panel, bg=BG_MAIN)
        self.tabs_header.pack(fill="x", pady=(0, 10))

        self.tab_config_btn = tk.Button(
            self.tabs_header,
            text="⚙ Konfigurasi Bot (.env)",
            bg=BG_PANEL,
            fg=FG_TEXT,
            relief="flat",
            font=("Segoe UI", 10, "bold"),
            command=lambda: self.switch_tab("config"),
            padx=15,
            pady=5
        )
        self.tab_config_btn.pack(side="left", padx=(0, 5))

        self.tab_logs_btn = tk.Button(
            self.tabs_header,
            text="🖥 Konsol Live Terminal",
            bg=BG_MAIN,
            fg=FG_MUTED,
            relief="flat",
            font=("Segoe UI", 10, "bold"),
            command=lambda: self.switch_tab("logs"),
            padx=15,
            pady=5
        )
        self.tab_logs_btn.pack(side="left")

        # Tab Content Area Container
        self.tab_content = tk.Frame(self.main_panel, bg=BG_PANEL, bd=1, relief="solid", highlightbackground="#3e3e4a")
        self.tab_content.pack(fill="both", expand=True)

        # ── TAB 1: CONFIGURATION FRAME ──
        self.config_frame = tk.Frame(self.tab_content, bg=BG_PANEL, padx=20, pady=20)
        self.config_frame.pack(fill="both", expand=True)

        # Scrollbar for Config Panel
        self.config_canvas = tk.Canvas(self.config_frame, bg=BG_PANEL, highlightthickness=0)
        self.config_scrollbar = ttk.Scrollbar(self.config_frame, orient="vertical", command=self.config_canvas.yview)
        self.scrollable_config_frame = tk.Frame(self.config_canvas, bg=BG_PANEL)

        self.scrollable_config_frame.bind(
            "<Configure>",
            lambda e: self.config_canvas.configure(scrollregion=self.config_canvas.bbox("all"))
        )
        self.config_canvas.create_window((0, 0), window=self.scrollable_config_frame, anchor="nw")
        self.config_canvas.configure(yscrollcommand=self.config_scrollbar.set)

        self.config_canvas.pack(side="left", fill="both", expand=True)
        self.config_scrollbar.pack(side="right", fill="y")

        self.build_config_form(self.scrollable_config_frame)

        # ── TAB 2: LIVE TERMINAL LOGS FRAME ──
        self.logs_frame = tk.Frame(self.tab_content, bg=CONSOLE_BG, padx=10, pady=10)

        # Console Text Widget
        self.log_text = tk.Text(
            self.logs_frame,
            bg=CONSOLE_BG,
            fg=CONSOLE_FG,
            insertbackground="#ffffff",
            font=("Consolas", 10),
            relief="flat",
            wrap="word",
            state="disabled"
        )
        self.log_scroll = ttk.Scrollbar(self.logs_frame, orient="vertical", command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=self.log_scroll.set)

        self.log_text.pack(side="left", fill="both", expand=True)
        self.log_scroll.pack(side="right", fill="y")

        # Welcome log message
        self.append_log("[GUI] Orchestra Duel Bot GUI Manager siap.\n[GUI] Konfigurasi `.env` dimuat.\n\n")

    def build_config_form(self, parent):
        """Populate the configuration form inputs."""
        # Section title
        sec_title = tk.Label(parent, text="PENGATURAN MODE & PROVIDER", fg=ACCENT_GREEN, bg=BG_PANEL, font=("Segoe UI", 11, "bold"))
        sec_title.grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 15))

        # 1. BOT_MODE
        tk.Label(parent, text="Bot Mode:", bg=BG_PANEL).grid(row=1, column=0, sticky="w", pady=6)
        self.bot_mode_val = tk.StringVar(value="hybrid")
        self.bot_mode_combo = ttk.Combobox(
            parent,
            textvariable=self.bot_mode_val,
            values=["hybrid", "memory_only"],
            state="readonly",
            width=25
        )
        self.bot_mode_combo.grid(row=1, column=1, sticky="w", pady=6, padx=(10, 0))
        
        mode_help = tk.Label(parent, text="hybrid (RAM + Vision) | memory_only (Pure RAM offline)", fg=FG_MUTED, bg=BG_PANEL, font=("Segoe UI", 8))
        mode_help.grid(row=1, column=2, sticky="w", padx=(10, 0))

        # 2. LLM_PROVIDER
        tk.Label(parent, text="LLM Provider:", bg=BG_PANEL).grid(row=2, column=0, sticky="w", pady=6)
        self.llm_provider_val = tk.StringVar(value="gemini")
        self.llm_provider_combo = ttk.Combobox(
            parent,
            textvariable=self.llm_provider_val,
            values=["gemini", "openai", "openrouter", "groq", "deepseek"],
            state="readonly",
            width=25
        )
        self.llm_provider_combo.grid(row=2, column=1, sticky="w", pady=6, padx=(10, 0))
        
        provider_help = tk.Label(parent, text="Provider untuk Text Decision Maker bot", fg=FG_MUTED, bg=BG_PANEL, font=("Segoe UI", 8))
        provider_help.grid(row=2, column=2, sticky="w", padx=(10, 0))

        # Divider
        ttk.Separator(parent, orient="horizontal").grid(row=3, column=0, columnspan=3, sticky="we", pady=15)

        # Section API Keys & Models
        sec_keys_title = tk.Label(parent, text="API KEYS & MODEL SETTINGS", fg=ACCENT_GREEN, bg=BG_PANEL, font=("Segoe UI", 11, "bold"))
        sec_keys_title.grid(row=4, column=0, columnspan=3, sticky="w", pady=(0, 10))

        self.key_entries = {}
        self.model_entries = {}

        # API configurations listing
        providers_keys = [
            ("GEMINI", "Gemini API Key:", "GEMINI_API_KEY", "GEMINI_MODEL", "gemini-2.5-flash"),
            ("OPENAI", "OpenAI API Key:", "OPENAI_API_KEY", "OPENAI_MODEL", "gpt-4o-mini"),
            ("OPENROUTER", "OpenRouter Key:", "OPENROUTER_API_KEY", "OPENROUTER_MODEL", "google/gemini-2.5-flash"),
            ("GROQ", "Groq API Key:", "GROQ_API_KEY", "GROQ_MODEL", "llama3-70b-8192"),
            ("DEEPSEEK", "DeepSeek API Key:", "DEEPSEEK_API_KEY", "DEEPSEEK_MODEL", "deepseek-chat"),
        ]

        curr_row = 5
        for prefix, label_text, env_key, env_model, default_model in providers_keys:
            # Key Label
            tk.Label(parent, text=label_text, bg=BG_PANEL).grid(row=curr_row, column=0, sticky="w", pady=5)
            
            # Key Entry
            key_var = tk.StringVar()
            entry = tk.Entry(parent, textvariable=key_var, show="*", bg=BG_INPUT, fg=FG_TEXT, insertbackground="#ffffff", relief="flat", width=35)
            entry.grid(row=curr_row, column=1, sticky="w", pady=5, padx=(10, 0))
            self.key_entries[env_key] = key_var
            self.show_keys[env_key] = False

            # Toggle Visibility Button
            toggle_btn = tk.Button(
                parent,
                text="👁",
                bg=BG_PANEL,
                fg=FG_TEXT,
                relief="flat",
                bd=0,
                activebackground=BG_PANEL,
                activeforeground=ACCENT_BLUE,
                command=lambda k=env_key, e=entry: self.toggle_key_visibility(k, e)
            )
            toggle_btn.grid(row=curr_row, column=1, sticky="e", pady=5)

            # Model Override Entry
            model_lbl = tk.Label(parent, text="Model Override:", bg=BG_PANEL, fg=FG_MUTED, font=("Segoe UI", 9))
            model_lbl.grid(row=curr_row+1, column=0, sticky="w", padx=(20, 0), pady=(0, 8))
            
            model_var = tk.StringVar()
            model_entry = tk.Entry(parent, textvariable=model_var, bg=BG_INPUT, fg=FG_TEXT, insertbackground="#ffffff", relief="flat", width=35)
            model_entry.grid(row=curr_row+1, column=1, sticky="w", pady=(0, 8), padx=(10, 0))
            self.model_entries[env_model] = model_var

            # Helper text showing defaults
            model_default_lbl = tk.Label(
                parent,
                text=f"Bawaan: {default_model}",
                fg=FG_MUTED,
                bg=BG_PANEL,
                font=("Segoe UI", 8, "italic")
            )
            model_default_lbl.grid(row=curr_row+1, column=2, sticky="w", padx=(10, 0), pady=(0, 8))

            curr_row += 2

        # Divider
        ttk.Separator(parent, orient="horizontal").grid(row=curr_row, column=0, columnspan=3, sticky="we", pady=15)

        # Frame untuk menampung tombol aksi secara horizontal
        btn_action_frame = tk.Frame(parent, bg=BG_PANEL)
        btn_action_frame.grid(row=curr_row+1, column=0, columnspan=3, sticky="w", pady=(5, 20), padx=(10, 0))

        # Save Button
        self.save_btn = tk.Button(
            btn_action_frame,
            text="💾 SIMPAN KONFIGURASI",
            bg=ACCENT_BLUE,
            fg="#ffffff",
            activebackground="#2563eb",
            activeforeground="#ffffff",
            font=("Segoe UI", 10, "bold"),
            relief="flat",
            bd=0,
            command=self.save_settings,
            padx=15,
            pady=8
        )
        self.save_btn.pack(side="left", padx=(0, 10))

        # Test Button
        self.test_btn = tk.Button(
            btn_action_frame,
            text="🧪 TEST KONEKSI LLM",
            bg=ACCENT_PURPLE,
            fg="#ffffff",
            activebackground="#7c3aed",
            activeforeground="#ffffff",
            font=("Segoe UI", 10, "bold"),
            relief="flat",
            bd=0,
            command=self.test_llm_connection,
            padx=15,
            pady=8
        )
        self.test_btn.pack(side="left")

    def toggle_key_visibility(self, env_key, entry_widget):
        """Toggle mask/unmask of API keys."""
        is_visible = self.show_keys[env_key]
        if is_visible:
            entry_widget.configure(show="*")
            self.show_keys[env_key] = False
        else:
            entry_widget.configure(show="")
            self.show_keys[env_key] = True

    def switch_tab(self, tab_name):
        """Switch visual frames between Configuration and Terminal Logs."""
        if tab_name == "config":
            self.logs_frame.pack_forget()
            self.config_frame.pack(fill="both", expand=True)
            self.tab_config_btn.configure(bg=BG_PANEL, fg=FG_TEXT)
            self.tab_logs_btn.configure(bg=BG_MAIN, fg=FG_MUTED)
            self.active_tab = "config"
        else:
            self.config_frame.pack_forget()
            self.logs_frame.pack(fill="both", expand=True)
            self.tab_config_btn.configure(bg=BG_MAIN, fg=FG_MUTED)
            self.tab_logs_btn.configure(bg=BG_PANEL, fg=FG_TEXT)
            self.active_tab = "logs"

    def load_settings(self):
        """Read settings from the .env file and fill GUI elements."""
        env_path = Path(__file__).parent / ".env"
        if not env_path.exists():
            # If no .env, copy from example
            example_path = Path(__file__).parent / ".env.example"
            if example_path.exists():
                try:
                    import shutil
                    shutil.copy(example_path, env_path)
                    self.append_log("[GUI] File `.env` baru dibuat dari `.env.example`.\n")
                except Exception as e:
                    self.append_log(f"[GUI ERROR] Gagal menyalin .env.example: {e}\n")

        # Parse keys
        settings = {}
        if env_path.exists():
            try:
                for line in env_path.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, val = line.split("=", 1)
                        settings[key.strip()] = val.strip()
            except Exception as e:
                self.append_log(f"[GUI ERROR] Gagal membaca berkas .env: {e}\n")

        # Apply settings to form fields
        self.bot_mode_val.set(settings.get("BOT_MODE", "hybrid"))
        self.llm_provider_val.set(settings.get("LLM_PROVIDER", "gemini"))

        for env_key, var in self.key_entries.items():
            var.set(settings.get(env_key, ""))

        for env_model, var in self.model_entries.items():
            var.set(settings.get(env_model, ""))

    def save_settings(self):
        """Intelligently write settings to .env while preserving lines and comments."""
        env_path = Path(__file__).parent / ".env"
        
        # Load existing lines
        lines = []
        if env_path.exists():
            try:
                lines = env_path.read_text(encoding="utf-8").splitlines()
            except Exception as e:
                self.append_log(f"[GUI ERROR] Gagal membaca berkas .env saat menyimpan: {e}\n")

        # Key mappings
        updates = {
            "BOT_MODE": self.bot_mode_val.get(),
            "LLM_PROVIDER": self.llm_provider_val.get()
        }
        for env_key, var in self.key_entries.items():
            updates[env_key] = var.get().strip()

        for env_model, var in self.model_entries.items():
            updates[env_model] = var.get().strip()

        # Update lines in-place
        key_line_index = {}
        for idx, line in enumerate(lines):
            line_strip = line.strip()
            if line_strip and not line_strip.startswith("#") and "=" in line:
                key = line.split("=", 1)[0].strip()
                key_line_index[key] = idx

        for key, val in updates.items():
            line_str = f"{key}={val}"
            if key in key_line_index:
                lines[key_line_index[key]] = line_str
            else:
                # If not found, append to end
                lines.append(line_str)

        # Write back to file
        try:
            env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            self.append_log("[GUI] Berkas konfigurasi `.env` berhasil disimpan.\n")
            messagebox.showinfo("Sukses", "Konfigurasi `.env` berhasil disimpan!")
        except Exception as e:
            self.append_log(f"[GUI ERROR] Gagal menulis berkas .env: {e}\n")
            messagebox.showerror("Error", f"Gagal menyimpan konfigurasi: {e}")

    def test_llm_connection(self):
        """Test calling the LLM endpoint to verify API key & model settings."""
        provider = self.llm_provider_val.get().strip().lower()
        key = ""
        model = ""
        default_model = ""

        if provider == "gemini":
            key = self.key_entries.get("GEMINI_API_KEY").get().strip()
            model = self.model_entries.get("GEMINI_MODEL").get().strip()
            default_model = "gemini-2.5-flash"
        elif provider == "openai":
            key = self.key_entries.get("OPENAI_API_KEY").get().strip()
            model = self.model_entries.get("OPENAI_MODEL").get().strip()
            default_model = "gpt-4o-mini"
        elif provider == "openrouter":
            key = self.key_entries.get("OPENROUTER_API_KEY").get().strip()
            model = self.model_entries.get("OPENROUTER_MODEL").get().strip()
            default_model = "google/gemini-2.5-flash"
        elif provider == "groq":
            key = self.key_entries.get("GROQ_API_KEY").get().strip()
            model = self.model_entries.get("GROQ_MODEL").get().strip()
            default_model = "llama3-70b-8192"
        elif provider == "deepseek":
            key = self.key_entries.get("DEEPSEEK_API_KEY").get().strip()
            model = self.model_entries.get("DEEPSEEK_MODEL").get().strip()
            default_model = "deepseek-chat"

        if not key:
            messagebox.showerror("Error", f"API Key untuk {provider.upper()} masih kosong!")
            return

        if not model:
            model = default_model

        # Disable button and update text
        self.test_btn.configure(state="disabled", text="⏳ TESTING...")
        self.append_log(f"[GUI] Memulai pengujian LLM Provider: {provider.upper()} dengan model {model}...\n")

        # Run connection test in a separate thread so GUI doesn't freeze
        threading.Thread(
            target=self._run_llm_test_thread,
            args=(provider, key, model),
            daemon=True
        ).start()

    def _run_llm_test_thread(self, provider, key, model):
        """Thread worker to make the actual HTTP call to the selected provider."""
        import requests
        success = False
        message = ""
        try:
            if provider == "gemini":
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
                payload = {
                    "contents": [{
                        "parts": [{"text": "Respond with only the word: OK"}]
                    }]
                }
                resp = requests.post(url, json=payload, timeout=15)
                if resp.status_code == 200:
                    ai_resp = resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
                    success = True
                    message = f"Sukses terkoneksi ke Gemini!\nRespon Model: {ai_resp}"
                else:
                    try:
                        err_json = resp.json()
                        err_msg = err_json.get("error", {}).get("message", resp.text)
                    except Exception:
                        err_msg = resp.text
                    message = f"Gagal (Status {resp.status_code}): {err_msg}"

            elif provider in ("openai", "deepseek", "openrouter", "groq"):
                if provider == "openai":
                    url = "https://api.openai.com/v1/chat/completions"
                elif provider == "deepseek":
                    url = "https://api.deepseek.com/chat/completions"
                elif provider == "openrouter":
                    url = "https://openrouter.ai/api/v1/chat/completions"
                else:  # groq
                    url = "https://api.groq.com/openai/v1/chat/completions"

                headers = {
                    "Authorization": f"Bearer {key}",
                    "Content-Type": "application/json"
                }
                payload = {
                    "model": model,
                    "messages": [{"role": "user", "content": "Respond with only the word: OK"}],
                    "temperature": 0.2
                }
                resp = requests.post(url, headers=headers, json=payload, timeout=15)
                if resp.status_code == 200:
                    ai_resp = resp.json()["choices"][0]["message"]["content"].strip()
                    success = True
                    message = f"Sukses terkoneksi ke {provider.upper()}!\nRespon Model: {ai_resp}"
                else:
                    try:
                        err_json = resp.json()
                        err_msg = err_json.get("error", {}).get("message", resp.text)
                    except Exception:
                        err_msg = resp.text
                    message = f"Gagal (Status {resp.status_code}): {err_msg}"
            else:
                message = f"Provider tidak didukung: {provider}"

        except requests.exceptions.Timeout:
            message = "Gagal terkoneksi: Batas waktu (timeout) habis. Periksa koneksi internet Anda."
        except Exception as e:
            message = f"Error tidak terduga: {str(e)}"

        # Safely return back to the main thread
        self.root.after(0, self._on_llm_test_complete, success, message)

    def _on_llm_test_complete(self, success, message):
        """Callback to run on main thread when LLM test finishes."""
        self.test_btn.configure(state="normal", text="🧪 TEST KONEKSI LLM")
        if success:
            self.append_log(f"[GUI] Uji LLM Berhasil: {message.replace('\n', ' ')}\n")
            messagebox.showinfo("Koneksi Sukses", message)
        else:
            self.append_log(f"[GUI ERROR] Uji LLM Gagal: {message.replace('\n', ' ')}\n")
            messagebox.showerror("Koneksi Gagal", message)

    def append_log(self, text):
        """Append text to the console display widget."""
        self.log_text.configure(state="normal")
        self.log_text.insert(tk.END, text)
        self.log_text.see(tk.END)
        self.log_text.configure(state="disabled")

    def clear_logs(self):
        """Clear console area."""
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", tk.END)
        self.log_text.configure(state="disabled")

    def poll_logs(self):
        """Check for background process output in the queue."""
        while not self.log_queue.empty():
            try:
                line = self.log_queue.get_nowait()
                self.append_log(line)
            except queue.Empty:
                break
        
        # Check process status and update status box and buttons
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

        # Keep polling
        self.root.after(100, self.poll_logs)

    def start_bot(self):
        """Run the bot in a background thread."""
        if self.running_process:
            return

        self.switch_tab("logs")
        self.clear_logs()
        self.append_log("[GUI] Menyimpan konfigurasi sebelum memulai...\n")
        self.save_settings()

        # Command to run (using sys.executable to ensure the correct python context is used)
        cmd = [sys.executable, "main.py"]

        # Run process in a separate thread to prevent UI lockup
        self.append_log(f"[GUI] Menjalankan: {' '.join(cmd)}\n")
        
        self.spawn_process(cmd, "Duel Bot")

    def run_calibration(self):
        """Run auto_calibrate.py in a background thread."""
        if self.running_process:
            return

        # Confirm first
        ans = messagebox.askyesno(
            "Kalibrasi Memori",
            "Pastikan Master Duel sudah terbuka dan berada dalam halaman Duel (Solo Mode) sebelum memulai.\n\nLanjutkan kalibrasi memori?"
        )
        if not ans:
            return

        self.switch_tab("logs")
        self.clear_logs()

        cmd = [sys.executable, "auto_calibrate.py", "--save"]
        self.append_log(f"[GUI] Menjalankan Kalibrasi: {' '.join(cmd)}\n")
        
        self.spawn_process(cmd, "Auto Calibrator")

    def spawn_process(self, cmd, label):
        """Run Popen subprocess and start a thread to read its stdout."""
        creation_flags = 0
        if os.name == 'nt':
            creation_flags = subprocess.CREATE_NO_WINDOW

        # Force UTF-8 communication with child processes
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"

        try:
            self.running_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                creationflags=creation_flags,
                env=env,
                bufsize=1
            )
            
            # Start reader thread
            thread = threading.Thread(target=self._read_process_output, args=(label,), daemon=True)
            thread.start()
        except Exception as e:
            self.append_log(f"[GUI ERROR] Gagal memulai proses {label}: {e}\n")
            messagebox.showerror("Error", f"Gagal menjalankan proses: {e}")

    def _read_process_output(self, label):
        """Read lines from subprocess stdout and place them into the queue."""
        for line in self.running_process.stdout:
            # Strip ANSI color codes from logs
            clean_line = re.sub(r'\x1b\[[0-9;]*[mK]', '', line)
            self.log_queue.put(clean_line)

        self.running_process.wait()
        ret = self.running_process.returncode
        self.log_queue.put(f"\n[GUI] {label} dihentikan. (Exit Code: {ret})\n")
        self.running_process = None

    def stop_process(self):
        """Terminate the active background subprocess."""
        if not self.running_process:
            return

        self.append_log("[GUI] Mengirim sinyal berhenti ke proses backend...\n")
        self.running_process.terminate()
        
        # Give it a brief window to exit, then kill if stubborn
        def force_kill_timer():
            time.sleep(2.0)
            if self.running_process:
                self.append_log("[GUI] Proses masih berjalan. Mematikan secara paksa...\n")
                try:
                    self.running_process.kill()
                except Exception:
                    pass

        threading.Thread(target=force_kill_timer, daemon=True).start()

if __name__ == "__main__":
    # Standard Tkinter initialization
    root = tk.Tk()
    app = OrchestraGUI(root)
    root.mainloop()
