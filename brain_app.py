"""
🧠 NEXT LEVEL BRAIN — Desktop Command Center
Standalone desktop trading software
Created by: Aleem Shahzad | AI Partner: Claude (Anthropic)

Run:   python brain_app.py
Build: pyinstaller --onefile --windowed --icon=brain.ico --name="NEXT LEVEL BRAIN" brain_app.py
"""

import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox, scrolledtext
import subprocess
import sys
import os
import json
import threading
import time
from pathlib import Path
from datetime import datetime, timedelta

# ─── Project Root ────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).parent.resolve()
os.chdir(str(PROJECT_ROOT))

# ─── Theme ───────────────────────────────────────────────────────────────────
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# ─── Colors ──────────────────────────────────────────────────────────────────
COLORS = {
    "bg_dark": "#080b12",
    "bg_card": "#0f1520",
    "bg_sidebar": "#0a0e18",
    "bg_input": "#141b2a",
    "border": "#1e293b",
    "border_hover": "#3b82f6",
    "text_primary": "#f1f5f9",
    "text_secondary": "#94a3b8",
    "text_muted": "#475569",
    "accent_blue": "#3b82f6",
    "accent_green": "#22c55e",
    "accent_amber": "#f59e0b",
    "accent_rose": "#f43f5e",
    "accent_purple": "#8b5cf6",
    "btn_primary": "#1d4ed8",
    "btn_hover": "#2563eb",
    "btn_danger": "#dc2626",
    "btn_success": "#16a34a",
}


class OutputRedirector:
    """Capture subprocess output into a text widget."""
    def __init__(self, text_widget):
        self.widget = text_widget

    def append(self, text):
        try:
            if self.widget.winfo_exists():
                self.widget.configure(state="normal")
                self.widget.insert("end", text)
                self.widget.see("end")
                self.widget.configure(state="disabled")
        except:
            pass

    def clear(self):
        try:
            if self.widget.winfo_exists():
                self.widget.configure(state="normal")
                self.widget.delete("1.0", "end")
                self.widget.configure(state="disabled")
        except:
            pass


