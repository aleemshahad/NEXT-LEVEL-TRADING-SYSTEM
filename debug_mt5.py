import MetaTrader5 as mt5
import os
import time
from dotenv import load_dotenv

load_dotenv()

def debug_mt5():
    # Force shutdown any previous sessions
    mt5.shutdown()
    time.sleep(1)
    
    # Attempt to initialize with retries
    success = False
    for i in range(3):
        print(f"Connection attempt {i+1}/3...")
        terminal_path = os.getenv("MT5_TERMINAL_PATH", r"C:\Program Files\MetaTrader 5 EXNESS\terminal64.exe")
        if mt5.initialize(path=terminal_path):
            success = True
            break
        time.sleep(1)
    
    if not success:
        print(f"All initialization attempts failed: {mt5.last_error()}")
        return
    
    print("✅ MT5 Initialized Successfully!")

    # Check if we are already logged in manually
    acc = mt5.account_info()
    if acc:
        print(f"\nCURRENT TERMINAL LOGIN:")
        print(f"  Account: {acc.login}")
        print(f"  Server: {acc.server}")
        print(f"  Balance: {acc.balance}")
        
        target_login = int(os.getenv('MT5_LOGIN', 0))
        if acc.login == target_login:
            print("\n🎉 You are already logged into the CORRECT account manually!")
            return # No need to login again
    else:
        print("\nTerminal is NOT currently logged into any account.")

    login = int(os.getenv('MT5_LOGIN', 0))
    password = os.getenv('MT5_PASSWORD')
    server = os.getenv('MT5_SERVER')
    
    print(f"\nAttempting logic-based login to {server} with account {login}...")
    
    if not mt5.login(login, password=password, server=server):
        print(f"Login failed: {mt5.last_error()}")
        print("\nPossible reasons:")
        print("1. Incorrect Login ID / Password")
        print("2. Wrong Server Name (Verify in Exness Dashboard)")
        print("3. Account Expired")
    else:
        print("Login SUCCESS!")
        acc = mt5.account_info()
        print(f"Account Balance: {acc.balance if acc else 'N/A'}")

    mt5.shutdown()

if __name__ == "__main__":
    debug_mt5()
