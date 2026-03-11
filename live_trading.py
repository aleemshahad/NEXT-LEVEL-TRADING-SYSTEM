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
import requests
import hmac
import hashlib
import uuid
import platform
from dotenv import load_dotenv

# Advanced Intelligence Integrations
from computer_vision_analyzer import ComputerVisionAnalyzer
from market_intelligence.sentiment_intelligence import SentimentIntelligenceEngine
from market_intelligence.data_acquisition import DataAcquisitionService

# Load environment variables
load_dotenv()

# Setup logging
logger.remove()
logger.add(sys.stdout, format="<green>{time:HH:mm:ss}</green> | <level>{level}</level> | <cyan>{message}</cyan>", level="INFO")
logger.add("logs/live_trading_{time:YYYY-MM-DD}.log", rotation="1 day", retention="30 days")

# Dashboard Log Pipe: Mirror all INFO/WARNING/ERROR to a separate text file for the console UI
logger.add("logs/latest_intelligence_report.txt", format="{time:HH:mm:ss} | {level} | {message}", 
           level="INFO", rotation="5 MB", mode="w")

class DiscordNotifier:
    """Discord Webhook Notifier for Real-time Trading Signals & Updates (Robust requests-based)"""
    def __init__(self, webhook_url: str = None):
        self.webhook_url = webhook_url or os.getenv("DISCORD_WEBHOOK_URL")

    async def close(self):
        if self.webhook_url:
            await self.send_message("👋 Trading Session Terminated. Bot is going offline.", title="System Shutdown", color=0x888888)

    async def send_message(self, content: str, title: str = "Trading Update", color: int = 0x58a6ff) -> bool:
        if not self.webhook_url:
            return False
        
        def _send():
            try:
                payload = {
                    "embeds": [{
                        "title": title,
                        "description": content,
                        "color": color,
                        "timestamp": datetime.utcnow().isoformat()
                    }]
                }
                resp = requests.post(self.webhook_url, json=payload, timeout=10)
                if resp.status_code not in [200, 204]:
                    logger.error(f"Discord Webhook Error ({resp.status_code}): {resp.text}")
                    return False
                return True
            except Exception as e:
                logger.error(f"Discord send failed: {e}")
                return False

        # Run synchronous request in a thread to avoid blocking the event loop
        return await asyncio.to_thread(_send)

    async def send_signal(self, symbol: str, action: str, confidence: float, reasoning: str, price: float, tp: float, sl: float):
        # 🟢 Bullish for BUY, 🔴 Bearish for SELL
        color = 0x00e676 if action == "BUY" else 0xff5252
        content = (
            f"🚀 **Symbol**: `{symbol}`\n"
            f"🎯 **Action**: `{action}`\n"
            f"💎 **Confidence**: `{confidence:.2f}`\n"
            f"💰 **Entry Price**: `{price:.5f}`\n"
            f"✅ **Take Profit**: `{tp:.5f}`\n"
            f"🛡️ **Stop Loss**: `{sl:.5f}`\n\n"
            f"🧠 **Logic**: {reasoning}"
        )
        return await self.send_message(content, title=f"🚨 New ICT Signal: {action} on {symbol}", color=color)

    async def send_heartbeat(self, account_info, daily_pnl, trades_today, active_positions) -> bool:
        content = (
            f"📈 **Account Balance**: `${account_info.balance:.2f}`\n"
            f"💵 **Daily P&L**: `{'+' if daily_pnl >= 0 else ''}${daily_pnl:.2f}`\n"
            f"📊 **Trades Today**: `{trades_today}`\n"
            f"📋 **Open Positions**: `{active_positions}`\n"
            f"⚖️ **Equity**: `${account_info.equity:.2f}`\n"
            f"⚓ **Margin Level**: `{account_info.margin_level:.1f}%`"
        )
        return await self.send_message(content, title="🕒 Scheduled Hourly Update", color=0x58a6ff)

# --- SECURITY & LICENSE MANAGER ---
class SecurityManager:
    """Institutional-grade License Management & HWID Validation"""
    def __init__(self):
        # Obfuscated SALT: Split into small chunks to prevent direct string searching
        # S1: "N3XT-L3V3L-TR4D1NG-"
        # S2: "5Y5T3M-2026-AL33M-"
        # S3: "SH4HZAD-S3CR3T"
        # Total SALT: "N3XT-L3V3L-TR4D1NG-5Y5T3M-2026-AL33M-SH4HZAD-S3CR3T"
        self._s_parts = ["N3XT-L3V3L-TR4D1NG-", "5Y5T3M-2026-AL33M-", "SH4HZAD-S3CR3T"]
        self.license_file = Path("logs/.license_key")
        self.hwid = self._generate_hwid()

    def _generate_hwid(self) -> str:
        """Derive a unique Hardware ID for the machine"""
        node_name = platform.node()
        node_id = uuid.getnode()
        return f"{node_name}-{node_id}"

    def get_full_salt(self) -> str:
        return "".join(self._s_parts)

    def validate_key(self, input_key: str) -> bool:
        """Verify the input key against the local HMAC-SHA256 signature"""
        clean_key = input_key.strip().upper().replace("-", "")
        if len(clean_key) != 16:
            return False

        # Calculate expected HMAC-SHA256 locally
        salt_bytes = self.get_full_salt().encode('utf-8')
        hwid_bytes = self.hwid.encode('utf-8')
        
        signature = hmac.new(salt_bytes, hwid_bytes, hashlib.sha256).hexdigest()
        expected_key = signature[:16].upper()
        
        # Constant-time comparison to prevent timing attacks
        return hmac.compare_digest(clean_key, expected_key)

    def is_authorized(self) -> bool:
        """Check if machine is already authorized with a valid key"""
        if self.license_file.exists():
            with open(self.license_file, "r") as f:
                saved_key = f.read().strip()
                return self.validate_key(saved_key)
        return False

    def save_key(self, key: str):
        """Persist key upon successful activation upon next launch"""
        with open(self.license_file, "w") as f:
            f.write(key.strip().upper())

    def prompt_activation(self):
        """User interaction flow for Activation"""
        print("\n" + "="*65)
        print("   🔒 NEXT LEVEL - SYSTEM ACTIVATION REQUIRED")
        print("="*65)
        print(f"   HWID: {self.hwid}")
        print("   " + "-"*65)
        print("   Please send the HWID above to the developer to get your key.")
        print("   " + "-"*65)
        
        while True:
            key = input("\n   >> Enter License Key: ").strip()
            if not key:
                print("   [!] Key cannot be empty.")
                continue
                
            if self.validate_key(key):
                self.save_key(key)
                print("\n   [SUCCESS] SYSTEM ACTIVATED FOR THIS MACHINE!")
                time.sleep(2)
                return True
            else:
                print("   [ERR] Invalid Key. Please try again or contact support.")
                retry = input("   Retry? (y/n): ").lower()
                if retry != 'y':
                    return False


