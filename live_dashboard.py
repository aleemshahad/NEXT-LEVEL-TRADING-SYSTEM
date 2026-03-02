import customtkinter as ctk
import tkinter as tk
from tkinter import ttk, messagebox
import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import threading
import time
import os
import json
from pathlib import Path
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from liquidity_engine import LiquidityEngine
try:
    import winsound
except ImportError:
    winsound = None

# --- Theme & Colors ---
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

COLORS = {
    "bg_dark": "#0D0D0D",
    "bg_card": "#1A1A1A",
    "neon_green": "#00FF7F",
    "neon_blue": "#1E90FF",
    "neon_red": "#FF4500",
    "neon_yellow": "#FFFF00",
    "text_primary": "#FFFFFF",
    "text_secondary": "#B0B0B0",
    "border": "#2A2A2A",
    "glass_bg": "#121212",
    "glass_highlight": "#252525",
    "bsl_color": "#00FF7F",
    "ssl_color": "#FF4500",
}

class LivePortfolioDashboard(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("🧠 NEXT LEVEL BRAIN - LIVE PERFORMANCE & CONTROL")
        self.geometry("1300x910")
        self.configure(fg_color=COLORS["bg_dark"])
        
        self.running = True
        self.magic_buy = 777001
        self.magic_sell = 777002
        self.history_days = 30
        
        self.trade_history = []
        self.metrics = {
            'total_trades': 0,
            'win_rate': 0.0,
            'total_pnl': 0.0,
            'profit_factor': 0.0,
            'max_drawdown': 0.0
        }
        self.last_hits = -1 
        
        self.unit = "$"
        self.active_symbol = "XAUUSDm"
        
        self.session_stats_file = Path("logs/dashboard_session_stats.json")
        self.accumulated_seconds = self._load_session_stats()
        self.start_time = None 
        self._last_history_update = 0 
        
        # --- Liquidity Intelligence Engine ---
        self.liq_engine = LiquidityEngine(self.active_symbol)
        self.liq_engine.start()
        
        self._setup_styles()
        self._create_widgets()
        
        # Start background update thread
        self.update_thread = threading.Thread(target=self._update_loop, daemon=True)
        self.update_thread.start()
        
        # Start high-frequency timer tick (Every 1 second)
        self._tick_timer()
        
        self.protocol("WM_DELETE_WINDOW", self._on_closing)

    def _load_session_stats(self):
        try:
            if self.session_stats_file.exists():
                with open(self.session_stats_file, 'r') as f:
                    return json.load(f).get('accumulated_seconds', 0)
        except Exception: pass
        return 0

    def _save_session_stats(self):
        try:
            self.session_stats_file.parent.mkdir(parents=True, exist_ok=True)
            current_session = (time.time() - self.start_time) if self.start_time else 0
            total = self.accumulated_seconds + current_session
            with open(self.session_stats_file, 'w') as f:
                json.dump({'accumulated_seconds': total}, f)
        except Exception: pass

    def _setup_styles(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Treeview", 
                        background=COLORS["bg_card"], 
                        foreground="white", 
                        fieldbackground=COLORS["bg_card"],
                        rowheight=35,
                        font=('Segoe UI', 10),
                        borderwidth=0)
        style.map("Treeview", background=[('selected', '#3d3d3d')])
        style.configure("Treeview.Heading", 
                        background="#212121", 
                        foreground="white", 
                        font=('Segoe UI', 10, 'bold'),
                        borderwidth=0)

    def _create_widgets(self):
        # 1. Sticky Header
        self.header = ctk.CTkFrame(self, height=80, fg_color=COLORS["bg_dark"], corner_radius=0)
        self.header.pack(fill=tk.X, side=tk.TOP, padx=0, pady=0)
        
        self.header_bg = ctk.CTkFrame(self.header, fg_color="#151515", height=78, corner_radius=0)
        self.header_bg.pack(fill=tk.X, padx=0, pady=(0, 2))
        
        title_frame = ctk.CTkFrame(self.header_bg, fg_color="transparent")
        title_frame.pack(side=tk.LEFT, padx=30)
        
        ctk.CTkLabel(title_frame, text="🧠", font=("Segoe UI Emoji", 32)).pack(side=tk.LEFT, padx=(0, 10))
        ctk.CTkLabel(title_frame, text="NEXT LEVEL BRAIN", font=("Segoe UI", 22, "bold"), text_color=COLORS["neon_green"]).pack(side=tk.LEFT)
        
        # Indicators & Icons
        self.right_header = ctk.CTkFrame(self.header_bg, fg_color="transparent")
        self.right_header.pack(side=tk.RIGHT, padx=30)
        
        # System Active Pulse
        self.pulse_canvas = tk.Canvas(self.right_header, width=30, height=30, bg="#151515", highlightthickness=0)
        self.pulse_canvas.pack(side=tk.LEFT, padx=5)
        self.pulse_circle = self.pulse_canvas.create_oval(7, 7, 23, 23, fill=COLORS["neon_green"], outline="")
        self._animate_pulse()
        
        self.status_label = ctk.CTkLabel(self.right_header, text="SYSTEM ACTIVE", font=("Segoe UI", 11, "bold"), text_color=COLORS["neon_green"])
        self.status_label.pack(side=tk.LEFT, padx=(0, 20))
        
        # Icons
        for icon in ["⚙️", "🔔", "📊", "💻"]:
            ctk.CTkLabel(self.right_header, text=icon, font=("Segoe UI Emoji", 18), cursor="hand2").pack(side=tk.LEFT, padx=10)
            
        # Clock
        self.clock_label = ctk.CTkLabel(self.right_header, text="00:00:00", font=("Consolas", 14, "bold"), text_color=COLORS["text_secondary"])
        self.clock_label.pack(side=tk.LEFT, padx=(20, 0))

        # Main Scrollable Content (Using Tabs)
        self.tab_view = ctk.CTkTabview(self, fg_color="transparent")
        self.tab_view.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        self.tab_performance = self.tab_view.add("📈 PERFORMANCE")
        self.tab_intelligence = self.tab_view.add("🧠 MARKET INTELLIGENCE")
        
        # --- TAB: PERFORMANCE ---
        self.main_container = ctk.CTkScrollableFrame(self.tab_performance, fg_color="transparent")
        self.main_container.pack(fill=tk.BOTH, expand=True)

        # 2. Stats Section (Cards)
        stats_frame = ctk.CTkFrame(self.main_container, fg_color="transparent")
        stats_frame.pack(fill=tk.X, pady=10)
        
        self.stat_cards = {}
        metrics_meta = [
            ("TOTAL TRADES", "total_trades", COLORS["text_primary"]),
            ("WIN RATE", "win_rate", COLORS["neon_green"]),
            ("TOTAL P&L", "total_pnl", COLORS["neon_green"]),
            ("PROFIT FACTOR", "profit_factor", COLORS["neon_blue"]),
            ("MAX DRAWDOWN", "max_drawdown", COLORS["neon_red"])
        ]
        
        for i, (label, key, color) in enumerate(metrics_meta):
            card = ScrollableStatCard(stats_frame, label, color)
            card.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)
            self.stat_cards[key] = card

        # 3. Portfolio Summary Cards
        summary_frame = ctk.CTkFrame(self.main_container, fg_color="transparent")
        summary_frame.pack(fill=tk.X, pady=10)
        
        self.summary_cards = {}
        summary_meta = [
            ("ACCOUNT BALANCE", "balance_val", COLORS["text_primary"]),
            ("FLOATING EQUITY", "equity_val", COLORS["neon_green"]),
            ("SESSION PNL", "session_val", COLORS["neon_green"]),
            ("FREE MARGIN", "margin_val", COLORS["neon_blue"]),
            ("SESSION TIME", "duration_val", COLORS["neon_yellow"])
        ]
        
        for i, (label, key, color) in enumerate(summary_meta):
            card = SummaryCard(summary_frame, label, color)
            card.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)
            self.summary_cards[key] = card

        # 4. Milestone Progress
        milestone_frame = ctk.CTkFrame(self.main_container, fg_color=COLORS["bg_card"], corner_radius=12, border_width=1, border_color=COLORS["border"])
        milestone_frame.pack(fill=tk.X, pady=10, padx=5)
        
        ctk.CTkLabel(milestone_frame, text="EQUITY MILESTONE PROGRESS", font=("Segoe UI", 11, "bold"), text_color=COLORS["text_secondary"]).pack(anchor=tk.W, padx=20, pady=(15, 5))
        
        prog_container = ctk.CTkFrame(milestone_frame, fg_color="transparent")
        prog_container.pack(fill=tk.X, padx=20, pady=(0, 20))
        
        self.milestone_progress = ctk.CTkProgressBar(prog_container, height=12, progress_color=COLORS["neon_green"], fg_color="#333333")
        self.milestone_progress.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 20))
        self.milestone_progress.set(0)
        
        self.milestone_text = ctk.CTkLabel(prog_container, text="0.00 / 100.00", font=("Consolas", 14, "bold"), text_color=COLORS["neon_green"])
        self.milestone_text.pack(side=tk.RIGHT)

        # 5. Middle Section: Table vs Small Chart
        middle_frame = ctk.CTkFrame(self.main_container, fg_color="transparent")
        middle_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        # Left: Positions Table
        table_container = ctk.CTkFrame(middle_frame, fg_color=COLORS["bg_card"], corner_radius=12, border_width=1, border_color=COLORS["border"])
        table_container.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)
        
        ctk.CTkLabel(table_container, text="💹 ACTIVE POSITIONS", font=("Segoe UI", 12, "bold")).pack(anchor=tk.W, padx=20, pady=15)
        
        self.pos_tree = ttk.Treeview(table_container, columns=("ticket", "symbol", "side", "lots", "price", "profit"), show="headings")
        self.pos_tree.heading("ticket", text="Ticket")
        self.pos_tree.heading("symbol", text="Symbol")
        self.pos_tree.heading("side", text="Side")
        self.pos_tree.heading("lots", text="Lots")
        self.pos_tree.heading("price", text="Entry")
        self.pos_tree.heading("profit", text="Profit")
        for col in ("ticket", "symbol", "side", "lots", "price", "profit"):
            self.pos_tree.column(col, anchor=tk.CENTER, width=80)
        self.pos_tree.pack(fill=tk.BOTH, expand=True, padx=15, pady=(0, 15))
        
        # Right: Mini Live Chart
        chart_container = ctk.CTkFrame(middle_frame, fg_color=COLORS["bg_card"], width=350, corner_radius=12, border_width=1, border_color=COLORS["border"])
        chart_container.pack(side=tk.RIGHT, fill=tk.BOTH, padx=5)
        chart_container.pack_propagate(False)
        
        ctk.CTkLabel(chart_container, text="📊 PERFORMANCE CURVE", font=("Segoe UI", 12, "bold")).pack(anchor=tk.W, padx=20, pady=15)
        
        self.fig, self.ax = plt.subplots(figsize=(4, 3), dpi=90)
        self.fig.patch.set_facecolor(COLORS["bg_card"])
        self.ax.set_facecolor(COLORS["bg_card"])
        self.ax.tick_params(colors='white', labelsize=8)
        for spine in self.ax.spines.values(): spine.set_edgecolor(COLORS["border"])
        
        self.canvas = FigureCanvasTkAgg(self.fig, master=chart_container)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        # --- TAB: MARKET INTELLIGENCE ---
        self._create_intelligence_widgets()

        # Bottom Actions
        footer = ctk.CTkFrame(self, height=60, fg_color=COLORS["bg_card"], corner_radius=0)
        footer.pack(fill=tk.X, side=tk.BOTTOM)
        
        ctk.CTkButton(footer, text="🔄 RESET PERFORMANCE", command=self._reset_dashboard, fg_color="#3B82F6", hover_color="#2563EB", font=("Segoe UI", 12, "bold")).pack(side=tk.RIGHT, padx=10, pady=15)
        ctk.CTkButton(footer, text="🧹 DELETE ALL PENDINGS", command=self._delete_pendings, fg_color="#EF4444", hover_color="#DC2626", font=("Segoe UI", 12, "bold")).pack(side=tk.RIGHT, padx=10, pady=15)
        ctk.CTkButton(footer, text="📊 GENERATE FULL REPORT", command=self._generate_report, fg_color=COLORS["neon_green"], text_color="black", hover_color="#00D96D", font=("Segoe UI", 12, "bold")).pack(side=tk.RIGHT, padx=10, pady=15)

    def _animate_pulse(self):
        if not self.running: return
        try:
            pulse_val = (np.sin(time.time() * 4) + 1) / 2
            size = 7 + (pulse_val * 6)
            self.pulse_canvas.coords(self.pulse_circle, 15-size/2, 15-size/2, 15+size/2, 15+size/2)
            self.after(50, self._animate_pulse)
        except: pass

    def _play_alert(self):
        """Play a loud 10-second beep alert for milestone hit"""
        def run_alert():
            if winsound:
                try:
                    # Looping beep for ~10 seconds (10 x 1000ms)
                    for _ in range(10):
                        if not self.running: break
                        winsound.Beep(1000, 800) # 1000Hz frequency, 800ms duration
                        time.sleep(0.2)
                except: pass
        threading.Thread(target=run_alert, daemon=True).start()

    def _on_closing(self):
        self.running = False
        if hasattr(self, 'liq_engine'):
            self.liq_engine.stop()
        self._save_session_stats()
        self.destroy()

    def _update_loop(self):
        terminal_path = os.getenv("MT5_TERMINAL_PATH", r"C:\Program Files\MetaTrader 5 EXNESS\terminal64.exe")
        if not mt5.initialize(path=terminal_path):
            self.after(0, lambda: messagebox.showerror("Error", f"MT5 not running at {terminal_path}!"))
            self.running = False
            return

        while self.running:
            try:
                acc = mt5.account_info()
                current_session = (time.time() - self.start_time) if self.start_time else 0
                if self.start_time and int(current_session) % 30 == 0:
                    self._save_session_stats()

                positions = mt5.positions_get()
                
                # Start session timer only if positions are detected
                if positions and self.start_time is None:
                    self.start_time = time.time()
                    self._last_history_update = 0 # Ensure fresh start
                
                self._detect_system_context()

                now = time.time()
                deals = None
                if now - self._last_history_update >= 2:
                    from_date = datetime.now() - timedelta(days=self.history_days)
                    to_date = datetime.now() + timedelta(days=1)
                    deals = mt5.history_deals_get(from_date, to_date)
                    self._last_history_update = now

                def _apply_ui(acc=acc, positions=positions, deals_data=deals):
                    try:
                        if acc:
                            self.summary_cards['balance_val'].update_value(f"{self.unit}{acc.balance:,.2f}")
                            self.summary_cards['equity_val'].update_value(f"{self.unit}{acc.equity:,.2f}")
                            free_margin = f"{self.unit}{acc.margin_free:,.2f}"
                            self.summary_cards['margin_val'].update_value(free_margin)
                        self._update_positions_tree(positions)
                        if deals_data is not None:
                            self._update_full_history(deals_data)
                        self._update_chart()
                    except Exception as ui_err:
                        print(f"UI apply error: {ui_err}")

                self.after(0, _apply_ui)
                self.after(0, self._update_intelligence_tabs)
                time.sleep(1)
            except Exception as e:
                print(f"UI Update error: {e}")
                time.sleep(5)

    def _update_intelligence_tabs(self):
        """Update metrics and chart for the unified terminal"""
        if not self.tab_view.get() == "🧠 MARKET INTELLIGENCE":
            return
            
        tf = self.active_tf
        data = self.liq_engine.liquidity_data.get(tf)
        
        if data:
            # Simple prediction for this specific TF
            curr = data['current_price']
            nearest_bsl = min([h['price'] for h in data['bsl']], key=lambda x: abs(x-curr)) if data['bsl'] else None
            nearest_ssl = min([l['price'] for l in data['ssl']], key=lambda x: abs(x-curr)) if data['ssl'] else None
            
            # Distance and Direction
            dist_up = (nearest_bsl - curr) if nearest_bsl else 0
            dist_down = (curr - nearest_ssl) if nearest_ssl else 0
            
            direction = "NEUTRAL"
            pot = 0
            if dist_up > 0 and (dist_up < dist_down or dist_down == 0):
                direction = "BULLISH"
                pot = dist_up * 10 if "XAU" in self.active_symbol else dist_up * 10000
            elif dist_down > 0:
                direction = "BEARISH"
                pot = dist_down * 10 if "XAU" in self.active_symbol else dist_down * 10000
            
            # Absolute Price Change Calculation ($)
            # For XAUUSD: 10 Pips = $1.00 change in price
            # For Forex: 10,000 Pips = $1.00 change in price
            price_change = (pot / 10) if "XAU" in self.active_symbol else (pot / 10000)
            
            dir_color = COLORS["neon_green"] if direction == "BULLISH" else COLORS["neon_red"] if direction == "BEARISH" else COLORS["text_secondary"]
            
            self.intel_ui['dir_card'].update_value(direction, dir_color)
            self.intel_ui['pot_label'].configure(text=f"{pot:.1f} Pips (Δ ${price_change:,.2f} Price)")
            
            intensity = max(0, min(1, 1 - (pot / 100))) if (nearest_bsl or nearest_ssl) else 0
            self.intel_ui['magnet_bar'].set(intensity)
            self.intel_ui['magnet_bar'].configure(progress_color=dir_color if (nearest_bsl or nearest_ssl) else COLORS["text_secondary"])
            
            self.intel_ui['bsl_card'].update_value(f"{nearest_bsl:.2f}" if nearest_bsl else "--")
            self.intel_ui['ssl_card'].update_value(f"{nearest_ssl:.2f}" if nearest_ssl else "--")
            
            # Liquidity Detailed Commentary
            comment_text = ""
            bsl_val = f"{nearest_bsl:.2f}" if nearest_bsl else "N/A"
            ssl_val = f"{nearest_ssl:.2f}" if nearest_ssl else "N/A"
            
            if direction == "BULLISH":
                comment_text += f"🟢 BULLISH BIAS (TARGETING BSL - {bsl_val}):\nMarket is moving towards Buy Side Liquidity (BSL). Sellers' Stop Losses (Buy Orders) are trapped here. Sweeping BSL triggers upward spikes, then often creates a reversal or continuation.\n\n"
            elif direction == "BEARISH":
                comment_text += f"🔴 BEARISH BIAS (TARGETING SSL - {ssl_val}):\nMarket is attacking Sell Side Liquidity (SSL). Buyers' Stop Losses (Sell Orders) rest here. Sweeping SSL triggers downward cascades, which act as a trap before a potential bounce or drop.\n\n"
            else:
                comment_text += f"⚪ NEUTRAL BIAS:\nMarket is hovering between BSL ({bsl_val}) & SSL ({ssl_val}) zones. Awaiting structure shift.\n\n"
            
            comment_text += "🧲 FVG ATTRACTION:\nFair Value Gaps (FVG) act as price magnets to rebalance unfilled orders."
            self.intel_ui['commentary_label'].configure(text=comment_text)
            
            # Throttle chart redraw to every 3 seconds to prevent UI hangs
            now = time.time()
            if not hasattr(self, '_last_intel_chart_redraw') or now - self._last_intel_chart_redraw >= 3:
                # Redraw chart for this specific TF
                self._draw_unified_tv_chart(tf)
                self._last_intel_chart_redraw = now

    def _create_intelligence_widgets(self):
        self.active_tf = "M15"
        self.intel_ui = {}
        
        container = ctk.CTkFrame(self.tab_intelligence, fg_color="transparent")
        container.pack(fill=tk.BOTH, expand=True)

        # 1. Header with TF Switcher
        header_frame = ctk.CTkFrame(container, fg_color="transparent")
        header_frame.pack(fill=tk.X, pady=(10, 5))
        
        ctk.CTkLabel(header_frame, text="⚡ TRADING TERMINAL", font=("Segoe UI", 20, "bold"), text_color=COLORS["neon_yellow"]).pack(side=tk.LEFT, padx=10)
        
        tf_switcher = ctk.CTkSegmentedButton(header_frame, values=["M1", "M3", "M5", "M10", "M15", "M30"],
                                             command=self._on_tf_change,
                                             selected_color=COLORS["neon_blue"],
                                             selected_hover_color=COLORS["neon_green"],
                                             unselected_color=COLORS["bg_card"],
                                             font=("Segoe UI", 11, "bold"))
        tf_switcher.set(self.active_tf)
        tf_switcher.pack(side=tk.RIGHT, padx=10)
        
        # 2. Main Terminal Layout (Sidebar + Chart)
        main_layout = ctk.CTkFrame(container, fg_color="transparent")
        main_layout.pack(fill=tk.BOTH, expand=True)
        
        # Left Dashboard (Metrics)
        dashboard = ctk.CTkFrame(main_layout, fg_color=COLORS["bg_card"], width=280, corner_radius=15, border_width=1, border_color=COLORS["border"])
        dashboard.pack(side=tk.LEFT, fill=tk.Y, padx=5, pady=5)
        dashboard.pack_propagate(False)
        
        ctk.CTkLabel(dashboard, text="INSTITUTIONAL METRICS", font=("Segoe UI", 11, "bold"), text_color=COLORS["neon_yellow"]).pack(pady=15)
        
        dir_card = SummaryCard(dashboard, "INSTITUTIONAL BIAS (SENTIMENT)", COLORS["neon_green"])
        dir_card.pack(fill=tk.X, padx=15, pady=5)
        
        mag_frame = ctk.CTkFrame(dashboard, fg_color="transparent")
        mag_frame.pack(fill=tk.X, padx=15, pady=10)
        ctk.CTkLabel(mag_frame, text="PROBABILITY OF MOVE (MAGNET)", font=("Segoe UI", 9, "bold"), text_color=COLORS["text_secondary"]).pack(anchor=tk.W)
        bar = ctk.CTkProgressBar(mag_frame, height=8)
        bar.pack(fill=tk.X, pady=5)
        pot_label = ctk.CTkLabel(mag_frame, text="0.0 Pips", font=("Consolas", 14, "bold"))
        pot_label.pack(anchor=tk.E)
        
        bsl_card = ScrollableStatCard(dashboard, "TARGET: BUY SIDE (BSL)", COLORS["bsl_color"])
        bsl_card.pack(fill=tk.X, padx=15, pady=5)
        
        ssl_card = ScrollableStatCard(dashboard, "TARGET: SELL SIDE (SSL)", COLORS["ssl_color"])
        ssl_card.pack(fill=tk.X, padx=15, pady=5)
        
        # Detailed Commentary Label
        commentary_frame = ctk.CTkFrame(dashboard, fg_color="transparent")
        commentary_frame.pack(fill=tk.BOTH, padx=15, pady=10, expand=True)
        commentary_label = ctk.CTkLabel(commentary_frame, text="ANALYZING LIQUIDITY...", 
                                             font=("Segoe UI", 13, "bold"), text_color="#E0E0E0", 
                                             justify="left", wraplength=230)
        commentary_label.pack(anchor=tk.NW, fill=tk.BOTH)
        
        # Right Terminal (Central Chart)
        chart_area = ctk.CTkFrame(main_layout, fg_color=COLORS["bg_card"], corner_radius=15, border_width=1, border_color=COLORS["border"])
        chart_area.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        fig, (ax_main, ax_vol) = plt.subplots(2, 1, figsize=(10, 8), dpi=100, gridspec_kw={'height_ratios': [4, 1], 'hspace': 0.05})
        fig.patch.set_facecolor(COLORS["bg_card"])
        
        for ax in [ax_main, ax_vol]:
            ax.set_facecolor(COLORS["bg_card"])
            ax.tick_params(colors=COLORS["text_secondary"], labelsize=8)
            for spine in ax.spines.values(): spine.set_visible(False)
            ax.grid(True, linestyle='--', alpha=0.05)
            
        canvas = FigureCanvasTkAgg(fig, master=chart_area)
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        self.intel_ui = {
            'dir_card': dir_card, 'magnet_bar': bar, 'pot_label': pot_label,
            'bsl_card': bsl_card, 'ssl_card': ssl_card, 'commentary_label': commentary_label,
            'fig': fig, 'ax': ax_main, 'ax_vol': ax_vol, 'canvas': canvas
        }

    def _on_tf_change(self, value):
        self.active_tf = value
        self._update_intelligence_tabs()

    def _draw_unified_tv_chart(self, tf):
        ui = self.intel_ui
        data = self.liq_engine.liquidity_data.get(tf)
        
        if not data or 'ohlc' not in data or not data['ohlc']: 
            ui['ax'].set_title(f"WAITING FOR {tf} DATA...", color=COLORS["neon_yellow"])
            ui['canvas'].draw()
            return
            
        ax = ui['ax']
        ax_vol = ui['ax_vol']
        ax.clear()
        ax_vol.clear()
        
        ohlc = data['ohlc']
        prices = pd.DataFrame(ohlc)
        
        # 1. Rendering Candlesticks (TV Styling)
        for i, row in prices.iterrows():
            color = "#089981" if row['close'] >= row['open'] else "#F23645"
            ax.vlines(i, row['low'], row['high'], color=color, linewidth=1, alpha=0.8)
            body_width = 0.6
            rect = plt.Rectangle((i - body_width/2, min(row['open'], row['close'])), 
                                  body_width, abs(row['open'] - row['close']),
                                  facecolor=color, edgecolor=color, alpha=0.9, linewidth=1)
            ax.add_patch(rect)
            ax_vol.bar(i, row['tick_volume'], color=color, alpha=0.3, width=0.8)

        # 2. Plot Institutional Liquidity Overlays (BSL/SSL)
        curr = data['current_price']
        # Dynamic glow offset based on price
        glow_size = curr * 0.0001
        
        for b in data['bsl']:
            is_grabbed = b.get('grabbed', False)
            color = "#555555" if is_grabbed else COLORS["bsl_color"]
            alpha = 0.15 if is_grabbed else 0.3
            linewidth = 0.8 if is_grabbed else 1.2
            
            ax.axhline(b['price'], color=color, linestyle='-', alpha=alpha, linewidth=linewidth)
            if not is_grabbed:
                for offset in [glow_size, glow_size*2]:
                    ax.axhline(b['price']+offset, color=color, alpha=0.05, linewidth=2.5)
            ax.text(len(prices)-1, b['price'], " BSL (G)" if is_grabbed else " BSL", color=color, fontweight='bold', fontsize=7, va='center')

        for s in data['ssl']:
            is_grabbed = s.get('grabbed', False)
            color = "#555555" if is_grabbed else COLORS["ssl_color"]
            alpha = 0.15 if is_grabbed else 0.3
            linewidth = 0.8 if is_grabbed else 1.2
            
            ax.axhline(s['price'], color=color, linestyle='-', alpha=alpha, linewidth=linewidth)
            if not is_grabbed:
                for offset in [glow_size, glow_size*2]:
                    ax.axhline(s['price']-offset, color=color, alpha=0.05, linewidth=2.5)
            ax.text(len(prices)-1, s['price'], " SSL (G)" if is_grabbed else " SSL", color=color, fontweight='bold', fontsize=7, va='center')

        # Plot FVGs (Mitigated first, Active last to prevent overlapping issues)
        fvg_data = data.get('fvg', [])
        fvg_data_sorted = sorted(fvg_data, key=lambda x: x.get('mitigated', False), reverse=True)
        
        if not prices.empty:
            min_time = prices['time'].min()
            for fvg in fvg_data_sorted:
                if fvg['time'] >= min_time:
                    matches = prices.index[prices['time'] == fvg['time']].tolist()
                    x_start = matches[0] if matches else 0
                else:
                    x_start = 0  # Render from left edge if FVG started before visible window
                    
                is_mitigated = fvg.get('mitigated', False)
                if is_mitigated and 'mitigated_time' in fvg:
                    if fvg['mitigated_time'] >= min_time:
                        end_matches = prices.index[prices['time'] == fvg['mitigated_time']].tolist()
                        x_end = end_matches[0] if end_matches else len(prices) - 1
                    else:
                        x_end = 0  # Mitigated before visible window
                else:
                    x_end = len(prices) - 1
                    
                if x_end > x_start:
                    if is_mitigated:
                        # Faded grey/neutral color for mitigated FVGs
                        color = "#777777" 
                        alpha_fvg = 0.15
                        text_alpha = 0.4
                        border_color = "#555555"
                        label = " FVG (M)"
                    else:
                        color = "#00FF00" if fvg['type'] == 'bullish' else "#FF0000"
                        alpha_fvg = 0.35
                        text_alpha = 0.8
                        border_color = color
                        label = " FVG"
                        
                    width = max(1, x_end - x_start) # Ensure at least 1 width
                    rect = plt.Rectangle((x_start, fvg['bottom']), 
                                         width, fvg['top'] - fvg['bottom'],
                                         facecolor=color, alpha=alpha_fvg, edgecolor=border_color, linewidth=1.5)
                    ax.add_patch(rect)
                    ax.text(x_start, (fvg['top'] + fvg['bottom'])/2, label, color=color, alpha=text_alpha, fontsize=8, fontweight='bold', va='center', ha='left')

        # Current Price Line
        ax.axhline(curr, color='white', linestyle='--', linewidth=0.8, alpha=0.8)
        
        # Scaling (Zoom into recent price action but keep liquidity visible if close)
        p_min, p_max = prices['low'].min(), prices['high'].max()
        p_range = p_max - p_min
        ax.set_ylim(p_min - p_range*0.2, p_max + p_range*0.2)
        
        ax_vol.relim()
        ax_vol.autoscale_view()
        
        ax.set_facecolor(COLORS["bg_card"])
        ax_vol.set_facecolor(COLORS["bg_card"])
        ax.grid(True, linestyle='--', color='white', alpha=0.05)
        ax_vol.grid(True, linestyle='--', color='white', alpha=0.05)
        ax.get_xaxis().set_visible(False)
        ax_vol.get_xaxis().set_visible(False)
        
        ax.set_title(f"PRO TRADING TERMINAL - {self.active_symbol} ({tf})", color=COLORS["neon_yellow"], fontname='Segoe UI', fontsize=12, pad=15)
        
        ui['fig'].tight_layout()
        ui['canvas'].draw()

       

    def _update_positions_tree(self, positions):
        # Clear
        for i in self.pos_tree.get_children():
            self.pos_tree.delete(i)
        if not positions: return
        
        for p in positions:
            side = "BUY" if p.type == mt5.POSITION_TYPE_BUY else "SELL"
            tag = "profit" if p.profit >= 0 else "loss"
            self.pos_tree.insert("", tk.END, values=(
                p.ticket, p.symbol, side, p.volume, f"{p.price_open:.5f}", f"{p.profit:.2f}"
            ), tags=(tag,))
        
        self.pos_tree.tag_configure("profit", foreground=COLORS["neon_green"])
        self.pos_tree.tag_configure("loss", foreground=COLORS["neon_red"])

    def _update_chart(self):
        if not hasattr(self, 'trade_history') or not self.trade_history: return
        profits = [h['profit'] for h in self.trade_history]
        if not profits: return
        cum_pnl = np.cumsum(profits)
        
        self.ax.clear()
        self.ax.plot(cum_pnl, color=COLORS["neon_green"], linewidth=2)
        self.ax.fill_between(range(len(cum_pnl)), cum_pnl, color=COLORS["neon_green"], alpha=0.1)
        self.ax.set_title("SESSION EQUITY CURVE", color='white', fontsize=10, fontname='Segoe UI')
        self.ax.grid(True, linestyle='--', alpha=0.1)
        self.canvas.draw()

    def _tick_timer(self):
        if not self.running: return
        try:
            now = datetime.now()
            self.clock_label.configure(text=now.strftime("%H:%M:%S"))
            
            if self.start_time is not None:
                total_seconds = int(self.accumulated_seconds + (time.time() - self.start_time))
            else:
                total_seconds = int(self.accumulated_seconds)
                
            d, r = divmod(total_seconds, 86400)
            h, r = divmod(r, 3600)
            m, s = divmod(r, 60)
            uptime_str = f"{d}d {h:02d}:{m:02d}:{s:02d}" if d > 0 else f"{h:02d}:{m:02d}:{s:02d}"
            self.summary_cards['duration_val'].update_value(uptime_str)

            # Milestone
            try:
                milestone_file = Path("logs/milestone_progress.json")
                if milestone_file.exists():
                    with open(milestone_file, 'r') as f:
                        data = json.load(f)
                        prog = data.get('progress', 0.0)
                        target = data.get('target_inc', 100.0)
                        val = max(0, min(1, prog / target))
                        self.milestone_progress.set(val)
                        color = COLORS["neon_green"] if prog >= 0 else COLORS["neon_red"]
                        self.milestone_text.configure(text=f"{self.unit}{prog:,.2f} / {self.unit}{target:.0f}", text_color=color)
                        self.milestone_progress.configure(progress_color=color)
                        
                        # --- Layer 3 Hit Counter & Alert ---
                        hits = data.get('hits', 0)
                        if self.last_hits == -1:
                            self.last_hits = hits
                        
                        if hits > self.last_hits:
                            self.last_hits = hits
                            self._play_alert()
                            print(f"🎉 MILESTONE HIT #{hits}!")
                            
                        # Display hits on the card
                        if hasattr(self, 'milestone_hits_label'):
                            self.milestone_hits_label.configure(text=f"Total Hits: {hits}")
                        else:
                            # Create label dynamically if not exists
                            self.milestone_hits_label = ctk.CTkLabel(self.main_container, text=f"Total Hits: {hits}", font=("Segoe UI", 11, "bold"), text_color=COLORS["neon_yellow"])
                            self.milestone_hits_label.place(in_=self.milestone_progress, relx=1.0, rely=-2.5, anchor=tk.E)
            except Exception: pass
        except Exception: pass
        self.after(1000, self._tick_timer)

    def _detect_system_context(self):
        try:
            milestone_file = Path("logs/milestone_progress.json")
            if milestone_file.exists():
                with open(milestone_file, 'r') as f:
                    data = json.load(f)
                    self.unit = data.get('unit', "$")
            acc = mt5.account_info()
            if acc:
                if "Real" in acc.server and "Exness" in acc.server: self.unit = "USC"
                elif acc.currency == "USC": self.unit = "USC"
            positions = mt5.positions_get()
            if positions: self.active_symbol = positions[0].symbol
            else: self.active_symbol = "XAUUSDc" if self.unit == "USC" else "XAUUSDm"
            
            # Sync Engine Symbol
            if hasattr(self, 'liq_engine') and self.liq_engine.symbol != self.active_symbol:
                self.liq_engine.symbol = self.active_symbol
                
            self.pos_tree.heading("profit", text=f"Profit ({self.unit})")
        except Exception as e: print(f"Context error: {e}")

    def _update_full_history(self, deals):
        if deals:
            reset_file = Path("logs/dashboard_reset.json")
            reset_ts = 0
            if reset_file.exists():
                try:
                    with open(reset_file, 'r') as f: reset_ts = json.load(f).get('reset_timestamp', 0)
                except: pass
            closed_deals = [d for d in deals if d.entry == 1 and d.time > reset_ts]
            
            self.trade_history = [{
                'time': datetime.fromtimestamp(d.time).strftime('%Y-%m-%d %H:%M'),
                'symbol': d.symbol,
                'side': 'BUY' if d.type == mt5.DEAL_TYPE_BUY else 'SELL',
                'profit': d.profit + d.commission + d.swap
            } for d in closed_deals]

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
                peak = np.maximum.accumulate(cum_pnl)
                dd = peak - cum_pnl
                max_dd = np.max(dd) if len(dd) > 0 else 0
                
                acc = mt5.account_info()
                balance = acc.balance if acc else 1.0
                max_dd_pct = (max_dd / balance) * 100 if balance > 0 else 0
                
                self.metrics = {'total_trades': len(profits), 'win_rate': win_rate, 'total_pnl': total_pnl, 'profit_factor': profit_factor, 'max_drawdown': max_dd, 'max_drawdown_pct': max_dd_pct}
                
                self.stat_cards['total_trades'].update_value(str(len(profits)))
                self.stat_cards['win_rate'].update_value(f"{win_rate:.1%}")
                pnl_color = COLORS["neon_green"] if total_pnl >= 0 else COLORS["neon_red"]
                self.stat_cards['total_pnl'].update_value(f"{self.unit}{total_pnl:,.2f}", pnl_color)
                self.stat_cards['profit_factor'].update_value(f"{profit_factor:.2f}")
                self.stat_cards['max_drawdown'].update_value(f"{max_dd_pct:.2f}%")
                
                now = datetime.now()
                session_pnl = sum(h['profit'] for h in self.trade_history if (now - datetime.strptime(h['time'], '%Y-%m-%d %H:%M')).total_seconds() < 86400)
                session_color = COLORS["neon_green"] if session_pnl >= 0 else COLORS["neon_red"]
                self.summary_cards['session_val'].update_value(f"{self.unit}{session_pnl:,.2f}", session_color)

    def _reset_dashboard(self):
        if not messagebox.askyesno("Confirm", "Reset performance data?"): return
        try:
            signal_file = Path("logs/global_reset.signal")
            with open(signal_file, 'w') as f: f.write(str(datetime.now().timestamp()))
            for f in ["logs/grid_state.json", "logs/recycler_state.json", "logs/smart_trailing_state.json", "logs/milestone_progress.json"]:
                if Path(f).exists(): Path(f).unlink()
        except: pass
        reset_point = datetime.now().timestamp()
        with open(Path("logs/dashboard_reset.json"), 'w') as f: json.dump({'reset_timestamp': reset_point}, f)
        self.trade_history = []
        self.accumulated_seconds = 0
        self.start_time = time.time()
        self._save_session_stats()
        messagebox.showinfo("Done", "Performance reset.")

    def _delete_pendings(self):
        if not messagebox.askyesno("Confirm", "Close all positions/orders?"): return
        positions = mt5.positions_get()
        if positions:
            for p in positions:
                mt5.Close(p.symbol, ticket=p.ticket)
        orders = mt5.orders_get()
        if orders:
            for o in orders:
                mt5.order_send({"action": mt5.TRADE_ACTION_REMOVE, "order": o.ticket})
        messagebox.showinfo("Done", "Cleanup complete.")

    def _generate_report(self):
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        report_data = {'timestamp': datetime.now().isoformat(), 'metrics': self.metrics, 'trades': self.trade_history}
        report_path = Path(f"logs/live_reports/dashboard_report_{timestamp}.json")
        report_path.parent.mkdir(parents=True, exist_ok=True)
        with open(report_path, 'w') as f: json.dump(report_data, f, indent=4)
        messagebox.showinfo("Saved", f"Report saved: {report_path}")

    def run(self):
        self.mainloop()

