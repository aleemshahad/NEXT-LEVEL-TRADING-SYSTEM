import MetaTrader5 as mt5
mt5.initialize()
pos = mt5.positions_get()
if not pos:
    print("No open positions")
else:
    for p in pos:
        t = "BUY" if p.type == 0 else "SELL"
        print(f"{p.symbol} | type={t} | vol={p.volume} | open={p.price_open} | current={p.price_current} | profit={p.profit:.2f} | magic={p.magic}")
acc = mt5.account_info()
if acc:
    dd = (acc.balance - acc.equity) / acc.balance * 100
    print(f"\nBalance={acc.balance:.2f} Equity={acc.equity:.2f} Drawdown={dd:.2f}% MarginLevel={acc.margin_level:.1f}%")
mt5.shutdown()
