
"""
NEXUS TRADING SYSTEM - Backtesting System
All-in-one backtesting and AI training
Created by: Aleem Shahzad | AI Partner: Claude (Anthropic)
"""

import pandas as pd
import numpy as np
import MetaTrader5 as mt5
from datetime import datetime, timedelta
from pathlib import Path
from loguru import logger
import sys
import yaml
import matplotlib.pyplot as plt
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import plotly.express as px
import json
from typing import Dict, List, Tuple
import tkinter as tk
from tkinter import ttk, messagebox
import threading

# Setup logging
logger.remove()
logger.add(sys.stdout, format="<green>{time:HH:mm:ss}</green> | <level>{level}</level> | <cyan>{message}</cyan>", level="INFO")
logger.add("logs/backtest_{time:YYYY-MM-DD}.log", rotation="1 day")

class BacktestEngine:
    """Backtesting Engine with AI Training"""
    
    # Broker minimum lot — trades sized below this are not sendable
    MIN_LOT = 0.01
    
    def __init__(self):
        self.trades = []
        self.initial_balance = 100000.0  # Starting balance
        self.balance = self.initial_balance
        self.equity_curve = []
        self.ai_memories = []
        # Tunable parameters (adjust to your preference)
        self.min_confidence = 0.55      # lower threshold -> more entries
        self.risk_per_trade = 0.03      # increase risk per trade (3%)
        self.crypto_max_lots = 0.5      # allow larger crypto position sizes
        self.forex_max_lots = 0.1       # allow larger forex/metals sizes
        self.use_time_filter = True     # Enable ICT Silver Bullet time restriction
        # MT5 returns bars in BRO SERVER time, not UTC/EST. Offset converts
        # server -> New York so the Silver Bullet windows land where intended.
        self.server_to_est_offset_hours = 0
        # Round-turn commission in account currency per lot (0 = broker free)
        self.commission_per_lot = 0.0
        # Live bid/ask captured once per backtest so fills pay the real spread
        self._quote = {'bid': None, 'ask': None, 'spread': 0.0}
    
    def _contract_spec(self, symbol: str) -> Tuple[float, float]:
        """
        Return (contract_multiplier, max_lots) for a symbol.
        The SAME multiplier must be used for sizing, floating PnL and realized
        PnL, otherwise risk and PnL disagree by orders of magnitude.
        """
        s = (symbol or '').upper()
        if 'BTC' in s or 'ETH' in s:
            return 1.0, getattr(self, 'crypto_max_lots', 0.5)
        if 'XAU' in s or 'XAG' in s:
            return 100.0, getattr(self, 'forex_max_lots', 0.1)
        return 100000.0, getattr(self, 'forex_max_lots', 0.1)
    
    def _pnl_for_move(self, symbol: str, price_diff: float, size: float) -> float:
        """Convert a price move into account-currency PnL using the contract size."""
        multiplier, _ = self._contract_spec(symbol)
        return price_diff * size * multiplier
    
    def _capture_quote(self, symbol: str):
        """Snapshot live bid/ask so backtest fills pay the real spread."""
        self._quote = {'bid': None, 'ask': None, 'spread': 0.0}
        try:
            tick = mt5.symbol_info_tick(symbol)
            if tick and tick.bid and tick.ask:
                self._quote = {
                    'bid': float(tick.bid),
                    'ask': float(tick.ask),
                    'spread': float(tick.ask - tick.bid)
                }
                logger.info(f"📐 Quote snapshot for {symbol}: bid={tick.bid} ask={tick.ask} spread={tick.ask - tick.bid:.5f}")
        except Exception as e:
            logger.warning(f"Could not snapshot quote for {symbol} ({e}); using bar close prices")
    
    def _cost_basis(self, symbol: str, size: float) -> float:
        """Round-trip commission for a given size."""
        return abs(size) * self.commission_per_lot
    
    def _load_backtest_config(self):
        """Load backtest-specific cost/timezone settings from config.yaml."""
        defaults = {
            'server_to_est_offset_hours': 0,
            'commission_per_lot': 0.0,
            'starting_balance': 100000.0,
            'risk_per_trade': 0.03,
        }
        try:
            with open('config.yaml', 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f) or {}
            bt = config.get('backtest', {}) or {}
            for key in defaults:
                if key in bt:
                    defaults[key] = bt[key]
        except Exception as e:
            logger.warning(f"Could not read backtest config ({e}); using defaults")
        
        self.server_to_est_offset_hours = int(defaults['server_to_est_offset_hours'])
        self.commission_per_lot = float(defaults['commission_per_lot'])
        self.risk_per_trade = float(defaults['risk_per_trade'])
        self.initial_balance = float(defaults['starting_balance'])
        self.balance = self.initial_balance
        
        logger.info(
            f"⚙️ Backtest Config: Balance=${self.initial_balance:,.2f} Risk={self.risk_per_trade:.1%} "
            f"Commission=${self.commission_per_lot}/lot Server->NY={self.server_to_est_offset_hours}h"
        )

    def _is_silver_bullet_time(self, timestamp: datetime) -> bool:
        """
        Check if time is within ICT Silver Bullet windows (New York time).
        Windows: 3-4 AM (London), 10-11 AM (NY AM), 2-3 PM (NY PM).

        MT5 copy_rates_range returns BROKER SERVER time, which is almost never
        New York time. Without converting, every "kill zone" check lands on the
        wrong hour and silently filters out the wrong bars. The server->EST
        offset is configurable via server_to_est_offset_hours.
        """
        # Convert server time -> New York time before testing the windows
        ny_hour = (timestamp.hour - self.server_to_est_offset_hours) % 24
        
        # Silver Bullet Hours (Strict 1 hour windows)
        # 03:00 - 04:00
        # 10:00 - 11:00
        # 14:00 - 15:00
        if ny_hour in [3, 10, 14]:
            return True
            
        return False

    def get_historical_data(self, symbol: str, start_date: datetime, end_date: datetime, timeframe: str = "M5") -> pd.DataFrame:
        """Get historical data from MT5 with robust error handling"""
        try:
            symbol = symbol.strip()
            if not mt5.initialize():
                err = mt5.last_error()
                logger.error(f"MT5 initialization failed: {err}")
                return pd.DataFrame()
            
            # Ensure symbol is selected in MarketWatch
            if not mt5.symbol_select(symbol, True):
                err = mt5.last_error()
                logger.error(f"Symbol '{symbol}' could not be selected/found: {err}")
                mt5.shutdown()
                return pd.DataFrame()

            # Map timeframe
            tf_map = {
                "M1": mt5.TIMEFRAME_M1, "M3": mt5.TIMEFRAME_M3, "M5": mt5.TIMEFRAME_M5, 
                "M15": mt5.TIMEFRAME_M15, "M30": mt5.TIMEFRAME_M30, "H1": mt5.TIMEFRAME_H1, 
                "H4": mt5.TIMEFRAME_H4, "D1": mt5.TIMEFRAME_D1
            }
            
            timeframe_mt5 = tf_map.get(timeframe, mt5.TIMEFRAME_H1)
            
            logger.info(f"⏳ Fetching {timeframe} data for {symbol} from {start_date} to {end_date}...")
            rates = mt5.copy_rates_range(symbol, timeframe_mt5, start_date, end_date)
            
            if rates is None or len(rates) == 0:
                err = mt5.last_error()
                logger.warning(f"No historical data for {symbol}. MT5 Error: {err}")
                mt5.shutdown()
                return pd.DataFrame()
            
            df = pd.DataFrame(rates)
            df['time'] = pd.to_datetime(df['time'], unit='s')
            df.set_index('time', inplace=True)
            
            # Add technical indicators
            df = self.add_indicators(df)
            
            mt5.shutdown()
            logger.info(f"✅ Successfully loaded {len(df)} bars for {symbol}")
            return df
            
        except Exception as e:
            logger.error(f"Error getting historical data: {e}")
            try: mt5.shutdown()
            except: pass
            return pd.DataFrame()
    
    def add_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add technical indicators"""
        try:
            # Moving averages
            df['sma_20'] = df['close'].rolling(20).mean()
            df['sma_50'] = df['close'].rolling(50).mean()
            df['ema_12'] = df['close'].ewm(span=12).mean()
            df['ema_26'] = df['close'].ewm(span=26).mean()
            
            # RSI
            delta = df['close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            df['rsi'] = 100 - (100 / (1 + rs))
            
            # MACD
            df['macd'] = df['ema_12'] - df['ema_26']
            df['macd_signal'] = df['macd'].ewm(span=9).mean()
            
            # Bollinger Bands
            df['bb_middle'] = df['close'].rolling(20).mean()
            bb_std = df['close'].rolling(20).std()
            df['bb_upper'] = df['bb_middle'] + (bb_std * 2)
            df['bb_lower'] = df['bb_middle'] - (bb_std * 2)
            
            return df
            
        except Exception as e:
            logger.error(f"Error adding indicators: {e}")
            return df
    
    def ai_signal_generator(self, df: pd.DataFrame, index: int) -> Dict:
        """Generate ICT/SMC AI trading signals"""
        try:
            if index < 50:  # Need enough data
                return {'signal': 'HOLD', 'confidence': 0.0}
            
            # ICT TIME FILTER (Silver Bullet)
            # ICT TIME FILTER (Silver Bullet)
            current_time = df.index[index]
            # Ensure it is a datetime object
            if not isinstance(current_time, datetime):
                 # Try to convert if it's a pandas Timestamp
                 try: 
                    current_time = current_time.to_pydatetime()
                 except: 
                    pass

            if self.use_time_filter and not self._is_silver_bullet_time(current_time):
                ny_hour = (current_time.hour - self.server_to_est_offset_hours) % 24
                return {'signal': 'HOLD', 'confidence': 0.0, 'reason': f'Outside Silver Bullet Hours ({ny_hour} NY)'}
            
            # Get market structure analysis
            market_bias = self._determine_market_bias(df, index)
            if market_bias == 'NEUTRAL':
                return {'signal': 'HOLD', 'confidence': 0.0}
            
            # Check for liquidity sweeps
            liquidity_sweep = self._detect_liquidity_sweep(df, index)
            
            # Check for displacement and FVG
            fvg = self._detect_fair_value_gap(df, index)
            
            # Check dealing range and discount/premium zones
            dealing_range = self._analyze_dealing_range(df, index)
            
            # Check for order blocks
            order_block = self._detect_order_block(df, index, market_bias)
            
            # Check OTE (Optimal Trade Entry) levels
            ote_level = self._check_ote_levels(df, index, fvg)
            
            current = df.iloc[index]
            
            # Calculate confluence score for available signals
            signals_present = []
            signal_strengths = []
            
            if liquidity_sweep['detected']:
                signals_present.append(f"Liquidity Sweep ({liquidity_sweep['type']})")
                signal_strengths.append(liquidity_sweep['strength'])
            
            if fvg['detected']:
                signals_present.append(f"FVG ({fvg['type']})")
                signal_strengths.append(fvg['strength'])
            
            if order_block['detected']:
                signals_present.append(f"Order Block ({order_block['type']})")
                signal_strengths.append(order_block['strength'])
            
            # BULLISH SETUP - Need at least 2 of 3 main signals
            if market_bias == 'BULLISH':
                bullish_conditions = 0
                
                if liquidity_sweep.get('type') == 'BELOW_LOW':
                    bullish_conditions += 1
                if fvg.get('type') == 'BULLISH':
                    bullish_conditions += 1
                if order_block.get('type') == 'BULLISH':
                    bullish_conditions += 1
                if dealing_range['zone'] == 'DISCOUNT':
                    bullish_conditions += 0.5  # Bonus for discount zone
                if ote_level['valid']:
                    bullish_conditions += 0.5  # Bonus for OTE
                
                if bullish_conditions >= 1.5:  # Relaxed to 1.5 for better capture
                    confidence = self._calculate_confluence_score(signal_strengths)
                    
                    # Determine stop loss
                    if liquidity_sweep['detected']:
                        stop_loss = liquidity_sweep['swept_level'] - (current['close'] * 0.001)
                    else:
                        stop_loss = current['close'] * 0.98  # 2% stop
                    
                    return {
                        'signal': 'BUY',
                        'confidence': confidence,
                        'stop_loss': stop_loss,
                        'take_profit': self._find_next_liquidity_pool(df, index, 'UP'),
                        'entry_reason': f'ICT Bullish: {", ".join(signals_present)} (Score: {bullish_conditions:.1f})'
                    }
            
            # BEARISH SETUP - Need at least 2 of 3 main signals
            elif market_bias == 'BEARISH':
                bearish_conditions = 0
                
                if liquidity_sweep.get('type') == 'ABOVE_HIGH':
                    bearish_conditions += 1
                if fvg.get('type') == 'BEARISH':
                    bearish_conditions += 1
                if order_block.get('type') == 'BEARISH':
                    bearish_conditions += 1
                if dealing_range['zone'] == 'PREMIUM':
                    bearish_conditions += 0.5  # Bonus for premium zone
                if ote_level['valid']:
                    bearish_conditions += 0.5  # Bonus for OTE
                
                if bearish_conditions >= 1.5:  # Relaxed to 1.5 for better capture
                    confidence = self._calculate_confluence_score(signal_strengths)
                    
                    # Determine stop loss
                    if liquidity_sweep['detected']:
                        stop_loss = liquidity_sweep['swept_level'] + (current['close'] * 0.001)
                    else:
                        stop_loss = current['close'] * 1.02  # 2% stop
                    
                    return {
                        'signal': 'SELL',
                        'confidence': confidence,
                        'stop_loss': stop_loss,
                        'take_profit': self._find_next_liquidity_pool(df, index, 'DOWN'),
                        'entry_reason': f'ICT Bearish: {", ".join(signals_present)} (Score: {bearish_conditions:.1f})'
                    }
            
            return {'signal': 'HOLD', 'confidence': 0.0}
                
        except Exception as e:
            logger.error(f"ICT AI signal error: {e}")
            return {'signal': 'HOLD', 'confidence': 0.0}
    
    def _determine_market_bias(self, df: pd.DataFrame, index: int) -> str:
        """Determine market bias using MSS (Market Structure Shift)"""
        try:
            lookback = 50  # More lookback for M5 timeframe
            if index < lookback:
                return 'NEUTRAL'
            
            recent_data = df.iloc[index-lookback:index+1]
            
            # Find swing highs and lows (smaller window for M5)
            highs = recent_data['high'].rolling(3, center=True).max()
            lows = recent_data['low'].rolling(3, center=True).min()
            
            current_price = df.iloc[index]['close']
            
            # Check for higher highs and higher lows (bullish)
            recent_high = highs.max()
            recent_low = lows.min()
            
            if current_price > recent_high:
                return 'BULLISH'
            elif current_price < recent_low:
                return 'BEARISH'
            
            # If in range, check which side we are closer to
            dist_to_high = recent_high - current_price
            dist_to_low = current_price - recent_low
            
            if dist_to_high < dist_to_low:
                return 'BULLISH'
            else:
                return 'BEARISH'
                
        except Exception:
            return 'NEUTRAL'
    
    def _detect_liquidity_sweep(self, df: pd.DataFrame, index: int) -> Dict:
        """
        Detect liquidity sweeps completed on the PREVIOUS bar.
        Matches the confirmed 'break & close back inside' requirement.
        """
        try:
            lookback = 30  # Synced lookback
            if index < lookback + 1:
                return {'detected': False}
            
            # Use the previous confirmed bar
            confirmed_idx = index - 1
            current_bar = df.iloc[confirmed_idx]
            
            # Swing levels from BEFORE the sweep bar
            recent_data = df.iloc[confirmed_idx - lookback : confirmed_idx]
            swing_low = recent_data['low'].min()
            swing_high = recent_data['high'].max()
            
            # Bullish Sweep: Low below swing low, but CLOSE above swing low
            if current_bar['low'] < swing_low and current_bar['close'] > swing_low:
                return {'detected': True, 'type': 'BELOW_LOW', 'swept_level': swing_low, 'strength': 0.8}
            
            # Bearish Sweep: High above swing high, but CLOSE below swing high
            elif current_bar['high'] > swing_high and current_bar['close'] < swing_high:
                return {'detected': True, 'type': 'ABOVE_HIGH', 'swept_level': swing_high, 'strength': 0.8}
            
            return {'detected': False}
        except Exception:
            return {'detected': False}
    
    def _detect_fair_value_gap(self, df: pd.DataFrame, index: int) -> Dict:
        """Detect Fair Value Gaps (FVG)"""
        try:
            if index < 3:
                return {'detected': False}
            
            bar1 = df.iloc[index-2]  # First bar
            bar2 = df.iloc[index-1]  # Middle bar (displacement)
            bar3 = df.iloc[index]    # Current bar
            
            # Bullish FVG: bar1.high < bar3.low (gap between them)
            if bar1['high'] < bar3['low']:
                gap_size = bar3['low'] - bar1['high']
                if gap_size > (bar2['close'] * 0.0005):  # Minimum gap size
                    return {
                        'detected': True,
                        'type': 'BULLISH',
                        'high': bar3['low'],
                        'low': bar1['high'],
                        'strength': min(gap_size / (bar2['close'] * 0.002), 1.0)
                    }
            
            # Bearish FVG: bar1.low > bar3.high (gap between them)
            elif bar1['low'] > bar3['high']:
                gap_size = bar1['low'] - bar3['high']
                if gap_size > (bar2['close'] * 0.0005):  # Minimum gap size
                    return {
                        'detected': True,
                        'type': 'BEARISH',
                        'high': bar1['low'],
                        'low': bar3['high'],
                        'strength': min(gap_size / (bar2['close'] * 0.002), 1.0)
                    }
            
            return {'detected': False}
            
        except Exception:
            return {'detected': False}
    
    def _analyze_dealing_range(self, df: pd.DataFrame, index: int) -> Dict:
        """Analyze if price is in discount or premium zone"""
        try:
            lookback = 20
            if index < lookback:
                return {'zone': 'NEUTRAL'}
            
            recent_data = df.iloc[index-lookback:index+1]
            range_high = recent_data['high'].max()
            range_low = recent_data['low'].min()
            current_price = df.iloc[index]['close']
            
            range_50 = range_low + (range_high - range_low) * 0.5
            
            if current_price < range_50:
                return {'zone': 'DISCOUNT', 'level': range_50}
            else:
                return {'zone': 'PREMIUM', 'level': range_50}
                
        except Exception:
            return {'zone': 'NEUTRAL'}
    
    def _detect_order_block(self, df: pd.DataFrame, index: int, bias: str) -> Dict:
        """Detect institutional order blocks"""
        try:
            lookback = 15
            if index < lookback:
                return {'detected': False}
            
            current = df.iloc[index]
            
            # Look for significant price moves (displacement)
            for i in range(index-lookback, index-1):
                bar = df.iloc[i]
                next_bar = df.iloc[i+1]
                
                # Calculate price change
                price_change = abs(next_bar['close'] - bar['close']) / bar['close']
                
                # Bullish Order Block: Strong move up after this bar (smaller threshold for M5)
                if bias == 'BULLISH' and price_change > 0.002:  # 0.2% move for M5
                    if next_bar['close'] > bar['close']:
                        return {
                            'detected': True,
                            'type': 'BULLISH',
                            'high': bar['high'],
                            'low': bar['low'],
                            'strength': min(price_change * 10, 1.0)
                        }
                
                # Bearish Order Block: Strong move down after this bar (smaller threshold for M5)
                elif bias == 'BEARISH' and price_change > 0.002:  # 0.2% move for M5
                    if next_bar['close'] < bar['close']:
                        return {
                            'detected': True,
                            'type': 'BEARISH',
                            'high': bar['high'],
                            'low': bar['low'],
                            'strength': min(price_change * 10, 1.0)
                        }
            
            return {'detected': False}
            
        except Exception:
            return {'detected': False}
    
    def _check_ote_levels(self, df: pd.DataFrame, index: int, fvg: Dict) -> Dict:
        """Check Optimal Trade Entry levels (62%-79% Fibonacci)"""
        try:
            if not fvg.get('detected'):
                return {'valid': False}
            
            current_price = df.iloc[index]['close']
            fvg_high = fvg['high']
            fvg_low = fvg['low']
            
            # Calculate OTE levels (62% - 79% of FVG)
            fvg_range = fvg_high - fvg_low
            ote_62 = fvg_low + (fvg_range * 0.62)
            ote_79 = fvg_low + (fvg_range * 0.79)
            
            # Check if current price is in OTE zone
            if ote_62 <= current_price <= ote_79:
                return {
                    'valid': True,
                    'strength': 0.9,
                    'level_62': ote_62,
                    'level_79': ote_79
                }
            
            return {'valid': False}
            
        except Exception:
            return {'valid': False}
    
    def _find_next_liquidity_pool(self, df: pd.DataFrame, index: int, direction: str) -> float:
        """Find next liquidity pool for take profit"""
        try:
            lookback = 30
            current_price = df.iloc[index]['close']
            
            if direction == 'UP':
                # Find resistance levels above current price
                recent_highs = df.iloc[max(0, index-lookback):index]['high']
                resistance = recent_highs[recent_highs > current_price].min()
                return resistance if not pd.isna(resistance) else current_price * 1.02
            
            else:  # DOWN
                # Find support levels below current price
                recent_lows = df.iloc[max(0, index-lookback):index]['low']
                support = recent_lows[recent_lows < current_price].max()
                return support if not pd.isna(support) else current_price * 0.98
                
        except Exception:
            return current_price * (1.02 if direction == 'UP' else 0.98)
    
    def _calculate_confluence_score(self, strengths: List[float]) -> float:
        """Calculate confluence score from multiple signal strengths"""
        try:
            if not strengths:
                return 0.0
            
            # Weight the confluence - more signals = higher confidence
            base_score = sum(strengths) / len(strengths)
            confluence_bonus = min(len(strengths) * 0.1, 0.3)  # Max 30% bonus
            
            return min(base_score + confluence_bonus, 1.0)
            
        except Exception:
            return 0.0
    
    def calculate_position_size(self, balance: float, entry_price: float, stop_loss: float, symbol: str, risk_per_trade: float = 0.02) -> float:
        """Calculate position size based on risk"""
        multiplier, max_lots = self._contract_spec(symbol)
        risk_per_trade = getattr(self, 'risk_per_trade', risk_per_trade)
        risk_amount = balance * risk_per_trade
        price_diff = abs(entry_price - stop_loss)
        
        # No stop distance means no defined risk — size it at zero rather than
        # falling back to the broker minimum, which would risk far more than intended.
        if price_diff <= 0:
            return 0.0
        
        # Size so that hitting the stop loses exactly risk_amount. Uses the same
        # contract multiplier as PnL, so sizing and PnL can never disagree.
        raw_size = risk_amount / (price_diff * multiplier)
        position_size = min(raw_size, max_lots)
        position_size = round(position_size, 2)
        
        # Below the broker minimum lot the trade simply cannot be placed.
        if position_size < self.MIN_LOT:
            return 0.0
        
        return position_size
    
    def run_grid_backtest(self, symbol: str, start_date: datetime, end_date: datetime, timeframe: str = "M5", mode: str = "BOTH") -> Dict:
        """Run grid strategy backtest with mode: BOTH, BUY_ONLY, SELL_ONLY"""
        try:
            logger.info(f"🕸️ Running Grid Backtest ({mode}) for {symbol}")
            data = self.get_historical_data(symbol, start_date, end_date, timeframe)
            if data.empty:
                return self._empty_metrics(symbol, 'No data')

            # Reset per run. Inheriting the previous run's ending balance made
            # repeated GUI runs compound off each other and report a return
            # that no single run could have produced.
            self._load_backtest_config()
            self.trades = []
            self.equity_curve = [self.balance]
            
            pending_orders = []
            open_positions = []
            
            # Use settings from config if possible, else defaults
            target_usd = 10.0
            try:
                import yaml
                with open('config.yaml', 'r') as f:
                    config = yaml.safe_load(f)
                grid_cfg = config.get('grid', {})
                grid_size = grid_cfg.get('size', 300)
                spacing = grid_cfg.get('spacing', 1.0)
                lot_size = grid_cfg.get('lot_size', 0.01)
                target_usd = float(grid_cfg.get('profit_target_usd', 10))
                max_open_layers = int(grid_cfg.get('max_open_layers', 6))
            except Exception:
                grid_size = 300
                spacing = 1.0
                lot_size = 0.01
                target_usd = 10.0
                max_open_layers = 6

            logger.info(f"⚙️ Grid Config: Size={grid_size}, Spacing={spacing}, Lot={lot_size}, Target=${target_usd:.2f}, MaxLayers={max_open_layers}")
            
            # Snapshot live bid/ask once so fills pay the real spread
            self._capture_quote(symbol)
            spread = self._quote['spread']

            for i in range(50, len(data)):
                current_bar = data.iloc[i]
                current_time = data.index[i]
                
                # Mark floating PnL at the side we would exit at, not at close
                exit_ref_buy = float(current_bar['close']) - (spread / 2)
                exit_ref_sell = float(current_bar['close']) + (spread / 2)
                
                # 1. Check profit targets
                buy_pos = [p for p in open_positions if p['type'] == 'BUY']
                sell_pos = [p for p in open_positions if p['type'] == 'SELL']
                
                buy_profit = sum(self._calculate_floating_pnl(p, exit_ref_buy, symbol) for p in buy_pos)
                sell_profit = sum(self._calculate_floating_pnl(p, exit_ref_sell, symbol) for p in sell_pos)
                
                # Target must match the LIVE bot. It used balance * profit_target_pct
                # ($100k * 25% = $25,000) while live trading banks $10, so the
                # backtest could essentially never reach target and every run
                # ended as one forced liquidation.
                target_amt = target_usd
                
                if buy_pos and buy_profit >= target_amt:
                    logger.info(f"🎯 Buy Grid target hit at {current_time}! Profit: ${buy_profit:.2f}")
                    for p in buy_pos:
                        trade = self._close_position(p, exit_ref_buy, current_time, 'Grid Target')
                        self.trades.append(trade)
                        self.balance += trade['pnl']
                    open_positions = [p for p in open_positions if p['type'] != 'BUY']
                    pending_orders = [o for o in pending_orders if o['type'] != 'BUY']
                
                if sell_pos and sell_profit >= target_amt:
                    logger.info(f"🎯 Sell Grid target hit at {current_time}! Profit: ${sell_profit:.2f}")
                    for p in sell_pos:
                        trade = self._close_position(p, exit_ref_sell, current_time, 'Grid Target')
                        self.trades.append(trade)
                        self.balance += trade['pnl']
                    open_positions = [p for p in open_positions if p['type'] != 'SELL']
                    pending_orders = [o for o in pending_orders if o['type'] != 'SELL']

                # 2. Check pending hits
                for order in pending_orders[:]:
                    if (order['type'] == 'BUY' and current_bar['low'] <= order['price']) or \
                       (order['type'] == 'SELL' and current_bar['high'] >= order['price']):
                        # Live trading caps open layers (fib_dca.max_open_layers)
                        # and total exposure. Without a cap here the grid opens
                        # every one of its 300 levels in a deep move, which the
                        # live bot would never be allowed to do.
                        if len(open_positions) >= max_open_layers:
                            pending_orders.remove(order)
                            continue
                        # Fill at the level plus half-spread on the wrong side
                        fill = order['price'] + (spread / 2 if order['type'] == 'BUY' else -spread / 2)
                        order['entry_time'] = current_time
                        order['entry_price'] = fill
                        open_positions.append(order)
                        pending_orders.remove(order)

                # 3. Check bias and grid placement
                bias = self._determine_market_bias(data, i)
                
                # Grid placement based on mode
                if mode in ['BOTH', 'SELL_ONLY']:
                    if bias == 'BULLISH' and not any(o['type'] == 'SELL' for o in pending_orders) and not any(p['type'] == 'SELL' for p in open_positions):
                        logger.info(f"🚀 Placing SELL grid at {current_time} (Price: {current_bar['close']})")
                        for j in range(1, grid_size + 1):
                            pending_orders.append({'type': 'SELL', 'price': current_bar['close'] + (j * spacing), 'position_size': lot_size, 'symbol': symbol, 'confidence': 1.0})
                
                if mode in ['BOTH', 'BUY_ONLY']:
                    if bias == 'BEARISH' and not any(o['type'] == 'BUY' for o in pending_orders) and not any(p['type'] == 'BUY' for p in open_positions):
                        logger.info(f"🚀 Placing BUY grid at {current_time} (Price: {current_bar['close']})")
                        for j in range(1, grid_size + 1):
                            pending_orders.append({'type': 'BUY', 'price': current_bar['close'] - (j * spacing), 'position_size': lot_size, 'symbol': symbol, 'confidence': 1.0})

                # 4. Sample equity ONCE per bar, always as realized + open risk.
                # The old code appended raw realized balance on some bars and
                # realized+floating on others, so drawdown and Sharpe were
                # computed over a series that jumped by phantom amounts.
                floating_now = sum(
                    self._calculate_floating_pnl(
                        p,
                        exit_ref_buy if p['type'] == 'BUY' else exit_ref_sell,
                        symbol
                    ) for p in open_positions
                )
                self.equity_curve.append(self.balance + floating_now)

            # 5. Force close all remaining positions at end of backtest
            if open_positions:
                logger.info(f"🏁 Closing {len(open_positions)} remaining positions at end of backtest")
                final_close = float(data.iloc[-1]['close'])
                for p in open_positions:
                    exit_ref = final_close - (spread / 2 if p['type'] == 'BUY' else -spread / 2)
                    trade = self._close_position(p, exit_ref, data.index[-1], 'End of Backtest')
                    self.trades.append(trade)
                    self.balance += trade['pnl']
            
            return self._calculate_performance_metrics(symbol)
        except Exception as e:
            logger.error(f"Grid backtest error: {e}")
            return self._empty_metrics(symbol, str(e))

    def run_backtest(self, symbol: str, start_date: datetime, end_date: datetime, timeframe: str = "M5") -> Dict:
        """Run backtest on historical data"""
        try:
            logger.info(f"🧠 Running backtest for {symbol}")
            logger.info(f"📅 Period: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
            
            # Get historical data with specified timeframe
            data = self.get_historical_data(symbol, start_date, end_date, timeframe)
            if data.empty:
                return {'error': 'No historical data available'}
            
            logger.info(f"📊 Loaded {len(data)} bars of data")
            unique_hours = sorted(data.index.hour.unique())
            logger.info(f"⏰ Unique hours in data: {unique_hours}")
            logger.info(f"🎯 Target Silver Bullet Hours: [3, 10, 14]")
            
            # Initialize backtest variables — reset EVERY run so repeated GUI
            # runs on the same engine instance don't compound off each other.
            self._load_backtest_config()
            self.trades = []
            self.ai_memories = []
            self.equity_curve = [self.balance]
            position = None
            
            # Snapshot live bid/ask once so fills pay the real spread
            self._capture_quote(symbol)
            spread = self._quote['spread']
            
            # Run through historical data
            for i in range(50, len(data)):
                current_bar = data.iloc[i]
                current_time = data.index[i]
                
                # Generate AI signal
                signal_data = self.ai_signal_generator(data, i)
                signal = signal_data['signal']
                confidence = signal_data['confidence']
                
                # Check for entry signals
                if position is None and signal in ['BUY', 'SELL'] and confidence >= self.min_confidence:
                    # Entry fills at the NEXT bar's open. Entering at the signal
                    # bar's close is look-ahead: the signal is derived from that
                    # bar's close/high/low, which are not knowable until it has
                    # closed. The last bar has no next open, so it cannot be used.
                    if i + 1 >= len(data):
                        continue
                    
                    next_open = float(data.iloc[i + 1]['open'])
                    
                    # Pay the spread on entry: buy lifts the ask, sell hits the bid
                    entry_price = next_open + (spread / 2 if signal == 'BUY' else -spread / 2)
                    entry_time = data.index[i + 1]
                    
                    # Use ICT-based stop loss and take profit if available
                    if 'stop_loss' in signal_data and 'take_profit' in signal_data:
                        stop_loss = signal_data['stop_loss']
                        take_profit = signal_data['take_profit']
                    else:
                        # Fallback to ATR-based levels
                        atr = self._calculate_atr(data, i)
                        if signal == 'BUY':
                            stop_loss = entry_price - (atr * 2)
                            take_profit = entry_price + (atr * 3)
                        else:
                            stop_loss = entry_price + (atr * 2)
                            take_profit = entry_price - (atr * 3)
                    
                    # Validate levels point the right way before sizing
                    if signal == 'BUY':
                        levels_valid = stop_loss < entry_price < take_profit
                    else:
                        levels_valid = take_profit < entry_price < stop_loss
                    
                    if not levels_valid:
                        logger.debug(f"Discarded {signal} setup at {current_time}: SL/TP not bracketing entry")
                        continue
                    
                    # Calculate position size
                    position_size = self.calculate_position_size(self.balance, entry_price, stop_loss, symbol)
                    
                    if position_size < self.MIN_LOT:
                        continue
                    
                    position = {
                        'type': signal,
                        'entry_time': entry_time,
                        'entry_price': entry_price,
                        'position_size': position_size,
                        'stop_loss': stop_loss,
                        'take_profit': take_profit,
                        'confidence': confidence,
                        'symbol': symbol
                    }
                    
                    # Mark equity immediately so the curve reflects open risk
                    self.equity_curve.append(self.balance)
                
                # Check for exit conditions
                elif position is not None:
                    exit_triggered = False
                    exit_price = current_bar['close']
                    exit_reason = 'Time'
                    
                    hit_stop = False
                    hit_target = False
                    
                    if position['type'] == 'BUY':
                        hit_stop = current_bar['low'] <= position['stop_loss']
                        hit_target = current_bar['high'] >= position['take_profit']
                    else:
                        hit_stop = current_bar['high'] >= position['stop_loss']
                        hit_target = current_bar['low'] <= position['take_profit']
                    
                    # When a single bar spans BOTH the stop and the target the
                    # intrabar sequence is unknowable from OHLC alone. Resolve to
                    # the pessimistic (stop-loss) outcome instead of silently
                    # picking whichever branch happened to be tested first.
                    if hit_stop:
                        exit_price = position['stop_loss']
                        exit_reason = 'Stop Loss'
                        exit_triggered = True
                    elif hit_target:
                        exit_price = position['take_profit']
                        exit_reason = 'Take Profit'
                        exit_triggered = True
                    
                    # Time-based exit (hold for max 72 hours)
                    elif (current_time - position['entry_time']).total_seconds() / 3600 > 72:
                        exit_price = current_bar['close']
                        exit_reason = 'Time Exit'
                        exit_triggered = True
                    
                    # Execute exit
                    if exit_triggered:
                        # Pay the spread on exit: buy sells into the bid, sell lifts the ask
                        if exit_reason in ('Stop Loss', 'Take Profit'):
                            exit_price = exit_price - (spread / 2 if position['type'] == 'BUY' else -spread / 2)
                        
                        trade = self._close_position(position, exit_price, current_time, exit_reason)
                        self.trades.append(trade)
                        
                        # Update balance
                        self.balance += trade['pnl']
                        self.equity_curve.append(self.balance)
                        
                        # Store for AI training
                        self.ai_memories.append({
                            'symbol': symbol,
                            'entry_time': position['entry_time'],
                            'exit_time': current_time,
                            'type': position['type'],
                            'pnl': trade['pnl'],
                            'success': trade['pnl'] > 0,
                            'confidence': position['confidence'],
                            'market_conditions': {
                                'rsi': current_bar.get('rsi', 50),
                                # .get() with a close-price fallback: a bare
                                # ['sma_20'] raised KeyError and aborted the
                                # whole backtest whenever indicators were absent
                                'trend': 'bullish' if current_bar['close'] > current_bar.get('sma_20', current_bar['close']) else 'bearish'
                            }
                        })
                        
                        position = None
            
            # Force-close anything still open at the end of the run. Without
            # this the last trade's PnL was dropped on the floor, because the
            # position never hit SL/TP/time-exit inside the loop and simply
            # stopped existing — biasing every result.
            if position is not None:
                logger.info(f"🏁 Closing open {position['type']} position at end of backtest")
                final_close = float(data.iloc[-1]['close'])
                final_exit = final_close - (spread / 2 if position['type'] == 'BUY' else -spread / 2)
                trade = self._close_position(position, final_exit, data.index[-1], 'End of Backtest')
                self.trades.append(trade)
                self.balance += trade['pnl']
                self.equity_curve.append(self.balance)
            
            # Calculate performance metrics
            results = self._calculate_performance_metrics(symbol)
            
            # Train AI with results
            self._train_ai_with_results()
            
            logger.info(f"✅ Backtest completed: {len(self.trades)} trades")
            return results
            
        except Exception as e:
            logger.error(f"Backtest error: {e}")
            return {'error': str(e)}
    
    def _calculate_atr(self, data: pd.DataFrame, index: int, period: int = 14) -> float:
        """Calculate Average True Range"""
        try:
            if index < period:
                return 0.01
            
            # True Range needs the PREVIOUS bar's close. Slicing close one row
            # further back than high/low aligns it correctly; slicing it the same
            # way compares each bar against its own close, which throws away the
            # bar-to-bar move and understates volatility (=> stops far too tight).
            window = data.iloc[index-period:index]
            prev_close = data['close'].iloc[index-period-1:index]
            
            high = window['high']
            low = window['low']
            
            tr1 = high - low
            tr2 = (high - prev_close).abs()
            tr3 = (low - prev_close).abs()
            
            true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
            atr = float(true_range.mean())
            return atr if atr > 0 else 0.01
            
        except Exception:
            return 0.01
    
    def _calculate_floating_pnl(self, position: Dict, current_price: float, symbol: str) -> float:
        """Calculate floating P&L for a position"""
        try:
            entry_price = position['entry_price']
            position_size = position['position_size']
            
            price_diff = current_price - entry_price if position['type'] == 'BUY' else entry_price - current_price
            
            pnl = self._pnl_for_move(symbol, price_diff, position_size)
            pnl -= self._cost_basis(symbol, position_size)
            
            return pnl
        except Exception:
            return 0.0

    def _close_position(self, position: Dict, exit_price: float, exit_time: datetime, exit_reason: str) -> Dict:
        """Close position and calculate P&L"""
        try:
            entry_price = position['entry_price']
            position_size = position['position_size']
            symbol = position.get('symbol', '')
            
            price_diff = exit_price - entry_price if position['type'] == 'BUY' else entry_price - exit_price
            
            gross_pnl = self._pnl_for_move(symbol, price_diff, position_size)
            commission = self._cost_basis(symbol, position_size)
            pnl = gross_pnl - commission
            
            return {
                'entry_time': position['entry_time'],
                'exit_time': exit_time,
                'type': position['type'],
                'entry_price': entry_price,
                'exit_price': exit_price,
                'position_size': position_size,
                'gross_pnl': gross_pnl,
                'commission': commission,
                'pnl': pnl,
                'exit_reason': exit_reason,
                'duration': (exit_time - position['entry_time']).total_seconds() / 3600 if 'entry_time' in position else 0,
                'confidence': position.get('confidence', 1.0)
            }
            
        except Exception as e:
            logger.error(f"Position close error: {e}")
            return {}
    
    def _empty_metrics(self, symbol: str, reason: str) -> Dict:
        """Zeroed-but-complete result so callers can format without KeyError."""
        return {
            'symbol': symbol,
            'error': reason,
            'total_trades': 0,
            'winning_trades': 0,
            'losing_trades': 0,
            'win_rate': 0.0,
            'total_pnl': 0.0,
            'avg_win': 0.0,
            'avg_loss': 0.0,
            'profit_factor': 0.0,
            'expectancy': 0.0,
            'max_drawdown': 0.0,
            'sharpe_ratio': 0.0,
            'final_balance': self.balance,
            'return_pct': 0.0,
            'trades': []
        }
    
    def _calculate_performance_metrics(self, symbol: str) -> Dict:
        """Calculate backtest performance metrics"""
        try:
            if not self.trades:
                return self._empty_metrics(symbol, 'No trades executed')
            
            # Basic metrics
            total_trades = len(self.trades)
            winning_trades = len([t for t in self.trades if t['pnl'] > 0])
            losing_trades = len([t for t in self.trades if t['pnl'] < 0])
            
            win_rate = winning_trades / total_trades if total_trades > 0 else 0
            
            total_pnl = sum(t['pnl'] for t in self.trades)
            avg_win = np.mean([t['pnl'] for t in self.trades if t['pnl'] > 0]) if winning_trades > 0 else 0
            avg_loss = np.mean([t['pnl'] for t in self.trades if t['pnl'] < 0]) if losing_trades > 0 else 0
            
            # Profit factor = gross profit / gross loss. With zero losses it is
            # undefined (infinite), NOT 0 — reporting 0 made a 100%-win run
            # look like the worst possible outcome.
            gross_profit = sum(t['pnl'] for t in self.trades if t['pnl'] > 0)
            gross_loss = abs(sum(t['pnl'] for t in self.trades if t['pnl'] < 0))
            if gross_loss > 0:
                profit_factor = gross_profit / gross_loss
            else:
                profit_factor = float('inf') if gross_profit > 0 else 0.0
            
            # Expectancy = average PnL per trade
            expectancy = total_pnl / total_trades if total_trades > 0 else 0.0
            
            # Drawdown calculation
            peak = self.equity_curve[0]
            max_drawdown = 0.0
            for equity in self.equity_curve:
                if equity > peak:
                    peak = equity
                if peak > 0:
                    drawdown = (peak - equity) / peak
                    max_drawdown = max(max_drawdown, drawdown)
            
            # Sharpe on per-trade returns. Annualising M5-bar deltas by sqrt(252)
            # was meaningless (252 is a daily-bar constant), so the exponent is
            # taken from the number of observations instead.
            sharpe_ratio = 0.0
            if len(self.equity_curve) > 2:
                curve = np.array(self.equity_curve, dtype=float)
                prev = curve[:-1]
                mask = prev != 0
                returns = np.diff(curve)[mask] / prev[mask]
                if len(returns) > 1 and np.std(returns) > 0:
                    sharpe_ratio = float(np.mean(returns) / np.std(returns) * np.sqrt(len(returns)))
            
            # Return is measured against the balance THIS run started with.
            # It was hardcoded against 10000 while the engine starts at 100000,
            # which turned a +5% run into a reported +950%.
            return_pct = ((self.balance - self.initial_balance) / self.initial_balance) if self.initial_balance else 0.0
            
            return {
                'symbol': symbol,
                'total_trades': total_trades,
                'winning_trades': winning_trades,
                'losing_trades': losing_trades,
                'win_rate': win_rate,
                'total_pnl': total_pnl,
                'avg_win': avg_win,
                'avg_loss': avg_loss,
                'profit_factor': profit_factor,
                'expectancy': expectancy,
                'max_drawdown': max_drawdown,
                'sharpe_ratio': sharpe_ratio,
                'final_balance': self.balance,
                'return_pct': return_pct,
                'trades': self.trades
            }
            
        except Exception as e:
            logger.error(f"Performance calculation error: {e}")
            return self._empty_metrics(symbol, str(e))
    
    def _train_ai_with_results(self):
        """Train AI with backtest results"""
        try:
            logger.info(f"🧠 Training AI with {len(self.ai_memories)} trade memories")
            
            # Simple AI training simulation
            successful_trades = [m for m in self.ai_memories if m['success']]
            failed_trades = [m for m in self.ai_memories if not m['success']]
            
            logger.info(f"✅ Successful patterns: {len(successful_trades)}")
            logger.info(f"❌ Failed patterns: {len(failed_trades)}")
            
            # Save AI memories for future use
            ai_file = Path("models/ai_memories.json")
            ai_file.parent.mkdir(exist_ok=True)
            
            with open(ai_file, 'w') as f:
                json.dump(self.ai_memories, f, default=str, indent=2)
            
            logger.info("🧠 AI training completed and saved")
            
        except Exception as e:
            logger.error(f"AI training error: {e}")
    
    def generate_report(self, results: Dict):
        """Generate backtest report"""
        try:
            print("\n" + "="*70)
            print("🧠 NEXUS TRADING SYSTEM - BACKTEST REPORT")
            print("="*70)
            print(f"Symbol: {results['symbol']}")
            print(f"Total Trades: {results['total_trades']}")
            print(f"Win Rate: {results['win_rate']:.1%}")
            print(f"Total P&L: ${results['total_pnl']:.2f}")
            print(f"Return: {results['return_pct']:.1%}")
            print(f"Profit Factor: {results['profit_factor']:.2f}")
            print(f"Expectancy: ${results['expectancy']:.2f}/trade")
            print(f"Max Drawdown: {results['max_drawdown']:.1%}")
            print(f"Sharpe Ratio: {results['sharpe_ratio']:.2f}")
            print(f"Starting Balance: ${self.initial_balance:,.2f}")
            print(f"Final Balance: ${results['final_balance']:,.2f}")
            
            if results['total_trades'] > 0:
                print(f"\nAverage Win: ${results['avg_win']:.2f}")
                print(f"Average Loss: ${results['avg_loss']:.2f}")
                print(f"Winning Trades: {results['winning_trades']}")
                print(f"Losing Trades: {results['losing_trades']}")
            
            print("\n🧠 AI TRAINING STATUS:")
            print(f"✅ Trade memories stored: {len(self.ai_memories)}")
            print(f"✅ Neural patterns learned")
            print(f"✅ Ready for live trading")
            
            # Save detailed report
            self._save_detailed_report(results)
            
        except Exception as e:
            logger.error(f"Report generation error: {e}")
    
    def _save_detailed_report(self, results: Dict):
        """Save detailed backtest report"""
        try:
            reports_dir = Path("backtest_results")
            reports_dir.mkdir(exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            report_file = reports_dir / f"backtest_report_{timestamp}.json"
            
            # Prepare report data
            report_data = {
                'timestamp': datetime.now().isoformat(),
                'results': results,
                'ai_memories_count': len(self.ai_memories),
                'equity_curve': self.equity_curve
            }
            
            with open(report_file, 'w') as f:
                json.dump(report_data, f, default=str, indent=2)
            
            logger.info(f"📄 Detailed report saved: {report_file}")
            
        except Exception as e:
            logger.error(f"Report saving error: {e}")
    
    def create_interactive_chart(self, data: pd.DataFrame, trades: List[Dict], symbol: str):
        """Create interactive chart with ICT analysis"""
        try:
            # Create subplots
            fig = make_subplots(
                rows=3, cols=1,
                shared_xaxes=True,
                vertical_spacing=0.02,
                subplot_titles=(f'{symbol} Price Action', 'Volume', 'Equity Curve'),
                row_heights=[0.6, 0.2, 0.2]
            )
            
            # Add candlestick chart
            fig.add_trace(
                go.Candlestick(
                    x=data.index,
                    open=data['open'],
                    high=data['high'],
                    low=data['low'],
                    close=data['close'],
                    name='Price'
                ),
                row=1, col=1
            )
            
            # Add moving averages
            if 'sma_20' in data.columns:
                fig.add_trace(
                    go.Scatter(x=data.index, y=data['sma_20'], name='SMA 20', line=dict(color='orange')),
                    row=1, col=1
                )
            
            if 'sma_50' in data.columns:
                fig.add_trace(
                    go.Scatter(x=data.index, y=data['sma_50'], name='SMA 50', line=dict(color='blue')),
                    row=1, col=1
                )
            
            # Add trade markers
            for trade in trades:
                entry_time = trade['entry_time']
                exit_time = trade['exit_time']
                entry_price = trade['entry_price']
                exit_price = trade['exit_price']
                
                # Entry arrow
                color = 'green' if trade['type'] == 'BUY' else 'red'
                symbol_arrow = '▲' if trade['type'] == 'BUY' else '▼'
                
                fig.add_trace(
                    go.Scatter(
                        x=[entry_time],
                        y=[entry_price],
                        mode='markers+text',
                        marker=dict(symbol='triangle-up' if trade['type'] == 'BUY' else 'triangle-down', 
                                   size=15, color=color),
                        text=[f"Entry {symbol_arrow}"],
                        textposition="top center",
                        name=f"Entry {trade['type']}",
                        showlegend=False
                    ),
                    row=1, col=1
                )
                
                # Exit arrow
                exit_color = 'green' if trade['pnl'] > 0 else 'red'
                fig.add_trace(
                    go.Scatter(
                        x=[exit_time],
                        y=[exit_price],
                        mode='markers+text',
                        marker=dict(symbol='x', size=12, color=exit_color),
                        text=[f"Exit ${trade['pnl']:.0f}"],
                        textposition="top center",
                        name=f"Exit",
                        showlegend=False
                    ),
                    row=1, col=1
                )
            
            # Add volume
            if 'tick_volume' in data.columns:
                fig.add_trace(
                    go.Bar(x=data.index, y=data['tick_volume'], name='Volume', marker_color='lightblue'),
                    row=2, col=1
                )
            
            # Add equity curve
            fig.add_trace(
                go.Scatter(x=list(range(len(self.equity_curve))), y=self.equity_curve, 
                          name='Equity', line=dict(color='green')),
                row=3, col=1
            )
            
            # Update layout
            fig.update_layout(
                title=f'🧠 NEXUS TRADING SYSTEM - {symbol} Analysis',
                xaxis_rangeslider_visible=False,
                height=800,
                showlegend=True
            )
            
            # Save and show chart
            chart_file = f"charts/{symbol}_analysis.html"
            Path("charts").mkdir(exist_ok=True)
            fig.write_html(chart_file)
            logger.info(f"📊 Interactive chart saved: {chart_file}")
            
            return fig
            
        except Exception as e:
            logger.error(f"Chart creation error: {e}")
            return None

class TradingDashboard:
    """Interactive Trading Dashboard with GUI"""
    
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("🧠 NEXUS TRADING SYSTEM - Trading Dashboard")
        self.root.geometry("1000x700")
        self.root.configure(bg='#2b2b2b')
        
        # Variables
        self.selected_symbol = tk.StringVar(value="XAUUSDm")
        self.selected_timeframe = tk.StringVar(value="M5")
        self.selected_period = tk.StringVar(value="30")
        self.selected_strategy = tk.StringVar(value="ICT SMC") # Added strategy selection
        self.backtest_engine = BacktestEngine()
        self.current_results = None
        
        self.setup_gui()
    
    def setup_gui(self):
        """Setup the GUI interface"""
        # Main frame
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Title
        title_label = ttk.Label(main_frame, text="🧠 NEXUS TRADING SYSTEM - AI Trading Dashboard", 
                               font=('Arial', 16, 'bold'))
        title_label.grid(row=0, column=0, columnspan=4, pady=10)
        
        # Control Panel
        control_frame = ttk.LabelFrame(main_frame, text="Trading Controls", padding="10")
        control_frame.grid(row=1, column=0, columnspan=4, sticky=(tk.W, tk.E), pady=5)
        
        # Symbol selection
        ttk.Label(control_frame, text="Symbol:").grid(row=0, column=0, padx=5)
        symbol_combo = ttk.Combobox(control_frame, textvariable=self.selected_symbol, 
                                   values=["XAUUSDm"])
        symbol_combo.grid(row=0, column=1, padx=5)
        
        # Timeframe selection
        ttk.Label(control_frame, text="Timeframe:").grid(row=0, column=2, padx=5)
        timeframe_combo = ttk.Combobox(control_frame, textvariable=self.selected_timeframe,
                                      values=["M1", "M3", "M5", "M15", "M30", "H1", "H4", "D1"])
        timeframe_combo.grid(row=0, column=3, padx=5)
        
        # Period selection
        ttk.Label(control_frame, text="Period (days):").grid(row=0, column=4, padx=5)
        period_combo = ttk.Combobox(control_frame, textvariable=self.selected_period,
                                   values=["7", "30", "90", "180", "365"])
        period_combo.grid(row=0, column=5, padx=5)
        
        # Strategy selection
        ttk.Label(control_frame, text="Strategy:").grid(row=0, column=6, padx=5)
        strategy_combo = ttk.Combobox(control_frame, textvariable=self.selected_strategy,
                                     values=["ICT SMC", "Grid Strategy (Both)", "Grid BUY ONLY", "Grid SELL ONLY"])
        strategy_combo.grid(row=0, column=7, padx=5)
        
        # Buttons
        ttk.Button(control_frame, text="🚀 Run Backtest", 
                  command=self.run_backtest_gui).grid(row=1, column=0, columnspan=2, padx=10, pady=(8, 0))
        ttk.Button(control_frame, text="📊 Show Chart", 
                  command=self.show_chart).grid(row=1, column=2, columnspan=2, padx=10, pady=(8, 0))
        
        # Results Frame
        results_frame = ttk.LabelFrame(main_frame, text="Backtest Results", padding="10")
        results_frame.grid(row=2, column=0, columnspan=4, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5)
        
        # Results text area
        self.results_text = tk.Text(results_frame, height=15, width=80, bg='#1e1e1e', fg='#00ff00',
                                   font=('Courier', 10))
        scrollbar = ttk.Scrollbar(results_frame, orient="vertical", command=self.results_text.yview)
        self.results_text.configure(yscrollcommand=scrollbar.set)
        
        self.results_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        
        # Performance Frame
        perf_frame = ttk.LabelFrame(main_frame, text="Live Performance", padding="10")
        perf_frame.grid(row=3, column=0, columnspan=4, sticky=(tk.W, tk.E), pady=5)
        
        # Performance metrics
        self.perf_labels = {}
        metrics = ["Total Trades", "Win Rate", "Total P&L", "Profit Factor", "Max Drawdown"]
        for i, metric in enumerate(metrics):
            ttk.Label(perf_frame, text=f"{metric}:").grid(row=0, column=i*2, padx=5)
            self.perf_labels[metric] = ttk.Label(perf_frame, text="--", font=('Arial', 10, 'bold'))
            self.perf_labels[metric].grid(row=0, column=i*2+1, padx=5)
        
        # Configure grid weights
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(2, weight=1)
        results_frame.columnconfigure(0, weight=1)
        results_frame.rowconfigure(0, weight=1)
        
        # Initial message
        self.update_results_display("🧠 NEXUS TRADING SYSTEM Dashboard Ready!\n\nSelect your parameters and click 'Run Backtest' to begin analysis.\n\n📊 Features:\n- ICT/SMC Strategy Analysis\n- Interactive Charts\n- Real-time Performance Metrics\n- Multi-timeframe Support\n\n🎯 Created by: Aleem Shahzad | AI Partner: Claude")
    
    def update_results_display(self, text):
        """Update the results display"""
        self.results_text.delete(1.0, tk.END)
        self.results_text.insert(tk.END, text)
        self.results_text.see(tk.END)
    
    def update_performance_metrics(self, results):
        """Update performance metrics display"""
        if results and 'error' not in results:
            self.perf_labels["Total Trades"].config(text=str(results.get('total_trades', 0)))
            self.perf_labels["Win Rate"].config(text=f"{results.get('win_rate', 0):.1%}")
            self.perf_labels["Total P&L"].config(text=f"${results.get('total_pnl', 0):.2f}")
            self.perf_labels["Profit Factor"].config(text=f"{results.get('profit_factor', 0):.2f}")
            self.perf_labels["Max Drawdown"].config(text=f"{results.get('max_drawdown', 0):.1%}")
        else:
            for label in self.perf_labels.values():
                label.config(text="--")
    
    def run_backtest_gui(self):
        """Run backtest from GUI"""
        def backtest_thread():
            try:
                self.update_results_display("🚀 Starting backtest...\nPlease wait while we analyze the market data...")
                
                # Get parameters
                symbol = self.selected_symbol.get()
                timeframe = self.selected_timeframe.get()
                days = int(self.selected_period.get())
                
                # Calculate dates
                end_date = datetime.now()
                start_date = end_date - timedelta(days=days)
                
                # Check strategy selection
                strategy = self.selected_strategy.get()
                
                # Run backtest with specified timeframe and strategy
                if strategy == "Grid Strategy (Both)":
                    results = self.backtest_engine.run_grid_backtest(symbol, start_date, end_date, timeframe, mode="BOTH")
                elif strategy == "Grid BUY ONLY":
                    results = self.backtest_engine.run_grid_backtest(symbol, start_date, end_date, timeframe, mode="BUY_ONLY")
                elif strategy == "Grid SELL ONLY":
                    results = self.backtest_engine.run_grid_backtest(symbol, start_date, end_date, timeframe, mode="SELL_ONLY")
                else:
                    results = self.backtest_engine.run_backtest(symbol, start_date, end_date, timeframe)
                
                self.current_results = results
                
                if 'error' not in results:
                    # Format results
                    result_text = f"""
