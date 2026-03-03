import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import threading
import time
from typing import Dict, List, Optional
from loguru import logger

# Reuse logic from ICT Auditor if possible, but keep engine standalone for speed
class LiquidityEngine:
    def __init__(self, symbol="XAUUSDm"):
        self.symbol = symbol
        self.timeframes = {
            "M1": mt5.TIMEFRAME_M1,
            "M3": mt5.TIMEFRAME_M3,
            "M5": mt5.TIMEFRAME_M5,
            "M10": mt5.TIMEFRAME_M10,
            "M15": mt5.TIMEFRAME_M15,
            "M30": mt5.TIMEFRAME_M30
        }
        self.liquidity_data = {}
        self.running = False
        self._lock = threading.Lock()

    def start(self):
        self.running = True
        self.thread = threading.Thread(target=self._update_loop, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False

    def _update_loop(self):
        while self.running:
            try:
                new_data = {}
                for tf_name, tf_val in self.timeframes.items():
                    levels = self._get_levels(tf_val)
                    if levels:
                        new_data[tf_name] = levels
                
                with self._lock:
                    self.liquidity_data = new_data
                
                time.sleep(2) # Update every 2 seconds
            except Exception as e:
                logger.error(f"Liquidity Engine Error: {e}")
                time.sleep(5)

    def _get_levels(self, timeframe):
        rates = mt5.copy_rates_from_pos(self.symbol, timeframe, 0, 100)
        if rates is None or len(rates) == 0:
            return None
        
        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        
        # Simple Swing Point Detection (3-bar fractal)
        highs = []
        lows = []
        
        for i in range(2, len(df) - 2):
            high_val = float(df.iloc[i]['high'])
            low_val = float(df.iloc[i]['low'])
            t_val = df.iloc[i]['time']
            
            # Swing High (BSL)
            if df.iloc[i]['high'] > df.iloc[i-1]['high'] and df.iloc[i]['high'] > df.iloc[i-2]['high'] and \
               df.iloc[i]['high'] > df.iloc[i+1]['high'] and df.iloc[i]['high'] > df.iloc[i+2]['high']:
                
                # Check if grabbed by any LATER candle in the same window
                grabbed = False
                for j in range(i + 1, len(df)):
                    if df.iloc[j]['high'] > high_val:
                        grabbed = True
                        break
                highs.append({'price': high_val, 'time': t_val, 'grabbed': grabbed})
            
            # Swing Low (SSL)
            if df.iloc[i]['low'] < df.iloc[i-1]['low'] and df.iloc[i]['low'] < df.iloc[i-2]['low'] and \
               df.iloc[i]['low'] < df.iloc[i+1]['low'] and df.iloc[i]['low'] < df.iloc[i+2]['low']:
                
                # Check if grabbed
                grabbed = False
                for j in range(i + 1, len(df)):
                    if df.iloc[j]['low'] < low_val:
                        grabbed = True
                        break
                lows.append({'price': low_val, 'time': t_val, 'grabbed': grabbed})
        
        # Fair Value Gaps
        fvgs = []
        for i in range(2, len(df)):
            # Bullish FVG
            if df.iloc[i-2]['high'] < df.iloc[i]['low'] and df.iloc[i-1]['close'] > df.iloc[i-1]['open']:
                fvgs.append({
                    'type': 'bullish',
                    'top': float(df.iloc[i]['low']),
                    'bottom': float(df.iloc[i-2]['high']),
                    'time': df.iloc[i-1]['time'],
                    'formation_end_time': df.iloc[i]['time'],
                    'mitigated': False
                })
            # Bearish FVG
            elif df.iloc[i-2]['low'] > df.iloc[i]['high'] and df.iloc[i-1]['close'] < df.iloc[i-1]['open']:
                fvgs.append({
                    'type': 'bearish',
                    'top': float(df.iloc[i-2]['low']),
                    'bottom': float(df.iloc[i]['high']),
                    'time': df.iloc[i-1]['time'],
                    'formation_end_time': df.iloc[i]['time'],
                    'mitigated': False
                })
                
        # Check Mitigation
        for fvg in fvgs:
            formation_end_time = fvg['formation_end_time']
            # Look at all price action strictly AFTER the FVG was completely formed (after 3rd candle)
            subsequent_price_action = df[df['time'] > formation_end_time]
            for _, row in subsequent_price_action.iterrows():
                if fvg['type'] == 'bullish':
                    # Bullish FVG mitigated if price drops *below* the top of the FVG (entering it)
                    # We consider it fully mitigated if it sweeps below the bottom, but for visual 
                    # purposes touching the FVG top or going inside marks it as mitigated
                    if row['low'] <= fvg['top']:
                        fvg['mitigated'] = True
                        fvg['mitigated_time'] = row['time']
                        break
                elif fvg['type'] == 'bearish':
                    # Bearish FVG mitigated if price rises *above* the bottom of the FVG (entering it)
                    if row['high'] >= fvg['bottom']:
                        fvg['mitigated'] = True
                        fvg['mitigated_time'] = row['time']
                        break

        # Filter out older mitigated FVGs to keep chart clean, keep recent ones
        active_fvgs = [f for f in fvgs if not f.get('mitigated', False)]
        mitigated_fvgs = [f for f in fvgs if f.get('mitigated', False)][-3:] # Keep only last 3 mitigated
        
        final_fvgs = active_fvgs + mitigated_fvgs
        # Sort by time
        final_fvgs = sorted(final_fvgs, key=lambda x: x['time'])

        return {
            'bsl': sorted(highs, key=lambda x: x['price'], reverse=True)[:5],
            'ssl': sorted(lows, key=lambda x: x['price'])[:5],
            'fvg': final_fvgs[-10:],
            'current_price': float(df.iloc[-1]['close']),
            'ohlc': df[['time', 'open', 'high', 'low', 'close', 'tick_volume']].tail(50).to_dict('records')
        }

    def get_prediction(self):
        with self._lock:
            if not self.liquidity_data:
                return None
            
            # Use M15 as primary for move prediction
            m15 = self.liquidity_data.get('M15')
            if not m15: return None
            
            curr = m15['current_price']
            nearest_bsl = min([h['price'] for h in m15['bsl']], key=lambda x: abs(x-curr)) if m15['bsl'] else None
            nearest_ssl = min([l['price'] for l in m15['ssl']], key=lambda x: abs(x-curr)) if m15['ssl'] else None
            
            # Simple Move Potential Logic
            # Distance to nearest liquidity pool
            dist_up = (nearest_bsl - curr) if nearest_bsl else 0
            dist_down = (curr - nearest_ssl) if nearest_ssl else 0
            
            # Prediction: Which one is closer or has more "magnetic" pull?
            # For now: Closer target is likely move.
            if dist_up > 0 and (dist_up < dist_down or dist_down == 0):
                direction = "BULLISH"
                pips = dist_up * 10 if "XAU" in self.symbol else dist_up * 10000
                potential = pips # Relative move in pips/points
            elif dist_down > 0:
                direction = "BEARISH"
                pips = dist_down * 10 if "XAU" in self.symbol else dist_down * 10000
                potential = pips
            else:
                direction = "NEUTRAL"
                potential = 0
                
            return {
                'direction': direction,
                'potential_move': potential,
                'nearest_bsl': nearest_bsl,
                'nearest_ssl': nearest_ssl
            }

if __name__ == "__main__":
    # Test
    if not mt5.initialize():
        print("MT5 Init Failed")
        exit()
    
    engine = LiquidityEngine("XAUUSDm")
    engine.start()
    time.sleep(5)
    print(engine.get_prediction())
    engine.stop()
    mt5.shutdown()
