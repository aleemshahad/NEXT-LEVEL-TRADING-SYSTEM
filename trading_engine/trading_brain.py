import time
import os
import requests
import json
import pandas as pd
import numpy as np
import asyncio
import MetaTrader5 as mt5
from datetime import datetime, timedelta
from pathlib import Path
from loguru import logger
from typing import Dict, List

# Advanced Intelligence Integrations
from computer_vision_analyzer import ComputerVisionAnalyzer
from market_intelligence.sentiment_intelligence import SentimentIntelligenceEngine
from market_intelligence.data_acquisition import DataAcquisitionService

class TradingBrain:
    """AI Trading Brain with Neural Network"""
    
    def __init__(self, config: Dict = None):
        self.config = config or {}
        self.memories = []
        self.model_trained = False
        self.confidence_threshold = 0.6
        self.sentiment_decision = "ALLOW"
        self.last_ff_status = "STALE"
        self._ff_events = []
        self._last_ff_download = 0
        
        # Advanced Decision Engines
        self.cv_analyzer = ComputerVisionAnalyzer()
        self.sentiment_engine = SentimentIntelligenceEngine()
        self.data_service = DataAcquisitionService()
        self.last_cv_report = "NO DATA"
        self.last_sentiment_report = "NO DATA"
        
        # Performance Optimizations (Caching)
        self._last_sentiment_check = 0
        self._sentiment_cache_ttl = 300 # 5 Minutes Cache
        self._last_intel_report = None
        self._last_intel_report_time = 0
        
        # Risk Parameters
        self.risk_modifier = 1.0
        self._load_memories()
        self._check_sentiment_bias()

    def _get_market_timestamp(self) -> datetime:
        """Get current market time (Server time) synchronized with MT5."""
        try:
            if not mt5.terminal_info():
                return datetime.utcnow()
            # Try Gold or other active symbols to get the latest server tick time
            for sym in ["XAUUSDc", "EURUSDm", "XAUUSDc", "XAUUSD"]:
                tick = mt5.symbol_info_tick(sym)
                if tick:
                    # Broker server time (stored as seconds since epoch, treated as naive UTC-like)
                    return datetime.utcfromtimestamp(tick.time)
        except:
            pass
        return datetime.utcnow()

    def _check_sentiment_bias(self):
        """
        Check Forex Factory for HIGH-impact USD events.
        CACHING: Downloads FF calendar every 1 hour.
        BLOCK status: Checked every cycle based on downloaded events.
        """
        try:
            now_t = time.time()
            now_utc = self._get_market_timestamp()

            # --- STEP 1: LOAD/DOWNLOAD EVENTS (Cached for 1 hour) ---
            if not self._ff_events or (now_t - self._last_ff_download > 3600):
                cache_file = Path("logs/ff_calendar_cache.json")
                events = None
                
                # Try cache first
                if cache_file.exists() and (now_t - cache_file.stat().st_mtime < 21600): # 6h file cache
                    with open(cache_file, 'r') as f:
                        events = json.load(f)
                
                # Download if needed
                if not events:
                    try:
                        url = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
                        resp = requests.get(url, timeout=8)
                        if resp.status_code == 200:
                            events = resp.json()
                            with open(cache_file, 'w') as f:
                                json.dump(events, f)
                            logger.info(f"[FF News] Downloaded {len(events)} events.")
                    except: pass
                
                self._ff_events = events or []
                self._last_ff_download = now_t

            if not self._ff_events:
                self.sentiment_decision = "ALLOW"
                return

            # --- STEP 2: CHECK FOR BLOCKING EVENTS ---
            block_window_min = 120
            blocking_event = None
            blocking_event_time = None

            for event in self._ff_events:
                if event.get('currency') == 'USD' and 'High' in event.get('impact', ''):
                    try:
                        date_str = event.get('date', '')
                        event_time = datetime.strptime(date_str[:19], "%Y-%m-%dT%H:%M:%S")
                        
                        diff_minutes = (event_time - now_utc).total_seconds() / 60
                        if -block_window_min <= diff_minutes <= block_window_min:
                            blocking_event = event.get('title')
                            blocking_event_time = event_time
                            break
                    except: continue

            # --- STEP 3: TAKE ACTION ---
            if blocking_event:
                if self.sentiment_decision != "BLOCK":
                    logger.warning(f"[NEWS BLOCK] HIGH USD Event: '{blocking_event}' at {blocking_event_time.strftime('%H:%M UTC')}")
                    # Note: We can't cancel pendings directly from here easily without broker access
                    # But the system will check sentiment_decision in the main loop
                self.sentiment_decision = "BLOCK"
            else:
                self.sentiment_decision = "ALLOW"

        except Exception as e:
            self.sentiment_decision = "ALLOW"
            logger.debug(f"FF News check error: {e}")

    def _load_memories(self):
        """Load trained memories from file"""
        try:
            memory_file = Path("models/ai_memories.json")
            if memory_file.exists():
                with open(memory_file, 'r') as f:
                    self.memories = json.load(f)
                self.model_trained = True
                logger.debug(f"🧠 Loaded {len(self.memories)} training memories. AI is ready.")
            else:
                logger.warning("⚠️ No training data found. AI starting with blank slate.")
        except Exception as e:
            logger.error(f"Failed to load memories: {e}")

    def _is_silver_bullet_time(self, timestamp: datetime) -> bool:
        """Check if time is within ICT Silver Bullet windows (EST based)."""
        offset = int(os.getenv("MT5_SERVER_TIME_OFFSET", 0))
        adj_time = timestamp + timedelta(hours=offset)
        h = adj_time.hour
        if h in [3, 10, 14]:
            return True
        return False

    async def analyze_market(self, symbol: str, data: pd.DataFrame) -> Dict:
        """ICT/SMC AI market analysis matching Notebook Accuracy"""
        try:
            if len(data) < 50:
                return {'action': 'HOLD', 'bias': 'NEUTRAL', 'confidence': 0.0, 'reasoning': 'Insufficient data'}
            
            data = self._add_indicators(data)
            index = len(data) - 1

            # 1. Core Structure
            mss_r = await self._detect_market_structure(data)
            bias = mss_r['bias']
            structure = mss_r['structure']
            
            # 2. Key ICT Concepts
            sweep = self._detect_liquidity_sweep(data, index)
            fvg = self._detect_fair_value_gap(data, index)
            ob = self._detect_order_block(data, index, bias)
            range_info = self._analyze_dealing_range(data, index)
            ote_level = self._check_ote_levels(data, index, fvg)
            rr_tracks = self._detect_railroad_tracks(data)
            
            # 3. Decision Logic
            score = 0
            signals_present = [f"MSS: {structure}"]
            
            if sweep['detected']:
                if (bias == 'BULLISH' and sweep['type'] == 'BELOW_LOW') or (bias == 'BEARISH' and sweep['type'] == 'ABOVE_HIGH'):
                    score += 1.0
                    signals_present.append(f"Sweep ({sweep['type']})")
                else: score += 0.5
            
            if fvg['detected'] and fvg.get('type') == bias:
                score += 1.0
                signals_present.append(f"FVG ({fvg['type']})")
            
            if ob['detected'] and ob.get('type') == bias:
                score += 0.5
                signals_present.append(f"OB ({ob['type']})")
            
            if rr_tracks['detected'] and rr_tracks.get('type') == bias:
                score += 0.5
                signals_present.append("RR Tracks")
            
            confidence = min(1.0, score / 2.5)
            
            # 4. CV Regime Validation
            try:
                cv_res = self.cv_analyzer.analyze_market_regime(data)
                curr_regime = cv_res.get('current_regime')
                if curr_regime:
                    self.last_cv_report = f"{curr_regime.regime.value} ({curr_regime.confidence:.0%})"
                    if (bias == 'BULLISH' and curr_regime.regime.name == 'TREND_DOWN') or \
                       (bias == 'BEARISH' and curr_regime.regime.name == 'TREND_UP'):
                        score *= 0.5
            except: pass

            # 5. Market Intelligence (Sentiment) Process
            try:
                now_s = time.time()
                if now_s - self._last_intel_report_time > self._sentiment_cache_ttl:
                    raw_intel = self.data_service.aggregate_data()
                    self._last_intel_report = self.sentiment_engine.run_analysis_cycle(raw_intel)
                    self._last_intel_report_time = now_s

                intel_report = self._last_intel_report
                if intel_report:
                    self.last_sentiment_report = f"{intel_report.sentiment_summary.bias.value.upper()} | Score: {intel_report.sentiment_summary.sentiment_score:.2f}"
                    self.risk_modifier = intel_report.decision_impact.risk_modifier
                    if intel_report.decision_impact.action == "BLOCK":
                         self.sentiment_decision = "BLOCK"
                else:
                    self.last_sentiment_report = "NO DATA"
            except: pass

            # Filter by Silver Bullet and Sentiment
            self._check_sentiment_bias()
            
            if self.sentiment_decision == "BLOCK":
                return {
                    'action': 'HOLD', 'bias': bias, 'confidence': 0.0, 
                    'reasoning': 'Intelligence: BLOCK', 
                    'ict_status': {'mss': structure, 'cv': self.last_cv_report}
                }
            
            action = 'HOLD'
            if score >= 1.5 and bias != 'NEUTRAL':
                if (bias == 'BULLISH' and range_info['zone'] == 'DISCOUNT') or (bias == 'BEARISH' and range_info['zone'] == 'PREMIUM'):
                    action = 'BUY' if bias == 'BULLISH' else 'SELL'
            
            # Final Return
            current = data.iloc[-1]
            stop_loss = current['close'] * (0.995 if action == 'BUY' else 1.005)
            if sweep['detected'] and ((action == 'BUY' and sweep['type'] == 'BELOW_LOW') or (action == 'SELL' and sweep['type'] == 'ABOVE_HIGH')):
                stop_loss = sweep['swept_level'] - (current['close'] * 0.0005) if action == 'BUY' else sweep['swept_level'] + (current['close'] * 0.0005)
            
            ict_status = {
                'mss': structure,
                'sweep': sweep['type'] if sweep['detected'] else "OFF",
                'fvg': fvg['type'] if fvg['detected'] else "OFF",
                'ob': ob['type'] if ob['detected'] else "OFF",
                'rr': rr_tracks['type'] if rr_tracks['detected'] else "OFF",
                'range': range_info['zone'],
                'ote': "VALID" if ote_level['valid'] else "OFF"
            }
            
            return {
                'action': action,
                'bias': bias,
                'confidence': confidence,
                'reasoning': f"AI {action}: {', '.join(signals_present)} | CV: {self.last_cv_report}",
                'entry_price': current['close'],
                'use_limit': False,
                'stop_loss': stop_loss,
                'take_profit': self._find_next_liquidity_pool(data, index, 'UP' if action == 'BUY' else 'DOWN'),
                'ict_status': ict_status,
                'risk_modifier': self.risk_modifier
            }
        except Exception as e:
            logger.error(f"ICT AI analysis error: {e}")
            return {'action': 'HOLD', 'bias': 'NEUTRAL', 'confidence': 0.0, 'reasoning': 'Analysis failed'}
    
    def _add_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add technical indicators to dataframe"""
        try:
            df['sma_20'] = df['close'].rolling(20).mean()
            df['sma_50'] = df['close'].rolling(50).mean()
            df['ema_12'] = df['close'].ewm(span=12).mean()
            df['ema_26'] = df['close'].ewm(span=26).mean()
            delta = df['close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            df['rsi'] = 100 - (100 / (1 + (gain / loss)))
            df['macd'] = df['ema_12'] - df['ema_26']
            df['macd_signal'] = df['macd'].ewm(span=9).mean()
            return df
        except Exception as e:
            logger.error(f"Error adding indicators: {e}")
            return df
    
    async def _detect_market_structure(self, df: pd.DataFrame, lookback: int = 20) -> Dict:
        """Concept 1: Market Structure (MSS / BOS / ChoCH)"""
        try:
            if len(df) < lookback + 2: return {'structure': "NEUTRAL", 'bias': "NEUTRAL"}
            index = len(df) - 1
            recent = df.iloc[max(0, index-lookback): index+1]
            swing_highs = recent['high'].rolling(3, center=True).max()
            swing_lows  = recent['low'].rolling(3, center=True).min()
            prev_high = swing_highs.iloc[-2]; prev_low = swing_lows.iloc[-2]
            curr_high = df['high'].iloc[-1]; curr_low = df['low'].iloc[-1]
            if curr_high > prev_high and curr_low > prev_low: structure = "BULLISH_BOS"; bias = "BULLISH"
            elif curr_low < prev_low and curr_high < prev_high: structure = "BEARISH_BOS"; bias = "BEARISH"
            elif (curr_low < prev_low and curr_high > prev_high) or (curr_high > prev_high and curr_low < prev_low): structure = "CHOCH"; bias = "NEUTRAL"
            else: structure = "NEUTRAL"; bias = "NEUTRAL"
            return {'structure': structure, 'bias': bias, 'prev_high': prev_high, 'prev_low': prev_low}
        except Exception as e:
            logger.error(f"Market structure error: {e}"); return {'structure': "NEUTRAL", 'bias': "NEUTRAL"}

    def _detect_railroad_tracks(self, df: pd.DataFrame) -> Dict:
        """Concept 12: Railroad Tracks"""
        try:
            if len(df) < 5: return {'detected': False}
            bar1 = df.iloc[-2]; bar2 = df.iloc[-1]
            dir1 = 1 if bar1['close'] > bar1['open'] else -1; dir2 = 1 if bar2['close'] > bar2['open'] else -1
            if dir1 == dir2: return {'detected': False}
            size1 = abs(bar1['close'] - bar1['open']); size2 = abs(bar2['close'] - bar2['open'])
            if size1 == 0 or size2 == 0: return {'detected': False}
            similarity = min(size1, size2) / max(size1, size2)
            atr = (df['high'] - df['low']).rolling(14).mean().iloc[-1]
            if size1 < atr * 0.3: return {'detected': False}
            if similarity > 0.75:
                return {'detected': True, 'type': "BULLISH" if dir2 == 1 else "BEARISH", 'strength': similarity}
            return {'detected': False}
        except: return {'detected': False}
    
    def _detect_liquidity_sweep(self, df: pd.DataFrame, index: int) -> Dict:
        """Refined Liquidity Sweep Detection"""
        try:
            lookback = 30
            if index < lookback + 1: return {'detected': False}
            recent = df.iloc[max(0, index-50):index]
            avg_range = (recent['high'] - recent['low']).mean(); avg_close = recent['close'].mean()
            vol_pct = (avg_range / avg_close) * 100 if avg_close > 0 else 0.1
            min_pen = max(0.001, vol_pct * 0.001); min_rej = max(0.0005, vol_pct * 0.0005)
            confirmed_idx = index - 1; current_bar = df.iloc[confirmed_idx]
            recent_data = df.iloc[confirmed_idx - lookback : confirmed_idx]
            swing_low = recent_data['low'].min(); swing_high = recent_data['high'].max()
            if current_bar['low'] < swing_low and current_bar['close'] > swing_low:
                pen = (swing_low - current_bar['low']) / swing_low * 100; rej = (current_bar['close'] - swing_low) / swing_low * 100
                if pen >= min_pen and rej >= min_rej: return {'detected': True, 'type': 'BELOW_LOW', 'swept_level': swing_low, 'strength': min((pen + rej) / (min_pen + min_rej + 1e-9), 1.0)}
            elif current_bar['high'] > swing_high and current_bar['close'] < swing_high:
                pen = (current_bar['high'] - swing_high) / swing_high * 100; rej = (swing_high - current_bar['close']) / swing_high * 100
                if pen >= min_pen and rej >= min_rej: return {'detected': True, 'type': 'ABOVE_HIGH', 'swept_level': swing_high, 'strength': min((pen + rej) / (min_pen + min_rej + 1e-9), 1.0)}
            return {'detected': False}
        except Exception as e:
            logger.error(f"Sweep detection error: {e}"); return {'detected': False}
    
    def _detect_fair_value_gap(self, df: pd.DataFrame, index: int) -> Dict:
        """Refined FVG Detection"""
        try:
            if index < 3: return {'detected': False}
            b1, b2, b3 = df.iloc[index-2], df.iloc[index-1], df.iloc[index]
            vol = (df['high'] - df['low']).rolling(14).mean().iloc[index-1]; min_gap = vol * 0.15
            if b1['high'] < b3['low']:
                gap_size = b3['low'] - b1['high']
                if gap_size > min_gap: return {'detected': True, 'type': 'BULLISH', 'high': b3['low'], 'low': b1['high'], 'strength': min(gap_size / (vol * 0.5 + 1e-9), 1.0)}
            elif b1['low'] > b3['high']:
                gap_size = b1['low'] - b3['high']
                if gap_size > min_gap: return {'detected': True, 'type': 'BEARISH', 'high': b1['low'], 'low': b3['high'], 'strength': min(gap_size / (vol * 0.5 + 1e-9), 1.0)}
            active = self._scan_active_fvgs(df)
            if active: return {'detected': True, 'active_only': True, **active[0]}
            return {'detected': False}
        except Exception: return {'detected': False}

    def _scan_active_fvgs(self, df: pd.DataFrame, lookback: int = 50) -> List[Dict]:
        """Scan for historical FVGs that remain unfilled"""
        unfilled = []
        try:
            for i in range(len(df)-lookback, len(df)-2):
                b1, b2, b3 = df.iloc[i], df.iloc[i+1], df.iloc[i+2]
                gap = None
                if b1['high'] < b3['low']: gap = {'type': 'BULLISH', 'high': b3['low'], 'low': b1['high']}
                elif b1['low'] > b3['high']: gap = {'type': 'BEARISH', 'high': b1['low'], 'low': b3['high']}
                if gap:
                    is_filled = False
                    for j in range(i+3, len(df)):
                        price = df.iloc[j]['low'] if gap['type'] == 'BULLISH' else df.iloc[j]['high']
                        if (gap['type'] == 'BULLISH' and price <= gap['low']) or (gap['type'] == 'BEARISH' and price >= gap['high']):
                            is_filled = True; break
                    if not is_filled: unfilled.append(gap)
            return unfilled[::-1]
        except: return []
    
    def _analyze_dealing_range(self, df: pd.DataFrame, index: int) -> Dict:
        """Analyze if price is in discount or premium zone"""
        try:
            lookback = 20
            if index < lookback: return {'zone': 'NEUTRAL'}
            recent = df.iloc[index-lookback:index+1]
            r_high = recent['high'].max(); r_low = recent['low'].min(); cp = df.iloc[index]['close']
            r_50 = r_low + (r_high - r_low) * 0.5
            return {'zone': 'DISCOUNT' if cp < r_50 else 'PREMIUM', 'level': r_50}
        except Exception: return {'zone': 'NEUTRAL'}
    
    def _detect_order_block(self, df: pd.DataFrame, index: int, bias: str) -> Dict:
        """Detect institutional order blocks"""
        try:
            lookback = 15
            if index < lookback: return {'detected': False}
            for i in range(index-lookback, index-1):
                b = df.iloc[i]; nb = df.iloc[i+1]
                pc = abs(nb['close'] - b['close']) / b['close']
                if bias == 'BULLISH' and pc > 0.001 and nb['close'] > b['close']: return {'detected': True, 'type': 'BULLISH', 'high': b['high'], 'low': b['low'], 'strength': min(pc * 15, 1.0)}
                elif bias == 'BEARISH' and pc > 0.001 and nb['close'] < b['close']: return {'detected': True, 'type': 'BEARISH', 'high': b['high'], 'low': b['low'], 'strength': min(pc * 15, 1.0)}
            return {'detected': False}
        except Exception: return {'detected': False}
    
    def _check_ote_levels(self, df: pd.DataFrame, index: int, fvg: Dict) -> Dict:
        """Check Optimal Trade Entry levels (62%-79% Fibonacci)"""
        try:
            if not fvg.get('detected'): return {'valid': False}
            cp = df.iloc[index]['close']; fvgr = fvg['high'] - fvg['low']
            ote_62 = fvg['low'] + (fvgr * 0.62); ote_79 = fvg['low'] + (fvgr * 0.79)
            if ote_62 <= cp <= ote_79: return {'valid': True, 'strength': 0.9, 'level_62': ote_62, 'level_79': ote_79}
            return {'valid': False}
        except Exception: return {'valid': False}
    
    def _find_next_liquidity_pool(self, df: pd.DataFrame, index: int, direction: str) -> float:
        """Find next liquidity pool for take profit"""
        try:
            lookback = 30; cp = df.iloc[index]['close']
            if direction == 'UP':
                rh = df.iloc[max(0, index-lookback):index]['high']
                res = rh[rh > cp].min()
                return res if not pd.isna(res) else cp * 1.02
            else:
                rl = df.iloc[max(0, index-lookback):index]['low']
                sup = rl[rl < cp].max()
                return sup if not pd.isna(sup) else cp * 0.98
        except Exception: return cp * (1.02 if direction == 'UP' else 0.98)

    def remember_trade(self, trade_data: Dict):
        """Store trade in memory for learning"""
        self.memories.append({'timestamp': datetime.now(), 'symbol': trade_data.get('symbol'), 'action': trade_data.get('action'), 'success': trade_data.get('pnl', 0) > 0, 'pnl': trade_data.get('pnl', 0)})
        if len(self.memories) > 1000: self.memories = self.memories[-1000:]