# --- Custom Widget Components ---

class ScrollableStatCard(ctk.CTkFrame):
    def __init__(self, master, label, color):
        super().__init__(master, fg_color=COLORS["bg_card"], corner_radius=12, border_width=1, border_color=COLORS["border"])
        self.label = ctk.CTkLabel(self, text=label, font=("Segoe UI", 9, "bold"), text_color=COLORS["text_secondary"])
        self.label.pack(pady=(15, 0))
        self.value_label = ctk.CTkLabel(self, text="--", font=("Consolas", 18, "bold"), text_color=color)
        self.value_label.pack(pady=(0, 15))

    def update_value(self, val, color=None):
        self.value_label.configure(text=val)
        if color: self.value_label.configure(text_color=color)

class SummaryCard(ctk.CTkFrame):
    def __init__(self, master, label, color):
        super().__init__(master, fg_color=COLORS["bg_card"], corner_radius=12, border_width=1, border_color=COLORS["border"])
        self.label = ctk.CTkLabel(self, text=label, font=("Segoe UI", 9, "bold"), text_color=COLORS["text_secondary"])
        self.label.pack(anchor=tk.W, padx=20, pady=(15, 0))
        self.value_label = ctk.CTkLabel(self, text="0.00", font=("Consolas", 22, "bold"), text_color=color)
        self.value_label.pack(anchor=tk.W, padx=20, pady=(0, 15))

    def update_value(self, val, color=None):
        self.value_label.configure(text=val)
        if color: self.value_label.configure(text_color=color)

if __name__ == "__main__":
    app = LivePortfolioDashboard()
    app.run()
