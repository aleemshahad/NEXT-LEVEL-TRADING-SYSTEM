import sys
import os
import time
import asyncio
import json
import yaml
import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
from loguru import logger
from typing import Dict, List

# Core Trading Engine Components
from trading_engine.notifications import DiscordNotifier
from trading_engine.security import SecurityManager
from trading_engine.trading_brain import TradingBrain
from trading_engine.ict_analyzer import ICTAnalyzer
from trading_engine.broker import MT5Broker
from trading_engine.risk import RiskManager
from trading_engine.grid_manager import GridManager

# Configure logger
logger.remove()
logger.add(sys.stderr, level="INFO", format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{message}</cyan>")
logger.add("logs/live_trading_{time:YYYY-MM-DD}.log", rotation="00:00", level="DEBUG")

class LiveTradingSystem:
    """Main Live Trading System"""
    
    def __init__(self, config_path: str = "config.yaml"):
        self.config = self._load_config(config_path)
        self.broker = MT5Broker(self.config.get('mt5', {}))
        self.ai_brain = TradingBrain(self.config) # Updated to pass config
        self.ict_analyzer = ICTAnalyzer()
        self.risk_manager = RiskManager(self.config.get('risk', {}))
        self.grid_manager = GridManager(self.broker, self.config)
        
        self.running = False
        self.symbols = self.config.get('symbols', ['XAUUSDc'])
        self.timeframe = self.config.get('timeframe', 'M15')
        self.strategy = "ICT SMC"
        
        self.trades_today = 0
        self.daily_pnl = 0.0
        self.reset_timestamp = self._load_reset_time()
        self.trade_history = []
        self.reports_dir = Path("logs/live_reports")
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        self.session_max_drawdown = 0.0
        self._current_biases = {}
        self.basket_trailing = {}
        
        self.discord = DiscordNotifier()
        self.last_discord_pulse = 0
        self.market_mode = "DEFAULT"
        self.start_time = datetime.now() # Season Timer Initialization

    def _save_reset_time(self, timestamp):
        try:
            config_file = Path("logs/reset_config.json")
            config_file.parent.mkdir(exist_ok=True)
            with open(config_file, 'w') as f:
                json.dump({'reset_timestamp': timestamp}, f)
        except Exception as e:
            logger.error(f"Failed to save reset config: {e}")

    def _load_reset_time(self):
        try:
            config_file = Path("logs/reset_config.json")
            if config_file.exists():
                with open(config_file, 'r') as f:
                    return json.load(f).get('reset_timestamp', 0)
        except Exception as e:
            logger.warning(f"Failed to load reset config: {e}")
        return 0

    def _reload_settings(self):
        """Update settings from config.yaml without restart"""
        try:
            config_file = Path("config.yaml")
            if not config_file.exists(): return
            mtime = config_file.stat().st_mtime
            if not hasattr(self, '_last_config_mtime') or mtime > self._last_config_mtime:
                logger.info("♻️ Hot Reloading Config...")
                new_config = self._load_config("config.yaml")
                if new_config:
                    self.config = new_config
                    # Update active settings (only update symbols if not forced into weekend mode)
                    if self.market_mode == "DEFAULT":
                        self.symbols = self.config.get('symbols', self.symbols)
                    self.timeframe = self.config.get('timeframe', self.timeframe)
                    self.strategy = self.config.get('strategy', self.strategy)
                    
                    # Update risk and grid controllers
                    self.risk_manager.__init__(self.config.get('risk', {}))
                    self.grid_manager.config = self.config
                    
                    self._last_config_mtime = mtime
                    logger.info(f"✅ Settings Updated: Symbols: {self.symbols} | Strategy: {self.strategy}")
        except Exception as e:
            logger.debug(f"Reload error: {e}")

    def _manage_symbol_switching(self):
        """Automatic Switcher for weekends/holidays"""
        try:
            now_utc = datetime.utcnow()
            day = now_utc.weekday()
            is_weekend = day in [5, 6]
            
            # Use configured symbols as primary reference
            primary_syms = self.config.get('symbols', ['XAUUSDm'])
            gold_ref = primary_syms[0]
            
            gold_info = mt5.symbol_info(gold_ref)
            trade_allowed = gold_info.trade_mode == 4 if gold_info else False
            should_be_crypto = is_weekend or not trade_allowed
            
            if should_be_crypto and self.market_mode != "WEEKEND_CRYPTO":
                logger.info(f"🕒 GOLD HOLIDAY/WEEKEND DETECTED. Switching to BTC/Crypto mode.")
                # Try to use BTCUSDm, fallback to initial config if not found
                self.symbols = ["BTCUSDm"] if mt5.symbol_info("BTCUSDm") else primary_syms
                self.market_mode = "WEEKEND_CRYPTO"
            elif not should_be_crypto and self.market_mode != "DEFAULT":
                logger.info(f"🕒 GOLD MARKET OPEN. Switching back to {primary_syms}.")
                self.symbols = primary_syms
                self.market_mode = "DEFAULT"
        except Exception as e:
            logger.error(f"Symbol switching error: {e}")

    def _load_config(self, config_path: str) -> Dict:
        try:
            if Path(config_path).exists():
                with open(config_path, 'r', encoding='utf-8') as f:
                    return yaml.safe_load(f)
            return {'symbols': ['XAUUSDc'], 'timeframe': 'M5', 'risk': {'max_risk_per_trade': 0.02, 'max_daily_loss': 0.05, 'max_drawdown': 0.15}}
        except Exception as e:
            logger.error(f"Config loading error: {e}"); return {}
    
    async def initialize(self) -> bool:
        try:
            logger.info("🧠 Initializing NEXT LEVEL BRAIN Live Trading System...")
            if not await self.broker.connect(): return False
            acc = mt5.account_info()
            if acc:
                self.start_balance = acc.balance
                logger.info(f"Account Balance: ${self.start_balance:.2f}")
            for symbol in self.symbols: self.broker.cancel_all_pendings(symbol)
            logger.info("✅ System initialized successfully")
            return True
        except Exception as e:
            logger.error(f"Initialization error: {e}"); return False
    
    async def analyze_and_trade(self, symbol: str):
        try:
            acc = mt5.account_info()
            if not acc: return
            data = self.broker.get_market_data(symbol, self.timeframe, 100)
            if data.empty: return
            ai_analysis = await self.ai_brain.analyze_market(symbol, data)
            tick = mt5.symbol_info_tick(symbol)
            if not tick: return
            current_price = tick.bid
            bias = ai_analysis.get('bias', 'NEUTRAL')
            self._current_biases[symbol] = bias
            
            if "Grid" in self.strategy or self.strategy == "Hybrid Mode":
                if "Grid Both" in self.strategy or self.strategy == "Hybrid Mode": self.grid_manager.mode = "GRID_BOTH"
                elif "BUY ONLY" in self.strategy: self.grid_manager.mode = "BUY_ONLY"
                elif "SELL ONLY" in self.strategy: self.grid_manager.mode = "SELL_ONLY"
                else: self.grid_manager.mode = "BOTH"
                self.grid_manager.time_frame_str = self.timeframe
                self.grid_manager.strategy = self.strategy

            display_strat = "HYBRID (Grid+ICT)" if self.strategy == "Hybrid Mode" else self.strategy
            if symbol not in self.grid_manager.active_grids:
                self.grid_manager.active_grids[symbol] = {'strategy': display_strat, 'bias': bias, 'last_index': 0, 'type': 'NEUTRAL'}
            self.grid_manager.active_grids[symbol]['ict_status'] = ai_analysis.get('ict_status', {})
            self.grid_manager.active_grids[symbol]['strategy'] = display_strat
            self.grid_manager.active_grids[symbol]['bias'] = bias
            self.grid_manager._save_state()

            if "Grid" in self.strategy or self.strategy == "Hybrid Mode":
                await self.grid_manager.update(symbol, current_price, bias, acc.balance)

            if self.strategy in ["ICT SMC", "Hybrid Mode", "Grid Both"]:
                if ai_analysis['action'] in ['BUY', 'SELL'] and ai_analysis['confidence'] >= 0.60:
                    logger.info(f"🎯 ICT Signal: {ai_analysis['action']} {symbol} (Conf: {ai_analysis['confidence']:.2f})")
                    try:
                        await self.discord.send_signal(symbol, ai_analysis['action'], ai_analysis['confidence'], ai_analysis['reasoning'], ai_analysis.get('entry_price', 0), ai_analysis.get('take_profit', 0), ai_analysis.get('stop_loss', 0))
                    except: pass
                    await self._execute_trade(symbol, ai_analysis)
        except Exception as e: logger.error(f"Analysis error for {symbol}: {e}")
    
    async def _execute_trade(self, symbol: str, ai_analysis: Dict):
        try:
            acc = mt5.account_info()
            if not acc: return
            drawdown = max(0, (self.start_balance - acc.balance) / self.start_balance) if self.start_balance else 0
            if not self.risk_manager.check_risk_limits(acc.balance, drawdown): return
            size = self.risk_manager.calculate_position_size(acc.balance, ai_analysis['entry_price'], ai_analysis['stop_loss'], symbol)
            res = self.broker.place_order(symbol=symbol, action=ai_analysis['action'], volume=size, price=ai_analysis['entry_price'], stop_loss=ai_analysis['stop_loss'], take_profit=ai_analysis['take_profit'], use_limit=ai_analysis.get('use_limit', False))
            if res['success']:
                self.trades_today += 1
                self.ai_brain.remember_trade({'symbol': symbol, 'action': ai_analysis['action'], 'entry_price': ai_analysis['entry_price'], 'confidence': ai_analysis['confidence']})
        except Exception as e: logger.error(f"Trade execution error: {e}")
    
    async def monitor_positions(self):
        """Monitor positions with Global Profit Exit, Basket Exit, and Trailing"""
        try:
            acc = mt5.account_info()
            if not acc: return
            
            # 1. --- GLOBAL PROFIT EXIT (ALL Trades) ---
            global_pnl = acc.equity - acc.balance
            target = self.config.get('risk', {}).get('global_profit_target_usd', 100)
            if not hasattr(self, '_last_global_log'): self._last_global_log = 0
            if time.time() - self._last_global_log > 30:
                logger.debug(f"🔍 [Global PnL Check] Current: ${global_pnl:.2f} / Target: ${target:.2f}")
                self._last_global_log = time.time()
            if global_pnl >= target:
                logger.info(f"💰 GLOBAL PROFIT REACHED: ${global_pnl:.2f} (Target: ${target}). CLOSING ALL...")
                all_pos = self.broker.get_positions()
                for p in all_pos: self.broker.close_position(p['symbol'], p['ticket'])
                self.trades_today += len(all_pos)
                self.broker.cancel_all_pendings("ALL") # Force cancel all
                if "XAUUSDm" in self.grid_manager.active_grids: del self.grid_manager.active_grids["XAUUSDm"]
                self.grid_manager._save_state()
                return

            positions = self.broker.get_positions()
            if not positions: return
            
            buy_grid = [p for p in positions if p['magic'] == self.grid_manager.magic_buy]
            sell_grid = [p for p in positions if p['magic'] == self.grid_manager.magic_sell]
            
            for grid_positions in [buy_grid, sell_grid]:
                if not grid_positions: continue
                symbol = grid_positions[0]['symbol']; direction = 'BUY' if grid_positions[0]['type'] == 'BUY' else 'SELL'
                vol = sum(p['volume'] for p in grid_positions); waep = sum(p['price_open'] * p['volume'] for p in grid_positions) / vol
                tick = mt5.symbol_info_tick(symbol); cp = (tick.bid if direction == 'BUY' else tick.ask) if tick else waep
                
                # Get ATR for distance calculation
                tf = self.grid_manager.TIMEFRAME_MAP.get(self.timeframe, mt5.TIMEFRAME_M5)
                rates = mt5.copy_rates_from_pos(symbol, tf, 0, 50)
                atr = 1.0
                if rates is not None and len(rates) >= 14:
                    import pandas as pd
                    import numpy as np
                    df = pd.DataFrame(rates)
                    df['tr'] = np.maximum(df['high'] - df['low'], np.maximum(abs(df['high'] - df['close'].shift(1)), abs(df['low'] - df['close'].shift(1))))
                    atr = df['tr'].rolling(14).mean().iloc[-1]
                
                target_usd = self.config.get('grid', {}).get('profit_target_usd', 3.0)
                
                count = len(grid_positions)
                
                if count <= 3: dist = atr * 0.8; min_p = (vol / 0.01) * target_usd
                elif count <= 5: dist = atr * 0.5; min_p = (vol / 0.01) * (target_usd * 0.6)
                else: dist = atr * 0.1; min_p = (vol / 0.01) * (target_usd * 0.3)
                
                target_p = waep + dist if direction == 'BUY' else waep - dist
                basket_pnl = sum(p['profit'] + p.get('swap', 0) for p in grid_positions)
                at_target = (direction == 'BUY' and cp >= target_p) or (direction == 'SELL' and cp <= target_p) or (basket_pnl >= min_p)
                
                if symbol not in self.basket_trailing: self.basket_trailing[symbol] = {}
                trailing = self.basket_trailing[symbol].get(direction, {'active': False, 'peak': 0.0})
                
                should_exit = False
                trailing_enabled = self.config.get('grid', {}).get('trailing_enabled', True)
                
                if at_target:
                    if not trailing_enabled:
                        logger.info(f"🎯 HARD EXIT (Trailing Off) for {symbol} {direction} | PnL: ${basket_pnl:.2f}")
                        should_exit = True
                    else:
                        if not trailing['active']:
                            logger.info(f"✨ TRAILING ACTIVATED for {symbol} {direction} | PnL: ${basket_pnl:.2f}")
                            trailing = {'active': True, 'peak': basket_pnl}
                            self.basket_trailing[symbol][direction] = trailing
                            if symbol in self.grid_manager.active_grids: self.grid_manager.active_grids[symbol]['is_trailing'] = True; self.grid_manager._save_state()
                        if basket_pnl > trailing['peak']: trailing['peak'] = basket_pnl; self.basket_trailing[symbol][direction] = trailing
                        if basket_pnl < trailing['peak'] * 0.85 or basket_pnl < min_p * 0.5: should_exit = True
                elif trailing['active'] and basket_pnl < min_p * 0.5: should_exit = True
                
                # Store target info for dashboard
                if symbol in self.grid_manager.active_grids:
                    self.grid_manager.active_grids[symbol]['min_profit'] = min_p

                if should_exit:
                    logger.info(f"🎯 BASKET EXIT for {symbol} {direction} | PnL: ${basket_pnl:.2f}")
                    for p in grid_positions: self.broker.close_position(symbol, p['ticket'])
                    self.trades_today += len(grid_positions) # Increment trades
                    orders = mt5.orders_get(symbol=symbol)
                    magic = self.grid_manager.magic_buy if direction == 'BUY' else self.grid_manager.magic_sell
                    if orders:
                        for o in [ord for ord in orders if ord.magic == magic]: mt5.order_send({"action": mt5.TRADE_ACTION_REMOVE, "order": o.ticket})
                    if symbol in self.grid_manager.active_grids: del self.grid_manager.active_grids[symbol]; self.grid_manager._save_state()
                    if symbol in self.basket_trailing and direction in self.basket_trailing[symbol]: del self.basket_trailing[symbol][direction]
        except Exception as e: logger.error(f"Monitoring error: {e}")
    
    def display_status(self):
        try:
            acc = mt5.account_info()
            if acc:
                pnl = acc.balance - self.start_balance
                duration = datetime.now() - self.start_time
                hours, remainder = divmod(int(duration.total_seconds()), 3600)
                minutes, seconds = divmod(remainder, 60)
                season_str = f"{hours}h {minutes}m {seconds}s"
                
                trailing_on = self.config.get('grid', {}).get('trailing_enabled', True)
                trail_status = "✨ ON" if trailing_on else "❌ OFF"
                
                print(f"\n{'='*50}\n🧠 SC-RIG-D v2.0 - PERFORMANCE DASHBOARD (Trail: {trail_status})\n{'='*50}")
                print(f"💰 Balance: ${acc.balance:.2f} | P&L: ${pnl:.2f} | Trades: {self.trades_today}")
                print(f"⏰ Server: {datetime.now().strftime('%H:%M:%S')} | Season: {season_str}")
                
                active_symbols = set(self.config.get('symbols', []))
                open_pos = self.broker.get_positions()
                active_symbols.update([p['symbol'] for p in open_pos])
                
                for symbol in active_symbols:
                    data = self.grid_manager.active_grids.get(symbol, {})
                    if data.get('type') != 'NEUTRAL' or (open_pos and any(p['symbol'] == symbol for p in open_pos)):
                        ict = data.get('ict_status', {})
                        active_sigs = [k.upper() for k, v in ict.items() if v]
                        confluence = " | ".join(active_sigs) if active_sigs else "SCANNED"
                        bias_str = data.get('bias_at_start', 'NEUTRAL')
                        target_usd_display = self.config.get('grid', {}).get('profit_target_usd', 3.0)
                        print(f"📉 Grid {symbol}: {data.get('type', 'SCAN')} ({bias_str}) | Target: ${data.get('min_profit', target_usd_display):.1f}")
                        print(f"   [ICT RAIL] {confluence}")
                
                print(f"📋 Open Positions: {len(open_pos)}")
                for p in open_pos: print(f"  {p['symbol']}: {p['type']} ${p['profit']:.2f}")
                print(f"{'='*50}")
        except: pass
    
    async def run(self):
        if not await self.initialize(): return
        self.running = True; logger.info("🚀 Starting live trading...")
        asyncio.create_task(self._monitor_heartbeat())
        cycle = 0
        while self.running:
            try:
                self._reload_settings() # Check for config updates
                if cycle % 3600 == 0:
                    acc = mt5.account_info()
                    if acc:
                        daily_pnl = acc.balance - self.start_balance
                        await self.discord.send_heartbeat(acc, daily_pnl, self.trades_today, len(self.broker.get_positions()))
                self._manage_symbol_switching()
                for symbol in self.symbols: await self.analyze_and_trade(symbol)
                await self.monitor_positions()
                if cycle % 60 == 0: self.display_status()
                cycle += 1; await asyncio.sleep(1)
            except Exception as e: logger.error(f"Loop error: {e}"); await asyncio.sleep(5)

    async def _monitor_heartbeat(self):
        while self.running:
            try:
                if not await self.broker.is_connected():
                    logger.warning("📉 Broker disconnected! Reconnecting...")
                    await self.broker.connect()
                await asyncio.sleep(10)
            except: pass

def select_trade_setup():
    # Check for command line arguments
    import argparse
    parser = argparse.ArgumentParser(description="NEXT LEVEL BRAIN Live Trading System")
    parser.add_argument("--strategy", type=str, help="Trading strategy to use")
    parser.add_argument("--timeframe", type=str, help="Timeframe to use (e.g., M1, M5, M15)")
    parser.add_argument("--cron", action="store_true", help="Run in non-interactive mode using config defaults")
    parser.add_argument("--auto-start", action="store_true", help="Auto-select options: strategy after 1s, timeframe after 2s")
    args, unknown = parser.parse_known_args()

    # Load config for defaults
    config = {}
    config_path = Path("config.yaml")
    if config_path.exists():
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
        except: pass

    # Resolve Strategy
    strats = ["Hybrid Mode", "Grid Both (Reversal/Pivot)", "ICT SMC (High Precision)", "BUY ONLY (Grid Support)", "SELL ONLY (Grid Resistance)"]
    strategy = None

    if args.strategy:
        strategy = args.strategy
    elif args.cron:
        strategy = config.get('strategy', 'Hybrid Mode')
    elif args.auto_start:
        print("\n" + "=" * 50); print("      🚀 NEXT LEVEL TRADING CONFIGURATION"); print("=" * 50)
        print("\n [1] Choose Strategy:")
        time.sleep(1)
        strategy = strats[0]
        print(f"  >> Auto-selected: {strategy} (after 1s)")
    
    if not strategy:
        print("\n" + "=" * 50); print("      🚀 NEXT LEVEL TRADING CONFIGURATION"); print("=" * 50)
        print("\n [1] Choose Strategy:"); [print(f"  {i+1}. {s}") for i, s in enumerate(strats)]
        try:
            s_choice = int(input("  >> Choice (1-5): ").strip())
            strategy = strats[s_choice-1]
        except: strategy = "Hybrid Mode"

    # Resolve Timeframe
    tfs = ["M1", "M5", "M15", "M30", "H1"]; labels = ["1 Minute (Scalp)", "5 Minutes (Intraday)", "15 Minutes (Swing)", "30 Minutes", "Hourly"]
    tf = None

    if args.timeframe:
        tf = args.timeframe
    elif args.cron:
        tf = config.get('timeframe', 'M5')
    elif args.auto_start:
        print("\n [2] Choose Timeframe:")
        time.sleep(1)
        tf = tfs[2]
        print(f"  >> Auto-selected: {labels[2]} (after 2s total)")

    if not tf:
        print("\n [2] Choose Timeframe:"); [print(f"  {i+1}. {l}") for i, l in enumerate(labels)]
        try:
            t_choice = int(input("  >> Choice (1-5): ").strip())
            tf = tfs[t_choice-1]
        except: tf = "M5"
    
    symbols = config.get('symbols', ['XAUUSDm'])
    return symbols, strategy, tf

def launch_dashboard():
    try:
        Path("logs/trading_active.lock").touch()
        print("\n  [>>] Launching Live Dashboard..."); import subprocess
        script_dir = os.path.dirname(os.path.abspath(__file__))
        proc = subprocess.Popen([sys.executable, os.path.join(script_dir, "live_dashboard.py")], creationflags=0x08100000 if os.name == 'nt' else 0, close_fds=True)
        return proc
    except: return None

def main():
    try:
        security = SecurityManager()
        if not security.is_authorized() and not security.prompt_activation(): return
        symbols, strategy, timeframe = select_trade_setup()
        print(f"\n   STARTING SESSION: {strategy} | {timeframe} | {datetime.now().strftime('%H:%M:%S')}\n")
        ts = LiveTradingSystem(); ts.symbols = symbols; ts.strategy = strategy; ts.timeframe = timeframe
        db_proc = launch_dashboard()
        asyncio.run(ts.run())
    except KeyboardInterrupt: logger.info("Keyboard interrupt.")
    except Exception as e: logger.error(f"Critical error: {e}")
    finally:
        if Path("logs/trading_active.lock").exists(): Path("logs/trading_active.lock").unlink()
        if 'db_proc' in locals() and db_proc: db_proc.terminate()
        logger.info("👋 System shutdown complete.")

if __name__ == "__main__":
    main()
