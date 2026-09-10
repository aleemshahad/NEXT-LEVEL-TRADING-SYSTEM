import asyncio
import json
import time
from pathlib import Path
from typing import Dict, Optional
from loguru import logger
import MetaTrader5 as mt5
import numpy as np
import pandas as pd


class GridManager:
    """Manages Dynamic Limit Order Grid / G-Channel DCA with Strict Lot & Risk Guards."""

    def __init__(self, broker, config: Optional[Dict] = None):
        self.broker = broker
        grid_config = (config or {}).get("grid", {})

        self.magic_buy = int(grid_config.get("magic_buy", 777001))
        self.magic_sell = int(grid_config.get("magic_sell", 777002))
        self.ai_magic = 234000  # AI single orders

        self.base_lot = float(grid_config.get("lot_size", 0.01))
        self.spacing_multiplier = float(grid_config.get("spacing", 0.4))
        self.max_dca_levels = int(grid_config.get("max_dca_levels", 10))
        self.max_total_exposure = float(grid_config.get("max_total_exposure", 0.10))
        self.batch_size = int(grid_config.get("batch_size", 2))
        self.lot_growth = float(grid_config.get("lot_growth", 1.3))
        self.max_order_lot = float(grid_config.get("max_order_lot", 0.10))
        self.recovery_levels = [float(d) for d in grid_config.get("level_distances_usd", [15, 30, 50, 70, 100])]
        self.floor_reference_price = float(grid_config.get("floor_reference_price", 4400.0))
        self.use_d1_pivot = bool(grid_config.get("use_d1_pivot", True))

        self.volume_flow_filter = bool(grid_config.get("volume_flow_filter", True))
        self.flow_surge_threshold = float(grid_config.get("flow_surge_threshold", 1.5))
        self.flow_obv_short = int(grid_config.get("flow_obv_short", 5))
        self.flow_obv_long = int(grid_config.get("flow_obv_long", 20))
        self.flow_min_score = float(grid_config.get("flow_min_score", 0.6))

        self.time_frame_str = grid_config.get("timeframe", "M1")
        self.strategy = grid_config.get("strategy", "Grid Both")
        self.mode = grid_config.get("mode", "BOTH")

        self.state_file = Path("logs/grid_state.json")
        self.active_grids: Dict[str, dict] = {}
        self._last_grid_log: Dict[str, float] = {}
        self.last_pivots: Dict[str, dict] = {}
        self.last_flow: Dict[str, dict] = {}

        self.TIMEFRAME_MAP = {
            "M1": mt5.TIMEFRAME_M1,
            "M3": mt5.TIMEFRAME_M3,
            "M5": mt5.TIMEFRAME_M5,
            "M15": mt5.TIMEFRAME_M15,
            "M30": mt5.TIMEFRAME_M30,
            "H1": mt5.TIMEFRAME_H1,
            "H4": mt5.TIMEFRAME_H4,
            "D1": mt5.TIMEFRAME_D1,
        }

        self._load_state()

    def _save_state(self) -> None:
        try:
            self.state_file.parent.mkdir(parents=True, exist_ok=True)
            for sym in list(self.active_grids.keys()):
                piv = self.last_pivots.get(sym)
                if piv:
                    self.active_grids[sym]["pivots"] = {
                        k: round(float(v), 2) for k, v in piv.items()
                    }
                    self.active_grids[sym]["daily_pivot"] = round(float(piv.get("P", 0.0)), 2)
                flw = self.last_flow.get(sym)
                if flw:
                    self.active_grids[sym]["volume_flow"] = flw
            with open(self.state_file, "w") as f:
                json.dump(self.active_grids, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save grid state: {e}")

    def _load_state(self) -> None:
        try:
            if self.state_file.exists() and self.state_file.stat().st_size > 0:
                with open(self.state_file, "r") as f:
                    self.active_grids = json.load(f)
            else:
                self.active_grids = {}
        except Exception as e:
            logger.warning(f"Could not load state, resetting: {e}")
            self.active_grids = {}

    def _calculate_martingale_lot(self, index: int, atr: float) -> float:
        lot = self.base_lot * (self.lot_growth ** max(0, index - 1)) if index > 0 else self.base_lot
        # Capped individual order size
        return min(round(lot, 2), self.max_order_lot)

    def _calculate_grid_price(self, base_price: float, index: int, atr: float, direction: str) -> float:
        dynamic_spacing = self.spacing_multiplier
        if index >= 2:
            dynamic_spacing *= 1.5
        if index >= 5:
            dynamic_spacing *= 2.0

        spacing = atr * dynamic_spacing
        offset = spacing * index
        return base_price - offset if direction == "BUY" else base_price + offset

    def _add_gchannel_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        if df is None or len(df) < 20:
            return df
        closes = df['close'].values
        if len(closes) == 0:
            return df
        highs = df["high"].values
        lows = df["low"].values

        df["hl_high"] = df["high"].rolling(20).max()
        df["hl_low"] = df["low"].rolling(20).min()
        divided_range = (df["hl_high"] - df["hl_low"]) / 2.6
        df["buy_level"] = df["hl_low"] - divided_range
        df["sell_level"] = df["hl_high"] + divided_range
        df["divided_range"] = divided_range

        # G-Channel Calculation
        gLength = 100
        n = len(closes)
        a = np.zeros(n)
        b = np.zeros(n)
        a[0] = closes[0]
        b[0] = closes[0]

        for i in range(1, n):
            a_prev = a[i - 1]
            b_prev = b[i - 1]
            diff = (a_prev - b_prev) / gLength
            a[i] = max(closes[i], a_prev) - diff
            b[i] = min(closes[i], b_prev) + diff

        df["gchannel_avg"] = (a + b) / 2.0

        crossup = np.zeros(n, dtype=bool)
        crossdn = np.zeros(n, dtype=bool)
        for i in range(1, n):
            crossup[i] = (b[i - 1] < closes[i - 1]) and (b[i] >= closes[i])
            crossdn[i] = (a[i - 1] > closes[i - 1]) and (a[i] <= closes[i])

        last_dn = 999999
        last_up = 999999
        bullish = np.zeros(n, dtype=bool)
        for i in range(n):
            last_dn = 0 if crossdn[i] else last_dn + 1
            last_up = 0 if crossup[i] else last_up + 1
            bullish[i] = last_dn <= last_up

        df["gchannel_bullish"] = bullish
        return df

    def _get_daily_pivots(self, symbol: str) -> Dict:
        """Classic Daily pivot levels from the previous (closed) D1 candle."""
        try:
            rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_D1, 0, 2)
            if rates is None or len(rates) < 2:
                return {}
            prev = rates[-2]
            H = float(prev["high"]); L = float(prev["low"]); C = float(prev["close"])
            P = (H + L + C) / 3.0
            return {
                "P": P,
                "R1": 2 * P - L, "S1": 2 * P - H,
                "R2": P + (H - L), "S2": P - (H - L),
                "R3": H + 2 * (P - L), "S3": L - 2 * (H - P),
            }
        except Exception as e:
            logger.debug(f"Daily pivot calc failed for {symbol}: {e}")
            return {}

    def _compute_volume_flow(self, df: pd.DataFrame):
        """Combined volume-flow filter: OBV trend alignment (60%) + surge conviction (40%)."""
        try:
            if df is None or len(df) < 22 or "tick_volume" not in df.columns:
                return None
            closes = df["close"].values
            vol = df["tick_volume"].values.astype(float)
            n = len(closes)
            obv = np.zeros(n)
            for i in range(1, n):
                if closes[i] > closes[i - 1]:
                    obv[i] = obv[i - 1] + vol[i]
                elif closes[i] < closes[i - 1]:
                    obv[i] = obv[i - 1] - vol[i]
                else:
                    obv[i] = obv[i - 1]
            s = pd.Series(obv)
            obv_short = float(s.rolling(self.flow_obv_short).mean().iloc[-1])
            obv_long = float(s.rolling(self.flow_obv_long).mean().iloc[-1])
            obv_up = obv_short >= obv_long
            recent_vol = vol[-self.flow_obv_long:]
            surge_ratio = float(vol[-1] / (recent_vol[:-1].mean() + 1e-9))
            surge = surge_ratio >= self.flow_surge_threshold
            score = round((0.6 if obv_up else 0.0) + (0.4 if surge else 0.0), 2)
            return {
                "bullish": obv_up,
                "surge": surge,
                "score": score,
                "surge_ratio": round(surge_ratio, 2),
            }
        except Exception as e:
            logger.debug(f"Volume flow calc failed: {e}")
            return None

    def _get_active_exposure(self, symbol_positions: list, pendings: list) -> float:
        """Returns the total volume committed (open positions + active pending limits)."""
        pos_vol = sum(p.get("volume", 0.0) for p in symbol_positions)
        pnd_vol = sum(o.volume_initial for o in pendings)
        return round(pos_vol + pnd_vol, 2)

    async def update(self, symbol: str, current_price: float, bias: str, balance: float):
        """Processes tick update, manages trailing pending orders, and adjusts basket TP."""
        try:
            tf = self.TIMEFRAME_MAP.get(self.time_frame_str, mt5.TIMEFRAME_M5)
            rates = mt5.copy_rates_from_pos(symbol, tf, 0, 150)

            atr = 1.0
            gchannel_bullish = None
            hl_high, hl_low, buy_level, sell_level = 0.0, 0.0, 0.0, 0.0

            if rates is not None and len(rates) >= 50:
                df = pd.DataFrame(rates)
                df["tr"] = np.maximum(
                    df["high"] - df["low"],
                    np.maximum(
                        abs(df["high"] - df["close"].shift(1)),
                        abs(df["low"] - df["close"].shift(1)),
                    ),
                )
                atr = float(df["tr"].rolling(14).mean().iloc[-1])

                df = self._add_gchannel_indicators(df)
                curr = df.iloc[-1]
                gchannel_bullish = bool(curr["gchannel_bullish"])
                hl_high = float(curr["hl_high"])
                hl_low = float(curr["hl_low"])
                buy_level = float(curr["buy_level"])
                sell_level = float(curr["sell_level"])

            # 2. Fetch Open Positions & Filter by Magics
            positions = self.broker.get_positions() or []
            symbol_positions = [
                p for p in positions
                if p["symbol"] == symbol and p.get("magic") in [self.magic_buy, self.magic_sell, self.ai_magic]
            ]

            buy_positions = [p for p in symbol_positions if p["type"] == "BUY"]
            sell_positions = [p for p in symbol_positions if p["type"] == "SELL"]

            all_pendings = mt5.orders_get(symbol=symbol) or []
            grid_pendings = [o for o in all_pendings if o.magic in [self.magic_buy, self.magic_sell]]

            total_open_vol = sum(p["volume"] for p in symbol_positions)
            total_exposure = self._get_active_exposure(symbol_positions, grid_pendings)
            total_grid_pnl = sum(p["profit"] + p.get("swap", 0.0) for p in symbol_positions)

            # Periodic Status Logging
            now_t = time.time()
            if now_t - self._last_grid_log.get(f"{symbol}_pnl", 0) > 60:
                logger.info(
                    f"📊 [Grid Status] {symbol} | Open Vol: {total_open_vol:.2f} | Total Exp: {total_exposure:.2f}/{self.max_total_exposure:.2f} | PnL: ${total_grid_pnl:.2f}"
                )
                self._last_grid_log[f"{symbol}_pnl"] = now_t

            # Reset state if no positions and no pendings remain
            if not symbol_positions and not grid_pendings and symbol in self.active_grids:
                logger.info(f"🧹 [Grid] All trades closed for {symbol}. Resetting state.")
                self.active_grids.pop(symbol, None)
                self._save_state()

            # -------------------------------------------------------------
            # Strategy A: G-Channel Trend / Hybrid DCA Mode
            # -------------------------------------------------------------
            if self.strategy in ["G-Channel Trend", "Hybrid Mode"] and gchannel_bullish is not None:
                # Volume flow computed every cycle (live dashboard display + entry gating)
                flow = self._compute_volume_flow(df) if self.volume_flow_filter else None
                self.last_flow[symbol] = flow or {}

                # 1. Initial Basket Entry
                if not symbol_positions and not grid_pendings:
                    # Volume-flow gate: direction only trades WITH confirmed flow
                    if flow:
                        flow_dir_ok = flow["bullish"] if gchannel_bullish else not flow["bullish"]
                        if not flow_dir_ok or flow["score"] < self.flow_min_score:
                            reason = ("direction mismatch" if not flow_dir_ok else f"low conviction (score {flow['score']:.2f} < {self.flow_min_score:.2f})")
                            logger.info(
                                f"⏳ [Flow Gate] {symbol} G-Channel {'BULLISH' if gchannel_bullish else 'BEARISH'} "
                                f"but volume flow {'BEARISH' if gchannel_bullish else 'BULLISH'} "
                                f"(score {flow['score']:.2f}, surge x{flow['surge_ratio']:.2f}) — blocked: {reason}"
                            )
                            self._save_state()
                            return

                    grid_type = "BUY" if gchannel_bullish else "SELL"
                    magic = self.magic_buy if grid_type == "BUY" else self.magic_sell

                    entry_note = ""
                    if flow:
                        entry_note = f" | Flow: {'BULLISH' if flow['bullish'] else 'BEARISH'} (score {flow['score']:.2f})"
                    logger.info(f"🚀 [G-Channel] Opening Initial {grid_type} order @ {current_price:.2f}{entry_note}")
                    res = self.broker.place_order(
                        symbol=symbol, action=grid_type, volume=self.base_lot,
                        price=current_price, use_limit=False, magic=magic
                    )
                    if res.get("success"):
                        self.active_grids[symbol] = {
                            "type": grid_type,
                            "base_price": current_price,
                            "last_index": 0,
                            "bias_at_start": "BULLISH" if gchannel_bullish else "BEARISH"
                        }
                        self._save_state()
                    return

                active_type = self.active_grids.get(symbol, {}).get("type")
                if not active_type and symbol_positions:
                    active_type = "BUY" if buy_positions else "SELL"

                if active_type:
                    magic = self.magic_buy if active_type == "BUY" else self.magic_sell
                    active_pos = buy_positions if active_type == "BUY" else sell_positions
                    pendings = [o for o in grid_pendings if o.magic == magic]

                    # Synchronize Basket TP
                    target_tp = hl_high if active_type == "BUY" else hl_low
                    for p in active_pos:
                        if abs(p.get("tp", 0.0) - target_tp) > (atr * 0.05) or p.get("sl", 0.0) != 0.0:
                            rounded_tp = self.broker.round_price(symbol, target_tp)
                            self.broker.modify_sl_tp(p["ticket"], sl=0.0, tp=rounded_tp)

                    # Check Exposure Limit (open position volume only, so healthy DCA
                    # pendings are not placed-and-cancelled on every cycle)
                    if total_open_vol >= self.max_total_exposure:
                        if pendings:
                            self.broker.cancel_all_pendings(symbol)
                        return

                    # Trailing Level Calculations (dynamic channel levels + D1 pivots + deeper dollar-floor recovery)
                    dynamic_levels = (
                        [l for l in [hl_low, buy_level] if 0 < l < current_price]
                        if active_type == "BUY"
                        else [l for l in [hl_high, sell_level] if l > 0 and l > current_price]
                    )
                    base_price = self.active_grids.get(symbol, {}).get("base_price", current_price)
                    price_scale = current_price / self.floor_reference_price
                    if price_scale <= 0 or current_price <= 0:
                        price_scale = 1.0
                    if active_type == "BUY":
                        floor_levels = [base_price - d * price_scale for d in self.recovery_levels
                                        if (base_price - d * price_scale) < current_price]
                    else:
                        floor_levels = [base_price + d * price_scale for d in self.recovery_levels
                                        if (base_price + d * price_scale) > current_price]

                    pivots = self._get_daily_pivots(symbol)
                    self.last_pivots[symbol] = pivots
                    if self.use_d1_pivot and pivots:
                        pivot_levels = (
                            [pivots["S1"], pivots["S2"], pivots["S3"]]
                            if active_type == "BUY"
                            else [pivots["R1"], pivots["R2"], pivots["R3"]]
                        )
                        pivot_levels = [p for p in pivot_levels if p > 0]
                    else:
                        pivot_levels = []

                    valid_levels = dynamic_levels + pivot_levels + floor_levels
                    # Deduplicate near-identical levels (min separation ~ 0.4 * ATR)
                    min_sep = max(atr * 0.4, 1.0 * price_scale)
                    unique_levels = []
                    for lvl in sorted(valid_levels, key=lambda x: abs(current_price - x)):
                        if lvl > 0 and all(abs(lvl - e) >= min_sep for e in unique_levels):
                            unique_levels.append(lvl)
                    valid_levels = sorted(unique_levels, key=lambda x: abs(current_price - x))
                    # Keep only the nearest levels that fit under max_dca_levels
                    valid_levels = valid_levels[:max(0, self.max_dca_levels - len(active_pos))]

                    # Incremental reconciliation — only add missing / remove stale pendings.
                    # Healthy levels are NEVER removed+re-placed (eliminates order churn).
                    if (len(active_pos) + len(valid_levels)) <= self.max_dca_levels:
                        tol = max(atr * 0.05, 0.10)
                        order_type = mt5.ORDER_TYPE_BUY_LIMIT if active_type == "BUY" else mt5.ORDER_TYPE_SELL_LIMIT

                        # 1) Remove pendings that no longer match any target level
                        placed_vol = total_open_vol + sum(o.volume_initial for o in pendings)
                        for o in list(pendings):
                            if not any(abs(o.price_open - lvl) <= tol for lvl in valid_levels):
                                mt5.order_send({"action": mt5.TRADE_ACTION_REMOVE, "order": o.ticket})
                                placed_vol -= o.volume_initial

                        # 2) Place missing levels, respecting the exposure cap
                        for idx, lvl in enumerate(valid_levels):
                            lot_size = self._calculate_martingale_lot(len(active_pos) + idx + 1, atr)
                            if any(abs(o.price_open - lvl) <= tol for o in pendings):
                                continue
                            if placed_vol + lot_size > self.max_total_exposure:
                                break
                            rounded_lvl = self.broker.round_price(symbol, lvl)
                            res = await self.broker.place_pending_order(symbol, order_type, lot_size, rounded_lvl, magic)
                            if res.get("success"):
                                placed_vol += lot_size

                    self._save_state()
                return

            # -------------------------------------------------------------
            # Strategy B: Standard Grid / Bias DCA
            # -------------------------------------------------------------
            pivot = (hl_high + hl_low) / 2.0 if hl_high > 0 else current_price

            if not symbol_positions and not grid_pendings:
                grid_type = "BUY" if bias == "BULLISH" else ("SELL" if bias == "BEARISH" else None)
                if not grid_type:
                    grid_type = "SELL" if current_price > pivot else "BUY"

                if self.mode == "BUY_ONLY":
                    grid_type = "BUY"
                elif self.mode == "SELL_ONLY":
                    grid_type = "SELL"

                magic = self.magic_buy if grid_type == "BUY" else self.magic_sell
                logger.info(f"🚀 [Grid] New {grid_type} Basket | Bias: {bias} | Pivot: {pivot:.2f}")

                res = self.broker.place_order(
                    symbol=symbol, action=grid_type, volume=self.base_lot,
                    price=current_price, use_limit=False, magic=magic
                )
                if res.get("success"):
                    self.active_grids[symbol] = {
                        "type": grid_type,
                        "base_price": current_price,
                        "last_index": 0,
                        "bias_at_start": bias
                    }
                    self._save_state()
                return

            active_type = self.active_grids.get(symbol, {}).get("type")
            if not active_type and symbol_positions:
                active_type = "BUY" if buy_positions else "SELL"

            if active_type:
                magic = self.magic_buy if active_type == "BUY" else self.magic_sell
                pendings = [o for o in grid_pendings if o.magic == magic]
                active_pos = buy_positions if active_type == "BUY" else sell_positions

                if total_open_vol >= self.max_total_exposure:
                    if pendings:
                        self.broker.cancel_all_pendings(symbol)
                    return

                if len(pendings) < self.batch_size and (len(active_pos) + len(pendings)) < self.max_dca_levels:
                    base_price = self.active_grids.get(symbol, {}).get("base_price", current_price)
                    start_idx = len(active_pos) + len(pendings) + 1
                    order_type = mt5.ORDER_TYPE_BUY_LIMIT if active_type == "BUY" else mt5.ORDER_TYPE_SELL_LIMIT
                    placed_vol = total_open_vol + sum(o.volume_initial for o in pendings)

                    for i in range(start_idx, min(start_idx + self.batch_size, self.max_dca_levels + 1)):
                        entry_price = self.broker.round_price(symbol, self._calculate_grid_price(base_price, i, atr, active_type))
                        lot_size = self._calculate_martingale_lot(i, atr)

                        # Enforce total exposure ceiling (includes already-placed pendings)
                        if placed_vol + lot_size > self.max_total_exposure:
                            break

                        if any(abs(o.price_open - entry_price) < (atr * 0.05) for o in pendings):
                            continue

                        if (active_type == "BUY" and entry_price < current_price) or (active_type == "SELL" and entry_price > current_price):
                            logger.info(f"⏳ [Grid] Placing Level {i} {active_type} Limit ({lot_size}) @ {entry_price:.2f}")
                            res = await self.broker.place_pending_order(symbol, order_type, lot_size, entry_price, magic)
                            if res.get("success"):
                                placed_vol += lot_size

                    self._save_state()

        except Exception as e:
            logger.error(f"Grid update error on {symbol}: {e}", exc_info=True)