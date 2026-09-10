# 📈 Next Level Trading System - Strategy Analysis (G-Channel)

**Strategy Type:** Indicator-Based Trend Grid
**Core Logic:** Uses the custom "G-Channel" PineScript indicator to align with the daily trend before deploying a grid.

## ⚙️ How it Works:
* **Direction:** Bi-directional, but filtered by the G-Channel trend.
* **Entry Logic:** The bot reads the G-Channel indicator. If the channel is green (bullish), it only deploys BUY grids. If red (bearish), it only deploys SELL grids.
* **Grid Mechanics:** Fixed lot size (0.05) with 0.6 ATR spacing.
* **Risk Parameters:** Stop loss is explicitly turned `false`. 50% Max drawdown. 

## 🏆 Long-Term Viability: **Fair (5/10)**
**Verdict:** Aligning a grid with a trend indicator is a classic retail strategy. It performs much better than a blind bi-directional grid (like v3.0) because it doesn't fight the trend. However, indicators always lag. By the time the G-Channel flips, the price might have already retraced deeply, putting the grid in heavy drawdown. Without a strict Stop Loss, it remains vulnerable to black-swan events.

---

## 🚀 Improvements Applied (v2.1)

1. **Deeper DCA recovery grid** — beyond the dynamic `hl_low`/`buy_level` (and `hl_high`/`sell_level`) entries, the grid now also deploys **dollar-floor recovery levels** (`grid.level_distances_usd: [15,30,50,70,100]`) below/above the basket base, so a deep retrace still recovers instead of just waiting.
   * Floors auto-scale via `grid.floor_reference_price` (4400) — on BTC/weekend mode a "15$" floor becomes ~200$ to stay sensible.
   * Near-duplicate levels are pruned (min separation ≈ 0.4 × ATR).
2. **Moderate lot growth** (`grid.lot_growth: 1.3`) — levels were all flat 0.05 before; now they scale 0.05 → 0.07 → 0.08 → 0.10 (capped by `grid.max_order_lot`, still bounded by `grid.max_total_exposure: 0.20`).
3. **Exposure-cap overshoot fix** — the level-placement loops now track committed volume (incl. just-placed pendings), so the cap can't be silently overshot within one cycle.
4. **Circuit breaker (emergency protection)** — `risk.circuit_breaker_loss_pct: 5.0`: if equity floating loss hits 5%, the bot **closes everything, cancels pendings, and pauses 120 min** (`circuit_breaker_cooldown_min`). Martingale/DCA fully recovers in normal ranges — this only fires on the rare trend/spike case.
5. **Risk gating on the grid path** — `risk_manager.check_risk_limits` (daily-loss / drawdown) now gates **grid deployment**, not just AI single orders. `update_daily_pnl` is wired into the 1s loop.
6. **Bug fixes** — missing `import time` in broker (bot couldn't connect), removed hard `aiohttp` dependency (now `requests` in a thread), heartbeat `except: pass` logged.
