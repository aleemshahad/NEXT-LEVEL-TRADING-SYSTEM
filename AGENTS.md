# AGENTS.md

## What This Is

Python MetaTrader 5 algo-trading bot (Windows-only). No package manager, no tests, no linter, no CI. Runs directly from root directory.

## How to Run

```powershell
pip install -r requirements.txt          # Core deps (MetaTrader5, pandas, numpy<2.4.0, loguru, PyYAML, etc.)
pip install -r ict_requirements.txt      # Optional: opencv, scipy, TA-Lib (TA-Lib may need system-level install on Windows)

python live_trading.py --cron            # Headless bot (auto-launches dashboard subprocess)
python live_trading.py                   # Interactive mode (prompts for strategy + timeframe)
python live_dashboard.py                 # Standalone dashboard
python backtesting.py                    # Backtester with Tkinter GUI
```

CLI flags for `live_trading.py`: `--strategy "Hybrid Mode"`, `--timeframe M15`, `--cron`, `--auto-start`

## Architecture

```
live_trading.py          Orchestrator — async loop, 1s cycle, spawns dashboard as subprocess
trading_engine/
  broker.py              MT5 connection & order execution
  grid_manager.py        G-Channel grid, **proactive market shift detection** (6-signal scoring), adaptive response (WARNING→log, CONFIRMED→cancel DCA+tight trail, EXTENDED→close+reverse), Fibonacci DCA, D1 pivots, volume flow filter
  trading_brain.py       AI decision engine (3 entry plans), G-Channel indicators, news gating (ICTAnalyzer removed — ICT logic consolidated here)
  risk.py                Daily loss/drawdown tracking, asset-class-aware position sizing
  notifications.py       Discord webhook alerts
  security.py            HWID license (always authorized — effectively disabled)
  __init__.py
live_dashboard.py        1420-line Tkinter GUI — reads logs/grid_state.json for shared state
backtesting.py           Standalone backtester (ICT/SMC + Grid modes) with Plotly charts
computer_vision_analyzer.py  STUB at root — 12 lines, not imported or used anywhere
market_intelligence/     STUBS — sentiment_intelligence.py and data_acquisition.py return empty data, enabled=False
g-channel.pine           TradingView PineScript v6 indicator (root level)
```

Entry flow: `main()` -> SecurityManager -> select_trade_setup -> LiveTradingSystem -> launch_dashboard(subprocess) -> asyncio.run(ts.run())

## Config

- **`config.yaml`** — All trading parameters. Hot-reloaded every cycle (file mtime check via `_reload_settings()`).
  - **`fib_dca` section** — Fibonacci-anchored DCA engine (replaces legacy ATR-pip / fixed-dollar floor DCA). `enabled: true` by default, uses `lookback_bars`, `max_open_layers`, `proximity_tolerance`, `body_ratio_limit`, `wick_ratio_min`, `freeze_on_gchannel_flip`.
  - **`grid.flow_min_score`** default `0.6` (OBV must align; `0`=direction only)
  - **`grid.lot_growth`** default `1.3`, **`max_order_lot`** `0.20`, **`max_total_exposure`** `0.20`
  - **`risk.circuit_breaker_loss_pct`** `5.0`, **`circuit_breaker_cooldown_min`** `120`
  - **`news.block_window_min`** `30` before high-impact USD news
- **`.env`** — MT5 credentials: `MT5_LOGIN`, `MT5_PASSWORD`, `MT5_SERVER`, `MT5_TERMINAL_PATH`, `DISCORD_WEBHOOK_URL`. Never commit `.env`; keep secrets local only.
- Grid state persists to `logs/grid_state.json` (bridge between bot and dashboard).
- **`logs/` is fully gitignored** — `grid_state.json`, `trading_active.lock`, and all `.log` files are NOT tracked in git. They are runtime files recreated on each session.
- **Code changes to `trading_engine/` require a full restart** — only `config.yaml` is hot-reloaded.
- **Default symbol is `XAUUSDm`** (Gold, 0.05 base lot). Bot switches to `BTCUSDm` on weekends/holidays.

## Strategy Improvement (Market Shift Detection)

**Problem solved:** Market direction shifts were only detected reactively (after G-Channel flip → FROZEN → no recovery path). Now detects shifts early with multi-signal scoring.

**New in `grid_manager.py`:**
- `_detect_market_shift()` — 6-signal detector:
  1. `GCHANNEL_CROSS` — M15 G-Channel actual flip
  2. `GCHANNEL_OVERTURN` — sustained G-Channel opposite direction
  3. `CONSECUTIVE_BEARISH/BULLISH` — 3+ candles against position
  4. `VOLUME_REVERSAL` — surge on wrong-side candle
  5. `STRUCTURAL_BREAK` — price broke buy_level/sell_level
  6. `ATR_EXPANSION` — volatility spike (≥1.3×)
  7. `GCHANNEL_SLOPE_DOWN` — G-Channel avg slope turning
