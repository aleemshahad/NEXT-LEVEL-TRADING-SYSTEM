# 🧠 NEXT LEVEL TRADING SYSTEM — SC-RIG-D v2.1 (G-Channel)

MetaTrader 5 ke liye ek **High-Performance Multi-Timeframe Trend-Locked DCA Grid Trading Bot** (Windows-only).

Bot Hybrid Mode (**G-Channel Cloud + D1 Pivots + Volume-Flow Gate**) par chalta hai aur dynamic pullback grid ke zariye recover karta hai, bina SL ke martingale-style DCA risk management ke sath.

> ⚠️ **EDUCATIONAL / DEMO USE ONLY.** Trading me risk hota hai. Bot demo/education ke liye hai.

---

## 🎯 Kya karta hai

- **G-Channel Cloud breakout** (trailing bands `a/b` + cross detection) se basket direction lock hota hai — sirf recent cross trend shift hota hai (whipsaw-proof).
- **Volume-Flow Gate** — naye basket se pehle OBV (5/20 MA) alignment + volume surge (`≥1.5×` 20-bar avg) confirm hoti hai. Direction mismatch ya low conviction par entry **flat wait** karti hai.
- **D1 Classic Pivots** (P, S1/S2/S3, R1/R2/R3) grid levels me extra structural support/resistance.
- **Dynamic Pullback Grid** — `hl_high/hl_low` (20-bar) channel retest levels + dollar-floor recovery levels (`level_distances_usd`), ATR boost + `floor_reference_price` scaling.
- **Lot Growth (Martingale-style)** — `lot_growth` ratio, `max_order_lot` cap, `max_total_exposure` cap (0.20 default) ke andar DCA.
- **Incremental Pending Reconcile** — sirf stale pendings remove / missing levels add hote hain; sehatmand levels kabhi remove+re-place nahi hote (**order churn khatam**).
- **Circuit Breaker** — floating loss `circuit_breaker_loss_pct` (5%) par **sab kuch close + bot pause** (cooldown minutes).
- **Risk Gate** — `check_risk_limits` (daily loss/drawdown) har grid deployment se pehle.
- **Auto Trailing + Basket Exit** — HARD EXIT (trailing off) / profit target par basket close; bot turant naya entry candidate dhoondhta hai.
- **Live Dashboard** — modern dark Tkinter UI: live clock, equity curve (gradient), DCA progress bar, volume-flow chip, D1 pivot, active positions, risk scenarios, terminal logs.

---

## 🏗️ Architecture

```
live_trading.py            Main bot (Hybrid SMC-Grid engine, circuit breaker, risk gate)
live_dashboard.py          Tkinter real-time dashboard
backtesting.py             Backtesting engine (Plotly charts + HTML reports)
computer_vision_analyzer.py Chart pattern recognition (OpenCV + sklearn)

trading_engine/
  ├─ broker.py             MT5 connection / order execution
  ├─ grid_manager.py       G-Channel grid — levels, reconcile, D1 pivots, volume flow
  ├─ risk.py               RiskManager — daily loss / drawdown / position sizing
  ├─ trading_brain.py      AI decision engine (requests-based calendar/news intelligence)
  ├─ notifications.py      Discord notifier
  └─ security.py           HWID license check

market_intelligence/       Sentiment + data acquisition subsystem
g-channel.pine             G-Channel indicator (TradingView PineScript)
```

---

## 🚀 RUN

```powershell
# 1) Requirements
pip install -r requirements.txt
pip install -r ict_requirements.txt      # CV/vision extras (optional)

# 2) Config
#   config.yaml  → symbol (XAUUSDm), timeframe (M15), grid knobs, risk limits
#   .env         → MT5_LOGIN / MT5_PASSWORD / MT5_SERVER / MT5_TERMINAL_PATH  (never commit!)

# 3) Launch (MetaTrader 5 terminal chalu hona zaroori hai; AUTO trading ON)
python live_trading.py --cron     # headless bot (auto-launches dashboard)
python live_dashboard.py          # sirf dashboard
python backtesting.py             # backtest + reports
```

- **Magic numbers:** `777001` (BUY grid) · `777002` (SELL grid) · `234000` (AI/ICT singles). Dashboard aur grid_manager dono me match hone zaroori hain.
- Default symbol **`XAUUSDm`** (Gold 0.05 base lot). Gold holidays/weekend par bot `BTCUSDm` par switch hota hai.
- Grid state → `logs/grid_state.json`, daily log → `logs/live_trading_YYYY-MM-DD.log`, reports → `logs/live_reports/`.

---

## ⚙️ Key Config Knobs (`config.yaml`)

| Key | Default | Meaning |
|---|---|---|
| `grid.level_distances_usd` | `[15,30,50,70,100]` | dollar-floor recovery levels (growing +30/level after L5) |
| `grid.floor_reference_price` | `4400` | floor scaling reference (auto-scales for BTC/weekends) |
| `grid.use_d1_pivot` | `true` | add daily pivots (S1/S2/S3 / R1/R2/R3) to grid levels |
| `grid.volume_flow_filter` | `true` | gate basket direction with volume flow |
| `grid.flow_min_score` | `0.6` | min flow score for entry (`0.6`=OBV must align; `0`=direction only) |
| `grid.flow_surge_threshold` | `1.5` | x-factor vs 20-bar avg volume for "surge" conviction |
| `grid.lot_growth` | `1.3` | DCA lot multiplier per level |
| `grid.max_order_lot` | `0.10` | per-order lot cap |
| `grid.max_total_exposure` | `0.20` | total committed volume (positions + pendings) cap |
| `risk.circuit_breaker_loss_pct` | `5.0` | floating-loss % that closes all + pauses |
| `risk.circuit_breaker_cooldown_min` | `120` | pause duration after circuit breaker |
| `risk.use_stop_loss` | `false` | SL toggle (off = martingale recovery, lot capped) |

> ⚠️ `grid_manager.py` ke changes bot restart ke baad load hote hain (hot-reload nahi). `config.yaml` hot-reload hota hai.

---

## 🧬 Changelog (v2.1 highlights)

- Order **churn fix** — incremental pending reconcile (no remove+re-place spam)
- **D1 pivots** in grid levels + live dashboard display
- **Volume-flow gate** (OBV + surge) — entry sirf confirmed flow ke sath
- **Circuit breaker** (floating-loss emergency exit + cooldown)
- **Risk gate** on grid deployment; `daily_pnl` live loop me wired
- Deeper **dollar-floor recovery** grid + auto price-scaling
- **Lot-growth** DCA config (lot_growth/max_order_lot/max_total_exposure)
- Broker `import time` fix, `aiohttp→requests` (calendar/news via `asyncio.to_thread`)
- Modern dashboard UI (clock, equity gradient, DCA bar, flow chip)

---
*NEXT LEVEL TRADING SYSTEM · SC-RIG-D v2.1 · G-Channel Hybrid Engine*