import asyncio
import json
import os
import time
import requests
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional
from loguru import logger
import MetaTrader5 as mt5
import numpy as np
import pandas as pd


class TradingBrain:
    """AI Trading Brain with G-Channel, 20-Candle OHLC Momentum, and Async News Filtering."""

    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        self.memories: List[Dict] = []
        self.model_trained = False
        self.confidence_threshold = float(self.config.get("confidence_threshold", 0.6))
        self.sentiment_decision = "ALLOW"

        # News / Calendar Cache
        self._ff_events: List[Dict] = []
        self._last_ff_download: float = 0.0
        self._cache_file = Path("logs/ff_calendar_cache.json")

        # Risk Modifier
        self.risk_modifier = float(self.config.get("risk_modifier", 1.0))

        self._load_memories()

    def _get_market_timestamp(self, symbol: Optional[str] = None) -> datetime:
        """Returns current broker server time in UTC, falling back to system UTC."""
        try:
            test_symbols = [symbol] if symbol else ["XAUUSD", "XAUUSDc", "EURUSD", "BTCUSD"]
            for sym in filter(None, test_symbols):
                tick = mt5.symbol_info_tick(sym)
                if tick and tick.time > 0:
                    return datetime.fromtimestamp(tick.time, timezone.utc)
        except Exception as e:
            logger.debug(f"Failed to get broker tick time: {e}")
        return datetime.now(timezone.utc)

    async def _update_calendar_cache_async(self) -> None:
        """Asynchronously refreshes the Forex Factory calendar if cache expired."""
        now_t = time.time()
        if self._ff_events and (now_t - self._last_ff_download < 3600):
            return

        # 1. Try local file cache (valid for 6 hours)
        if self._cache_file.exists() and (now_t - self._cache_file.stat().st_mtime < 21600):
            try:
                with open(self._cache_file, "r") as f:
                    self._ff_events = json.load(f)
                    self._last_ff_download = now_t
                    return
            except Exception as e:
                logger.warning(f"Failed to read news cache file: {e}")

        # 2. Asynchronously download fresh calendar
        url = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
        try:
            events = await asyncio.to_thread(self._fetch_calendar_sync, url)
            if events:
                self._ff_events = events
                self._last_ff_download = now_t

                self._cache_file.parent.mkdir(parents=True, exist_ok=True)
                with open(self._cache_file, "w") as f:
                    json.dump(events, f)
                logger.info(f"[FF News] Refreshed {len(self._ff_events)} economic events.")
        except Exception as e:
            logger.warning(f"[FF News] Calendar download failed (using memory cache): {e}")

    @staticmethod
    def _fetch_calendar_sync(url: str) -> List:
        """Synchronous Forex Factory calendar download (runs in a worker thread)."""
        try:
            resp = requests.get(url, timeout=6)
            if resp.status_code == 200:
                return resp.json() or []
        except Exception:
            pass
        return []

    async def check_news_block(self, symbol: Optional[str] = None) -> bool:
        """
        Evaluates active news impact window for USD high-impact events.
        Returns True if trading should be BLOCKED.
        """
        try:
            await self._update_calendar_cache_async()
            if not self._ff_events:
                self.sentiment_decision = "ALLOW"
                return False

            now_utc = self._get_market_timestamp(symbol)
            pre_block_min = int(self.config.get("news", {}).get("block_window_min", 30))
            post_block_min = max(15, pre_block_min // 2)

            blocking_event = None
            blocking_event_time = None

            for event in self._ff_events:
                if event.get("currency") == "USD" and "High" in event.get("impact", ""):
                    date_str = event.get("date", "")
                    if len(date_str) < 19:
                        continue
                    try:
                        # Parse naive datetime and explicitly attach UTC timezone
                        parsed_dt = datetime.strptime(date_str[:19], "%Y-%m-%dT%H:%M:%S")
                        event_time = parsed_dt.replace(tzinfo=timezone.utc)

                        diff_minutes = (event_time - now_utc).total_seconds() / 60.0
                        if -post_block_min <= diff_minutes <= pre_block_min:
                            blocking_event = event.get("title")
                            blocking_event_time = event_time
                            break
                    except ValueError:
                        continue

            if blocking_event:
                if self.sentiment_decision != "BLOCK":
                    logger.warning(
                        f"🚫 [NEWS BLOCK] USD High-Impact Event: '{blocking_event}' at {blocking_event_time.strftime('%H:%M UTC')}"
                    )
                self.sentiment_decision = "BLOCK"
                return True

            self.sentiment_decision = "ALLOW"
            return False

        except Exception as e:
            logger.error(f"Error checking news impact: {e}")
            self.sentiment_decision = "ALLOW"
            return False

    def _add_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculates G-Channel lines and dynamic high/low support-resistance bands."""
        try:
            lookback = 20
            division_factor = 2.6
            gLength = 100

            closes = df["close"].values
            n = len(closes)

            # Dynamic Support & Resistance levels
            df["hl_high"] = df["high"].rolling(lookback).max()
            df["hl_low"] = df["low"].rolling(lookback).min()
            price_range = df["hl_high"] - df["hl_low"]
            divided_range = price_range / division_factor

            df["buy_level"] = df["hl_low"] - divided_range
            df["sell_level"] = df["hl_high"] + divided_range
            df["divided_range"] = divided_range

            # Recursive G-Channel Calculation
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

            # Crossover evaluation
            crossup = np.zeros(n, dtype=bool)
            crossdn = np.zeros(n, dtype=bool)
            for i in range(1, n):
                crossup[i] = (b[i - 1] < closes[i - 1]) and (b[i] >= closes[i])
                crossdn[i] = (a[i - 1] > closes[i - 1]) and (a[i] <= closes[i])

            # Trend Persistence State
            last_dn = 999999
            last_up = 999999
            bullish = np.zeros(n, dtype=bool)

            for i in range(n):
                last_dn = 0 if crossdn[i] else last_dn + 1
                last_up = 0 if crossup[i] else last_up + 1
                bullish[i] = last_dn <= last_up

            df["gchannel_bullish"] = bullish
            return df
        except Exception as e:
            logger.error(f"Error adding indicators: {e}")
            return df

    def _detect_ohlc_trend(self, df: pd.DataFrame, lookback: int = 20) -> str:
        """Determines price momentum direction using structural higher highs / lower lows."""
        try:
            if len(df) < lookback + 1:
                return "NEUTRAL"

            recent = df.iloc[-lookback:]
            highs = recent["high"].values
            lows = recent["low"].values
            closes = recent["close"].values
            opens = recent["open"].values

            higher_highs = np.sum(highs[1:] > highs[:-1])
            lower_lows = np.sum(lows[1:] < lows[:-1])
            bullish_candles = np.sum(closes[1:] > opens[1:])
            bearish_candles = np.sum(closes[1:] < opens[1:])

            bullish_score = higher_highs + bullish_candles
            bearish_score = lower_lows + bearish_candles

            if bullish_score > bearish_score + 1:
                return "BULLISH"
            elif bearish_score > bullish_score + 1:
                return "BEARISH"
            return "NEUTRAL"
        except Exception as e:
            logger.error(f"OHLC trend detection error: {e}")
            return "NEUTRAL"

    async def analyze_market(self, symbol: str, data: pd.DataFrame) -> Dict:
        """Runs indicator analysis, price action evaluation, and news gating."""
        try:
            if len(data) < 50:
                return {"action": "HOLD", "bias": "NEUTRAL", "confidence": 0.0, "reasoning": "Insufficient data"}

            df = self._add_indicators(data.copy())
            idx = len(df) - 1

            gchannel_bullish = bool(df["gchannel_bullish"].iloc[idx])
            gchannel_bullish_prev = bool(df["gchannel_bullish"].iloc[idx - 1]) if idx > 0 else gchannel_bullish
            ltf_trend = self._detect_ohlc_trend(df.iloc[: idx + 1], lookback=20)

            buy_level = float(df["buy_level"].iloc[idx])
            sell_level = float(df["sell_level"].iloc[idx])
            hl_high = float(df["hl_high"].iloc[idx])
            hl_low = float(df["hl_low"].iloc[idx])
            current_price = float(df["close"].iloc[idx])

            gchannel_buy_sig = gchannel_bullish and not gchannel_bullish_prev
            gchannel_sell_sig = not gchannel_bullish and gchannel_bullish_prev

            action = "HOLD"
            bias = "NEUTRAL"
            confidence = 0.0
            entry_plan = "SCAN"
            reason = "No structural setup detected"

            # Plan 1: Momentum Breakout
            if gchannel_buy_sig and ltf_trend == "BULLISH":
                action, bias, confidence, entry_plan = "BUY", "BULLISH", 0.90, "BREAKOUT"
                reason = "Breakout BUY: G-Channel Bullish Flip + OHLC Alignment"
            elif gchannel_sell_sig and ltf_trend == "BEARISH":
                action, bias, confidence, entry_plan = "SELL", "BEARISH", 0.90, "BREAKOUT"
                reason = "Breakout SELL: G-Channel Bearish Flip + OHLC Alignment"

            # Plan 2: Mean-Reversion Pullback inside Channel
            elif gchannel_bullish and (buy_level <= current_price <= hl_low):
                action, bias, confidence, entry_plan = "BUY", "BULLISH", 0.80, "PULLBACK"
                reason = "Pullback BUY: Channel Support Re-test"
            elif not gchannel_bullish and (hl_high <= current_price <= sell_level):
                action, bias, confidence, entry_plan = "SELL", "BEARISH", 0.80, "PULLBACK"
                reason = "Pullback SELL: Channel Resistance Re-test"

            # Plan 3: Trend Continuation Scalp
            elif gchannel_bullish and ltf_trend == "BULLISH":
                action, bias, confidence, entry_plan = "BUY", "BULLISH", 0.70, "RANGE_SCALP"
                reason = "Scalp BUY: Bullish G-Channel + Momentum"
            elif not gchannel_bullish and ltf_trend == "BEARISH":
                action, bias, confidence, entry_plan = "SELL", "BEARISH", 0.70, "RANGE_SCALP"
                reason = "Scalp SELL: Bearish G-Channel + Momentum"

            take_profit = sell_level if action == "BUY" else (buy_level if action == "SELL" else 0.0)

            # Check Economic News Impact Window
            if await self.check_news_block(symbol):
                return {
                    "action": "HOLD",
                    "bias": bias,
                    "confidence": 0.0,
                    "reasoning": "NEWS BLOCK: Active USD High-Impact Window",
                    "ict_status": {"status": "NEWS BLOCK"},
                }

            return {
                "action": action,
                "bias": bias,
                "confidence": confidence,
                "reasoning": reason,
                "entry_price": current_price,
                "use_limit": False,
                "stop_loss": 0.0,
                "take_profit": take_profit,
                "ict_status": {
                    "trend": "BULLISH" if gchannel_bullish else "BEARISH",
                    "mode": entry_plan,
                    "ltf_trend": ltf_trend,
                },
                "risk_modifier": self.risk_modifier,
            }

        except Exception as e:
            logger.error(f"Market analysis error on {symbol}: {e}", exc_info=True)
            return {"action": "HOLD", "bias": "NEUTRAL", "confidence": 0.0, "reasoning": "Analysis Exception"}

    def remember_trade(self, trade_data: Dict) -> None:
        """Stores trade metadata using ISO timestamps for JSON serialization safety."""
        self.memories.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "symbol": trade_data.get("symbol"),
            "action": trade_data.get("action"),
            "pnl": float(trade_data.get("pnl", 0.0)),
            "success": float(trade_data.get("pnl", 0.0)) > 0,
        })
        if len(self.memories) > 1000:
            self.memories = self.memories[-1000:]

    def _load_memories(self) -> None:
        """Loads historical trade logs from disk."""
        try:
            memory_file = Path("models/ai_memories.json")
            if memory_file.exists() and memory_file.stat().st_size > 0:
                with open(memory_file, "r") as f:
                    self.memories = json.load(f)
                self.model_trained = bool(self.memories)
                logger.debug(f"🧠 Loaded {len(self.memories)} trade memories.")
        except Exception as e:
            logger.warning(f"Could not load memory file: {e}")