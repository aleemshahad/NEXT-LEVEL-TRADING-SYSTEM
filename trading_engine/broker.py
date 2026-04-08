import asyncio
import os
import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime
from loguru import logger
from typing import Dict, List

class MT5Broker:
    """MetaTrader 5 Broker Interface"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.connected = False
        
    async def connect(self) -> bool:
        """Connect to MT5 with robust retries and session clearing"""
        try:
            mt5.shutdown()
            await asyncio.sleep(1)
            
            terminal_path = r"C:\Users\Next\AppData\Roaming\MetaTrader 5 EXNESS\terminal64.exe"
            
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
                
            login = self.config.get('login') or int(os.getenv('MT5_LOGIN', 0))
            password = self.config.get('password') or os.getenv('MT5_PASSWORD')
            server = self.config.get('server') or os.getenv('MT5_SERVER')
            
            logger.info(f"Logging into {server} (Account: {login})...")
            if login and password and server:
                if not mt5.login(login, password=password, server=server):
                    logger.error(f"MT5 login failed: {mt5.last_error()}")
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
            acc = mt5.account_info()
            if acc is None:
                self.connected = False
                return False
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
            tf_map = {
                "M1":  mt5.TIMEFRAME_M1, "M3":  mt5.TIMEFRAME_M3, "M5":  mt5.TIMEFRAME_M5,
                "M15": mt5.TIMEFRAME_M15, "M30": mt5.TIMEFRAME_M30, "H1":  mt5.TIMEFRAME_H1,
                "H4":  mt5.TIMEFRAME_H4, "D1":  mt5.TIMEFRAME_D1
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
            logger.error(f"Error getting market data: {e}"); return pd.DataFrame()
    
    async def place_pending_order(self, symbol: str, order_type: int, volume: float, price: float, magic: int) -> Dict:
        """Place a pending limit order"""
        try:
            symbol_info = mt5.symbol_info(symbol)
            if not symbol_info: return {'success': False, 'error': f'Symbol {symbol} not found'}
            price = self.round_price(symbol, price)
            request = {
                "action": mt5.TRADE_ACTION_PENDING, "symbol": symbol, "volume": volume,
                "type": order_type, "price": price, "magic": magic,
                "comment": "GRID_ENTRY", "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_RETURN,
            }
            result = mt5.order_send(request)
            if result.retcode != mt5.TRADE_RETCODE_DONE:
                return {'success': False, 'error': f'Code {result.retcode}: {result.comment}'}
            return {'success': True, 'ticket': result.order}
        except Exception as e: return {'success': False, 'error': str(e)}

    def cancel_all_pendings(self, symbol: str):
        """Cancel pending orders (specific or ALL)"""
        try:
            if symbol == "ALL":
                orders = mt5.orders_get() # All symbols
            else:
                orders = mt5.orders_get(symbol=symbol)
            if orders is None: return
            for o in orders:
                request = {"action": mt5.TRADE_ACTION_REMOVE, "order": o.ticket}
                mt5.order_send(request)
            logger.info(f"🧹 Cleaned pending orders for {symbol}")
        except Exception as e: logger.error(f"Error canceling pendings: {e}")

    def close_all_side(self, symbol: str, side: str, magic: int = None):
        """Close all positions for a specific side (BUY/SELL)"""
        try:
            positions = mt5.positions_get(symbol=symbol)
            if not positions: return
            for p in positions:
                pos_side = 'BUY' if p.type == mt5.POSITION_TYPE_BUY else 'SELL'
                if pos_side == side and (magic is None or p.magic == magic):
                    self.close_position(symbol, p.ticket)
        except Exception as e: logger.error(f"Error closing side {side}: {e}")

    def close_position(self, symbol: str, ticket: int) -> bool:
        """Close a specific position by ticket"""
        try:
            position = mt5.positions_get(ticket=ticket)
            if not position: return False
            p = position[0]
            action = mt5.ORDER_TYPE_SELL if p.type == mt5.POSITION_TYPE_BUY else mt5.ORDER_TYPE_BUY
            tick = mt5.symbol_info_tick(symbol)
            if tick is None: return False
            price = tick.bid if p.type == mt5.POSITION_TYPE_BUY else tick.ask
            request = {
                "action": mt5.TRADE_ACTION_DEAL, "symbol": symbol, "volume": p.volume,
                "type": action, "position": p.ticket, "price": price,
                "deviation": 200, "magic": p.magic, "comment": "CLOSE_POSITION",
                "type_time": mt5.ORDER_TIME_GTC, "type_filling": mt5.ORDER_FILLING_IOC,
            }
            result = mt5.order_send(request)
            return result.retcode == mt5.TRADE_RETCODE_DONE
        except Exception as e: logger.error(f"Error closing position {ticket}: {e}"); return False

    def place_order(self, symbol: str, action: str, volume: float, price: float, 
                   stop_loss: float = None, take_profit: float = None,
                   use_limit: bool = False, magic: int = 234000) -> Dict:
        """Place trading order (Market or Limit)"""
        try:
            symbol_info = mt5.symbol_info(symbol)
            if not symbol_info: return {'success': False, 'error': f'Symbol {symbol} not found'}
            if use_limit:
                trade_action = mt5.TRADE_ACTION_PENDING
                order_type = mt5.ORDER_TYPE_BUY_LIMIT if action == "BUY" else mt5.ORDER_TYPE_SELL_LIMIT
                filling_type = mt5.ORDER_FILLING_RETURN
            else:
                trade_action = mt5.TRADE_ACTION_DEAL
                order_type = mt5.ORDER_TYPE_BUY if action == "BUY" else mt5.ORDER_TYPE_SELL
                filling_type = mt5.ORDER_FILLING_IOC
            price = self.round_price(symbol, price)
            if stop_loss: stop_loss = self.round_price(symbol, stop_loss)
            if take_profit: take_profit = self.round_price(symbol, take_profit)
            request = {
                "action": trade_action, "symbol": symbol, "volume": volume,
                "type": order_type, "price": price, "deviation": 20, "magic": magic,
                "comment": "ICT_SMC_TRADE" if magic == 234000 else "GRID_DCA", 
                "type_time": mt5.ORDER_TIME_GTC, "type_filling": filling_type,
            }
            if stop_loss: request["sl"] = stop_loss
            if take_profit: request["tp"] = take_profit
            result = mt5.order_send(request)
            if result.retcode != mt5.TRADE_RETCODE_DONE: return {'success': False, 'error': f'Order failed: {result.retcode}'}
            logger.info(f"Order placed: {action} {volume} {symbol} at {price} (Magic: {magic})")
            return {'success': True, 'ticket': result.order, 'price': result.price, 'volume': result.volume}
        except Exception as e: logger.error(f"Order placement error: {e}"); return {'success': False, 'error': str(e)}
    
    def modify_sl_tp(self, ticket: int, sl: float = 0.0, tp: float = 0.0) -> bool:
        """Modify SL/TP for an open position"""
        try:
            request = {"action": mt5.TRADE_ACTION_SLTP, "position": ticket, "sl": sl, "tp": tp}
            result = mt5.order_send(request)
            return result.retcode == mt5.TRADE_RETCODE_DONE
        except Exception as e: logger.error(f"Modify error: {e}"); return False

    def get_positions(self) -> List[Dict]:
        """Get open positions"""
        try:
            positions = mt5.positions_get()
            if not positions: return []
            return [
                {
                    'ticket': p.ticket, 'symbol': p.symbol, 'type': 'BUY' if p.type == mt5.POSITION_TYPE_BUY else 'SELL',
                    'volume': p.volume, 'price_open': p.price_open, 'price_current': p.price_current,
                    'sl': p.sl, 'tp': p.tp, 'profit': p.profit, 'swap': p.swap, 'magic': p.magic,
                    'time': datetime.fromtimestamp(p.time)
                } for p in positions
            ]
        except Exception as e: logger.error(f"Error getting positions: {e}"); return []

    def get_symbol_info(self, symbol: str):
        return mt5.symbol_info(symbol)

    def round_price(self, symbol: str, price: float) -> float:
        """Round price to valid symbol digits"""
        try:
            info = mt5.symbol_info(symbol)
            return round(price, info.digits) if info else round(price, 2)
        except: return price
