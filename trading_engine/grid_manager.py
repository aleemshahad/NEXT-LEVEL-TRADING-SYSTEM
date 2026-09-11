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
        self.max_total_exposure = float(grid_config.get("max_total_exposure", 0.10))
        self.lot_growth = float(grid_config.get("lot_growth", 1.3))
        self.max_order_lot = float(grid_config.get("max_order_lot", 0.10))

        # Fibonacci-Anchored DCA Engine (fully replaces legacy ATR / fixed-pip spacing)
        fib_cfg = (config or {}).get("fib_dca", {})
        self.fib_enabled = bool(fib_cfg.get("enabled", True))
        self.fib_lookback_bars = int(fib_cfg.get("lookback_bars", 40))
        self.fib_max_open_layers = int(fib_cfg.get("max_open_layers", 3))
        self.fib_proximity_tolerance = float(fib_cfg.get("proximity_tolerance", 0.40))
        self.fib_body_ratio_limit = float(fib_cfg.get("body_ratio_limit", 0.70))
        self.fib_wick_ratio_min = float(fib_cfg.get("wick_ratio_min", 0.20))
        self.fib_freeze_on_flip = bool(fib_cfg.get("freeze_on_gchannel_flip", True))

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
        self._last_dca_log: Dict[str, float] = {}
        self._last_collision_log: Dict[str, float] = {}
        self.last_pivots: Dict[str, dict] = {}
        self.last_flow: Dict[str, dict] = {}
        self.grid_frozen: Dict[str, str] = {}

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
            with open(self.state_file, "w", encoding="utf-8") as f:
                json.dump(self.active_grids, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save grid state: {e}")

    def _load_state(self) -> None:
        try:
            if self.state_file.exists() and self.state_file.stat().st_size > 0:
                with open(self.state_file, "r", encoding="utf-8") as f:
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

    # ------------------------------------------------------------------
    # Structural Fibonacci-Anchored DCA Engine
    # ------------------------------------------------------------------
    FIB_RATIOS = {1: 0.50, 2: 0.618, 3: 0.786}   # DCA1 = 50%, DCA2 = Golden Pocket, DCA3 = Deep Value

    def _get_m15_closed_df(self, symbol: str):
        """Fetch the last N closed M15 bars for swing detection (excludes forming candle)."""
        try:
            rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M15, 0, self.fib_lookback_bars + 5)
            if rates is None or len(rates) < self.fib_lookback_bars:
                return None
            return pd.DataFrame(rates[:-1])  # drop the still-forming candle
        except Exception as e:
            logger.debug(f"M15 fetch failed for {symbol}: {e}")
            return None

    def _get_m1_closed_df(self, symbol: str):
        """Fetch the last closed M1 candle + buffer for the deceleration filter."""
        try:
            rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M1, 0, 5)
            if rates is None or len(rates) < 2:
                return None
            return pd.DataFrame(rates[:-1])
        except Exception as e:
            logger.debug(f"M1 fetch failed for {symbol}: {e}")
            return None

    def _get_swing_range(self, m15_df) -> Dict:
        """Detect the active impulsive swing from closed M15 bars."""
        try:
            if m15_df is None or len(m15_df) < 2:
                return {}
            window = m15_df.tail(self.fib_lookback_bars)
            swing_high = float(window["high"].max())
            swing_low = float(window["low"].min())
            swing_range = swing_high - swing_low
            if swing_range <= 0:
                return {}
            return {
                "swing_high": swing_high,
                "swing_low": swing_low,
                "swing_range": swing_range,
            }
        except Exception as e:
            logger.debug(f"Swing calc failed: {e}")
            return {}

    def get_fibonacci_dca_level(self, direction: str, layer: int, m15_df) -> Optional[Dict]:
        """Calculate the exact Fibonacci DCA target price for a layer.

        Returns None when the layer has no defined ratio (Layer 4+ = invalidated).
        For BUY:  target = swing_high - swing_range * ratio
        For SELL: target = swing_low + swing_range * ratio
        """
        try:
            ratio = self.FIB_RATIOS.get(layer)
            if ratio is None:
                return None  # no blind layers beyond the defined structure
            swing = self._get_swing_range(m15_df)
            if not swing:
                return None
            factor = swing["swing_range"] * ratio
            if direction == "BUY":
                target = swing["swing_high"] - factor
            else:
                target = swing["swing_low"] + factor
            return {
                "target": float(target),
                "ratio": ratio,
                "layer": layer,
                "swing_high": swing["swing_high"],
                "swing_low": swing["swing_low"],
            }
        except Exception as e:
            logger.debug(f"Fib DCA level calc failed: {e}")
            return None

    def is_m1_rejection_confirmed(self, direction: str, m1_df) -> bool:
        """Candle deceleration / knife filter on the latest closed M1 candle.

        - A candle whose body is > fib_body_ratio_limit AGAINST the position
          (i.e. bearish body for a BUY DCA, bullish body for a SELL DCA) blocks the fire.
        - BUY DCA requires a bottom wick >= fib_wick_ratio_min of the M1 range (buyer defense).
        - SELL DCA requires a top wick >= fib_wick_ratio_min of the M1 range (seller rejection).
        """
        try:
            if m1_df is None or len(m1_df) < 1:
                return False  # no data -> do not fire
            bar = m1_df.iloc[-1]
            o, h, l, c = float(bar["open"]), float(bar["high"]), float(bar["low"]), float(bar["close"])
            rng = h - l
            if rng <= 0:
                return False
            body = abs(c - o)
            body_ratio = body / rng
            bottom_wick = (min(o, c) - l) / rng
            top_wick = (h - max(o, c)) / rng

            if direction == "BUY":
                # Bearish momentum candle > 70% body = falling knife -> wait
                if c < o and body_ratio > self.fib_body_ratio_limit:
                    return False
                return bottom_wick >= self.fib_wick_ratio_min  # buyer defense
            else:
                # Bullish momentum candle > 70% body = no seller rejection yet -> wait
                if c > o and body_ratio > self.fib_body_ratio_limit:
                    return False
                return top_wick >= self.fib_wick_ratio_min  # seller rejection
        except Exception as e:
            logger.debug(f"M1 rejection check failed: {e}")
            return False

    async def _try_place_dca_layer(self, symbol: str, active_type: str, current_price: float,
                                    atr: float, now_t: float, magic: int,
                                    active_pos: list, grid_vol: float):
        """Attempt to place a pending-limit DCA layer at the next Fibonacci target."""
        if not self.fib_enabled:
            self._save_state()
            return

        m15_df = self._get_m15_closed_df(symbol)
        m1_df = self._get_m1_closed_df(symbol)

        next_layer = max(1, len(active_pos))
        if next_layer > self.fib_max_open_layers:
            logger.info(
                f"⛔ [DCA] {symbol} Layer {next_layer} >= max_open_layers {self.fib_max_open_layers} — no further averaging."
            )
            self._save_state()
            return

        fib = self.get_fibonacci_dca_level(active_type, next_layer, m15_df)
        if fib is None:
            logger.info(
                f"⛔ [DCA] {symbol} Layer {next_layer} has no defined fib ratio (Layer 4+ invalidated) — no blind layers."
            )
            self._save_state()
            return

        # Price-tap convergence: within tolerance zone of the fib target
        proximity_ok = (active_type == "BUY" and fib["target"] - self.fib_proximity_tolerance <= current_price <= fib["target"]) or \
                       (active_type == "SELL" and fib["target"] <= current_price <= fib["target"] + self.fib_proximity_tolerance)
        rejection_ok = self.is_m1_rejection_confirmed(active_type, m1_df)
        condition_met = bool(proximity_ok and rejection_ok)

        _dca_log_key = f"{symbol}_dca"
        if now_t - self._last_dca_log.get(_dca_log_key, 0) > 30:
            logger.info(
                f"DCA Layer {next_layer} target: {fib['target']:.2f} (Fib: {fib['ratio']}). "
                f"Current Price: {current_price:.2f} -> Condition Met: {condition_met}"
            )
            self._last_dca_log[_dca_log_key] = now_t

        if condition_met:
            lot_size = self._calculate_martingale_lot(next_layer, atr)
            if grid_vol + lot_size <= self.max_total_exposure:
                res = await self.broker.place_order(
                    symbol=symbol, action=active_type, volume=lot_size,
                    price=fib["target"], use_limit=True, magic=magic
                )
                if res.get("success"):
                    self.active_grids[symbol]["last_index"] = next_layer
                    logger.info(
                        f"⚡ [DCA] Pending Layer {next_layer} {active_type} @ {fib['target']:.2f} "
                        f"(Fib {fib['ratio']}, proximity trigger on current price {current_price:.2f})"
                    )
                else:
                    logger.warning(f"⚠️ [DCA] Layer {next_layer} order failed: {res.get('error')}")
            else:
                logger.info(f"⛔ [DCA] {symbol} exposure cap {self.max_total_exposure} reached — skip Layer {next_layer}")

        self._save_state()

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
                # Full series (incl. forming candle) kept for volume flow
                df = pd.DataFrame(rates)

                # Use only CLOSED bars for ATR + G-Channel bands so the level
                # set freezes per candle instead of swimming with the forming
                # bar's live high/low (root cause of pending order churn).
                df_closed = pd.DataFrame(rates[:-1])
                df_closed["tr"] = np.maximum(
                    df_closed["high"] - df_closed["low"],
                    np.maximum(
                        abs(df_closed["high"] - df_closed["close"].shift(1)),
                        abs(df_closed["low"] - df_closed["close"].shift(1)),
                    ),
                )
                atr = float(df_closed["tr"].rolling(14).mean().iloc[-1])

                df_closed = self._add_gchannel_indicators(df_closed)
                curr = df_closed.iloc[-1]
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

            grid_only_positions = [
                p for p in symbol_positions
                if p.get("magic") in (self.magic_buy, self.magic_sell)
            ]
            ict_positions = [
                p for p in symbol_positions if p.get("magic") == self.ai_magic
            ]

            all_pendings = mt5.orders_get(symbol=symbol) or []
            grid_pendings = [o for o in all_pendings if o.magic in [self.magic_buy, self.magic_sell]]

            grid_open_vol = sum(p["volume"] for p in grid_only_positions)
            total_exposure = self._get_active_exposure(symbol_positions, grid_pendings)
            total_grid_pnl = sum(p["profit"] + p.get("swap", 0.0) for p in symbol_positions)

            # Periodic Status Logging
            now_t = time.time()
            if now_t - self._last_grid_log.get(f"{symbol}_pnl", 0) > 60:
                logger.info(
                    f"📊 [Grid Status] {symbol} | Open Vol: {grid_open_vol:.2f} | Total Exp: {total_exposure:.2f}/{self.max_total_exposure:.2f} | PnL: ${total_grid_pnl:.2f}"
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

                # Hybrid Collision Lock: no new Grid basket while ICT holds exposure
                if ict_positions and not grid_only_positions:
                    if now_t - self._last_collision_log.get(f"{symbol}_grid", 0) > 30:
                        logger.info(
                            f"🛡️ Hybrid Collision Prevented: Skipping Grid entry because ICT has active exposure "
                            f"({len(ict_positions)} ICT position(s) on {symbol})."
                        )
                        self._last_collision_log[f"{symbol}_grid"] = now_t
                    self._save_state()
                    return

                # 1. Initial Basket Entry
                if not grid_only_positions and not grid_pendings:
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

                    # Check Exposure Limit (open position volume only)
                    if grid_open_vol >= self.max_total_exposure:
                        if pendings:
                            self.broker.cancel_all_pendings(symbol)
                        return

                    # D1 pivots still published for the shared dashboard state bridge
                    self.last_pivots[symbol] = self._get_daily_pivots(symbol)

                    m15_df = self._get_m15_closed_df(symbol)

                    # M15 G-Channel flip guard -> FROZEN (no averaging into a flipped structure)
                    frozen = False
                    if self.fib_freeze_on_flip and m15_df is not None and len(m15_df) >= 20:
                        try:
                            m15_ctx = self._add_gchannel_indicators(m15_df.copy())
                            m15_bull = bool(m15_ctx["gchannel_bullish"].iloc[-1])
                            frozen = (active_type == "BUY" and not m15_bull) or (active_type == "SELL" and m15_bull)
                        except Exception as e:
                            logger.debug(f"M15 flip check failed for {symbol}: {e}")

                    if frozen:
                        self.grid_frozen[symbol] = "FROZEN"
                        logger.info(
                            f"🧊 [FROZEN] {symbol} M15 G-Channel flipped against {active_type} basket — no averaging."
                        )
                        self._save_state()
                    else:
                        self.grid_frozen.pop(symbol, None)
                        # Structural invalidation: price beyond 100% of the swing -> freeze DCA layers
                        swing = self._get_swing_range(m15_df)
                        if swing:
                            if (active_type == "BUY" and current_price < swing["swing_low"]) or \
                               (active_type == "SELL" and current_price > swing["swing_high"]):
                                self.grid_frozen[symbol] = "FROZEN"
                                logger.info(
                                    f"🧊 [FROZEN] {symbol} price {current_price:.2f} broke the 100% swing "
                                    f"({'swing_low' if active_type == 'BUY' else 'swing_high'}) — no blind layers."
                                )
                                self._save_state()
                            else:
                                await self._try_place_dca_layer(
                                    symbol, active_type, current_price, atr, now_t, magic,
                                    active_pos, grid_open_vol
                                )
                return

            # -------------------------------------------------------------
            # Strategy B: Standard Grid / Bias DCA
            # -------------------------------------------------------------
            pivot = (hl_high + hl_low) / 2.0 if hl_high > 0 else current_price

            # Hybrid Collision Lock: no new Grid basket while ICT holds exposure
            if ict_positions and not grid_only_positions:
                if now_t - self._last_collision_log.get(f"{symbol}_grid", 0) > 30:
                    logger.info(
                        f"🛡️ Hybrid Collision Prevented: Skipping Grid entry because ICT has active exposure "
                        f"({len(ict_positions)} ICT position(s) on {symbol})."
                    )
                    self._last_collision_log[f"{symbol}_grid"] = now_t
                self._save_state()
                return

            if not grid_only_positions and not grid_pendings:
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

                if grid_open_vol >= self.max_total_exposure:
                    if pendings:
                        self.broker.cancel_all_pendings(symbol)
                    return

                await self._try_place_dca_layer(
                    symbol, active_type, current_price, atr, now_t, magic,
                    active_pos, grid_open_vol
                )

        except Exception as e:
            logger.error(f"Grid update error on {symbol}: {e}", exc_info=True)