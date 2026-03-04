"""
🧠 NEXT LEVEL BRAIN — Operational Command Center
Real buttons • Real actions • Run everything from here
Created by: Aleem Shahzad | AI Partner: Claude (Anthropic)
"""

import streamlit as st
import subprocess
import sys
import os
import time
import json
import signal
from pathlib import Path
from datetime import datetime, timedelta

# ─── Project Root ────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).parent.resolve()
os.chdir(str(PROJECT_ROOT))

# ─── Page Config ─────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="🧠 NEXT LEVEL BRAIN — Command Center",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── Premium CSS ─────────────────────────────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&family=JetBrains+Mono:wght@400;500;600&display=swap');

    html, body, [class*="css"] {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    }

    .stApp {
        background: #080b12;
        background-image:
            radial-gradient(ellipse 80% 50% at 50% -20%, rgba(59, 130, 246, 0.08), transparent),
            radial-gradient(ellipse 60% 40% at 80% 60%, rgba(168, 85, 247, 0.05), transparent);
    }

    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0c1018 0%, #0f141e 100%) !important;
        border-right: 1px solid rgba(59, 130, 246, 0.08);
    }

    h1 {
        background: linear-gradient(135deg, #60a5fa 0%, #a78bfa 50%, #f472b6 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-weight: 900 !important;
        letter-spacing: -0.8px;
        font-size: 2.2rem !important;
    }
    h2 { color: #e2e8f0 !important; font-weight: 700 !important; }
    h3 { color: #cbd5e1 !important; font-weight: 600 !important; }

    /* Action Card */
    .action-card {
        background: linear-gradient(135deg, rgba(15,23,42,0.8), rgba(15,23,42,0.5));
        backdrop-filter: blur(24px);
        border: 1px solid rgba(59,130,246,0.1);
        border-radius: 16px;
        padding: 24px 28px;
        margin: 10px 0;
        transition: all 0.35s ease;
        box-shadow: 0 4px 32px rgba(0,0,0,0.4);
        position: relative;
        overflow: hidden;
    }
    .action-card::before {
        content: '';
        position: absolute;
        top: 0; left: 0; right: 0;
        height: 1px;
        background: linear-gradient(90deg, transparent, rgba(96,165,250,0.3), transparent);
    }
    .action-card:hover {
        border-color: rgba(96,165,250,0.25);
        transform: translateY(-2px);
        box-shadow: 0 8px 48px rgba(59,130,246,0.12);
    }

    .card-title {
        font-size: 1.2rem;
        font-weight: 700;
        color: #f1f5f9;
        margin-bottom: 6px;
    }
    .card-desc {
        color: #94a3b8;
        font-size: 0.88rem;
        line-height: 1.5;
    }

    /* Big stat */
    .big-stat {
        text-align: center;
        padding: 24px 16px;
        background: linear-gradient(135deg, rgba(15,23,42,0.8), rgba(15,23,42,0.5));
        border: 1px solid rgba(51,65,85,0.3);
        border-radius: 16px;
        position: relative;
        overflow: hidden;
    }
    .big-stat::before {
        content: '';
        position: absolute;
        top: 0; left: 0; right: 0;
        height: 2px;
    }
    .big-stat-num {
        font-size: 2.2rem;
        font-weight: 900;
        line-height: 1;
    }
    .big-stat-label {
        color: #64748b;
        font-size: 0.78rem;
        font-weight: 500;
        margin-top: 8px;
        text-transform: uppercase;
        letter-spacing: 0.8px;
    }
    .grad-blue .big-stat-num { background: linear-gradient(135deg, #3b82f6, #60a5fa); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
    .grad-blue::before { background: linear-gradient(90deg, transparent, #3b82f6, transparent); }
    .grad-green .big-stat-num { background: linear-gradient(135deg, #22c55e, #4ade80); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
    .grad-green::before { background: linear-gradient(90deg, transparent, #22c55e, transparent); }
    .grad-amber .big-stat-num { background: linear-gradient(135deg, #f59e0b, #fbbf24); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
    .grad-amber::before { background: linear-gradient(90deg, transparent, #f59e0b, transparent); }
    .grad-rose .big-stat-num { background: linear-gradient(135deg, #f43f5e, #fb7185); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
    .grad-rose::before { background: linear-gradient(90deg, transparent, #f43f5e, transparent); }
    .grad-purple .big-stat-num { background: linear-gradient(135deg, #8b5cf6, #a78bfa); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
    .grad-purple::before { background: linear-gradient(90deg, transparent, #8b5cf6, transparent); }

    /* Status badges */
    .status-running {
        display: inline-block;
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 0.75rem;
        font-weight: 700;
        background: rgba(34,197,94,0.15);
        color: #4ade80;
        animation: pulse 2s ease-in-out infinite;
    }
    .status-stopped {
        display: inline-block;
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 0.75rem;
        font-weight: 700;
        background: rgba(100,116,139,0.15);
        color: #94a3b8;
    }
    @keyframes pulse {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.6; }
    }

    /* Output terminal */
    .terminal-output {
        background: #0a0e17;
        border: 1px solid rgba(51,65,85,0.4);
        border-radius: 12px;
        padding: 16px 20px;
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.82rem;
        color: #4ade80;
        line-height: 1.6;
        max-height: 400px;
        overflow-y: auto;
        white-space: pre-wrap;
    }

    /* Buttons */
    .stButton > button {
        background: linear-gradient(135deg, #1d4ed8 0%, #3b82f6 100%) !important;
        color: white !important;
        border: none !important;
        border-radius: 10px !important;
        padding: 10px 24px !important;
        font-weight: 600 !important;
        font-family: 'Inter', sans-serif !important;
        transition: all 0.3s ease !important;
        box-shadow: 0 2px 12px rgba(59,130,246,0.25) !important;
    }
    .stButton > button:hover {
        background: linear-gradient(135deg, #2563eb 0%, #60a5fa 100%) !important;
        box-shadow: 0 4px 20px rgba(59,130,246,0.4) !important;
        transform: translateY(-1px) !important;
    }

    /* Tabs */
    .stTabs [data-baseweb="tab-list"] { gap: 2px; }
    .stTabs [data-baseweb="tab"] {
        background: rgba(15,23,42,0.5) !important;
        border: 1px solid rgba(51,65,85,0.3) !important;
        border-radius: 10px 10px 0 0 !important;
        color: #94a3b8 !important;
        padding: 10px 20px !important;
        font-weight: 500 !important;
    }
    .stTabs [aria-selected="true"] {
        background: rgba(59,130,246,0.08) !important;
        border-color: rgba(96,165,250,0.3) !important;
        color: #60a5fa !important;
        font-weight: 600 !important;
    }

    /* Scrollbar */
    ::-webkit-scrollbar { width: 5px; }
    ::-webkit-scrollbar-track { background: transparent; }
    ::-webkit-scrollbar-thumb { background: #1e293b; border-radius: 3px; }

    /* Hide branding */
    #MainMenu { visibility: hidden; }
    footer { visibility: hidden; }
    header { visibility: hidden; }
</style>
""", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
# HELPER: Run a script and capture output
# ═══════════════════════════════════════════════════════════════════════════════

def run_script(script_path, timeout=30, extra_args=None):
    """Run a Python script and return output."""
    cmd = [sys.executable, str(script_path)]
    if extra_args:
        cmd.extend(extra_args)
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(PROJECT_ROOT),
            env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        )
        return {
            "success": result.returncode == 0,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode,
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "stdout": "", "stderr": f"Script timed out after {timeout}s (ye normal hai interactive scripts ke liye)", "returncode": -1}
    except Exception as e:
        return {"success": False, "stdout": "", "stderr": str(e), "returncode": -1}


def launch_in_new_terminal(script_path, title=""):
    """Launch a script in a new terminal window (Windows)."""
    try:
        cmd = f'start "{title}" cmd /k "cd /d {PROJECT_ROOT} && python {script_path}"'
        os.system(cmd)
        return True
    except Exception as e:
        st.error(f"Launch failed: {e}")
        return False


def load_config():
    """Load config.yaml."""
    try:
        import yaml
        config_path = PROJECT_ROOT / "config.yaml"
        if config_path.exists():
            with open(config_path) as f:
                return yaml.safe_load(f)
    except:
        pass
    return {}


def get_latest_reports():
    """Get latest backtest/live reports."""
    reports = []
    
    # Backtest results
    bt_dir = PROJECT_ROOT / "backtest_results"
    if bt_dir.exists():
        for f in sorted(bt_dir.glob("*.json"), key=os.path.getmtime, reverse=True)[:5]:
            reports.append(("backtest", f))
    
    # Live reports
    live_dir = PROJECT_ROOT / "logs" / "live_reports"
    if live_dir.exists():
        for f in sorted(live_dir.glob("*.md"), key=os.path.getmtime, reverse=True)[:5]:
            reports.append(("live", f))
    
    return reports


def get_log_files():
    """Get recent log files."""
    logs_dir = PROJECT_ROOT / "logs"
    if logs_dir.exists():
        return sorted(
            [f for f in logs_dir.glob("*") if f.is_file() and not f.name.endswith(".json")],
            key=os.path.getmtime,
            reverse=True
        )[:10]
    return []


# ═══════════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ═══════════════════════════════════════════════════════════════════════════════

with st.sidebar:
    st.markdown("""
    <div style="text-align: center; padding: 28px 0 16px 0;">
        <div style="font-size: 3.2rem; line-height: 1; filter: drop-shadow(0 0 20px rgba(96,165,250,0.4));">🧠</div>
        <div style="font-size: 1.3rem; font-weight: 900;
            background: linear-gradient(135deg, #60a5fa 0%, #a78bfa 50%, #f472b6 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-top: 10px; letter-spacing: -0.5px;">
            NEXT LEVEL BRAIN
        </div>
        <div style="color: #475569; font-size: 0.72rem; margin-top: 6px; letter-spacing: 1.5px; text-transform: uppercase;">
            Command Center
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown('<div style="height:1px; background:linear-gradient(90deg, transparent, rgba(59,130,246,0.2), transparent); margin:12px 0;"></div>', unsafe_allow_html=True)

    page = st.radio(
        "nav",
        [
            "🏠 Dashboard",
            "📊 Backtesting",
            "🔴 Live Trading",
            "🌐 Market Intelligence",
            "⚙️ Settings",
            "📜 Logs & Reports",
            "🖥️ Terminal",
        ],
        label_visibility="collapsed",
    )

    st.markdown('<div style="height:1px; background:linear-gradient(90deg, transparent, rgba(59,130,246,0.2), transparent); margin:12px 0;"></div>', unsafe_allow_html=True)

    # Status checks
    config = load_config()
    config_ok = bool(config)
    env_ok = (PROJECT_ROOT / ".env").exists()
    
    st.markdown(f"""
    <div style="padding: 8px 0;">
        <div style="color:#475569; font-size:0.7rem; text-transform:uppercase; letter-spacing:1px; margin-bottom:8px;">System</div>
        <div style="font-size:0.82rem; margin:4px 0;">{'🟢' if config_ok else '🔴'} config.yaml</div>
        <div style="font-size:0.82rem; margin:4px 0;">{'🟢' if env_ok else '🟡'} .env</div>
        <div style="font-size:0.82rem; margin:4px 0;">{'🟢' if (PROJECT_ROOT / 'backtesting.py').exists() else '🔴'} backtesting.py</div>
        <div style="font-size:0.82rem; margin:4px 0;">{'🟢' if (PROJECT_ROOT / 'live_trading.py').exists() else '🔴'} live_trading.py</div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown(f'<div style="color:#334155; font-size:0.68rem; margin-top:20px; text-align:center;">⏱ {datetime.now().strftime("%d %b %Y • %H:%M:%S")}</div>', unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE: DASHBOARD (Home)
# ═══════════════════════════════════════════════════════════════════════════════

if page == "🏠 Dashboard":
    st.markdown("# 🧠 NEXT LEVEL BRAIN")
    st.markdown('<div style="color:#64748b; margin:-12px 0 24px 0;">Yahan se sab kuch control karein — Backtesting, Live Trading, Market Intelligence</div>', unsafe_allow_html=True)

    # Quick stats
    c1, c2, c3, c4 = st.columns(4)

    # Count reports
    bt_count = len(list((PROJECT_ROOT / "backtest_results").glob("*.json"))) if (PROJECT_ROOT / "backtest_results").exists() else 0
    live_count = len(list((PROJECT_ROOT / "logs" / "live_reports").glob("*.md"))) if (PROJECT_ROOT / "logs" / "live_reports").exists() else 0
    ai_memories = 0
    mem_file = PROJECT_ROOT / "models" / "ai_memories.json"
    if mem_file.exists():
        try:
            ai_memories = len(json.load(open(mem_file)))
        except:
            pass

    with c1:
        st.markdown(f'<div class="big-stat grad-blue"><div class="big-stat-num">{bt_count}</div><div class="big-stat-label">Backtest Reports</div></div>', unsafe_allow_html=True)
    with c2:
        st.markdown(f'<div class="big-stat grad-green"><div class="big-stat-num">{live_count}</div><div class="big-stat-label">Live Sessions</div></div>', unsafe_allow_html=True)
    with c3:
        st.markdown(f'<div class="big-stat grad-amber"><div class="big-stat-num">{ai_memories}</div><div class="big-stat-label">AI Memories</div></div>', unsafe_allow_html=True)
    with c4:
        symbols_str = ", ".join(config.get("symbols", ["N/A"]))
        st.markdown(f'<div class="big-stat grad-purple"><div class="big-stat-num">{symbols_str}</div><div class="big-stat-label">Active Symbols</div></div>', unsafe_allow_html=True)

    st.markdown("")

    # Quick launch cards
    st.markdown("## ⚡ Quick Actions")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("""
        <div class="action-card">
            <div class="card-title">📊 Backtesting</div>
            <div class="card-desc">Historical data pe ICT/SMC strategy test karein. Symbol, timeframe, aur period choose karein.</div>
        </div>
        """, unsafe_allow_html=True)
        if st.button("▶️ Run Backtesting", key="q_bt", use_container_width=True):
            st.session_state["go_to"] = "📊 Backtesting"
            st.rerun()

    with col2:
        st.markdown("""
        <div class="action-card">
            <div class="card-title">🔴 Live Trading</div>
            <div class="card-desc">Grid Strategy ya ICT SMC se real-time trading start karein MT5 pe.</div>
        </div>
        """, unsafe_allow_html=True)
        if st.button("▶️ Start Live Trading", key="q_live", use_container_width=True):
            st.session_state["go_to"] = "🔴 Live Trading"
            st.rerun()

    with col3:
        st.markdown("""
        <div class="action-card">
            <div class="card-title">🌐 Market Intelligence</div>
            <div class="card-desc">Sentiment analysis aur smart money inference — market ka mood jaanein.</div>
        </div>
        """, unsafe_allow_html=True)
        if st.button("▶️ Run Intelligence", key="q_mi", use_container_width=True):
            st.session_state["go_to"] = "🌐 Market Intelligence"
            st.rerun()

    # Latest report preview
    st.markdown("---")
    st.markdown("## 📄 Latest Report")

    report_file = PROJECT_ROOT / "latest_intelligence_report.txt"
    if report_file.exists():
        txt = report_file.read_text(encoding="utf-8", errors="ignore")
        mod_time = datetime.fromtimestamp(report_file.stat().st_mtime).strftime("%d %b %Y • %H:%M")
        st.caption(f"🕐 Last updated: {mod_time}")
        st.code(txt[:3000], language="text")
    else:
        st.info("🔍 Abhi koi intelligence report nahi hai. 'Market Intelligence' chalao pehle.")


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE: BACKTESTING
# ═══════════════════════════════════════════════════════════════════════════════

elif page == "📊 Backtesting":
    st.markdown("# 📊 Backtesting Engine")
    st.markdown('<div style="color:#64748b; margin:-12px 0 24px 0;">Symbol, timeframe, aur period select karein — phir Run dabayein</div>', unsafe_allow_html=True)

    tab1, tab2 = st.tabs(["🚀 Run Backtest", "📋 Past Results"])

    with tab1:
        st.markdown("### ⚙️ Backtest Settings")

        col1, col2, col3 = st.columns(3)

        with col1:
            symbol = st.selectbox("🪙 Symbol", ["XAUUSDm", "BTCUSDm", "EURUSDm", "GBPUSDm", "USDJPYm", "ETHUSDm", "XAGUSDm"])

        with col2:
            timeframe = st.selectbox("⏰ Timeframe", ["M1", "M3", "M5", "M15", "M30", "H1", "H4", "D1"], index=2)

        with col3:
            period = st.selectbox("📅 Period", ["7 days", "30 days", "90 days", "180 days", "365 days"], index=1)
            days = int(period.split()[0])

        strategy = st.selectbox("🎯 Strategy", ["ICT SMC", "Grid Strategy (Both)", "Grid BUY ONLY", "Grid SELL ONLY"])

        st.markdown("---")

        col_run, col_gui = st.columns(2)

        with col_run:
            st.markdown("""
            <div class="action-card">
                <div class="card-title">🖥️ GUI Dashboard</div>
                <div class="card-desc">Tkinter GUI open hoga nayi window mein — wahan se interactive backtest karein</div>
            </div>
            """, unsafe_allow_html=True)
            if st.button("🖥️ Open Backtest GUI", key="bt_gui", use_container_width=True):
                launch_in_new_terminal("backtesting.py", "NEXT LEVEL BRAIN - Backtesting")
                st.success("✅ Backtesting GUI launch ho raha hai nayi window mein!")
                st.info("👆 Nayi terminal window check karein")

        with col_gui:
            st.markdown("""
            <div class="action-card">
                <div class="card-title">⚡ Quick Backtest</div>
                <div class="card-desc">Yahan se seedha backtest result dekhein — terminal output neeche show hoga</div>
            </div>
            """, unsafe_allow_html=True)
            if st.button("▶️ Run Quick Backtest", key="bt_quick", use_container_width=True):
                # We'll create a small helper script and run it
                helper = PROJECT_ROOT / "_quick_backtest.py"
                helper_code = f"""
import sys, os
sys.path.insert(0, r"{PROJECT_ROOT}")
os.chdir(r"{PROJECT_ROOT}")

from pathlib import Path
Path("logs").mkdir(exist_ok=True)
Path("backtest_results").mkdir(exist_ok=True)
Path("models").mkdir(exist_ok=True)
Path("charts").mkdir(exist_ok=True)

from datetime import datetime, timedelta
from backtesting import BacktestEngine

engine = BacktestEngine()
end_date = datetime.now()
start_date = end_date - timedelta(days={days})

print("🚀 Starting backtest...")
print(f"Symbol: {symbol}")
print(f"Timeframe: {timeframe}")
print(f"Period: {days} days")
print(f"Strategy: {strategy}")
print()

strategy_name = "{strategy}"
if "Grid" in strategy_name and "BUY" in strategy_name:
    results = engine.run_grid_backtest("{symbol}", start_date, end_date, "{timeframe}", mode="BUY_ONLY")
elif "Grid" in strategy_name and "SELL" in strategy_name:
    results = engine.run_grid_backtest("{symbol}", start_date, end_date, "{timeframe}", mode="SELL_ONLY")
elif "Grid" in strategy_name:
    results = engine.run_grid_backtest("{symbol}", start_date, end_date, "{timeframe}", mode="BOTH")
else:
    results = engine.run_backtest("{symbol}", start_date, end_date, "{timeframe}")

if 'error' not in results:
    engine.generate_report(results)
    print()
    print("✅ Backtest complete!")
else:
    print(f"❌ Error: {{results['error']}}")
"""
                helper.write_text(helper_code, encoding="utf-8")
                
                with st.spinner(f"⏳ Backtesting {symbol} ({timeframe}, {days} days)... MT5 se data le raha hai"):
                    result = run_script(helper, timeout=120)
                
                try:
                    helper.unlink()
                except:
                    pass
                
                if result["stdout"]:
                    st.markdown(f'<div class="terminal-output">{result["stdout"]}</div>', unsafe_allow_html=True)
                if result["stderr"]:
                    st.error(result["stderr"][:2000])
                if not result["stdout"] and not result["stderr"]:
                    st.warning("Script ne koi output nahi diya. MT5 connection check karein.")

    with tab2:
        st.markdown("### 📋 Previous Backtest Results")
        bt_dir = PROJECT_ROOT / "backtest_results"
        if bt_dir.exists():
            reports = sorted(bt_dir.glob("*.json"), key=os.path.getmtime, reverse=True)
            if reports:
                for report_file in reports[:10]:
                    mod_time = datetime.fromtimestamp(report_file.stat().st_mtime).strftime("%d %b %Y • %H:%M")
                    with st.expander(f"📊 {report_file.stem} — {mod_time}"):
                        try:
                            data = json.loads(report_file.read_text())
                            results = data.get("results", data)
                            if "total_trades" in results:
                                c1, c2, c3, c4 = st.columns(4)
                                c1.metric("Total Trades", results.get("total_trades", 0))
                                c2.metric("Win Rate", f"{results.get('win_rate', 0):.1%}")
                                c3.metric("Total P&L", f"${results.get('total_pnl', 0):.2f}")
                                c4.metric("Profit Factor", f"{results.get('profit_factor', 0):.2f}")
                            st.json(results)
                        except:
                            st.code(report_file.read_text()[:3000])
            else:
                st.info("Abhi koi backtest report nahi hai. Pehle ek backtest run karein!")
        else:
            st.info("backtest_results/ folder nahi mila. Pehle ek backtest run karein!")


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE: LIVE TRADING
# ═══════════════════════════════════════════════════════════════════════════════

elif page == "🔴 Live Trading":
    st.markdown("# 🔴 Live Trading System")
    st.markdown('<div style="color:#64748b; margin:-12px 0 24px 0;">Strategy select karein aur trading start karein — nayi terminal window mein chalega</div>', unsafe_allow_html=True)

    tab1, tab2, tab3 = st.tabs(["🚀 Start Trading", "🧹 Manage Orders", "📈 Live Dashboard"])

    with tab1:
        st.markdown("### 🎯 Trading Setup")

        col1, col2 = st.columns(2)

        with col1:
            live_strategy = st.selectbox(
                "🎯 Strategy / Direction",
                ["Grid BUY ONLY (300 Orders)", "Grid SELL ONLY (300 Orders)", "Grid BOTH (300+300 Orders)", "ICT SMC (Trend Following)"],
                index=0
            )

        with col2:
            live_tf = st.selectbox("⏰ Timeframe", ["M1", "M3", "M5", "M15", "M30", "H1", "H4", "D1"], index=0)

        live_symbol = st.selectbox("🪙 Symbol", config.get("symbols", ["XAUUSDm"]))

        st.markdown("---")

        st.markdown("""
        <div class="action-card">
            <div class="card-title">⚠️ Important</div>
            <div class="card-desc">
                Live Trading ek nayi terminal window mein start hogi. Woh window band mat karein jab tak trading chal rahi ho.
                Band karne ke liye terminal mein <strong>Ctrl+C</strong> dabayein.
            </div>
        </div>
        """, unsafe_allow_html=True)

        if st.button("🚀 START LIVE TRADING", key="start_live", use_container_width=True, type="primary"):
            # Map strategy selection to the script's expected input
            if "BUY ONLY" in live_strategy:
                strat_choice = "1"
            elif "SELL ONLY" in live_strategy:
                strat_choice = "2"
            elif "BOTH" in live_strategy:
                strat_choice = "3"
            else:
                strat_choice = "4"

            tf_map = {"M1": "1", "M3": "2", "M5": "3", "M15": "4", "M30": "5", "H1": "6", "H4": "7", "D1": "8"}
            tf_choice = tf_map.get(live_tf, "1")

            # Create auto-input helper
            auto_helper = PROJECT_ROOT / "_auto_live.py"
            auto_code = f"""
import sys, os, asyncio
sys.path.insert(0, r"{PROJECT_ROOT}")
os.chdir(r"{PROJECT_ROOT}")

from pathlib import Path
Path("logs").mkdir(exist_ok=True)
Path("charts").mkdir(exist_ok=True)
Path("models").mkdir(exist_ok=True)

from live_trading import LiveTradingSystem

strategy_map = {{"1": "Grid BUY ONLY", "2": "Grid SELL ONLY", "3": "Grid Both", "4": "ICT SMC"}}
strategy = strategy_map["{strat_choice}"]

print("=" * 60)
print("🧠 NEXT LEVEL BRAIN - LIVE TRADING")
print("=" * 60)
print(f"Symbol: {live_symbol}")
print(f"Strategy: {{strategy}}")
print(f"Timeframe: {live_tf}")
print("=" * 60)
print()

system = LiveTradingSystem()
system.symbols = ["{live_symbol}"]
system.strategy = strategy
system.timeframe = "{live_tf}"

asyncio.run(system.run())
"""
            auto_helper.write_text(auto_code, encoding="utf-8")

            # Launch in new terminal
            cmd = f'start "NEXT LEVEL BRAIN - Live Trading" cmd /k "cd /d {PROJECT_ROOT} && python _auto_live.py"'
            os.system(cmd)

            st.success("✅ Live Trading launch ho gaya nayi terminal window mein!")
            st.info("👆 Nayi terminal window check karein — wahan pe trading output dikhega")
            st.warning("⚠️ Band karne ke liye terminal mein Ctrl+C press karein")

    with tab2:
        st.markdown("### 🧹 Order Management")

        st.markdown("""
        <div class="action-card">
            <div class="card-title">🗑️ Delete All Pending Orders</div>
            <div class="card-desc">Saare pending orders (Gold/XAUUSDm aur XAUUSD) delete kar dein — active positions nahi band hongi</div>
        </div>
        """, unsafe_allow_html=True)

        if st.button("🧹 DELETE ALL PENDING ORDERS", key="del_orders", use_container_width=True):
            delete_script = PROJECT_ROOT / "_delete_pendings.py"
            delete_code = """
import MetaTrader5 as mt5

if not mt5.initialize():
    print(f"MT5 init failed: {mt5.last_error()}")
    quit()

print("🧹 Deleting all pending orders...")
total = 0
for sym in ["XAUUSDm", "XAUUSD"]:
    orders = mt5.orders_get(symbol=sym)
    if orders:
        print(f"  {sym}: {len(orders)} pending orders found")
        for o in orders:
            result = mt5.order_send({"action": mt5.TRADE_ACTION_REMOVE, "order": o.ticket})
            if result and result.retcode == mt5.TRADE_RETCODE_DONE:
                total += 1
        print(f"  ✅ Deleted from {sym}")
    else:
        print(f"  {sym}: No pending orders")

print(f"\\n✅ Total {total} pending orders deleted!")
mt5.shutdown()
"""
            delete_script.write_text(delete_code, encoding="utf-8")

            with st.spinner("🧹 Pending orders delete ho rahe hain..."):
                result = run_script(delete_script, timeout=30)

            try:
                delete_script.unlink()
            except:
                pass

            if result["stdout"]:
                st.markdown(f'<div class="terminal-output">{result["stdout"]}</div>', unsafe_allow_html=True)
            if result["stderr"]:
                st.error(result["stderr"][:1000])

    with tab3:
        st.markdown("### 📈 Live Portfolio Dashboard")
        st.markdown("""
        <div class="action-card">
            <div class="card-title">📈 Real-time Portfolio Monitor</div>
            <div class="card-desc">Tkinter GUI se apne positions, equity, aur trade history track karein</div>
        </div>
        """, unsafe_allow_html=True)

        if st.button("📈 Open Live Dashboard", key="open_live_dash", use_container_width=True):
            launch_in_new_terminal("live_dashboard.py", "Live Portfolio Dashboard")
            st.success("✅ Live Dashboard launch ho raha hai!")


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE: MARKET INTELLIGENCE
# ═══════════════════════════════════════════════════════════════════════════════

elif page == "🌐 Market Intelligence":
    st.markdown("# 🌐 Market Intelligence")
    st.markdown('<div style="color:#64748b; margin:-12px 0 24px 0;">Sentiment analysis, smart money inference, aur market mood — ek click mein</div>', unsafe_allow_html=True)

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("""
        <div class="action-card">
            <div class="card-title">🧠 Run Intelligence Analysis</div>
            <div class="card-desc">Autonomous sentiment aur smart money analysis chalayein — report generate hoga</div>
        </div>
        """, unsafe_allow_html=True)

        if st.button("▶️ Run Market Intelligence", key="run_mi", use_container_width=True):
            mi_script = PROJECT_ROOT / "run_market_intelligence.py"
            if mi_script.exists():
                with st.spinner("🌐 Market intelligence analysis chal raha hai..."):
                    result = run_script(mi_script, timeout=60)
                
                if result["stdout"]:
                    st.markdown(f'<div class="terminal-output">{result["stdout"]}</div>', unsafe_allow_html=True)
                if result["stderr"]:
                    with st.expander("⚠️ Warnings/Errors"):
                        st.code(result["stderr"][:2000])
                
                if result["success"]:
                    st.success("✅ Intelligence report generate ho gaya!")
                    st.rerun()  # Refresh to show latest report
            else:
                st.error("run_market_intelligence.py nahi mila!")

    with col2:
        st.markdown("""
        <div class="action-card">
            <div class="card-title">🔍 ICT Concept Auditor</div>
            <div class="card-desc">Poora ICT strategy evaluation pipeline — feature engineering se verdict tak</div>
        </div>
        """, unsafe_allow_html=True)

        if st.button("▶️ Run ICT Auditor", key="run_ict", use_container_width=True):
            ict_script = PROJECT_ROOT / "ict_concept_auditor.py"
            if ict_script.exists():
                with st.spinner("🔍 ICT audit chal raha hai..."):
                    result = run_script(ict_script, timeout=120)
                
                if result["stdout"]:
                    st.markdown(f'<div class="terminal-output">{result["stdout"]}</div>', unsafe_allow_html=True)
                if result["stderr"]:
                    with st.expander("⚠️ Warnings/Errors"):
                        st.code(result["stderr"][:2000])
            else:
                st.error("ict_concept_auditor.py nahi mila!")

    st.markdown("---")
    st.markdown("### 📄 Latest Intelligence Report")

    report_file = PROJECT_ROOT / "latest_intelligence_report.txt"
    if report_file.exists():
        mod_time = datetime.fromtimestamp(report_file.stat().st_mtime).strftime("%d %b %Y • %H:%M:%S")
        st.caption(f"🕐 Last updated: {mod_time}")
        content = report_file.read_text(encoding="utf-8", errors="ignore")
        st.code(content, language="text")
    else:
        st.info("Abhi koi report nahi hai. Upar se 'Run Market Intelligence' dabayein.")


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE: SETTINGS
# ═══════════════════════════════════════════════════════════════════════════════

elif page == "⚙️ Settings":
    st.markdown("# ⚙️ Settings")
    st.markdown('<div style="color:#64748b; margin:-12px 0 24px 0;">Configuration files — settings, environment, dependencies</div>', unsafe_allow_html=True)

    tab1, tab2, tab3 = st.tabs(["⚙️ config.yaml", "🔒 .env", "📦 requirements.txt"])

    with tab1:
        config_path = PROJECT_ROOT / "config.yaml"
        if config_path.exists():
            config_text = config_path.read_text()
            
            st.markdown("### Current Config")
            st.code(config_text, language="yaml")

            st.markdown("### ✏️ Edit Config")
            new_config = st.text_area("Config content (edit karein aur save dabayein)", config_text, height=300, key="config_edit")
            
            if st.button("💾 Save Config", key="save_config"):
                try:
                    import yaml
                    yaml.safe_load(new_config)  # Validate
                    config_path.write_text(new_config)
                    st.success("✅ Config saved!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Invalid YAML: {e}")
        else:
            st.warning("config.yaml nahi mila!")

    with tab2:
        env_path = PROJECT_ROOT / ".env"
        if env_path.exists():
            lines = env_path.read_text().splitlines()
            masked = []
            for line in lines:
                s = line.strip()
                if "=" in s and not s.startswith("#"):
                    key, _, val = s.partition("=")
                    v = val.strip().strip('"').strip("'")
                    masked.append(f"{key.strip()} = {'•••' if v else '(empty)'}")
                else:
                    masked.append(s)
            st.code("\n".join(masked), language="bash")
            st.caption("🔒 Values masked for security")
        else:
            st.info(".env file nahi mila")

    with tab3:
        req_path = PROJECT_ROOT / "requirements.txt"
        if req_path.exists():
            st.code(req_path.read_text(), language="text")
        else:
            st.info("requirements.txt nahi mila")


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE: LOGS & REPORTS
# ═══════════════════════════════════════════════════════════════════════════════

elif page == "📜 Logs & Reports":
    st.markdown("# 📜 Logs & Reports")
    st.markdown('<div style="color:#64748b; margin:-12px 0 24px 0;">Recent logs, session reports, aur error tracking</div>', unsafe_allow_html=True)

    tab1, tab2, tab3 = st.tabs(["📜 System Logs", "📊 Live Reports", "❌ Errors"])

    with tab1:
        log_files = get_log_files()
        if log_files:
            selected_log = st.selectbox(
                "Select Log",
                log_files,
                format_func=lambda f: f"📄 {f.name} ({f.stat().st_size/1024:.1f} KB • {datetime.fromtimestamp(f.stat().st_mtime).strftime('%d %b %H:%M')})"
            )
            if selected_log:
                content = selected_log.read_text(encoding="utf-8", errors="ignore")
                lines = content.splitlines()
                if len(lines) > 300:
                    st.info(f"Last 300 of {len(lines):,} lines")
                    content = "\n".join(lines[-300:])
                st.code(content, language="log")
        else:
            st.info("Koi log file nahi mili")

    with tab2:
        live_dir = PROJECT_ROOT / "logs" / "live_reports"
        if live_dir.exists():
            reports = sorted(live_dir.glob("*.md"), key=os.path.getmtime, reverse=True)
            if reports:
                for rpt in reports[:10]:
                    mod_time = datetime.fromtimestamp(rpt.stat().st_mtime).strftime("%d %b %Y • %H:%M")
                    with st.expander(f"📊 {rpt.stem} — {mod_time}"):
                        st.markdown(rpt.read_text(encoding="utf-8", errors="ignore"))
            else:
                st.info("Abhi koi live report nahi hai")
        else:
            st.info("Live reports folder nahi mila")

    with tab3:
        error_log = PROJECT_ROOT / "error.log"
        if error_log.exists() and error_log.stat().st_size > 0:
            content = error_log.read_text(encoding="utf-8", errors="ignore")
            st.code(content[-5000:], language="log")
            
            if st.button("🗑️ Clear Error Log", key="clear_err"):
                error_log.write_text("")
                st.success("✅ Error log cleared!")
                st.rerun()
        else:
            st.success("✅ No errors — all clear!")


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE: TERMINAL
# ═══════════════════════════════════════════════════════════════════════════════

elif page == "🖥️ Terminal":
    st.markdown("# 🖥️ Terminal")
    st.markdown('<div style="color:#64748b; margin:-12px 0 24px 0;">Koi bhi command yahan se run karein</div>', unsafe_allow_html=True)

    # Predefined commands
    st.markdown("### ⚡ Quick Commands")

    quick_cmds = {
        "🛠️ MT5 Debug": "python debug_mt5.py",
        "🩺 MT5 Diagnose": "python diagnose_mt5.py",
        "📊 Backtesting GUI": "python backtesting.py",
        "🔴 Live Trading": "python live_trading.py",
        "🌐 Market Intelligence": "python run_market_intelligence.py",
        "📈 Live Dashboard": "python live_dashboard.py",
    }

    cols = st.columns(3)
    for i, (label, cmd) in enumerate(quick_cmds.items()):
        with cols[i % 3]:
            if st.button(label, key=f"qcmd_{i}", use_container_width=True):
                script_name = cmd.split()[-1]
                launch_in_new_terminal(script_name, label)
                st.success(f"✅ {label} launch ho gaya nayi window mein!")

    st.markdown("---")
    st.markdown("### 💻 Custom Command")

    custom_cmd = st.text_input("Command likhein", placeholder="python backtesting.py", key="custom_cmd")

    col1, col2 = st.columns(2)

    with col1:
        if st.button("▶️ Run Here (output neeche)", key="run_here", use_container_width=True):
            if custom_cmd:
                with st.spinner(f"Running: {custom_cmd}"):
                    try:
                        result = subprocess.run(
                            custom_cmd,
                            shell=True,
                            capture_output=True,
                            text=True,
                            timeout=60,
                            cwd=str(PROJECT_ROOT),
                        )
                        if result.stdout:
                            st.markdown(f'<div class="terminal-output">{result.stdout}</div>', unsafe_allow_html=True)
                        if result.stderr:
                            st.error(result.stderr[:2000])
                        if not result.stdout and not result.stderr:
                            st.info("Command executed — no output")
                    except subprocess.TimeoutExpired:
                        st.warning("⏰ Command timed out (60s). Interactive scripts ke liye 'Run in Terminal' use karein.")
                    except Exception as e:
                        st.error(str(e))

    with col2:
        if st.button("🖥️ Run in New Terminal", key="run_terminal", use_container_width=True):
            if custom_cmd:
                cmd = f'start "Command" cmd /k "cd /d {PROJECT_ROOT} && {custom_cmd}"'
                os.system(cmd)
                st.success("✅ Nayi terminal window mein chal raha hai!")


# ═══════════════════════════════════════════════════════════════════════════════
# FOOTER
# ═══════════════════════════════════════════════════════════════════════════════

st.markdown(f"""
<div style="text-align:center; padding:32px 0 16px 0;">
    <div style="height:1px; background:linear-gradient(90deg, transparent, rgba(59,130,246,0.1), transparent); margin-bottom:20px;"></div>
    <div style="color:#1e293b; font-size:0.72rem;">
        🧠 NEXT LEVEL BRAIN v2.0 — Created by Aleem Shahzad | AI Partner: Claude (Anthropic)
    </div>
</div>
""", unsafe_allow_html=True)