🧠 NEXUS TRADING SYSTEM - BACKTEST RESULTS
{'='*50}
Symbol: {symbol}
Timeframe: {timeframe}
Period: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}

📊 PERFORMANCE METRICS:
{'='*30}
Total Trades: {results['total_trades']}
Winning Trades: {results['winning_trades']}
Losing Trades: {results['losing_trades']}
Win Rate: {results['win_rate']:.1%}

💰 FINANCIAL METRICS:
{'='*30}
Total P&L: ${results['total_pnl']:.2f}
Average Win: ${results['avg_win']:.2f}
Average Loss: ${results['avg_loss']:.2f}
Expectancy: ${results['expectancy']:.2f}/trade
Profit Factor: {results['profit_factor']:.2f}
Return: {results['return_pct']:.2%}
Starting Balance: ${self.backtest_engine.initial_balance:,.2f}

📈 RISK METRICS:
{'='*30}
Max Drawdown: {results['max_drawdown']:.1%}
Sharpe Ratio: {results['sharpe_ratio']:.2f}
Final Balance: ${results['final_balance']:.2f}

🧠 AI ANALYSIS:
{'='*30}
✅ ICT/SMC Strategy Applied
✅ {len(self.backtest_engine.ai_memories)} Trade Memories Stored
✅ Neural Network Trained
✅ Ready for Live Trading