class NextLevelBrainApp(ctk.CTk):
    """Main Desktop Application."""

    def __init__(self):
        super().__init__()

        # ── Window Setup ──
        self.title("🧠 NEXT LEVEL BRAIN — Command Center")
        self.geometry("1280x780")
        self.minsize(1000, 650)
        self.configure(fg_color=COLORS["bg_dark"])

        # Try to set icon
        icon_path = PROJECT_ROOT / "brain.ico"
        if icon_path.exists():
            self.iconbitmap(str(icon_path))

        # ── State ──
        self.running_processes = {}
        self.current_page = "dashboard"

        # ── Build UI ──
        self._build_sidebar()
        self._build_content_area()
        self._show_page("dashboard")

        # ── On Close ──
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ═══════════════════════════════════════════════════════════════════════════
    # SIDEBAR
    # ═══════════════════════════════════════════════════════════════════════════

    def _build_sidebar(self):
        self.sidebar = ctk.CTkFrame(self, width=220, fg_color=COLORS["bg_sidebar"],
                                     corner_radius=0, border_width=0)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)

        # Logo area
        logo_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        logo_frame.pack(pady=(28, 5), padx=16)

        ctk.CTkLabel(logo_frame, text="🧠", font=("Segoe UI Emoji", 40)).pack()
        ctk.CTkLabel(logo_frame, text="NEXT LEVEL\nBRAIN",
                     font=("Segoe UI", 18, "bold"),
                     text_color=COLORS["accent_blue"]).pack(pady=(5, 0))
        ctk.CTkLabel(logo_frame, text="Command Center",
                     font=("Segoe UI", 9),
                     text_color=COLORS["text_muted"]).pack(pady=(2, 0))

        # Separator
        sep = ctk.CTkFrame(self.sidebar, height=1, fg_color=COLORS["border"])
        sep.pack(fill="x", padx=20, pady=16)

        # Navigation buttons
        nav_items = [
            ("🏠  Dashboard", "dashboard"),
            ("🔑  Account", "account"),
            ("📊  Backtesting", "backtesting"),
            ("🔴  Live Trading", "live_trading"),
            ("🌐  Intelligence", "intelligence"),
            ("🧹  Orders", "orders"),
            ("⚙️  Settings", "settings"),
            ("📜  Logs", "logs"),
            ("🖥️  Terminal", "terminal"),
        ]

        self.nav_buttons = {}
        for text, page_id in nav_items:
            btn = ctk.CTkButton(
                self.sidebar, text=text, anchor="w",
                font=("Segoe UI", 13), height=38,
                fg_color="transparent",
                text_color=COLORS["text_secondary"],
                hover_color=COLORS["bg_card"],
                corner_radius=8,
                command=lambda p=page_id: self._show_page(p),
            )
            btn.pack(fill="x", padx=12, pady=2)
            self.nav_buttons[page_id] = btn

        # Bottom status
        spacer = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        spacer.pack(expand=True)

        self.status_label = ctk.CTkLabel(
            self.sidebar, text="",
            font=("Segoe UI", 8),
            text_color=COLORS["text_muted"],
        )
        self.status_label.pack(pady=(0, 8))
        self._update_clock()

    def _update_clock(self):
        try:
            if self.status_label.winfo_exists():
                self.status_label.configure(text=f"⏱ {datetime.now().strftime('%d %b %Y • %H:%M:%S')}")
                self.after(1000, self._update_clock)
        except:
            pass

    # ═══════════════════════════════════════════════════════════════════════════
    # CONTENT AREA
    # ═══════════════════════════════════════════════════════════════════════════

    def _build_content_area(self):
        self.content = ctk.CTkFrame(self, fg_color=COLORS["bg_dark"], corner_radius=0)
        self.content.pack(side="right", fill="both", expand=True)

        # Scrollable container
        self.scroll = ctk.CTkScrollableFrame(self.content, fg_color=COLORS["bg_dark"])
        self.scroll.pack(fill="both", expand=True, padx=0, pady=0)

        self.pages = {}

    def _show_page(self, page_id):
        self.current_page = page_id

        # Update nav highlighting
        for pid, btn in self.nav_buttons.items():
            if pid == page_id:
                btn.configure(fg_color=COLORS["bg_card"], text_color=COLORS["accent_blue"])
            else:
                btn.configure(fg_color="transparent", text_color=COLORS["text_secondary"])

        # Clear content
        for widget in self.scroll.winfo_children():
            widget.destroy()

        # Build page
        builder = getattr(self, f"_page_{page_id}", None)
        if builder:
            builder()

    # ═══════════════════════════════════════════════════════════════════════════
    # HELPERS
    # ═══════════════════════════════════════════════════════════════════════════

    def _make_title(self, parent, text, subtitle=""):
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.pack(fill="x", padx=24, pady=(20, 4))
        ctk.CTkLabel(frame, text=text, font=("Segoe UI", 24, "bold"),
                     text_color=COLORS["accent_blue"]).pack(anchor="w")
        if subtitle:
            ctk.CTkLabel(frame, text=subtitle, font=("Segoe UI", 12),
                         text_color=COLORS["text_muted"]).pack(anchor="w", pady=(2, 0))

    def _make_card(self, parent, **kwargs):
        card = ctk.CTkFrame(parent, fg_color=COLORS["bg_card"],
                            corner_radius=14, border_width=1,
                            border_color=COLORS["border"])
        card.pack(fill="x", padx=24, pady=8, **kwargs)
        return card

    def _make_stat_box(self, parent, value, label, color):
        box = ctk.CTkFrame(parent, fg_color=COLORS["bg_card"],
                           corner_radius=14, border_width=1,
                           border_color=COLORS["border"])
        box.pack(side="left", fill="both", expand=True, padx=6)
        ctk.CTkLabel(box, text=str(value), font=("Segoe UI", 28, "bold"),
                     text_color=color).pack(pady=(16, 2))
        ctk.CTkLabel(box, text=label, font=("Segoe UI", 9),
                     text_color=COLORS["text_muted"]).pack(pady=(0, 14))

    def _make_output_box(self, parent, height=250):
        out = ctk.CTkTextbox(parent, height=height,
                              fg_color="#0a0e14", text_color="#4ade80",
                              font=("Consolas", 11), corner_radius=10,
                              border_width=1, border_color=COLORS["border"],
                              state="disabled", wrap="word")
        out.pack(fill="x", padx=16, pady=(8, 16))
        return OutputRedirector(out)

    def _run_async(self, script_path, output: OutputRedirector, timeout=120, done_msg="✅ Done!"):
        """Run a script in background thread, output to widget."""
        def worker():
            output.clear()
            output.append(f"▶ Running: python {script_path}\n{'─'*50}\n")
            try:
                proc = subprocess.Popen(
                    [sys.executable, "-u", str(PROJECT_ROOT / script_path)],
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    cwd=str(PROJECT_ROOT),
                    env={**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"},
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
                    encoding="utf-8", errors="replace",
                )
                start = time.time()
                for line in proc.stdout:
                    output.append(line)
                    if time.time() - start > timeout:
                        proc.kill()
                        output.append(f"\n⏰ Timeout ({timeout}s)\n")
                        break
                proc.wait(timeout=5)
                output.append(f"\n{'─'*50}\n{done_msg}\n")
            except Exception as e:
                output.append(f"\n❌ Error: {e}\n")

        threading.Thread(target=worker, daemon=True).start()

    def _launch_terminal(self, script, title="NEXT LEVEL BRAIN"):
        """Launch script in new CMD window."""
        try:
            cmd = f'start "{title}" cmd /k "cd /d {PROJECT_ROOT} && python {script}"'
            os.system(cmd)
            return True
        except:
            return False

    def _load_config(self):
        try:
            import yaml
            p = PROJECT_ROOT / "config.yaml"
            if p.exists():
                return yaml.safe_load(p.read_text(encoding="utf-8", errors="replace"))
        except:
            pass
        return {}

    def _load_env_values(self):
        """Read current MT5 values from .env"""
        values = {"MT5_LOGIN": "", "MT5_PASSWORD": "", "MT5_SERVER": ""}
        env_path = PROJECT_ROOT / ".env"
        if env_path.exists():
            content = env_path.read_text(encoding="utf-8", errors="replace")
            for line in content.splitlines():
                if "=" in line and not line.startswith("#"):
                    key, _, val = line.partition("=")
                    key = key.strip()
                    if key in values:
                        values[key] = val.strip().strip('"').strip("'")
        return values

    def _save_env_values(self, new_values):
        """Update .env file with new credentials"""
        env_path = PROJECT_ROOT / ".env"
        if not env_path.exists():
            # Create a basic .env if it doesn't exist
            content = "# NEXT LEVEL BRAIN - Environment Variables\n"
        else:
            content = env_path.read_text(encoding="utf-8", errors="replace")

        lines = content.splitlines()
        updated_keys = set()
        
        for i, line in enumerate(lines):
            if "=" in line and not line.startswith("#"):
                key, _, _ = line.partition("=")
                key = key.strip()
                if key in new_values:
                    lines[i] = f"{key}={new_values[key]}"
                    updated_keys.add(key)
        
        # Add keys that didn't exist
        for key, val in new_values.items():
            if key not in updated_keys:
                lines.append(f"{key}={val}")

        env_path.write_text("\n".join(lines), encoding="utf-8")
        return True

    # ═══════════════════════════════════════════════════════════════════════════
    # PAGE: DASHBOARD
    # ═══════════════════════════════════════════════════════════════════════════

    def _page_dashboard(self):
        self._make_title(self.scroll, "🧠 NEXT LEVEL BRAIN",
                         "Yahan se sab kuch control karein — Backtesting, Live Trading, Intelligence")

        # Stats row
        stats_frame = ctk.CTkFrame(self.scroll, fg_color="transparent")
        stats_frame.pack(fill="x", padx=24, pady=12)

        # Count stuff
        bt_count = len(list((PROJECT_ROOT / "backtest_results").glob("*.json"))) if (PROJECT_ROOT / "backtest_results").exists() else 0
        live_count = len(list((PROJECT_ROOT / "logs" / "live_reports").glob("*.md"))) if (PROJECT_ROOT / "logs" / "live_reports").exists() else 0
        ai_mem = 0
        mem_f = PROJECT_ROOT / "models" / "ai_memories.json"
        if mem_f.exists():
            try: ai_mem = len(json.load(open(mem_f)))
            except: pass
        config = self._load_config()
        syms = ", ".join(config.get("symbols", ["N/A"]))

        self._make_stat_box(stats_frame, bt_count, "BACKTEST REPORTS", COLORS["accent_blue"])
        self._make_stat_box(stats_frame, live_count, "LIVE SESSIONS", COLORS["accent_green"])
        self._make_stat_box(stats_frame, ai_mem, "AI MEMORIES", COLORS["accent_amber"])
        self._make_stat_box(stats_frame, syms, "ACTIVE SYMBOLS", COLORS["accent_purple"])

        # Quick actions
        actions_frame = ctk.CTkFrame(self.scroll, fg_color="transparent")
        actions_frame.pack(fill="x", padx=24, pady=12)

        quick_actions = [
            ("📊  Run Backtesting", "backtesting", COLORS["accent_blue"]),
            ("🔴  Start Live Trading", "live_trading", COLORS["accent_rose"]),
            ("🌐  Market Intelligence", "intelligence", COLORS["accent_green"]),
            ("🧹  Manage Orders", "orders", COLORS["accent_amber"]),
        ]

        for text, page, color in quick_actions:
            btn = ctk.CTkButton(
                actions_frame, text=text, height=50,
                font=("Segoe UI", 14, "bold"),
                fg_color=color, hover_color=color,
                corner_radius=12,
                command=lambda p=page: self._show_page(p),
            )
            btn.pack(side="left", fill="both", expand=True, padx=6)

        # Latest report
        card = self._make_card(self.scroll)
        ctk.CTkLabel(card, text="📄 Latest Intelligence Report",
                     font=("Segoe UI", 14, "bold"),
                     text_color=COLORS["text_primary"]).pack(anchor="w", padx=16, pady=(14, 4))

        report_path = PROJECT_ROOT / "latest_intelligence_report.txt"
        if report_path.exists():
            mod = datetime.fromtimestamp(report_path.stat().st_mtime).strftime("%d %b %Y • %H:%M")
            ctk.CTkLabel(card, text=f"🕐 Last updated: {mod}",
                         font=("Segoe UI", 10), text_color=COLORS["text_muted"]).pack(anchor="w", padx=16)
            txt = report_path.read_text(encoding="utf-8", errors="ignore")[:2000]
            tb = ctk.CTkTextbox(card, height=180, fg_color="#0a0e14",
                                 text_color="#94a3b8", font=("Consolas", 10),
                                 corner_radius=8, state="normal")
            tb.pack(fill="x", padx=16, pady=(8, 14))
            tb.insert("1.0", txt)
            tb.configure(state="disabled")
        else:
            ctk.CTkLabel(card, text="🔍 Abhi koi report nahi. 'Intelligence' page se generate karein.",
                         font=("Segoe UI", 11), text_color=COLORS["text_muted"]).pack(padx=16, pady=16)

    # ═══════════════════════════════════════════════════════════════════════════
    # PAGE: ACCOUNT
    # ═══════════════════════════════════════════════════════════════════════════

    def _page_account(self):
        self._make_title(self.scroll, "🔑 MT5 Account Management",
                         "Apne trading account credentials manage karein")

        # Connection Status Card
        card_status = self._make_card(self.scroll)
        status_frame = ctk.CTkFrame(card_status, fg_color="transparent")
        status_frame.pack(fill="x", padx=16, pady=14)
        
        ctk.CTkLabel(status_frame, text="📡 MT5 Status:", font=("Segoe UI", 13, "bold"),
                     text_color=COLORS["text_primary"]).pack(side="left")
        
        # We check MT5 quickly in separate thread
        self.acc_status_label = ctk.CTkLabel(status_frame, text="Checking...", 
                                             font=("Segoe UI", 13), text_color=COLORS["accent_amber"])
        self.acc_status_label.pack(side="left", padx=10)
        
        ctk.CTkButton(status_frame, text="🔄 Refresh", width=80, height=28,
                      command=self._check_mt5_account_status).pack(side="right")

        # Credentials Card
        card_creds = self._make_card(self.scroll)
        ctk.CTkLabel(card_creds, text="🔒 MT5 Credentials",
                     font=("Segoe UI", 16, "bold"),
                     text_color=COLORS["text_primary"]).pack(anchor="w", padx=16, pady=(16, 4))
        ctk.CTkLabel(card_creds, text="Account details directly .env file mein save honge",
                     font=("Segoe UI", 11), text_color=COLORS["text_muted"]).pack(anchor="w", padx=16, pady=(0, 10))

        env_vals = self._load_env_values()

        # Login
        ctk.CTkLabel(card_creds, text="Account Login:", font=("Segoe UI", 12),
                     text_color=COLORS["text_secondary"]).pack(anchor="w", padx=16, pady=(10, 2))
        self.acc_login = ctk.CTkEntry(card_creds, width=400, fg_color=COLORS["bg_input"], 
                                      placeholder_text="e.g. 12345678")
        self.acc_login.pack(anchor="w", padx=16, pady=(0, 10))
        self.acc_login.insert(0, env_vals["MT5_LOGIN"])

        # Password
        ctk.CTkLabel(card_creds, text="Account Password:", font=("Segoe UI", 12),
                     text_color=COLORS["text_secondary"]).pack(anchor="w", padx=16, pady=(10, 2))
        self.acc_pass = ctk.CTkEntry(card_creds, width=400, fg_color=COLORS["bg_input"], 
                                      placeholder_text="Mypassword123", show="*")
        self.acc_pass.pack(anchor="w", padx=16, pady=(0, 10))
        self.acc_pass.insert(0, env_vals["MT5_PASSWORD"])

        # Server
        ctk.CTkLabel(card_creds, text="MT5 Server:", font=("Segoe UI", 12),
                     text_color=COLORS["text_secondary"]).pack(anchor="w", padx=16, pady=(10, 2))
        self.acc_server = ctk.CTkEntry(card_creds, width=400, fg_color=COLORS["bg_input"], 
                                        placeholder_text="e.g. Exness-MT5Trial15")
        self.acc_server.pack(anchor="w", padx=16, pady=(0, 10))
        self.acc_server.insert(0, env_vals["MT5_SERVER"])

        # Save Button
        save_btn = ctk.CTkButton(card_creds, text="💾 Save Credentials",
                                 font=("Segoe UI", 14, "bold"), height=46,
                                 fg_color=COLORS["accent_blue"], hover_color=COLORS["btn_hover"],
                                 corner_radius=10, command=self._save_account_creds)
        save_btn.pack(padx=16, pady=20, anchor="w")

        # MT5 Diagnostic info
        card_diag = self._make_card(self.scroll)
        ctk.CTkLabel(card_diag, text="🩺 Quick Diagnostics",
                     font=("Segoe UI", 14, "bold"),
                     text_color=COLORS["text_primary"]).pack(anchor="w", padx=16, pady=(14, 6))
        
        diag_btns = ctk.CTkFrame(card_diag, fg_color="transparent")
        diag_btns.pack(fill="x", padx=16, pady=10)
        
        ctk.CTkButton(diag_btns, text="🔍 Test Connection", width=150, height=36,
                      command=lambda: self._launch_terminal("diagnose_mt5.py", "MT5 Connect Test")).pack(side="left", padx=5)
        ctk.CTkButton(diag_btns, text="🛠️ Debug Info", width=150, height=36,
                      command=lambda: self._launch_terminal("debug_mt5.py", "MT5 Debug")).pack(side="left", padx=5)

        # Initial status check
        self._check_mt5_account_status()

    def _save_account_creds(self):
        new_values = {
            "MT5_LOGIN": self.acc_login.get().strip(),
            "MT5_PASSWORD": self.acc_pass.get().strip(),
            "MT5_SERVER": self.acc_server.get().strip()
        }
        if self._save_env_values(new_values):
            messagebox.showinfo("Success", "✅ Account credentials saved to .env!\nMetaTrader 5 will use these details next time.")
            self._check_mt5_account_status()

    def _check_mt5_account_status(self):
        """Run a hidden process to check MT5 connection"""
        self.acc_status_label.configure(text="Checking...", text_color=COLORS["accent_amber"])
        
        def check():
            check_script = PROJECT_ROOT / "_temp_check_mt5.py"
            check_script.write_text(f'''
import MetaTrader5 as mt5
import os
from dotenv import load_dotenv
load_dotenv()
res = mt5.initialize(
    login=int(os.getenv("MT5_LOGIN", 0)),
    password=os.getenv("MT5_PASSWORD", ""),
    server=os.getenv("MT5_SERVER", "")
)
if res:
    print(f"CONNECTED|{{mt5.account_info().login}}")
    mt5.shutdown()
else:
    print(f"FAILED|{{mt5.last_error()}}")
''', encoding="utf-8")
            
            try:
                result = subprocess.run(
                    [sys.executable, str(check_script)],
                    capture_output=True, text=True, timeout=10, cwd=str(PROJECT_ROOT)
                )
                if not self.acc_status_label.winfo_exists():
                    return
                
                output = result.stdout.strip()
                if "CONNECTED" in output:
                    login = output.split("|")[1]
                    self.acc_status_label.configure(text=f"✅ Connected (Acc: {login})", text_color=COLORS["accent_green"])
                else:
                    err = output.split("|")[1] if "|" in output else "Unknown Error"
                    self.acc_status_label.configure(text=f"❌ Failed: {err}", text_color=COLORS["accent_rose"])
            except Exception as e:
                if self.acc_status_label.winfo_exists():
                    self.acc_status_label.configure(text=f"❌ Error: {str(e)[:20]}", text_color=COLORS["accent_rose"])
            finally:
                if check_script.exists(): check_script.unlink()

        threading.Thread(target=check, daemon=True).start()

    # ═══════════════════════════════════════════════════════════════════════════
    # PAGE: BACKTESTING
    # ═══════════════════════════════════════════════════════════════════════════

    def _page_backtesting(self):
        self._make_title(self.scroll, "📊 Backtesting Engine",
                         "Symbol, Timeframe, Period select karein — phir Run dabayein")

        # Settings card
        card = self._make_card(self.scroll)
        ctk.CTkLabel(card, text="⚙️ Backtest Settings",
                     font=("Segoe UI", 14, "bold"),
                     text_color=COLORS["text_primary"]).pack(anchor="w", padx=16, pady=(14, 10))

        # Row 1: Symbol, Timeframe, Period
        row1 = ctk.CTkFrame(card, fg_color="transparent")
        row1.pack(fill="x", padx=16, pady=4)

        # Symbol
        ctk.CTkLabel(row1, text="🪙 Symbol", font=("Segoe UI", 11),
                     text_color=COLORS["text_secondary"]).pack(side="left", padx=(0, 8))
        self.bt_symbol = ctk.CTkComboBox(row1, values=["XAUUSDm", "BTCUSDm", "EURUSDm", "GBPUSDm", "USDJPYm", "ETHUSDm", "XAGUSDm"],
                                          width=140, fg_color=COLORS["bg_input"])
        self.bt_symbol.pack(side="left", padx=(0, 20))
        self.bt_symbol.set("XAUUSDm")

        # Timeframe
        ctk.CTkLabel(row1, text="⏰ Timeframe", font=("Segoe UI", 11),
                     text_color=COLORS["text_secondary"]).pack(side="left", padx=(0, 8))
        self.bt_tf = ctk.CTkComboBox(row1, values=["M1", "M3", "M5", "M15", "M30", "H1", "H4", "D1"],
                                      width=100, fg_color=COLORS["bg_input"])
        self.bt_tf.pack(side="left", padx=(0, 20))
        self.bt_tf.set("M5")

        # Period
        ctk.CTkLabel(row1, text="📅 Period", font=("Segoe UI", 11),
                     text_color=COLORS["text_secondary"]).pack(side="left", padx=(0, 8))
        self.bt_period = ctk.CTkComboBox(row1, values=["7", "30", "90", "180", "365"],
                                          width=100, fg_color=COLORS["bg_input"])
        self.bt_period.pack(side="left")
        self.bt_period.set("30")

        # Row 2: Strategy
        row2 = ctk.CTkFrame(card, fg_color="transparent")
        row2.pack(fill="x", padx=16, pady=(8, 4))

        ctk.CTkLabel(row2, text="🎯 Strategy", font=("Segoe UI", 11),
                     text_color=COLORS["text_secondary"]).pack(side="left", padx=(0, 8))
        self.bt_strategy = ctk.CTkComboBox(row2, values=["ICT SMC", "Grid Strategy (Both)", "Grid BUY ONLY", "Grid SELL ONLY"],
                                            width=220, fg_color=COLORS["bg_input"])
        self.bt_strategy.pack(side="left")
        self.bt_strategy.set("ICT SMC")

        # Buttons
        btn_row = ctk.CTkFrame(card, fg_color="transparent")
        btn_row.pack(fill="x", padx=16, pady=(12, 14))

        ctk.CTkButton(btn_row, text="▶️  Run Quick Backtest",
                      font=("Segoe UI", 13, "bold"), height=42,
                      fg_color=COLORS["accent_blue"], hover_color=COLORS["btn_hover"],
                      corner_radius=10,
                      command=self._run_backtest_quick).pack(side="left", padx=(0, 10))

        ctk.CTkButton(btn_row, text="🖥️  Open GUI Dashboard",
                      font=("Segoe UI", 13, "bold"), height=42,
                      fg_color=COLORS["accent_purple"], hover_color="#7c3aed",
                      corner_radius=10,
                      command=lambda: self._launch_terminal("backtesting.py", "Backtesting GUI")).pack(side="left")

        # Output
        self.bt_output = self._make_output_box(card, height=280)

        # Past results
        card2 = self._make_card(self.scroll)
        ctk.CTkLabel(card2, text="📋 Previous Results",
                     font=("Segoe UI", 14, "bold"),
                     text_color=COLORS["text_primary"]).pack(anchor="w", padx=16, pady=(14, 8))

        bt_dir = PROJECT_ROOT / "backtest_results"
        if bt_dir.exists():
            reports = sorted(bt_dir.glob("*.json"), key=os.path.getmtime, reverse=True)[:5]
            if reports:
                for rpt in reports:
                    mod = datetime.fromtimestamp(rpt.stat().st_mtime).strftime("%d %b • %H:%M")
                    try:
                        data = json.loads(rpt.read_text(encoding="utf-8", errors="replace"))
                        results = data.get("results", data)
                        pnl = results.get("total_pnl", 0)
                        wr = results.get("win_rate", 0)
                        trades = results.get("total_trades", 0)
                        summary = f"📊 {rpt.stem}  |  {mod}  |  {trades} trades  |  WR: {wr:.0%}  |  P&L: ${pnl:.2f}"
                    except:
                        summary = f"📊 {rpt.stem}  |  {mod}"

                    pnl_color = COLORS["accent_green"] if pnl > 0 else COLORS["accent_rose"]
                    ctk.CTkLabel(card2, text=summary, font=("Consolas", 10),
                                 text_color=pnl_color).pack(anchor="w", padx=16, pady=2)
            else:
                ctk.CTkLabel(card2, text="Abhi koi result nahi — pehle backtest run karein",
                             text_color=COLORS["text_muted"]).pack(padx=16, pady=12)
        else:
            ctk.CTkLabel(card2, text="backtest_results/ folder nahi mila",
                         text_color=COLORS["text_muted"]).pack(padx=16, pady=12)

    def _run_backtest_quick(self):
        symbol = self.bt_symbol.get()
        tf = self.bt_tf.get()
        days = self.bt_period.get()
        strategy = self.bt_strategy.get()

        # Create temp helper
        helper = PROJECT_ROOT / "_quick_bt.py"
        code = f'''
import sys, os
sys.path.insert(0, r"{PROJECT_ROOT}")
os.chdir(r"{PROJECT_ROOT}")
from pathlib import Path
for d in ["logs","backtest_results","models","charts"]: Path(d).mkdir(exist_ok=True)
from datetime import datetime, timedelta
from backtesting import BacktestEngine

engine = BacktestEngine()
end_date = datetime.now()
start_date = end_date - timedelta(days={days})

print("🚀 Backtest Starting...")
print(f"Symbol: {symbol} | TF: {tf} | Days: {days} | Strategy: {strategy}")
print()

strategy_name = "{strategy}"
if "Grid" in strategy_name and "BUY" in strategy_name:
    results = engine.run_grid_backtest("{symbol}", start_date, end_date, "{tf}", mode="BUY_ONLY")
elif "Grid" in strategy_name and "SELL" in strategy_name:
    results = engine.run_grid_backtest("{symbol}", start_date, end_date, "{tf}", mode="SELL_ONLY")
elif "Grid" in strategy_name:
    results = engine.run_grid_backtest("{symbol}", start_date, end_date, "{tf}", mode="BOTH")
else:
    results = engine.run_backtest("{symbol}", start_date, end_date, "{tf}")

if "error" not in results:
    engine.generate_report(results)
    print("\\n✅ Backtest Complete!")
else:
    print(f"❌ Error: {{results['error']}}")
'''
        helper.write_text(code, encoding="utf-8")
        self._run_async("_quick_bt.py", self.bt_output, timeout=120,
                        done_msg="✅ Backtest complete! Results saved.")

    # ═══════════════════════════════════════════════════════════════════════════
    # PAGE: LIVE TRADING
    # ═══════════════════════════════════════════════════════════════════════════

    def _page_live_trading(self):
        self._make_title(self.scroll, "🔴 Live Trading System",
                         "Strategy choose karein aur nayi window mein trading start karein")

        # Setup card
        card = self._make_card(self.scroll)
        ctk.CTkLabel(card, text="🎯 Trading Setup",
                     font=("Segoe UI", 14, "bold"),
                     text_color=COLORS["text_primary"]).pack(anchor="w", padx=16, pady=(14, 10))

        row1 = ctk.CTkFrame(card, fg_color="transparent")
        row1.pack(fill="x", padx=16, pady=4)

        ctk.CTkLabel(row1, text="🎯 Strategy", font=("Segoe UI", 11),
                     text_color=COLORS["text_secondary"]).pack(side="left", padx=(0, 8))
        self.live_strategy = ctk.CTkComboBox(
            row1, values=["Grid BUY ONLY", "Grid SELL ONLY", "Grid BOTH", "ICT SMC"],
            width=200, fg_color=COLORS["bg_input"])
        self.live_strategy.pack(side="left", padx=(0, 20))
        self.live_strategy.set("Grid BUY ONLY")

        ctk.CTkLabel(row1, text="⏰ Timeframe", font=("Segoe UI", 11),
                     text_color=COLORS["text_secondary"]).pack(side="left", padx=(0, 8))
        self.live_tf = ctk.CTkComboBox(row1, values=["M1", "M3", "M5", "M15", "M30", "H1", "H4", "D1"],
                                        width=100, fg_color=COLORS["bg_input"])
        self.live_tf.pack(side="left")
        self.live_tf.set("M1")

        row2 = ctk.CTkFrame(card, fg_color="transparent")
        row2.pack(fill="x", padx=16, pady=(8, 4))

        config = self._load_config()
        symbols = config.get("symbols", ["XAUUSDm"])

        ctk.CTkLabel(row2, text="🪙 Symbol", font=("Segoe UI", 11),
                     text_color=COLORS["text_secondary"]).pack(side="left", padx=(0, 8))
        self.live_symbol = ctk.CTkComboBox(row2, values=symbols, width=140,
                                            fg_color=COLORS["bg_input"])
        self.live_symbol.pack(side="left")
        self.live_symbol.set(symbols[0])

        # Warning
        warn = ctk.CTkFrame(card, fg_color="#1c1917", corner_radius=10,
                             border_width=1, border_color="#854d0e")
        warn.pack(fill="x", padx=16, pady=10)
        ctk.CTkLabel(warn, text="⚠️  Live Trading nayi terminal window mein start hogi. Band karne ke liye Ctrl+C dabayein.",
                     font=("Segoe UI", 11), text_color="#fbbf24",
                     wraplength=600).pack(padx=12, pady=10)

        # Launch button
        ctk.CTkButton(card, text="🚀  START LIVE TRADING",
                      font=("Segoe UI", 16, "bold"), height=50,
                      fg_color="#dc2626", hover_color="#b91c1c",
                      corner_radius=12,
                      command=self._start_live_trading).pack(padx=16, pady=(4, 14))

        # Live Dashboard button
        card2 = self._make_card(self.scroll)
        ctk.CTkLabel(card2, text="📈 Live Portfolio Dashboard",
                     font=("Segoe UI", 14, "bold"),
                     text_color=COLORS["text_primary"]).pack(anchor="w", padx=16, pady=(14, 6))
        ctk.CTkLabel(card2, text="Real-time positions, equity, trade history monitor",
                     font=("Segoe UI", 11), text_color=COLORS["text_muted"]).pack(anchor="w", padx=16)
        ctk.CTkButton(card2, text="📈  Open Live Dashboard",
                      font=("Segoe UI", 13, "bold"), height=42,
                      fg_color=COLORS["accent_green"], hover_color="#15803d",
                      corner_radius=10,
                      command=lambda: self._launch_terminal("live_dashboard.py", "Live Dashboard")).pack(
                          padx=16, pady=(10, 14))

    def _start_live_trading(self):
        strategy = self.live_strategy.get()
        tf = self.live_tf.get()
        symbol = self.live_symbol.get()

        strat_map = {"Grid BUY ONLY": "Grid BUY ONLY", "Grid SELL ONLY": "Grid SELL ONLY",
                     "Grid BOTH": "Grid Both", "ICT SMC": "ICT SMC"}
        strat = strat_map.get(strategy, strategy)

        helper = PROJECT_ROOT / "_auto_live.py"
        code = f'''
import sys, os, asyncio
sys.path.insert(0, r"{PROJECT_ROOT}")
os.chdir(r"{PROJECT_ROOT}")
from pathlib import Path
for d in ["logs","charts","models"]: Path(d).mkdir(exist_ok=True)
from live_trading import LiveTradingSystem

print("=" * 60)
print("🧠 NEXT LEVEL BRAIN - LIVE TRADING")
print("=" * 60)
print(f"Symbol: {symbol}")
print(f"Strategy: {strat}")
print(f"Timeframe: {tf}")
print("=" * 60)
print()

system = LiveTradingSystem()
system.symbols = ["{symbol}"]
system.strategy = "{strat}"
system.timeframe = "{tf}"
asyncio.run(system.run())
'''
        helper.write_text(code, encoding="utf-8")
        self._launch_terminal("_auto_live.py", f"Live Trading — {symbol} — {strat}")
        messagebox.showinfo("Live Trading", f"✅ Trading started!\n\nSymbol: {symbol}\nStrategy: {strat}\nTimeframe: {tf}\n\nNayi terminal window check karein.")

    # ═══════════════════════════════════════════════════════════════════════════
    # PAGE: INTELLIGENCE
    # ═══════════════════════════════════════════════════════════════════════════

    def _page_intelligence(self):
        self._make_title(self.scroll, "🌐 Market Intelligence",
                         "Sentiment analysis, smart money inference — ek click mein")

        # Run buttons
        btn_frame = ctk.CTkFrame(self.scroll, fg_color="transparent")
        btn_frame.pack(fill="x", padx=24, pady=12)

        ctk.CTkButton(btn_frame, text="🧠  Run Market Intelligence",
                      font=("Segoe UI", 14, "bold"), height=46,
                      fg_color=COLORS["accent_green"], hover_color="#15803d",
                      corner_radius=10,
                      command=self._run_intelligence).pack(side="left", expand=True, fill="x", padx=(0, 8))

        ctk.CTkButton(btn_frame, text="🔍  Run ICT Auditor",
                      font=("Segoe UI", 14, "bold"), height=46,
                      fg_color=COLORS["accent_purple"], hover_color="#7c3aed",
                      corner_radius=10,
                      command=self._run_ict_audit).pack(side="left", expand=True, fill="x", padx=(8, 0))

        # Output card
        card = self._make_card(self.scroll)
        ctk.CTkLabel(card, text="📋 Output",
                     font=("Segoe UI", 14, "bold"),
                     text_color=COLORS["text_primary"]).pack(anchor="w", padx=16, pady=(14, 4))
        self.intel_output = self._make_output_box(card, height=300)

        # Report card
        card2 = self._make_card(self.scroll)
        ctk.CTkLabel(card2, text="📄 Latest Report",
                     font=("Segoe UI", 14, "bold"),
                     text_color=COLORS["text_primary"]).pack(anchor="w", padx=16, pady=(14, 6))

        report_path = PROJECT_ROOT / "latest_intelligence_report.txt"
        if report_path.exists():
            mod = datetime.fromtimestamp(report_path.stat().st_mtime).strftime("%d %b %Y • %H:%M")
            ctk.CTkLabel(card2, text=f"🕐 {mod}", font=("Segoe UI", 10),
                         text_color=COLORS["text_muted"]).pack(anchor="w", padx=16)
            txt = report_path.read_text(encoding="utf-8", errors="ignore")[:3000]
            tb = ctk.CTkTextbox(card2, height=200, fg_color="#0a0e14",
                                 text_color="#94a3b8", font=("Consolas", 10),
                                 corner_radius=8, state="normal")
            tb.pack(fill="x", padx=16, pady=(8, 14))
            tb.insert("1.0", txt)
            tb.configure(state="disabled")
        else:
            ctk.CTkLabel(card2, text="Report nahi mila — upar button se generate karein",
                         text_color=COLORS["text_muted"]).pack(padx=16, pady=14)

    def _run_intelligence(self):
        self._run_async("run_market_intelligence.py", self.intel_output, timeout=60,
                        done_msg="✅ Intelligence report generated!")

    def _run_ict_audit(self):
        self._run_async("ict_concept_auditor.py", self.intel_output, timeout=120,
                        done_msg="✅ ICT audit complete!")

    # ═══════════════════════════════════════════════════════════════════════════
    # PAGE: ORDERS
    # ═══════════════════════════════════════════════════════════════════════════

    def _page_orders(self):
        self._make_title(self.scroll, "🧹 Order Management",
                         "Pending orders delete karein — active positions safe rahenge")

        card = self._make_card(self.scroll)
        ctk.CTkLabel(card, text="🗑️ Delete All Pending Orders",
                     font=("Segoe UI", 14, "bold"),
                     text_color=COLORS["text_primary"]).pack(anchor="w", padx=16, pady=(14, 6))
        ctk.CTkLabel(card, text="Gold (XAUUSDm/XAUUSD) ke saare pending orders delete ho jayenge.\nActive positions SAFE rahenge — unhe koi touch nahi karega.",
                     font=("Segoe UI", 11), text_color=COLORS["text_muted"],
                     justify="left").pack(anchor="w", padx=16)

        ctk.CTkButton(card, text="🧹  DELETE ALL PENDING ORDERS",
                      font=("Segoe UI", 14, "bold"), height=46,
                      fg_color=COLORS["btn_danger"], hover_color="#b91c1c",
                      corner_radius=10,
                      command=self._delete_pendings).pack(padx=16, pady=(12, 4))

        self.orders_output = self._make_output_box(card, height=200)

        # MT5 diagnostics
        card2 = self._make_card(self.scroll)
        ctk.CTkLabel(card2, text="🛠️ MT5 Diagnostics",
                     font=("Segoe UI", 14, "bold"),
                     text_color=COLORS["text_primary"]).pack(anchor="w", padx=16, pady=(14, 8))

        diag_row = ctk.CTkFrame(card2, fg_color="transparent")
        diag_row.pack(fill="x", padx=16, pady=(0, 14))

        ctk.CTkButton(diag_row, text="🛠️ Debug MT5",
                      font=("Segoe UI", 12), height=38,
                      fg_color=COLORS["accent_amber"], hover_color="#d97706",
                      corner_radius=8,
                      command=lambda: self._launch_terminal("debug_mt5.py", "MT5 Debug")).pack(side="left", padx=(0, 8))

        ctk.CTkButton(diag_row, text="🩺 Diagnose MT5",
                      font=("Segoe UI", 12), height=38,
                      fg_color=COLORS["accent_amber"], hover_color="#d97706",
                      corner_radius=8,
                      command=lambda: self._launch_terminal("diagnose_mt5.py", "MT5 Diagnose")).pack(side="left")

    def _delete_pendings(self):
        if not messagebox.askyesno("Confirm", "Kya aap sure hain? Saare pending orders delete ho jayenge."):
            return

        helper = PROJECT_ROOT / "_del_pend.py"
        code = '''
import MetaTrader5 as mt5
if not mt5.initialize():
    print(f"MT5 init failed: {mt5.last_error()}")
    quit()
print("🧹 Deleting pending orders...")
total = 0
for sym in ["XAUUSDm", "XAUUSD"]:
    orders = mt5.orders_get(symbol=sym)
    if orders:
        print(f"  {sym}: {len(orders)} pending orders")
        for o in orders:
            r = mt5.order_send({"action": mt5.TRADE_ACTION_REMOVE, "order": o.ticket})
            if r and r.retcode == mt5.TRADE_RETCODE_DONE: total += 1
        print(f"  ✅ Done")
    else:
        print(f"  {sym}: No pending orders")
print(f"\\n✅ Total {total} orders deleted!")
mt5.shutdown()
'''
        helper.write_text(code, encoding="utf-8")
        self._run_async("_del_pend.py", self.orders_output, timeout=30)

    # ═══════════════════════════════════════════════════════════════════════════
    # PAGE: SETTINGS
    # ═══════════════════════════════════════════════════════════════════════════

    def _page_settings(self):
        self._make_title(self.scroll, "⚙️ Settings",
                         "Configuration files — edit aur save karein")

        # Config.yaml
        card = self._make_card(self.scroll)
        ctk.CTkLabel(card, text="⚙️ config.yaml",
                     font=("Segoe UI", 14, "bold"),
                     text_color=COLORS["text_primary"]).pack(anchor="w", padx=16, pady=(14, 8))

        config_path = PROJECT_ROOT / "config.yaml"
        config_text = config_path.read_text(encoding="utf-8", errors="replace") if config_path.exists() else "# config.yaml not found"

        self.config_editor = ctk.CTkTextbox(card, height=220, fg_color=COLORS["bg_input"],
                                             text_color=COLORS["text_primary"],
                                             font=("Consolas", 11), corner_radius=8,
                                             border_width=1, border_color=COLORS["border"])
        self.config_editor.pack(fill="x", padx=16, pady=(0, 8))
        self.config_editor.insert("1.0", config_text)

        ctk.CTkButton(card, text="💾  Save Config",
                      font=("Segoe UI", 12, "bold"), height=38,
                      fg_color=COLORS["accent_green"], hover_color="#15803d",
                      corner_radius=8,
                      command=self._save_config).pack(padx=16, pady=(0, 14))

        # .env (masked)
        card2 = self._make_card(self.scroll)
        ctk.CTkLabel(card2, text="🔒 .env (masked)",
                     font=("Segoe UI", 14, "bold"),
                     text_color=COLORS["text_primary"]).pack(anchor="w", padx=16, pady=(14, 8))

        env_path = PROJECT_ROOT / ".env"
        if env_path.exists():
            lines = env_path.read_text(encoding="utf-8", errors="replace").splitlines()
            masked = []
            for line in lines:
                s = line.strip()
                if "=" in s and not s.startswith("#"):
                    key, _, val = s.partition("=")
                    masked.append(f"{key.strip()} = •••")
                else:
                    masked.append(s)
            env_text = "\n".join(masked)
        else:
            env_text = "# .env not found"

        tb = ctk.CTkTextbox(card2, height=150, fg_color=COLORS["bg_input"],
                             text_color=COLORS["text_secondary"], font=("Consolas", 10),
                             corner_radius=8, state="normal")
        tb.pack(fill="x", padx=16, pady=(0, 14))
        tb.insert("1.0", env_text)
        tb.configure(state="disabled")

    def _save_config(self):
        try:
            import yaml
            new_text = self.config_editor.get("1.0", "end").strip()
            yaml.safe_load(new_text)  # Validate
            (PROJECT_ROOT / "config.yaml").write_text(new_text)
            messagebox.showinfo("Success", "✅ Config saved!")
        except Exception as e:
            messagebox.showerror("Error", f"Invalid YAML:\n{e}")

    # ═══════════════════════════════════════════════════════════════════════════
    # PAGE: LOGS
    # ═══════════════════════════════════════════════════════════════════════════

    def _page_logs(self):
        self._make_title(self.scroll, "📜 Logs & Reports",
                         "System logs, live reports, aur errors dekhein")

        # Log files
        card = self._make_card(self.scroll)
        ctk.CTkLabel(card, text="📜 System Logs",
                     font=("Segoe UI", 14, "bold"),
                     text_color=COLORS["text_primary"]).pack(anchor="w", padx=16, pady=(14, 8))

        logs_dir = PROJECT_ROOT / "logs"
        log_files = []
        if logs_dir.exists():
            log_files = sorted(
                [f for f in logs_dir.glob("*") if f.is_file() and f.suffix in (".log", ".txt", "")],
                key=os.path.getmtime, reverse=True
            )[:10]

        if log_files:
            log_names = [f"{f.name} ({f.stat().st_size/1024:.1f}KB)" for f in log_files]

            row = ctk.CTkFrame(card, fg_color="transparent")
            row.pack(fill="x", padx=16, pady=4)

            self.log_selector = ctk.CTkComboBox(row, values=log_names, width=350,
                                                  fg_color=COLORS["bg_input"])
            self.log_selector.pack(side="left", padx=(0, 10))

            ctk.CTkButton(row, text="📖 View", width=80, height=32,
                          command=lambda: self._view_log(log_files)).pack(side="left")

            self.log_viewer = ctk.CTkTextbox(card, height=300, fg_color="#0a0e14",
                                              text_color="#94a3b8", font=("Consolas", 10),
                                              corner_radius=8)
            self.log_viewer.pack(fill="x", padx=16, pady=(8, 14))
            self.log_viewer.insert("1.0", "Select a log file and click View")
            self.log_viewer.configure(state="disabled")
        else:
            ctk.CTkLabel(card, text="Koi log file nahi mili",
                         text_color=COLORS["text_muted"]).pack(padx=16, pady=14)

        # Error log
        card2 = self._make_card(self.scroll)
        ctk.CTkLabel(card2, text="❌ Error Log",
                     font=("Segoe UI", 14, "bold"),
                     text_color=COLORS["text_primary"]).pack(anchor="w", padx=16, pady=(14, 8))

        err_log = PROJECT_ROOT / "error.log"
        if err_log.exists() and err_log.stat().st_size > 0:
            err_text = err_log.read_text(encoding="utf-8", errors="ignore")[-3000:]
            tb = ctk.CTkTextbox(card2, height=150, fg_color="#0a0e14",
                                 text_color="#fb7185", font=("Consolas", 10),
                                 corner_radius=8, state="normal")
            tb.pack(fill="x", padx=16, pady=(0, 14))
            tb.insert("1.0", err_text)
            tb.configure(state="disabled")
        else:
            ctk.CTkLabel(card2, text="✅ No errors — all clear!",
                         text_color=COLORS["accent_green"], font=("Segoe UI", 12)).pack(padx=16, pady=14)

    def _view_log(self, log_files):
        idx = 0
        selected = self.log_selector.get()
        for i, f in enumerate(log_files):
            if f.name in selected:
                idx = i
                break

        content = log_files[idx].read_text(encoding="utf-8", errors="ignore")
        lines = content.splitlines()
        if len(lines) > 500:
            content = "\n".join(lines[-500:])

        self.log_viewer.configure(state="normal")
        self.log_viewer.delete("1.0", "end")
        self.log_viewer.insert("1.0", content)
        self.log_viewer.configure(state="disabled")

    # ═══════════════════════════════════════════════════════════════════════════
    # PAGE: TERMINAL
    # ═══════════════════════════════════════════════════════════════════════════

    def _page_terminal(self):
        self._make_title(self.scroll, "🖥️ Terminal",
                         "Koi bhi command yahan se run karein")

        # Quick launch
        card = self._make_card(self.scroll)
        ctk.CTkLabel(card, text="⚡ Quick Launch (New Window)",
                     font=("Segoe UI", 14, "bold"),
                     text_color=COLORS["text_primary"]).pack(anchor="w", padx=16, pady=(14, 8))

        quick = [
            ("📊 Backtesting", "backtesting.py"),
            ("🔴 Live Trading", "live_trading.py"),
            ("📈 Live Dashboard", "live_dashboard.py"),
            ("🌐 Intelligence", "run_market_intelligence.py"),
            ("🛠️ Debug MT5", "debug_mt5.py"),
            ("🩺 Diagnose MT5", "diagnose_mt5.py"),
        ]

        btn_frame = ctk.CTkFrame(card, fg_color="transparent")
        btn_frame.pack(fill="x", padx=16, pady=(0, 14))

        for i, (label, script) in enumerate(quick):
            ctk.CTkButton(btn_frame, text=label, width=150, height=36,
                          font=("Segoe UI", 11), corner_radius=8,
                          fg_color=COLORS["bg_input"], hover_color=COLORS["border"],
                          text_color=COLORS["text_primary"],
                          command=lambda s=script, l=label: self._launch_terminal(s, l)).pack(
                              side="left", padx=4, pady=4)

        # Custom command
        card2 = self._make_card(self.scroll)
        ctk.CTkLabel(card2, text="💻 Custom Command",
                     font=("Segoe UI", 14, "bold"),
                     text_color=COLORS["text_primary"]).pack(anchor="w", padx=16, pady=(14, 8))

        cmd_row = ctk.CTkFrame(card2, fg_color="transparent")
        cmd_row.pack(fill="x", padx=16, pady=4)

        self.cmd_input = ctk.CTkEntry(cmd_row, placeholder_text="python backtesting.py",
                                       fg_color=COLORS["bg_input"], height=38,
                                       font=("Consolas", 12))
        self.cmd_input.pack(side="left", fill="x", expand=True, padx=(0, 8))

        ctk.CTkButton(cmd_row, text="▶️ Run", width=80, height=38,
                      fg_color=COLORS["accent_blue"],
                      command=self._run_custom_cmd).pack(side="left", padx=(0, 4))

        ctk.CTkButton(cmd_row, text="🖥️ Terminal", width=100, height=38,
                      fg_color=COLORS["accent_purple"],
                      command=self._run_custom_terminal).pack(side="left")

        self.cmd_output = self._make_output_box(card2, height=280)

    def _run_custom_cmd(self):
        cmd = self.cmd_input.get().strip()
        if not cmd:
            return

        def worker():
            self.cmd_output.clear()
            self.cmd_output.append(f"▶ {cmd}\n{'─'*50}\n")
            try:
                result = subprocess.run(
                    cmd, shell=True, capture_output=True, text=True,
                    timeout=60, cwd=str(PROJECT_ROOT),
                )
                if result.stdout:
                    self.cmd_output.append(result.stdout)
                if result.stderr:
                    self.cmd_output.append(f"\n⚠ STDERR:\n{result.stderr}")
                self.cmd_output.append(f"\n{'─'*50}\n✅ Exit code: {result.returncode}\n")
            except subprocess.TimeoutExpired:
                self.cmd_output.append("\n⏰ Timeout (60s). Interactive commands ke liye 'Terminal' button use karein.\n")
            except Exception as e:
                self.cmd_output.append(f"\n❌ {e}\n")

        threading.Thread(target=worker, daemon=True).start()

    def _run_custom_terminal(self):
        cmd = self.cmd_input.get().strip()
        if cmd:
            os.system(f'start "Command" cmd /k "cd /d {PROJECT_ROOT} && {cmd}"')

    # ═══════════════════════════════════════════════════════════════════════════
    # CLEANUP
    # ═══════════════════════════════════════════════════════════════════════════

    def _on_close(self):
        # Clean temp files
        for tmp in PROJECT_ROOT.glob("_quick_bt.py"):
            try: tmp.unlink()
            except: pass
        for tmp in PROJECT_ROOT.glob("_auto_live.py"):
            try: tmp.unlink()
            except: pass
        for tmp in PROJECT_ROOT.glob("_del_pend.py"):
            try: tmp.unlink()
            except: pass

        self.destroy()


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    app = NextLevelBrainApp()
    app.mainloop()
