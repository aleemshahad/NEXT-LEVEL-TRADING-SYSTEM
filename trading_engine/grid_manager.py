import time
import json
import pandas as pd
import numpy as np
import MetaTrader5 as mt5
from pathlib import Path
from loguru import logger
from typing import Dict

class GridManager:
    """Manages User Requested Grid Strategy (Limit Order Grid)"""
    def __init__(self, broker, config: Dict = None):
        self.broker = broker
        grid_config = (config or {}).get('grid', {})
        
        self.magic_buy = 777001
        self.magic_sell = 777002
        self.base_lot = grid_config.get('lot_size', 0.01)
        self.lot_multiplier = 1.6
        self.spacing_multiplier = grid_config.get('spacing', 0.4)
        self.max_dca_levels = 10
        self.max_lot_cap = 5.0
        self.batch_size = 5 # How many levels to pre-place
        self.time_frame_str = "M1"
        self.state_file = Path("logs/grid_state.json")
        self.strategy = "Grid Both"
        self.active_grids = {}
        self._load_state()
        self.mode = grid_config.get('mode', 'BOTH')
        self.trigger_threshold = 2 # Add more orders if pendings drop below this
        
        self.TIMEFRAME_MAP = {
            "M1": mt5.TIMEFRAME_M1, "M3": mt5.TIMEFRAME_M3, "M5": mt5.TIMEFRAME_M5,
            "M15": mt5.TIMEFRAME_M15, "M30": mt5.TIMEFRAME_M30, "H1": mt5.TIMEFRAME_H1,
            "H4": mt5.TIMEFRAME_H4, "D1": mt5.TIMEFRAME_D1
        }

    def _save_state(self):
        try:
            self.state_file.parent.mkdir(exist_ok=True)
            with open(self.state_file, 'w') as f:
                json.dump(self.active_grids, f)
        except Exception as e:
            logger.error(f"Failed to save grid state: {e}")

    def _get_dynamic_multiplier(self, atr: float) -> float:
        if atr > 3.0: return 1.2
        if atr < 1.5: return 1.6
        return 1.4

    def _calculate_martingale_lot(self, index: int, atr: float) -> float:
        multiplier = self._get_dynamic_multiplier(atr)
        lot = self.base_lot * (multiplier ** (index - 1)) if index > 0 else self.base_lot
        # Hard Cap for safety as requested: total grid usually stays under 0.1
        return min(round(lot, 2), 0.05) 

    def _calculate_grid_price(self, base_price: float, index: int, atr: float, direction: str) -> float:
        # User requested more space for larger lots (0.02+)
        # We increase spacing multiplier as index grows
        dynamic_spacing = self.spacing_multiplier
        if index >= 2: dynamic_spacing *= 1.5 # Level 2+ (usually 0.02+) gets 50% more space
        if index >= 5: dynamic_spacing *= 2.0 # Level 5+ gets 100% more space (survival)
        
        spacing = atr * dynamic_spacing
        offset = spacing * index
        return base_price - offset if direction == 'BUY' else base_price + offset

    async def _detect_market_condition(self, symbol):
        try:
            tf = self.TIMEFRAME_MAP.get(self.time_frame_str, mt5.TIMEFRAME_M1)
            rates = mt5.copy_rates_from_pos(symbol, tf, 0, 50)
            if rates is not None and len(rates) >= 40:
                df = pd.DataFrame(rates)
                df['tr'] = np.maximum(df['high'] - df['low'], np.maximum(abs(df['high'] - df['close'].shift(1)), abs(df['low'] - df['close'].shift(1))))
                atr = df['tr'].rolling(14).mean().iloc[-1]
                # High-frequency analysis for price action
                h10 = df['high'].rolling(10).max().iloc[-1]
                l10 = df['low'].rolling(10).min().iloc[-1]
                pivot = (h10 + l10) / 2
                return {'pivot': pivot, 'atr': atr}
            return {'pivot': 0, 'atr': 1.0}
        except: return {'pivot': 0, 'atr': 1.0}

    def _load_state(self):
        try:
            if self.state_file.exists() and self.state_file.stat().st_size > 0:
                with open(self.state_file, 'r') as f:
                    self.active_grids = json.load(f)
            else: self.active_grids = {}
        except: self.active_grids = {}

    async def update(self, symbol, current_price, bias, balance):
        """Update grid logic: ENFORCED 0.1 LOT CAP + DYNAMIC SPACING"""
        if not hasattr(self, '_last_grid_log'): self._last_grid_log = {}
        try:
            data = await self._detect_market_condition(symbol)
            positions = self.broker.get_positions()
            symbol_positions = [p for p in positions if p['symbol'] == symbol]
            
            # Filter for this grid's positions
            buy_positions = [p for p in symbol_positions if p['type'] == 'BUY' and p.get('magic') == self.magic_buy]
            sell_positions = [p for p in symbol_positions if p['type'] == 'SELL' and p.get('magic') == self.magic_sell]
            
            # --- USER SAFETY CAP: Total Lot Exposure <= 0.1 ---
            total_lot_exposure = sum(p['volume'] for p in buy_positions + sell_positions)
            total_grid_profit = sum(p['profit'] + p.get('swap', 0) for p in buy_positions + sell_positions)
            
            now_t = time.time()
            if now_t - self._last_grid_log.get(f"{symbol}_pnl", 0) > 60:
                logger.info(f"📊 [Grid] {symbol} | Vol: {total_lot_exposure:.2f}/0.10 | PnL: ${total_grid_profit:.2f}")
                self._last_grid_log[f"{symbol}_pnl"] = now_t

            pivot = data['pivot']; atr = data.get('atr', 1.0)
            # FIX #4: Check ALL positions for this symbol (includes ICT magic 234000)
            # Previously `has_positions` only checked grid magics — caused conflicting baskets
            has_positions = len(symbol_positions) > 0
            all_pendings = mt5.orders_get(symbol=symbol) or []
            grid_pendings = [o for o in all_pendings if o.magic in [self.magic_buy, self.magic_sell]]
            
            if self.strategy == "Hybrid Mode" or self.strategy == "Grid Both": self.mode = "BOTH"
            elif "BUY ONLY" in self.strategy: self.mode = "BUY_ONLY"
            elif "SELL ONLY" in self.strategy: self.mode = "SELL_ONLY"

            if not has_positions and not grid_pendings:
                # Prioritize ICT Bias for initial entry choice
                grid_type = 'BUY' if bias == "BULLISH" else ('SELL' if bias == "BEARISH" else None)
                
                # Fallback to Pivot if Bias is Neutral
                if not grid_type:
                    grid_type = 'SELL' if current_price > pivot else 'BUY'
                
                # Apply hard mode restrictions if set
                if self.mode != "BOTH":
                    grid_type = 'BUY' if self.mode == "BUY_ONLY" else 'SELL'
                
                logger.info(f"🚀 Starting New {grid_type} Basket | Bias: {bias} | Pivot: {pivot:.2f}")
                magic = self.magic_buy if grid_type == 'BUY' else self.magic_sell
                res = self.broker.place_order(symbol=symbol, action=grid_type, volume=self.base_lot, price=current_price, use_limit=False, magic=magic)
                if res['success']:
                    self.active_grids[symbol] = {'type': grid_type, 'base_price': current_price, 'last_index': 0, 'bias_at_start': bias}
                    self._save_state()
            
            active_type = self.active_grids.get(symbol, {}).get('type')
            if not active_type and has_positions: active_type = 'BUY' if buy_positions else 'SELL'
            
            if active_type:
                magic = self.magic_buy if active_type == 'BUY' else self.magic_sell
                pendings = [o for o in grid_pendings if o.magic == magic]
                active_pos = buy_positions if active_type == 'BUY' else sell_positions
                total_open = len(active_pos)
                
                # --- APPLY USER CAP ON PENDING PLACEMENT ---
                if total_lot_exposure >= 0.10:
                    if pendings: self.broker.cancel_all_pendings(symbol)
                    return # Hard stop for new DCA entries

                batch_limit = 2 # User requested only 2 limit orders at a time
                if len(pendings) < batch_limit and (total_open + len(pendings)) < self.max_dca_levels:
                    base_price = self.active_grids.get(symbol, {}).get('base_price', current_price)
                    start_idx = total_open + len(pendings) + 1
                    
                    order_type = mt5.ORDER_TYPE_BUY_LIMIT if active_type == 'BUY' else mt5.ORDER_TYPE_SELL_LIMIT
                    for i in range(start_idx, min(start_idx + batch_limit, self.max_dca_levels + 1)):
                        entry_price = self.broker.round_price(symbol, self._calculate_grid_price(base_price, i, atr, active_type))
                        lot_size = self._calculate_martingale_lot(i, atr)
                        
                        # Stop if THIS order would cross the 0.1 threshold
                        if total_lot_exposure + lot_size > 0.10: break

                        if any(abs(o.price_open - entry_price) < (atr * 0.05) for o in pendings): continue
                        if (active_type == 'BUY' and entry_price < current_price) or (active_type == 'SELL' and entry_price > current_price):
                            logger.info(f"⏳ [Grid] Level {i} ({lot_size}) for {active_type} at {entry_price:.2f}")
                            await self.broker.place_pending_order(symbol, order_type, lot_size, entry_price, magic)
                    
                    self._save_state()

        except Exception as e: logger.error(f"Grid update error: {e}")
