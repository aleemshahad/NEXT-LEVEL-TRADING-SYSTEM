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
        """
        Check Forex Factory for HIGH-impact USD events.
        CACHING: Downloads FF calendar ONCE and saves to local file.
                 Refreshes every 6 hours. All other calls use local cache.
        TIME SYNC: All comparisons done in UTC.
        On BLOCK: Cancel pending orders. Open positions run to profit naturally.
        """
        try:
            cache_file = Path("logs/ff_calendar_cache.json")
            cache_max_age_hours = 6
            events = None

            # --- STEP 1: LOAD FROM CACHE OR DOWNLOAD ---
            need_download = True
            if cache_file.exists():
                file_age_hours = (time.time() - cache_file.stat().st_mtime) / 3600
                if file_age_hours < cache_max_age_hours:
                    # Cache is fresh, use it
                    with open(cache_file, 'r') as f:
                        events = json.load(f)
                    need_download = False

            if need_download:
                try:
                    import requests
                    url = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
                    response = requests.get(url, timeout=8)
                    if response.status_code == 200:
                        events = response.json()
                        cache_file.parent.mkdir(exist_ok=True)
                        with open(cache_file, 'w') as f:
                            json.dump(events, f)
                        logger.info(f"[FF Calendar] Downloaded & cached ({len(events)} events). Next refresh in {cache_max_age_hours}h.")
                    else:
                        logger.warning("[FF Calendar] Download failed, using stale cache if available.")
                        if cache_file.exists():
                            with open(cache_file, 'r') as f:
                                events = json.load(f)
                except Exception as download_err:
                    logger.warning(f"[FF Calendar] Network error: {download_err}. Using cache if available.")
                    if cache_file.exists():
                        with open(cache_file, 'r') as f:
                            events = json.load(f)

            if not events:
                self.sentiment_decision = "ALLOW"
                logger.info("[FF Calendar] No data available. Defaulting to ALLOW.")
                return

            # --- STEP 2: TIME SYNC (UTC reference) ---
            now_local_utc = datetime.utcnow()
            mt5_tick = mt5.symbol_info_tick("XAUUSDm") if mt5.terminal_info() else None
            if mt5_tick:
                mt5_server_utc = datetime.utcfromtimestamp(mt5_tick.time)
                time_diff_sec = abs((now_local_utc - mt5_server_utc).total_seconds())
                if time_diff_sec > 60:
                    logger.warning(f"[TIME] Clock drift! Local UTC: {now_local_utc.strftime('%H:%M:%S')} | MT5 UTC: {mt5_server_utc.strftime('%H:%M:%S')} | Diff: {time_diff_sec:.0f}s")
                now_utc = mt5_server_utc
            else:
                now_utc = now_local_utc

            # --- STEP 3: CHECK EVENTS FROM LOCAL CACHE ---
            block_window_min = 15
            blocking_event = None
            blocking_event_time = None

            for event in events:
                currency = event.get('currency', '').upper()
                impact   = event.get('impact', '').upper()
                if currency != 'USD' or 'HIGH' not in impact:
                    continue

                date_str = event.get('date', '')
                try:
                    event_time = datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%S%z").replace(tzinfo=None)
                except Exception:
                    try:
                        event_time = datetime.strptime(date_str[:19], "%Y-%m-%dT%H:%M:%S")
                    except Exception:
                        continue

                diff_minutes = (event_time - now_utc).total_seconds() / 60
                if -block_window_min <= diff_minutes <= block_window_min:
                    blocking_event = event.get('title', 'Unknown Event')
                    blocking_event_time = event_time
                    break

            # --- STEP 4: TAKE ACTION ---
            if blocking_event:
                self.sentiment_decision = "BLOCK"
                event_utc_str = blocking_event_time.strftime('%H:%M UTC') if blocking_event_time else "?"
                logger.warning(
                    f"[NEWS BLOCK] HIGH USD Event: '{blocking_event}' at {event_utc_str} | "
                    f"Now (UTC): {now_utc.strftime('%H:%M:%S')} | "
                    f"Window: +/-{block_window_min} min | Cancelling pending orders..."
                )
                if mt5.terminal_info():
                    for sym in ["XAUUSDm", "XAUUSD"]:
                        pending = mt5.orders_get(symbol=sym)
                        if pending:
                            cancelled = sum(
                                1 for o in pending
                                if mt5.order_send({"action": mt5.TRADE_ACTION_REMOVE, "order": o.ticket})
                                and mt5.order_send({"action": mt5.TRADE_ACTION_REMOVE, "order": o.ticket}).retcode == mt5.TRADE_RETCODE_DONE
                            )
                            if cancelled:
                                logger.warning(f"[NEWS BLOCK] Cancelled {cancelled} pending orders for {sym}. Open positions continue to trailing profit.")
            else:
                self.sentiment_decision = "ALLOW"
                logger.info(
                    f"[FF News] ALLOW | No HIGH USD events in +/-{block_window_min} min | "
                    f"UTC: {now_utc.strftime('%H:%M:%S')}"
                )

        except Exception as e:
            self.sentiment_decision = "ALLOW"
            logger.warning(f"[FF News] ALLOW (Error: {e})")

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

