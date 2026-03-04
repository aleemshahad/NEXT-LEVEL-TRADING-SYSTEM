import MetaTrader5 as mt5

def detect_center_pivot(symbol, timeframe=mt5.TIMEFRAME_M5, lookback=20):
    """
    Calculates the Center Pivot (Mean) based on High/Low of last N candles.
    Returns a dictionary with High, Low, and Pivot.
    """
    try:
        rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, lookback)
        if rates is not None and len(rates) > 0:
            h20 = max([r['high'] for r in rates])
            l20 = min([r['low'] for r in rates])
            pivot = (h20 + l20) / 2
            
            return {
                'success': True,
                'high': h20,
                'low': l20,
                'pivot': pivot,
                'current_price': rates[-1]['close']
            }
        return {'success': False, 'error': 'No data'}
    except Exception as e:
        return {'success': False, 'error': str(e)}

def get_grid_direction(current_price, pivot):
    """
    Returns the appropriate grid direction based on Center Pivot logic.
    """
    if pivot <= 0: return 'NEUTRAL'
    
    if current_price > pivot:
        return 'SELL'  # Revert to Mean from High
    elif current_price < pivot:
        return 'BUY'   # Revert to Mean from Low
    else:
        return 'NEUTRAL'

if __name__ == "__main__":
    # Test logic
    if mt5.initialize():
        result = detect_center_pivot("XAUUSDm")
        if result['success']:
            direction = get_grid_direction(result['current_price'], result['pivot'])
            print(f"--- Center Pivot Indicator ---")
            print(f"Symbol: XAUUSDm")
            print(f"High: {result['high']}")
            print(f"Low: {result['low']}")
            print(f"Pivot (Center): {result['pivot']}")
            print(f"Current Price: {result['current_price']}")
            print(f"Recommended Side: {direction}")
        mt5.shutdown()
