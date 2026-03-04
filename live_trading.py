#!/usr/bin/env python3
"""
NEXT LEVEL TRADING SYSTEM - Live Trading System (CLI only)
All-in-one live trading with AI enhancement
Created by: Aleem Shahzad
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
        """Load external market intelligence report"""
        try:
            report_file = Path("latest_intelligence_report.txt")
            if report_file.exists():
                with open(report_file, 'r') as f:
                    content = f.read()
                    if content != getattr(self, '_last_sentiment_content', ''):
                        if "DECISION:           BLOCK" in content:
                            self.sentiment_decision = "BLOCK"
                        elif "DECISION:           REDUCE" in content:
                            self.sentiment_decision = "REDUCE"
                            self.risk_modifier = 0.5
                        else:
                            self.sentiment_decision = "ALLOW"
                            self.risk_modifier = 1.0
                        logger.info(f"📡 Market Intelligence: {self.sentiment_decision}")
                        self._last_sentiment_content = content
            else:
                # Only warn once at startup, not every loop cycle
                if not getattr(self, '_sentiment_warning_shown', False):
                    logger.info("📡 No intelligence report — running in default ALLOW mode.")
                    self._sentiment_warning_shown = True
        except Exception as e:
            logger.error(f"Failed to read sentiment report: {e}")

    def _load_memories(self):
        """Load trained memories from file"""
        try:
            memory_file = Path("models/ai_memories.json")
            if memory_file.exists():
                import json
                with open(memory_file, 'r') as f:
                    self.memories = json.load(f)
                self.model_trained = True
                logger.info(f"🧠 Loaded {len(self.memories)} training memories. AI is ready.")
            else:
                logger.warning("⚠️ No training data found. AI starting with blank slate.")
        except Exception as e:
            logger.error(f"Failed to load memories: {e}")

    def _save_memories(self):
        """Persist memories to disk"""
        try:
            memory_file = Path("models/ai_memories.json")
            memory_file.parent.mkdir(parents=True, exist_ok=True)
            import json
            with open(memory_file, 'w') as f:
                # Store datetime as string for JSON
                json.dump(self.memories, f, default=str, indent=2)
        except Exception as e:
            logger.error(f"Failed to save memories: {e}")

    def _get_ai_adjustment(self, symbol: str, action: str) -> Tuple[float, str]:
        """
        Analyze past memories to adjust current confidence.
        Returns: (adjustment_val, reasoning)
        """
        if not self.memories:
            return 0.0, ""

        # Filter relevant memories (last 100 for this symbol/action)
        relevant = [m for m in self.memories if m.get('symbol') == symbol and m.get('action') == action]
        if not relevant:
            return 0.0, ""

        recent = relevant[-20:] # Last 20 trades
        wins = [m for m in recent if m.get('success', False)]
        win_rate = len(wins) / len(recent)

        if win_rate >= 0.7:
            return 0.2, f"AI Learning: High win rate on {symbol} {action} ({win_rate:.0%})"
        elif win_rate <= 0.3:
            return -0.3, f"AI Learning: Low success on {symbol} {action} ({win_rate:.0%})"
        
        return 0.0, ""

    def _is_silver_bullet_time(self, timestamp: datetime) -> bool:
        """
        ICT Silver Bullet Windows (New York EST = UTC-5).
        Windows:
          - 3:00 AM - 4:00 AM EST  (London Open)
          - 10:00 AM - 11:00 AM EST (NY AM Session)
          - 2:00 PM - 3:00 PM EST  (NY PM Session)

        MT5_SERVER_TIME_OFFSET in .env:
          Set this to convert your system time to EST.
          Pakistan (PKT) = UTC+5, EST = UTC-5 => offset = -10
          MT5 Server (EET/UTC+2) => offset = -7
        """
        offset = int(os.getenv("MT5_SERVER_TIME_OFFSET", -10))  # default PKT -> EST
        adj_time = timestamp + timedelta(hours=offset)
        h = adj_time.hour
        m = adj_time.minute

        # Full Silver Bullet window ranges (start inclusive, end exclusive)
        windows = [(3, 4), (10, 11), (14, 15)]
        for (start, end) in windows:
            if start <= h < end:
                return True
        return False

    def analyze_market(self, symbol: str, data: pd.DataFrame) -> Dict:
        """ICT/SMC AI market analysis"""
        try:
            # BTC/ETH: More data for volatility, wider lookback
            lookback = 100 if "BTC" in symbol or "ETH" in symbol else 50
            if len(data) < lookback:
                return {'action': 'HOLD', 'bias': 'NEUTRAL', 'confidence': 0.0, 'reasoning': 'Insufficient data'}
            
            data = self._add_indicators(data)
            index = len(data) - 1
            
            market_bias = self._determine_market_bias(data, index, symbol)
            
            # Silver Bullet / Killzone Time
            current_time = datetime.now()
            is_sb_time = True if ("BTC" in symbol or "ETH" in symbol) else self._is_silver_bullet_time(current_time)
            
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
            
            # BULLISH SETUP - Need at least 1.5 confluence score
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

                if bullish_conditions >= 1.5:
                    confidence = self._calculate_confluence_score(signal_strengths)

                    # AI Memory Adjustment
                    ai_adj, ai_reason = self._get_ai_adjustment(symbol, 'BUY')
                    confidence = max(0.0, min(1.0, confidence + ai_adj))
                    final_reasoning = f'ICT Bullish: {", ".join(signals_present)} (Score: {bullish_conditions:.1f})'
                    if ai_reason:
                        final_reasoning += f" | {ai_reason}"

                    if liquidity_sweep['detected']:
                        stop_loss = liquidity_sweep['swept_level'] - (current['close'] * 0.001)
                    else:
                        stop_loss = current['close'] * 0.98

                    return {
                        'action': 'BUY',
                        'bias': 'BULLISH',
                        'confidence': confidence,
                        'reasoning': final_reasoning,
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
                
                if bearish_conditions >= 1.5:
                    confidence = self._calculate_confluence_score(signal_strengths)

                    # AI Memory Adjustment
                    ai_adj, ai_reason = self._get_ai_adjustment(symbol, 'SELL')
                    confidence = max(0.0, min(1.0, confidence + ai_adj))
                    final_reasoning = f'ICT Bearish: {", ".join(signals_present)} (Score: {bearish_conditions:.1f})'
                    if ai_reason:
                        final_reasoning += f" | {ai_reason}"
                    
                    if liquidity_sweep['detected']:
                        stop_loss = liquidity_sweep['swept_level'] + (current['close'] * 0.001)
                    else:
                        stop_loss = current['close'] * 1.02
                    
                    return {
                        'action': 'SELL',
                        'bias': 'BEARISH',
                        'confidence': confidence,
                        'reasoning': final_reasoning,
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
    
    def _determine_market_bias(self, df: pd.DataFrame, index: int, symbol: str = "") -> str:
        """MSS Sensitive Bias Detection"""
        try:
            is_crypto = "BTC" in symbol or "ETH" in symbol
            lookback = 60 if is_crypto else 40
            sens = 0.0002 if is_crypto else 0.0005 # Sensitivity
            
            recent_data = df.iloc[index-lookback:index+1]
            highs = recent_data['high'].rolling(4, center=True).max()
            lows = recent_data['low'].rolling(4, center=True).min()
            current_price = df.iloc[index]['close']
            
            # Simplified Flow: If price breaks range high/low significantly
            if current_price > highs.max() * (1 - sens): return 'BULLISH'
            if current_price < lows.min() * (1 + sens): return 'BEARISH'
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
    
    def _detect_order_block(self, df: pd.DataFrame, index: int, bias: str, symbol: str = "") -> Dict:
        """Enhanced Order Block Detection for High Price Symbols"""
        try:
            is_crypto = "BTC" in symbol or "ETH" in symbol
            lookback = 12
            threshold = 0.0008 if is_crypto else 0.0015 # More sensitive for BTC
            
            for i in range(index-lookback, index-1):
                bar = df.iloc[i]
                next_bar = df.iloc[i+1]
                price_change = abs(next_bar['close'] - bar['close']) / bar['close']
                
                if bias == 'BULLISH' and price_change > threshold and next_bar['close'] > bar['close']:
                    return {'detected': True, 'type': 'BULLISH', 'high': bar['high'], 'low': bar['low'], 'strength': min(price_change * 20, 1.0)}
                elif bias == 'BEARISH' and price_change > threshold and next_bar['close'] < bar['close']:
                    return {'detected': True, 'type': 'BEARISH', 'high': bar['high'], 'low': bar['low'], 'strength': min(price_change * 20, 1.0)}
            
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
            'timestamp': str(datetime.now()),
            'symbol': trade_data.get('symbol'),
            'action': trade_data.get('action'),
            'success': trade_data.get('success', False),
            'pnl': trade_data.get('pnl', 0),
            'confidence': trade_data.get('confidence', 0.0)
        })
        
        # Keep only last 1000 memories
        if len(self.memories) > 1000:
            self.memories = self.memories[-1000:]
            
        self._save_memories()

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
        """Calculate optimal position size"""
        try:
            # Risk amount
            risk_amount = account_balance * self.max_risk_per_trade
            
            # Price difference
            price_diff = abs(entry_price - stop_loss)
            if price_diff == 0:
                return 0.01  # Minimum position size
            
            # Calculate position size based on asset type
            if 'BTC' in symbol or 'ETH' in symbol:
                # For crypto, use smaller position sizes
                position_size = min(risk_amount / (price_diff * 10), 0.1)
            elif 'XAU' in symbol or 'XAG' in symbol:
                # For metals
                position_size = min(risk_amount / price_diff, 1.0)
            else:
                # For forex
                position_size = min(risk_amount / (price_diff * 100000), 1.0)
            
            # Round to valid lot size
            position_size = round(position_size, 2)
            
            # Ensure minimum and maximum limits
            return max(0.01, min(position_size, 1.0))
            
        except Exception as e:
            logger.error(f"Position size calculation error: {e}")
            return 0.01
    
    def check_risk_limits(self, account_balance: float, current_drawdown: float) -> bool:
        """Check if trading is allowed based on risk limits"""
        # Check daily loss limit
        if abs(self.daily_pnl) > account_balance * self.max_daily_loss:
            logger.warning("Daily loss limit reached")
            return False
            
        # Check maximum drawdown
        if current_drawdown > self.max_drawdown:
            logger.warning("Maximum drawdown limit reached")
            return False
            
        return True

class GridManager:
    """Manages User Requested Grid Strategy"""
    def __init__(self, broker, config: Dict = None):
        self.broker = broker
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
        
        # Profit Controller integration
        self.profit_ctrl = ProfitController(broker, self.strategy_name)
        
        # State Persistence
        self.state_file = Path("logs/grid_state.json")
        self._load_state()

    def _save_state(self):
        """Save grid progress to file"""
        try:
            self.state_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.state_file, 'w') as f:
                json.dump(self.active_grids, f)
        except Exception as e:
            logger.error(f"Error saving grid state: {e}")

    def _load_state(self):
        """Load grid progress from file"""
        if self.state_file.exists():
            try:
                with open(self.state_file, 'r') as f:
                    self.active_grids = json.load(f)
                    
                    # Migration: If old state had 'type' at top level for a symbol, wrap it
                    for symbol in list(self.active_grids.keys()):
                        data = self.active_grids[symbol]
                        if 'type' in data: # Check for old structure
                            side = data['type']
                            del data['type'] # Remove the top-level 'type'
                            self.active_grids[symbol] = {side: data}
                            logger.info(f"🚚 Migrated legacy grid state for {symbol} ({side})")
                logger.info(f"📁 Loaded Grid State from {self.state_file}")
            except json.JSONDecodeError:
                logger.warning("⚠️ Grid state file was corrupt. Starting fresh.")
                self.active_grids = {}
            except Exception as e:
                logger.error(f"Failed to load grid state: {e}")
                self.active_grids = {}
        else:
            self.active_grids = {}

    async def update(self, symbol, current_price, bias, balance):
        """Update grid logic based on bias and profit"""
        try:
            symbol_info = mt5.symbol_info(symbol)
            if not symbol_info:
                logger.error(f"Cannot update grid: Symbol {symbol} not found")
                return

            # BTC Optimization: Use $50 spacing instead of default $1 for Bitcoin's higher price
            spacing = 50.0 if "BTC" in symbol.upper() else self.spacing

            # 1. Update Grid Positions (Raw objects for ProfitController)
            raw_positions = mt5.positions_get(symbol=symbol)
            if raw_positions is None: raw_positions = []
            grid_objs = [p for p in raw_positions if p.magic in (self.magic_buy, self.magic_sell)]

            # 2. Individual Trailing Check via ProfitController
            to_close = await self.profit_ctrl.monitor_individual_trailing(grid_objs, self.per_trade_profit)
            
            for pos in to_close:
                logger.info(f"💰 Grid Trade {pos.ticket} closed via Individual Trailing.")
                # Close the position
                res = await self.broker.close_position(pos.ticket)
                if res['success']:
                    # Immediately recycle the level
                    await self._recycle_level(symbol, pos.price_open, pos.type)

            # 2.5 Side-Based Basket Trailing (Smart Trailing Selection)
            if getattr(self, 'trailing_enabled', False):
                await self.profit_ctrl.monitor_trailing(symbol, self.magic_buy, self.magic_sell)

            # 3. Batch Maintenance Logic
            all_orders = mt5.orders_get(symbol=symbol)
            if all_orders is None: all_orders = []
            grid_pendings = [o for o in all_orders if o.magic in (self.magic_buy, self.magic_sell)]

            # 3. Dynamic Grid Logic (SELL Side)
            if self.mode in ('SELL_ONLY', 'BOTH'):
                sell_pendings = {round(o.price_open, 2): o for o in grid_pendings if o.magic == self.magic_sell}
                sell_positions = {round(p.price_open, 2): p for p in grid_objs if p.magic == self.magic_sell}
                
                # SNAP ANCHOR: Round to nearest whole spacing (e.g. $1 increments)
                # This ensures rolling only occurs in jumps of 'spacing', not 10-cent intervals.
                anchor = round(current_price / spacing) * spacing
                
                # A. MAINTAIN GRID: Fill levels from anchor + 1 up to total_target
                # This keeps the grid centered around the current price.
                success_count = 0
                for i in range(1, self.batch_size + 1):
                    level_price = anchor + (i * spacing)
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
                limit_dist = (self.batch_size + 5) * spacing
                for p_price, order in sell_pendings.items():
                    if abs(p_price - anchor) > limit_dist:
                        await self.broker.cancel_order(order.ticket)

            # 4. Dynamic Grid Logic (BUY Side)
            if self.mode in ('BUY_ONLY', 'BOTH'):
                buy_pendings = {round(o.price_open, 2): o for o in grid_pendings if o.magic == self.magic_buy}
                buy_positions = {round(p.price_open, 2): p for p in grid_objs if p.magic == self.magic_buy}
                
                # SNAP ANCHOR
                anchor = round(current_price / spacing) * spacing
                
                # A. MAINTAIN GRID: Fill levels from anchor - 1 down
                success_count = 0
                for i in range(1, self.batch_size + 1):
                    level_price = anchor - (i * spacing)
                    level_price = round(round(level_price / symbol_info.trade_tick_size) * symbol_info.trade_tick_size, symbol_info.digits)
                    r_price = round(level_price, 2)
                    
                    if r_price in buy_pendings or r_price in buy_positions:
                        continue
                        
                    if level_price >= current_price - (symbol_info.spread * symbol_info.point): continue
                    
                    res = await self.broker.place_pending_order(symbol, mt5.ORDER_TYPE_BUY_LIMIT, self.lot_size, level_price, self.magic_buy)
                    if res['success']: success_count += 1
                    elif res.get('error') == 'MARKET_CLOSED': break

                # B. PRUNE: Remove far-away orders
                limit_dist = (self.batch_size + 5) * spacing
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
                # Small buffer (1.5x spread) to avoid INVALID_PRICE rejection
                buffer = symbol_info.spread * symbol_info.point * 1.5
                if side == "BUY" and price >= tick.ask - buffer:
                    return # Market moved past level or too close
                if side == "SELL" and price <= tick.bid + buffer:
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
        self.grid_manager = GridManager(self.broker, self.config)
        self.grid_recycler = GridRecycler(self.broker, self.config)
        
        self.running = False
        self.symbols = self.config.get('symbols', ['XAUUSDm'])
        self.timeframe = self.config.get('timeframe', 'M5')
        self.strategy = "ICT SMC" # Default strategy
        self.profit_pct = 0.01 # Default 1%
        self.profit_usd = self.config.get('grid', {}).get('profit_target_usd', 20)
        self.trailing_enabled = False
        
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
            logger.info("🧠 Initializing NEXT LEVEL TRADING SYSTEM Live Trading System...")
            
            # Connect to broker
            if not await self.broker.connect():
                logger.warning("📡 MT5 not connected during startup. Watchdog will handle reconnection.")
            
            # Get account info (If connected)
            account_info = mt5.account_info()
            if account_info:
                self.start_balance = account_info.balance
                logger.info(f"Account Balance: ${self.start_balance:.2f}")
            
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
    
    async def analyze_and_trade(self, symbol: str):
        """Analyze market and execute trades for a symbol"""
        try:
            # Get account context
            acc = mt5.account_info()
            if not acc: return
            balance = acc.balance

            # Get market data
            data = self.broker.get_market_data(symbol, self.timeframe, 500)
            if data.empty:
                return
            
            # AI Analysis (Keep for bias detection)
            ai_analysis = self.ai_brain.analyze_market(symbol, data)
            current_price = data['close'].iloc[-1]
            bias = ai_analysis.get('bias', 'NEUTRAL')
            
            # 1. Grid Strategy Logic (Smart Trailing / Standard Grid)
            if ("Grid" in self.strategy or "Smart" in self.strategy) and "Recycler" not in self.strategy:
                # Set mode and name
                self.grid_manager.strategy_name = self.strategy
                if "BUY ONLY" in self.strategy.upper():
                    self.grid_manager.mode = "BUY_ONLY"
                elif "SELL ONLY" in self.strategy.upper():
                    self.grid_manager.mode = "SELL_ONLY"
                else:
                    self.grid_manager.mode = "BOTH"
                
                self.grid_manager.profit_threshold_pct = self.profit_pct
                self.grid_manager.profit_target_usd = self.profit_usd
                self.grid_manager.trailing_enabled = self.trailing_enabled
                await self.grid_manager.update(symbol, current_price, bias, balance)
            
            # 2. Grid Recycler Strategy Logic
            elif "Recycler" in self.strategy:
                if "BUY ONLY" in self.strategy.upper():
                    self.grid_recycler.mode = "BUY_ONLY"
                elif "SELL ONLY" in self.strategy.upper():
                    self.grid_recycler.mode = "SELL_ONLY"
                else:
                    self.grid_recycler.mode = "BOTH"
                await self.grid_recycler.update(symbol, current_price)
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
            
            # Place order
            result = self.broker.place_order(
                symbol=symbol,
                action=ai_analysis['action'],
                volume=position_size,
                price=entry_price,
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
                if pos['profit'] > 50:  # If profit > $50
                    logger.info(f"💰 Position {pos['symbol']} in profit: ${pos['profit']:.2f}")
                elif pos['profit'] < -100:  # If loss > $100
                    logger.warning(f"⚠️ Position {pos['symbol']} in loss: ${pos['profit']:.2f}")
                    
        except Exception as e:
            logger.error(f"Position monitoring error: {e}")
    
    def display_status(self):
        """Display current system status"""
        try:
            account_info = mt5.account_info()
            if account_info:
                current_balance = account_info.balance
                
                # Safety check for start_balance
                if self.start_balance <= 0 or self.start_balance > 1000000: # Sanity check
                    self.start_balance = current_balance
                
                daily_change = current_balance - self.start_balance
                
                logger.info(f"\n{'='*50}")
                logger.info(f"🧠 NEXT LEVEL TRADING - LIVE TRADING STATUS")
                logger.info(f"{'='*50}")
                logger.info(f"💰 Balance: ${current_balance:.2f}")
                logger.info(f"📈 Daily P&L: ${daily_change:.2f} (Start: ${self.start_balance:.2f})")
                logger.info(f"📊 Trades Today: {self.trades_today}")
                
                # Show Individual Trailing Status (Summary)
                ticket_states = self.grid_manager.profit_ctrl.ticket_states
                if ticket_states:
                    active_locks = [s['lock'] for s in ticket_states.values() if s['lock'] > 0]
                    if active_locks:
                        max_lock = max(active_locks)
                        logger.info(f"🛡️  PROTECTION: {len(active_locks)} Trades Trailing (Max Lock: ${max_lock:.1f})")

                logger.info(f"🎯 AI Memories: {len(self.ai_brain.memories)}")
                logger.info(f"⏰ Last Update: {datetime.now().strftime('%H:%M:%S')}")
                logger.info(f"📂 Reports Path: {self.reports_dir.absolute()}")
                
                positions = self.broker.get_positions()
                if positions:
                    logger.info(f"📋 Open Positions: {len(positions)}")
                    for pos in positions:
                        logger.info(f"  {pos['symbol']}: {pos['type']} ${pos['profit']:.2f}")
                else:
                    logger.info(f"📋 Open Positions: 0")
                logger.info(f"{'='*50}")
                
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
                        if stored_baseline <= 0 or acc.equity < (stored_baseline - 10):
                            logger.info(f"🔄 Auto-Syncing Equity Baseline to current equity: ${acc.equity:.2f}")
                            ctrl.reset_equity_milestone(acc.equity)
                            logger.info(f"📊 Equity Milestone Synced. Baseline: ${acc.equity:.2f} | Target: ${acc.equity+100:.2f}")
                        else:
                            # Baseline is valid, just log it
                            logger.info(f"📊 Equity Milestone Loaded. Baseline: ${stored_baseline:.2f} | Target: ${stored_baseline+100:.2f}")
            except Exception as e:
                logger.error(f"Error during equity baseline sync: {e}")

            logger.info("🚀 Starting live trading...")
            
            cycle_count = 0
            
            while self.running:
                try:
                    # Connection Watchdog
                    if not await self.broker.is_connected():
                        logger.warning("📡 Connection lost! Attempting to reconnect...")
                        # Wait exponentially or simply retry
                        if await self.broker.connect():
                            logger.info("✅ Reconnected successfully!")
                        else:
                            logger.error("❌ Reconnect failed. Retrying in 10 seconds...")
                            await asyncio.sleep(10)
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
                            logger.info(f"🎯 Milestone Baseline Set: ${acc.balance:.2f}. Target: ${acc.balance+100:.2f}")

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
                    
                    # 3. Grand Basket Trailing (Universe-Wide)
                    # Monitor ALL active positions across ALL symbols/strategies
                    all_positions = self.broker.get_positions()
                    if await self.grid_manager.profit_ctrl.monitor_grand_basket(all_positions, trigger_usd=5.0):
                        logger.warning("🏁 GRAND BASKET TRAILING EXIT TRIGGERED! Closing everything.")
                        await self._close_all_universe()
                        # Reset Layer 3 baseline after Layer 2 exit with FRESH equity
                        fresh_acc = mt5.account_info()
                        if fresh_acc: self.grid_manager.profit_ctrl.reset_equity_milestone(fresh_acc.equity)

                    # 4. LAYER 3: Equity Milestone Monitor ($100 Target)
                    if acc:
                        if await self.grid_manager.profit_ctrl.monitor_equity_milestone(acc.equity, target_increase=100.0):
                            logger.success("🏆 EQUITY MILESTONE HIT! Closing Universe.")
                            await self._close_all_universe()
                            # Reset with FRESH equity
                            fresh_acc = mt5.account_info()
                            if fresh_acc: self.grid_manager.profit_ctrl.reset_equity_milestone(fresh_acc.equity)

                    # Analyze each symbol
                    for symbol in self.symbols:
                        await self.analyze_and_trade(symbol)
                        await asyncio.sleep(0.01)  # Minimal delay between symbols
                    
                    # Update session history (Every ~10 seconds) - Skip if silent
                    if not all_closed and cycle_count % 100 == 0:
                        self._update_session_history()
                    
                    # Update session history and save partial report
                    self._update_session_history()
                    if cycle_count % 20 == 0:
                        self.generate_session_report()
                    
                    # Wait before next cycle
                    if all_closed:
                        delay = 2.0 # Slow heartbeat when closed
                    else:
                        # ULTRA SPEED for Grid/Smart strategies (20 times per second)
                        delay = 0.05 if ("Grid" in self.strategy or "Smart" in self.strategy or "Recycler" in self.strategy) else 5
                    
                    await asyncio.sleep(delay)
                    
                except KeyboardInterrupt:
                    logger.info("Shutdown signal received")
                    break
                except Exception as e:
                    logger.error(f"Trading loop error: {e}")
                    # If it's a network error, MT5 calls might fail
                    await asyncio.sleep(5)
            
        except Exception as e:
            logger.error(f"Fatal trading error: {e}")
        finally:
            await self.shutdown()
    
    async def _close_all_universe(self):
        """Emergency Close: Wipe all positions and pendings across all symbols"""
        try:
            positions = self.broker.get_positions()
            for pos in positions:
                await self.broker.close_position(pos['ticket'])
            
            # Cancel all pendings for our symbols
            for symbol in self.symbols:
                await self.broker.cancel_all_pendings(symbol)
            
            logger.info("✅ Universe cleanup completed.")
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
            
            # Synchronize AI Memories with actual historical deals
            # We clear and rebuild to ensure memories are always 100% accurate from MT5 history
            self.ai_brain.memories = [] 
            for t in self.trade_history:
                # We only want to learn from ICT strategy trades (typically have comments or specific magic numbers)
                # But for now, let's learn from everything to build a robust symbol bias
                self.ai_brain.remember_trade({
                    'symbol': t['symbol'],
                    'action': t['type'],
                    'pnl': t['profit'],
                    'success': t['profit'] > 0
                })

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
                "# 🧠 NEXT LEVEL TRADING- LIVE PERFORMANCE REPORT",
                f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                f"**Tracking Period:** Last 30 Days",
                f"**Strategy:** {self.strategy}",
                "\n## 📊 PERFORMANCE SUMMARY (Backtest Style)",
                f"- **Total Trades:** {len(profits)}",
                f"- **Win Rate:** {win_rate:.1f}%",
                f"- **Total P&L:** ${sum(profits):.2f}",
                f"- **Profit Factor:** {profit_factor:.2f}",
                f"- **Max Drawdown:** {max_dd_pct:.2f}%",
                f"- **Avg Win:** ${ (sum(wins)/len(wins)) if wins else 0 :.2f}",
                f"- **Avg Loss:** ${ (sum(losses)/len(losses)) if losses else 0 :.2f}",
                "\n## 📋 RECENT TRADE LOG (Last 50)",
                "| Time | Symbol | Side | Lots | Profit ($) | Comment |",
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

# Exness available trading pairs (micro/standard)
EXNESS_PAIRS = [
    "XAUUSDm",   # Gold
    "XAGUSDm",   # Silver
    "EURUSDm",   # Euro / US Dollar
    "GBPUSDm",   # British Pound / US Dollar
    "USDJPYm",   # US Dollar / Japanese Yen
    "USDCHFm",   # US Dollar / Swiss Franc
    "AUDUSDm",   # Australian Dollar / US Dollar
    "NZDUSDm",   # New Zealand Dollar / US Dollar
    "USDCADm",   # US Dollar / Canadian Dollar
    "EURGBPm",   # Euro / British Pound
    "EURJPYm",   # Euro / Japanese Yen
    "GBPJPYm",   # British Pound / Japanese Yen
    "BTCUSDm",   # Bitcoin / US Dollar
    "ETHUSDm",   # Ethereum / US Dollar
    "USOILm",    # US Crude Oil
    "UKOILm",    # Brent Crude Oil
    "NASDAQ",    # Nasdaq 100 Index
    "SP500m",    # S&P 500 Index
]

def select_trade_setup():
    """Setup selection with full Exness pair list"""
    print("\n" + "="*60)
    print("🚀 NEXT LEVEL TRADING SYSTEM")
    print("="*60)

    # 0. Symbol Selection
    print("\n🪙 SELECT TRADING PAIR:")
    for i, sym in enumerate(EXNESS_PAIRS, 1):
        print(f"{i:2}. {sym}")
    selected_symbol = "XAUUSDm"
    while True:
        try:
            val = input(f"Choice (1-{len(EXNESS_PAIRS)}) [Default 1 - XAUUSDm]: ").strip()
            if not val:
                selected_symbol = "XAUUSDm"
                break
            idx = int(val)
            if 1 <= idx <= len(EXNESS_PAIRS):
                selected_symbol = EXNESS_PAIRS[idx - 1]
                break
        except: pass
        print(f"Invalid. Enter 1-{len(EXNESS_PAIRS)}.")
    print(f"✅ Selected: {selected_symbol}")

    # 1. Strategy/Direction
    print("\n🎯 SELECT DIRECTION / ACTION:")
    print("1. 🛡️ SMART TRAILING BUY ONLY ($10/$20)")
    print("2. 🛡️ SMART TRAILING SELL ONLY ($10/$20)")
    print("3. 🧠 ICT SMC (Trend Following)")
    print("4. 📊 OPEN LIVE DASHBOARD (Visual Tracker)")
    print("5. 🧹 DELETE ALL PENDING ORDERS")
    print("6. 📈 OPEN BACKTESTING (Strategy Tester)")

    strategy = "Grid Both"
    trailing_enabled = False
    recycler_mode = False
    recycler_profit_usd = 1.0  # default per-trade profit target
    while True:
        choice = input("Choice (1-6): ").strip()
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
            print("🧹 Cleaning up all pending orders across all pairs...")
            if mt5.initialize():
                count = 0
                for s in EXNESS_PAIRS + [p.replace('m','') for p in EXNESS_PAIRS]:
                    orders = mt5.orders_get(symbol=s)
                    if orders:
                        for o in orders:
                            mt5.order_send({"action": mt5.TRADE_ACTION_REMOVE, "order": o.ticket})
                            count += 1
                print(f"✅ {count} pending orders deleted.")
            else:
                print("❌ Failed to connect to MT5 for cleanup.")
            continue
        if choice == "6":
            print("🚀 Opening Backtesting System...")
            import subprocess
            subprocess.Popen([sys.executable, "backtesting.py"], creationflags=subprocess.CREATE_NEW_CONSOLE if os.name == 'nt' else 0)
            print("✅ Backtesting launched.")
            continue
        print("Invalid choice.")

    # 1b. Per-Trade Target is now trailing-based (Default $1.0)
    if recycler_mode:
        recycler_profit_usd = 1.0
        print(f"✅ Recycler: Trailing Profit Activated (Base: ${recycler_profit_usd:.2f})")


    # 2. Profit Target
    profit_pct = 0.01
    profit_usd = 0
    if recycler_mode:
        # For Recycler, we skip standard targets as it uses per-trade targets
        pass
    elif trailing_enabled:
        print(f"\n🛡️  PROTECTION: Using {strategy} ($10/$20 Tracking)")
    else:
        print("\n💰 SELECT PROFIT TARGET:")
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

        print("\nB. Or Enter Target USD ($):")
        while True:
            try:
                val = input("Target USD (e.g. 10, 20) [Enter 'T' for Smart Trailing 10-20]: ").strip().upper()
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
            print("Invalid choice. Please enter a positive number or 'T'.")

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
            choice = input("Choice (1-8) [Default 1]: ").strip()
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

    return [selected_symbol], strategy, timeframe, profit_pct, profit_usd, trailing_enabled, recycler_profit_usd, lot_size


def main():
    """Main function - CLI mode"""
    try:
        # Create necessary directories
        Path("logs").mkdir(exist_ok=True)
        Path("charts").mkdir(exist_ok=True)
        Path("models").mkdir(exist_ok=True)
        
        symbols, strategy, timeframe, profit_pct, profit_usd, trailing_enabled, recycler_profit_usd, lot_size = select_trade_setup()
        if symbols is None or strategy is None or timeframe is None:
            print("Exiting.")
            return
        
        trading_system = LiveTradingSystem()
        trading_system.symbols = symbols
        trading_system.strategy = strategy
        trading_system.timeframe = timeframe
        trading_system.profit_pct = profit_pct
        trading_system.trailing_enabled = trailing_enabled
        
        # Propagate lot size and profit targets to ALL components
        trading_system.grid_manager.lot_size = lot_size
        trading_system.grid_manager.per_trade_profit = recycler_profit_usd
        
        trading_system.grid_recycler.lot_size = lot_size
        trading_system.grid_recycler.per_trade_profit = recycler_profit_usd
        if profit_usd > 0:
            trading_system.profit_usd = profit_usd
        
        # Run trading loop
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
