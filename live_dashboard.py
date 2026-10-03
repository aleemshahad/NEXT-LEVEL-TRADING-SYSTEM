import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk, messagebox
import customtkinter as ctk
import pywinstyles
import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import threading
import time
import math
import os
import json
from pathlib import Path
from dotenv import load_dotenv
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.ticker import FuncFormatter

# Load environment variables
load_dotenv()

class LivePortfolioDashboard:
    def __init__(self):
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("dark-blue")

        self.root = ctk.CTk()
        self.root.title("NEXUS TRADING SYSTEM")
        self.root.geometry("1180x750")
        self.root.minsize(1020, 680)
        self.root.resizable(True, True)

        self._apply_window_chrome()

        self.style = ttk.Style()
        self.style.theme_use('clam')
        self._setup_styles()
        
        self.running = True
        self.magic_buy = 777001
        self.magic_sell = 777002
        self.history_days = 30 # Track last 30 days by default
        self.reset_timestamp, self.session_max_drawdown, self.start_balance = self._load_reset_config()
        
        self.trade_history = []
        self.metrics = {
            'total_trades': 0,
            'win_rate': 0.0,
            'total_pnl': 0.0,
            'profit_factor': 0.0,
            'max_drawdown': 0.0
        }
        self.equity_history = self._load_chart_history() # Load persistent history
        self._last_chart_append = 0
        self._chart_anim_job = None
        self._growing = False

        # --- Enhanced curve state ---
        self._anim_mode = None          # "grow" | "pulse" | None
        self._pulse_frame = 0
        self._grow_n = 0                # display points currently revealed
        self._grow_from = 0
        self._grow_to = 0
        self._grow_frame = 0
        self._grow_frames = 12
        self._live_dot = None           # pulsating live-price marker
        self._live_glow = None          # soft halo behind it
        self._disp = None               # sampled display series (np array)
        self._base = 0.0                # start-balance baseline
        self._ylo = 0.0
        self._yhi = 0.0
        self._last_sig = None           # (len, last) used to skip no-op redraws

        self._flash_job = None
        self._flash_label = None
        self._flash_text = ""
        self._flash_color = "#00FF66"
        self._flash_step = 0
        self._last_pnl_seen = None
        self._dot_job = None
        self._dot_step = 0
        self._ticker_job = None
        self._chart_resize_job = None
        
        self._create_widgets()
        
        # Start the update loop on the main thread instead of a background thread
        # to prevent Tkinter silent crashes (Tcl async errors).
        self.root.after(1000, self._update_loop)
        
        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)

    def _apply_window_chrome(self):
        """Native dark title bar + custom window icon (Windows only, best effort)."""
        try:
            pywinstyles.apply_style(self.root, "dark")
            pywinstyles.change_header_color(self.root, self.C['bg'])
            pywinstyles.change_title_color(self.root, "#ffffff")
        except Exception:
            pass
        for icon_name in ("nexus.ico", "assets/nexus.ico", "g-channel.ico"):
            icon_path = Path(__file__).parent / icon_name
            if icon_path.exists():
                try:
                    self.root.iconbitmap(str(icon_path))
                except Exception:
                    pass
                break

    def animate_pnl_flash(self, label, text, base_color):
        """Momentarily brighten a P&L label, then ease it back to its resting color."""
        if not self.running or label is None:
            return
        self._flash_label = label
        self._flash_text = text
        self._flash_color = base_color
        self._flash_step = 0
        if self._flash_job is not None:
            try:
                self.root.after_cancel(self._flash_job)
            except Exception:
                pass
        try:
            label.configure(text=text, text_color=self.C['flash'])
        except Exception:
            return
        self._flash_job = self.root.after(70, self._ease_pnl_flash)

    def _ease_pnl_flash(self):
        """Step the flashing P&L label back toward its normal color."""
        if not self.running or self._flash_label is None:
            self._flash_job = None
            return
        self._flash_step += 1
        if self._flash_step >= 2:
            try:
                self._flash_label.configure(text=self._flash_text, text_color=self._flash_color)
            except Exception:
                pass
            self._flash_job = None
            return
        self._flash_job = self.root.after(70, self._ease_pnl_flash)

    def _animate_status_dot(self):
        """Green pulsing SYSTEM ACTIVE dot."""
        if not self.running:
            self._dot_job = None
            return
        shades = (self.C['green'], '#00cc55', '#009944', '#00cc55')
        try:
            self.status_dot.configure(text_color=shades[self._dot_step % len(shades)])
        except Exception:
            pass
        self._dot_step += 1
        self._dot_job = self.root.after(650, self._animate_status_dot)

    def _setup_styles(self):
        # Modern palette
        self.C = {
            'bg': '#070a0e', 'card': '#0d131a', 'card2': '#0d131a',
            'border': '#182330', 'text': '#ffffff', 'muted': '#7b8b9a',
            'green': '#00FF66', 'mint': '#00E5FF', 'blue': '#3399ff',
            'orange': '#ffa726', 'red': '#FF4D4D', 'purple': '#a78bfa',
            'chip': '#141d27', 'dim': '#7b8b9a', 'flash': '#00FFC8',
        }
        self.style.configure("TFrame", background=self.C['bg'])
        self.style.configure("Card.TFrame", background=self.C['card'], relief="flat", borderwidth=0)
        self.style.configure("TLabel", background=self.C['card'], foreground=self.C['text'], font=('Segoe UI', 10))
        self.style.configure("Header.TLabel", background=self.C['bg'], foreground=self.C['green'], font=('Segoe UI', 16, 'bold'))
        self.style.configure("Stat.TLabel", background=self.C['card'], foreground=self.C['green'], font=('Consolas', 15, 'bold'))
        self.style.configure("Metric.TLabel", background=self.C['card'], foreground=self.C['muted'], font=('Segoe UI', 9))
        self.style.configure("Ticker.TLabel", background=self.C['bg'], foreground=self.C['green'], font=('Consolas', 11, 'italic'))

        # Treeview styles
        self.style.configure("Treeview",
                           background=self.C['card'],
                           foreground="#dfe7f2",
                           fieldbackground=self.C['card'],
                           rowheight=30,
                           font=('Segoe UI', 10),
                           borderwidth=0)
        self.style.map("Treeview", background=[('selected', '#1d3348')])
        self.style.configure("Treeview.Heading", background=self.C['chip'], foreground='#aebbd0',
                           font=('Segoe UI', 9, 'bold'), relief='flat')
        self.style.map("Treeview.Heading", background=[('active', '#223046')])

        # Card helper: bordered rounded frame
        def _card_frame(parent, bg=None):
            return ctk.CTkFrame(parent, fg_color=bg or self.C['card'],
                                border_color=self.C['border'], border_width=1,
                                corner_radius=9)
        self._card = _card_frame

        # Treeview tags for coloring
        self.pos_tree_tags = {
            'profit': {'foreground': '#00FF66'},
            'loss': {'foreground': '#FF4D4D'}
        }

    def _create_widgets(self):
        main_frame = ctk.CTkFrame(self.root, fg_color=self.C['bg'], corner_radius=0)
        main_frame.pack(fill=tk.BOTH, expand=True)
        main_frame.grid_columnconfigure(0, weight=0)
        main_frame.grid_columnconfigure(1, weight=1)
        main_frame.grid_columnconfigure(2, weight=0)
        main_frame.grid_rowconfigure(5, weight=1)

        pad = {"padx": 12}

        # ============ 1. MODERN HEADER (brand + status) ============
        header = ctk.CTkFrame(main_frame, fg_color=self.C['card'],
                              border_color=self.C['border'], border_width=1, corner_radius=9)
        header.grid(row=0, column=0, columnspan=3, sticky="ew", **pad, pady=(6, 0))
        header.grid_columnconfigure(1, weight=1)

        brand_box = ctk.CTkFrame(header, fg_color="transparent")
        brand_box.grid(row=0, column=0, sticky="w", padx=(14, 10), pady=7)
        ctk.CTkLabel(brand_box, text="NEXUS TRADING SYSTEM", text_color="#ffffff",
                     font=ctk.CTkFont(size=19, weight="bold")).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(brand_box, text="• LIVE PERFORMANCE & CONTROL [XAUUSDm]",
                     text_color=self.C['muted'],
                     font=ctk.CTkFont(size=9)).grid(row=1, column=0, sticky="w")

        right_box = ctk.CTkFrame(header, fg_color="transparent")
        right_box.grid(row=0, column=2, sticky="e", padx=16, pady=6)
        self.clock_label = ctk.CTkLabel(right_box, text="--:--:--", text_color=self.C['blue'],
                                        font=ctk.CTkFont(family="Consolas", size=13, weight="bold"))
        self.clock_label.grid(row=0, column=0, sticky="e")
        status_row = ctk.CTkFrame(right_box, fg_color="transparent")
        status_row.grid(row=1, column=0, sticky="e", pady=(2, 0))
        self.status_dot = ctk.CTkLabel(status_row, text="●", text_color=self.C['green'],
                                       font=ctk.CTkFont(size=10))
        self.status_dot.grid(row=0, column=0, padx=(0, 5))
        self.status_label = ctk.CTkLabel(status_row, text="SYSTEM ACTIVE", text_color=self.C['green'],
                                         font=ctk.CTkFont(size=10, weight="bold"))
        self.status_label.grid(row=0, column=1)

        # gradient accent line
        accent = tk.Canvas(main_frame, height=3, highlightthickness=0, bd=0, bg=self.C['bg'])
        accent.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(8, 0))
        aw = accent.winfo_reqwidth() or 1180
        cols = ['#00FF66', '#00E5FF', '#3399ff', '#a78bfa']
        seg = max(1, aw // len(cols))
        for i, c in enumerate(cols):
            accent.create_rectangle(i * seg, 0, (i + 1) * seg + 2, 3, fill=c, outline=c)

        # ============ 2. PERFORMANCE METRICS ROW ============
        perf_container = self._card(main_frame, bg=self.C['card'])
        perf_container.grid(row=2, column=0, columnspan=3, sticky="ew", **pad, pady=(6, 0))
        perf_container.grid_columnconfigure(0, weight=3)
        perf_container.grid_columnconfigure(1, weight=1)

        metrics_host = ctk.CTkFrame(perf_container, fg_color="transparent")
        metrics_host.grid(row=0, column=0, sticky="nsew", padx=4, pady=5)
        for i in range(5):
            metrics_host.grid_columnconfigure(i, weight=1)

        metrics_list = [
            ("Total Trades", "total_trades", self.C['text']),
            ("Win Rate", "win_rate", self.C['mint']),
            ("Total P&L", "total_pnl", self.C['green']),
            ("Profit Factor", "profit_factor", self.C['blue']),
            ("Max Drawdown", "max_drawdown", self.C['red']),
        ]
        self.metric_labels = {}
        for i, (label, key, color) in enumerate(metrics_list):
            m = ctk.CTkFrame(metrics_host, fg_color="transparent", corner_radius=8)
            m.grid(row=0, column=i, sticky="nsew", padx=6)
            ctk.CTkLabel(m, text=f"{label.upper()}", text_color=self.C['muted'],
                         font=ctk.CTkFont(size=8, weight="bold")).grid(row=0, column=0)
            self.metric_labels[key] = ctk.CTkLabel(m, text="--", text_color=color,
                                                   font=ctk.CTkFont(family="Consolas", size=16, weight="bold"))
            self.metric_labels[key].grid(row=1, column=0, pady=(2, 0))

        # --- INSTITUTIONAL FILTERS (Rail Board) ---
        self.ict_frame = ctk.CTkFrame(perf_container, fg_color=self.C['chip'],
                                      border_color=self.C['border'], border_width=1, corner_radius=8)
        self.ict_frame.grid(row=0, column=1, sticky="nsew", padx=8, pady=5)
        for i in range(3):
            self.ict_frame.grid_columnconfigure(i, weight=1)
        ctk.CTkLabel(self.ict_frame, text="INSTITUTIONAL FILTERS", text_color=self.C['mint'],
                     font=ctk.CTkFont(size=8, weight="bold")).grid(row=0, column=0, columnspan=3, pady=(3, 0))
        self.ict_labels = {}
        concepts = [
            ("H4 TREND", "status_h4", self.C['blue']),
            ("TRAP FILTER", "status_trap", self.C['orange']),
            ("D1 PIVOT", "daily_pivot", self.C['green']),
        ]
        for col_i, (label_text, key, color) in enumerate(concepts):
            f = ctk.CTkFrame(self.ict_frame, fg_color="transparent")
            f.grid(row=1, column=col_i, sticky="nsew", padx=6, pady=(0, 4))
            ctk.CTkLabel(f, text=f"{label_text}:", text_color=self.C['muted'],
                         font=ctk.CTkFont(size=8, weight="bold")).grid(row=0, column=0)
            l = ctk.CTkLabel(f, text="--", text_color=color,
                             font=ctk.CTkFont(family="Consolas", size=12, weight="bold"))
            l.grid(row=1, column=0, pady=(2, 0))
            self.ict_labels[key] = l

        # ============ 3. PORTFOLIO SUMMARY CARDS ============
        summary_container = ctk.CTkFrame(main_frame, fg_color="transparent")
        summary_container.grid(row=3, column=0, columnspan=3, sticky="ew", **pad, pady=(6, 0))
        for i in range(6):
            summary_container.grid_columnconfigure(i, weight=1)

        self.cards = {}
        items = [
            ("STARTING BALANCE", "start_val", "#ffffff"),
            ("ACCOUNT BALANCE", "balance_val", "#ffffff"),
            ("FLOATING EQUITY", "equity_val", self.C['blue']),
            ("SESSION PNL", "session_val", self.C['green']),
            ("MAX FLOATING (-)", "drawdown_val", self.C['red']),
            ("MARGIN LEVEL", "margin_val", self.C['mint']),
        ]
        for i, (label, key, color) in enumerate(items):
            card = self._card(summary_container)
            card.grid(row=0, column=i, sticky="nsew", padx=3, pady=3)
            ctk.CTkLabel(card, text=label, text_color=self.C['muted'],
                         font=ctk.CTkFont(size=8, weight="bold")).grid(row=0, column=0, pady=(5, 0))
            self.cards[key] = ctk.CTkLabel(card, text="$0.00", text_color=color,
                                           font=ctk.CTkFont(family="Consolas", size=16, weight="bold"))
            self.cards[key].grid(row=1, column=0, pady=(1, 5))

        # ============ 4. GRID & STRATEGY MONITOR ============
        grid_container = self._card(main_frame)
        grid_container.grid(row=4, column=0, columnspan=3, sticky="ew", **pad, pady=(6, 0))
        grid_container.grid_columnconfigure(0, weight=1)
        head_row = ctk.CTkFrame(grid_container, fg_color="transparent")
        head_row.grid(row=0, column=0, sticky="ew", padx=12, pady=(5, 1))
        ctk.CTkLabel(head_row, text="GRID & STRATEGY MONITOR", text_color=self.C['mint'],
                     font=ctk.CTkFont(size=9, weight="bold")).grid(row=0, column=0, sticky="w")

        status_sub_frame = ctk.CTkFrame(grid_container, fg_color="transparent")
        status_sub_frame.grid(row=1, column=0, sticky="ew", padx=6, pady=(0, 2))

        self.grid_cards = {}
        grid_items = [
            ("STRATEGY", "grid_mode", "#ffffff"),
            ("BIAS / TREND", "current_bias", self.C['blue']),
            ("VOLATILITY ATR", "current_atr", "#ffffff"),
            ("DCA PROGRESS", "grid_progress", "#ffffff"),
            ("VOLUME FLOW", "volume_flow", self.C['purple']),
            ("BASKET PNL", "peak_val", self.C['green']),
            ("SAFETY", "lock_val", self.C['red']),
            ("SEASON", "season_timer", self.C['green']),
        ]
        for i, (label, key, color) in enumerate(grid_items):
            status_sub_frame.grid_columnconfigure(i, weight=1, uniform="grid_items")
            f = ctk.CTkFrame(status_sub_frame, fg_color="transparent")
            f.grid(row=0, column=i, sticky="nsew", padx=(4, 4))
            ctk.CTkLabel(f, text=label, text_color=self.C['muted'],
                         font=ctk.CTkFont(size=8, weight="bold")).grid(row=0, column=0, pady=2)
            self.grid_cards[key] = ctk.CTkLabel(f, text="--", text_color=color,
                                                font=ctk.CTkFont(family="Consolas", size=13, weight="bold"))
            self.grid_cards[key].grid(row=1, column=0, pady=(0, 2))

        # DCA progress bar
        bar_row = ctk.CTkFrame(grid_container, fg_color="transparent")
        bar_row.grid(row=2, column=0, sticky="ew", padx=14, pady=(0, 6))
        bar_row.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(bar_row, text="DCA LEVELS", text_color=self.C['muted'],
                     font=ctk.CTkFont(size=7, weight="bold")).grid(row=0, column=0, sticky="w", padx=(0, 8))
        self.dca_bar = ctk.CTkProgressBar(bar_row, height=14, corner_radius=7,
                                           progress_color=self.C['green'],
                                           fg_color=self.C['border'],
                                           border_color=self.C['card'], border_width=1)
        self.dca_bar.grid(row=0, column=1, sticky="ew")
        self.dca_bar.set(0)

        # ============ 5. CONTENT AREA ============
        self.content_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        self.content_frame.grid(row=5, column=0, columnspan=3, sticky="nsew", **pad, pady=(6, 0))
        self.content_frame.grid_rowconfigure(0, weight=1)
        self.content_frame.grid_columnconfigure(0, weight=1, uniform="cols")
        self.content_frame.grid_columnconfigure(1, weight=1, uniform="cols")
        self.content_frame.grid_columnconfigure(2, weight=1, uniform="cols")

        # Left: Active Positions
        self.left_col = self._card(self.content_frame)
        self.left_col.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        self.left_col.grid_columnconfigure(0, weight=1)
        self.left_col.grid_rowconfigure(1, weight=1)
        ctk.CTkLabel(self.left_col, text="ACTIVE POSITIONS", text_color=self.C['mint'],
                     font=ctk.CTkFont(size=10, weight="bold")).grid(row=0, column=0, sticky="w", padx=10, pady=(6, 2))

        pos_host = ctk.CTkFrame(self.left_col, fg_color="transparent")
        pos_host.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 8))
        pos_host.grid_rowconfigure(0, weight=1)
        pos_host.grid_columnconfigure(0, weight=1)

        self.pos_tree = ttk.Treeview(pos_host, columns=("symbol", "side", "lots", "profit"),
                                    show="headings", height=5)
        self.pos_tree.heading("symbol", text="SYMBOL")
        self.pos_tree.heading("side", text="SIDE")
        self.pos_tree.heading("lots", text="LOTS")
        self.pos_tree.heading("profit", text="PROFIT ($)")
        for col in ("symbol", "side", "lots", "profit"):
            self.pos_tree.column(col, anchor=tk.CENTER, width=78, stretch=True)
        self.pos_tree.tag_configure('profit', foreground='#00FF66')
        self.pos_tree.tag_configure('loss', foreground='#FF4D4D')
        self.pos_tree.grid(row=0, column=0, sticky="nsew")

        # Middle: Equity Chart
        self.mid_col = self._card(self.content_frame)
        self.mid_col.grid(row=0, column=1, sticky="nsew", padx=5)
        self.mid_col.grid_columnconfigure(0, weight=1)
        self.mid_col.grid_rowconfigure(1, weight=1)
        ctk.CTkLabel(self.mid_col, text="PERFORMANCE CURVE (EQUITY)", text_color=self.C['mint'],
                     font=ctk.CTkFont(size=10, weight="bold")).grid(row=0, column=0, sticky="w", padx=10, pady=(6, 2))

        chart_host = ctk.CTkFrame(self.mid_col, fg_color="transparent")
        chart_host.grid(row=1, column=0, sticky="nsew", padx=6, pady=(0, 6))
        chart_host.grid_rowconfigure(0, weight=1)
        chart_host.grid_columnconfigure(0, weight=1)

        self.chart_fig = Figure(figsize=(3.2, 1.7), dpi=100, facecolor=self.C['card'])
        self.chart_ax = self.chart_fig.add_subplot(111)
        self.chart_ax.set_facecolor(self.C['card'])
        self.chart_fig.subplots_adjust(left=0.11, right=0.995, top=0.93, bottom=0.04)
        self.chart_agg = FigureCanvasTkAgg(self.chart_fig, master=chart_host)
        self.chart_canvas = self.chart_agg.get_tk_widget()
        self.chart_canvas.configure(highlightthickness=0, bd=0)
        self.chart_canvas.grid(row=0, column=0, sticky="nsew")
        self.chart_canvas.bind("<Configure>", self._on_chart_resize)

        # Right: Risk + Exposure
        self.right_col = self._card(self.content_frame)
        self.right_col.grid(row=0, column=2, sticky="nsew", padx=(5, 0))
        self.right_col.grid_columnconfigure(0, weight=1)
        self.right_col.grid_rowconfigure(1, weight=1)
        ctk.CTkLabel(self.right_col, text="RISK & EXPOSURE", text_color=self.C['orange'],
                     font=ctk.CTkFont(size=10, weight="bold")).grid(row=0, column=0, sticky="w", padx=10, pady=(8, 2))

        calc_inner = ctk.CTkFrame(self.right_col, fg_color="transparent")
        calc_inner.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 8))
        calc_inner.grid_columnconfigure(0, weight=1)
        calc_inner.grid_columnconfigure(1, weight=1)

        stats_frame = ctk.CTkFrame(calc_inner, fg_color="transparent")
        stats_frame.grid(row=0, column=0, columnspan=2, sticky="ew", pady=2)
        self.live_price_label = ctk.CTkLabel(stats_frame, text="LIVE PRICE: --", text_color="#ffffff",
                                             font=ctk.CTkFont(family="Consolas", size=11, weight="bold"),
                                             anchor="w")
        self.live_price_label.grid(row=0, column=0, sticky="w")
        self.net_lots_label = ctk.CTkLabel(stats_frame, text="NET EXPOSURE: --", text_color="#ffffff",
                                           font=ctk.CTkFont(family="Consolas", size=11, weight="bold"),
                                           anchor="w")
        self.net_lots_label.grid(row=1, column=0, sticky="w")
        self.floating_pnl_label = ctk.CTkLabel(stats_frame, text="CURRENT PNL: --", text_color=self.C['green'],
                                               font=ctk.CTkFont(family="Consolas", size=11, weight="bold"),
                                               anchor="w")
        self.floating_pnl_label.grid(row=2, column=0, sticky="w")

        self.proj_cards = {}
        self._last_log_pos = 0

        ctk.CTkLabel(calc_inner, text="LIVE TERMINAL LOGS", text_color=self.C['mint'],
                     font=ctk.CTkFont(size=9, weight="bold")).grid(row=1, column=0, columnspan=2,
                                                                  sticky="w", pady=(8, 3))
        self.log_text = ctk.CTkTextbox(calc_inner, fg_color=self.C['bg'], text_color="#c9d1d9",
                                       font=ctk.CTkFont(family="Consolas", size=9),
                                       corner_radius=6, border_width=1,
                                       border_color=self.C['border'],
                                       scrollbar_button_color=self.C['border'],
                                       scrollbar_button_hover_color=self.C['dim'])
        self.log_text.grid(row=2, column=0, columnspan=2, sticky="nsew", pady=(0, 2))
        self.log_text.tag_config("INFO", foreground=self.C['green'])
        self.log_text.tag_config("WARNING", foreground=self.C['orange'])
        self.log_text.tag_config("ERROR", foreground=self.C['red'])
        self.log_text.configure(state="disabled")
        calc_inner.grid_rowconfigure(2, weight=1)

        # ============ 6. FOOTER ============
        footer = ctk.CTkFrame(main_frame, fg_color="transparent")
        footer.grid(row=6, column=0, columnspan=3, sticky="ew", **pad, pady=(8, 0))
        for i in range(4):
            footer.grid_columnconfigure(i, weight=0)
        footer.grid_columnconfigure(4, weight=1)
        btn_font = ctk.CTkFont(size=9, weight="bold")
        BTN_W = 146

        self.btn_emergency_reset = ctk.CTkButton(footer, text="EMERGENCY RESET", command=self._emergency_reset,
                                                 width=BTN_W,
                                                 fg_color="#c62828", hover_color="#8e0000",
                                                 text_color="#ffffff", corner_radius=7, height=30, font=btn_font)
        self.btn_emergency_reset.grid(row=0, column=0, sticky="w", padx=(0, 6))

        self.btn_delete_pendings = ctk.CTkButton(footer, text="DELETE PENDINGS", command=self._delete_pendings,
                                                 width=BTN_W,
                                                 fg_color="#f4511e", hover_color="#c43d0d",
                                                 text_color="#ffffff", corner_radius=7, height=30, font=btn_font)
        self.btn_delete_pendings.grid(row=0, column=1, sticky="w", padx=(0, 6))

        self.btn_clear_history = ctk.CTkButton(footer, text="CLEAR HISTORY", command=self._clear_history,
                                               width=BTN_W,
                                               fg_color="#e65100", hover_color="#b84300",
                                               text_color="#ffffff", corner_radius=7, height=30, font=btn_font)
        self.btn_clear_history.grid(row=0, column=2, sticky="w", padx=(0, 6))

        self.btn_full_report = ctk.CTkButton(footer, text="FULL REPORT", command=self._generate_report,
                                             width=BTN_W,
                                             fg_color="#00b0ff", hover_color="#008ecc",
                                             text_color="#06121c", corner_radius=7, height=30, font=btn_font)
        self.btn_full_report.grid(row=0, column=3, sticky="w", padx=(0, 6))

        # ============ 7. TICKER ============
        ticker_bg = ctk.CTkFrame(main_frame, fg_color=self.C['bg'], height=28, corner_radius=0)
        ticker_bg.grid(row=7, column=0, columnspan=3, sticky="ew", pady=(8, 6))
        ticker_bg.grid_propagate(False)
        self.ticker_text = "[RISK DISCLAIMER] FOR EDUCATIONAL PURPOSES ONLY • NOT FINANCIAL ADVICE (NFA) • TRADING FINANCIAL ASSETS INVOLVES HIGH RISK AND CAN RESULT IN CAPITAL LOSS • DO YOUR OWN RESEARCH (DYOR) • NEXUS TRADING SYSTEM ACCEPTS NO LIABILITY FOR TRADING LOSSES"
        self._ticker_font = ctk.CTkFont(family="Consolas", size=11, slant="italic")
        self.ticker_label = ctk.CTkLabel(ticker_bg, text=self.ticker_text * 3,
                                         text_color="#ffcc00", font=self._ticker_font,
                                         anchor="w", corner_radius=0)
        self.ticker_label.place(x=0, y=6)
        self._scroll_ticker()
        self._animate_status_dot()

    def _delete_pendings(self):
        if not messagebox.askyesno("Confirm", "Delete all pending orders?"): return
        orders = mt5.orders_get()
        if orders:
            for o in orders:
                mt5.order_send({"action": mt5.TRADE_ACTION_REMOVE, "order": o.ticket})
            messagebox.showinfo("Success", f"Deleted {len(orders)} pending orders.")

    def _clear_history(self):
        """Reset persistent chart and metrics history without affecting active trades"""
        if not messagebox.askyesno("Confirm Clear", "This will wipe the Equity Curve chart and reset session stats. Active trades will NOT be affected.\n\nContinue?"):
            return
            
        # 1. Reset metrics and timestamps
        acc = mt5.account_info()
        self.start_balance = acc.balance if acc else 0.0
        self.reset_timestamp = int(time.time())
        self.session_max_drawdown = 0.0 # Clear session drawdown too
        self._save_reset_config()
        
        # 2. Reset internal data
        self.trade_history = []
        self.equity_history = [self.start_balance]
        self._save_chart_history()
        self._grow_n = 0
        self._last_sig = None
        self._disp = None
        self.metrics = {
            'total_trades': 0, 'win_rate': 0.0, 'total_pnl': 0.0,
            'profit_factor': 0.0, 'max_drawdown': 0.0
        }
        
        # 3. IMMEDIATELY update UI to show zero/cleaned state
        for key in self.metric_labels:
            default_val = "0.0%" if "rate" in key or "drawdown" in key else ("0" if "trades" in key else "$0.00")
            self.metric_labels[key].configure(text=default_val, text_color=self.C['green'])
            
        self.cards['session_val'].configure(text="$0.00", text_color=self.C['green'])
        self.cards['drawdown_val'].configure(text="$0.00", text_color=self.C['red'])
        self.cards['start_val'].configure(text=f"${self.start_balance:,.2f}")
        
        # 4. Clear chart visual
        self._draw_chart()
        
        messagebox.showinfo("History Cleared", "Dashboard metrics and chart history have been reset successfully.")

    def _scroll_ticker(self):
        """Infinite horizontal scroll for Risk Disclaimer - seamless full-cycle loop."""
        if not hasattr(self, '_ticker_pos'): self._ticker_pos = 0
        if not hasattr(self, '_ticker_cycle'):
            self._ticker_cycle = self._ticker_font.measure(self.ticker_text)
        self._ticker_pos -= 1
        if self._ticker_pos <= -self._ticker_cycle:
            self._ticker_pos += self._ticker_cycle
        self.ticker_label.place(x=self._ticker_pos, y=6)
        if self.running:
            self._ticker_job = self.root.after(40, self._scroll_ticker)

    def _generate_report(self):
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        report_dir = Path("logs/live_reports")
        report_dir.mkdir(parents=True, exist_ok=True)
        
        json_path = report_dir / f"dashboard_report_{timestamp}.json"
        html_path = report_dir / f"performance_report_{timestamp}.html"
        
        # Calculate extended metrics for report
        profits = [t['profit'] for t in self.trade_history]
        total_loss = sum(abs(p) for p in profits if p < 0)
        total_profit = sum(p for p in profits if p > 0)
        
        report_data = {
            'timestamp': datetime.now().isoformat(),
            'metrics': {
                **self.metrics, 
                'total_loss': total_loss, 
                'total_gain': total_profit,
                'max_floating_minus': self.session_max_drawdown  # NEW: Added as requested
            },
            'trades': self.trade_history
        }
        
        # 1. Save JSON
        with open(json_path, 'w') as f:
            json.dump(report_data, f, default=str, indent=4)
        
        # 2. Update Global Index
        self._update_global_index()
        
        # 2. Generate HTML Report
        chart_labels = json.dumps([t['time'] for t in self.trade_history])
        chart_data = json.dumps(list(np.cumsum(profits)) if profits else [0])
        
        pnl_color = "#00e676" if self.metrics['total_pnl'] >= 0 else "#ff5252"
        
        table_rows = ""
        for t in sorted(self.trade_history, key=lambda x: x['time'], reverse=True)[:100]:
            p_color = "profit-pos" if t['profit'] >= 0 else "profit-neg"
            table_rows += f"""
                <tr>
                    <td>{t['time']}</td>
                    <td>{t['symbol']}</td>
                    <td>{t['side']}</td>
                    <td>{t['volume']}</td>
                    <td class="{p_color}">${t['profit']:.2f}</td>
                </tr>
            """

        html_template = f"""
<!DOCTYPE html>
<html>
<head>
    <title>NEXUS TRADING SYSTEM - Performance Report</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #0d1117; color: #c9d1d9; padding: 40px; line-height: 1.6; }}
        .container {{ max-width: 1100px; margin: auto; background: #161b22; padding: 40px; border-radius: 20px; box-shadow: 0 10px 30px rgba(0,0,0,0.5); border: 1px solid #30363d; }}
        h1 {{ color: #00e676; text-align: center; font-size: 2.5em; margin-bottom: 40px; text-transform: uppercase; letter-spacing: 2px; }}
        .stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin-bottom: 40px; }}
        .stat-card {{ background: #21262d; padding: 25px; border-radius: 15px; text-align: center; border: 1px solid #30363d; transition: transform 0.3s; }}
        .stat-card:hover {{ transform: translateY(-5px); border-color: #00e676; }}
        .stat-value {{ font-size: 28px; font-weight: 800; margin-top: 10px; }}
        .stat-label {{ font-size: 12px; color: #8b949e; text-transform: uppercase; font-weight: bold; }}
        .loss-val {{ color: #ff5252; }}
        .gain-val {{ color: #00e676; }}
        .chart-container {{ background: #0d1117; padding: 20px; border-radius: 15px; margin-bottom: 40px; border: 1px solid #30363d; }}
        table {{ width: 100%; border-collapse: separate; border-spacing: 0; margin-top: 20px; border-radius: 10px; overflow: hidden; }}
        th, td {{ padding: 15px; text-align: left; border-bottom: 1px solid #30363d; }}
        th {{ background: #21262d; color: #00e676; font-weight: 600; text-transform: uppercase; font-size: 0.9em; }}
        tr:hover {{ background-color: #21262d; }}
        .profit-pos {{ color: #00e676; font-weight: bold; }}
        .profit-neg {{ color: #ff5252; font-weight: bold; }}
        .footer {{ text-align: center; margin-top: 40px; color: #8b949e; font-size: 0.8em; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🧠 Performance Report</h1>
        <div class="stats">
            <div class="stat-card">
                <div class="stat-label">Total Trades</div>
                <div class="stat-value">{len(profits)}</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Total P&L</div>
                <div class="stat-value" style="color: {pnl_color}">${self.metrics['total_pnl']:.2f}</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Total Minus (Loss)</div>
                <div class="stat-value loss-val">-${total_loss:.2f}</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Win Rate</div>
                <div class="stat-value gain-val">{self.metrics['win_rate']:.1%}</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Profit Factor</div>
                <div class="stat-value">{self.metrics['profit_factor']:.2f}</div>
            </div>
        </div>
        
        <div class="chart-container">
            <canvas id="equityChart"></canvas>
        </div>
        
        <h3>📋 RECENT TRANSACTIONS</h3>
        <table>
            <thead>
                <tr>
                    <th>Time</th>
                    <th>Symbol</th>
                    <th>Side</th>
                    <th>Lots</th>
                    <th>Profit ($)</th>
                </tr>
            </thead>
            <tbody>
                {table_rows}
            </tbody>
        </table>
        <div class="footer">Generated by NEXUS TRADING SYSTEM AI Trading System | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</div>
    </div>

    <script>
        const ctx = document.getElementById('equityChart').getContext('2d');
        new Chart(ctx, {{
            type: 'line',
            data: {{
                labels: {chart_labels},
                datasets: [{{
                    label: 'Cumulative Equity Curve ($)',
                    data: {chart_data},
                    borderColor: '#00e676',
                    borderWidth: 3,
                    pointRadius: 2,
                    backgroundColor: 'rgba(0, 230, 118, 0.1)',
                    fill: true,
                    tension: 0.3
                }}]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                scales: {{
                    x: {{ 
                        grid: {{ color: '#30363d' }},
                        ticks: {{ color: '#8b949e' }}
                    }},
                    y: {{ 
                        grid: {{ color: '#30363d' }},
                        ticks: {{ color: '#8b949e' }}
                    }}
                }},
                plugins: {{
                    legend: {{ display: false }},
                    tooltip: {{
                        backgroundColor: '#161b22',
                        titleColor: '#00e676',
                        bodyColor: '#fff',
                        borderColor: '#30363d',
                        borderWidth: 1
                    }}
                }}
            }}
        }});
    </script>
</body>
</html>
"""
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(html_template)
            
        messagebox.showinfo("Report Saved", f"Performance reports generated:\n- HTML: {html_path.name}\n- JSON: {json_path.name}\n- GLOBAL: index.html updated\n\nLocation: logs/live_reports/")

    def _update_global_index(self):
        """Aggregate all session data into a premium main index.html"""
        try:
            report_dir = Path("logs/live_reports")
            json_files = sorted(list(report_dir.glob("*.json")), key=lambda x: x.name)
            
            all_sessions = []
            for jf in json_files:
                try:
                    with open(jf, 'r') as f:
                        data = json.load(f)
                        # Extract key data for the global chart
                        all_sessions.append({
                            'time': data.get('timestamp', 'N/A')[:16].replace('T', ' '),
                            'pnl': data.get('metrics', {}).get('total_pnl', 0),
                            'minus': data.get('metrics', {}).get('max_floating_minus', 0),
                            'trades': data.get('metrics', {}).get('total_trades', 0),
                            'file': jf.name.replace('.json', '.html').replace('dashboard_report_', 'performance_report_')
                        })
                except: continue

            if not all_sessions: return

            # Generate Graph Data
            labels = [s['time'] for s in all_sessions]
            pnl_data = [s['pnl'] for s in all_sessions]
            minus_data = [abs(s['minus']) for s in all_sessions]
            
            cum_pnl = np.cumsum(pnl_data).tolist()
            
            html_template = f"""
<!DOCTYPE html>
<html>
<head>
    <title>NEXUS TRADING SYSTEM - Global Trading Intelligence</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        body {{ font-family: 'Inter', 'Segoe UI', sans-serif; background-color: #0d1117; color: #c9d1d9; padding: 40px; margin: 0; }}
        .container {{ max-width: 1200px; margin: auto; }}
        .header {{ text-align: center; margin-bottom: 50px; padding: 40px; background: linear-gradient(145deg, #161b22, #0d1117); border-radius: 24px; border: 1px solid #30363d; box-shadow: 0 20px 50px rgba(0,0,0,0.5); }}
        h1 {{ color: #00e676; font-size: 3em; margin: 0; text-transform: uppercase; letter-spacing: 4px; }}
        .subtitle {{ color: #8b949e; font-size: 1.1em; margin-top: 10px; }}
        
        .summary-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 25px; margin-bottom: 50px; }}
        .card {{ background: #161b22; padding: 30px; border-radius: 20px; border: 1px solid #30363d; text-align: center; transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1); }}
        .card:hover {{ transform: translateY(-10px); border-color: #00e676; box-shadow: 0 10px 30px rgba(0, 230, 118, 0.1); }}
        .val {{ font-size: 32px; font-weight: 800; margin-top: 10px; font-family: 'Consolas', monospace; }}
        .lab {{ font-size: 13px; color: #8b949e; text-transform: uppercase; font-weight: bold; letter-spacing: 1px; }}
        
        .chart-container {{ background: #161b22; padding: 30px; border-radius: 24px; border: 1px solid #30363d; margin-bottom: 50px; height: 500px; }}
        
        .session-list {{ background: #161b22; border-radius: 24px; border: 1px solid #30363d; overflow: hidden; }}
        table {{ width: 100%; border-collapse: collapse; }}
        th {{ background: #21262d; color: #00e676; padding: 20px; text-align: left; text-transform: uppercase; font-size: 12px; }}
        td {{ padding: 18px 20px; border-bottom: 1px solid #30363d; font-size: 14px; }}
        tr:hover {{ background: #1c2128; }}
        .btn {{ display: inline-block; padding: 8px 16px; background: #238636; color: white; text-decoration: none; border-radius: 6px; font-size: 12px; font-weight: bold; }}
        .btn:hover {{ background: #2ea043; }}
        .minus-val {{ color: #ff5252; font-weight: bold; }}
        .pnl-pos {{ color: #00e676; font-weight: bold; }}
        .pnl-neg {{ color: #ff5252; font-weight: bold; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🧠 GLOBAL DASHBOARD</h1>
            <div class="subtitle">NEXUS TRADING SYSTEM - Unified Performance Intelligence</div>
        </div>

        <div class="summary-grid">
            <div class="card">
                <div class="lab">Total Sessions</div>
                <div class="val" style="color: #58a6ff;">{len(all_sessions)}</div>
            </div>
            <div class="card">
                <div class="lab">Cumulative PnL</div>
                <div class="val" style="color: {('#00e676' if sum(pnl_data) >= 0 else '#ff5252')};">${sum(pnl_data):,.2f}</div>
            </div>
            <div class="card">
                <div class="lab">Total Trade Count</div>
                <div class="val">{sum(s['trades'] for s in all_sessions)}</div>
            </div>
            <div class="card">
                <div class="lab">Peak Market Minus</div>
                <div class="val" style="color: #ff5252;">-${max(minus_data):,.2f}</div>
            </div>
        </div>

        <div class="chart-container">
            <canvas id="mainChart"></canvas>
        </div>

        <div class="session-list">
            <table>
                <thead>
                    <tr>
                        <th>Session Timestamp</th>
                        <th>Trades</th>
                        <th>Session PnL</th>
                        <th>Max Market Minus ($)</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody>
                    {"".join([f'''<tr>
                        <td>{s['time']}</td>
                        <td>{s['trades']}</td>
                        <td class="{('pnl-pos' if s['pnl'] >= 0 else 'pnl-neg')}">${s['pnl']:.2f}</td>
                        <td class="minus-val">-${abs(s['minus']):.2f}</td>
                        <td><a href="{s['file']}" class="btn">VIEW FULL REPORT</a></td>
                    </tr>''' for s in reversed(all_sessions)])}
                </tbody>
            </table>
        </div>
        
        <p style="text-align: center; color: #8b949e; margin-top: 40px; font-size: 12px;">
            SYSTEM STATUS: ONLINE | DATABASE: SYNCED | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        </p>
    </div>

    <script>
        const ctx = document.getElementById('mainChart').getContext('2d');
        new Chart(ctx, {{
            type: 'line',
            data: {{
                labels: {json.dumps(labels)},
                datasets: [
                    {{
                        label: 'Total Cumulative Profit ($)',
                        data: {json.dumps(cum_pnl)},
                        borderColor: '#00e676',
                        backgroundColor: 'rgba(0, 230, 118, 0.1)',
                        fill: true,
                        tension: 0.3,
                        yAxisID: 'y'
                    }},
                    {{
                        label: 'Market Minus at Peak ($)',
                        data: {json.dumps(minus_data)},
                        borderColor: '#ff5252',
                        backgroundColor: 'rgba(255, 82, 82, 0.1)',
                        borderDash: [5, 5],
                        fill: false,
                        tension: 0.1,
                        yAxisID: 'y1'
                    }}
                ]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                interaction: {{ mode: 'index', intersect: false }},
                plugins: {{
                    tooltip: {{
                        backgroundColor: '#161b22',
                        titleColor: '#00e676',
                        bodyColor: '#fff',
                        borderColor: '#30363d',
                        borderWidth: 1,
                        callbacks: {{
                            label: function(context) {{
                                let label = context.dataset.label || '';
                                if (label) label += ': ';
                                if (context.parsed.y !== null) {{
                                    label += '$' + context.parsed.y.toLocaleString();
                                }}
                                return label;
                            }}
                        }}
                    }}
                }},
                scales: {{
                    y: {{
                        type: 'linear',
                        display: true,
                        position: 'left',
                        grid: {{ color: '#30363d' }},
                        ticks: {{ color: '#00e676' }}
                    }},
                    y1: {{
                        type: 'linear',
                        display: true,
                        position: 'right',
                        grid: {{ drawOnChartArea: false }},
                        ticks: {{ color: '#ff5252' }},
                        title: {{ display: true, text: 'Floating Minus Impact ($)', color: '#ff5252' }}
                    }},
                    x: {{
                        grid: {{ color: '#30363d' }},
                        ticks: {{ color: '#8b949e' }}
                    }}
                }}
            }}
        }});
    </script>
</body>
</html>
"""
            with open(report_dir / "index.html", "w", encoding="utf-8") as f:
                f.write(html_template)
        except Exception as e:
            print(f"Global index update error: {e}")

    def _save_reset_config(self):
        try:
            config_file = Path("logs/reset_config.json")
            config_file.parent.mkdir(exist_ok=True)
            with open(config_file, 'w') as f:
                json.dump({
                    'reset_timestamp': self.reset_timestamp,
                    'session_max_drawdown': self.session_max_drawdown,
                    'start_balance': self.start_balance
                }, f)
        except Exception as e:
            print(f"Failed to save reset config: {e}")

    def _load_reset_config(self):
        try:
            config_file = Path("logs/reset_config.json")
            if config_file.exists() and config_file.stat().st_size > 0:
                with open(config_file, 'r') as f:
                    data = json.load(f)
                    return data.get('reset_timestamp', 0), data.get('session_max_drawdown', 0.0), data.get('start_balance', 0.0)
        except:
            pass
        return 0, 0.0, 0.0

    def _emergency_reset(self):
        if not messagebox.askyesno("🚨 EMERGENCY RESET", "DANGER: This will close ALL open positions, DELETE all pending orders, and RESET dashboard metrics.\n\nAre you absolutely sure?"):
            return
            
        # 1. Close all active positions
        positions = mt5.positions_get()
        closed_count = 0
        if positions:
            for p in positions:
                action = mt5.ORDER_TYPE_SELL if p.type == mt5.POSITION_TYPE_BUY else mt5.ORDER_TYPE_BUY
                tick = mt5.symbol_info_tick(p.symbol)
                if tick:
                    price = tick.bid if p.type == mt5.POSITION_TYPE_BUY else tick.ask
                    request = {
                        "action": mt5.TRADE_ACTION_DEAL,
                        "symbol": p.symbol,
                        "volume": p.volume,
                        "type": action,
                        "position": p.ticket,
                        "price": price,
                        "deviation": 20,
                        "magic": p.magic,
                        "comment": "EMERGENCY_RESET",
                        "type_time": mt5.ORDER_TIME_GTC,
                        "type_filling": mt5.ORDER_FILLING_IOC,
                    }
                    res = mt5.order_send(request)
                    if res.retcode == mt5.TRADE_RETCODE_DONE:
                        closed_count += 1
                    else:
                        print(f"Failed to close {p.ticket}: {res.retcode}")

        # 2. Delete all pending orders
        orders = mt5.orders_get()
        deleted_count = 0
        if orders:
            for o in orders:
                res = mt5.order_send({"action": mt5.TRADE_ACTION_REMOVE, "order": o.ticket})
                if res.retcode == mt5.TRADE_RETCODE_DONE:
                    deleted_count += 1
        
        # 3. Clear Grid State File
        state_file = Path("logs/grid_state.json")
        if state_file.exists():
            try:
                state_file.unlink()
            except Exception as e:
                print(f"Failed to delete state file: {e}")
        
        # 4. Reset Performance Metrics in UI
        acc = mt5.account_info()
        self.start_balance = acc.balance if acc else 0
        self.reset_timestamp = int(time.time())
        self._save_reset_config()
        self.trade_history = []
        # The hist_tree is no longer part of the main display, so this line is removed.
        # for i in self.hist_tree.get_children(): self.hist_tree.delete(i)
        
        # Update metrics to 0 immediately
        for key in self.metric_labels:
            self.metric_labels[key].configure(text="0.0" if "rate" not in key else "0.0%")
        self.cards['session_val'].configure(text="$0.00", text_color=self.C['green'])
        
        # User requested: DO NOT reset max floating (-) in emergency reset
        # self.session_max_drawdown = 0.0 # Reset session max drawdown (REMOVED as requested)
        # self.cards['drawdown_val'].config(text="$0.00") # Update card (REMOVED as requested)
        
        self.equity_history = [] # Clear equity history for chart
        
        messagebox.showinfo("Reset Complete", f"Emergency Reset Successful:\n- Closed: {closed_count} positions\n- Deleted: {deleted_count} pending orders\n- Performance Metrics Resetted.")

    def _update_loop(self):
        terminal_path = r"C:\Program Files\MetaTrader 5\terminal64.exe"
        if not mt5.initialize(path=terminal_path):
            messagebox.showerror("Error", f"MT5 initialize failed: {mt5.last_error()}")
            self.running = False
            return
            
        # Login if needed
        login_str = os.getenv('MT5_LOGIN', '0')
        login = int(login_str) if login_str.isdigit() else 0
        password = os.getenv('MT5_PASSWORD')
        server = os.getenv('MT5_SERVER')
        
        if login and password and server:
            if not mt5.login(login, password=password, server=server):
                print(f"MT5 login failed in dashboard: {mt5.last_error()}")

        if not self.running: return
        
        try:
            # 0. Check if live trading is still active via lock file
            lock_file = Path("logs/trading_active.lock")
            if not lock_file.exists():
                self._on_closing()
                return

            # 1. Update Account and Trading Stats
            acc = mt5.account_info()
            if acc:
                balance = acc.balance
                equity = acc.equity
                
                # Initialize Starting Balance if not set
                if self.start_balance == 0:
                    self.start_balance = balance
                    self._save_reset_config()
                balance = acc.balance
                equity = acc.equity
                
                # Update Trading Cards
                session_pnl = balance - self.start_balance
                session_color = self.C['green'] if session_pnl >= 0 else self.C['red']
                
                self.cards['start_val'].configure(text=f"${self.start_balance:,.2f}")
                self.cards['balance_val'].configure(text=f"${balance:,.2f}")
                self.cards['equity_val'].configure(text=f"${equity:,.2f}")
                self.cards['session_val'].configure(text=f"${session_pnl:,.2f}", text_color=session_color)
                
                # Flash effect whenever session P&L changes
                if self._last_pnl_seen is None or round(session_pnl, 2) != self._last_pnl_seen:
                    self._last_pnl_seen = round(session_pnl, 2)
                    self.animate_pnl_flash(self.cards['session_val'], f"${session_pnl:,.2f}", session_color)
                
                margin_pct = f"{acc.margin_level:.1f}%" if acc.margin_level else "0%"
                self.cards['margin_val'].configure(text=margin_pct)
                
                # Track Chart History (Persistent & Long-Term)
                # Equity (balance + floating P&L) keeps the curve alive intraday
                # instead of a flat realized-balance staircase.
                now = time.time()
                if not self.equity_history:
                    self.equity_history.append(self.start_balance or equity)
                
                # Append every ~5s when equity moved, else heartbeat every 60s
                last_point = self.equity_history[-1]
                delta_sufficient = abs(equity - last_point) > 0.005
                if (now - self._last_chart_append > 5 and delta_sufficient) or now - self._last_chart_append > 60:
                    self.equity_history.append(round(equity, 2))
                    if len(self.equity_history) > 300: self.equity_history.pop(0)
                    self._last_chart_append = now
                    self._save_chart_history()

            positions = mt5.positions_get()
            current_floating_pnl = sum(p.profit for p in positions) if positions else 0.0
            
            # Update Max Floating Minus Tracker
            if current_floating_pnl < self.session_max_drawdown:
                self.session_max_drawdown = current_floating_pnl
                self._save_reset_config() # Persist new drawdown peak
            
            self.cards['drawdown_val'].configure(text=f"${self.session_max_drawdown:,.2f}")
            
            self._draw_chart(animate=True)
            self._update_risk_calculator(positions)
            self._update_positions_tree(positions)
            self._update_full_history()
            self._update_grid_status()
            self._update_log_console()

            # Live clock
            self.clock_label.configure(text=datetime.now().strftime('%H:%M:%S'))
            
        except Exception as e:
            print(f"UI Update error: {e}")
        
        # Schedule the next tick
        if self.running:
            self.root.after(1000, self._update_loop)

    def _on_chart_resize(self, event):
        """Keep the matplotlib figure matched to the widget size (debounced)."""
        w, h = event.width, event.height
        if w < 40 or h < 40:
            return
        if self._chart_resize_job is not None:
            try:
                self.root.after_cancel(self._chart_resize_job)
            except Exception:
                pass
        self._chart_resize_job = self.root.after(120, lambda: self._apply_chart_size(w, h))

    def _apply_chart_size(self, w, h):
        self._chart_resize_job = None
        try:
            dpi = self.chart_fig.dpi
            self.chart_fig.set_size_inches(w / dpi, h / dpi)
            self.chart_agg.draw_idle()
        except Exception as e:
            print(f"Chart resize error: {e}")

    def _stop_chart_anim(self):
        if self._chart_anim_job is not None:
            try:
                self.root.after_cancel(self._chart_anim_job)
            except Exception:
                pass
            self._chart_anim_job = None
        self._anim_mode = None

    def _schedule_anim(self, delay_ms, mode):
        """Cancel any pending anim job and schedule a new one with the given mode."""
        if self._chart_anim_job is not None:
            try:
                self.root.after_cancel(self._chart_anim_job)
            except Exception:
                pass
            self._chart_anim_job = None
        self._anim_mode = mode
        self._chart_anim_job = self.root.after(delay_ms, self._tick_anim)

    def _tick_anim(self):
        self._chart_anim_job = None
        if not self.running:
            self._anim_mode = None
            return
        mode = self._anim_mode
        self._anim_mode = None
        try:
            if mode == "grow":
                # Smooth eased reveal of the freshly appended points.
                self._grow_frame += 1
                t = self._grow_frame / float(self._grow_frames)
                ease = 1.0 - (1.0 - t) ** 3  # easeOutCubic
                n = self._grow_from + int(round((self._grow_to - self._grow_from) * ease))
                if n >= self._grow_to or self._grow_frame >= self._grow_frames:
                    n = self._grow_to
                self._grow_n = n
                self._render_curve()
                if n >= self._grow_to:
                    self._growing = False
                    self._start_pulse_anim()
                else:
                    self._schedule_anim(50, "grow")
            elif mode == "pulse":
                self._pulse_frame += 1
                self._step_pulse_render()
                self._schedule_anim(72, "pulse")
        except Exception as e:
            print(f"Chart anim error: {e}")
            self._anim_mode = None
            self._chart_anim_job = None

    def _start_pulse_anim(self):
        """Breathing halo on the live dot (continuous but cheap & smooth)."""
        if self._live_dot is None:
            return
        self._schedule_anim(72, "pulse")

    def _step_pulse_render(self):
        if self._live_dot is None:
            self._anim_mode = None
            return
        t = (self._pulse_frame % 26) / 26.0
        wave = (1.0 - math.cos(t * 2.0 * math.pi)) / 2.0
        if self._live_glow is not None:
            self._live_glow.set_markersize(9.0 + wave * 12.0)
            self._live_glow.set_alpha(0.30 * (1.0 - wave * 0.6))
        if self._live_dot is not None:
            self._live_dot.set_markersize(4.6 + wave * 1.1)
        self.chart_agg.draw_idle()

    def _sample_series(self, points, target=160):
        """Downsample a long point list to `target` evenly spaced samples,
        always keeping the very last (live) point intact."""
        n = len(points)
        if n <= target:
            return np.asarray(points, dtype=float)
        idx = np.linspace(0, n - 1, target).round().astype(int)
        idx[-1] = n - 1
        return np.asarray(np.take(points, idx), dtype=float)

    def _render_empty(self):
        ax = self.chart_ax
        ax.clear()
        ax.set_xticks([]); ax.set_yticks([])
        for spine in ax.spines.values():
            spine.set_visible(False)
        ax.text(0.5, 0.56, "COLLECTING EQUITY DATA", transform=ax.transAxes,
                ha="center", va="center", color=self.C['dim'], fontsize=8, family="Consolas")
        ax.text(0.5, 0.44, "appending from MT5 every few seconds", transform=ax.transAxes,
                ha="center", va="center", color=self.C['chip'], fontsize=6.5, family="Consolas")
        self.chart_fig.patch.set_facecolor(self.C['card'])
        self.chart_agg.draw_idle()

    def _render_curve(self):
        """Professional equity curve: glowing gradient line, area fill to the
        start-balance baseline, muted grid and a pulsating live dot."""
        ax = self.chart_ax
        ax.clear()
        ax.set_facecolor(self.C['card'])
        self._live_dot = None
        self._live_glow = None

        disp = self._disp
        if disp is None or len(disp) < 2:
            self._render_empty()
            return

        n = max(2, min(self._grow_n, len(disp)))
        xs = np.arange(n, dtype=float)
        ys = disp[:n]

        ax.set_xlim(0, len(disp) - 1)
        ax.set_ylim(self._ylo, self._yhi)

        up = ys[-1] >= self._base
        col = self.C['green'] if up else self.C['red']

        # Start-balance dashed baseline + label
        ax.axhline(self._base, color=self.C['border'], lw=0.9, ls=(0, (4, 3)), zorder=1)
        ax.text(0.006, 0.02, f"START ${self._base:,.0f}", transform=ax.transAxes,
                color=self.C['muted'], fontsize=6.5, family="Consolas",
                va="bottom", ha="left", zorder=2)

        # Soft area fill under the curve down to the baseline
        ax.fill_between(xs, ys, self._base, color=col, alpha=0.12,
                        linewidth=0, zorder=2)

        # Glow pass (wide, translucent) + crisp core line
        ax.plot(xs, ys, color=col, linewidth=5.0, alpha=0.16,
                solid_capstyle="round", zorder=3)
        ax.plot(xs, ys, color=col, linewidth=2.0,
                solid_capstyle="round", zorder=4)

        # Live dot + halo
        (self._live_glow,) = ax.plot([xs[-1]], [ys[-1]], marker="o", linestyle="none",
                                     markersize=13, color=col, alpha=0.30, zorder=5)
        (self._live_dot,) = ax.plot([xs[-1]], [ys[-1]], marker="o", linestyle="none",
                                    markersize=5, color=self.C['mint'],
                                    markeredgecolor=col, markeredgewidth=1.2, zorder=6)

        # Grid + spines + dims
        ax.grid(True, axis="y", linestyle=":", linewidth=0.7, color=self.C['chip'])
        ax.set_axisbelow(True)
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['left'].set_visible(True)
        ax.spines['bottom'].set_visible(True)
        ax.spines['left'].set_color(self.C['border'])
        ax.spines['bottom'].set_color(self.C['border'])
        ax.tick_params(colors=self.C['dim'], labelsize=7, length=0)
        for lbl in ax.get_xticklabels():
            lbl.set_color(self.C['dim'])
        for lbl in ax.get_yticklabels():
            lbl.set_color(self.C['dim'])
            lbl.set_fontfamily("Consolas")
        ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:,.0f}"))
        ax.set_xticks([])

        # Live value + session-change badge (anchored to the top-right)
        arrow = "▲" if up else "▼"
        chg = ys[-1] - self._base
        pct = (chg / self._base * 100.0) if self._base else 0.0
        ax.text(0.985, 0.93, f"{arrow} {ys[-1]:,.2f}", transform=ax.transAxes,
                color=col, fontsize=8, weight="bold", family="Consolas",
                va="top", ha="right", zorder=7)
        ax.text(0.985, 0.80, f"{chg:+,.2f}  ({pct:+.2f}%)", transform=ax.transAxes,
                color=self.C['muted'], fontsize=6.5, family="Consolas",
                va="top", ha="right", zorder=7)

        # Animated hint during grow
        if self._growing and n < len(disp):
            ax.text(0.5, 0.97, "REPLAYING…", transform=ax.transAxes,
                    color=self.C['mint'], fontsize=6, family="Consolas",
                    va="top", ha="center", zorder=8)

        self.chart_fig.patch.set_facecolor(self.C['card'])
        self.chart_agg.draw_idle()

    def _draw_chart(self, animate=False):
        try:
            points = self.equity_history
            sig = (len(points), points[-1] if points else None)
            if self._last_sig == sig:
                return
            self._last_sig = sig

            self._stop_chart_anim()
            if not points or len(points) < 2:
                self._grow_n = 0
                self._render_empty()
                return

            # Downsample for display and anchor the y-range so the curve always
            # breathes visibly around the baseline (no dead space / flat lines).
            disp = self._sample_series(points, 160)
            base = float(self.start_balance) if self.start_balance else float(points[0])

            lo = min(float(disp.min()), base)
            hi = max(float(disp.max()), base)
            raw = hi - lo
            pad = max(raw * 0.10, max(lo * 0.002, 25.0))
            self._ylo, self._yhi = lo - pad, hi + pad

            prev_n = self._grow_n if self._grow_to == len(disp) else max(2, self._grow_n)
            self._disp = disp
            self._base = base
            self._grow_to = len(disp)

            if animate and self._grow_to > prev_n:
                self._grow_from = max(2, prev_n)
                self._grow_frame = 0
                span = self._grow_to - self._grow_from
                self._grow_frames = min(max(int(span * 0.45), 10), 26)
                self._grow_n = self._grow_from
                self._anim_mode = "grow"
                self._growing = True
                self._render_curve()
                self._schedule_anim(50, "grow")
                return

            self._grow_n = self._grow_to
            self._growing = False
            self._render_curve()
            self._start_pulse_anim()
        except Exception as e:
            print(f"Chart draw error: {e}")

    def _load_chart_history(self):
        try:
            path = Path("logs/chart_history.json")
            if path.exists() and path.stat().st_size > 0:
                with open(path, 'r') as f:
                    return json.load(f)
        except: pass
        return []

    def _save_chart_history(self):
        try:
            path = Path("logs/chart_history.json")
            path.parent.mkdir(exist_ok=True)
            with open(path, 'w') as f:
                json.dump(self.equity_history, f)
        except: pass

    def _update_risk_calculator(self, positions):
        try:
            # 1. Detect active symbol
            symbol = "XAUUSDc"
            if positions:
                symbol = positions[0].symbol
            
            # 2. Update Live Price
            tick = mt5.symbol_info_tick(symbol)
            if tick:
                self.live_price_label.configure(text=f"LIVE PRICE: {tick.bid:.3f}")
            
            # 3. Calculate Exposure & Floating
            current_floating_pnl = sum(p.profit for p in positions) if positions else 0.0
            pnl_color = self.C['green'] if current_floating_pnl >= 0 else self.C['red']
            self.floating_pnl_label.configure(text=f"CURRENT PNL: ${current_floating_pnl:,.2f}", text_color=pnl_color)

            if not positions:
                self.net_lots_label.configure(text="NET EXPOSURE: 0.00")
                for pips in self.proj_cards:
                    self.proj_cards[pips].configure(text="$0.00", text_color=self.C['dim'])
                return

            total_buy_vol = sum(p.volume for p in positions if p.type == mt5.POSITION_TYPE_BUY)
            total_sell_vol = sum(p.volume for p in positions if p.type == mt5.POSITION_TYPE_SELL)
            net_vol = total_buy_vol - total_sell_vol 
            
            direction = "BUY (Long)" if net_vol > 0 else "SELL (Short)" if net_vol < 0 else "HEDGED"
            self.net_lots_label.configure(text=f"NET EXPOSURE: {abs(net_vol):.2f} Lots {direction}")
            
            # 4. Scenario Projections (Total PnL = Current + Movement Impact)
            # Gold: $1 move (100 pips) = Lots * 100.
            # Example: 1 Lot * $10 move = $1000 impact.
            for pips in [1000, 2000, 5000, 10000, 15000, 30000]:
                movement_impact = abs(net_vol) * pips # Pips * Vol = Impact in $
                total_projected_pnl = current_floating_pnl - movement_impact
                
                proj_color = self.C['green'] if total_projected_pnl >= 0 else self.C['red']
                if pips in self.proj_cards:
                    self.proj_cards[pips].configure(text=f"${total_projected_pnl:,.2f}", text_color=proj_color)
                
        except Exception as e:
            print(f"Risk calc error: {e}")

    # _update_chart removed as requested

    def _compute_h4_trend(self, symbol):
        """Always-on H4 trend from latest H4 candles - never returns placeholder."""
        try:
            rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_H4, 0, 30)
            if rates is None or len(rates) < 20:
                return "NORMAL", "#ffa726"
            df = pd.DataFrame(rates)
            closes = df["close"].values
            fast = float(np.mean(closes[-5:]))
            slow = float(np.mean(closes[-20:]))
            if fast > slow * 1.0005: return "BULLISH", "#00e676"
            if fast < slow * 0.9995: return "BEARISH", "#ff5252"
            return "NEUTRAL", "#ffa726"
        except Exception:
            return "NORMAL", "#ffa726"

    def _compute_trap_filter(self, symbol):
        """Always-on trap/liquidity-sweep filter from latest H4 candles."""
        try:
            rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_H4, 0, 20)
            if rates is None or len(rates) < 8:
                return "CLEAR", "#ffa726"
            df = pd.DataFrame(rates)
            window = df.iloc[-8:-1]
            last = df.iloc[-1]
            swept_high = float(last["high"]) > float(window["high"].max()) and float(last["close"]) < float(window["high"].max())
            swept_low = float(last["low"]) < float(window["low"].min()) and float(last["close"]) > float(window["low"].min())
            return ("CONFIRMED", "#00e676") if (swept_high or swept_low) else ("CLEAR", "#ffa726")
        except Exception:
            return "CLEAR", "#ffa726"

    def _compute_daily_pivot(self, symbol):
        """Always-on classic D1 pivot from the previous (closed) D1 candle."""
        try:
            rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_D1, 0, 2)
            if rates is None or len(rates) < 2:
                return 0.0
            prev = rates[-2]
            H = float(prev["high"]); L = float(prev["low"]); C = float(prev["close"])
            return round((H + L + C) / 3.0, 2)
        except Exception:
            return 0.0

    def _compute_live_atr(self, symbol):
        """Always-on ATR from latest M15 candles."""
        try:
            rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M15, 0, 30)
            if rates is None or len(rates) < 14:
                return 1.0
            df = pd.DataFrame(rates)
            tr = np.maximum(df["high"] - df["low"], np.maximum(abs(df["high"] - df["close"].shift(1)), abs(df["low"] - df["close"].shift(1))))
            return float(tr.rolling(14).mean().iloc[-1])
        except Exception:
            return 1.0

    def _update_grid_status(self):
        try:
            state = {}
            state_file = Path("logs/grid_state.json")
            if state_file.exists():
                with open(state_file, 'r') as f:
                    state = json.load(f)

            all_positions = mt5.positions_get()
            active_syms = set(p.symbol for p in all_positions) if all_positions else set()

            # Symbol selection: prefer live positions, else state, else default
            symbol = None
            if all_positions:
                symbol = max(active_syms, key=lambda s: sum(p.volume for p in all_positions if p.symbol == s))
            if not symbol and state:
                symbol = "XAUUSDc" if "XAUUSDc" in state else list(state.keys())[0]
            if not symbol:
                symbol = "XAUUSDc"

            data = state.get(symbol, {}) or {}

            # --- Always-on Institutional Filters (never "--" or "OFF") ---
            h4_val, h4_col = self._compute_h4_trend(symbol)
            if data.get("status_h4") in ("BULLISH", "BEARISH", "NEUTRAL", "NORMAL", "TREND EXP"):
                h4_val = data["status_h4"]
                h4_col = "#ff5252" if h4_val == "TREND EXP" else "#00e676"

            trap_val, trap_col = self._compute_trap_filter(symbol)
            if data.get("status_trap"):
                trap_val = data["status_trap"]
                trap_col = "#00e676" if trap_val == "CONFIRMED" else "#ffa726"

            pivot = self._compute_daily_pivot(symbol)
            if data.get("daily_pivot"):
                pivot = float(data["daily_pivot"])

            self.ict_labels['status_h4'].configure(text=h4_val, text_color=h4_col)
            self.ict_labels['status_trap'].configure(text=trap_val, text_color=trap_col)
            self.ict_labels['daily_pivot'].configure(text=f"${pivot:.2f}" if pivot > 0 else "--", text_color=self.C['blue'])

            # --- Grid & Strategy Monitor: real-time computed state ---
            strategy = data.get('strategy', 'SYSTEM ACTIVE')
            bias = data.get('bias', h4_val)
            atr = data.get('atr', self._compute_live_atr(symbol))
            is_trailing = data.get('is_trailing', False)
            level_cnt = data.get('level_count', data.get('last_index', 0))
            if not level_cnt and all_positions:
                level_cnt = len([p for p in all_positions if p.symbol == symbol])
            max_lvl = data.get('max_dca_levels', 6)
            frozen_tp = data.get('min_profit', data.get('basket_target_pivot', 0.0))
            tp_str = f"TP@{frozen_tp:.2f}" if frozen_tp > 0 else "--"
            progress = f"LVL {level_cnt} | {tp_str}"

            positions = mt5.positions_get(symbol=symbol)
            basket_pnl = sum(p.profit for p in positions) if positions else 0.0

            self.grid_cards['grid_mode'].configure(text=strategy)
            self.grid_cards['current_bias'].configure(text=bias)
            self.grid_cards['current_atr'].configure(text=f"{atr:.2f}")
            self.grid_cards['grid_progress'].configure(text=progress)

            # Volume flow: from state, else live monitoring state
            vf = data.get('volume_flow') or {}
            if vf.get('score') is not None:
                arrow = '▲' if vf.get('bullish') else '▼'
                vcolor = self.C['green'] if vf.get('bullish') else self.C['red']
                self.grid_cards['volume_flow'].configure(text=f"{arrow} {vf['score']:.2f}", text_color=vcolor)
            else:
                self.grid_cards['volume_flow'].configure(text="WATCHING", text_color=self.C['purple'])

            # DCA progress bar
            self._draw_dca_bar(level_cnt, max_lvl)

            pnl_col = self.C['green'] if basket_pnl >= 0 else self.C['red']
            if is_trailing: pnl_col = self.C['blue']
            self.grid_cards['peak_val'].configure(text=f"${basket_pnl:,.2f}", text_color=pnl_col)

            # Safety Level: Spread Guard status OR Trailing Status
            if is_trailing:
                self.grid_cards['lock_val'].configure(text="TRAILING", text_color=self.C['blue'])
            else:
                tick = mt5.symbol_info_tick(symbol)
                if tick:
                    spread = abs(tick.ask - tick.bid)
                    limit = atr * 0.1
                    if spread > limit:
                        self.grid_cards['lock_val'].configure(text="PAUSED", text_color=self.C['orange'])
                    else:
                        self.grid_cards['lock_val'].configure(text="SAFE", text_color=self.C['green'])
        except Exception as e:
            print(f"Grid Status Update error: {e}")

    def _draw_dca_bar(self, level_cnt, max_lvl):
        try:
            max_lvl = max(1, int(max_lvl))
            level_cnt = max(0, int(level_cnt))
            self.dca_bar.set(min(1.0, level_cnt / max_lvl))
        except Exception as e:
            print(f"DCA bar error: {e}")

    def _update_log_console(self):
        """Read and append latest logs from the shared log file"""
        try:
            log_file = Path("logs/latest_intelligence_report.txt")
            if not log_file.exists(): return
            
            with open(log_file, 'r', encoding='latin-1') as f:
                content = f.read().splitlines()
                
            new_lines = content[self._last_log_pos:]
            if new_lines:
                self.log_text.configure(state="normal")
                for line in new_lines:
                    tag = "INFO"
                    if "WARNING" in line: tag = "WARNING"
                    elif "ERROR" in line: tag = "ERROR"
                    self.log_text.insert("end", line + "\n", tag)
                
                self.log_text.see("end")
                self.log_text.configure(state="disabled")
                self._last_log_pos = len(content)
        except Exception as e:
            print(f"Log console update error: {e}")

    def _update_positions_tree(self, positions):
        # Selected items tracking if needed
        for i in self.pos_tree.get_children():
            self.pos_tree.delete(i)
            
        if not positions:
            return
            
        for p in positions:
            side = "BUY" if p.type == mt5.POSITION_TYPE_BUY else "SELL"
            profit = p.profit
            tag = 'profit' if profit >= 0 else 'loss'
            self.pos_tree.insert("", tk.END, values=(
                p.symbol, side, p.volume, f"{profit:.2f}"
            ), tags=(tag,))

    def _update_full_history(self):
        from_date = datetime.now() - timedelta(days=self.history_days)
        to_date = datetime.now() + timedelta(days=1)
        
        # --- Update Season Timer (Live every second) ---
        elapsed = int(time.time()) - self.reset_timestamp
        days = elapsed // 86400
        hours = (elapsed % 86400) // 3600
        minutes = (elapsed % 3600) // 60
        seconds = elapsed % 60
        time_str = f"{days}D {hours}H {minutes}M {seconds}S"
        if 'season_timer' in self.grid_cards:
            self.grid_cards['season_timer'].configure(text=time_str, text_color=self.C['green'])

        deals = mt5.history_deals_get(from_date, to_date)
        if deals:
            closed_deals = [d for d in deals if d.entry == 1 and d.time > self.reset_timestamp]
            
            new_history = []
            for d in closed_deals:
                new_history.append({
                    'time': datetime.fromtimestamp(d.time).strftime('%Y-%m-%d %H:%M'),
                    'symbol': d.symbol,
                    'side': 'BUY' if d.type == mt5.DEAL_TYPE_BUY else 'SELL',
                    'volume': d.volume,
                    'profit': d.profit + d.commission + d.swap,
                    'comment': d.comment or ""
                })
            
            if len(new_history) != len(self.trade_history):
                self.trade_history = new_history
                # hist_tree removed from UI, skipping update

            profits = [h['profit'] for h in self.trade_history]
            if profits:
                wins = [p for p in profits if p > 0]
                losses = [p for p in profits if p <= 0]
                
                total_pnl = sum(profits)
                win_rate = len(wins) / len(profits) if profits else 0
                
                gross_profit = sum(wins)
                gross_loss = abs(sum(losses))
                profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
                
                cum_pnl = np.cumsum(profits)
                acc_info = mt5.account_info()
                base_balance = acc_info.balance if acc_info else 10000.0
                equity_curve = base_balance + cum_pnl
                peak = np.maximum.accumulate(equity_curve)
                dd_pct = (peak - equity_curve) / peak * 100
                max_dd_pct = np.max(dd_pct) if len(dd_pct) > 0 else 0
                
                self.metrics = {
                    'total_trades': len(profits), 'win_rate': win_rate, 'total_pnl': total_pnl,
                    'profit_factor': profit_factor, 'max_drawdown': max_dd_pct
                }
                
                self.metric_labels['total_trades'].configure(text=str(len(profits)))
                self.metric_labels['win_rate'].configure(text=f"{win_rate:.1%}")
                pnl_color = self.C['green'] if total_pnl >= 0 else self.C['red']
                self.metric_labels['total_pnl'].configure(text=f"${total_pnl:,.2f}", text_color=pnl_color)
                self.metric_labels['profit_factor'].configure(text=f"{profit_factor:.2f}")
                self.metric_labels['max_drawdown'].configure(text=f"{max_dd_pct:.2f}%")
            else:
                self._reset_labels_to_zero()
        else:
            self._reset_labels_to_zero()

    def _reset_labels_to_zero(self):
        """Helper to ensure UI labels show zeroed state when no history exists"""
        self.metric_labels['total_trades'].configure(text="0")
        self.metric_labels['win_rate'].configure(text="0.0%")
        self.metric_labels['total_pnl'].configure(text="$0.00", text_color=self.C['green'])
        self.metric_labels['profit_factor'].configure(text="0.00")
        self.metric_labels['max_drawdown'].configure(text="0.00%")
        self.metrics = {
            'total_trades': 0, 'win_rate': 0.0, 'total_pnl': 0.0,
            'profit_factor': 0.0, 'max_drawdown': 0.0
        }
                
                # Session PNL (Last 24h) removed to avoid overwriting the Session Growth metric 
                # (Balance - StartBalance) calculated in the main update loop.


    def _on_closing(self):
        self.running = False
        for job in (self._flash_job, self._dot_job, self._ticker_job, self._chart_resize_job, self._chart_anim_job):
            if job is not None:
                try:
                    self.root.after_cancel(job)
                except Exception:
                    pass
        self._flash_job = self._dot_job = self._ticker_job = self._chart_resize_job = self._chart_anim_job = None
        self._live_dot = None
        self._live_glow = None
        self.root.destroy()

    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    app = LivePortfolioDashboard()
    app.run()
