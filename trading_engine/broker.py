from dotenv import load_dotenv
import asyncio
import os
import time
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
            try:
                from dotenv import load_dotenv
                load_dotenv()
            except Exception:
                pass
            login = self.config.get('login') or int(os.getenv('MT5_LOGIN', 0))
            password = self.config.get('password') or os.getenv('MT5_PASSWORD')
            server = self.config.get('server') or os.getenv('MT5_SERVER')
            terminal_path = os.getenv('MT5_TERMINAL_PATH', r"C:\Program Files\MetaTrader 5\terminal64.exe")

            # Check if MT5 is already running and connected
            if mt5.terminal_info() is not None:
                acc = mt5.account_info()
                if acc and (not login or acc.login == login):
                    logger.info(f"✅ Connection already active on Account #{acc.login} ({acc.server}) - Balance: ${acc.balance:.2f}")
                    self.connected = True
                    return True

            # Initialize terminal
            init_success = False
            for attempt in range(3):
                logger.info(f"Connecting to MT5 terminal (Attempt {attempt+1}/3)...")
                if mt5.initialize(path=terminal_path) or mt5.initialize():
                    init_success = True
                    break
                time.sleep(1)

            if not init_success:
                logger.error(f"❌ MT5 initialization failed: {mt5.last_error()}")
                return False

            # If login credentials provided, perform login
            if login and password and server:
                if not mt5.login(login, password=password, server=server):
                    acc = mt5.account_info()
                    if acc and acc.login == login:
                        logger.info(f"Terminal already logged into account #{login}")
                    else:
                        logger.error(f"❌ MT5 login failed: {mt5.last_error()}")
                        return False
            else:
                acc = mt5.account_info()
                if acc and acc.login > 0:
                    logger.info(f"✅ Attached to active terminal session on Account #{acc.login}")
                else:
                    logger.warning("⚠️ No MT5 credentials configured, continuing with active session")

            self.connected = True
            acc = mt5.account_info()
            if acc:
                logger.info(f"✅ Connected to MT5 - Account #{acc.login} | Balance: ${acc.balance:.2f}")
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
            mt5.symbol_select(symbol, True)
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

    def close_partial(self, symbol: str, ticket: int, volume: float) -> bool:
        """Close a slice of a position, falling back to a full close when the slice is too small"""
        try:
            position = mt5.positions_get(ticket=ticket)
            if not position: return False
            p = position[0]
            info = mt5.symbol_info(symbol)
            if not info: return False
            vmin = info.volume_min or 0.01
            slice_vol = self.normalize_volume(symbol, volume)
            if slice_vol >= p.volume - vmin + 1e-8 or (p.volume - slice_vol) < vmin:
                return self.close_position(symbol, ticket)
            action = mt5.ORDER_TYPE_SELL if p.type == mt5.POSITION_TYPE_BUY else mt5.ORDER_TYPE_BUY
            tick = mt5.symbol_info_tick(symbol)
            if tick is None: return False
            price = tick.bid if p.type == mt5.POSITION_TYPE_BUY else tick.ask
            request = {
                "action": mt5.TRADE_ACTION_DEAL, "symbol": symbol, "volume": slice_vol,
                "type": action, "position": p.ticket, "price": price,
                "deviation": 200, "magic": p.magic, "comment": "ICT_TP_SLICE",
                "type_time": mt5.ORDER_TIME_GTC, "type_filling": mt5.ORDER_FILLING_IOC,
            }
            result = mt5.order_send(request)
            if result.retcode != mt5.TRADE_RETCODE_DONE:
                logger.error(f"Partial close failed #{ticket}: {result.retcode} {result.comment}")
                return False
            logger.info(f"Partial close #{ticket}: {slice_vol} @ {price} (left {round(p.volume - slice_vol, 8)})")
            return True
        except Exception as e:
            logger.error(f"Error partially closing #{ticket}: {e}")
            return False

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
            request = {
                "action": trade_action, "symbol": symbol, "volume": volume,
                "type": order_type, "price": price, "deviation": 20, "magic": magic,
                "comment": "ICT_SMC_TRADE" if magic == 234000 else "GRID_DCA",
                "type_time": mt5.ORDER_TIME_GTC, "type_filling": filling_type,
            }
            # FIX #3: Explicit validation — `if stop_loss:` was falsy for 0.0
            if stop_loss is not None and stop_loss > 0:
                request["sl"] = self.round_price(symbol, stop_loss)
            if take_profit is not None and take_profit > 0:
                request["tp"] = self.round_price(symbol, take_profit)
            result = mt5.order_send(request)
            if result.retcode != mt5.TRADE_RETCODE_DONE: return {'success': False, 'error': f'Order failed: {result.retcode}'}
            logger.info(f"Order placed: {action} {volume} {symbol} at {price} (Magic: {magic})")
            position_ticket = getattr(result, 'position', 0) or result.order
            return {'success': True, 'ticket': position_ticket, 'order': result.order, 'price': result.price, 'volume': result.volume}
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

    def normalize_volume(self, symbol: str, volume: float) -> float:
        """Clamp volume to the symbol's min/max and align it to volume_step"""
        try:
            info = mt5.symbol_info(symbol)
            if not info: return volume
            vmin = info.volume_min or 0.01
            vmax = info.volume_max or vmin
            step = info.volume_step or 0.01
            volume = max(vmin, min(vmax, volume))
            steps = int(round(volume / step))
            return round(max(1, steps) * step, 8)
        except Exception:
            return volume