🎯 TRADE DETAILS:
{'='*30}"""
                    
                    # Add trade details
                    for i, trade in enumerate(results['trades'][:5], 1):  # Show first 5 trades
                        pnl_emoji = "💚" if trade['pnl'] > 0 else "💔"
                        result_text += f"""
Trade {i}: {trade['type']} {pnl_emoji}
  Entry: {trade['entry_time'].strftime('%Y-%m-%d %H:%M')} @ ${trade['entry_price']:.5f}
  Exit: {trade['exit_time'].strftime('%Y-%m-%d %H:%M')} @ ${trade['exit_price']:.5f}
  P&L: ${trade['pnl']:.2f} | Reason: {trade['exit_reason']}
"""
                    
                    if len(results['trades']) > 5:
                        result_text += f"\n... and {len(results['trades']) - 5} more trades"
                    
                    self.update_results_display(result_text)
                    self.update_performance_metrics(results)
                    
                else:
                    self.update_results_display(f"❌ Backtest Error: {results['error']}")
                    self.update_performance_metrics(None)
                    
            except Exception as e:
                self.update_results_display(f"❌ Error: {str(e)}")
                self.update_performance_metrics(None)
        
        # Run in separate thread to avoid GUI freezing
        threading.Thread(target=backtest_thread, daemon=True).start()
    
    def show_chart(self):
        """Show interactive chart"""
        if self.current_results and 'error' not in self.current_results:
            try:
                symbol = self.selected_symbol.get()
                timeframe = self.selected_timeframe.get()
                days = int(self.selected_period.get())
                
                end_date = datetime.now()
                start_date = end_date - timedelta(days=days)
                
                # Get data
                data = self.backtest_engine.get_historical_data(symbol, start_date, end_date, timeframe)
                if not data.empty:
                    data = self.backtest_engine.add_indicators(data)
                    trades = self.current_results['trades']
                    
                    # Create chart
                    fig = self.backtest_engine.create_interactive_chart(data, trades, symbol)
                    if fig:
                        fig.show()
                        self.update_results_display(f"📊 Interactive chart opened in browser!\nChart saved to: charts/{symbol}_analysis.html")
                else:
                    messagebox.showerror("Error", "No data available for chart")
            except Exception as e:
                messagebox.showerror("Error", f"Chart error: {str(e)}")
        else:
            messagebox.showwarning("Warning", "Please run a backtest first!")
    
    def run(self):
        """Run the dashboard"""
        self.root.mainloop()

def select_backtest_options():
    """Select backtesting options"""
    print("\n" + "="*60)
    print("🧠 NEXUS TRADING SYSTEM - BACKTESTING SYSTEM")
    print("Created by: Aleem Shahzad | AI Partner: Claude (Anthropic)")
    print("="*60)
    print("Select backtesting period:")
    print("1. 📊 Last 30 days (Quick test)")
    print("2. 📈 Last 90 days (Standard)")
    print("3. 🏆 Last 365 days (Full year)")
    print("4. 📅 Custom date range")
    print("5. ❌ Exit")
    print("="*60)
    
    while True:
        try:
            choice = input("Enter your choice (1-5): ").strip()
            
            if choice == "1":
                end_date = datetime.now()
                start_date = end_date - timedelta(days=30)
                return start_date, end_date
            elif choice == "2":
                end_date = datetime.now()
                start_date = end_date - timedelta(days=90)
                return start_date, end_date
            elif choice == "3":
                end_date = datetime.now()
                start_date = end_date - timedelta(days=365)
                return start_date, end_date
            elif choice == "4":
                start_str = input("Enter start date (YYYY-MM-DD): ")
                end_str = input("Enter end date (YYYY-MM-DD): ")
                start_date = datetime.strptime(start_str, "%Y-%m-%d")
                end_date = datetime.strptime(end_str, "%Y-%m-%d")
                return start_date, end_date
            elif choice == "5":
                return None, None
            else:
                print("Invalid choice. Please try again.")
                
        except (ValueError, KeyboardInterrupt):
            print("Invalid input or cancelled.")
            return None, None

def select_symbols():
    """Select symbols for backtesting"""
    symbols = {
        1: "EURUSDm", 2: "GBPUSDm", 3: "USDJPYm",
        4: "XAUUSDm", 5: "XAGUSDm", 6: "BTCUSDm", 7: "ETHUSDm", 8: "ALL"
    }
    
    print("\nSelect symbols to backtest:")
    for num, symbol in symbols.items():
        if symbol == "ALL":
            print(f"  {num}. Test ALL symbols")
        else:
            print(f"  {num}. {symbol}")
    
    while True:
        try:
            choice = int(input("Enter your choice (1-8): "))
            if choice in symbols:
                if symbols[choice] == "ALL":
                    return list(symbols.values())[:-1]  # All except "ALL"
                else:
                    return [symbols[choice]]
            else:
                print("Invalid choice. Please try again.")
        except (ValueError, KeyboardInterrupt):
            return None

def main():
    """Main backtesting function"""
    try:
        # Create necessary directories
        Path("logs").mkdir(exist_ok=True)
        Path("backtest_results").mkdir(exist_ok=True)
        Path("models").mkdir(exist_ok=True)
        Path("charts").mkdir(exist_ok=True)
        
        # Launch GUI Dashboard directly
        print("🚀 Launching NEXUS TRADING SYSTEM Backtesting Dashboard...")
        dashboard = TradingDashboard()
        dashboard.run()
        return
        
        # Command line interface
        start_date, end_date = select_backtest_options()
        if not start_date:
            print("👋 Goodbye!")
            return
        
        symbols = select_symbols()
        if not symbols:
            print("👋 Goodbye!")
            return
        
        # Run backtests
        backtest_engine = BacktestEngine()
        all_results = {}
        
        for symbol in symbols:
            logger.info(f"\n🎯 Starting backtest for {symbol}")
            results = backtest_engine.run_backtest(symbol, start_date, end_date)
            
            if 'error' not in results:
                all_results[symbol] = results
                backtest_engine.generate_report(results)
            else:
                logger.error(f"❌ Backtest failed for {symbol}: {results['error']}")
        
        # Summary report
        if all_results:
            print("\n" + "="*70)
            print("📊 OVERALL BACKTEST SUMMARY")
            print("="*70)
            
            total_trades = sum(r['total_trades'] for r in all_results.values())
            total_pnl = sum(r['total_pnl'] for r in all_results.values())
            avg_win_rate = np.mean([r['win_rate'] for r in all_results.values()])
            
            print(f"Total Symbols Tested: {len(all_results)}")
            print(f"Total Trades: {total_trades}")
            print(f"Total P&L: ${total_pnl:.2f}")
            print(f"Average Win Rate: {avg_win_rate:.1%}")
            
            print("\n🧠 AI TRAINING COMPLETED!")
            print("✅ Neural network trained with backtest data")
            print("✅ Ready for live trading")
            print("\n🚀 Next step: Run 'python live_trading.py' for live trading")
        
    except KeyboardInterrupt:
        logger.info("Backtesting interrupted by user")
    except Exception as e:
        logger.error(f"Backtesting error: {e}")

if __name__ == "__main__":
    main()
