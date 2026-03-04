import MetaTrader5 as mt5
import pandas as pd
import os
import asyncio
from typing import Dict, List, Optional
from loguru import logger
import time

class MT5Broker:
    """MetaTrader 5 Broker Interface"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.connected = False
        
    async def connect(self, login: int = None, password: str = None, server: str = None) -> bool:
        """Connect to MT5 with robust retries and session clearing"""
        try:
            # Force close any hung sessions first
            mt5.shutdown()
            await asyncio.sleep(1)
            
            terminal_path = os.getenv("MT5_TERMINAL_PATH", r"C:\Program Files\MetaTrader 5 EXNESS\terminal64.exe")
            
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
                
            # Login with credentials
            login = login or self.config.get('login') or int(os.getenv('MT5_LOGIN', 0))
            password = password or self.config.get('password') or os.getenv('MT5_PASSWORD')
            server = server or self.config.get('server') or os.getenv('MT5_SERVER')
            
            logger.info(f"Logging into {server} (Account: {login})...")
            if login and password and server:
                if not mt5.login(login, password=password, server=server):
                    logger.error(f"MT5 login failed: {mt5.last_error()}")
                    # Fail-safe: Check if we are already logged in to this account
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
            # Check account info as a heartbeat
            acc = mt5.account_info()
            if acc is None:
                self.connected = False
                return False
            # Check terminal connection status
            terminal = mt5.terminal_info()
            if terminal and not terminal.connected:
                self.connected = False
                return False
            self.connected = True
            return True
        except:
            self.connected = False
            return False

    async def is_market_open(self, symbol: str) -> bool:
        """Check if market is currently open for trading"""
        try:
            mt5.symbol_select(symbol, True)
            info = mt5.symbol_info(symbol)
            if not info: return False
            
            # 1. Check if trading is disabled by broker
            if info.trade_mode == mt5.SYMBOL_TRADE_MODE_DISABLED:
                return False
                
            # 2. Weekend Check (Standard for Forex/Gold)
            # 5 = Saturday, 6 = Sunday
            from datetime import datetime
            if datetime.now().weekday() >= 5:
                # Except for Crypto which trades 24/7
                if not any(x in symbol.upper() for x in ['BTC', 'ETH', 'SOL', 'CRYPTO']):
                    return False
            
            return True
        except:
            return False

    def get_market_data(self, symbol: str, timeframe: str = "M5", count: int = 500) -> pd.DataFrame:
        """Get market data from MT5"""
        try:
            mt5.symbol_select(symbol, True)
            # Map timeframe
            tf_map = {
                "M1": mt5.TIMEFRAME_M1,
                "M5": mt5.TIMEFRAME_M5,
                "M15": mt5.TIMEFRAME_M15,
                "H1": mt5.TIMEFRAME_H1,
                "H4": mt5.TIMEFRAME_H4,
                "D1": mt5.TIMEFRAME_D1
            }
            
            timeframe_mt5 = tf_map.get(timeframe, mt5.TIMEFRAME_H1)
            rates = mt5.copy_rates_from_pos(symbol, timeframe_mt5, 0, count)
            
            if rates is None or len(rates) == 0:
                logger.warning(f"No data received for {symbol}")
                return pd.DataFrame()
                
            df = pd.DataFrame(rates)
            df['time'] = pd.to_datetime(df['time'], unit='s')
            df.set_index('time', inplace=True)
            
            return df
            
        except Exception as e:
            logger.error(f"Error getting market data: {e}")
            return pd.DataFrame()
    
    async def _send_with_retry(self, request: Dict, max_retries: int = 50) -> Optional[object]:
        """Send order with infinite-like retry for rejections (10006)"""
        for i in range(max_retries):
            result = mt5.order_send(request)
            if result is None:
                logger.error("Critial Error: mt5.order_send returned None")
                await asyncio.sleep(1)
                continue

            # Success
            if result.retcode == mt5.TRADE_RETCODE_DONE:
                return result

            if result.retcode in [10006, 10027]:
                if i == 0:  # Log only once per order attempt — no spam
                    logger.warning(f"⚠️ Order queued (code {result.retcode}). Retrying silently...")
                # 10027 = Too Many Requests — keep sleep minimal for fast execution
                delay = 0.1 if result.retcode == 10027 else 0.01
                await asyncio.sleep(delay)
                continue
            
            # Terminal Errors (Balance, Invalid Price handled by caller, etc.)
            return result

        return None  # All retries exhausted

    async def place_pending_order(self, symbol: str, order_type: int, volume: float, price: float, magic: int) -> Dict:
        """Place a pending limit order with retry logic"""
        try:
            symbol_info = mt5.symbol_info(symbol)
            if not symbol_info:
                return {'success': False, 'error': f'Symbol {symbol} not found'}
            
            # Round price
            tick_size = getattr(symbol_info, 'trade_tick_size', 0.0)
            if tick_size > 0:
                price = round(round(price / tick_size) * tick_size, symbol_info.digits)
            else:
                price = round(price, symbol_info.digits)
            
            request = {
                "action": mt5.TRADE_ACTION_PENDING,
                "symbol": symbol,
                "volume": volume,
                "type": order_type,
                "price": price,
                "magic": magic,
                "comment": "GRID_ENTRY",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": self._get_filling_mode(symbol),
            }
            
            result = await self._send_with_retry(request)
            if result is None:
                return {'success': False, 'error': 'Connection Lost'}
                
            # Auto-Retry for INVALID_PRICE (Stop Level violation)
            if result.retcode == 10015:
                logger.warning(f"⚠️ INVALID_PRICE for {symbol} at {price}. Applying buffer and retrying...")
                # Apply a small buffer (0.5 points) away from market to clear Stop Level
                buffer = 0.5 if order_type in [mt5.ORDER_TYPE_BUY_LIMIT, mt5.ORDER_TYPE_SELL_STOP] else -0.5
                request["price"] -= buffer
                result = await self._send_with_retry(request)

            if result is None:
                return {'success': False, 'error': 'Connection Lost after retry'}
            if result.retcode in [mt5.TRADE_RETCODE_MARKET_CLOSED, 10044, 10017, 10018]:
                return {'success': False, 'error': 'MARKET_CLOSED', 'retcode': result.retcode}
            
            if result.retcode != mt5.TRADE_RETCODE_DONE:
                logger.error(f"❌ Order Final Failure for {symbol}: Code {result.retcode}, Comment: {result.comment}")
                return {'success': False, 'error': f'Code {result.retcode}: {result.comment}', 'retcode': result.retcode}
            
            return {'success': True, 'ticket': result.order}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    async def cancel_order(self, ticket: int) -> bool:
        """Cancel an individual pending order"""
        try:
            request = {
                "action": mt5.TRADE_ACTION_REMOVE,
                "order": ticket
            }
            result = await self._send_with_retry(request)
            if result and result.retcode == mt5.TRADE_RETCODE_DONE:
                logger.info(f"🗑️ Order {ticket} canceled successfully.")
                return True
            else:
                logger.error(f"Failed to cancel order {ticket}: {result.retcode if result else 'No Result'}")
                return False
        except Exception as e:
            logger.error(f"Error canceling individual order {ticket}: {e}")
            return False

    async def cancel_all_pendings(self, symbol: str, magic: Optional[int] = None):
        """Cancel pending orders for a specific symbol in PARALLEL"""
        try:
            orders = mt5.orders_get(symbol=symbol)
            if orders is None: return
            
            tasks = []
            for o in orders:
                if magic is not None and o.magic != magic:
                    continue
                    
                request = {
                    "action": mt5.TRADE_ACTION_REMOVE,
                    "order": o.ticket
                }
                tasks.append(self._send_with_retry(request))
            
            if tasks:
                await asyncio.gather(*tasks)
            
            filter_str = f" (Magic: {magic})" if magic else ""
            logger.info(f"🧹 Cleaned pending orders for {symbol}{filter_str}")
        except Exception as e:
            logger.error(f"Error canceling pendings: {e}")

    async def close_all_side(self, symbol: str, side: str, magic: int = None):
        """Close all positions of a specific side in PARALLEL for speed"""
        try:
            raw_positions = mt5.positions_get(symbol=symbol)
            if raw_positions is None: return
            
            target_type = mt5.POSITION_TYPE_BUY if side == 'BUY' else mt5.POSITION_TYPE_SELL
            
            # Fetch tick ONCE for all positions to minimize latency
            tick = mt5.symbol_info_tick(symbol)
            if not tick:
                logger.error(f"Failed to fetch tick for {symbol}. Cannot close positions.")
                return

            tasks = []
            for p in raw_positions:
                if p.type == target_type and (magic is None or p.magic == magic):
                    close_price = tick.bid if p.type == mt5.POSITION_TYPE_BUY else tick.ask
                    request = {
                        "action": mt5.TRADE_ACTION_DEAL,
                        "position": p.ticket,
                        "symbol": symbol,
                        "volume": p.volume,
                        "type": mt5.ORDER_TYPE_SELL if p.type == mt5.POSITION_TYPE_BUY else mt5.ORDER_TYPE_BUY,
                        "price": close_price,
                        "deviation": 100, # Increased deviation (1.00 for Gold) to accept slippage and avoid rejections
                        "magic": p.magic,
                        "comment": "PARALLEL_CLOSE",
                        "type_time": mt5.ORDER_TIME_GTC,
                        "type_filling": self._get_filling_mode(symbol),
                    }
                    tasks.append(self._send_with_retry(request))
            
            if tasks:
                logger.info(f"⚡ Closing {len(tasks)} {side} positions in parallel for {symbol}...")
                await asyncio.gather(*tasks)
        except Exception as e:
            logger.error(f"Error closing side {side}: {e}")

    def place_order(self, symbol: str, action: str, volume: float, price: float, 
                   stop_loss: float = None, take_profit: float = None) -> Dict:
        """Place trading order (Synchronous wrapper for async retry)"""
        # Note: Since this is synchronous and used in some sync contexts, we do a basic retry loop
        try:
            order_type = mt5.ORDER_TYPE_BUY if action == "BUY" else mt5.ORDER_TYPE_SELL
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": symbol,
                "volume": volume,
                "type": order_type,
                "price": price,
                "deviation": 20,
                "magic": 234000,
                "comment": "NEXT_LEVEL_BRAIN",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": self._get_filling_mode(symbol),
            }
            if stop_loss: request["sl"] = stop_loss
            if take_profit: request["tp"] = take_profit
            
            # Fast sync retry loop
            for i in range(10):
                result = mt5.order_send(request)
                if result is None:
                    time.sleep(0.01) # 10ms
                    continue
                if result.retcode == mt5.TRADE_RETCODE_DONE:
                    return {'success': True, 'ticket': result.order, 'price': result.price, 'volume': result.volume}
                if result.retcode in [10006, 10027, 10044]:
                    time.sleep(0.01) # 10ms
                    continue
                break

            return {'success': False, 'error': f'Order failed: {result.retcode if result else "Internal Error"}'}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    async def place_market_order(self, symbol: str, action: str, volume: float,
                                  stop_loss: float = None, take_profit: float = None) -> Dict:
        """Place a market order asynchronously (for ICT SMC strategy)"""
        try:
            tick = mt5.symbol_info_tick(symbol)
            if not tick:
                return {'success': False, 'error': 'No tick data'}
            
            order_type = mt5.ORDER_TYPE_BUY if action == "BUY" else mt5.ORDER_TYPE_SELL
            price = tick.ask if action == "BUY" else tick.bid
            
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": symbol,
                "volume": volume,
                "type": order_type,
                "price": price,
                "deviation": 20,
                "magic": 234000,
                "comment": "NEXT_LEVEL_BRAIN",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": self._get_filling_mode(symbol),
            }
            if stop_loss: request["sl"] = stop_loss
            if take_profit: request["tp"] = take_profit
            
            result = await self._send_with_retry(request)
            if result is None:
                return {'success': False, 'error': 'Connection Lost'}
            if result.retcode == mt5.TRADE_RETCODE_DONE:
                return {'success': True, 'ticket': result.order, 'price': result.price, 'volume': result.volume}
            return {'success': False, 'error': f'Code {result.retcode}: {result.comment}'}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    async def close_position(self, ticket: int) -> Dict:
        """Close an individual position with retry"""
        try:
            positions = mt5.positions_get(ticket=ticket)
            if not positions:
                return {'success': False, 'error': f'Position {ticket} not found'}
            
            pos = positions[0]
            action = mt5.ORDER_TYPE_SELL if pos.type == mt5.POSITION_TYPE_BUY else mt5.ORDER_TYPE_BUY
            price = mt5.symbol_info_tick(pos.symbol).bid if pos.type == mt5.POSITION_TYPE_BUY else mt5.symbol_info_tick(pos.symbol).ask
            
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": pos.symbol,
                "volume": pos.volume,
                "type": action,
                "position": pos.ticket,
                "price": price,
                "deviation": 50,
                "magic": pos.magic,
                "comment": "CLOSE_INDIVIDUAL",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": self._get_filling_mode(pos.symbol),
            }
            
            result = await self._send_with_retry(request)
            if result is None:
                return {'success': False, 'error': 'Connection Lost'}
            if result.retcode != mt5.TRADE_RETCODE_DONE:
                return {'success': False, 'error': f'Code {result.retcode}: {result.comment}'}
            
            return {'success': True, 'ticket': ticket}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def get_positions(self) -> List[Dict]:
        """Get open positions"""
        try:
            positions = mt5.positions_get()
            if not positions:
                return []
                
            return [
                {
                    'ticket': pos.ticket,
                    'symbol': pos.symbol,
                    'type': 'BUY' if pos.type == mt5.POSITION_TYPE_BUY else 'SELL',
                    'volume': pos.volume,
                    'price_open': pos.price_open,
                    'price_current': pos.price_current,
                    'profit': pos.profit,
                    'swap': pos.swap,
                    'commission': getattr(pos, 'commission', 0.0),
                    'magic': pos.magic,
                    'time': pd.to_datetime(pos.time, unit='s')
                }
                for pos in positions
            ]
            
        except Exception as e:
            logger.error(f"Error getting positions: {e}")
            return []

    def get_available_slots(self) -> int:
        """Calculate available order slots based on broker limits"""
        try:
            acc = mt5.account_info()
            if not acc: return 0
            
            # Most brokers have a limit (e.g. 1024 or 200)
            limit = getattr(acc, 'limit_orders', 1000)
            if limit == 0: limit = 1000 # Safety
            
            orders = mt5.orders_get()
            orders_count = len(orders) if orders else 0
            
            positions = mt5.positions_get()
            pos_count = len(positions) if positions else 0
            
            total_active = orders_count + pos_count
            available = limit - total_active
            
            return max(0, available)
        except Exception as e:
            logger.error(f"Error getting available slots: {e}")
            return 0

    def _get_filling_mode(self, symbol: str) -> int:
        """Detect correct filling mode for the symbol/broker"""
        try:
            symbol_info = mt5.symbol_info(symbol)
            if not symbol_info:
                return mt5.ORDER_FILLING_IOC
            
            filling_mode = symbol_info.filling_mode
            if filling_mode & mt5.SYMBOL_FILLING_FOK:
                return mt5.ORDER_FILLING_FOK
            elif filling_mode & mt5.SYMBOL_FILLING_IOC:
                return mt5.ORDER_FILLING_IOC
            else:
                return mt5.ORDER_FILLING_RETURN
        except:
            return mt5.ORDER_FILLING_IOC

    def get_active_magic_numbers(self) -> set:
        """Layer 4 Helper: Return all unique magic numbers from live MT5 positions."""
        try:
            positions = mt5.positions_get()
            if not positions:
                return set()
            return {p.magic for p in positions}
        except:
            return set()