- Stages: `NONE` → `WARNING`(1 signal) → `CONFIRMED`(3+) → `EXTENDED`(5+)
- `_adaptive_response()`: WARNING=log alert; CONFIRMED=cancel DCA pendings + tight trailing; EXTENDED=close basket + reverse grid direction
- In `update()`, shift detection runs BEFORE the old FROZEN check. If shift is detected, adaptive response handles it and returns early. Simple FROZEN only triggers if NO shift signals are active.

**Config needed:** No new config keys — uses existing `flow_surge_threshold`, `fib_freeze_on_flip`, `volume_flow_filter`.

## Gotchas

- **Windows-only**: MetaTrader5 package, `subprocess.Popen` with Windows creation flags, hardcoded `C:\Program Files\MetaTrader 5\terminal64.exe` path in dashboard.
- **Mixed async/sync**: `broker.py` has some `async def` methods and some regular `def` — grid_manager calls both via `await` and direct calls.
- **Magic numbers hardcoded in dashboard**: `magic_buy = 777001`, `magic_sell = 777002`, **`234000` (AI/ICT singles)** — must match `grid_manager.py`. If changed in one place, update all others.
- **`logs/trading_active.lock`** coordinates single-instance. Stale lock prevents dashboard from starting. Only cleaned in `main()` finally block.
- **`logs/grid_state.json`** corruption breaks dashboard. Bot writes, dashboard reads directly. Dashboard **self-heals when state is empty/missing**: computes H4 trend, trap filter, D1 pivot, ATR, and basket PnL live from MT5 and shows STANDBY/WATCHING — never "OFF". If you change bot state keys, update the dashboard's fallbacks (e.g. `min_profit` vs legacy `basket_target_pivot`) in `_update_grid_status`.
- **TP is decoupled from lot size** — `min_p` in `live_trading.py monitor_positions` is fixed USD tiers (`profit_target_usd`, ×0.6 for 4-5 positions, ×0.3 for 6+), NOT `(vol / 0.01) * target_usd`. The old coupled formula silently raises the threshold 5x+ (0.05 lot → $25 instead of $5) and breaks TP exits. Don't "restore" it from git history.
- **Volume-flow gate can block ALL entries** — `grid_manager.update()` hard-blocks on direction mismatch (`flow_dir_ok` AND score ≥ `flow_min_score`). Set `flow_min_score: 0` for direction-only gate, or remove the flow check to disable.
- **Dashboard branding is "NEXUS TRADING SYSTEM"** (window title, header, ticker). Ticker is a fixed RISK DISCLAIMER loop (wrapped via `text * 3` + `tkfont` measure cycle in `_scroll_ticker` — don't shrink the reset threshold or it jumps mid-loop).
- **Stop loss OFF by default** (`use_stop_loss: false`). Bot relies on martingale/DCA recovery. When SL is off, lot is capped to `base_lot`.
- **Circuit breaker is separate from SL** — closes everything when floating loss exceeds `circuit_breaker_loss_pct` (5% equity).
- **No tests, no linter, no CI** — verify changes manually by running the bot or backtester.
- **Files are UTF-8 encoded** — emoji in log strings used to be mojibake (`âš`); that's been fixed. Don't rewrite files in `latin-1`/`cp1252` or the emoji corruption returns. When in doubt, use Python file I/O with `encoding='utf-8'`.
- **`market_intelligence/` and `computer_vision_analyzer.py` are stubs** — don't import or modify expecting functionality. They return empty data and have `enabled = False`.
- **`models/` directory is empty** — `models/*.json` is gitignored. No ML model files exist.
- **`g-channel.pine`** (TradingView PineScript v6) is at root — this is the indicator the bot reads from. Not executable by the bot directly; manual chart attachment required.

## Conventions

- `snake_case` functions/variables, `PascalCase` classes
- `loguru` for all logging (not stdlib `logging`). Daily file rotation to `logs/`.
- Broad `try/except Exception` blocks everywhere (existing pattern — don't narrow without reason)
- Comments mix English and Hindi/Urdu (Roman script)
- Type hints used partially (`Dict`, `List`, `Optional` from `typing`)
- `asyncio.to_thread()` wraps synchronous HTTP requests (calendar downloads, Discord)
- Config values accessed via `self.config.get('section', {}).get('key', default)` pattern throughout
- `trading_engine/__init__.py` present — package is importable as `trading_engine.*`
- `numpy<2.4.0` constraint in requirements.txt — do not upgrade numpy past 2.4.0 without testing
