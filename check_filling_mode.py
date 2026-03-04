import MetaTrader5 as mt5
import sys

def diagnose():
    if not mt5.initialize():
        print("MT5 initialization failed")
        return

    symbol = "XAUUSDm"
    info = mt5.symbol_info(symbol)
    if info is None:
        print(f"Symbol {symbol} not found")
        mt5.shutdown()
        return

    print(f"Symbol: {symbol}")
    print(f"Filling mode value: {info.filling_mode}")
    
    # Check flags (typical bitmask values)
    if info.filling_mode & 1:
        print("Supported: FOK (Fill or Kill)")
    if info.filling_mode & 2:
        print("Supported: IOC (Immediate or Cancel)")
    if info.filling_mode & 4:
        print("Supported: BOC (Book or Cancel)")
        
    mt5.shutdown()

if __name__ == "__main__":
    diagnose()
