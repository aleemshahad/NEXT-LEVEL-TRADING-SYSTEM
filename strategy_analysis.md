# 📈 Next Level Trading System - Strategy Analysis (G-Channel)

**Strategy Type:** Indicator-Based Trend Grid
**Core Logic:** Uses the custom "G-Channel" PineScript indicator to align with the daily trend before deploying a grid.

## ⚙️ How it Works:
* **Direction:** Bi-directional, but filtered by the G-Channel trend.
* **Entry Logic:** The bot reads the G-Channel indicator. If the channel is green (bullish), it only deploys BUY grids. If red (bearish), it only deploys SELL grids.
* **Grid Mechanics:** Base lot 0.05 with 1.3× martingale growth per DCA level, 0.6 ATR spacing, capped by `max_order_lot`/`max_total_exposure`.
* **Risk Parameters:** Stop loss is explicitly turned `false`. 50% Max drawdown. Circuit breaker at 5% floating loss (closes all + pauses 120 min). 

## 🏆 Long-Term Viability: **Fair (5/10)**
**Verdict:** Aligning a grid with a trend indicator is a classic retail strategy. It performs much better than a blind bi-directional grid (like v3.0) because it doesn't fight the trend. However, indicators always lag. By the time the G-Channel flips, the price might have already retraced deeply, putting the grid in heavy drawdown. Without a strict Stop Loss, it remains vulnerable to black-swan events.

---

## 🚀 Improvements Applied (v2.1)

1. **Deeper DCA recovery grid** — beyond the dynamic `hl_low`/`buy_level` (and `hl_high`/`sell_level`) entries, the grid now also deploys **dollar-floor recovery levels** (`grid.level_distances_usd: [15,30,50,70,100]`) below/above the basket base, so a deep retrace still recovers instead of just waiting.
   * Floors auto-scale via `grid.floor_reference_price` (4400) — on BTC/weekend mode a "15$" floor becomes ~200$ to stay sensible.
   * Near-duplicate levels are pruned (min separation ≈ 0.4 × ATR).
2. **Moderate lot growth** (`grid.lot_growth: 1.3`) — levels were all flat 0.05 before; now they scale martingale-style (0.05 → 0.07 → 0.09 → 0.11 → 0.14 → 0.19…), capped by `grid.max_order_lot: 0.20` and the basket-wide `grid.max_total_exposure: 0.20`.
3. **Exposure-cap overshoot fix** — the level-placement loops now track committed volume (incl. just-placed pendings), so the cap can't be silently overshot within one cycle.
4. **Circuit breaker (emergency protection)** — `risk.circuit_breaker_loss_pct: 5.0`: if equity floating loss hits 5%, the bot **closes everything, cancels pendings, and pauses 120 min** (`circuit_breaker_cooldown_min`). Martingale/DCA fully recovers in normal ranges — this only fires on the rare trend/spike case.
5. **Risk gating on the grid path** — `risk_manager.check_risk_limits` (daily-loss / drawdown) now gates **grid deployment**, not just AI single orders. `update_daily_pnl` is wired into the 1s loop.
6. **Bug fixes** — missing `import time` in broker (bot couldn't connect), removed hard `aiohttp` dependency (now `requests` in a thread), heartbeat `except: pass` logged.

---

## 🚀 Improvements Applied (v2.2 — Current)

1. **TP decoupled from lot size** — basket profit target (`min_p` in `live_trading.py`) was previously scaled by total committed volume `(vol/0.01) × profit_target_usd`, so increasing `lot_size` silently raised the TP. Now the basket closes at a **fixed dollar target** = `grid.profit_target_usd` (5 USD), hit by count + ATR distance (`target_p`) or dollar PnL. Only the position-count tier scales it: ≤3 positions = 100%, 4–5 = 60%, 6+ = 30%. Changing `lot_size` no longer changes the TP.
2. **Pending-order churn eliminated** (`grid_manager.py` reconciliation) — three root causes fixed:
   - **Closed-candle G-Channel + ATR**: bands (`hl_low`, `buy_level`, `hl_high`, `sell_level`) and ATR now come from `rates[:-1]` (last *closed* candle) instead of the live forming bar, so the recommended level set freezes per candle instead of swimming with every tick.
   - **Price-scale anchored to basket base**: `price_scale = base_price / floor_reference_price` (was `current_price / …`) — dollar-floor levels are now static for the life of a basket rather than drifting with live price.
   - **Level-boundary hysteresis**: levels stay valid while price is within `± atr × 0.5` of the boundary, so a buy-limit hovering exactly at market no longer flips on/off every cycle (the previous remove→re-place → replace loop every 1s).
   - Result: pending orders are only added/removed on real structure changes (new candle close, D1 pivot rollover, exposure cap), not every second.
3. **Phantom grid-state entry removed** (`live_trading.py`) — metadata updates no longer insert a fake `{type:'NEUTRAL'}` entry into `active_grids` every cycle; stopped the "Resetting state" log spam and per-cycle `grid_state.json` writes. Grid state is now only written when grid_manager actually owns the symbol.
