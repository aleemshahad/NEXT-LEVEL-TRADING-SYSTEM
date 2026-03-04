import MetaTrader5 as mt5
import sys
import os

print(f"Python: {sys.version}")
print(f"MT5: {mt5.__version__}")

terminal_path = r"C:\Program Files\MetaTrader 5 EXNESS\terminal64.exe"
print(f"Trying to initialize with path: {terminal_path}")
if mt5.initialize(path=terminal_path):
    print("Success with path!")
    acc = mt5.account_info()
    if acc:
        print(f"Account: {acc.login}")
    else:
        print("Failed to get account info, trying login...")
        login = int(os.getenv("MT5_LOGIN", 260338499))
        password = os.getenv("MT5_PASSWORD", "sV*HRkC8QH7_!7V")
        server = os.getenv("MT5_SERVER", "Exness-MT5Trial15")
        if mt5.login(login, password=password, server=server):
             print("Logged in successfully!")
        else:
             print(f"Login failed: {mt5.last_error()}")
    mt5.shutdown()
else:
    print(f"Failed with path: {mt5.last_error()}")

print("\nTrying to initialize without path...")
if mt5.initialize():
    print("Success without path!")
    mt5.shutdown()
else:
    print(f"Failed without path: {mt5.last_error()}")
