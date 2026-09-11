# AGENTS.md

## What This Is

Python MetaTrader 5 algo-trading bot (Windows-only). No package manager, no tests, no linter, no CI. Runs directly from root directory.

## How to Run

```powershell
pip install -r requirements.txt          # Core deps (MetaTrader5, pandas, numpy, loguru, PyYAML, etc.)
pip install -r ict_requirements.txt      # Optional: opencv, scipy, TA-Lib

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
  grid_manager.py        G-Channel grid, DCA, D1 pivots, volume flow filter
  trading_brain.py       AI decision engine (3 entry plans), G-Channel indicators, news gating
  risk.py                Daily loss/drawdown tracking, asset-class-aware position sizing
  notifications.py       Discord webhook alerts
  security.py            HWID license (always authorized — effectively disabled)
live_dashboard.py        1420-line Tkinter GUI — reads logs/grid_state.json for shared state
backtesting.py           Standalone backtester (ICT/SMC + Grid modes) with Plotly charts
market_intelligence/     STUBS — sentiment_intelligence.py and data_acquisition.py are empty
computer_vision_analyzer.py  STUB — not imported or used anywhere
```

Entry flow: `main()` -> SecurityManager -> select_trade_setup -> LiveTradingSystem -> launch_dashboard(subprocess) -> asyncio.run(ts.run())

## Config

- **`config.yaml`** — All trading parameters. Hot-reloaded every cycle (file mtime check via `_reload_settings()`).
- **`.env`** — MT5 credentials: `MT5_LOGIN`, `MT5_PASSWORD`, `MT5_SERVER`, `MT5_TERMINAL_PATH`, `DISCORD_WEBHOOK_URL`
- Grid state persists to `logs/grid_state.json` (bridge between bot and dashboard).
- **Code changes to `trading_engine/` require a full restart** — only `config.yaml` is hot-reloaded.

## Gotchas

- **Windows-only**: MetaTrader5 package, `subprocess.Popen` with Windows creation flags, hardcoded `C:\Program Files\MetaTrader 5\terminal64.exe` path in dashboard.
- **Mixed async/sync**: `broker.py` has some `async def` methods and some regular `def` — grid_manager calls both via `await` and direct calls.
- **Magic numbers hardcoded in dashboard**: `magic_buy = 777001`, `magic_sell = 777002` — must match `grid_manager.py`. If changed in one place, update the other.
- **`logs/trading_active.lock`** coordinates single-instance. Stale lock prevents dashboard from starting. Only cleaned in `main()` finally block.
- **`logs/grid_state.json`** corruption breaks dashboard. Bot writes, dashboard reads directly. Dashboard **self-heals when state is empty/missing**: computes H4 trend, trap filter, D1 pivot, ATR, and basket PnL live from MT5 and shows STANDBY/WATCHING — never "OFF". If you change bot state keys, update the dashboard's fallbacks (e.g. `min_profit` vs legacy `basket_target_pivot`) in `_update_grid_status`.
- **TP is decoupled from lot size** — `min_p` in `live_trading.py monitor_positions` is fixed USD tiers (`profit_target_usd`, ×0.6 for 4-5 positions, ×0.3 for 6+), NOT `(vol / 0.01) * target_usd`. The old coupled formula silently raises the threshold 5x+ (0.05 lot → $25 instead of $5) and breaks TP exits. Don't "restore" it from git history.
- **Volume-flow gate can block ALL entries** — `grid_manager.update()` hard-blocks on direction mismatch (`flow_dir_ok` AND score ≥ `flow_min_score`). Set `flow_min_score: 0` for direction-only gate, or remove the flow check to disable.
- **Dashboard branding is "NEXUS AUTOMATION"** (window title, header). Ticker is a fixed RISK DISCLAIMER loop (wrapped via `text * 3` + `tkfont` measure cycle in `_scroll_ticker` — don't shrink the reset threshold or it jumps mid-loop).
- **Stop loss OFF by default** (`use_stop_loss: false`). Bot relies on martingale/DCA recovery. When SL is off, lot is capped to `base_lot`.
- **Circuit breaker is separate from SL** — closes everything when floating loss exceeds `circuit_breaker_loss_pct` (5% equity).
- **No tests, no linter, no CI** — verify changes manually by running the bot or backtester.
- **Files are UTF-8 encoded** — emoji in log strings used to be mojibake (`âš`); that's been fixed. Don't rewrite files in `latin-1`/`cp1252` or the emoji corruption returns. When in doubt, use Python file I/O with `encoding='utf-8'`.
- **`market_intelligence/` and `computer_vision_analyzer.py` are stubs** — don't import or modify expecting functionality. They return empty data and have `enabled = False`.

## Conventions

- `snake_case` functions/variables, `PascalCase` classes
- `loguru` for all logging (not stdlib `logging`). Daily file rotation to `logs/`.
- Broad `try/except Exception` blocks everywhere (existing pattern — don't narrow without reason)
- Comments mix English and Hindi/Urdu (Roman script)
- Type hints used partially (`Dict`, `List`, `Optional` from `typing`)
- `asyncio.to_thread()` wraps synchronous HTTP requests (calendar downloads, Discord)
- Config values accessed via `self.config.get('section', {}).get('key', default)` pattern throughout
