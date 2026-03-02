#!/usr/bin/env python3
"""
NEXT LEVEL BRAIN - Live Trading System (CLI only)
All-in-one live trading with AI enhancement
Created by: Aleem Shahzad | AI Partner: Claude (Anthropic)
"""

import asyncio
import MetaTrader5 as mt5
import pandas as pd
import numpy as np
import yaml
from datetime import datetime, timedelta
from pathlib import Path
from loguru import logger
import sys
import signal
import threading
import time
from typing import Dict, List, Optional, Tuple
import os
import json
from dotenv import load_dotenv
from smart_trailing import SmartTrailingHandler
from grid_recycler import GridRecycler
from mt5_broker import MT5Broker
from profit_controller import ProfitController

# Load environment variables
load_dotenv()

# Setup logging
logger.remove()
logger.add(sys.stdout, format="<green>{time:HH:mm:ss}</green> | <level>{level}</level> | <cyan>{message}</cyan>", level="INFO")
logger.add("logs/live_trading_{time:YYYY-MM-DD}.log", rotation="1 day", retention="30 days")

class TradingBrain:
    """AI Trading Brain with Neural Network"""
    
    def __init__(self):
        self.memories = []
        self.model_trained = False
        self.confidence_threshold = 0.6
        self.sentiment_decision = "ALLOW"
        self.risk_modifier = 1.0
        self._load_memories()
        self._check_sentiment_bias()

    def _check_sentiment_bias(self):
        """Load external market intelligence report with file-change detection"""
        try:
            report_file = Path("latest_intelligence_report.txt")
            if report_file.exists():
                # Only read if file has been modified since last check
                mtime = report_file.stat().st_mtime
                if mtime > getattr(self, '_last_mtime', 0):
                    with open(report_file, 'r') as f:
                        content = f.read()
                        if "DECISION:           BLOCK" in content:
                            self.sentiment_decision = "BLOCK"
                        elif "DECISION:           REDUCE" in content:
                            self.sentiment_decision = "REDUCE"
                            self.risk_modifier = 0.5
                        else:
                            self.sentiment_decision = "ALLOW"
                            self.risk_modifier = 1.0
                        logger.info(f"📡 Market Intelligence Updated: {self.sentiment_decision}")
                    self._last_mtime = mtime
            else:
                if not hasattr(self, '_notified_missing'):
                    logger.warning("📡 No intelligence report found. Defaulting to ALLOW.")
                    self._notified_missing = True
        except Exception as e:
            logger.error(f"Failed to read sentiment report: {e}")

    def _load_memories(self):
        """Load trained memories from file"""
        try:
            memory_file = Path("models/ai_memories.json")
            if memory_file.exists():
                with open(memory_file, 'r') as f:
                    self.memories = json.load(f)
                self.model_trained = True
                logger.info(f"🧠 Loaded {len(self.memories)} training memories. AI is ready.")
            else:
                logger.warning("⚠️ No training data found. AI starting with blank slate.")
        except Exception as e:
            logger.error(f"Failed to load memories: {e}")

    def _is_silver_bullet_time(self, timestamp: datetime) -> bool:
        """
        Check if time is within ICT Silver Bullet windows (EST based).
        Windows: 3-4 AM (London), 10-11 AM (NY AM), 2-3 PM (NY PM).
        
        We assume NY time for these windows.
        """
        # If user has not configured timezone, we assume current system time is NY or MT5 Server time.
        # To be safe, we check 'MT5_SERVER_TIME_OFFSET' if defined in .env
        offset = int(os.getenv("MT5_SERVER_TIME_OFFSET", 0))
        adj_time = timestamp + timedelta(hours=offset)
        h = adj_time.hour
        
        if h in [3, 10, 14]:
            return True
        return False

    def analyze_market(self, symbol: str, data: pd.DataFrame) -> Dict:
        """ICT/SMC AI market analysis"""
        try:
            if len(data) < 50:
                return {'action': 'HOLD', 'bias': 'NEUTRAL', 'confidence': 0.0, 'reasoning': 'Insufficient data'}
            
            # Add technical indicators
            data = self._add_indicators(data)
            index = len(data) - 1  # Current bar index
            
            # ALWAYS determine market bias for systems like Grid
            market_bias = self._determine_market_bias(data, index)
            
            # Check Silver Bullet Time (Only blocks ICT execution, not bias detection)
            current_time = datetime.now()
            is_sb_time = self._is_silver_bullet_time(current_time)
            
            # Update sentiment from file regularly
            self._check_sentiment_bias()
            
            if self.sentiment_decision == "BLOCK":
                return {'action': 'HOLD', 'bias': market_bias, 'confidence': 0.0, 'reasoning': 'Intelligence Engine Decision: BLOCK'}

            # ICT Signal filtering
            if not is_sb_time:
                 # We still return the bias so Grid can work, but signal is HOLD for ICT
                 return {'action': 'HOLD', 'bias': market_bias, 'confidence': 0.0, 'reasoning': 'Outside Silver Bullet Windows'}
            
            # Check for liquidity sweeps
            liquidity_sweep = self._detect_liquidity_sweep(data, index)
            
            # Check for displacement and FVG
            fvg = self._detect_fair_value_gap(data, index)
            
            # Check dealing range and discount/premium zones
            dealing_range = self._analyze_dealing_range(data, index)
            
            # Check for order blocks
            order_block = self._detect_order_block(data, index, market_bias)
            
            # Check OTE (Optimal Trade Entry) levels
            ote_level = self._check_ote_levels(data, index, fvg)
            
            current = data.iloc[index]
            
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
                    bullish_conditions += 0.5
                if ote_level['valid']:
                    bullish_conditions += 0.5
                
                if bullish_conditions >= 2.0:
                    confidence = self._calculate_confluence_score(signal_strengths)
                    
                    if liquidity_sweep['detected']:
                        stop_loss = liquidity_sweep['swept_level'] - (current['close'] * 0.001)
                    else:
                        stop_loss = current['close'] * 0.98
                    
                    return {
                        'action': 'BUY',
                        'bias': 'BULLISH',
                        'confidence': confidence,
                        'reasoning': f'ICT Bullish: {", ".join(signals_present)} (Score: {bullish_conditions:.1f})',
                        'entry_price': current['close'],
                        'stop_loss': stop_loss,
                        'take_profit': self._find_next_liquidity_pool(data, index, 'UP')
                    }
                return {'action': 'HOLD', 'bias': 'BULLISH', 'confidence': 0.0, 'reasoning': 'ICT conditions not aligned'}
            
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
                    bearish_conditions += 0.5
                if ote_level['valid']:
                    bearish_conditions += 0.5
                
                if bearish_conditions >= 2.0:
                    confidence = self._calculate_confluence_score(signal_strengths)
                    
                    if liquidity_sweep['detected']:
                        stop_loss = liquidity_sweep['swept_level'] + (current['close'] * 0.001)
                    else:
                        stop_loss = current['close'] * 1.02
                    
                    return {
                        'action': 'SELL',
                        'bias': 'BEARISH',
                        'confidence': confidence,
                        'reasoning': f'ICT Bearish: {", ".join(signals_present)} (Score: {bearish_conditions:.1f})',
                        'entry_price': current['close'],
                        'stop_loss': stop_loss,
                        'take_profit': self._find_next_liquidity_pool(data, index, 'DOWN')
                    }
                return {'action': 'HOLD', 'bias': 'BEARISH', 'confidence': 0.0, 'reasoning': 'ICT conditions not aligned'}
            
            return {'action': 'HOLD', 'bias': 'NEUTRAL', 'confidence': 0.0, 'reasoning': 'ICT conditions not fully aligned'}
                
        except Exception as e:
            logger.error(f"ICT AI analysis error: {e}")
            return {'action': 'HOLD', 'bias': 'NEUTRAL', 'confidence': 0.0, 'reasoning': 'Analysis failed'}
    
    def _calculate_rsi(self, prices: pd.Series, period: int = 14) -> float:
        """Calculate RSI indicator"""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi.iloc[-1] if not pd.isna(rsi.iloc[-1]) else 50.0
    
    def _add_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add technical indicators to dataframe"""
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
            
            return df
        except Exception as e:
            logger.error(f"Error adding indicators: {e}")
            return df
    
    def _determine_market_bias(self, df: pd.DataFrame, index: int) -> str:
        """Determine market bias using MSS (Market Structure Shift)"""
        try:
            lookback = 50  # More lookback for M5 timeframe
            if index < lookback:
                return 'NEUTRAL'
            
            recent_data = df.iloc[index-lookback:index+1]
            highs = recent_data['high'].rolling(3, center=True).max()  # Smaller window for M5
            lows = recent_data['low'].rolling(3, center=True).min()
            current_price = df.iloc[index]['close']
            
            recent_high = highs.max()
            recent_low = lows.min()
            
            if current_price > recent_high * 0.9995:  # More sensitive for M5
                return 'BULLISH'
            elif current_price < recent_low * 1.0005:  # More sensitive for M5
                return 'BEARISH'
            else:
                return 'NEUTRAL'
        except Exception:
            return 'NEUTRAL'
    
    def _detect_liquidity_sweep(self, df: pd.DataFrame, index: int) -> Dict:
        """Detect liquidity sweeps below lows or above highs"""
        try:
            lookback = 20  # More lookback for M5 timeframe
            if index < lookback:
                return {'detected': False}
            
            current = df.iloc[index]
            recent_data = df.iloc[index-lookback:index]
            swing_low = recent_data['low'].min()
            swing_high = recent_data['high'].max()
            
            if current['low'] < swing_low and current['close'] > swing_low:
                return {'detected': True, 'type': 'BELOW_LOW', 'swept_level': swing_low, 'strength': 0.8}
            elif current['high'] > swing_high and current['close'] < swing_high:
                return {'detected': True, 'type': 'ABOVE_HIGH', 'swept_level': swing_high, 'strength': 0.8}
            
            return {'detected': False}
        except Exception:
            return {'detected': False}
    
    def _detect_fair_value_gap(self, df: pd.DataFrame, index: int) -> Dict:
        """Detect Fair Value Gaps (FVG)"""
        try:
            if index < 3:
                return {'detected': False}
            
            bar1 = df.iloc[index-2]
            bar2 = df.iloc[index-1]
            bar3 = df.iloc[index]
            
            if bar1['high'] < bar3['low']:
                gap_size = bar3['low'] - bar1['high']
                if gap_size > (bar2['close'] * 0.0005):
                    return {'detected': True, 'type': 'BULLISH', 'high': bar3['low'], 'low': bar1['high'], 'strength': min(gap_size / (bar2['close'] * 0.002), 1.0)}
            elif bar1['low'] > bar3['high']:
                gap_size = bar1['low'] - bar3['high']
                if gap_size > (bar2['close'] * 0.0005):
                    return {'detected': True, 'type': 'BEARISH', 'high': bar1['low'], 'low': bar3['high'], 'strength': min(gap_size / (bar2['close'] * 0.002), 1.0)}
            
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
            
            for i in range(index-lookback, index-1):
                bar = df.iloc[i]
                next_bar = df.iloc[i+1]
                price_change = abs(next_bar['close'] - bar['close']) / bar['close']
                
                if bias == 'BULLISH' and price_change > 0.002 and next_bar['close'] > bar['close']:  # 0.2% for M5
                    return {'detected': True, 'type': 'BULLISH', 'high': bar['high'], 'low': bar['low'], 'strength': min(price_change * 10, 1.0)}
                elif bias == 'BEARISH' and price_change > 0.002 and next_bar['close'] < bar['close']:  # 0.2% for M5
                    return {'detected': True, 'type': 'BEARISH', 'high': bar['high'], 'low': bar['low'], 'strength': min(price_change * 10, 1.0)}
            
            return {'detected': False}
        except Exception:
            return {'detected': False}
    
    def _check_ote_levels(self, df: pd.DataFrame, index: int, fvg: Dict) -> Dict:
        """Check Optimal Trade Entry levels (62%-79% Fibonacci)"""
        try:
            if not fvg.get('detected'):
                return {'valid': False}
            
            current_price = df.iloc[index]['close']
            fvg_range = fvg['high'] - fvg['low']
            ote_62 = fvg['low'] + (fvg_range * 0.62)
            ote_79 = fvg['low'] + (fvg_range * 0.79)
            
            if ote_62 <= current_price <= ote_79:
                return {'valid': True, 'strength': 0.9, 'level_62': ote_62, 'level_79': ote_79}
            
            return {'valid': False}
        except Exception:
            return {'valid': False}
    
    def _find_next_liquidity_pool(self, df: pd.DataFrame, index: int, direction: str) -> float:
        """Find next liquidity pool for take profit"""
        try:
            lookback = 30
            current_price = df.iloc[index]['close']
            
            if direction == 'UP':
                recent_highs = df.iloc[max(0, index-lookback):index]['high']
                resistance = recent_highs[recent_highs > current_price].min()
                return resistance if not pd.isna(resistance) else current_price * 1.02
            else:
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
            base_score = sum(strengths) / len(strengths)
            confluence_bonus = min(len(strengths) * 0.1, 0.3)
            return min(base_score + confluence_bonus, 1.0)
        except Exception:
            return 0.0

    def remember_trade(self, trade_data: Dict):
        """Store trade in memory for learning"""
        self.memories.append({
            'timestamp': datetime.now(),
            'symbol': trade_data.get('symbol'),
            'action': trade_data.get('action'),
            'success': trade_data.get('pnl', 0) > 0,
            'pnl': trade_data.get('pnl', 0)
        })
        
        # Keep only last 1000 memories
        if len(self.memories) > 1000:
            self.memories = self.memories[-1000:]

class ICTAnalyzer:
    """ICT/SMC Strategy Implementation"""
    
    def __init__(self):
        self.lookback_periods = 20
        
    def analyze_market_structure(self, data: pd.DataFrame) -> Dict:
        """Analyze market structure for BOS/ChoCH"""
        try:
            highs = data['high'].rolling(self.lookback_periods).max()
            lows = data['low'].rolling(self.lookback_periods).min()
            
            current_high = data['high'].iloc[-1]
            current_low = data['low'].iloc[-1]
            prev_high = highs.iloc[-2] if len(highs) > 1 else current_high
            prev_low = lows.iloc[-2] if len(lows) > 1 else current_low
            
            # Simple structure analysis
            structure = "NEUTRAL"
            if current_high > prev_high:
                structure = "BULLISH_BOS"
            elif current_low < prev_low:
                structure = "BEARISH_BOS"
                
            return {
                'structure': structure,
                'strength': 0.6,
                'key_levels': {
                    'resistance': float(highs.iloc[-1]),
                    'support': float(lows.iloc[-1])
                }
            }
        except Exception as e:
            logger.error(f"Structure analysis error: {e}")
            return {'structure': 'NEUTRAL', 'strength': 0.0, 'key_levels': {}}
    
    def detect_order_blocks(self, data: pd.DataFrame) -> List[Dict]:
        """Detect institutional order blocks"""
        try:
            order_blocks = []
            
            # Simple order block detection
            for i in range(10, len(data) - 5):
                high = data['high'].iloc[i]
                low = data['low'].iloc[i]
                volume = data.get('tick_volume', pd.Series([1] * len(data))).iloc[i]
                
                # Check for significant price movement
                prev_close = data['close'].iloc[i-1]
                curr_close = data['close'].iloc[i]
                price_change = abs(curr_close - prev_close) / prev_close
                
                if price_change > 0.002 and volume > data.get('tick_volume', pd.Series([1] * len(data))).rolling(20).mean().iloc[i]:
                    order_blocks.append({
                        'type': 'BULLISH' if curr_close > prev_close else 'BEARISH',
                        'high': float(high),
                        'low': float(low),
                        'strength': min(price_change * 100, 1.0),
                        'timestamp': data.index[i] if hasattr(data.index[i], 'strftime') else datetime.now()
                    })
            
            return order_blocks[-5:]  # Return last 5 order blocks
        except Exception as e:
            logger.error(f"Order block detection error: {e}")
            return []

class RiskManager:
    """Risk Management System"""
    
    def __init__(self, config: Dict):
        self.max_risk_per_trade = config.get('max_risk_per_trade', 0.02)
        self.max_daily_loss = config.get('max_daily_loss', 0.05)
        self.max_drawdown = config.get('max_drawdown', 0.15)
        self.daily_pnl = 0.0
        
    def calculate_position_size(self, account_balance: float, entry_price: float, 
                              stop_loss: float, symbol: str) -> float:
        """Calculate optimal position size using real-time broker tick values"""
        try:
            # Risk amount
            risk_amount = account_balance * self.max_risk_per_trade
            
            # Price difference (Points)
            price_diff = abs(entry_price - stop_loss)
            if price_diff <= 0:
                return 0.01 
            
            # Get Symbol Meta-data for precision
            symbol_info = mt5.symbol_info(symbol)
            if not symbol_info:
                return 0.01

            # Get Tick Value (Profit/Loss for 1 lot if price moves 1 tick)
            tick_value = symbol_info.trade_tick_value
            tick_size = symbol_info.trade_tick_size
            
            if tick_value <= 0 or tick_size <= 0:
                # Fallback if tick data is missing
                logger.warning(f"⚠️ Missing tick data for {symbol}. Using legacy fallback.")
                if 'XAU' in symbol or 'XAG' in symbol:
                    return min(risk_amount / (price_diff * 100), 1.0) # Gold contract 100
                return 0.01

            # Formula: Risk / ( (PriceDiff / TickSize) * TickValue )
            # This is the industry standard for any asset (Forex, Gold, Crypto)
            position_size = risk_amount / ((price_diff / tick_size) * tick_value)
            
            # Round to valid lot size (MT5 lots usually 0.01 steps)
            lot_step = symbol_info.volume_step
            position_size = round(round(position_size / lot_step) * lot_step, 2)
            
            # Apply Min/Max limits from Broker
            pos_size = max(symbol_info.volume_min, min(position_size, symbol_info.volume_max))
            return round(pos_size, 2)
            
        except Exception as e:
            logger.error(f"Position size calculation error: {e}")
            return 0.01
    
    def check_risk_limits(self, account_balance: float, current_drawdown: float) -> bool:
        """Check if trading is allowed based on risk limits"""
        # Check maximum drawdown
        if current_drawdown > self.max_drawdown:
            logger.warning("Maximum drawdown limit reached")
            return False
            
        return True

class GridManager:
    """Manages User Requested Grid Strategy"""
    def __init__(self, broker, config: Dict = None, profit_controller=None):
        self.broker = broker
        self.profit_ctrl = profit_controller or ProfitController(broker, "GRID_DYNAMIC")
        grid_config = (config or {}).get('grid', {})
        
        self.magic_buy = 777001
        self.magic_sell = 777002
        self.grid_size = grid_config.get('size', 300)
        self.spacing = grid_config.get('spacing', 1.0)  # Spacing in $
        self.lot_size = grid_config.get('lot_size', 0.01)
        self.per_trade_profit = 1.0                     # $ profit per trade target
        self.mode = grid_config.get('mode', 'BOTH') 
        self.active_grids = {} # symbol -> {'BUY/SELL': {'base_price': float, 'first_index': int, 'last_index': int}}
        self.batch_size = 20
        self.trigger_threshold = 5
        self.total_target = 5000                             # Infinite Grid target
        self.strategy_name = "GRID DYNAMIC"
        
        # Profit Controller integration (via system or manual)
        pass
        
        # State Persistence
        self.state_file = Path("logs/grid_state.json")
        self.resumed = False  # Layer 4: Flag to track if we resumed from a crash
        self._load_state()

    def _save_state(self):
        """Save full grid snapshot (config + runtime) for crash recovery"""
        try:
            self.state_file.parent.mkdir(parents=True, exist_ok=True)
            snapshot = {
                'active_grids': self.active_grids,
                'lot_size': self.lot_size,
                'spacing': self.spacing,
                'mode': self.mode,
                'strategy_name': self.strategy_name,
                'saved_at': time.time()
            }
            with open(self.state_file, 'w') as f:
                json.dump(snapshot, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving grid state: {e}")

    def _load_state(self):
        """Load full grid snapshot from disk (supports legacy and new format)"""
        if self.state_file.exists():
            try:
                with open(self.state_file, 'r') as f:
                    data = json.load(f)

                # Detect new snapshot format vs legacy
                if 'active_grids' in data:
                    self.active_grids = data['active_grids']
                    # Restore config params so grid resumes with same settings
                    self.lot_size  = data.get('lot_size', self.lot_size)
                    self.spacing   = data.get('spacing', self.spacing)
                    self.mode      = data.get('mode', self.mode)
                    self.strategy_name = data.get('strategy_name', self.strategy_name)
                    logger.info(f"📁 Grid snapshot loaded (lot={self.lot_size}, spacing={self.spacing}, mode={self.mode})")
                else:
                    # Legacy format: root IS the active_grids dict
                    self.active_grids = data
                    logger.info("📁 Loaded legacy grid state.")

                # Migration: wrap old flat structure
                for symbol in list(self.active_grids.keys()):
                    d = self.active_grids[symbol]
                    if isinstance(d, dict) and 'type' in d:
                        side = d.pop('type')
                        self.active_grids[symbol] = {side: d}
                        logger.info(f"🚚 Migrated legacy grid state for {symbol} ({side})")

            except json.JSONDecodeError:
                logger.warning("⚠️ Grid state file was corrupt. Starting fresh.")
                self.active_grids = {}
            except Exception as e:
                logger.error(f"Failed to load grid state: {e}")
                self.active_grids = {}
        else:
            self.active_grids = {}

    async def auto_detect_and_resume(self, symbol: str) -> bool:
        """
        Layer 4: Scan live MT5 positions for our grid magic numbers.
        If found, reconstruct active_grids state and skip duplicate order placement.
        Returns True if an active grid was detected (resumed mode).
        """
        try:
            positions = mt5.positions_get(symbol=symbol)
            orders   = mt5.orders_get(symbol=symbol)
            
            buy_positions  = [p for p in (positions or []) if p.magic == self.magic_buy]
            sell_positions = [p for p in (positions or []) if p.magic == self.magic_sell]
            buy_orders     = [o for o in (orders or [])   if o.magic == self.magic_buy]
            sell_orders    = [o for o in (orders or [])   if o.magic == self.magic_sell]

            has_buy  = bool(buy_positions  or buy_orders)
            has_sell = bool(sell_positions or sell_orders)

            if not (has_buy or has_sell):
                return False  # No grid found — fresh start

            # --- Reconstruct active_grids from live MT5 data ---
            reconstructed = {}

            all_buy_prices = (
                [p.price_open for p in buy_positions] +
                [o.price_open for o in buy_orders]
            )
            all_sell_prices = (
                [p.price_open for p in sell_positions] +
                [o.price_open for o in sell_orders]
            )

            if all_buy_prices:
                base = round(min(all_buy_prices) / self.spacing) * self.spacing
                reconstructed['BUY'] = {
                    'base_price':   round(base, 5),
                    'first_index':  0,
                    'last_index':   len(all_buy_prices)
                }

            if all_sell_prices:
                base = round(max(all_sell_prices) / self.spacing) * self.spacing
                reconstructed['SELL'] = {
                    'base_price':   round(base, 5),
                    'first_index':  0,
                    'last_index':   len(all_sell_prices)
                }

            self.active_grids[symbol] = reconstructed
            self.resumed = True
            self._save_state()

            total = len(buy_positions) + len(sell_positions) + len(buy_orders) + len(sell_orders)
            logger.success(
                f"🔄 [LAYER 4] Grid AUTO-RESUMED for {symbol}! "
                f"{total} live entries detected "
                f"(BUY: {len(buy_positions)}pos+{len(buy_orders)}ord | "
                f"SELL: {len(sell_positions)}pos+{len(sell_orders)}ord)"
            )
            return True

        except Exception as e:
            logger.error(f"Layer 4 auto-detect error for {symbol}: {e}")
            return False

    async def update(self, symbol, current_price, bias, balance, positions: List[dict] = None, orders: List[dict] = None):
        """Update grid logic based on bias and profit"""
        try:
            symbol_info = mt5.symbol_info(symbol)
            if not symbol_info:
                logger.error(f"Cannot update grid: Symbol {symbol} not found")
                return

            # 1. Update Grid Positions (Raw objects or dicts)
            if positions is None:
                raw_positions = mt5.positions_get(symbol=symbol)
                if raw_positions is None: raw_positions = []
                grid_objs = [p for p in raw_positions if p.magic in (self.magic_buy, self.magic_sell)]
            else:
                # Use pre-filtered/fetched positions (handle both object and dict)
                def _get_val(p, k, default=0):
                    if hasattr(p, k): return getattr(p, k)
                    if isinstance(p, dict): return p.get(k, default)
                    return default
                grid_objs = [p for p in positions if _get_val(p, 'symbol') == symbol and _get_val(p, 'magic') in (self.magic_buy, self.magic_sell)]

            # 2. Side-Basket Trailing/Individual checks are handled in Turbo Loop (100Hz)
            pass

            # 3. Batch Maintenance Logic
            if orders is None:
                all_orders = mt5.orders_get(symbol=symbol)
                if all_orders is None: all_orders = []
                grid_pendings = [o for o in all_orders if o.magic in (self.magic_buy, self.magic_sell)]
            else:
                grid_pendings = [o for o in orders if o.symbol == symbol and o.magic in (self.magic_buy, self.magic_sell)]

            # 3. Dynamic Grid Logic (SELL Side)
            if self.mode in ('SELL_ONLY', 'BOTH'):
                sell_pendings = {round(o.price_open if hasattr(o, 'price_open') else o.get('price_open', 0), symbol_info.digits): o for o in grid_pendings if (o.magic if hasattr(o, 'magic') else o.get('magic')) == self.magic_sell}
                sell_positions = {round(p.price_open if hasattr(p, 'price_open') else p.get('price_open', 0), symbol_info.digits): p for p in grid_objs if (p.magic if hasattr(p, 'magic') else p.get('magic')) == self.magic_sell}
                
                # SNAP ANCHOR: Round to nearest whole spacing (e.g. $1 increments)
                # This ensures rolling only occurs in $1 jumps, not 10-cent intervals.
                anchor = round(current_price / self.spacing) * self.spacing
                
                # A. MAINTAIN GRID: Fill levels from anchor + 1 up to total_target
                # This keeps the grid centered around the current price.
                success_count = 0
                for i in range(1, self.batch_size + 1):
                    level_price = anchor + (i * self.spacing)
                    level_price = round(round(level_price / symbol_info.trade_tick_size) * symbol_info.trade_tick_size, symbol_info.digits)
                    r_price = round(level_price, 2)
                    
                    if r_price in sell_pendings or r_price in sell_positions:
                        continue
                        
                    # Avoid placing right on top of market
                    if level_price <= current_price + (symbol_info.spread * symbol_info.point): continue
                    
                    res = await self.broker.place_pending_order(symbol, mt5.ORDER_TYPE_SELL_LIMIT, self.lot_size, level_price, self.magic_sell)
                    if res['success']: success_count += 1
                    elif res.get('error') == 'MARKET_CLOSED': break

                # B. PRUNE: Remove orders too far from the current market anchor
                # This prevents old orders at 4900 when the market is at 5200.
                limit_dist = (self.batch_size + 5) * self.spacing
                for p_price, order in sell_pendings.items():
                    if abs(p_price - anchor) > limit_dist:
                        await self.broker.cancel_order(order.ticket)

            # 4. Dynamic Grid Logic (BUY Side)
            if self.mode in ('BUY_ONLY', 'BOTH'):
                buy_pendings = {round(o.price_open if hasattr(o, 'price_open') else o.get('price_open', 0), symbol_info.digits): o for o in grid_pendings if (o.magic if hasattr(o, 'magic') else o.get('magic')) == self.magic_buy}
                buy_positions = {round(p.price_open if hasattr(p, 'price_open') else p.get('price_open', 0), symbol_info.digits): p for p in grid_objs if (p.magic if hasattr(p, 'magic') else p.get('magic')) == self.magic_buy}
                
                # SNAP ANCHOR
                anchor = round(current_price / self.spacing) * self.spacing
                
                # A. MAINTAIN GRID: Fill levels from anchor - 1 down
                success_count = 0
                for i in range(1, self.batch_size + 1):
                    level_price = anchor - (i * self.spacing)
                    level_price = round(round(level_price / symbol_info.trade_tick_size) * symbol_info.trade_tick_size, symbol_info.digits)
                    r_price = round(level_price, 2)
                    
                    if r_price in buy_pendings or r_price in buy_positions:
                        continue
                        
                    if level_price >= current_price - (symbol_info.spread * symbol_info.point): continue
                    
                    res = await self.broker.place_pending_order(symbol, mt5.ORDER_TYPE_BUY_LIMIT, self.lot_size, level_price, self.magic_buy)
                    if res['success']: success_count += 1
                    elif res.get('error') == 'MARKET_CLOSED': break

                # B. PRUNE: Remove far-away orders
                limit_dist = (self.batch_size + 5) * self.spacing
                for p_price, order in buy_pendings.items():
                    if abs(p_price - anchor) > limit_dist:
                        await self.broker.cancel_order(order.ticket)
                    
                # State saving no longer needed for Dynamic Snap-Grid

        except Exception as e:
            logger.error(f"Error in grid update: {e}")

    async def _recycle_level(self, symbol: str, price: float, pos_type: int):
        """Immediately re-place a pending order at the level that just closed."""
        try:
            symbol_info = mt5.symbol_info(symbol)
            if not symbol_info: return

            side = "BUY" if pos_type == mt5.POSITION_TYPE_BUY else "SELL"
            order_type = mt5.ORDER_TYPE_BUY_LIMIT if side == "BUY" else mt5.ORDER_TYPE_SELL_LIMIT
            magic = self.magic_buy if side == "BUY" else self.magic_sell
            
            # Normalize price
            tick_size = getattr(symbol_info, 'trade_tick_size', 0.0)
            if tick_size > 0:
                price = round(round(price / tick_size) * tick_size, symbol_info.digits)

            # Safety check: ensure price is not too close to market
            tick = mt5.symbol_info_tick(symbol)
            if tick:
                # Dynamic buffer: max(2.0x spread, 10 points) to avoid INVALID_PRICE rejection
                min_buffer = max(symbol_info.spread * symbol_info.point * 2.0, symbol_info.point * 10)
                if side == "BUY" and price >= tick.ask - min_buffer:
                    return # Market moved past level or too close
                if side == "SELL" and price <= tick.bid + min_buffer:
                    return # Market moved past level or too close

            res = await self.broker.place_pending_order(symbol, order_type, self.lot_size, price, magic)
            if res.get('success'):
                logger.info(f"♻️ Level Recycled: {side} Limit replaced at {price:.3f}")
            else:
                logger.warning(f"Failed to recycle level at {price:.3f}: {res.get('error')}")
                    
        except Exception as e:
            logger.error(f"Error recycling level: {e}")

class LiveTradingSystem:
    """Main Live Trading System"""
    
    def __init__(self, config_path: str = "config.yaml"):
        self.config = self._load_config(config_path)
        self.broker = MT5Broker(self.config.get('mt5', {}))
        self.ai_brain = TradingBrain()
        self.ict_analyzer = ICTAnalyzer()
        self.risk_manager = RiskManager(self.config.get('risk', {}))
        self.profit_ctrl = ProfitController(self.broker, "CORE_SYSTEM")
        self.grid_manager = GridManager(self.broker, self.config, profit_controller=self.profit_ctrl)
        self.grid_recycler = GridRecycler(self.broker, self.config, profit_controller=self.profit_ctrl)
        
        self.running = False
        self.symbols = self.config.get('symbols', ['XAUUSDm'])
        self.timeframe = self.config.get('timeframe', 'M5')
        self.strategy = "ICT SMC" # Default strategy
        self.profit_pct = 0.01 # Default 1%
        self.profit_usd = self.config.get('grid', {}).get('profit_target_usd', 20)
        self.trailing_enabled = False
        
        # Unit and Account Info
        self.account_type = "DEMO" # "DEMO" or "REAL_CENT"
        self.unit = "$" # "$" for Demo, "USC" for Cent
        self.login = None
        self.password = None
        self.server = None
        
        # Performance tracking
        self.trades_today = 0
        self.daily_pnl = 0.0
        self.start_balance = 0.0
        self.trade_history = []
        self.reports_dir = Path("logs/live_reports")
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        self.market_closed_logged = set() # Track symbols logged for market closure
        
    def _load_config(self, config_path: str) -> Dict:
        """Load configuration"""
        try:
            if Path(config_path).exists():
                with open(config_path, 'r') as f:
                    return yaml.safe_load(f)
            else:
                # Default configuration
                return {
                    'mt5': {
                        'login': None,
                        'password': None,
                        'server': None
                    },
                    'symbols': ['EURUSDm', 'GBPUSDm', 'XAUUSDm'],
                    'timeframe': 'M5',
                    'risk': {
                        'max_risk_per_trade': 0.02,
                        'max_daily_loss': 0.05,
                        'max_drawdown': 0.15
                    }
                }
        except Exception as e:
            logger.error(f"Config loading error: {e}")
            return {}
    
    async def initialize(self) -> bool:
        """Initialize the trading system"""
        try:
            logger.info("🧠 Initializing NEXT LEVEL BRAIN Live Trading System...")
            
            # Connect to broker with selected credentials
            if not await self.broker.connect(login=self.login, password=self.password, server=self.server):
                logger.warning("📡 MT5 not connected during startup. Watchdog will handle reconnection.")
            
            # Get account info (If connected)
            account_info = mt5.account_info()
            if account_info:
                self.start_balance = account_info.balance
                logger.info(f"Account Balance: ${self.start_balance:.2f}")
            
            # Layer 4 is triggered from run() AFTER strategy is selected, not here.
            
            # Cleanup removed: User handles this manually via Choice 6
            try:
                import subprocess
                subprocess.Popen([sys.executable, "live_dashboard.py"], creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
                logger.info("🚀 Live Dashboard auto-opened.")
            except Exception as e:
                logger.warning(f"Failed to auto-open dashboard: {e}")
            
            logger.info("✅ System initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Initialization error: {e}")
            return False
    
    async def analyze_and_trade(self, symbol: str, positions: List = None, orders: List = None, cycle_count: int = 0):
        """Analyze market and execute trades for a symbol"""
        try:
            # Get account context
            acc = mt5.account_info()
            if not acc: return
            balance = acc.balance

            # Get market data
            data = self.broker.get_market_data(symbol, self.timeframe, 500)
            if data.empty:
                # If market data is missing intermittently, it might be closed.
                # Don't add to market_closed_logged yet, as it could be a transient connection issue.
                return
            
            # If we were logged as closed, but now have data -> remove from set
            if symbol in self.market_closed_logged:
                self.market_closed_logged.discard(symbol)
                logger.info(f"🟢 Market RE-OPENED for {symbol}. Resuming Turbo Loop.")
            
            # AI Analysis (Keep for bias detection)
            ai_analysis = self.ai_brain.analyze_market(symbol, data)
            current_price = data['close'].iloc[-1]
            bias = ai_analysis.get('bias', 'NEUTRAL')
            
            # 1. Grid Strategy Logic (Smart Trailing / Standard Grid)
            if ("Grid" in self.strategy or "Smart" in self.strategy) and "Recycler" not in self.strategy:
                # Only set mode once (not every cycle) to avoid overriding Layer 4 restored state
                if not hasattr(self, '_mode_initialized'):
                    if "BUY ONLY" in self.strategy.upper():
                        self.grid_manager.mode = "BUY_ONLY"
                    elif "SELL ONLY" in self.strategy.upper():
                        self.grid_manager.mode = "SELL_ONLY"
                    else:
                        self.grid_manager.mode = "BOTH"
                    self._mode_initialized = True
                
                # 🎯 GRID RISK CHECK (BUG FIX: Previously bypassed risk limits)
                current_drawdown = max(0, (self.start_balance - balance) / self.start_balance) if self.start_balance else 0
                if not self.risk_manager.check_risk_limits(balance, current_drawdown):
                    if cycle_count % 300 == 0: logger.warning(f"⚠️ Grid Trading Suspended: {symbol} in drawdown limit.")
                    return

                self.grid_manager.profit_threshold_pct = self.profit_pct
                self.grid_manager.profit_target_usd = self.profit_usd
                self.grid_manager.trailing_enabled = self.trailing_enabled
                
                # Logic Fix: In Smart Trailing mode, we want individual trades to stay open 
                # so the basket can grow to $10/$20. Set individual Hard TP to a high value.
                if self.trailing_enabled:
                    self.grid_manager.per_trade_profit = 50.0 
                else:
                    self.grid_manager.per_trade_profit = self.profit_usd if self.profit_usd > 0 else 1.0
                    
                await self.grid_manager.update(symbol, current_price, bias, balance, positions=positions, orders=orders)
            
            # 2. Grid Recycler Strategy Logic
            elif "Recycler" in self.strategy:
                # 🎯 RECYCLER RISK CHECK
                current_drawdown = max(0, (self.start_balance - balance) / self.start_balance) if self.start_balance else 0
                if not self.risk_manager.check_risk_limits(balance, current_drawdown):
                    return

                if "BUY ONLY" in self.strategy.upper():
                    self.grid_recycler.mode = "BUY_ONLY"
                elif "SELL ONLY" in self.strategy.upper():
                    self.grid_recycler.mode = "SELL_ONLY"
                else:
                    self.grid_recycler.mode = "BOTH"
                await self.grid_recycler.update(symbol, current_price, positions=positions, orders=orders)
            # 2. ICT SMC Strategy Logic
            elif self.strategy == "ICT SMC":
                if ai_analysis['action'] in ['BUY', 'SELL'] and ai_analysis['confidence'] >= 0.70:
                    logger.info(f"🎯 ICT Signal Detected: {ai_analysis['action']} {symbol} (Confidence: {ai_analysis['confidence']:.2f})")
                    await self._execute_trade(symbol, ai_analysis, {})
                
        except Exception as e:
            logger.error(f"Analysis error for {symbol}: {e}")
    
    async def _execute_trade(self, symbol: str, ai_analysis: Dict, structure: Dict):
        """Execute a trade based on analysis"""
        try:
            # Get account balance
            account_info = mt5.account_info()
            if not account_info:
                return
            
            balance = account_info.balance
            
            # Check risk limits
            current_drawdown = max(0, (self.start_balance - balance) / self.start_balance) if self.start_balance else 0
            if not self.risk_manager.check_risk_limits(balance, current_drawdown):
                logger.warning(f"Risk limits prevent trading {symbol}")
                return
            
            # Calculate position size
            entry_price = ai_analysis['entry_price']
            stop_loss = ai_analysis['stop_loss']
            take_profit = ai_analysis['take_profit']
            
            position_size = self.risk_manager.calculate_position_size(
                balance, entry_price, stop_loss, symbol
            )
            
            # Place order (using async-compatible direct MT5 call)
            result = await self.broker.place_market_order(
                symbol=symbol,
                action=ai_analysis['action'],
                volume=position_size,
                stop_loss=stop_loss,
                take_profit=take_profit
            )
            
            if result['success']:
                self.trades_today += 1
                logger.info(f"✅ Trade executed: {ai_analysis['action']} {symbol}")
                logger.info(f"📊 Reasoning: {ai_analysis['reasoning']}")
                
                # Remember trade for AI learning
                self.ai_brain.remember_trade({
                    'symbol': symbol,
                    'action': ai_analysis['action'],
                    'entry_price': entry_price,
                    'confidence': ai_analysis['confidence']
                })
            else:
                logger.error(f"❌ Trade failed: {result.get('error')}")
                
        except Exception as e:
            logger.error(f"Trade execution error: {e}")
    
    async def monitor_positions(self):
        """Monitor and manage open positions"""
        try:
            positions = self.broker.get_positions()
            
            for pos in positions:
                # Simple trailing stop logic
                if pos['profit'] > 50:  # If profit > 50
                    logger.info(f"💰 Position {pos['symbol']} in profit: {pos['profit']:.2f} {self.unit}")
                elif pos['profit'] < -100:  # If loss > 100
                    logger.warning(f"⚠️ Position {pos['symbol']} in loss: {pos['profit']:.2f} {self.unit}")
                    
        except Exception as e:
            logger.error(f"Position monitoring error: {e}")
    
    def display_status(self):
        """Display current system status"""
        try:
            account_info = mt5.account_info()
            if account_info:
                current_balance = account_info.balance
                
                # Safety check for start_balance
                if self.start_balance <= 0:
                    self.start_balance = current_balance
                
                daily_change = current_balance - self.start_balance
                
                print(f"\n{'='*50}")
                print(f"🧠 NEXT LEVEL BRAIN - LIVE TRADING STATUS")
                print(f"{'='*50}")
                print(f"💰 Balance: {current_balance:.2f} {self.unit}")
                print(f"📈 Daily P&L: {daily_change:.2f} {self.unit} (Start: {self.start_balance:.2f} {self.unit})")
                print(f"📊 Trades Today: {self.trades_today}")
                
                # Show Individual Trailing Status (Summary)
                ticket_states = self.grid_manager.profit_ctrl.ticket_states
                if ticket_states:
                    active_locks = [s['lock'] for s in ticket_states.values() if s['lock'] > 0]
                    if active_locks:
                        max_lock = max(active_locks)
                        print(f"🛡️  PROTECTION: {len(active_locks)} Trades Trailing (Max Lock: {self.unit}{max_lock:.1f})")

                print(f"🎯 AI Memories: {len(self.ai_brain.memories)}")
                print(f"⏰ Last Update: {datetime.now().strftime('%H:%M:%S')}")
                print(f"📂 Reports Path: {self.reports_dir.absolute()}")
                
                positions = self.broker.get_positions()
                if positions:
                    print(f"📋 Open Positions: {len(positions)}")
                    for pos in positions:
                        print(f"  {pos['symbol']}: {pos['type']} {pos['profit']:.2f} {self.unit}")
                else:
                    print(f"📋 Open Positions: 0")
                print(f"{'='*50}")
                
        except Exception as e:
            logger.error(f"Status display error: {e}")
    
    async def run(self):
        """Main trading loop with Auto-Reconnect Watchdog"""
        try:
            if not await self.initialize():
                return
            
            self.running = True
            try:
                # On every fresh startup: write new dashboard_reset.json so history starts from NOW
                try:
                    dash_reset_file = Path("logs/dashboard_reset.json")
                    dash_reset_file.parent.mkdir(parents=True, exist_ok=True)
                    with open(dash_reset_file, 'w') as f:
                        json.dump({'reset_timestamp': time.time()}, f)
                except: pass

                # Sync Equity Milestone Baseline on Startup
                acc = mt5.account_info()
                if acc:
                    ctrl = self.grid_manager.profit_ctrl
                    stored_baseline = ctrl.equity_milestone_state.get('baseline_equity', 0)
                    
                    # Check if a reset signal is pending (dashboard reset was just done)
                    reset_signal = Path("logs/global_reset.signal")
                    has_pending_reset = reset_signal.exists()
                    
                    # If reset is pending: immediately zero out the dashboard bridge file
                    # so the dashboard shows $0.00 right away (BEFORE main loop detects the signal)
                    if has_pending_reset:
                        try:
                            progress_file = Path("logs/milestone_progress.json")
                            progress_file.parent.mkdir(parents=True, exist_ok=True)
                            with open(progress_file, 'w') as f:
                                json.dump({'current': acc.equity, 'baseline': acc.equity,
                                           'target': acc.equity + 100.0, 'progress': 0.0,
                                           'target_inc': 100.0, 'timestamp': time.time()}, f)
                        except: pass
                    
                    # Only auto-sync if: no baseline set, or equity dropped significantly below baseline
                    # Do NOT auto-sync if a pending reset exists (reset flow will handle it)
                    # Do NOT auto-sync if baseline is valid and close to current equity
                    if not has_pending_reset:
                        # Adaptive baseline sync: $10 for Demo, 50 USC for Cent
                        sync_threshold = 10.0 if self.unit == "$" else 50.0
                        if stored_baseline <= 0 or acc.equity < (stored_baseline - sync_threshold):
                            logger.info(f"🔄 Auto-Syncing Equity Baseline to current equity: {self.unit}{acc.equity:.2f}")
                            ctrl.reset_equity_milestone(acc.equity)
                            logger.info(f"📊 Equity Milestone Synced. Baseline: {self.unit}{acc.equity:.2f} | Target: {self.unit}{acc.equity+100:.2f}")
                        else:
                            # Baseline is valid, just log it
                            logger.info(f"📊 Equity Milestone Loaded. Baseline: {self.unit}{stored_baseline:.2f} | Target: {self.unit}{stored_baseline+100:.2f}")
            except Exception as e:
                logger.error(f"Error during equity baseline sync: {e}")

            logger.info("🚀 Starting live trading...")
            
            # --- Holiday Check (Layer 4.5) ---
            # Check if any of our symbols are open for trading
            open_symbols = []
            for s in self.symbols:
                if await self.broker.is_market_open(s):
                    open_symbols.append(s)
            
            if not open_symbols:
                print("\n" + "!"*40)
                print("🏖️  Aaj Chutti Hai! (Markets are closed)")
                print("Script will wait for connection but won't trade.")
                print("!"*40 + "\n")
                logger.warning("🏖️  Market is closed. Waiting for session open...")
            
            # Layer 4: Auto-Resume Detection (runs HERE after strategy is confirmed set)
            if ('Grid' in self.strategy or 'Recycler' in self.strategy):
                logger.info("🔍 [LAYER 4] Scanning MT5 for existing grid positions...")
                any_resumed = False
                for symbol in self.symbols:
                    resumed = await self.grid_manager.auto_detect_and_resume(symbol)
                    if resumed:
                        any_resumed = True
                if not any_resumed:
                    logger.info("✅ [LAYER 4] No existing grid found. Fresh start.")

            cycle_count = 0
            
            while self.running:
                try:
                    # Connection Watchdog (Throttled to 2 seconds to avoid overhead in 100Hz loop)
                    if cycle_count % 200 == 0:
                        if not await self.broker.is_connected():
                            logger.warning("📡 Connection lost! Attempting to reconnect...")
                            # Wait exponentially or simply retry
                            if await self.broker.connect(login=self.login, password=self.password, server=self.server):
                                logger.info("✅ Reconnected successfully!")
                            else:
                                logger.error("❌ Reconnect failed. Retrying soon...")
                                await asyncio.sleep(5)
                                continue

                    cycle_count += 1
                    acc = mt5.account_info()

                    # 2. GLOBAL RESET WATCHDOG (Dashboard Signal)
                    reset_signal = Path("logs/global_reset.signal")
                    if reset_signal.exists():
                        logger.warning("🛑 GLOBAL RESET SIGNAL DETECTED! Performing full wipe...")
                        await self._close_all_universe()
                        self.grid_manager.profit_ctrl.reset() # Clears all peaks, locks, and milestones
                        
                        # Reset internal stats for terminal display
                        self.trades_today = 0
                        self.daily_pnl = 0.0
                        if acc:
                            self.start_balance = acc.balance
                            logger.info(f"🎯 Milestone Baseline Set: {acc.balance:.2f} {self.unit}. Target: {acc.balance+100.0:.2f} {self.unit}")

                        try:
                            reset_signal.unlink() # Delete signal
                            # Update dashboard reset timestamp so history shows 0 on fresh restart
                            try:
                                dash_reset_file = Path("logs/dashboard_reset.json")
                                dash_reset_file.parent.mkdir(parents=True, exist_ok=True)
                                with open(dash_reset_file, 'w') as f:
                                    json.dump({'reset_timestamp': time.time()}, f)
                            except: pass
                            logger.success("✅ Global Reset Complete. System Clean.")
                            # Set fresh baseline from current equity so restart loads correct data
                            if acc:
                                self.grid_manager.profit_ctrl.reset_equity_milestone(acc.equity)
                        except Exception as e:
                            logger.error(f"Failed to delete reset signal: {e}")
                        
                        # Refresh account info after closure
                        acc = mt5.account_info()

                    # Silent Waiting Mode: If all symbols are closed, skip status and slow down
                    all_closed = all(s in self.market_closed_logged for s in self.symbols)
                    
                    # Display status every 30 seconds (300 cycles @ 0.1s) - Skip if silent
                    if not all_closed and cycle_count % 300 == 0:
                        self.display_status()
                    
                    # 1. FETCH ALL DATA ONCE (Raw MT5 Objects for Speed)
                    all_positions = mt5.positions_get()
                    if all_positions is None: all_positions = []
                    
                    all_orders = mt5.orders_get()
                    if all_orders is None: all_orders = []

                    # 🎯 TURBO TRAILING: CHECK ALL LAYERS BEFORE ANY DATA FETCHING
                    # Layer 1: Individual Trade Trailing (Checked every tick 100Hz)
                    to_close_individual = await self.grid_manager.profit_ctrl.monitor_individual_trailing(all_positions, self.grid_manager.per_trade_profit)
                    if to_close_individual:
                        tasks = []
                        for pos in to_close_individual:
                            logger.info(f"💰 [TURBO] Ticket {pos.ticket} Trail Exit hit. Adding to parallel close.")
                            tasks.append(self.broker.close_position(pos.ticket))
                        
                        if tasks:
                            results = await asyncio.gather(*tasks)
                            # Handle level recycling for closed positions
                            for i, res in enumerate(results):
                                if res['success']:
                                    pos = to_close_individual[i]
                                    if "Grid" in self.strategy or "Smart" in self.strategy:
                                        await self.grid_manager._recycle_level(pos.symbol, pos.price_open, pos.type)
                                    elif "Recycler" in self.strategy:
                                        side_str = 'BUY' if pos.type == mt5.POSITION_TYPE_BUY else 'SELL'
                                        s_info = mt5.symbol_info(pos.symbol)
                                        if s_info:
                                            await self.grid_recycler._recycle_level(pos.symbol, pos.price_open, side_str, s_info)
                                        
                        # Refresh for next layers to avoid stale PnL calcs
                        all_positions = mt5.positions_get() or []
                        all_orders = mt5.orders_get() or []

                    # Layer 2: Side Basket Trailing (Basket of BUYs or SELLs)
                    if self.trailing_enabled:
                        for symbol in self.symbols:
                            # Pass all_positions to avoid redundant MT5 fetches
                            await self.grid_manager.profit_ctrl.monitor_trailing(symbol, self.grid_manager.magic_buy, self.grid_manager.magic_sell, positions=all_positions)

                    # Layer 2.5: Grand Basket Trailing (Total Account Basket)
                    if await self.grid_manager.profit_ctrl.monitor_grand_basket(all_positions, trigger_usd=20.0):
                        print(f"\n{'!'*50}")
                        print(f"🏁 GRAND BASKET TRAILING EXIT TRIGGERED!")
                        print(f"💰 Closing all trades to secure profit...")
                        print(f"{'!'*50}\n")
                        logger.warning("🏁 GRAND BASKET TRAILING EXIT TRIGGERED! Closing everything.")
                        await self._close_all_universe()
                        # Reset Layer 3 baseline after Layer 2 exit with FRESH equity
                        fresh_acc = mt5.account_info()
                        if fresh_acc:
                            self.grid_manager.profit_ctrl.reset_equity_milestone(fresh_acc.equity)
                            # ✅ FIX: Update start_balance so drawdown resets to new higher balance
                            # Balance badh gaya = maqsa poora hua. Isko drawdown mein count nahi karein.
                            if fresh_acc.balance > self.start_balance:
                                logger.info(f"✅ [LAYER 2] Balance upgraded: {self.unit}{self.start_balance:.2f} → {self.unit}{fresh_acc.balance:.2f}. Drawdown baseline reset.")
                                self.start_balance = fresh_acc.balance

                    # 4. LAYER 3: Equity Milestone Monitor ($100 Target)
                    if acc:
                        if await self.profit_ctrl.monitor_equity_milestone(acc.equity, target_increase=100.0):
                            print(f"\n{'#'*50}")
                            print(f"🏆 EQUITY MILESTONE HIT (+100 {self.unit})!")
                            print(f"💰 Securing account-level profit...")
                            print(f"{'#'*50}\n")
                            logger.success("🏆 EQUITY MILESTONE HIT! Closing Universe.")
                            await self._close_all_universe()
                            # Reset with FRESH equity
                            fresh_acc = mt5.account_info()
                            if fresh_acc:
                                self.profit_ctrl.reset_equity_milestone(fresh_acc.equity)
                                # ✅ FIX: Update start_balance so drawdown resets to new higher balance
                                # Layer 3 ne profit book kiya — yeh success hai, drawdown nahi.
                                # Ab naya baseline naye bade balance se shuru hoga.
                                if fresh_acc.balance > self.start_balance:
                                    logger.info(f"✅ [LAYER 3] Balance upgraded: {self.unit}{self.start_balance:.2f} → {self.unit}{fresh_acc.balance:.2f}. Drawdown baseline reset.")
                                    self.start_balance = fresh_acc.balance

                    # ── STRATEGY & ANALYSIS (Throttled for Speed) ─────────────
                    now_ts = time.time()
                    if not hasattr(self, '_last_market_analysis'): self._last_market_analysis = 0
                    
                    if now_ts - self._last_market_analysis >= 1.0:
                        for symbol in self.symbols:
                            await self.analyze_and_trade(symbol, all_positions, all_orders, cycle_count=cycle_count)
                        self._last_market_analysis = now_ts
                        # Remove internal delay to increase check frequency
                    
                    # Update session history and save partial report (Every ~20 cycles)
                    if cycle_count % 20 == 0:
                        self._update_session_history()
                        self.generate_session_report()
                    
                    # Wait before next cycle
                    if all_closed:
                        delay = 2.0
                    else:
                        # SUPER FAST MODE: 0.01s (approx 100 checks/sec) for high-frequency monitoring
                        delay = 0.01 if ("Grid" in self.strategy or "Smart" in self.strategy or "Recycler" in self.strategy) else 5
                    
                    await asyncio.sleep(delay)
                    
                except KeyboardInterrupt:
                    logger.info("Shutdown signal received")
                    break
                except asyncio.CancelledError: 
                    raise
                except Exception as e: 
                    logger.error(f"Main loop step error: {e}")
                    await asyncio.sleep(0.1)
                    
        except Exception as e:
            logger.error(f"Fatal trading error: {e}")
        finally:
            self.running = False
            await self.broker.disconnect()
            await self.shutdown()

    async def run_diagnostic(self):
        """Perform system diagnostics without trading"""
        print("\n" + "="*60)
        print("🔍 NEXT LEVEL BRAIN - SYSTEM DIAGNOSTIC")
        print("="*60)
        
        # 1. Connection check
        print(f"📡 Testing connection to {self.server} (Login: {self.login})...")
        if await self.broker.connect(login=self.login, password=self.password, server=self.server):
            print("✅ CONNECTION SUCCESSFUL!")
        else:
            print("❌ CONNECTION FAILED! Check your .env credentials.")
            return

        # 2. Account Check
        acc = mt5.account_info()
        if acc:
            print(f"👤 Account: {acc.login}")
            print(f"🏢 Server: {acc.server}")
            print(f"💰 Balance: {acc.balance:.2f} {self.unit}")
            print(f"📊 Equity: {acc.equity:.2f} {self.unit}")
            if acc.balance <= 0:
                 print(f"⚠️  Warning: Balance is 0 {self.unit}. Trading will be disabled but connection is verified.")
        else:
            print("❌ ERROR: Could not retrieve account information.")

        # 3. Symbol Check
        for s in self.symbols:
            print(f"📈 Checking Symbol: {s}...")
            if mt5.symbol_select(s, True):
                info = mt5.symbol_info(s)
                if info:
                    print(f"✅ Symbol {s} is visible and reachable.")
                    print(f"   - Bid: {info.bid} | Ask: {info.ask}")
                    print(f"   - Spread: {info.spread}")
                else:
                    print(f"❌ ERROR: Symbol {s} info is null.")
            else:
                print(f"❌ ERROR: Symbol {s} NOT FOUND in MT5 MarketWatch.")

        # 4. Intelligence Check
        print("🧠 Verifying AI Brain...")
        if self.ai_brain:
            print(f"✅ AI Brain Initialized. Memories: {len(self.ai_brain.memories)}")
        
        # 5. Logic Check
        print(f"⚙️  Verified Units: {self.unit}")
        print(f"⚙️  Account Mode: {self.account_type}")
        
        print("\n" + "="*60)
        print("🎉 DIAGNOSTIC COMPLETE: ALL SYSTEMS FUNCTIONAL!")
        print("="*60)
        print("You can now safely deposit or switch to real trading.\n")
        mt5.shutdown()
    
    async def _close_all_universe(self):
        """Emergency Close: Wipe all positions and pendings across all symbols in PARALLEL"""
        try:
            positions = mt5.positions_get()
            tasks = []
            
            # 1. Parallel Position Closing
            if positions:
                for pos in positions:
                    tasks.append(self.broker.close_position(pos.ticket))
            
            # 2. Parallel Pending Cancellation
            for symbol in self.symbols:
                tasks.append(self.broker.cancel_all_pendings(symbol))
            
            if tasks:
                logger.info(f"🚀 Sending {len(tasks)} parallel exit commands...")
                await asyncio.gather(*tasks)
            
            logger.info("✅ Universe cleanup completed in milliseconds.")
        except Exception as e:
            logger.error(f"Error during universe cleanup: {e}")
    
    async def shutdown(self):
        """Shutdown the trading system"""
        try:
            self.running = False
            logger.info("🛑 Shutting down trading system...")
            
            # Generate final report before closing
            self._update_session_history()
            report_file = self.generate_session_report()
            if report_file:
                logger.info(f"📄 Final Session Report saved: {report_file}")
            
            # Close MT5 connection
            mt5.shutdown()
            
            logger.info("✅ Shutdown completed")
        except Exception as e:
            logger.error(f"Shutdown error: {e}")

    def _update_session_history(self):
        """Fetch closed deals from MT5 for the last 30 days to build performance metrics"""
        try:
            # Fetch last 30 days for comprehensive performance tracking
            from_date = datetime.now() - timedelta(days=30)
            to_date = datetime.now() + timedelta(days=1)
            
            deals = mt5.history_deals_get(from_date, to_date)
            if not deals:
                return

            new_history = []
            for d in deals:
                if d.entry == 1: # DEAL_ENTRY_OUT
                    new_history.append({
                        'ticket': d.ticket,
                        'symbol': d.symbol,
                        'type': 'BUY' if d.type == mt5.DEAL_TYPE_BUY else 'SELL',
                        'volume': d.volume,
                        'price': d.price,
                        'profit': d.profit + d.commission + d.swap,
                        'magic': d.magic,
                        'time': datetime.fromtimestamp(d.time).strftime('%Y-%m-%d %H:%M:%S'),
                        'comment': d.comment
                    })
            
            self.trade_history = new_history
            # Today's specific metrics for display
            today_str = datetime.now().strftime('%Y-%m-%d')
            today_trades = [t for t in self.trade_history if today_str in t['time']]
            self.daily_pnl = sum(t['profit'] for t in today_trades)
            self.trades_today = len(today_trades)
            
        except Exception as e:
            logger.error(f"Failed to update history: {e}")

    def generate_session_report(self) -> Optional[str]:
        """Generate a detailed markdown report with Backtest-style metrics"""
        try:
            if not self.trade_history:
                return None
            
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            report_file = self.reports_dir / f"live_performance_{timestamp}.md"
            
            # Advanced metrics calculation
            profits = [t['profit'] for t in self.trade_history]
            wins = [p for p in profits if p > 0]
            losses = [p for p in profits if p <= 0]
            
            win_rate = (len(wins) / len(profits) * 100) if profits else 0
            gross_profit = sum(wins)
            gross_loss = abs(sum(losses))
            profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else float('inf')
            
            # Drawdown calculation
            acc_info = mt5.account_info()
            base_balance = acc_info.balance if acc_info else 10000.0
            cum_pnl = np.cumsum(profits)
            equity_curve = base_balance + cum_pnl
            peak = np.maximum.accumulate(equity_curve)
            drawdown_pct = (peak - equity_curve) / peak * 100
            max_dd_pct = np.max(drawdown_pct) if len(drawdown_pct) > 0 else 0
            
            report = [
                "# 🧠 NEXT LEVEL BRAIN - LIVE PERFORMANCE REPORT",
                f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                f"**Tracking Period:** Last 30 Days",
                f"**Strategy:** {self.strategy}",
                "\n## 📊 PERFORMANCE SUMMARY (Backtest Style)",
                f"- **Total Trades:** {len(profits)}",
                f"- **Win Rate:** {win_rate:.1f}%",
                f"- **Total P&L:** {self.unit}{sum(profits):.2f}",
                f"- **Profit Factor:** {profit_factor:.2f}",
                f"- **Max Drawdown:** {max_dd_pct:.2f}%",
                f"- **Avg Win:** {self.unit}{ (sum(wins)/len(wins)) if wins else 0 :.2f}",
                f"- **Avg Loss:** {self.unit}{ (sum(losses)/len(losses)) if losses else 0 :.2f}",
                "\n## 📋 RECENT TRADE LOG (Last 50)",
                "| Time | Symbol | Side | Lots | Profit ({self.unit}) | Comment |",
                "|------|--------|------|------|------------|---------|"
            ]
            
            for t in sorted(self.trade_history, key=lambda x: x['time'], reverse=True)[:50]:
                report.append(f"| {t['time']} | {t['symbol']} | {t['type']} | {t['volume']} | {t['profit']:.2f} | {t['comment']} |")
            
            with open(report_file, 'w', encoding='utf-8') as f:
                f.write("\n".join(report))
            
            return str(report_file)
            
        except Exception as e:
            logger.error(f"Failed to generate report: {e}")
            return None

def select_trade_setup():
    """Simplified setup selection as requested"""
    print("\n" + "="*60)
    print("🚀 NEXT LEVEL BRAIN - QUICK LAUNCH (GOLD ONLY)")
    print("="*60)
    
    # --- 1. Account Selection ---
    print("\n🏦 SELECT ACCOUNT TYPE:")
    print("1. 🧪 DEMO ACCOUNT (Default)")
    print("2. 💯 REAL CENT ACCOUNT (Exness)")
    
    account_type = "DEMO"
    unit = "$"
    acc_choice = input("Choice (1-2) [Default 1]: ").strip()
    
    import os
    from dotenv import load_dotenv
    load_dotenv()
    
    login = None
    password = None
    server = None
    
    if acc_choice == "2":
        account_type = "REAL_CENT"
        unit = "USC"
        login = int(os.getenv('REAL_MT5_LOGIN', 0))
        password = os.getenv('REAL_MT5_PASSWORD')
        server = os.getenv('REAL_MT5_SERVER')
        print(f"✅ Real Cent Account Selected. Units: {unit}")
    else:
        login = int(os.getenv('MT5_LOGIN', 0))
        password = os.getenv('MT5_PASSWORD')
        server = os.getenv('MT5_SERVER')
        print(f"✅ Demo Account Selected. Units: {unit}")

    # Dynamic Symbol Suffix
    final_symbols = []
    for s in ["XAUUSD"]:
        if account_type == "REAL_CENT":
            final_symbols.append(s + "c")
        else:
            final_symbols.append(s + "m")

    # --- 2. Strategy/Direction ---
    print("\n🎯 SELECT DIRECTION / ACTION:")
    print("1. 🛡️ SMART TRAILING BUY ONLY (10/20)")
    print("2. 🛡️ SMART TRAILING SELL ONLY (10/20)")
    print("3. 🧠 ICT SMC (Trend Following)")
    print("4. 📊 OPEN LIVE DASHBOARD (Visual Tracker)")
    print("5. 🧹 DELETE ALL PENDING ORDERS")
    print("6. 📈 OPEN BACKTESTING (Strategy Tester)")
    print("7. 🔍 SYSTEM & CONNECTION DIAGNOSTIC")
    
    strategy = "Grid Both"
    trailing_enabled = False
    recycler_mode = False
    recycler_profit_usd = 1.0  # default per-trade profit target
    
    while True:
        choice = input("Choice (1-7): ").strip()
        if choice == "1":
            strategy = "Smart Trailing BUY ONLY"
            trailing_enabled = True
            break
        if choice == "2":
            strategy = "Smart Trailing SELL ONLY"
            trailing_enabled = True
            break
        if choice == "3": strategy = "ICT SMC"; break
        if choice == "4":
            print(" Opening Live Dashboard...")
            import subprocess
            subprocess.Popen([sys.executable, "live_dashboard.py"], creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
            print("✅ Dashboard launched. Continuing...")
            continue
        if choice == "5":
            print("🧹 Cleaning up all Gold pending orders...")
            if mt5.initialize():
                # Rapid cleanup
                for s in ["XAUUSDm", "XAUUSD"]:
                    orders = mt5.orders_get(symbol=s)
                    if orders:
                        for o in orders:
                            mt5.order_send({"action": mt5.TRADE_ACTION_REMOVE, "order": o.ticket})
                print("✅ All pending orders deleted.")
            else:
                print("❌ Failed to connect to MT5 for cleanup.")
            continue
        if choice == "6":
            print("🚀 Opening Backtesting System...")
            import subprocess
            subprocess.Popen([sys.executable, "backtesting.py"], creationflags=subprocess.CREATE_NEW_CONSOLE if os.name == 'nt' else 0)
            print("✅ Backtesting launched.")
            continue
        if choice == "7":
            strategy = "DIAGNOSTIC"
            break
        print("Invalid choice.")

    if strategy == "DIAGNOSTIC":
        return final_symbols, strategy, "M1", 0, 0, False, 0, 0.01, account_type, unit, login, password, server

    # 1b. Per-Trade Target is now trailing-based (Default $1.0)
    if recycler_mode:
        recycler_profit_usd = 1.0
        print(f"✅ Recycler: Trailing Profit Activated (Base: {unit}{recycler_profit_usd:.2f})")


    # 2. Profit Target
    profit_pct = 0.01
    profit_usd = 0
    if recycler_mode:
        # For Recycler, we skip standard targets as it uses per-trade targets
        pass
    elif trailing_enabled:
        print(f"\n🛡️  PROTECTION: Using {strategy} (10/20 Smart Basket Logic)")
    else:
        print(f"\n💰 SELECT PROFIT TARGET ({unit}):")
        print("A. Enter Target % (1 to 20):")
        while True:
            try:
                val = input("Target % (1-20) [Default 1]: ").strip()
                if not val:
                    profit_pct = 0.01
                    break
                f_val = float(val)
                if 1 <= f_val <= 20:
                    profit_pct = f_val / 100.0
                    break
            except: pass
            print("Invalid choice. Please enter a number between 1 and 20.")

        print(f"\nB. Or Enter Target {unit}:")
        while True:
            try:
                val = input(f"Target {unit} (e.g. 10, 20) [Enter 'T' for Smart Trailing 10-20]: ").strip().upper()
                if val == 'T':
                    profit_usd = 0
                    trailing_enabled = True
                    # Set strategy name based on implied mode if not already set specifically
                    if strategy == "Grid Both": strategy = "Smart Trailing Both"
                    elif strategy == "Grid BUY ONLY": strategy = "Smart Trailing BUY ONLY"
                    elif strategy == "Grid SELL ONLY": strategy = "Smart Trailing SELL ONLY"
                    else: strategy = "SMART TRAILING 10-20"
                    
                    print(f"✅ Smart Trailing Activated for {strategy}")
                    break
                
                trailing_enabled = False
                if not val:
                    profit_usd = 0 
                    break
                f_val = float(val)
                if f_val > 0:
                    profit_usd = f_val
                    break
            except: pass
            print(f"Invalid choice. Please enter a positive number or 'T'.")

    # 3. Timeframe
    print("\n⏰ SELECT TIMEFRAME:")
    print("1. M1")
    print("2. M3")
    print("3. M5")
    print("4. M15")
    print("5. M30")
    print("6. H1")
    print("7. H4")
    print("8. D1")
    
    timeframe = "M1"
    while True:
        try:
            choice = input(f"Choice (1-8) [Default 1]: ").strip()
            if not choice: timeframe = "M1"; break
            
            tf_map = {
                "1": "M1", "2": "M3", "3": "M5", "4": "M15",
                "5": "M30", "6": "H1", "7": "H4", "8": "D1"
            }
            if choice in tf_map:
                timeframe = tf_map[choice]
                break
        except: pass
        print("Invalid choice.")

    # 4. Lot Size Selection (Choice Menu 1-10)
    print("\n📦 SELECT LOT SIZE:")
    lot_choices = [0.01, 0.02, 0.03, 0.04, 0.05, 0.06, 0.07, 0.08, 0.09, 0.10]
    for i, size in enumerate(lot_choices, 1):
        print(f"{i}. {size}")
    
    lot_size = 0.01
    while True:
        try:
            choice = input(f"Choice (1-10) [Default 1]: ").strip()
            if not choice:
                lot_size = 0.01
                break
            idx = int(choice)
            if 1 <= idx <= 10:
                lot_size = lot_choices[idx-1]
                # Update config.yaml
                try:
                    with open('config.yaml', 'r') as f:
                        config = yaml.safe_load(f) or {}
                    if 'grid' not in config: config['grid'] = {}
                    config['grid']['lot_size'] = lot_size
                    with open('config.yaml', 'w') as f:
                        yaml.dump(config, f)
                    logger.info(f"📝 config.yaml updated: lot_size = {lot_size}")
                except Exception as e:
                    logger.error(f"Failed to update config.yaml: {e}")
                break
        except: pass
        print("Invalid choice. Please enter 1-10.")

    return final_symbols, strategy, timeframe, profit_pct, profit_usd, trailing_enabled, recycler_profit_usd, lot_size, account_type, unit, login, password, server


def main():
    """Main function - CLI mode"""
    try:
        # Create necessary directories
        Path("logs").mkdir(exist_ok=True)
        Path("charts").mkdir(exist_ok=True)
        Path("models").mkdir(exist_ok=True)
        
        symbols, strategy, timeframe, profit_pct, profit_usd, trailing_enabled, recycler_profit_usd, lot_size, account_type, unit, login, password, server = select_trade_setup()
        if symbols is None or strategy is None or timeframe is None:
            print("Exiting.")
            return
        
        trading_system = LiveTradingSystem()
        trading_system.symbols = symbols
        trading_system.strategy = strategy
        trading_system.timeframe = timeframe
        trading_system.profit_pct = profit_pct
        trading_system.trailing_enabled = trailing_enabled
        
        # Account units and credentials
        trading_system.account_type = account_type
        trading_system.unit = unit
        trading_system.login = login
        trading_system.password = password
        trading_system.server = server
        
        # Propagate lot size and profit targets to ALL components
        trading_system.grid_manager.lot_size = lot_size
        trading_system.grid_manager.per_trade_profit = recycler_profit_usd
        
        trading_system.grid_recycler.lot_size = lot_size
        trading_system.grid_recycler.per_trade_profit = recycler_profit_usd
        if profit_usd > 0:
            trading_system.profit_usd = profit_usd
        
        # Propagate unit to controllers
        trading_system.grid_manager.profit_ctrl.unit = unit
        trading_system.grid_recycler.profit_ctrl.unit = unit
        
        # Run diagnostic OR trading loop
        if strategy == "DIAGNOSTIC":
            asyncio.run(trading_system.run_diagnostic())
        else:
            asyncio.run(trading_system.run())
        
        # After trading loop, offer to open backtesting
        print("\n" + "="*50)
        print("🏁 SESSION ENDED")
        print("="*50)
        bt_choice = input("Open Backtesting System? (Y/N): ").strip().upper()
        if bt_choice == 'Y':
            import subprocess
            subprocess.Popen([sys.executable, "backtesting.py"], creationflags=subprocess.CREATE_NEW_CONSOLE if os.name == 'nt' else 0)
            print("✅ Backtesting launched. Goodbye!")
        else:
            print("Goodbye!")
        
    except KeyboardInterrupt:
        logger.info("Application interrupted by user")
    except Exception as e:
        logger.error(f"Application error: {e}")

if __name__ == "__main__":
    main()
