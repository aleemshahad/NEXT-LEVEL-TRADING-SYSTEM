import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime, timedelta

def check_mt5():
    if not mt5.initialize():
        print(f"MT5 initialize() failed, error code = {mt5.last_error()}")
        quit()

    print("MT5 initialized successfully")
    
    # Check account info
    account_info = mt5.account_info()
    if account_info:
        print(f"Account: {account_info.login}, Server: {account_info.server}")
    else:
        print("Failed to get account info")

    # Check some symbols
    symbols = ["BTCUSDm", "BTCUSD", "XAUUSDm", "XAUUSD", "EURUSDm", "EURUSD"]
    for sym in symbols:
        info = mt5.symbol_info(sym)
        if info is None:
            print(f"Symbol '{sym}' not found")
        else:
            if not info.visible:
                print(f"Symbol '{sym}' found but not visible in MarketWatch. Attempting to select...")
                if not mt5.symbol_select(sym, True):
                    print(f"Failed to select '{sym}'")
                else:
                    print(f"'{sym}' is now visible")
            else:
                print(f"Symbol '{sym}' is found and visible")

    # Check data for BTCUSDm
    sym = "BTCUSDm"
    if mt5.symbol_info(sym):
        start = datetime.now() - timedelta(days=7)
        end = datetime.now()
        rates = mt5.copy_rates_range(sym, mt5.TIMEFRAME_M5, start, end)
        if rates is not None and len(rates) > 0:
            print(f"Successfully fetched {len(rates)} bars for {sym}")
        else:
            print(f"Failed to fetch data for {sym}. Error: {mt5.last_error()}")

    mt5.shutdown()

if __name__ == "__main__":
    check_mt5()