class TradingBrain:
    """AI Trading Brain with Neural Network"""
    
    def __init__(self):
        self.memories = []
        self.model_trained = False
        self.confidence_threshold = 0.6
        self.sentiment_decision = "ALLOW"
        self.last_ff_status = "STALE"
        
        # Advanced Decision Engines (No longer simulated!)
        self.cv_analyzer = ComputerVisionAnalyzer()
        self.sentiment_engine = SentimentIntelligenceEngine()
        self.data_service = DataAcquisitionService()
        self.last_cv_report = "NO DATA"
        self.last_sentiment_report = "NO DATA"
        
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
            for sym in ["XAUUSDm", "EURUSDm", "XAUUSDm", "XAUUSD"]:
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

            # --- STEP 2: CLOCK SYNC (Critical Fix for Drift) ---
            now_utc = self._get_market_timestamp()
            local_utc = datetime.utcnow()
            drift = (local_utc - now_utc).total_seconds()
            
            if abs(drift) > 60:
                logger.warning(f"[TIME] System clock drift detected ({drift:.0f}s). Anchoring analysis to Broker Time: {now_utc.strftime('%H:%M:%S')}")

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
                logger.debug(f"🧠 Loaded {len(self.memories)} training memories. AI is ready.")
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

    async def analyze_market(self, symbol: str, data: pd.DataFrame) -> Dict:
        """ICT/SMC AI market analysis matching Notebook Accuracy"""
        try:
            if len(data) < 50:
                return {'action': 'HOLD', 'bias': 'NEUTRAL', 'confidence': 0.0, 'reasoning': 'Insufficient data'}
            
            # Add technical indicators
            data = self._add_indicators(data)
            index = len(data) - 1

            # 1. Core Structure (Notebook logic)
            mss_r = await self._detect_market_structure(data)
            bias = mss_r['bias']
            structure = mss_r['structure']
            
            # 2. Key ICT Concepts (Notebook logic)
            sweep = self._detect_liquidity_sweep(data, index)
            fvg = self._detect_fair_value_gap(data, index)
            ob = self._detect_order_block(data, index, bias)
            range_info = self._analyze_dealing_range(data, index)
            ote_level = self._check_ote_levels(data, index, fvg)
            rr_tracks = self._detect_railroad_tracks(data)
            
            # 3. Decision Logic (Notebook weighted score)
            score = 0
            signals_present = [f"MSS: {structure}"]
            
            if sweep['detected']:
                if (bias == 'BULLISH' and sweep['type'] == 'BELOW_LOW') or (bias == 'BEARISH' and sweep['type'] == 'ABOVE_HIGH'):
                    score += 1.0
                    signals_present.append(f"Sweep ({sweep['type']})")
                else:
                    score += 0.5
            
            if fvg['detected'] and fvg.get('type') == bias:
                score += 1.0
                signals_present.append(f"FVG ({fvg['type']})")
            
            if ob['detected'] and ob.get('type') == bias:
                score += 0.5
                signals_present.append(f"OB ({ob['type']})")
            
            if rr_tracks['detected'] and rr_tracks.get('type') == bias:
                score += 0.5
                signals_present.append("RR Tracks")
            
            # Confluence check
            confidence = min(1.0, score / 2.5)
            
            # --- ADVANCED AI INTEGRATION (CV & SENTIMENT) ---
            # 1. Computer Vision Regime Validation
            try:
                cv_res = self.cv_analyzer.analyze_market_regime(data)
                curr_regime = cv_res.get('current_regime')
                if curr_regime:
                    self.last_cv_report = f"{curr_regime.regime.value} ({curr_regime.confidence:.0%})"
                    # If CV disagrees with MSS bias, reduce confidence
                    if (bias == 'BULLISH' and curr_regime.regime.name == 'TREND_DOWN') or \
                       (bias == 'BEARISH' and curr_regime.regime.name == 'TREND_UP'):
                        score *= 0.5
            except Exception as cv_e:
                logger.debug(f"CV analysis error: {cv_e}")

            # 2. Market Intelligence (Sentiment) Process
            try:
                # Aggregate latest 'news' and 'macro' data
                raw_intel = self.data_service.aggregate_data()
                intel_report = self.sentiment_engine.run_analysis_cycle(raw_intel)
                
                self.last_sentiment_report = f"{intel_report.sentiment_summary.bias.value.upper()} | Score: {intel_report.sentiment_summary.sentiment_score:.2f}"
                self.risk_modifier = intel_report.decision_impact.risk_modifier
                
                # Check for blocking sentiment
                if intel_report.decision_impact.action == "BLOCK":
                     self.sentiment_decision = "BLOCK"
            except Exception as sent_e:
                logger.debug(f"Sentiment engine error: {sent_e}")

            # Filter by Silver Bullet and Sentiment
            market_now = self._get_market_timestamp()
            is_sb_time = self._is_silver_bullet_time(market_now)
            self._check_sentiment_bias() # Legacy FF news check
            
            if self.sentiment_decision == "BLOCK":
                return {
                    'action': 'HOLD', 
                    'bias': bias, 
                    'confidence': 0.0, 
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
    
    async def _detect_market_structure(self, df: pd.DataFrame, lookback: int = 20) -> Dict:
        """Concept 1: Market Structure (MSS / BOS / ChoCH) - Notebook Match"""
        try:
            if len(df) < lookback + 2: return {'structure': "NEUTRAL", 'bias': "NEUTRAL"}
            
            index = len(df) - 1
            recent = df.iloc[max(0, index-lookback): index+1]
            
            # Using 3-bar rolling window for swing points like notebook
            swing_highs = recent['high'].rolling(3, center=True).max()
            swing_lows  = recent['low'].rolling(3, center=True).min()
            
            prev_high   = swing_highs.iloc[-2]
            prev_low    = swing_lows.iloc[-2]
            curr_high   = df['high'].iloc[-1]
            curr_low    = df['low'].iloc[-1]

            if curr_high > prev_high and curr_low > prev_low:
                structure = "BULLISH_BOS"
                bias = "BULLISH"
            elif curr_low < prev_low and curr_high < prev_high:
                structure = "BEARISH_BOS"
                bias = "BEARISH"
            elif (curr_low < prev_low and curr_high > prev_high) or (curr_high > prev_high and curr_low < prev_low):
                structure = "CHOCH"
                bias = "NEUTRAL" # Character change is transitional
            else:
                structure = "NEUTRAL"
                bias = "NEUTRAL"

            return {'structure': structure, 'bias': bias, 'prev_high': prev_high, 'prev_low': prev_low}
        except Exception as e:
            logger.error(f"Market structure error: {e}")
            return {'structure': "NEUTRAL", 'bias': "NEUTRAL"}

    def _detect_railroad_tracks(self, df: pd.DataFrame) -> Dict:
        """Concept 12: Railroad Tracks (Major Reversal Pattern)"""
        try:
            if len(df) < 5: return {'detected': False}
            
            bar1 = df.iloc[-2]
            bar2 = df.iloc[-1]
            
            # 1. Opposite Directions
            dir1 = 1 if bar1['close'] > bar1['open'] else -1
            dir2 = 1 if bar2['close'] > bar2['open'] else -1
            
            if dir1 == dir2: return {'detected': False}
            
            # 2. Similar Size (Relaxed to 75% for more frequent detection)
            size1 = abs(bar1['close'] - bar1['open'])
            size2 = abs(bar2['close'] - bar2['open'])
            
            if size1 == 0 or size2 == 0: return {'detected': False}
            
            similarity = min(size1, size2) / max(size1, size2)
            
            # 3. Size must be significant (Relaxed to 0.3 ATR)
            atr = (df['high'] - df['low']).rolling(14).mean().iloc[-1]
            if size1 < atr * 0.3: return {'detected': False}
            
            if similarity > 0.75:
                track_type = "BULLISH" if dir2 == 1 else "BEARISH"
                return {
                    'detected': True,
                    'type': track_type,
                    'strength': similarity,
                    'msg': f"🚂 Railroad Tracks Found! ({track_type})"
                }
            
            return {'detected': False}
        except: return {'detected': False}
    
    def _detect_liquidity_sweep(self, df: pd.DataFrame, index: int) -> Dict:
        """Refined Liquidity Sweep Detection (Notebook v2.2)"""
        try:
            lookback = 30
            if index < lookback + 1:
                return {'detected': False}
            
            # Auto-tune thresholds based on recent volatility
            recent = df.iloc[max(0, index-50):index]
            avg_range = (recent['high'] - recent['low']).mean()
            avg_close = recent['close'].mean()
            vol_pct = (avg_range / avg_close) * 100 if avg_close > 0 else 0.1
            
            min_pen = max(0.001, vol_pct * 0.001)
            min_rej = max(0.0005, vol_pct * 0.0005)
            
            confirmed_idx = index - 1
            current_bar = df.iloc[confirmed_idx]
            recent_data = df.iloc[confirmed_idx - lookback : confirmed_idx]
            swing_low = recent_data['low'].min()
            swing_high = recent_data['high'].max()
            
            # Bullish Sweep (Sell-Side Liquidity)
            if current_bar['low'] < swing_low and current_bar['close'] > swing_low:
                pen = (swing_low - current_bar['low']) / swing_low * 100
                rej = (current_bar['close'] - swing_low) / swing_low * 100
                if pen >= min_pen and rej >= min_rej:
                    strength = min((pen + rej) / (min_pen + min_rej + 1e-9), 1.0)
                    return {'detected': True, 'type': 'BELOW_LOW', 'swept_level': swing_low, 'strength': strength}
            
            # Bearish Sweep (Buy-Side Liquidity)
            elif current_bar['high'] > swing_high and current_bar['close'] < swing_high:
                pen = (current_bar['high'] - swing_high) / swing_high * 100
                rej = (swing_high - current_bar['close']) / swing_high * 100
                if pen >= min_pen and rej >= min_rej:
                    strength = min((pen + rej) / (min_pen + min_rej + 1e-9), 1.0)
                    return {'detected': True, 'type': 'ABOVE_HIGH', 'swept_level': swing_high, 'strength': strength}
            
            return {'detected': False}
        except Exception as e:
            logger.error(f"Sweep detection error: {e}")
            return {'detected': False}
    
    def _detect_fair_value_gap(self, df: pd.DataFrame, index: int) -> Dict:
        """Refined FVG Detection with ATR-based significance (Notebook v2.0)"""
        try:
            if index < 3: return {'detected': False}
            
            bar1 = df.iloc[index-2]
            bar2 = df.iloc[index-1]
            bar3 = df.iloc[index]
            
            # ATR-based significance
            volatility = (df['high'] - df['low']).rolling(14).mean().iloc[index-1]
            min_gap = volatility * 0.15 # 15% of ATR threshold
            
            # Detect Bullish Gap (BISI)
            if bar1['high'] < bar3['low']:
                gap_size = bar3['low'] - bar1['high']
                if gap_size > min_gap:
                    strength = min(gap_size / (volatility * 0.5 + 1e-9), 1.0)
                    return {'detected': True, 'type': 'BULLISH', 'high': bar3['low'], 'low': bar1['high'], 'strength': strength}
            
            # Detect Bearish Gap (SIBI)
            elif bar1['low'] > bar3['high']:
                gap_size = bar1['low'] - bar3['high']
                if gap_size > min_gap:
                    strength = min(gap_size / (volatility * 0.5 + 1e-9), 1.0)
                    return {'detected': True, 'type': 'BEARISH', 'high': bar1['low'], 'low': bar3['high'], 'strength': strength}
            
            # 2. Scanning for Active (Unfilled) Gaps
            active_gaps = self._scan_active_fvgs(df)
            if active_gaps:
                nearest = active_gaps[0]
                return {'detected': True, 'active_only': True, **nearest}

            return {'detected': False}
        except Exception:
            return {'detected': False}

    def _scan_active_fvgs(self, df: pd.DataFrame, lookback: int = 50) -> List[Dict]:
        """Scan for historical FVGs that remain unfilled (Magnets)"""
        unfilled = []
        try:
            for i in range(len(df)-lookback, len(df)-2):
                b1, b2, b3 = df.iloc[i], df.iloc[i+1], df.iloc[i+2]
                gap = None
                if b1['high'] < b3['low']: # Bullish
                    gap = {'type': 'BULLISH', 'high': b3['low'], 'low': b1['high']}
                elif b1['low'] > b3['high']: # Bearish
                    gap = {'type': 'BEARISH', 'high': b1['low'], 'low': b3['high']}
                
                if gap:
                    # Check if filled since detected
                    is_filled = False
                    for j in range(i+3, len(df)):
                        price = df.iloc[j]['low'] if gap['type'] == 'BULLISH' else df.iloc[j]['high']
                        if (gap['type'] == 'BULLISH' and price <= gap['low']) or \
                           (gap['type'] == 'BEARISH' and price >= gap['high']):
                            is_filled = True
                            break
                    if not is_filled:
                        unfilled.append(gap)
            return unfilled[::-1] # Newest first
        except: return []
    
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
                
                # Relaxed price change threshold to 0.1% (0.001) for M5
                if bias == 'BULLISH' and price_change > 0.001 and next_bar['close'] > bar['close']: 
                    return {'detected': True, 'type': 'BULLISH', 'high': bar['high'], 'low': bar['low'], 'strength': min(price_change * 15, 1.0)}
                elif bias == 'BEARISH' and price_change > 0.001 and next_bar['close'] < bar['close']: 
                    return {'detected': True, 'type': 'BEARISH', 'high': bar['high'], 'low': bar['low'], 'strength': min(price_change * 15, 1.0)}
            
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
                    self.close_position(symbol, p.ticket)
        except Exception as e:
            logger.error(f"Error closing side {side}: {e}")

    def close_position(self, symbol: str, ticket: int) -> bool:
        """Close a specific position by ticket"""
        try:
            position = mt5.positions_get(ticket=ticket)
            if not position:
                return False
            
            p = position[0]
            action = mt5.ORDER_TYPE_SELL if p.type == mt5.POSITION_TYPE_BUY else mt5.ORDER_TYPE_BUY
            tick = mt5.symbol_info_tick(symbol)
            if tick is None:
                return False
            
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
                "comment": "CLOSE_POSITION",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }
            
            result = mt5.order_send(request)
            return result.retcode == mt5.TRADE_RETCODE_DONE
        except Exception as e:
            logger.error(f"Error closing position {ticket}: {e}")
            return False


    def place_order(self, symbol: str, action: str, volume: float, price: float, 
                   stop_loss: float = None, take_profit: float = None,
                   use_limit: bool = False) -> Dict:
        """Place trading order (Market or Limit)"""
        try:
            # Get symbol info
            symbol_info = mt5.symbol_info(symbol)
            if not symbol_info:
                return {'success': False, 'error': f'Symbol {symbol} not found'}
            
            # Determine order and action type
            if use_limit:
                trade_action = mt5.TRADE_ACTION_PENDING
                order_type = mt5.ORDER_TYPE_BUY_LIMIT if action == "BUY" else mt5.ORDER_TYPE_SELL_LIMIT
                filling_type = mt5.ORDER_FILLING_RETURN # Pendings prefer RETURN
            else:
                trade_action = mt5.TRADE_ACTION_DEAL
                order_type = mt5.ORDER_TYPE_BUY if action == "BUY" else mt5.ORDER_TYPE_SELL
                filling_type = mt5.ORDER_FILLING_IOC   # Instant orders use IOC
            
            # CRITICAL: Round all prices
            price = self.round_price(symbol, price)
            if stop_loss: stop_loss = self.round_price(symbol, stop_loss)
            if take_profit: take_profit = self.round_price(symbol, take_profit)

            request = {
                "action": trade_action,
                "symbol": symbol,
                "volume": volume,
                "type": order_type,
                "price": price,
                "deviation": 20,
                "magic": 234000,
                "comment": "ICT_SMC_TRADE",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": filling_type,
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
    
    def modify_sl_tp(self, ticket: int, sl: float = 0.0, tp: float = 0.0) -> bool:
        """Modify SL/TP for an open position"""
        try:
            # Prepare modify request
            request = {
                "action": mt5.TRADE_ACTION_SLTP,
                "position": ticket,
                "sl": sl,
                "tp": tp
            }
            result = mt5.order_send(request)
            if result.retcode != mt5.TRADE_RETCODE_DONE:
                logger.error(f"Failed to modify SL/TP for {ticket}: {result.retcode}")
                return False
            return True
        except Exception as e:
            logger.error(f"Modify error: {e}")
            return False

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
                    'sl': pos.sl,
                    'tp': pos.tp,
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

    def get_symbol_info(self, symbol: str):
        return mt5.symbol_info(symbol)

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
            if 'XAU' in symbol or 'ETH' in symbol:
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
        self.base_lot = grid_config.get('lot_size', 0.01)
        self.lot_multiplier = 1.5 # Martingale multiplier (DCA Upgrade)
        self.spacing_multiplier = grid_config.get('spacing', 0.4) # Optimized for proximity
        self.max_dca_levels = 10
        self.max_lot_cap = 5.0
        self.batch_size = 5
        self.time_frame_str = "M1" # High-Frequency DCA
        self.state_file = Path("logs/grid_state.json")
        self.strategy = "Grid Both" # Initial default
        self.active_grids = {}
        self._load_state()
        
        self.mode = grid_config.get('mode', 'BOTH')
        self.trigger_threshold = 2
        
        # Mapping for MT5 Timeframes
        self.TIMEFRAME_MAP = {
            "M1": mt5.TIMEFRAME_M1, "M3": mt5.TIMEFRAME_M3, "M5": mt5.TIMEFRAME_M5,
            "M15": mt5.TIMEFRAME_M15, "M30": mt5.TIMEFRAME_M30, "H1": mt5.TIMEFRAME_H1,
            "H4": mt5.TIMEFRAME_H4, "D1": mt5.TIMEFRAME_D1
        }

    def _save_state(self):
        """Save grid progress to file"""
        try:
            self.state_file.parent.mkdir(exist_ok=True)
            with open(self.state_file, 'w') as f:
                json.dump(self.active_grids, f)
        except Exception as e:
            logger.error(f"Failed to save grid state: {e}")

    def _get_dynamic_multiplier(self, atr: float) -> float:
        """DYNAMIC LOT MULTIPLIER (The 'Shock Absorber')"""
        if atr > 3.0: return 1.2  # Survival Mode (High Volatility)
        if atr < 1.5: return 1.6  # Aggressive Mode (Low Volatility)
        return 1.4                # Balanced Default

    def _calculate_martingale_lot(self, index: int, atr: float) -> float:
        """Calculate lot size for DCA level using ATR-driven dynamic multiplier"""
        multiplier = self._get_dynamic_multiplier(atr)
        lot = self.base_lot * (multiplier ** (index - 1))
        return min(round(lot, 2), self.max_lot_cap)

    def _calculate_grid_price(self, base_price: float, index: int, atr: float, direction: str) -> float:
        """Calculate price for k-th DCA level using ATR-based spacing"""
        spacing = atr * self.spacing_multiplier
        offset = spacing * index
        return base_price - offset if direction == 'BUY' else base_price + offset

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
                # DANGEROUS if ADX > 60 (Extremely Strong Trend) OR ATR is 5x normal
                volatility_dangerous = (adx > 60) or (atr > avg_atr_long * 5.0)
                
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
                logger.debug(f"📁 Loaded Grid State from {self.state_file}")
            else:
                self.active_grids = {}
        except json.JSONDecodeError:
            logger.warning("⚠️ Grid state file was corrupt. Starting fresh.")
            self.active_grids = {}
        except Exception as e:
            logger.error(f"Failed to load grid state: {e}")
            self.active_grids = {}

    async def update(self, symbol, current_price, bias, balance):
        """Update grid logic: 1-3-5 Spacing + Individual Breakeven management"""
        if not hasattr(self, '_last_vol_warn'): self._last_vol_warn = {}
        if not hasattr(self, '_last_grid_log'): self._last_grid_log = {}
        
        try:
            # 1. Pre-fetch market conditions and positions
            data = await self._detect_market_condition(symbol)
            positions = self.broker.get_positions()
            symbol_positions = [p for p in positions if p['symbol'] == symbol]
            
            # 2. Status Logging for Basket PnL
            buy_positions = [p for p in symbol_positions if p['type'] == 'BUY' and p.get('magic') == self.magic_buy]
            sell_positions = [p for p in symbol_positions if p['type'] == 'SELL' and p.get('magic') == self.magic_sell]
            total_grid_profit = sum(p['profit'] + p.get('swap', 0) for p in buy_positions + sell_positions)
            
            now_t = time.time()
            if now_t - self._last_grid_log.get(f"{symbol}_pnl", 0) > 30:
                logger.info(f"📊 [Monitor] {symbol} | Price: {current_price:.2f} | Pivot: {data['pivot']:.2f} | ADX: {data['adx']:.1f} | PnL: ${total_grid_profit:.2f}")
                self._last_grid_log[f"{symbol}_pnl"] = now_t

            # 3. Dynamic Bias Selection for GRID_BOTH
            pivot = data['pivot']
            atr = data.get('atr', 1.0)
            
            # BUG FIX: Always define has_active before use (needed for drawdown guard below)
            has_active = len(buy_positions + sell_positions) > 0 or (len(mt5.orders_get(symbol=symbol)) if mt5.orders_get(symbol=symbol) else 0) > 0
            
            if self.mode == "GRID_BOTH":
                if not has_active:
                    if pivot > 0:
                        # Increased sensitivity: 0.1 ATR instead of 0.3
                        if current_price > pivot + (atr * 0.1): 
                            bias = 'BULLISH' # SELL Bias
                        elif current_price < pivot - (atr * 0.1):
                            bias = 'BEARISH' # BUY Bias
                        else:
                            bias = 'BULLISH' if data['trend'] == 'BULLISH' else 'BEARISH'
                        
                        grid_type = 'SELL' if bias == 'BULLISH' else 'BUY'
                        if self.active_grids.get(symbol, {}).get('type') != grid_type:
                            logger.info(f"[Grid Both] Mode Logic -> Biasing {grid_type} based on Price relative to Pivot/Trend.")
                            if symbol not in self.active_grids:
                                self.active_grids[symbol] = {'ict_status': {}}

                            self.active_grids[symbol].update({
                                'type': grid_type, 
                                'last_index': 0,
                                'strategy': self.strategy,
                                'bias': bias,
                                'atr': atr
                            })
                            self._save_state()
                    else:
                        logger.warning(f"⚠️ [Grid] Pivot calculation returned 0 for {symbol}. Check market data.")
                else:
                    # If we have active trades, deduce grid type from positions/orders
                    grid_type = self.active_grids.get(symbol, {}).get('type')
                    if not grid_type:
                        if len(buy_positions) > 0: grid_type = 'BUY'
                        elif len(sell_positions) > 0: grid_type = 'SELL'
                        elif len(mt5.orders_get(symbol=symbol) or []) > 0:
                            pendings = mt5.orders_get(symbol=symbol)
                            if any(o.magic == self.magic_buy for o in pendings): grid_type = 'BUY'
                            elif any(o.magic == self.magic_sell for o in pendings): grid_type = 'SELL'
                    
                    if grid_type:
                        if symbol not in self.active_grids: 
                            self.active_grids[symbol] = {'ict_status': {}}
                            self.active_grids[symbol].update({
                                'type': grid_type, 
                                'last_index': 0,
                                'strategy': self.strategy,
                                'bias': bias,
                                'atr': atr
                            })
                        else:
                            # Keep metadata updated for dashboard
                            self.active_grids[symbol]['strategy'] = self.strategy
                            self.active_grids[symbol]['bias'] = bias
                            self.active_grids[symbol]['atr'] = atr
                        
                        if grid_type == 'BUY': bias = 'BEARISH'
                        elif grid_type == 'SELL': bias = 'BULLISH'
                        self._save_state()

            # 4. Placement Permissions
            can_place_sell = (self.mode == 'SELL_ONLY') or (self.mode == 'GRID_BOTH' and bias == 'BULLISH')
            can_place_buy = (self.mode == 'BUY_ONLY') or (self.mode == 'GRID_BOTH' and bias == 'BEARISH')

            # 5. DRAWDOWN PAUSE LOGIC (The 'Breathing Room')
            equity = mt5.account_info().equity if mt5.account_info() else balance
            drawdown_pct = (balance - equity) / balance if balance > 0 else 0
            
            # Tier 1: Pause NEW separate grids if DD > 5%
            if drawdown_pct > 0.05 and not has_active:
                if now_t - self._last_vol_warn.get(f"{symbol}_new_pause", 0) > 60:
                    logger.warning(f"🛡️ Drawdown Guard (Tier 1): {drawdown_pct*100:.1f}% > 5%. Blocking NEW grids.")
                    self._last_vol_warn[f"{symbol}_new_pause"] = now_t
                return

            # Tier 2: Hard Safety Stop at 15%
            if drawdown_pct > 0.15:
                logger.error(f"🚨 HARD SAFETY STOP: {drawdown_pct*100:.1f}% > 15%. Liquidating all positions.")
                self.broker.close_all_side(symbol, 'BUY')
                self.broker.close_all_side(symbol, 'SELL')
                if symbol in self.active_grids: del self.active_grids[symbol]
                self._save_state()
                return

            # 6. Grid Execution (Martingale DCA Logic with Shock Absorber)
            atr = data.get('atr', 1.0)
            
            for direction in ['BUY', 'SELL']:
                if (direction == 'BUY' and not can_place_buy) or (direction == 'SELL' and not can_place_sell):
                    continue
                
                magic = self.magic_buy if direction == 'BUY' else self.magic_sell
                order_type = mt5.ORDER_TYPE_BUY_LIMIT if direction == 'BUY' else mt5.ORDER_TYPE_SELL_LIMIT
                
                active_pendings = [o for o in (mt5.orders_get(symbol=symbol) or []) if o.magic == magic]
                active_positions = buy_positions if direction == 'BUY' else sell_positions
                total_open = len(active_positions)
                
                # SPREAD FILTER: XAU has naturally wide spreads. Allow up to 50% of ATR.
                symbol_info = mt5.symbol_info(symbol)
                if symbol_info:
                    current_spread = symbol_info.spread * symbol_info.point
                    spread_limit = atr * 0.5 # 50% of ATR - wide enough for XAU
                    if current_spread > spread_limit:
                        if now_t - self._last_vol_warn.get(f"{symbol}_spread", 0) > 30:
                            logger.warning(f"⚠️ Wide Spread Detected ({current_spread:.2f} > {spread_limit:.2f}). Pausing placement.")
                            self._last_vol_warn[f"{symbol}_spread"] = now_t
                        continue

                # DRIFT RESET: If no positions open, keep grid near the market (Save near the price)
                if total_open == 0 and len(active_pendings) > 0:
                    grid_data = self.active_grids.get(symbol, {})
                    old_base = grid_data.get('base_price', current_price)
                    drift = abs(current_price - old_base)
                    # If price drifts more than 1.5x spacing, reset the grid anchor
                    if drift > (atr * self.spacing_multiplier * 1.5):
                        logger.info(f"🔄 Grid Drift Detected ({drift:.2f}). Re-anchoring grid near current market.")
                        self.broker.cancel_all_pendings(symbol)
                        active_pendings = [] # Triggers fresh placement below

                # TRIGGER: No pendings AND space for more layers
                if len(active_pendings) <= self.trigger_threshold and (total_open + len(active_pendings)) < self.max_dca_levels:
                    if not active_pendings and not active_positions:
                        msg = f"🚀 Starting FRESH Martingale DCA {direction} Grid"
                        base_price = current_price
                        start_idx = 1
                    else:
                        msg = f"🔄 Expanding DCA {direction} Grid (Waiting for next level)"
                        base_price = self.active_grids.get(symbol, {}).get('base_price', current_price)
                        start_idx = total_open + len(active_pendings) + 1
                    
                    if start_idx > self.max_dca_levels:
                        continue # Hard level cap hit

                    logger.info(f"{msg} | Level {start_idx} lot size escalation active.")
                    
                    success_count = 0
                    for i in range(start_idx, min(start_idx + self.batch_size, self.max_dca_levels + 1)):
                        entry_price = self._calculate_grid_price(base_price, i, atr, direction)
                        lot_size = self._calculate_martingale_lot(i, atr)
                        
                        # Minimum distance safety
                        if direction == 'BUY' and entry_price > current_price - 0.10: continue
                        if direction == 'SELL' and entry_price < current_price + 0.10: continue
                        
                        res = await self.broker.place_pending_order(symbol, order_type, lot_size, entry_price, magic)
                        if res['success']: 
                            success_count += 1
                        else:
                            logger.error(f"❌ Failed Martingale Level {i} ({lot_size} lots) for {direction}: {res.get('error')}")
                    
                    if success_count > 0:
                        if symbol not in self.active_grids:
                            self.active_grids[symbol] = {'ict_status': {}}

                        self.active_grids[symbol].update({
                            'type': direction,
                            'base_price': base_price,
                            'last_index': start_idx + success_count - 1,
                            'atr': atr
                        })
                        self._save_state()
                        logger.info(f"✅ {success_count} Martingale levels added. Current Max Index: {self.active_grids[symbol]['last_index']}")

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
        self.basket_trailing = {} # {symbol: {direction: {peak: float, active: bool}}}
        
        # Discord Notifier
        self.discord = DiscordNotifier()
        self.last_discord_pulse = 0 # Forces initial update on start
        
        # Symbol Switching State
        self.original_symbols = self.symbols.copy()
        self.market_mode = "DEFAULT" # DEFAULT, WEEKEND_CRYPTO
        
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

    def _manage_symbol_switching(self):
        """Automatic Switcher: XAUUSDm on weekdays, XAUUSDm on weekends"""
        try:
            # Check current day (0=Mon, ..., 5=Sat, 6=Sun)
            now_utc = datetime.utcnow()
            day = now_utc.weekday()
            
            # Weekend Check: Sat and Sun
            is_weekend = day in [5, 6]
            
            # Target Symbol Handling (Check for Gold status if possible)
            gold_sym = "XAUUSDm"
            gold_info = mt5.symbol_info(gold_sym)
            
            # If Gold info is not available or market is closed/weekend
            trade_allowed = False
            if gold_info and gold_info.visible:
                # SYMBOL_TRADE_MODE_FULL = 4
                trade_allowed = (gold_info.trade_mode == 4)
            
            should_be_crypto = is_weekend or not trade_allowed
            
            if should_be_crypto and self.market_mode != "WEEKEND_CRYPTO":
                logger.info(f"🕒 GOLD HOLIDAY/WEEKEND DETECTED. Switching to Bitcoin (XAUUSDm).")
                self.symbols = ["XAUUSDm"]
                self.market_mode = "WEEKEND_CRYPTO"
            elif not should_be_crypto and self.market_mode != "DEFAULT":
                logger.info(f"🕒 GOLD MARKET OPEN. Switching to Gold ({gold_sym}).")
                self.symbols = [gold_sym]
                self.market_mode = "DEFAULT"
                
        except Exception as e:
            logger.error(f"Symbol switching error: {e}")

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
            ai_analysis = await self.ai_brain.analyze_market(symbol, data)
            
            # CRITICAL FIX: Use Real-time Tick Price for Gold instead of candle close to avoid slippage/invalid price
            tick = mt5.symbol_info_tick(symbol)
            if not tick: return
            current_price = tick.bid
            
            bias = ai_analysis.get('bias', 'NEUTRAL')
            self._current_biases[symbol] = bias
            
            # 1. Strategy Mode Routing
            if "Grid" in self.strategy or self.strategy == "Hybrid Mode":
                if "Grid Both" in self.strategy or self.strategy == "Hybrid Mode":
                    self.grid_manager.mode = "GRID_BOTH"
                elif "BUY ONLY" in self.strategy:
                    self.grid_manager.mode = "BUY_ONLY"
                elif "SELL ONLY" in self.strategy:
                    self.grid_manager.mode = "SELL_ONLY"
                else:
                    self.grid_manager.mode = "BOTH"
                self.grid_manager.time_frame_str = self.timeframe

            # 2. Metadata & Dashboard Sync (Ensure symbol exists for Rail Board visibility)
            strategy_to_display = self.strategy
            if self.strategy == "Hybrid Mode":
                strategy_to_display = "HYBRID (Grid+ICT)"
            
            if symbol not in self.grid_manager.active_grids:
                self.grid_manager.active_grids[symbol] = {
                    'strategy': strategy_to_display,
                    'bias': bias,
                    'last_index': 0,
                    'type': 'NEUTRAL'
                }
            
            # Always update Metadata (Dashboard & Sync)
            self.grid_manager.active_grids[symbol]['ict_status'] = ai_analysis.get('ict_status', {})
            self.grid_manager.active_grids[symbol]['strategy'] = strategy_to_display
            self.grid_manager.active_grids[symbol]['bias'] = bias
            self.grid_manager._save_state()

            # A. Grid Update (Only if Grid or Hybrid)
            if "Grid" in self.strategy or self.strategy == "Hybrid Mode":
                await self.grid_manager.update(symbol, current_price, bias, balance)

            # B. ICT Signal Execution (Enabled for Hybrid AND Grid Both to satisfy "Grid is Hybrid" request)
            # Lowered threshold to 0.60 (Score 1.5+) for better entry frequency
            if self.strategy in ["ICT SMC", "Hybrid Mode", "Grid Both"]:
                if ai_analysis['action'] in ['BUY', 'SELL'] and ai_analysis['confidence'] >= 0.60:
                    logger.info(f"🎯 ICT Signal Detected: {ai_analysis['action']} {symbol} (Confidence: {ai_analysis['confidence']:.2f})")
                    
                    # 🔔 DISCORD SIGNAL NOTIFICATION
                    try:
                        await self.discord.send_signal(
                            symbol, 
                            ai_analysis['action'], 
                            ai_analysis['confidence'], 
                            ai_analysis['reasoning'], 
                            ai_analysis.get('entry_price', 0), 
                            ai_analysis.get('take_profit', 0), 
                            ai_analysis.get('stop_loss', 0)
                        )
                    except Exception as de:
                        logger.error(f"Discord signal failed: {de}")

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
            
            # Place order (passing the use_limit flag if present)
            result = self.broker.place_order(
                symbol=symbol,
                action=ai_analysis['action'],
                volume=position_size,
                price=entry_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                use_limit=ai_analysis.get('use_limit', False)
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
        """Monitor and manage open positions with Weighted Average Basket Exit"""
        try:
            positions = self.broker.get_positions()
            if not positions:
                return

            # Group positions by MAGIC (Grid Directions)
            buy_grid = [p for p in positions if p['magic'] == self.grid_manager.magic_buy]
            sell_grid = [p for p in positions if p['magic'] == self.grid_manager.magic_sell]
            
            # Process Basket Exits
            for grid_positions in [buy_grid, sell_grid]:
                if not grid_positions: continue
                
                symbol = grid_positions[0]['symbol']
                direction = 'BUY' if grid_positions[0]['type'] == 'BUY' else 'SELL'
                
                # Calculate Weighted Average Entry Price (WAEP)
                total_volume = sum(p['volume'] for p in grid_positions)
                total_weighted_price = sum(p['price_open'] * p['volume'] for p in grid_positions)
                waep = total_weighted_price / total_volume
                
                # Get current price
                tick = mt5.symbol_info_tick(symbol)
                if not tick: continue
                current_price = tick.bid if direction == 'BUY' else tick.ask
                
                # ADAPTIVE BASKET TP (The 'Elastic Target')
                grid_params = self.grid_manager.active_grids.get(symbol, {})
                atr = grid_params.get('atr', 1.0)
                open_count = len(grid_positions)
                
                if open_count <= 3:
                    # Small Basket: Aim for Profit (Increased for better yield)
                    target_profit_dist = atr * 0.8 # Was 0.5
                    min_profit_target = (total_volume / 0.01) * 3.0 # Was $1.50 -> Now $3.00 per 0.01 lot
                elif open_count <= 5:
                    # Medium Basket: Standard Move
                    target_profit_dist = atr * 0.5 # Was 0.25
                    min_profit_target = (total_volume / 0.01) * 2.0 # Was $1.00 -> Now $2.00 per 0.01 lot
                else:
                    # Heavy Basket: ESCAPE MODE
                    target_profit_dist = atr * 0.1 # Was 0.05
                    min_profit_target = (total_volume / 0.01) * 1.0 # Was $0.50 -> Now $1.00 per 0.01 lot
                
                target_price = waep + target_profit_dist if direction == 'BUY' else waep - target_profit_dist
                
                # Current Basket PnL
                basket_pnl = sum(p['profit'] + p.get('swap', 0) for p in grid_positions)
                
                # BUG FIX: Define is_hit BEFORE trailing block uses it
                is_hit = (direction == 'BUY' and current_price >= target_price) or \
                         (direction == 'SELL' and current_price <= target_price)
                
                # 3.5 TRAILING BASKET PROFIT (Stealth Exit Strategy)
                if symbol not in self.basket_trailing: self.basket_trailing[symbol] = {}
                trailing = self.basket_trailing[symbol].get(direction, {'active': False, 'peak': 0.0})

                should_exit = False
                
                # Trigger point: Price action hit OR USD Profit target hit
                at_target = is_hit or (basket_pnl >= min_profit_target)
                
                if at_target:
                    if not trailing['active']:
                        logger.info(f"✨ TRAILING ACTIVATED for {symbol} {direction} | Initial Target: ${basket_pnl:.2f}")
                        trailing = {'active': True, 'peak': basket_pnl}
                        self.basket_trailing[symbol][direction] = trailing
                        # Update persistent state for dashboard visibility
                        if symbol in self.grid_manager.active_grids:
                            self.grid_manager.active_grids[symbol]['is_trailing'] = True
                            self.grid_manager._save_state()
                    
                    # Update Peak
                    if basket_pnl > trailing['peak']:
                        trailing['peak'] = basket_pnl
                        self.basket_trailing[symbol][direction] = trailing
                    
                    # Exit condition: 15% pullback from peak, but never below 50% of original target
                    trail_level = trailing['peak'] * 0.85
                    floor_level = min_profit_target * 0.5
                    
                    if basket_pnl < trail_level or basket_pnl < floor_level:
                        logger.info(f"💰 TRAILING EXIT: {symbol} {direction} | PnL: ${basket_pnl:.2f} | Peak: ${trailing['peak']:.2f}")
                        should_exit = True
                    else:
                        # Log significant jumps (Marketing/Visual feedback)
                        if basket_pnl > trailing['peak'] * 0.98 and basket_pnl > min_profit_target * 1.1:
                            if time.time() % 30 < 1: # Log occasionally
                                logger.info(f"🚀 Trailing Profit for {symbol} {direction}: ${basket_pnl:.2f} (Target was ${min_profit_target:.1f})")
                        continue # STILL TRAILING - DO NOT EXIT
                else:
                    # If we were trailing but it dropped back to target floor
                    if trailing['active'] and basket_pnl < min_profit_target * 0.5:
                        logger.warning(f"⚠️ Trailing Safety Floor Hit: Closing {symbol} {direction} at ${basket_pnl:.2f}")
                        should_exit = True

                if should_exit:
                    logger.info(f"🎯 BASKET EXIT ({'ESCAPE' if open_count > 5 else 'PROFIT'}) triggered for {symbol} {direction} | PnL: ${basket_pnl:.2f} | Open: {open_count}")
                    
                    # 1. Close all positions in the basket
                    for p in grid_positions:
                        self.broker.close_position(symbol, p['ticket'])
                    
                    # 2. Cancel ALL pending orders for this grid
                    orders = mt5.orders_get(symbol=symbol)
                    if orders:
                        magic = self.grid_manager.magic_buy if direction == 'BUY' else self.grid_manager.magic_sell
                        for o in orders:
                            if o.magic == magic:
                                mt5.order_send({"action": mt5.TRADE_ACTION_REMOVE, "order": o.ticket})
                    
                    # 3. Clear Grid State
                    if symbol in self.grid_manager.active_grids:
                        del self.grid_manager.active_grids[symbol]
                        self.grid_manager._save_state()
                    
                    # 4. Clear Trailing State
                    if symbol in self.basket_trailing and direction in self.basket_trailing[symbol]:
                        del self.basket_trailing[symbol][direction]
                    
                    logger.info(f"✅ {direction} Grid Reset Complete.")
                    
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
                # 🕒 DISCORD HOURLY HEARTBEAT
                now = time.time()
                
                # 🔄 AUTOMATIC SYMBOL SWITCHER (Check every cycle)
                self._manage_symbol_switching()

                if now - self.last_discord_pulse >= 3600:
                    acc = mt5.account_info()
                    if acc:
                        pos = self.broker.get_positions()
                        daily_pnl = acc.balance - self.start_balance
                        if await self.discord.send_heartbeat(acc, daily_pnl, self.trades_today, len(pos)):
                            logger.info("📩 Hourly Discord Performance report sent.")
                        self.last_discord_pulse = now

                # Core Monitoring
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
                        last_bias = self._current_biases.get(symbol)
                        if last_bias: # Only update if we have an initial bias from main analyzer
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
    print("  [2]  ICT SMC          - AI Trend Following")
    print("  [3]  HYBRID MODE      - Run Grid + ICT Simultaneously")
    print("  " + "-" * 45)
    
    strategy = "Grid Both"
    while True:
        choice = input("  >> Choice (1-3): ").strip()
        if choice == "1":
            strategy = "Grid Both"
            print(f"\n  [OK] Strategy Selected: GRID BOTH (Center Pivot + ATR/ADX Filter)\n")
            break
        if choice == "2":
            strategy = "ICT SMC"
            print(f"\n  [OK] Strategy Selected: ICT SMC (AI Trend Following)\n")
            break
        if choice == "3":
            strategy = "Hybrid Mode"
            print(f"\n  [OK] Strategy Selected: HYBRID MODE (Dynamic Grid + AI Signal Scaling)\n")
            break
        print("  [!] Invalid choice. Please enter 1-3.")

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
    """Helper to launch the dashboard safely and return the process handle"""
    try:
        # Create a trigger file to signal trading is active
        trigger_file = Path("logs/trading_active.lock")
        trigger_file.parent.mkdir(exist_ok=True)
        trigger_file.touch()

        print("\n  [>>] Launching Live Dashboard in background...")
        import subprocess
        script_dir = os.path.dirname(os.path.abspath(__file__))
        dashboard_path = os.path.join(script_dir, "live_dashboard.py")
        proc = subprocess.Popen([sys.executable, dashboard_path],
                         creationflags=0x08100000 if os.name == 'nt' else 0, # Added CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP
                         close_fds=True)
        print(f"  [OK] Dashboard launched successfully (PID: {proc.pid}).\n")
        return proc
    except Exception as e:
        print(f"  [ERR] Failed to launch dashboard: {e}\n")
        return None

def main():
    """Main function - CLI mode"""
    try:
        # --- SECURITY CHECK ---
        security = SecurityManager()
        if not security.is_authorized():
            if not security.prompt_activation():
                print("  [!] Activation failed. Exiting.")
                return

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
        dashboard_proc = launch_dashboard()
        
        # Run trading loop
        asyncio.run(trading_system.run())
        
    except KeyboardInterrupt:
        logger.info("Application interrupted by user")
    except Exception as e:
        logger.error(f"Application error: {e}")
    finally:
        # CLEANUP: Kill dashboard and remove lock file
        trigger_file = Path("logs/trading_active.lock")
        if trigger_file.exists():
            try: trigger_file.unlink()
            except: pass
            
        if dashboard_proc:
            try:
                print("\n  [>>] Closing Dashboard...")
                dashboard_proc.terminate()
                # Optional: Force kill if terminate fails after short wait
                # dashboard_proc.wait(timeout=3)
            except:
                pass
        
        # Close Discord session
        try:
            if hasattr(trading_system, 'discord'):
                asyncio.run(trading_system.discord.close())
        except:
            pass

        logger.info("👋 System shutdown complete.")

if __name__ == "__main__":
    main()