class MT5Broker:
    """MetaTrader 5 Broker Interface"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.connected = False
        
    async def connect(self) -> bool:
        """Connect to MT5 with robust retries and session clearing"""
        try:
            # Force close any hung sessions first
            mt5.shutdown()
            await asyncio.sleep(1)
            
            terminal_path = r"C:\Program Files\MetaTrader 5 EXNESS\terminal64.exe"
            
            success = False
            for i in range(3):
                logger.info(f"Connecting to MT5 (Attempt {i+1}/3)...")
                if mt5.initialize(path=terminal_path):
                    success = True
                    break
                logger.warning(f"Connection attempt {i+1} failed: {mt5.last_error()}")
                await asyncio.sleep(2)
                
            if not success:
                logger.error(f"MT5 could not be initialized after 3 attempts: {mt5.last_error()}")
                return False
                
            # Login with credentials
            login = self.config.get('login') or int(os.getenv('MT5_LOGIN', 0))
            password = self.config.get('password') or os.getenv('MT5_PASSWORD')
            server = self.config.get('server') or os.getenv('MT5_SERVER')
            
            logger.info(f"Logging into {server} (Account: {login})...")
            if login and password and server:
                if not mt5.login(login, password=password, server=server):
                    logger.error(f"MT5 login failed: {mt5.last_error()}")
                    # Fail-safe: Check if we are already logged in to this account
                    acc = mt5.account_info()
                    if acc and acc.login == login:
                        logger.info("Terminal is already logged into the correct account manually. Proceeding.")
                    else:
                        return False
            
            self.connected = True
            account_info = mt5.account_info()
            if account_info:
                logger.info(f"Connected to MT5 - Balance: ${account_info.balance:.2f}")
            return True
            
        except Exception as e:
            logger.error(f"MT5 connection error: {e}")
            return False
    
    async def is_connected(self) -> bool:
        """Check if MT5 is still connected and responsive"""
        try:
            # Check account info as a heartbeat
            acc = mt5.account_info()
            if acc is None:
                self.connected = False
                return False
            # Check terminal connection status
            terminal = mt5.terminal_info()
            if terminal and not terminal.connected:
                self.connected = False
                return False
            self.connected = True
            return True
        except:
            self.connected = False
            return False

    def get_market_data(self, symbol: str, timeframe: str = "M5", count: int = 500) -> pd.DataFrame:
        """Get market data from MT5"""
        try:
            # Map timeframe — matches ALL terminal options (M1, M3, M5, M15, M30, H1, H4, D1)
            tf_map = {
                "M1":  mt5.TIMEFRAME_M1,
                "M3":  mt5.TIMEFRAME_M3,
                "M5":  mt5.TIMEFRAME_M5,
                "M15": mt5.TIMEFRAME_M15,
                "M30": mt5.TIMEFRAME_M30,
                "H1":  mt5.TIMEFRAME_H1,
                "H4":  mt5.TIMEFRAME_H4,
                "D1":  mt5.TIMEFRAME_D1
            }

            timeframe_mt5 = tf_map.get(timeframe, mt5.TIMEFRAME_M5)
            rates = mt5.copy_rates_from_pos(symbol, timeframe_mt5, 0, count)
            
            if rates is None or len(rates) == 0:
                logger.warning(f"No data received for {symbol}")
                return pd.DataFrame()
                
            df = pd.DataFrame(rates)
            df['time'] = pd.to_datetime(df['time'], unit='s')
            df.set_index('time', inplace=True)
            
            return df
            
        except Exception as e:
            logger.error(f"Error getting market data: {e}")
            return pd.DataFrame()
    
    async def place_pending_order(self, symbol: str, order_type: int, volume: float, price: float, magic: int) -> Dict:
        """Place a pending limit order"""
        try:
            symbol_info = mt5.symbol_info(symbol)
            if not symbol_info:
                return {'success': False, 'error': f'Symbol {symbol} not found'}
            
            # CRITICAL: Round price to valid digits
            price = self.round_price(symbol, price)
            
            request = {
                "action": mt5.TRADE_ACTION_PENDING,
                "symbol": symbol,
                "volume": volume,
                "type": order_type,
                "price": price,
                "magic": magic,
                "comment": "GRID_ENTRY",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_RETURN, # Changed to RETURN for better compatibility
            }
            
            result = mt5.order_send(request)
            if result.retcode != mt5.TRADE_RETCODE_DONE:
                return {'success': False, 'error': f'Code {result.retcode}: {result.comment}'}
            
            return {'success': True, 'ticket': result.order}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def cancel_all_pendings(self, symbol: str):
        """Cancel all pending orders for a specific symbol"""
        try:
            orders = mt5.orders_get(symbol=symbol)
            if orders is None: return
            
            for o in orders:
                request = {
                    "action": mt5.TRADE_ACTION_REMOVE,
                    "order": o.ticket
                }
                result = mt5.order_send(request)
                if result.retcode != mt5.TRADE_RETCODE_DONE:
                    logger.error(f"Failed to cancel order {o.ticket}: {result.retcode}")
            logger.info(f"🧹 Cleaned all existing pending orders for {symbol}")
        except Exception as e:
            logger.error(f"Error canceling pendings: {e}")

    def close_all_side(self, symbol: str, side: str, magic: int = None):
        """Close all positions for a specific side (BUY/SELL)"""
        try:
            positions = mt5.positions_get(symbol=symbol)
            if not positions:
                return
            
            for p in positions:
                pos_side = 'BUY' if p.type == mt5.POSITION_TYPE_BUY else 'SELL'
                if pos_side == side and (magic is None or p.magic == magic):
                    # Close position
                    action = mt5.ORDER_TYPE_SELL if p.type == mt5.POSITION_TYPE_BUY else mt5.ORDER_TYPE_BUY
                    tick = mt5.symbol_info_tick(symbol)
                    if tick is None:
                        continue
                    price = tick.bid if p.type == mt5.POSITION_TYPE_BUY else tick.ask
                    
                    request = {
                        "action": mt5.TRADE_ACTION_DEAL,
                        "symbol": symbol,
                        "volume": p.volume,
                        "type": action,
                        "position": p.ticket,
                        "price": price,
                        "deviation": 200,
                        "magic": p.magic,
                        "comment": "CLOSE_GRID",
                        "type_time": mt5.ORDER_TIME_GTC,
                        "type_filling": mt5.ORDER_FILLING_IOC,
                    }
                    mt5.order_send(request)
        except Exception as e:
            logger.error(f"Error closing side {side}: {e}")

    def place_order(self, symbol: str, action: str, volume: float, price: float, 
                   stop_loss: float = None, take_profit: float = None) -> Dict:
        """Place trading order"""
        try:
            # Get symbol info
            symbol_info = mt5.symbol_info(symbol)
            if not symbol_info:
                return {'success': False, 'error': f'Symbol {symbol} not found'}
            
            # Prepare order request
            order_type = mt5.ORDER_TYPE_BUY if action == "BUY" else mt5.ORDER_TYPE_SELL
            
            # CRITICAL: Round all prices
            price = self.round_price(symbol, price)
            if stop_loss: stop_loss = self.round_price(symbol, stop_loss)
            if take_profit: take_profit = self.round_price(symbol, take_profit)

            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": symbol,
                "volume": volume,
                "type": order_type,
                "price": price,
                "deviation": 200,
                "magic": 234000,
                "comment": "NEXT_LEVEL_BRAIN",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }
            
            if stop_loss:
                request["sl"] = stop_loss
            if take_profit:
                request["tp"] = take_profit
            
            # Send order
            result = mt5.order_send(request)
            
            if result.retcode != mt5.TRADE_RETCODE_DONE:
                return {'success': False, 'error': f'Order failed: {result.retcode}'}
            
            logger.info(f"Order placed: {action} {volume} {symbol} at {price}")
            return {
                'success': True,
                'ticket': result.order,
                'price': result.price,
                'volume': result.volume
            }
            
        except Exception as e:
            logger.error(f"Order placement error: {e}")
            return {'success': False, 'error': str(e)}
    
    def get_positions(self) -> List[Dict]:
        """Get open positions"""
        try:
            positions = mt5.positions_get()
            if not positions:
                return []
                
            return [
                {
                    'ticket': pos.ticket,
                    'symbol': pos.symbol,
                    'type': 'BUY' if pos.type == mt5.POSITION_TYPE_BUY else 'SELL',
                    'volume': pos.volume,
                    'price_open': pos.price_open,
                    'price_current': pos.price_current,
                    'profit': pos.profit,
                    'swap': pos.swap,
                    'magic': pos.magic,
                    'time': datetime.fromtimestamp(pos.time)
                }
                for pos in positions
            ]
            
        except Exception as e:
            logger.error(f"Error getting positions: {e}")
            return []

    def round_price(self, symbol: str, price: float) -> float:
        """Round price to valid symbol digits"""
        try:
            info = mt5.symbol_info(symbol)
            if info:
                return round(price, info.digits)
            return round(price, 2) # Default for Gold/XAU if info fails
        except:
            return price

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
        self.profit_threshold_pct = grid_config.get('profit_target_pct', 0.25) # 25% profit target
        self.profit_target_usd = grid_config.get('profit_target_usd', 0) # Fixed $ profit target
        self.mode = grid_config.get('mode', 'BOTH') # Added mode: BOTH, BUY_ONLY, SELL_ONLY
        self.active_grids = {} # symbol -> {'type': 'BUY/SELL', 'base_price': float, 'last_index': int}
        self.batch_size = 10
        self.trigger_threshold = 2 # Place next batch if 8 orders are hit (only 2 pendings left)
        self.total_target = self.grid_size # Default 300
        self.time_frame_str = "M5" # Default, synced from terminal input
        
        # Mapping for MT5 Timeframes
        self.TIMEFRAME_MAP = {
            "M1": mt5.TIMEFRAME_M1, "M3": mt5.TIMEFRAME_M3, "M5": mt5.TIMEFRAME_M5,
            "M15": mt5.TIMEFRAME_M15, "M30": mt5.TIMEFRAME_M30, "H1": mt5.TIMEFRAME_H1,
            "H4": mt5.TIMEFRAME_H4, "D1": mt5.TIMEFRAME_D1
        }
        
        # State Persistence
        self.state_file = Path("logs/grid_state.json")
        self.is_closing = False # Guard to prevent multiple close calls in rapid loops
        self._load_state()

    def _save_state(self):
        """Save grid progress to file"""
        try:
            self.state_file.parent.mkdir(exist_ok=True)
            with open(self.state_file, 'w') as f:
                json.dump(self.active_grids, f)
        except Exception as e:
            logger.error(f"Failed to save grid state: {e}")

    def _calculate_grid_offset(self, k: int) -> float:
        """Calculate cumulative offset for k-th grid level with dynamic spacing"""
        offset = 0.0
        for i in range(1, k + 1):
            if i <= 10:
                offset += 1.0 # 1st 10: $1 space
            elif i <= 20:
                offset += 2.0 # 2nd 10: $2 space
            elif i <= 30:
                offset += 3.0 # 3rd 10: $3 space
            elif i <= 40:
                offset += 4.0 # 4th 10: $4 space
            else:
                offset += 5.0 # 5th to 300th: $5 space
        return offset

    async def _detect_market_condition(self, symbol):
        """Detect trend, ranges, and volatility (ATR/ADX) based on selected timeframe (Last 50 candles)"""
        try:
            tf = self.TIMEFRAME_MAP.get(self.time_frame_str, mt5.TIMEFRAME_M5)
            # Fetch 50 candles to compute 14-period ATR and ADX accurately
            rates = mt5.copy_rates_from_pos(symbol, tf, 0, 50)
            if rates is not None and len(rates) >= 40:
                df = pd.DataFrame(rates)
                
                # 1. Pivot Logic (Last 20)
                rates_20 = rates[-20:]
                open_start = rates_20[0]['open']
                close_now = rates_20[-1]['close']
                h20 = max([r['high'] for r in rates_20])
                l20 = min([r['low'] for r in rates_20])
                pivot = (h20 + l20) / 2
                
                # 2. ATR Calculation (14 period)
                df['tr'] = np.maximum(df['high'] - df['low'], 
                                    np.maximum(abs(df['high'] - df['close'].shift(1)), 
                                               abs(df['low'] - df['close'].shift(1))))
                atr = df['tr'].rolling(14).mean().iloc[-1]
                avg_atr_long = df['tr'].rolling(40).mean().iloc[-1] # Baseline volatility
                
                # 3. ADX Calculation (14 period - Simplified)
                df['up_move'] = df['high'] - df['high'].shift(1)
                df['down_move'] = df['low'].shift(1) - df['low']
                
                df['plus_dm'] = np.where((df['up_move'] > df['down_move']) & (df['up_move'] > 0), df['up_move'], 0)
                df['minus_dm'] = np.where((df['down_move'] > df['up_move']) & (df['down_move'] > 0), df['down_move'], 0)
                
                tr_14 = df['tr'].rolling(14).sum()
                plus_di = 100 * (df['plus_dm'].rolling(14).sum() / tr_14)
                minus_di = 100 * (df['minus_dm'].rolling(14).sum() / tr_14)
                
                df['dx'] = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
                adx = df['dx'].rolling(14).mean().iloc[-1]
                
                # Safety Thresholds
                # DANGEROUS if ADX > 35 (Strong Trend) OR ATR is 2x normal (High Volatility)
                volatility_dangerous = (adx > 35) or (atr > avg_atr_long * 2.0)
                
                trend = 'BULLISH' if close_now > open_start else ('BEARISH' if close_now < open_start else 'NEUTRAL')
                return {
                    'trend': trend, 'pivot': pivot, 'high': h20, 'low': l20,
                    'atr': atr, 'adx': adx, 'volatility_dangerous': volatility_dangerous
                }
            return {'trend': 'NEUTRAL', 'pivot': 0, 'atr': 0, 'adx': 0, 'volatility_dangerous': False}
        except Exception as e:
            logger.error(f"Detection error: {e}")
            return {'trend': 'NEUTRAL', 'pivot': 0, 'atr': 0, 'adx': 0, 'volatility_dangerous': False}

    def _load_state(self):
        """Load grid progress from file"""
        try:
            if self.state_file.exists() and self.state_file.stat().st_size > 0:
                with open(self.state_file, 'r') as f:
                    self.active_grids = json.load(f)
                logger.info(f"📁 Loaded Grid State from {self.state_file}")
            else:
                self.active_grids = {}
        except json.JSONDecodeError:
            logger.warning("⚠️ Grid state file was corrupt. Starting fresh.")
            self.active_grids = {}
        except Exception as e:
            logger.error(f"Failed to load grid state: {e}")
            self.active_grids = {}

    async def update(self, symbol, current_price, bias, balance):
        """Update grid logic based on bias and profit"""
        if not hasattr(self, '_last_vol_warn'): self._last_vol_warn = {}
        if not hasattr(self, '_last_grid_log'): self._last_grid_log = {}
        try:
            # Option 1: Grid Both Logic
            if self.mode == "GRID_BOTH":
                # Check for existing positions first to decide if we can switch
                positions = self.broker.get_positions()
                symbol_positions = [p for p in positions if p['symbol'] == symbol]
                grid_info = self.active_grids.get(symbol, {})
                
                # Check for Switch (If no positions are open and market moves $20.0)
                if grid_info and not symbol_positions:
                    bp = grid_info.get('base_price', current_price)
                    # If market moves UP -> Switch to SELL Grid (Catching pullback)
                    if current_price > bp + 20.0:
                        logger.info(f"🔄 Grid Both Switch: Market moved UP ${current_price - bp:.2f} ($20 threshold hit). Switching to SELL Grid to catch pullback.")
                        self.broker.cancel_all_pendings(symbol)
                        del self.active_grids[symbol]
                        bias = "BULLISH" # SELL direction
                    # If market moves DOWN -> Switch to BUY Grid
                    elif current_price < bp - 20.0:
                        logger.info(f"🔄 Grid Both Switch: Market moved DOWN ${bp - current_price:.2f} ($20 threshold hit). Switching to BUY Grid to catch bounce.")
                        self.broker.cancel_all_pendings(symbol)
                        del self.active_grids[symbol]
                        bias = "BEARISH" # BUY direction
                
                # Decision if no grid active
                if not self.active_grids.get(symbol):
                    data = await self._detect_market_condition(symbol)
                    
                    pivot = data['pivot']
                    h20   = data.get('high', 0)
                    l20   = data.get('low', 0)
                    adx   = data.get('adx', 0)
                    atr   = data.get('atr', 0)

                    if pivot > 0:
                        now_t = time.time()
                        if now_t - self._last_grid_log.get(symbol, 0) > 30:
                            # Full indicator log — matches TradingView indicator panel
                            logger.info(
                                f"[Indicator] TF:{self.time_frame_str} | "
                                f"H20:{h20:.2f} | L20:{l20:.2f} | "
                                f"Pivot:{pivot:.2f} | Price:{current_price:.2f} | "
                                f"ADX:{adx:.1f} | ATR:{atr:.2f}"
                            )
                            self._last_grid_log[symbol] = now_t

                        if current_price > pivot:
                            bias = 'BULLISH' # SELL direction
                            logger.info(f"[Grid Both] Price ABOVE Pivot -> SELL Grid selected")
                        elif current_price < pivot:
                            bias = 'BEARISH' # BUY direction
                            logger.info(f"[Grid Both] Price BELOW Pivot -> BUY Grid selected")
                        else:
                            bias = 'NEUTRAL'
                    
                    # VOLATILITY FILTER Relocated: Moved after trailing profit check

            # 1. Check profit targets for existing positions
            positions = self.broker.get_positions()
            symbol_positions = [p for p in positions if p['symbol'] == symbol]
            
            # Filter Grid positions
            buy_positions = [p for p in symbol_positions if p['type'] == 'BUY' and p.get('magic') == self.magic_buy]
            sell_positions = [p for p in symbol_positions if p['type'] == 'SELL' and p.get('magic') == self.magic_sell]
            
            # Net PnL (including swap)
            buy_profit = sum(p['profit'] + p.get('swap', 0) for p in buy_positions)
            sell_profit = sum(p['profit'] + p.get('swap', 0) for p in sell_positions)
            total_grid_profit = buy_profit + sell_profit
            
            # Updated Trailing: No Balance Target, Start as soon as profit is positive ($1+)
            if symbol not in self.active_grids:
                self.active_grids[symbol] = {}
            grid_info = self.active_grids[symbol]
            
            # Start tracking peak immediately when in profit
            if total_grid_profit > 1.0:
                if 'peak_usd' not in grid_info:
                    grid_info['peak_usd'] = total_grid_profit
                    logger.info(f"🛡️ Trailing Activated for {symbol}: Booking Style - 1% Drop from Peak Profit")
                elif total_grid_profit > grid_info.get('peak_usd', 0):
                    grid_info['peak_usd'] = total_grid_profit

            if 'peak_usd' in grid_info:
                if self.is_closing: return
                # NEW LOGIC: Tight Trailing that NEVER goes into loss
                # Distance is 10% of peak, but at least $2.0 for stability
                trailing_dist = max(grid_info['peak_usd'] * 0.10, 2.0)
                lock_level_usd = grid_info['peak_usd'] - trailing_dist
                
                # FINAL PROTECTION: Lock must NEVER be below $1.0 (Minimum base profit)
                if lock_level_usd < 1.0:
                    lock_level_usd = 1.0

                now = time.time()
                if not hasattr(self, '_last_log_time'): self._last_log_time = 0
                if now - self._last_log_time > 10:
                    logger.info(f"📊 Trailing {symbol}: Current ${total_grid_profit:.2f} | Lock: ${lock_level_usd:.2f} (Peak: ${grid_info['peak_usd']:.2f})")
                    self._last_log_time = now

                # CRITICAL: Only close if we are still in POSITIVE profit
                # This prevents slippage from turning a trail into a loss-cut
                if total_grid_profit < lock_level_usd:
                    if total_grid_profit > 0.50: # Must be at least $0.50 to book
                        self.is_closing = True # Set guard
                        logger.info(f"⏹️ Trailing Lock Hit: ${total_grid_profit:.2f} < ${lock_level_usd:.2f}. Closing All Orders.")
                        self.broker.close_all_side(symbol, 'BUY', self.magic_buy)
                        self.broker.close_all_side(symbol, 'SELL', self.magic_sell)
                        self.broker.cancel_all_pendings(symbol)
                        if symbol in self.active_grids:
                            del self.active_grids[symbol]
                        self._save_state()
                        self.is_closing = False # Reset guard
                        return 
                    else:
                        # Profit dropped below safety, reset peak and wait for recovery
                        # This prevents 'Trailing Lock Hit: $-7.51' issues
                        if total_grid_profit < 0:
                            logger.warning(f"⚠️ Trail slipped into loss (${total_grid_profit:.2f}). Waiting for recovery.")
                            if 'peak_usd' in grid_info: del grid_info['peak_usd'] 
            else:
                # Basic status log before entering profit
                now = time.time()
                if not hasattr(self, '_last_log_time'): self._last_log_time = 0
                if now - self._last_log_time > 10:
                    logger.info(f"📊 Basket {symbol} Current PnL: ${total_grid_profit:.2f} (Waiting for profit to start trailing)")
                    self._last_log_time = now

            # 2. Place Grid
            # Check Account Limits (Fix for Error 10033)
            acc_info = mt5.account_info()
            effective_grid_size = self.grid_size
            if acc_info and acc_info.limit_orders > 0:
                # If broker limit is e.g. 100, we must stay below it
                # We subtract current positions/pendings to be safe
                active_count = len(positions) + (len(mt5.orders_get()) if mt5.orders_get() else 0)
                available = max(0, acc_info.limit_orders - active_count - 5)
                if effective_grid_size > available:
                    effective_grid_size = available
                    if available < 5: 
                        return # Not enough room for a grid

            # SELL Grid Placement
            # Mode SELL_ONLY OR (BOTH with Bullish bias) OR (GRID_BOTH with Bullish bias)
            can_place_sell = (self.mode == 'SELL_ONLY') or \
                             (self.mode == 'BOTH' and bias == 'BULLISH') or \
                             (self.mode == 'GRID_BOTH' and bias == 'BULLISH')
            
            if can_place_sell:
                # In GRID_BOTH, don't place SELL if a BUY grid already exists for this symbol
                if self.mode == 'GRID_BOTH' and symbol in self.active_grids and self.active_grids[symbol].get('type') == 'BUY':
                    can_place_sell = False # Block placement
                
            if can_place_sell:
                active_pendings = mt5.orders_get(symbol=symbol)
                sell_pendings = [o for o in active_pendings if o.magic == self.magic_sell] if active_pendings else []
                sell_positions = [p for p in symbol_positions if p['type'] == 'SELL' and p.get('magic') == self.magic_sell]
                
                # Check if we need to start or add a batch
                grid_info = self.active_grids.get(symbol, {})
                if grid_info.get('type') != 'SELL': grid_info = {} # Reset if direction changed
                
                last_index = grid_info.get('last_index', 0)
                
                # Trigger: No pendings/positions OR only trigger_threshold pendings left AND haven't reached total_target
                if (not sell_pendings and not sell_positions) or (len(sell_pendings) <= self.trigger_threshold and last_index < self.total_target):
                    
                    if not sell_pendings and not sell_positions:
                        last_index = 0 # Fresh start
                        base_price = current_price  # Always anchor to current price
                        if self.mode == 'GRID_BOTH':
                            data = await self._detect_market_condition(symbol)
                            
                            # VOLATILITY FILTER
                            if data.get('volatility_dangerous'):
                                now = time.time()
                                if now - self._last_vol_warn.get(symbol, 0) > 30:
                                    logger.warning(f"[VOL] SELL Grid paused. ADX: {data['adx']:.1f} too high.")
                                    self._last_vol_warn[symbol] = now
                                return
                            # Log only once per 30 sec
                            now_t = time.time()
                            if now_t - self._last_grid_log.get(f"{symbol}_sell_start", 0) > 30:
                                logger.info(f"[Grid] Starting SELL Grid for {symbol} at {base_price:.2f} (Pivot direction: {data['pivot']:.2f}) | ADX: {data['adx']:.1f}")
                                self._last_grid_log[f"{symbol}_sell_start"] = now_t
                        else:
                            logger.info(f"[Grid] Starting NEW SELL Grid for {symbol} at {base_price:.2f}")
                    else:
                        base_price = grid_info.get('base_price', current_price)
                        logger.info(f"🔄 Staggered Batch: Placing next set of SELL orders for {symbol} (Last Index: {last_index})")

                    num_to_place = min(self.batch_size, self.total_target - last_index)
                    if num_to_place > 0:
                        success_count = 0
                        for i in range(1, num_to_place + 1):
                            k = last_index + i
                            entry_price = base_price + self._calculate_grid_offset(k)
                            # Safety: Skip orders behind current price (for Sell Limits)
                            if entry_price < current_price + 0.10: continue 
                            res = await self.broker.place_pending_order(symbol, mt5.ORDER_TYPE_SELL_LIMIT, self.lot_size, entry_price, self.magic_sell)
                            if res['success']: 
                                success_count += 1
                            else:
                                logger.warning(f"⚠️ Failed to place SELL order at {entry_price}: {res.get('error')}. Skipping to avoid loop.")
                        
                        if success_count > 0:
                            self.active_grids[symbol] = {
                                'type': 'SELL', 
                                'base_price': base_price,
                                'last_index': last_index + success_count
                            }
                            # Important: In Grid Both, we might need to preserve peak if it was already tracking
                            if 'peak_usd' in grid_info: self.active_grids[symbol]['peak_usd'] = grid_info['peak_usd']
                            
                            self._save_state()
                            logger.info(f"✅ {success_count} SELL orders added. Total placed in sequence: {last_index + success_count}/{self.total_target}")

            # VOLATILITY FILTER: Applied here to block entry/expansion WITHOUT blocking trailing exits
            data = await self._detect_market_condition(symbol)
            if data.get('volatility_dangerous'):
                now_t = time.time()
                if now_t - self._last_vol_warn.get(symbol, 0) > 30:
                    logger.warning(f"⚠️ DANGER: High Trend/Volatility — Grid Expansion/Entry Paused. ADX: {data['adx']:.1f} | ATR: {data['atr']:.2f}")
                    self._last_vol_warn[symbol] = now_t
                return

                # Case A: Market pushes HIGHER (Trend Extension) - Sequential Batch Placement
                bp = grid_info.get('base_price', current_price)
                current_offset = current_price - bp
                
                # If price moves beyond our current grid coverage, add the NEXT sequential batch
                # Anchoring BP exactly to current price to ensure next spacing is perfect
                if current_offset > self._calculate_grid_offset(last_index) and last_index < self.total_target:
                    # Anchor bp so the NEXT sequential index starts exactly at current price level
                    new_bp = current_price - self._calculate_grid_offset(last_index)
                    self.active_grids[symbol]['base_price'] = new_bp
                    bp = new_bp
                    
                    num_to_add = min(self.batch_size, self.total_target - last_index)
                    if num_to_add > 0:
                        logger.info(f"📈 Market pushed higher ({current_price}). Expanding SELL grid by {num_to_add} orders.")
                        success_count = 0
                        for i in range(1, num_to_add + 1):
                            k = last_index + i
                            entry_price = bp + self._calculate_grid_offset(k)
                            res = await self.broker.place_pending_order(symbol, mt5.ORDER_TYPE_SELL_LIMIT, self.lot_size, entry_price, self.magic_sell)
                            if res['success']: 
                                success_count += 1
                            else:
                                logger.warning(f"⚠️ Failed to expand SELL grid at {entry_price}: {res.get('error')}")
                        
                        if success_count > 0:
                            self.active_grids[symbol]['last_index'] += success_count
                            self._save_state()

                # Case B: Market pushes LOWER (Gap Filling) - No positions open, shift grid to follow market down
                elif not sell_positions and current_price < bp - 1.0: # Using 1.0 threshold
                    # Calculate new base to be near current price
                    new_base = current_price
                    logger.info(f"📉 Market moved down ({current_price}). Shifting SELL grid base. Fresh orders will follow.")
                    
                    # Cancel existing to restart at new price
                    self.broker.cancel_all_pendings(symbol)
                    self.active_grids[symbol] = {
                        'type': 'SELL',
                        'base_price': new_base,
                        'peak_pct': grid_info.get('peak_pct', 0), # Preserve trailing peak
                        'last_index': 0
                    }
                    self._save_state()

            # BUY Grid Placement
            # Mode BUY_ONLY OR (BOTH with Bearish bias) OR (GRID_BOTH with Bearish bias)
            can_place_buy = (self.mode == 'BUY_ONLY') or \
                            (self.mode == 'BOTH' and bias == 'BEARISH') or \
                            (self.mode == 'GRID_BOTH' and bias == 'BEARISH')
            
            if can_place_buy:
                # In GRID_BOTH, don't place BUY if a SELL grid already exists for this symbol
                if self.mode == 'GRID_BOTH' and symbol in self.active_grids and self.active_grids[symbol].get('type') == 'SELL':
                    can_place_buy = False # Block placement

            if can_place_buy:
                active_pendings = mt5.orders_get(symbol=symbol)
                buy_pendings = [o for o in active_pendings if o.magic == self.magic_buy] if active_pendings else []
                buy_positions = [p for p in symbol_positions if p['type'] == 'BUY' and p.get('magic') == self.magic_buy]

                # Check if we need to start or add a batch
                grid_info = self.active_grids.get(symbol, {})
                if grid_info.get('type') != 'BUY': grid_info = {} # Reset if direction changed

                last_index = grid_info.get('last_index', 0)

                # Trigger: No pendings/positions OR only trigger_threshold pendings left AND haven't reached total_target
                if (not buy_pendings and not buy_positions) or (len(buy_pendings) <= self.trigger_threshold and last_index < self.total_target):
                    
                    if not buy_pendings and not buy_positions:
                        last_index = 0 # Fresh start
                        base_price = current_price
                        # Grid Both: Anchor to Pivot
                        if self.mode == 'GRID_BOTH':
                            data = await self._detect_market_condition(symbol)
                            
                            # VOLATILITY FILTER: Don't start new grid in high trend
                            if data.get('volatility_dangerous'):
                                now = time.time()
                                if now - self._last_vol_warn.get(symbol, 0) > 30:
                                    logger.warning(f"[VOL] BUY Grid paused. ADX: {data['adx']:.1f} too high.")
                                    self._last_vol_warn[symbol] = now
                                return
                            # Log only once per 30 sec
                            now_t = time.time()
                            if now_t - self._last_grid_log.get(f"{symbol}_buy_start", 0) > 30:
                                logger.info(f"[Grid] Starting BUY Grid for {symbol} at {base_price:.2f} (Pivot direction: {data['pivot']:.2f}) | ADX: {data['adx']:.1f}")
                                self._last_grid_log[f"{symbol}_buy_start"] = now_t
                        else:
                            logger.info(f"[Grid] Starting NEW BUY Grid for {symbol} at {base_price:.2f}")
                    else:
                        base_price = grid_info.get('base_price', current_price)
                        logger.info(f"🔄 Staggered Batch: Placing next set of BUY orders for {symbol} (Last Index: {last_index})")

                    num_to_place = min(self.batch_size, self.total_target - last_index)
                    if num_to_place > 0:
                        success_count = 0
                        for i in range(1, num_to_place + 1):
                            k = last_index + i
                            entry_price = base_price - self._calculate_grid_offset(k)
                            # Safety: Skip orders behind current price (for Buy Limits)
                            if entry_price > current_price - 0.10: continue
                            res = await self.broker.place_pending_order(symbol, mt5.ORDER_TYPE_BUY_LIMIT, self.lot_size, entry_price, self.magic_buy)
                            if res['success']: 
                                success_count += 1
                            else:
                                logger.warning(f"⚠️ Failed to place BUY order at {entry_price}: {res.get('error')}. Skipping to avoid loop.")
                        
                        if success_count > 0:
                            self.active_grids[symbol] = {
                                'type': 'BUY', 
                                'base_price': base_price,
                                'last_index': last_index + success_count
                            }
                            # Important: Preserve peak if it was already tracking
                            if 'peak_usd' in grid_info: self.active_grids[symbol]['peak_usd'] = grid_info['peak_usd']
                            
                            self._save_state()
                            logger.info(f"✅ {success_count} BUY orders added. Total placed in sequence: {last_index + success_count}/{self.total_target}")

            # VOLATILITY FILTER: Applied here to block expansion WITHOUT blocking trailing exits
            data = await self._detect_market_condition(symbol)
            if data.get('volatility_dangerous'):
                now_t = time.time()
                if now_t - self._last_vol_warn.get(symbol, 0) > 30:
                    logger.warning(f"⚠️ DANGER: High Trend/Volatility — Grid Expansion/Entry Paused. ADX: {data['adx']:.1f} | ATR: {data['atr']:.2f}")
                    self._last_vol_warn[symbol] = now_t
                return

                # Case A: Market pushes LOWER (Trend Extension) - Sequential Batch Placement
                bp = grid_info.get('base_price', current_price)
                current_offset = bp - current_price
                
                # If price moves beyond current coverage, add the NEXT batch sequentially
                # Anchoring BP exactly to current price to ensure next spacing is perfect
                if current_offset > self._calculate_grid_offset(last_index) and last_index < self.total_target:
                    # Anchor bp so the NEXT sequential index starts exactly at current price level
                    new_bp = current_price + self._calculate_grid_offset(last_index)
                    self.active_grids[symbol]['base_price'] = new_bp
                    bp = new_bp
                    
                    num_to_add = min(self.batch_size, self.total_target - last_index)
                    if num_to_add > 0:
                        logger.info(f"📉 Market pushed lower ({current_price}). Expanding BUY grid by {num_to_add} orders.")
                        success_count = 0
                        for i in range(1, num_to_add + 1):
                            k = last_index + i
                            entry_price = bp - self._calculate_grid_offset(k)
                            res = await self.broker.place_pending_order(symbol, mt5.ORDER_TYPE_BUY_LIMIT, self.lot_size, entry_price, self.magic_buy)
                            if res['success']: 
                                success_count += 1
                            else:
                                logger.warning(f"⚠️ Failed to expand BUY grid at {entry_price}: {res.get('error')}")
                        
                        if success_count > 0:
                            self.active_grids[symbol]['last_index'] += success_count
                            self._save_state()

                # Case B: Market pushes HIGHER (Gap Filling) - No positions open, shift grid to follow market up
                elif not buy_positions and current_price > bp + 1.0: # Using 1.0 threshold
                    new_base = current_price
                    logger.info(f"📈 Market moved up ({current_price}). Shifting BUY grid base. Fresh orders will follow.")
                    
                    # Cancel existing to restart at new price
                    self.broker.cancel_all_pendings(symbol)
                    self.active_grids[symbol] = {
                        'type': 'BUY',
                        'base_price': new_base,
                        'peak_pct': grid_info.get('peak_pct', 0), # Preserve trailing peak
                        'last_index': 0
                    }
                    self._save_state()

        except Exception as e:
            logger.error(f"Error in grid update: {e}")

class LiveTradingSystem:
    """Main Live Trading System"""
    
    def __init__(self, config_path: str = "config.yaml"):
        self.config = self._load_config(config_path)
        self.broker = MT5Broker(self.config.get('mt5', {}))
        self.ai_brain = TradingBrain()
        self.ict_analyzer = ICTAnalyzer()
        self.risk_manager = RiskManager(self.config.get('risk', {}))
        self.grid_manager = GridManager(self.broker, self.config)
        
        self.running = False
        self.symbols = self.config.get('symbols', ['XAUUSDm'])
        self.timeframe = self.config.get('timeframe', 'M5')
        self.strategy = "ICT SMC" # Default strategy
        
        # Performance tracking
        self.trades_today = 0
        self.daily_pnl = 0.0
        self.reset_timestamp = self._load_reset_time()
        self.trade_history = []
        self.reports_dir = Path("logs/live_reports")
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        self.session_max_drawdown = 0.0 # NEW: Track floating minus in trading loop
        self._current_biases = {} # Track last detected bias for each symbol
        
    def _save_reset_time(self, timestamp):
        try:
            config_file = Path("logs/reset_config.json")
            config_file.parent.mkdir(exist_ok=True)
            with open(config_file, 'w') as f:
                json.dump({'reset_timestamp': timestamp}, f)
        except Exception as e:
            logger.error(f"Failed to save reset config: {e}")

    def _load_reset_time(self):
        try:
            config_file = Path("logs/reset_config.json")
            if config_file.exists():
                with open(config_file, 'r') as f:
                    return json.load(f).get('reset_timestamp', 0)
        except Exception as e:
            logger.warning(f"Failed to load reset config, starting fresh: {e}")
        return 0

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
            
            # Connect to broker
            if not await self.broker.connect():
                logger.error("Failed to connect to MT5")
                return False
            
            # Get account info
            account_info = mt5.account_info()
            if account_info:
                self.start_balance = account_info.balance
                logger.info(f"Account Balance: ${self.start_balance:.2f}")
            
            # Cleanup old pending orders first
            for symbol in self.symbols:
                self.broker.cancel_all_pendings(symbol)
            
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
            
            # CRITICAL FIX: Use Real-time Tick Price for Gold instead of candle close to avoid slippage/invalid price
            tick = mt5.symbol_info_tick(symbol)
            if not tick: return
            current_price = tick.bid
            
            bias = ai_analysis.get('bias', 'NEUTRAL')
            self._current_biases[symbol] = bias
            
            # 1. Grid Strategy Logic
            if "Grid" in self.strategy:
                # Set mode based on strategy name
                if "Grid Both" in self.strategy:
                    self.grid_manager.mode = "GRID_BOTH"
                elif "BUY ONLY" in self.strategy:
                    self.grid_manager.mode = "BUY_ONLY"
                elif "SELL ONLY" in self.strategy:
                    self.grid_manager.mode = "SELL_ONLY"
                else:
                    self.grid_manager.mode = "BOTH"
                
                # Sync timeframe selection to GridManager
                self.grid_manager.time_frame_str = self.timeframe
                
                await self.grid_manager.update(symbol, current_price, bias, balance)
            
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
            
            # NEW: Track session max floating minus
            current_pnl = sum(p['profit'] for p in positions)
            if current_pnl < self.session_max_drawdown:
                self.session_max_drawdown = current_pnl
                
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
                daily_change = current_balance - self.start_balance
                
                print(f"\n{'='*50}")
                print(f"🧠 NEXT LEVEL BRAIN - LIVE TRADING STATUS")
                print(f"{'='*50}")
                print(f"💰 Balance: ${current_balance:.2f}")
                print(f"📈 Daily P&L: ${daily_change:.2f}")
                print(f"📊 Trades Today: {self.trades_today}")
                print(f"🎯 AI Memories: {len(self.ai_brain.memories)}")
                print(f"⏰ Last Update: {datetime.now().strftime('%H:%M:%S')}")
                print(f"📂 Reports Path: {self.reports_dir.absolute()}")
                
                positions = self.broker.get_positions()
                if positions:
                    print(f"📋 Open Positions: {len(positions)}")
                    for pos in positions:
                        print(f"  {pos['symbol']}: {pos['type']} ${pos['profit']:.2f}")
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
            logger.info("🚀 Starting live trading with RAPID MONITORING (1s heartbeat)...")
            
            # Start a separate high-frequency monitoring task
            monitor_task = asyncio.create_task(self._monitor_heartbeat())
            
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
                    
                    # Display status every 10 cycles
                    if cycle_count % 10 == 0:
                        self.display_status()
                    
                    # Analyze each symbol
                    for symbol in self.symbols:
                        await self.analyze_and_trade(symbol)
                        await asyncio.sleep(1)  # Small delay between symbols
                    
                    # Monitor positions
                    await self.monitor_positions()
                    
                    # Update session history and save partial report
                    self._update_session_history()
                    if cycle_count % 20 == 0:
                        self.generate_session_report()
                    
                    # Wait before next analysis cycle
                    await asyncio.sleep(5)  # 5 second analysis cycle (monitoring is now handled by heartbeat)
                    
                except KeyboardInterrupt:
                    logger.info("Shutdown signal received")
                    break
                except Exception as e:
                    logger.error(f"Trading loop error: {e}")
                    # If it's a network error, MT5 calls might fail
                    await asyncio.sleep(5)
            
        finally:
            self.running = False
            await self.shutdown()

    async def _monitor_heartbeat(self):
        """High-frequency position monitoring and trailing lock check (Every 1 second)"""
        logger.info("💓 Position Heartbeat Monitor Started")
        while self.running:
            try:
                # 1. Update Grid/Trailing Logic (CRITICAL)
                # We fetch current price for Gold (or 1st symbol) to keep it fast
                if self.symbols:
                    symbol = self.symbols[0]
                    tick = mt5.symbol_info_tick(symbol)
                    if tick:
                        acc = mt5.account_info()
                        balance = acc.balance if acc else 0
                        # We trigger GridManager update frequently for the trailing lock
                        # USE persistent bias to allow expansion during heartbeat
                        last_bias = self._current_biases.get(symbol, "NEUTRAL")
                        await self.grid_manager.update(symbol, tick.bid, last_bias, balance)

                # 2. General position monitoring
                await self.monitor_positions()
                
            except Exception as e:
                logger.error(f"Heartbeat monitor error: {e}")
            
            await asyncio.sleep(0.1) # 10 checks per second (Ultra-Fast)
    
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
                if d.entry == 1 and d.time > self.reset_timestamp: # DEAL_ENTRY_OUT + Reset Filter
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
        """Generate a detailed report in both MD and HTML/CSS formats with charts"""
        try:
            if not self.trade_history:
                return None
            
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            md_report_file = self.reports_dir / f"live_performance_{timestamp}.md"
            html_report_file = self.reports_dir / f"performance_report_{timestamp}.html"
            
            # Advanced metrics calculation
            profits = [t['profit'] for t in self.trade_history]
            wins = [p for p in profits if p > 0]
            losses = [p for p in profits if p <= 0]
            
            total_trades = len(profits)
            total_pnl = sum(profits)
            total_loss = abs(sum(losses))
            win_rate = (len(wins) / total_trades * 100) if total_trades else 0
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
            
            # 1. Generate Markdown Report
            report_lines = [
                "# 🧠 NEXT LEVEL BRAIN - LIVE PERFORMANCE REPORT",
                f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                f"**Tracking Period:** Last 30 Days",
                f"**Strategy:** {self.strategy}",
                "\n## 📊 PERFORMANCE SUMMARY",
                f"- **Total Trades:** {total_trades}",
                f"- **Win Rate:** {win_rate:.1f}%",
                f"- **Total P&L:** ${total_pnl:.2f}",
                f"- **Total Minus (Loss):** -${total_loss:.2f}",
                f"- **Profit Factor:** {profit_factor:.2f}",
                f"- **Max Drawdown:** {max_dd_pct:.2f}%",
                "\n## 📋 RECENT TRADE LOG (Last 50)",
                "| Time | Symbol | Side | Lots | Profit ($) | Comment |",
                "|------|--------|------|------|------------|---------|"
            ]
            
            sorted_history = sorted(self.trade_history, key=lambda x: x['time'], reverse=True)
            for t in sorted_history[:50]:
                report_lines.append(f"| {t['time']} | {t['symbol']} | {t['type']} | {t['volume']} | {t['profit']:.2f} | {t['comment']} |")
            
            with open(md_report_file, 'w', encoding='utf-8') as f:
                f.write("\n".join(report_lines))

            # 2. Generate Premium HTML Report
            chart_labels = json.dumps([t['time'] for t in sorted(self.trade_history, key=lambda x: x['time'])])
            chart_data = json.dumps(list(cum_pnl))
            pnl_color = "#00e676" if total_pnl >= 0 else "#ff5252"
            
            table_rows = ""
            for t in sorted_history[:100]:
                p_color = "profit-pos" if t['profit'] >= 0 else "profit-neg"
                table_rows += f"""
                <tr>
                    <td>{t['time']}</td>
                    <td>{t['symbol']}</td>
                    <td>{t['type']}</td>
                    <td>{t['volume']}</td>
                    <td class="{p_color}">${t['profit']:.2f}</td>
                </tr>
                """

            html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <title>NEXT LEVEL BRAIN - Live Performance</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        body {{ font-family: 'Segoe UI', sans-serif; background-color: #0b0e14; color: #ecf0f1; padding: 30px; }}
        .report-card {{ max-width: 1000px; margin: auto; background: #1a1e27; padding: 40px; border-radius: 20px; box-shadow: 0 15px 35px rgba(0,0,0,0.4); border: 1px solid #2d3436; }}
        h1 {{ color: #00e676; text-align: center; font-size: 32px; margin-bottom: 30px; letter-spacing: 1px; }}
        .metrics-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 15px; margin-bottom: 40px; }}
        .metric-box {{ background: #242933; padding: 20px; border-radius: 12px; text-align: center; border: 1px solid #2d3436; }}
        .metric-label {{ font-size: 11px; color: #b2bec3; text-transform: uppercase; font-weight: bold; margin-bottom: 8px; }}
        .metric-value {{ font-size: 24px; font-weight: 800; }}
        .loss-text {{ color: #ff7675; }}
        .win-text {{ color: #55efc4; }}
        .chart-section {{ background: #0b0e14; padding: 20px; border-radius: 15px; margin-bottom: 40px; border: 1px solid #2d3436; min-height: 400px; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
        th, td {{ padding: 12px 15px; text-align: left; border-bottom: 1px solid #2d3436; }}
        th {{ background: #242933; color: #00e676; font-size: 13px; text-transform: uppercase; }}
        .profit-pos {{ color: #00e676; font-weight: bold; }}
        .profit-neg {{ color: #ff7675; font-weight: bold; }}
    </style>
</head>
<body>
    <div class="report-card">
        <h1>📊 LIVE TRADING PERFORMANCE</h1>
        <div class="metrics-grid">
            <div class="metric-box">
                <div class="metric-label">Total Trades</div>
                <div class="metric-value">{total_trades}</div>
            </div>
            <div class="metric-box">
                <div class="metric-label">Net P&L</div>
                <div class="metric-value" style="color: {pnl_color}">${total_pnl:.2f}</div>
            </div>
            <div class="metric-box">
                <div class="metric-label">Total Minus (Loss)</div>
                <div class="metric-value loss-text">-${total_loss:.2f}</div>
            </div>
            <div class="metric-box">
                <div class="metric-label">Win Rate</div>
                <div class="metric-value win-text">{win_rate:.1f}%</div>
            </div>
            <div class="metric-box">
                <div class="metric-label">Max DD</div>
                <div class="metric-value">{max_dd_pct:.2f}%</div>
            </div>
        </div>
        
        <div class="chart-section">
            <canvas id="pnlChart"></canvas>
        </div>

        <h3>📝 RECENT TRADES</h3>
        <table>
            <thead>
                <tr>
                    <th>Time</th>
                    <th>Symbol</th>
                    <th>Side</th>
                    <th>Lots</th>
                    <th>Profit ($)</th>
                </tr>
            </thead>
            <tbody>
                {table_rows}
            </tbody>
        </table>
    </div>
    <script>
        const ctx = document.getElementById('pnlChart').getContext('2d');
        new Chart(ctx, {{
            type: 'line',
            data: {{
                labels: {chart_labels},
                datasets: [{{
                    label: 'Cumulative Equity',
                    data: {chart_data},
                    borderColor: '#00e676',
                    backgroundColor: 'rgba(0, 230, 118, 0.1)',
                    fill: true,
                    tension: 0.2,
                    borderWidth: 2
                }}]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                scales: {{
                    x: {{ display: false }},
                    y: {{ grid: {{ color: '#2d3436' }}, ticks: {{ color: '#b2bec3' }} }}
                }},
                plugins: {{
                    legend: {{ display: false }}
                }}
            }}
        }});
    </script>
</body>
</html>
"""
            with open(html_report_file, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            # 3. Generate JSON Report for Global Index compatibility
            json_report_file = self.reports_dir / f"trading_report_{timestamp}.json"
            json_data = {
                'timestamp': datetime.now().isoformat(),
                'metrics': {
                    'total_trades': total_trades,
                    'total_pnl': total_pnl,
                    'win_rate': win_rate / 100.0 if total_trades else 0,
                    'profit_factor': profit_factor,
                    'max_drawdown': max_dd_pct,
                    'total_loss': total_loss,
                    'max_floating_minus': self.session_max_drawdown
                },
                'trades': self.trade_history
            }
            with open(json_report_file, 'w') as f:
                json.dump(json_data, f, indent=4, default=str)
            
            # 4. Update Global Index
            self._update_global_index()
            
            return str(md_report_file)

        except Exception as e:
            logger.error(f"Failed to generate report: {e}")
            return None

    def _update_global_index(self):
        """Aggregate all session data into a premium main index.html (Shared with Dashboard)"""
        try:
            report_dir = self.reports_dir
            # Look for all dashboard and trading reports
            json_files = sorted(list(report_dir.glob("*.json")), key=lambda x: x.name)
            
            all_sessions = []
            for jf in json_files:
                try:
                    with open(jf, 'r') as f:
                        data = json.load(f)
                        # Detect report type to link correctly
                        f_name = jf.name
                        if "dashboard_report" in f_name:
                            html_file = f_name.replace('.json', '.html').replace('dashboard_report_', 'performance_report_')
                        elif "trading_report" in f_name:
                            html_file = f_name.replace('.json', '.html').replace('trading_report_', 'performance_report_')
                        else:
                            html_file = f_name.replace('.json', '.html')
                            
                        all_sessions.append({
                            'time': data.get('timestamp', 'N/A')[:16].replace('T', ' '),
                            'pnl': data.get('metrics', {}).get('total_pnl', 0),
                            'minus': data.get('metrics', {}).get('max_floating_minus', 0),
                            'trades': data.get('metrics', {}).get('total_trades', 0),
                            'file': html_file
                        })
                except: continue

            if not all_sessions: return
            import numpy as np
            labels = [s['time'] for s in all_sessions]
            pnl_data = [s['pnl'] for s in all_sessions]
            minus_data = [abs(s['minus']) for s in all_sessions]
            cum_pnl = np.cumsum(pnl_data).tolist()
            
            html_template = f"""
<!DOCTYPE html>
<html>
<head>
    <title>NEXT LEVEL BRAIN - Global Trading Intelligence</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        body {{ font-family: 'Inter', 'Segoe UI', sans-serif; background-color: #0d1117; color: #c9d1d9; padding: 40px; margin: 0; }}
        .container {{ max-width: 1200px; margin: auto; }}
        .header {{ text-align: center; margin-bottom: 50px; padding: 40px; background: linear-gradient(145deg, #161b22, #0d1117); border-radius: 24px; border: 1px solid #30363d; box-shadow: 0 20px 50px rgba(0,0,0,0.5); }}
        h1 {{ color: #00e676; font-size: 3em; margin: 0; text-transform: uppercase; letter-spacing: 4px; }}
        .subtitle {{ color: #8b949e; font-size: 1.1em; margin-top: 10px; }}
        .summary-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 25px; margin-bottom: 50px; }}
        .card {{ background: #161b22; padding: 30px; border-radius: 20px; border: 1px solid #30363d; text-align: center; transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1); }}
        .card:hover {{ transform: translateY(-10px); border-color: #00e676; box-shadow: 0 10px 30px rgba(0, 230, 118, 0.1); }}
        .val {{ font-size: 32px; font-weight: 800; margin-top: 10px; font-family: 'Consolas', monospace; }}
        .lab {{ font-size: 13px; color: #8b949e; text-transform: uppercase; font-weight: bold; letter-spacing: 1px; }}
        .chart-container {{ background: #161b22; padding: 30px; border-radius: 24px; border: 1px solid #30363d; margin-bottom: 50px; height: 500px; }}
        .session-list {{ background: #161b22; border-radius: 24px; border: 1px solid #30363d; overflow: hidden; }}
        table {{ width: 100%; border-collapse: collapse; }}
        th {{ background: #21262d; color: #00e676; padding: 20px; text-align: left; text-transform: uppercase; font-size: 12px; }}
        td {{ padding: 18px 20px; border-bottom: 1px solid #30363d; font-size: 14px; }}
        tr:hover {{ background: #1c2128; }}
        .btn {{ display: inline-block; padding: 8px 16px; background: #238636; color: white; text-decoration: none; border-radius: 6px; font-size: 12px; font-weight: bold; }}
        .btn:hover {{ background: #2ea043; }}
        .minus-val {{ color: #ff5252; font-weight: bold; }}
        .pnl-pos {{ color: #00e676; font-weight: bold; }}
        .pnl-neg {{ color: #ff5252; font-weight: bold; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🧠 GLOBAL DASHBOARD</h1>
            <div class="subtitle">Next Level Brain - Unified Performance Intelligence</div>
        </div>
        <div class="summary-grid">
            <div class="card">
                <div class="lab">Total Sessions</div>
                <div class="val" style="color: #58a6ff;">{len(all_sessions)}</div>
            </div>
            <div class="card">
                <div class="lab">Cumulative PnL</div>
                <div class="val" style="color: {('#00e676' if sum(pnl_data) >= 0 else '#ff5252')};">${sum(pnl_data):,.2f}</div>
            </div>
            <div class="card">
                <div class="lab">Total Trade Count</div>
                <div class="val">{sum(s['trades'] for s in all_sessions)}</div>
            </div>
            <div class="card">
                <div class="lab">Peak Market Minus</div>
                <div class="val" style="color: #ff5252;">-${max(minus_data) if minus_data else 0:,.2f}</div>
            </div>
        </div>
        <div class="chart-container">
            <canvas id="mainChart"></canvas>
        </div>
        <div class="session-list">
            <table>
                <thead>
                    <tr>
                        <th>Session Timestamp</th>
                        <th>Trades</th>
                        <th>Session PnL</th>
                        <th>Max Market Minus ($)</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody>
                    {"".join([f'''<tr>
                        <td>{s['time']}</td>
                        <td>{s['trades']}</td>
                        <td class="{('pnl-pos' if s['pnl'] >= 0 else 'pnl-neg')}">${s['pnl']:.2f}</td>
                        <td class="minus-val">-${abs(s['minus']):.2f}</td>
                        <td><a href="{s['file']}" class="btn">VIEW FULL REPORT</a></td>
                    </tr>''' for s in reversed(all_sessions)])}
                </tbody>
            </table>
        </div>
        <p style="text-align: center; color: #8b949e; margin-top: 40px; font-size: 12px;">
            SYSTEM STATUS: ONLINE | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        </p>
    </div>
    <script>
        const ctx = document.getElementById('mainChart').getContext('2d');
        new Chart(ctx, {{
            type: 'line',
            data: {{
                labels: {json.dumps(labels)},
                datasets: [
                    {{
                        label: 'Total Cumulative Profit ($)',
                        data: {json.dumps(cum_pnl)},
                        borderColor: '#00e676',
                        backgroundColor: 'rgba(0, 230, 118, 0.1)',
                        fill: true,
                        tension: 0.3,
                        yAxisID: 'y'
                    }},
                    {{
                        label: 'Market Minus at Peak ($)',
                        data: {json.dumps(minus_data)},
                        borderColor: '#ff5252',
                        backgroundColor: 'rgba(255, 82, 82, 0.1)',
                        borderDash: [5, 5],
                        fill: false,
                        tension: 0.1,
                        yAxisID: 'y1'
                    }}
                ]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                interaction: {{ mode: 'index', intersect: false }},
                plugins: {{
                    tooltip: {{
                        backgroundColor: '#161b22',
                        titleColor: '#00e676',
                        bodyColor: '#fff',
                        borderColor: '#30363d',
                        borderWidth: 1,
                        callbacks: {{
                            label: function(context) {{
                                let label = context.dataset.label || '';
                                if (label) label += ': ';
                                if (context.parsed.y !== null) {{
                                    label += '$' + context.parsed.y.toLocaleString();
                                }}
                                return label;
                            }}
                        }}
                    }}
                }},
                scales: {{
                    y: {{
                        type: 'linear',
                        display: true,
                        position: 'left',
                        grid: {{ color: '#30363d' }},
                        ticks: {{ color: '#00e676' }}
                    }},
                    y1: {{
                        type: 'linear',
                        display: true,
                        position: 'right',
                        grid: {{ drawOnChartArea: false }},
                        ticks: {{ color: '#ff5252' }},
                        title: {{ display: true, text: 'Floating Minus Impact ($)', color: '#ff5252' }}
                    }},
                    x: {{
                        grid: {{ color: '#30363d' }},
                        ticks: {{ color: '#8b949e' }}
                    }}
                }}
            }}
        }});
    </script>
</body>
</html>
"""
            with open(report_dir / "index.html", "w", encoding="utf-8") as f:
                f.write(html_template)
        except Exception as e:
            logger.error(f"Global index update error: {e}")

def select_trade_setup():
    """Professional CLI setup selection"""
    # Fix Windows terminal encoding for unicode
    import sys
    if sys.platform == 'win32':
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    
    print("\n" + "=" * 65)
    print("   NEXT LEVEL BRAIN  |  LIVE TRADING SYSTEM  |  GOLD (XAUUSDm)")
    print("=" * 65)
    
    # 1. Strategy Selection
    print("\n  [STEP 1/2]  SELECT STRATEGY")
    print("  " + "-" * 45)
    print("  [1]  GRID BOTH        - Auto Trend + Center Pivot  (SMART)")
    print("  [2]  GRID BUY ONLY   - 300 Buy Limit Orders")
    print("  [3]  GRID SELL ONLY  - 300 Sell Limit Orders")
    print("  [4]  ICT SMC          - AI Trend Following")
    print("  [5]  OPEN DASHBOARD   - Visual Tracker (Browser)")
    print("  [6]  DELETE ALL       - Cancel All Pending Orders")
    print("  " + "-" * 45)
    
    strategy = "Grid Both"
    while True:
        choice = input("  >> Choice (1-6): ").strip()
        if choice == "1":
            strategy = "Grid Both"
            print(f"\n  [OK] Strategy Selected: GRID BOTH (Center Pivot + ATR/ADX Filter)\n")
            break
        if choice == "2":
            strategy = "Grid BUY ONLY"
            print(f"\n  [OK] Strategy Selected: GRID BUY ONLY (300 Orders)\n")
            break
        if choice == "3":
            strategy = "Grid SELL ONLY"
            print(f"\n  [OK] Strategy Selected: GRID SELL ONLY (300 Orders)\n")
            break
        if choice == "4":
            strategy = "ICT SMC"
            print(f"\n  [OK] Strategy Selected: ICT SMC (AI Trend Following)\n")
            break
        if choice == "5":
            launch_dashboard()
            continue
        if choice == "6":
            print("\n  [!] Cleaning up all XAUUSDm pending orders...")
            if mt5.initialize():
                total = 0
                for s in ["XAUUSDm", "XAUUSD"]:
                    orders = mt5.orders_get(symbol=s)
                    if orders:
                        for o in orders:
                            mt5.order_send({"action": mt5.TRADE_ACTION_REMOVE, "order": o.ticket})
                        total += len(orders)
                print(f"  [OK] {total} pending orders deleted successfully.\n")
            else:
                print("  [ERR] Failed to connect to MT5 for cleanup.\n")
            continue
        print("  [!] Invalid choice. Please enter 1-6.")

    # 2. Timeframe Selection
    print("  [STEP 2/2]  SELECT ANALYSIS TIMEFRAME")
    print("  " + "-" * 45)
    tfs = ["M1", "M3", "M5", "M15", "M30", "H1", "H4", "D1"]
    tf_labels = ["1 Minute", "3 Minutes", "5 Minutes", "15 Minutes", "30 Minutes", "1 Hour", "4 Hours", "Daily"]
    for i, (tf, label) in enumerate(zip(tfs, tf_labels), 1):
        print(f"  [{i}]  {tf:<6}  - {label}")
    print("  " + "-" * 45)
    
    timeframe = "M1"
    while True:
        try:
            choice = int(input(f"  >> Choice (1-{len(tfs)}): ").strip())
            if 1 <= choice <= len(tfs):
                timeframe = tfs[choice - 1]
                print(f"\n  [OK] Timeframe Selected: {timeframe} ({tf_labels[choice-1]})\n")
                break
        except:
            pass
        print("  [!] Invalid choice. Please enter a number.")

    return ["XAUUSDm"], strategy, timeframe


def launch_dashboard():
    """Helper to launch the dashboard safely"""
    try:
        print("\n  [>>] Launching Live Dashboard in background...")
        import subprocess
        script_dir = os.path.dirname(os.path.abspath(__file__))
        dashboard_path = os.path.join(script_dir, "live_dashboard.py")
        subprocess.Popen([sys.executable, dashboard_path],
                         creationflags=0x08000000 if os.name == 'nt' else 0,
                         close_fds=True)
        print("  [OK] Dashboard launched successfully.\n")
    except Exception as e:
        print(f"  [ERR] Failed to launch dashboard: {e}\n")

def main():
    """Main function - CLI mode"""
    try:
        # Create necessary directories
        Path("logs").mkdir(exist_ok=True)
        Path("charts").mkdir(exist_ok=True)
        Path("models").mkdir(exist_ok=True)
        
        symbols, strategy, timeframe = select_trade_setup()
        if symbols is None or strategy is None or timeframe is None:
            print("  Exiting.")
            return
        
        # Print startup summary
        print("=" * 65)
        print("   TRADING SESSION STARTING")
        print("=" * 65)
        print(f"   Symbol    : {', '.join(symbols)}")
        print(f"   Strategy  : {strategy}")
        print(f"   Timeframe : {timeframe}")
        print(f"   Started   : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 65 + "\n")
        
        trading_system = LiveTradingSystem()
        trading_system.symbols = symbols
        trading_system.strategy = strategy
        trading_system.timeframe = timeframe
        
        # AUTO-LAUNCH Dashboard when trading starts
        launch_dashboard()
        
        # Run trading loop
        asyncio.run(trading_system.run())
        
    except KeyboardInterrupt:
        logger.info("Application interrupted by user")
    except Exception as e:
        logger.error(f"Application error: {e}")

if __name__ == "__main__":
    main()
