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
from dotenv import load_dotenv
# Charting removed to replace with Calculator

# Load environment variables
load_dotenv()

class LivePortfolioDashboard:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("NEXT LEVEL - LIVE PERFORMANCE & CONTROL")
        self.root.geometry("1200x850")
        self.root.configure(bg='#0a0a0a') # Deeper Dark Background
        
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
        
        self._create_widgets()
        
        # Start background update thread
        self.update_thread = threading.Thread(target=self._update_loop, daemon=True)
        self.update_thread.start()
        
        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)

    def _setup_styles(self):
        self.style.configure("TFrame", background="#0a0a0a")
        self.style.configure("Card.TFrame", background="#151515", relief="flat", borderwidth=0)
        self.style.configure("TLabel", background="#151515", foreground="#ffffff", font=('Segoe UI', 10))
        self.style.configure("Header.TLabel", background="#0a0a0a", foreground="#00e676", font=('Segoe UI', 16, 'bold'))
        self.style.configure("Stat.TLabel", background="#151515", foreground="#00e676", font=('Consolas', 22, 'bold')) # Bigger, Neon Green
        self.style.configure("Metric.TLabel", background="#151515", foreground="#8b949e", font=('Segoe UI', 10))
        self.style.configure("Ticker.TLabel", background="#050505", foreground="#00e676", font=('Consolas', 11, 'italic'))
        
        # Treeview styles
        self.style.configure("Treeview", 
                           background="#151515", 
                           foreground="white", 
                           fieldbackground="#151515",
                           rowheight=28,
                           font=('Segoe UI', 10))
        self.style.map("Treeview", background=[('selected', '#3d3d3d')])
        self.style.configure("Treeview.Heading", background="#212121", foreground="white", font=('Segoe UI', 10, 'bold'))
        
        # Treeview tags for coloring
        self.pos_tree_tags = {
            'profit': {'foreground': '#00e676'},
            'loss': {'foreground': '#ff5252'}
        }

    def _create_widgets(self):
        # Main Container
        main_frame = ttk.Frame(self.root, padding="15")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # 1. Header
        header_frame = ttk.Frame(main_frame, style="TFrame")
        header_frame.pack(fill=tk.X, pady=(0, 15))
        
        title = tk.Label(header_frame, text="NEXT LEVEL - LIVE PERFORMANCE", 
                        bg="#0a0a0a", fg="#00e676", font=('Segoe UI', 22, 'bold'))
        title.pack(side=tk.LEFT)
        
        self.status_label = tk.Label(header_frame, text="● SYSTEM ACTIVE", bg="#0a0a0a", 
                                   fg="#00e676", font=('Segoe UI', 10, 'bold'))
        self.status_label.pack(side=tk.RIGHT)

        # 2. Performance Summary Metrics (Restored)
        perf_container = ttk.Frame(main_frame, style="Card.TFrame", padding="15")
        perf_container.pack(fill=tk.X, pady=10)
        
        metrics_list = [
            ("Total Trades", "total_trades"),
            ("Win Rate", "win_rate"),
            ("Total P&L", "total_pnl"),
            ("Profit Factor", "profit_factor"),
            ("Max Drawdown", "max_drawdown")
        ]
        
        self.metric_labels = {}
        for i, (label, key) in enumerate(metrics_list):
            m_frame = ttk.Frame(perf_container, style="Card.TFrame")
            m_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            
            ttk.Label(m_frame, text=f"{label}:", font=('Segoe UI', 10, 'bold')).pack(side=tk.LEFT, padx=5)
            self.metric_labels[key] = ttk.Label(m_frame, text="--", style="Stat.TLabel")
            self.metric_labels[key].pack(side=tk.LEFT, padx=5)

        # 3. Portfolio Summary Cards (Real-time)
        summary_container = ttk.Frame(main_frame, style="TFrame")
        summary_container.pack(fill=tk.X, pady=10)
        
        self.cards = {}
        items = [
            ("STARTING BALANCE", "start_val", "#ffffff"),
            ("ACCOUNT BALANCE", "balance_val", "#ffffff"),
            ("FLOATING EQUITY", "equity_val", "#58a6ff"),
            ("SESSION PNL", "session_val", "#00e676"),
            ("MAX FLOATING (-) $", "drawdown_val", "#ff5252"),
            ("MARGIN LEVEL", "margin_val", "#03a9f4")
        ]
        
        for i, (label, key, color) in enumerate(items):
            card = ttk.Frame(summary_container, style="Card.TFrame", padding="15")
            card.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=3)
            
            ttk.Label(card, text=label, font=('Segoe UI', 9, 'bold'), foreground="#8b949e").pack(anchor=tk.CENTER)
            self.cards[key] = tk.Label(card, text="$0.00", bg="#151515", 
                                      fg=color, font=('Consolas', 18, 'bold')) # Balanced size for 6 cards
            self.cards[key].pack(anchor=tk.CENTER, pady=5)
            
        # 3.5 Grid & Trailing Status Card (NEW)
        grid_container = ttk.Frame(main_frame, style="Card.TFrame", padding="15")
        grid_container.pack(fill=tk.X, pady=10)
        
        ttk.Label(grid_container, text="🕸️ GRID & TRAILING MONITOR", font=('Segoe UI', 10, 'bold'), foreground="#00e676").pack(anchor=tk.W, pady=(0,10))
        
        status_sub_frame = ttk.Frame(grid_container, style="Card.TFrame")
        status_sub_frame.pack(fill=tk.X)
        
        self.grid_cards = {}
        grid_items = [
            ("GRID MODE", "grid_mode", "#ffffff"),
            ("PROGRESS", "grid_progress", "#ffffff"),
            ("PEAK PROFIT", "peak_val", "#00e676"),
            ("TRAILING LOCK", "lock_val", "#ff5252")
        ]
        
        for label, key, color in grid_items:
            f = ttk.Frame(status_sub_frame, style="Card.TFrame")
            f.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            ttk.Label(f, text=label, font=('Segoe UI', 8, 'bold'), foreground="#888888").pack(anchor=tk.CENTER)
            self.grid_cards[key] = tk.Label(f, text="--", bg="#151515", fg=color, font=('Consolas', 14, 'bold'))
            self.grid_cards[key].pack(anchor=tk.CENTER)

        # 4. Content Area: Three Columns (Active Trades | Performance Curve | Live Risk Monitor)
        self.content_frame = ttk.Frame(main_frame, style="TFrame")
        self.content_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        # Left Column: Active Positions (32%)
        self.left_col = ttk.Frame(self.content_frame, style="Card.TFrame", padding=10)
        self.left_col.place(relx=0, rely=0, relwidth=0.32, relheight=1)
        
        ttk.Label(self.left_col, text="💹 ACTIVE POSITIONS", font=('Segoe UI', 10, 'bold'), foreground="#00e676").pack(anchor=tk.W, pady=(0,5))
        
        self.pos_tree = ttk.Treeview(self.left_col, columns=("symbol", "side", "lots", "profit"), show="headings")
        self.pos_tree.heading("symbol", text="Symbol")
        self.pos_tree.heading("side", text="Side")
        self.pos_tree.heading("lots", text="Lots")
        self.pos_tree.heading("profit", text="Profit ($)")
        for col in ("symbol", "side", "lots", "profit"):
            self.pos_tree.column(col, anchor=tk.CENTER, width=65)
        self.pos_tree.pack(fill=tk.BOTH, expand=True)
        
        # Middle Column: Equity Performance Curve (34%)
        self.mid_col = ttk.Frame(self.content_frame, style="Card.TFrame", padding=10)
        self.mid_col.place(relx=0.33, rely=0, relwidth=0.34, relheight=1)
        
        ttk.Label(self.mid_col, text="📈 PERFORMANCE CURVE (EQUITY)", font=('Segoe UI', 10, 'bold'), foreground="#00e676").pack(anchor=tk.W, pady=(0,5))
        self.chart_canvas = tk.Canvas(self.mid_col, bg="#0d1117", highlightthickness=0)
        self.chart_canvas.pack(fill=tk.BOTH, expand=True)
        
        # Right Column: Live Risk Monitor (32%)
        self.right_col = ttk.Frame(self.content_frame, style="Card.TFrame", padding=15)
        self.right_col.place(relx=0.68, rely=0, relwidth=0.32, relheight=1)
        
        ttk.Label(self.right_col, text="🛡️ LIVE RISK & EXPOSURE MONITOR", font=('Segoe UI', 11, 'bold'), foreground="#ffa726").pack(anchor=tk.W, pady=(0,15))
        
        calc_inner = ttk.Frame(self.right_col, style="Card.TFrame")
        calc_inner.pack(fill=tk.BOTH, expand=True)
        
        # Live Data Section
        stats_frame = ttk.Frame(calc_inner, style="Card.TFrame")
        stats_frame.pack(fill=tk.X, pady=5)
        
        self.live_price_label = tk.Label(stats_frame, text="LIVE PRICE: --", bg="#151515", fg="#ffffff", font=('Consolas', 11, 'bold'))
        self.live_price_label.pack(anchor=tk.W)
        
        self.net_lots_label = tk.Label(stats_frame, text="NET EXPOSURE: --", bg="#151515", fg="#ffffff", font=('Consolas', 11, 'bold'))
        self.net_lots_label.pack(anchor=tk.W)

        self.floating_pnl_label = tk.Label(stats_frame, text="CURRENT PNL: --", bg="#151515", fg="#00e676", font=('Consolas', 11, 'bold'))
        self.floating_pnl_label.pack(anchor=tk.W)
        
        ttk.Label(calc_inner, text="--- TOTAL PNL IF MARKET MOVES AGAINST YOU ---", font=('Segoe UI', 8, 'bold'), foreground="#888888").pack(pady=(15,10))
        
        self.proj_cards = {}
        # Scenarios: Price move in Dollars (e.g. Gold -1, -2 etc)
        # We'll label them as Pips but show the $ impact clearly
        scenarios = [
            ("$10 Move (1000 Pips)", 1000),
            ("$20 Move (2000 Pips)", 2000),
            ("$50 Move (5000 Pips)", 5000),
            ("$100 Move (10000 Pips)", 10000),
            ("$150 Move (15000 Pips)", 15000)
        ]
        
        for label, pips in scenarios:
            f = ttk.Frame(calc_inner, style="Card.TFrame")
            f.pack(fill=tk.X, pady=4)
            ttk.Label(f, text=label, font=('Segoe UI', 9), foreground="#cccccc").pack(side=tk.LEFT)
            self.proj_cards[pips] = tk.Label(f, text="$0.00", bg="#151515", fg="#ff5252", font=('Consolas', 12, 'bold'))
            self.proj_cards[pips].pack(side=tk.RIGHT)

        # Remove the previous horizontal risk_calc_frame if it exists to clean up
        # Note: Previous risk_calc_frame was at footer, we'll hide it to focus on this one
        
        # Configure tags for pos_tree
        self.pos_tree.tag_configure('profit', foreground='#00e676')
        self.pos_tree.tag_configure('loss', foreground='#ff5252')

        # 5. Bottom AI Ticker (Scrolling Thoughts)
        ticker_bg = tk.Frame(main_frame, bg="#050505", height=40)
        ticker_bg.pack(fill=tk.X, pady=(10, 0), side=tk.BOTTOM)
        
        # More dynamic ticker text
        # Ticker text with Education, Demo notice and Strategy Praise
        self.ticker_text = "[XAUUSD] NEXT LEVEL TRADING: GOLD SCALPING SPECIALIST... | [NOTICE] FOR EDUCATIONAL PURPOSES ONLY... | [ACCOUNT] DEMO ACCOUNT TRADING LIVE... | [STRATEGY] ELITE GRID-SCALPING IN ACTION: THE SMARTEST WAY TO PROFIT FROM MARKET PULLBACKS... | [STATUS] 100% OPERATIONAL... | [YT LIVE] STREAMING LIVE PERFORMANCE... | [MODE] FULL AUTO-TRAILING ACTIVE... "
        self.ticker_label = tk.Label(ticker_bg, text=self.ticker_text * 3, 
                                     bg="#050505", fg="#00e676", 
                                     font=('Consolas', 11, 'italic'),
                                     anchor='w')
        self.ticker_label.place(x=0, y=10)
        self._scroll_ticker()

        # Footer Actions (Smaller, to side)
        footer = ttk.Frame(main_frame, style="TFrame")
        footer.pack(fill=tk.X, pady=10, side=tk.BOTTOM)
        
        tk.Button(footer, text="🚨 EMERGENCY RESET", command=self._emergency_reset, bg="#ff1744", fg="white", font=('Segoe UI', 9, 'bold')).pack(side=tk.RIGHT, padx=5)
        tk.Button(footer, text="🧹 DELETE ALL PENDINGS", command=self._delete_pendings, bg="#ff5252", fg="white", font=('Segoe UI', 9, 'bold')).pack(side=tk.RIGHT, padx=5)
        tk.Button(footer, text="🧹 CLEAR HISTORY", command=self._clear_history, bg="#ff9100", fg="black", font=('Segoe UI', 9, 'bold')).pack(side=tk.RIGHT, padx=5)
        tk.Button(footer, text="📊 GENERATE FULL REPORT", command=self._generate_report, bg="#00e676", fg="black", font=('Segoe UI', 9, 'bold')).pack(side=tk.RIGHT, padx=5)

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
            
        # 1. Reset metrics
        acc = mt5.account_info()
        self.start_balance = acc.balance if acc else 0
        self.reset_timestamp = int(time.time())
        self._save_reset_config()
        
        # 2. Reset chart
        self.equity_history = [self.start_balance]
        self._save_chart_history()
        
        # 3. Clear local trade list
        self.trade_history = []
        
        messagebox.showinfo("History Cleared", "Dashboard metrics and chart history have been reset successfully.")

    def _scroll_ticker(self):
        """Infinite horizontal scroll for AI Ticker"""
        if not hasattr(self, '_ticker_pos'): self._ticker_pos = 0
        self._ticker_pos -= 1
        if self._ticker_pos < -1000: self._ticker_pos = 0
        self.ticker_label.place(x=self._ticker_pos, y=5)
        self.root.after(40, self._scroll_ticker)

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
    <title>NEXT LEVEL BRAIN - Performance Report</title>
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
        <div class="footer">Generated by NEXT LEVEL BRAIN AI Trading System | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</div>
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
    <title>NEXT LEVEL BRAIN - Global Trading Intelligence</title>
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
            <div class="subtitle">Next Level Brain - Unified Performance Intelligence</div>
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
            if config_file.exists():
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
            self.metric_labels[key].config(text="0.0" if "rate" not in key else "0.0%")
        self.cards['session_val'].config(text="$0.00", foreground="#00e676")
        
        # User requested: DO NOT reset max floating (-) in emergency reset
        # self.session_max_drawdown = 0.0 # Reset session max drawdown (REMOVED as requested)
        # self.cards['drawdown_val'].config(text="$0.00") # Update card (REMOVED as requested)
        
        self.equity_history = [] # Clear equity history for chart
        
        messagebox.showinfo("Reset Complete", f"Emergency Reset Successful:\n- Closed: {closed_count} positions\n- Deleted: {deleted_count} pending orders\n- Performance Metrics Resetted.")

    def _update_loop(self):
        terminal_path = r"C:\Program Files\MetaTrader 5 EXNESS\terminal64.exe"
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

        while self.running:
            try:
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
                    session_color = "#00e676" if session_pnl >= 0 else "#ff5252"
                    
                    self.cards['start_val'].config(text=f"${self.start_balance:,.2f}")
                    self.cards['balance_val'].config(text=f"${balance:,.2f}")
                    self.cards['equity_val'].config(text=f"${equity:,.2f}")
                    self.cards['session_val'].config(text=f"${session_pnl:,.2f}", fg=session_color)
                    
                    margin_pct = f"{acc.margin_level:.1f}%" if acc.margin_level else "0%"
                    self.cards['margin_val'].config(text=margin_pct)
                    
                    # Track Chart History (Persistent & Long-Term)
                    now = time.time()
                    if not self.equity_history:
                        self.equity_history.append(self.start_balance)
                    
                    # Append every 60 seconds OR if balance changed significantly
                    last_point = self.equity_history[-1]
                    if now - self._last_chart_append > 60 or abs(balance - last_point) > 0.01:
                        self.equity_history.append(balance)
                        if len(self.equity_history) > 200: self.equity_history.pop(0)
                        self._last_chart_append = now
                        self._save_chart_history()

                positions = mt5.positions_get()
                current_floating_pnl = sum(p.profit for p in positions) if positions else 0.0
                
                # Update Max Floating Minus Tracker
                if current_floating_pnl < self.session_max_drawdown:
                    self.session_max_drawdown = current_floating_pnl
                    self._save_reset_config() # Persist new drawdown peak
                
                self.cards['drawdown_val'].config(text=f"${self.session_max_drawdown:,.2f}")
                
                self._draw_chart()
                self._update_risk_calculator(positions)
                self._update_positions_tree(positions)
                self._update_full_history()
                self._update_grid_status()
                
                time.sleep(1) # Increased frequency to 1 second
            except Exception as e:
                print(f"UI Update error: {e}")
                time.sleep(5)

    def _draw_chart(self):
        try:
            self.chart_canvas.delete("all")
            w = self.chart_canvas.winfo_width()
            h = self.chart_canvas.winfo_height()
            if w < 10 or h < 10 or not self.equity_history:
                return

            points = self.equity_history
            if len(points) < 2:
                return

            min_val = min(points)
            max_val = max(points)
            
            # Smart Scale: Ensure some 'breathing room' so points aren't flat on edges
            val_range = max_val - min_val
            if val_range < 0.1: # If flat, give a small range
                val_range = 10.0
                min_val = max_val - 5.0
                max_val = max_val + 5.0
            else:
                padding = val_range * 0.1
                min_val -= padding
                max_val += padding
                val_range = max_val - min_val

            # Padding
            pad = 25
            
            # Draw Grid Lines
            for i in range(5):
                y = pad + (h - 2*pad) * i / 4
                self.chart_canvas.create_line(pad, y, w-pad, y, fill="#1e2229", dash=(2, 2))

            # Scaled points
            coords = []
            for i, val in enumerate(points):
                x = pad + (w - 2*pad) * i / (len(points) - 1 if len(points) > 1 else 1)
                y = h - pad - (h - 2*pad) * (val - min_val) / val_range
                coords.append((x, y))

            line_color = "#00e676" 
            
            # 1. Draw Area Fill (Polygon)
            if len(coords) > 1:
                poly_coords = [coords[0][0], h - pad] # Start at bottom left
                for x, y in coords:
                    poly_coords.extend([x, y])
                poly_coords.extend([coords[-1][0], h - pad]) # End at bottom right
                self.chart_canvas.create_polygon(poly_coords, fill="#00e676", stipple="gray25", outline="")
                # Note: gray25 is a built-in bitmap for transparency in Tkinter
            
            # 2. Draw Curve
            for i in range(len(coords) - 1):
                self.chart_canvas.create_line(coords[i][0], coords[i][1], 
                                            coords[i+1][0], coords[i+1][1], 
                                            fill=line_color, width=3, smooth=True)
            
            # 3. Draw Hollow Dots at intervals
            # If we have many points, only draw some dots to avoid clutter
            step = max(1, len(coords) // 10)
            for i in range(0, len(coords), step):
                cx, cy = coords[i]
                self.chart_canvas.create_oval(cx-3, cy-3, cx+3, cy+3, 
                                            fill="#0d1117", outline=line_color, width=2)
            
            # Final point always has a dot
            self.chart_canvas.create_oval(coords[-1][0]-4, coords[-1][1]-4, 
                                        coords[-1][0]+4, coords[-1][1]+4, 
                                        fill="#ffffff", outline=line_color, width=2)
            
            # Labels (Moved inside chart for better visibility)
            self.chart_canvas.create_text(pad + 5, pad + 10, text=f"${max_val:,.0f}", fill="#8b949e", font=('Segoe UI', 8, 'bold'), anchor=tk.W)
            self.chart_canvas.create_text(pad + 5, h - pad - 10, text=f"${min_val:,.0f}", fill="#8b949e", font=('Segoe UI', 8, 'bold'), anchor=tk.W)
            
        except Exception as e:
            print(f"Chart draw error: {e}")

    def _load_chart_history(self):
        try:
            path = Path("logs/chart_history.json")
            if path.exists():
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
            symbol = "XAUUSDm"
            if positions:
                symbol = positions[0].symbol
            
            # 2. Update Live Price
            tick = mt5.symbol_info_tick(symbol)
            if tick:
                self.live_price_label.config(text=f"LIVE PRICE: {tick.bid:.3f}")
            
            # 3. Calculate Exposure & Floating
            current_floating_pnl = sum(p.profit for p in positions) if positions else 0.0
            pnl_color = "#00e676" if current_floating_pnl >= 0 else "#ff5252"
            self.floating_pnl_label.config(text=f"CURRENT PNL: ${current_floating_pnl:,.2f}", fg=pnl_color)

            if not positions:
                self.net_lots_label.config(text="NET EXPOSURE: 0.00")
                for pips in [50, 100, 200, 300, 500]: 
                    self.proj_cards[pips].config(text="$0.00", fg="#888888")
                return

            total_buy_vol = sum(p.volume for p in positions if p.type == mt5.POSITION_TYPE_BUY)
            total_sell_vol = sum(p.volume for p in positions if p.type == mt5.POSITION_TYPE_SELL)
            net_vol = total_buy_vol - total_sell_vol 
            
            direction = "BUY (Long)" if net_vol > 0 else "SELL (Short)" if net_vol < 0 else "HEDGED"
            self.net_lots_label.config(text=f"NET EXPOSURE: {abs(net_vol):.2f} Lots {direction}")
            
            # 4. Scenario Projections (Total PnL = Current + Movement Impact)
            # Gold: $1 move (100 pips) = Lots * 100.
            # Example: 1 Lot * $10 move = $1000 impact.
            for pips in [1000, 2000, 5000, 10000, 15000, 30000]:
                movement_impact = abs(net_vol) * pips # Pips * Vol = Impact in $
                total_projected_pnl = current_floating_pnl - movement_impact
                
                proj_color = "#00e676" if total_projected_pnl >= 0 else "#ff5252"
                if pips in self.proj_cards:
                    self.proj_cards[pips].config(text=f"${total_projected_pnl:,.2f}", fg=proj_color)
                
        except Exception as e:
            print(f"Risk calc error: {e}")

    # _update_chart removed as requested

    def _update_grid_status(self):
        try:
            state_file = Path("logs/grid_state.json")
            if state_file.exists():
                with open(state_file, 'r') as f:
                    state = json.load(f)
                
                # Assume first symbol found for now (usually XAUUSDm)
                if state:
                    symbol = list(state.keys())[0]
                    data = state[symbol]
                    
                    mode = data.get('type', 'N/A')
                    progress = f"{data.get('last_index', 0)} / 300"
                    peak = data.get('peak_usd', 0.0)
                    
                    # Calculate lock same as trading script
                    lock = 0.0
                    if peak > 0:
                        lock = peak * 0.99
                        if peak - lock < 5.0:
                            lock = peak - 5.0
                    
                    self.grid_cards['grid_mode'].config(text=mode)
                    self.grid_cards['grid_progress'].config(text=progress)
                    self.grid_cards['peak_val'].config(text=f"${peak:,.2f}")
                    self.grid_cards['lock_val'].config(text=f"${lock:,.2f}")
                    
                    # Highlight if trailing is active
                    if peak > 1.0:
                        self.grid_cards['lock_val'].config(fg="#ff5252")
                    else:
                        self.grid_cards['lock_val'].config(fg="#888888", text="WAITING")
            else:
                for key in self.grid_cards:
                    self.grid_cards[key].config(text="OFF", fg="#888888")
        except Exception as e:
            print(f"Grid Status Update error: {e}")

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
                for i in self.hist_tree.get_children(): self.hist_tree.delete(i)
                for item in sorted(self.trade_history, key=lambda x: x['time'], reverse=True)[:50]:
                    self.hist_tree.insert("", tk.END, values=(
                        item['time'], item['symbol'], item['side'], item['volume'], f"{item['profit']:.2f}", item['comment']
                    ))

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
                
                self.metric_labels['total_trades'].config(text=str(len(profits)))
                self.metric_labels['win_rate'].config(text=f"{win_rate:.1%}")
                pnl_color = "#00ff00" if total_pnl >= 0 else "#ff5252"
                self.metric_labels['total_pnl'].config(text=f"${total_pnl:,.2f}", foreground=pnl_color)
                self.metric_labels['profit_factor'].config(text=f"{profit_factor:.2f}")
                self.metric_labels['max_drawdown'].config(text=f"{max_dd_pct:.2f}%")
                
                # Session PNL (Last 24h) removed to avoid overwriting the Session Growth metric 
                # (Balance - StartBalance) calculated in the main update loop.


    def _on_closing(self):
        self.running = False
        self.root.destroy()

    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    app = LivePortfolioDashboard()
    app.run()
