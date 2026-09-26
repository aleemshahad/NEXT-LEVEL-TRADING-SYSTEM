import asyncio
import json
import os
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from loguru import logger
import MetaTrader5 as mt5
import numpy as np
import pandas as pd

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False


class TradingBrain:
    """ICT Smart Money Strategy: Liquidity Sweep + Structure Shift + OB/FVG Entry"""

    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        self.memories: List[Dict] = []
        self.model_trained = False
        
        # Rate limiting for logs
        self._last_ict_log: Dict[str, float] = {}
        
        # ICT Configuration
        ict_cfg = self.config.get('ict', {})
        self.ict_enabled = ict_cfg.get('enabled', True)
        self.risk_percent = ict_cfg.get('risk_percent', 0.5)
        self.lookback_bars = ict_cfg.get('lookback_bars', 50)
        self.choch_lookback = ict_cfg.get('choch_lookback', 20)
        self.ob_lookback = ict_cfg.get('ob_lookback', 30)
        self.fvg_lookback = ict_cfg.get('fvg_lookback', 30)
        self.min_confluence = ict_cfg.get('min_confluence', 3)
        self.sl_atr_mult = ict_cfg.get('sl_atr_mult', 1.5)
        self.tp_min_rr = ict_cfg.get('tp_min_risk_reward', 2.0)
        self.tp_prefer_rr = ict_cfg.get('tp_prefer_rr', 3.0)
        
        # Kill Zone configuration
        kz_cfg = ict_cfg.get('kill_zones', {})
        self.london_start = kz_cfg.get('london', {}).get('start', '02:00')
        self.london_end = kz_cfg.get('london', {}).get('end', '05:00')
        self.ny_start = kz_cfg.get('new_york', {}).get('start', '07:00')
        self.ny_end = kz_cfg.get('new_york', {}).get('end', '10:00')
        
        # Sweep detection parameters
        sweep_cfg = ict_cfg.get('sweep', {})
        self.sweep_min_wick = sweep_cfg.get('sweep_min_wick_ratio', 0.3)
        self.sweep_confirm_bars = sweep_cfg.get('sweep确认后_bars', 2)
        
        # News / Calendar Cache
        self._ff_events: List[Dict] = []
        self._last_ff_download: float = 0.0
        self._cache_file = Path("logs/ff_calendar_cache.json")
        self.sentiment_decision = "ALLOW"
        
        if HAS_REQUESTS:
            self._load_memories()

    def _get_market_timestamp(self, symbol: Optional[str] = None) -> datetime:
        """Get current broker server time in UTC."""
        try:
            test_symbols = [symbol] if symbol else ["XAUUSD", "XAUUSDc", "EURUSD", "BTCUSD"]
            for sym in test_symbols:
                if sym:
                    tick = mt5.symbol_info_tick(sym)
                    if tick and tick.time > 0:
                        return datetime.fromtimestamp(tick.time, timezone.utc)
        except Exception as e:
            logger.debug(f"Failed to get broker tick: {e}")
        return datetime.now(timezone.utc)

    # ====================================================================
    # KILL ZONE DETECTION
    # ====================================================================
    
    def is_kill_zone_active(self) -> Tuple[bool, str]:
        """Check if current time falls within a Kill Zone (EST).
        
        Returns:
            (is_active, zone_name) - e.g., (True, "LONDON")
        """
        try:
            utc_now = self._get_market_timestamp()
            # Convert UTC to EST (UTC-5)
            est_now = utc_now - timedelta(hours=5)
            current_time = est_now.strftime("%H:%M")
            
            # London Session: 02:00 - 05:00 EST
            if self.london_start <= current_time <= self.london_end:
                return True, "LONDON"
            
            # New York Session: 07:00 - 10:00 EST
            if self.ny_start <= current_time <= self.ny_end:
                return True, "NEW_YORK"
            
            return False, ""
        except Exception as e:
            logger.debug(f"Kill zone check failed: {e}")
            return False, ""

    # ====================================================================
    # MARKET STRUCTURE DETECTION (BOS / CHoCH)
    # ====================================================================
    
    def _find_swings(self, df: pd.DataFrame, lookback: int = 50) -> Dict[str, List]:
        """Find recent swing highs and lows.
        
        Returns:
            {'swing_highs': [(idx, price), ...], 'swing_lows': [(idx, price), ...]}
        """
        try:
            if len(df) < lookback:
                return {'swing_highs': [], 'swing_lows': []}
            
            recent = df.tail(lookback)
            swings_high = []
            swings_low = []
            
            # Look for swing highs (peak)
            for i in range(2, len(recent) - 2):
                row = recent.iloc[i]
                prev_rows = recent.iloc[i-2:i]
                next_rows = recent.iloc[i+1:i+3]
                
                if (row['high'] > prev_rows['high'].max() and 
                    row['high'] > next_rows['high'].max()):
                    swings_high.append((len(recent) - len(recent) + i, row['high']))
            
            # Look for swing lows (trough)
            for i in range(2, len(recent) - 2):
                row = recent.iloc[i]
                prev_rows = recent.iloc[i-2:i]
                next_rows = recent.iloc[i+1:i+3]
                
                if (row['low'] < prev_rows['low'].min() and 
                    row['low'] < next_rows['low'].min()):
                    swings_low.append((len(recent) - len(recent) + i, row['low']))
            
            return {'swing_highs': swings_high, 'swing_lows': swings_low}
        except Exception as e:
            logger.debug(f"Swing detection failed: {e}")
            return {'swing_highs': [], 'swing_lows': []}

    def detect_bos(self, df: pd.DataFrame, direction: str, lookback: int = 30) -> Optional[Dict]:
        """Detect Break of Structure (BOS).
        
        Args:
            direction: 'BULLISH' or 'BEARISH'
            
        Returns:
            Dict with BOS info or None if not detected
        """
        try:
            if len(df) < lookback:
                return None
            
            recent = df.tail(lookback)
            current_price = float(recent['close'].iloc[-1])
            
            if direction == "BULLISH":
                # Look for higher high breakout
                recent_highs = recent['high'].values[:-3]  # Exclude last 3 bars
                if len(recent_highs) > 0:
                    previous_hh = recent_highs.max()
                    if current_price > previous_hh * 1.001:  # 0.1% buffer
                        return {
                            'type': 'BOS',
                            'direction': 'BULLISH',
                            'level': float(previous_hh),
                            'confirmed': True
                        }
            else:
                # Look for lower low breakout
                recent_lows = recent['low'].values[:-3]
                if len(recent_lows) > 0:
                    previous_ll = recent_lows.min()
                    if current_price < previous_ll * 0.999:
                        return {
                            'type': 'BOS',
                            'direction': 'BEARISH',
                            'level': float(previous_ll),
                            'confirmed': True
                        }
            
            return None
        except Exception as e:
            logger.debug(f"BOS detection failed: {e}")
            return None

    def detect_choch(self, df: pd.DataFrame, prev_trend: str, lookback: int = 20) -> Optional[Dict]:
        """Detect Change of Character (CHoCH) - first sign of trend reversal.
        
        Args:
            prev_trend: Previous trend direction ('BULLISH' or 'BEARISH')
            
        Returns:
            Dict with CHoCH info or None
        """
        try:
            if len(df) < lookback:
                return None
            
            recent = df.tail(lookback)
            closes = recent['close'].values
            highs = recent['high'].values
            lows = recent['low'].values
            
            # For BULLISH to BEARISH CHoCH: price breaks below recent swing low
            if prev_trend == "BULLISH":
                swing_low_idx = np.argmin(lows[-10:]) if len(lows) >= 10 else 0
                swing_low = float(lows[swing_low_idx])
                current_close = float(closes[-1])
                
                if current_close < swing_low * 0.999:
                    return {
                        'type': 'CHoCH',
                        'from_trend': 'BULLISH',
                        'to_trend': 'BEARISH',
                        'level': swing_low,
                        'confirmed': True
                    }
            
            # For BEARISH to BULLISH CHoCH: price breaks above recent swing high
            elif prev_trend == "BEARISH":
                swing_high_idx = np.argmax(highs[-10:]) if len(highs) >= 10 else 0
                swing_high = float(highs[swing_high_idx])
                current_close = float(closes[-1])
                
                if current_close > swing_high * 1.001:
                    return {
                        'type': 'CHoCH',
                        'from_trend': 'BEARISH',
                        'to_trend': 'BULLISH',
                        'level': swing_high,
                        'confirmed': True
                    }
            
            return None
        except Exception as e:
            logger.debug(f"CHoCH detection failed: {e}")
            return None

    # ====================================================================
    # LIQUIDITY SWEEP DETECTION
    # ====================================================================
    
    def detect_liquidity_sweep(self, df: pd.DataFrame, lookback: int = 30) -> Optional[Dict]:
        """Detect Liquidity Sweep pattern.
        
        Pattern: Price wicks beyond recent swing high/low, then closes back inside.
        
        Returns:
            Dict with sweep info or None
        """
        try:
            if len(df) < lookback:
                return None
            
            recent = df.tail(lookback)
            n = len(recent)
            
            # Find recent swing points
            highs = recent['high'].values
            lows = recent['low'].values
            closes = recent['close'].values
            opens = recent['open'].values
            ranges = highs - lows
            
            # Check for BUY-side liquidity sweep (wick above swing high, close back inside)
            for i in range(n - 3):  # Leave room for confirmation
                current_bar = recent.iloc[i]
                current_high = float(current_bar['high'])
                current_low = float(current_bar['low'])
                current_close = float(current_bar['close'])
                current_open = float(current_bar['open'])
                current_range = current_high - current_low
                
                if current_range <= 0:
                    continue
                
                # Check if this bar swept above a recent high
                prev_highs = highs[:i]
                if len(prev_highs) > 0:
                    recent_high = prev_highs.max()
                    
                    # Wick must extend beyond previous high by at least some ratio
                    wick_above = current_high - max(current_open, current_close)
                    wick_ratio = wick_above / current_range
                    
                    if current_high > recent_high and wick_ratio >= self.sweep_min_wick:
                        # Check if next 1-2 bars close back inside (below the swept high)
                        if i + 1 < n:
                            next_close = float(recent.iloc[i + 1]['close'])
                            if next_close < current_high:
                                # BUY-side liquidity sweep confirmed
                                return {
                                    'type': 'SWEEP',
                                    'side': 'BUY_SIDE',
                                    'swept_level': float(recent_high),
                                    'wick_high': current_high,
                                    'wick_ratio': round(wick_ratio, 2),
                                    'sweep_bar_idx': i,
                                    'confirmed': True,
                                    'description': f"Buy-side liquidity sweep at {recent_high:.2f}"
                                }
            
            # Check for SELL-side liquidity sweep (wick below swing low, close back inside)
            for i in range(n - 3):
                current_bar = recent.iloc[i]
                current_high = float(current_bar['high'])
                current_low = float(current_bar['low'])
                current_close = float(current_bar['close'])
                current_open = float(current_bar['open'])
                current_range = current_high - current_low
                
                if current_range <= 0:
                    continue
                
                # Check if this bar swept below a recent low
                prev_lows = lows[:i]
                if len(prev_lows) > 0:
                    recent_low = prev_lows.min()
                    
                    # Wick must extend beyond previous low
                    wick_below = min(current_open, current_close) - current_low
                    wick_ratio = wick_below / current_range
                    
                    if current_low < recent_low and wick_ratio >= self.sweep_min_wick:
                        # Check if next bar closes back inside (above the swept low)
                        if i + 1 < n:
                            next_close = float(recent.iloc[i + 1]['close'])
                            if next_close > current_low:
                                # SELL-side liquidity sweep confirmed
                                return {
                                    'type': 'SWEEP',
                                    'side': 'SELL_SIDE',
                                    'swept_level': float(recent_low),
                                    'wick_low': current_low,
                                    'wick_ratio': round(wick_ratio, 2),
                                    'sweep_bar_idx': i,
                                    'confirmed': True,
                                    'description': f"Sell-side liquidity sweep at {recent_low:.2f}"
                                }
            
            return None
        except Exception as e:
            logger.debug(f"Liquidity sweep detection failed: {e}")
            return None

    # ====================================================================
    # ORDER BLOCK DETECTION
    # ====================================================================
    
    def detect_order_block(self, df: pd.DataFrame, lookback: int = 30) -> Optional[Dict]:
        """Detect fresh Order Block zones.
        
        Bullish OB: Last bearish candle before impulsive move up
        Bearish OB: Last bullish candle before impulsive move down
        
        Returns:
            Dict with OB info or None
        """
        try:
            if len(df) < lookback:
                return None
            
            recent = df.tail(lookback)
            n = len(recent)
            
            # Find impulsive moves (large candles)
            for i in range(5, n):
                current = recent.iloc[i]
                prev = recent.iloc[i - 1]
                
                current_range = float(current['high'] - current['low'])
                prev_range = float(prev['high'] - prev['low'])
                
                if current_range <= 0 or prev_range <= 0:
                    continue
                
                # Bullish Order Block: Last bearish candle before strong bullish move
                if (float(current['close'] - current['open']) > current_range * 0.6 and  # Strong bullish
                    float(prev['close'] - prev['open']) < 0):  # Previous was bearish
                    # Check if this is an impulsive move (>1.5x average range)
                    avg_range = float(np.mean([float(recent.iloc[j]['high'] - recent.iloc[j]['low']) for j in range(max(0,i-10), i)]))
                    if current_range > avg_range * 1.5:
                        return {
                            'type': 'ORDER_BLOCK',
                            'side': 'BULLISH',
                            'zone': {
                                'high': float(prev['high']),
                                'low': float(prev['low']),
                                'open': float(prev['open']),
                                'close': float(prev['close'])
                            },
                            'impulse_bar_idx': i,
                            'range': round(current_range, 5),
                            'fresh': True,
                            'description': f"Bullish OB at {prev['low']:.2f}-{prev['high']:.2f}"
                        }
                
                # Bearish Order Block: Last bullish candle before strong bearish move
                if (float(current['close'] - current['open']) < -current_range * 0.6 and  # Strong bearish
                    float(prev['close'] - prev['open']) > 0):  # Previous was bullish
                    avg_range = float(np.mean([float(recent.iloc[j]['high'] - recent.iloc[j]['low']) for j in range(max(0,i-10), i)]))
                    if current_range > avg_range * 1.5:
                        return {
                            'type': 'ORDER_BLOCK',
                            'side': 'BEARISH',
                            'zone': {
                                'high': float(prev['high']),
                                'low': float(prev['low']),
                                'open': float(prev['open']),
                                'close': float(prev['close'])
                            },
                            'impulse_bar_idx': i,
                            'range': round(current_range, 5),
                            'fresh': True,
                            'description': f"Bearish OB at {prev['low']:.2f}-{prev['high']:.2f}"
                        }
            
            return None
        except Exception as e:
            logger.debug(f"Order block detection failed: {e}")
            return None

    # ====================================================================
    # FAIR VALUE GAP (FVG) DETECTION
    # ====================================================================
    
    def detect_fvg(self, df: pd.DataFrame, lookback: int = 30) -> Optional[Dict]:
        """Detect Fair Value Gap patterns.
        
        Bullish FVG: Candle 1 high < Candle 3 low (gap between)
        Bearish FVG: Candle 1 low > Candle 3 high (gap between)
        
        Returns:
            Dict with FVG info or None
        """
        try:
            if len(df) < lookback:
                return None
            
            recent = df.tail(lookback)
            n = len(recent)
            
            for i in range(2, n):
                c1 = recent.iloc[i - 2]
                c2 = recent.iloc[i - 1]
                c3 = recent.iloc[i]
                
                c1_high = float(c1['high'])
                c1_low = float(c1['low'])
                c2_high = float(c2['high'])
                c2_low = float(c2['low'])
                c3_high = float(c3['high'])
                c3_low = float(c3['low'])
                
                # Bullish FVG: Gap between c1 high and c3 low
                if c3_low > c1_high:
                    gap_size = c3_low - c1_high
                    if gap_size > 0:  # Valid gap
                        return {
                            'type': 'FVG',
                            'side': 'BULLISH',
                            'gap_top': c1_high,
                            'gap_bottom': c3_low,
                            'gap_size': round(gap_size, 5),
                            'middle': round((c1_high + c3_low) / 2, 5),
                            'formed_at_idx': i - 2,
                            'fresh': True,
                            'description': f"Bullish FVG: {c1_high:.2f} - {c3_low:.2f}"
                        }
                
                # Bearish FVG: Gap between c3 high and c1 low
                if c1_low > c3_high:
                    gap_size = c1_low - c3_high
                    if gap_size > 0:
                        return {
                            'type': 'FVG',
                            'side': 'BEARISH',
                            'gap_top': c1_low,
                            'gap_bottom': c3_high,
                            'gap_size': round(gap_size, 5),
                            'middle': round((c1_low + c3_high) / 2, 5),
                            'formed_at_idx': i - 2,
                            'fresh': True,
                            'description': f"Bearish FVG: {c3_high:.2f} - {c1_low:.2f}"
                        }
            
            return None
        except Exception as e:
            logger.debug(f"FVG detection failed: {e}")
            return None

    # ====================================================================
    # VOLUME ANALYSIS
    # ====================================================================
    
    def analyze_volume(self, df: pd.DataFrame) -> Dict:
        """Analyze volume for surge and flow confirmation."""
        try:
            if 'tick_volume' not in df.columns or len(df) < 20:
                return {'surge': False, 'ratio': 0, 'trend': 'NEUTRAL'}
            
            recent_vol = df['tick_volume'].values[-20:]
            avg_vol = float(np.mean(recent_vol[:-1]))
            latest_vol = float(recent_vol[-1])
            surge_ratio = latest_vol / (avg_vol + 1e-9)
            
            # Volume trend (last 5 vs previous 5)
            vol_short = float(np.mean(recent_vol[-5:]))
            vol_long = float(np.mean(recent_vol[:-5]))
            vol_trend = 'INCREASING' if vol_short > vol_long * 1.1 else ('DECREASING' if vol_short < vol_long * 0.9 else 'NEUTRAL')
            
            return {
                'surge': surge_ratio >= 1.5,
                'ratio': round(surge_ratio, 2),
                'trend': vol_trend,
                'avg': round(avg_vol, 0),
                'latest': round(latest_vol, 0)
            }
        except Exception as e:
            logger.debug(f"Volume analysis failed: {e}")
            return {'surge': False, 'ratio': 0, 'trend': 'NEUTRAL'}

    # ====================================================================
    # CONFLENCE SCORING
    # ====================================================================
    
    def calculate_confluence_score(self, signals: List[str]) -> int:
        """Calculate confluence score based on active signals.
        
        Each valid signal adds points:
        - Liquidity Sweep: +2
        - BOS/CHoCH: +2
        - Order Block: +1
        - FVG: +1
        - Volume Surge: +1
        - G-Channel Alignment: +1
        """
        score = 0
        for sig in signals:
            if sig in ['LIQUIDITY_SWEEP', 'BOS', 'CHoCH']:
                score += 2
            elif sig in ['ORDER_BLOCK', 'FVG', 'VOLUME_SURGE', 'GCHANNEL_ALIGN']:
                score += 1
        return score

    # ====================================================================
    # NEWS FILTER (existing)
    # ====================================================================
    
    async def _update_calendar_cache_async(self) -> None:
        """Refresh Forex Factory calendar cache."""
        if not HAS_REQUESTS:
            return
            
        now_t = time.time()
        if self._ff_events and (now_t - self._last_ff_download < 3600):
            return

        if self._cache_file.exists() and (now_t - self._cache_file.stat().st_mtime < 21600):
            try:
                with open(self._cache_file, "r") as f:
                    self._ff_events = json.load(f)
                    self._last_ff_download = now_t
                    return
            except Exception as e:
                logger.warning(f"Failed to read news cache: {e}")

        url = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
        try:
            events = await asyncio.to_thread(self._fetch_calendar_sync, url)
            if events:
                self._ff_events = events
                self._last_ff_download = now_t
                self._cache_file.parent.mkdir(parents=True, exist_ok=True)
                with open(self._cache_file, "w") as f:
                    json.dump(events, f)
                logger.info(f"[FF News] Refreshed {len(self._ff_events)} events.")
        except Exception as e:
            logger.warning(f"[FF News] Calendar download failed: {e}")

    @staticmethod
    def _fetch_calendar_sync(url: str) -> List:
        try:
            resp = requests.get(url, timeout=6)
            if resp.status_code == 200:
                return resp.json() or []
        except Exception:
            pass
        return []

    async def check_news_block(self, symbol: Optional[str] = None) -> bool:
        """Block trading during high-impact USD news."""
        try:
            await self._update_calendar_cache_async()
            if not self._ff_events:
                self.sentiment_decision = "ALLOW"
                return False

            now_utc = self._get_market_timestamp(symbol)
            pre_block = int(self.config.get("news", {}).get("block_window_min", 30))
            post_block = max(15, pre_block // 2)

            for event in self._ff_events:
                if event.get("currency") == "USD" and "High" in event.get("impact", ""):
                    date_str = event.get("date", "")
                    if len(date_str) < 19:
                        continue
                    try:
                        parsed_dt = datetime.strptime(date_str[:19], "%Y-%m-%dT%H:%M:%S")
                        event_time = parsed_dt.replace(tzinfo=timezone.utc)
                        diff_minutes = (event_time - now_utc).total_seconds() / 60.0
                        if -post_block <= diff_minutes <= pre_block:
                            logger.warning(f"🚫 [NEWS BLOCK] '{event.get('title')}' at {event_time.strftime('%H:%M UTC')}")
                            self.sentiment_decision = "BLOCK"
                            return True
                    except ValueError:
                        continue

            self.sentiment_decision = "ALLOW"
            return False
        except Exception as e:
            logger.error(f"News block error: {e}")
            self.sentiment_decision = "ALLOW"
            return False

    # ====================================================================
    # MAIN ANALYSIS ENTRY POINT
    # ====================================================================
    
    async def analyze_market(self, symbol: str, data: pd.DataFrame) -> Dict:
        """Main ICT analysis entry point.
        
        Returns dict with: action, bias, confidence, reasoning, entry_price, 
        stop_loss, take_profit, tp_levels, ict_status, confluence_score
        """
        try:
            if len(data) < self.lookback_bars:
                return {"action": "HOLD", "bias": "NEUTRAL", "confidence": 0.0, 
                        "reasoning": "Insufficient data"}

            df = data.copy()
            idx = len(df) - 1
            current_price = float(df["close"].iloc[idx])
            
            # Calculate ATR
            if len(df) >= 14 and "tr" in df.columns:
                atr = float(df["tr"].rolling(14).mean().iloc[-1])
            else:
                atr = current_price * 0.01
            
            # Detect all ICT components
            liquidity_sweep = self.detect_liquidity_sweep(df, self.lookback_bars)
            bos = self.detect_bos(df, "BULLISH", self.lookback_bars)
            choch = None
            order_block = self.detect_order_block(df, self.ob_lookback)
            fvg = self.detect_fvg(df, self.fvg_lookback)
            volume = self.analyze_volume(df)
            kill_zone_active, kill_zone_name = self.is_kill_zone_active()
            
            # Determine market bias from structure
            bias = self._determine_bias_from_structure(df, liquidity_sweep, bos, choch)
            
            # Count confluence signals
            signals = []
            if liquidity_sweep:
                signals.append('LIQUIDITY_SWEEP')
            if bos:
                signals.append('BOS')
            if order_block:
                signals.append('ORDER_BLOCK')
            if fvg:
                signals.append('FVG')
            if volume.get('surge'):
                signals.append('VOLUME_SURGE')
            
            confluence_score = self.calculate_confluence_score(signals)
            
            # Determine action based on ICT setup
            action, confidence, entry_plan, reason = self._evaluate_ict_setup(
                liquidity_sweep, bos, order_block, fvg, volume, kill_zone_active, bias
            )
            
            # Calculate SL/TP based on ICT levels
            stop_loss, take_profit, tp_levels = self._calculate_ict_sl_tp(
                action, current_price, liquidity_sweep, atr, order_block
            )
            
            # Build result
            result = {
                "action": action,
                "bias": bias,
                "confidence": confidence,
                "reasoning": reason,
                "entry_price": current_price,
                "use_limit": False,
                "stop_loss": stop_loss,
                "take_profit": take_profit,
                "tp_levels": tp_levels,
                "volume_surge": volume.get('surge', False),
                "confluence_score": confluence_score,
                "min_confluence_met": confluence_score >= self.min_confluence,
                "kill_zone_active": kill_zone_active,
                "kill_zone_name": kill_zone_name,
                "signal_meta": {
                    "plan": entry_plan,
                    "atr": round(atr, 2),
                    "sl_distance": round(abs(current_price - stop_loss), 2) if stop_loss else 0,
                    "signals_detected": signals,
                    "liquidity_sweep": liquidity_sweep is not None,
                    "bos_detected": bos is not None,
                    "order_block": order_block is not None,
                    "fvg_detected": fvg is not None,
                    "volume_ratio": volume.get('ratio', 0),
                },
                "ict_status": {
                    "trend": bias,
                    "mode": entry_plan,
                    "confluence": confluence_score,
                    "kill_zone": kill_zone_name if kill_zone_active else "OUTSIDE_ZONE",
                    "sweep": liquidity_sweep['description'] if liquidity_sweep else None,
                    "structure": f"BOS: {bos['direction']}" if bos else ("CHoCH detected" if choch else "No shift"),
                    "ob": order_block['description'] if order_block else None,
                    "fvg": fvg['description'] if fvg else None,
                    "volume": f"Surge: {volume.get('ratio', 0)}x" if volume.get('surge') else "Normal",
                },
            }
            
            # Check news block
            if await self.check_news_block(symbol):
                result['action'] = 'HOLD'
                result['reasoning'] = 'NEWS BLOCK: Active USD High-Impact Window'
                result['ict_status']['status'] = 'NEWS_BLOCK'
            
            # Only log significant signals at most once per 30 seconds
            if action in ['BUY', 'SELL'] or confluence_score >= self.min_confluence:
                _now = time.time()
                _last = self._last_ict_log.get(symbol, 0)
                if _now - _last > 30:
                    logger.info(
                        f"📊 [ICT Analysis] {symbol} | Action: {action} | Conf: {confidence:.2f} | "
                        f"Confluence: {confluence_score}/{self.min_confluence} | "
                        f"Zone: {kill_zone_name if kill_zone_active else 'OUTSIDE'} | "
                        f"Signals: {signals}"
                    )
                    self._last_ict_log[symbol] = _now
            
            return result
            
        except Exception as e:
            logger.error(f"ICT analysis error on {symbol}: {e}", exc_info=True)
            return {"action": "HOLD", "bias": "NEUTRAL", "confidence": 0.0, 
                    "reasoning": f"Analysis Exception: {str(e)}"}

    def _determine_bias_from_structure(self, df: pd.DataFrame, sweep, bos, choch) -> str:
        """Determine market bias from structural analysis."""
        try:
            if sweep:
                # Sweep side indicates likely reversal direction
                if sweep.get('side') == 'BUY_SIDE':
                    return "BEARISH"
                elif sweep.get('side') == 'SELL_SIDE':
                    return "BULLISH"
            
            if bos:
                return "BULLISH" if bos.get('direction') == 'BULLISH' else "BEARISH"
            
            if choch:
                return choch.get('to_trend', 'NEUTRAL')
            
            # Fallback to simple momentum
            if len(df) >= 20:
                recent = df.tail(20)
                closes = recent['close'].values
                if closes[-1] > closes[-5] and closes[-5] > closes[-10]:
                    return "BULLISH"
                elif closes[-1] < closes[-5] and closes[-5] < closes[-10]:
                    return "BEARISH"
            
            return "NEUTRAL"
        except Exception:
            return "NEUTRAL"

    def _evaluate_ict_setup(self, sweep, bos, ob, fvg, volume, kill_zone, bias) -> Tuple[str, float, str, str]:
        """Evaluate ICT setup and determine action."""
        try:
            signals = []
            reason_parts = []
            
            if sweep:
                signals.append('sweep')
                reason_parts.append(f"Sweep: {sweep.get('description', '')}")
            
            if bos:
                signals.append('bos')
                reason_parts.append(f"BOS: {bos.get('direction', '')}")
            
            if ob:
                signals.append('ob')
                reason_parts.append(f"OB: {ob.get('description', '')}")
            
            if fvg:
                signals.append('fvg')
                reason_parts.append(f"FVG: {fvg.get('description', '')}")
            
            if volume.get('surge'):
                signals.append('vol')
                reason_parts.append("Volume Surge")
            
            if not kill_zone:
                reason_parts.append("Outside Kill Zone")
            
            # Decision logic
            if len(signals) >= 2 and bias != "NEUTRAL":
                if bias == "BULLISH":
                    return "BUY", 0.85 + (len(signals) * 0.02), "ICT_SWEEP_REVERSAL", "; ".join(reason_parts)
                elif bias == "BEARISH":
                    return "SELL", 0.85 + (len(signals) * 0.02), "ICT_SWEEP_REVERSAL", "; ".join(reason_parts)
            
            return "HOLD", 0.0, "SCAN", "Insufficient ICT confluence"
        except Exception as e:
            logger.debug(f"ICT evaluation error: {e}")
            return "HOLD", 0.0, "ERROR", str(e)

    def _calculate_ict_sl_tp(self, action: str, entry_price: float, sweep, atr: float, ob) -> Tuple[float, float, Dict]:
        """Calculate ICT-based SL and TP levels."""
        try:
            if action not in ["BUY", "SELL"]:
                return 0.0, 0.0, {}
            
            # SL: Beyond sweep extreme or OB zone
            if sweep and sweep.get('side') == 'BUY_SIDE':
                # For SELL: SL above sweep high
                sl_price = sweep.get('wick_high', entry_price + atr * self.sl_atr_mult)
                sl_distance = abs(sl_price - entry_price)
            elif sweep and sweep.get('side') == 'SELL_SIDE':
                # For BUY: SL below sweep low
                sl_price = sweep.get('wick_low', entry_price - atr * self.sl_atr_mult)
                sl_distance = abs(sl_price - entry_price)
            else:
                # Default: ATR-based
                sl_price = entry_price - atr * self.sl_atr_mult if action == "BUY" else entry_price + atr * self.sl_atr_mult
                sl_distance = atr * self.sl_atr_mult
            
            # TP: Based on R:R targets
            tp1 = entry_price + sl_distance * self.tp_min_rr if action == "BUY" else entry_price - sl_distance * self.tp_min_rr
            tp2 = entry_price + sl_distance * self.tp_prefer_rr if action == "BUY" else entry_price - sl_distance * self.tp_prefer_rr
            tp3 = entry_price + sl_distance * 4.0 if action == "BUY" else entry_price - sl_distance * 4.0
            tp4 = entry_price + sl_distance * 5.0 if action == "BUY" else entry_price - sl_distance * 5.0
            
            # Primary TP = next opposing liquidity pool (use swing high/low)
            primary_tp = tp2  # Default to 1:3 R:R
            
            return sl_price, primary_tp, {
                "tp1": tp1, "tp2": tp2, "tp3": tp3, "tp4": tp4,
                "sl": sl_price,
                "rr_min": self.tp_min_rr,
                "rr_preferred": self.tp_prefer_rr,
                "sl_distance": round(sl_distance, 5)
            }
        except Exception as e:
            logger.debug(f"SL/TP calculation error: {e}")
            return 0.0, 0.0, {}

    def remember_trade(self, trade_data: Dict) -> None:
        """Store trade metadata for learning."""
        try:
            self.memories.append({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "symbol": trade_data.get("symbol"),
                "action": trade_data.get("action"),
                "pnl": float(trade_data.get("pnl", 0.0)),
                "success": float(trade_data.get("pnl", 0.0)) > 0,
            })
            if len(self.memories) > 1000:
                self.memories = self.memories[-1000:]
        except Exception as e:
            logger.debug(f"Trade memory save failed: {e}")

    def _load_memories(self) -> None:
        """Load historical trade logs."""
        try:
            memory_file = Path("models/ai_memories.json")
            if memory_file.exists() and memory_file.stat().st_size > 0:
                with open(memory_file, "r") as f:
                    self.memories = json.load(f)
                self.model_trained = bool(self.memories)
                logger.debug(f"🧠 Loaded {len(self.memories)} trade memories.")
        except Exception as e:
            logger.warning(f"Could not load memory file: {e}")
