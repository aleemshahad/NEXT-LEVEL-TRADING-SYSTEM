import MetaTrader5 as mt5
import time
from loguru import logger
from smart_trailing import SmartTrailingHandler
from typing import Optional, List, Dict
import json
from pathlib import Path

class ProfitController:
    """
    Centralized Profit Controller:
    - Paste Close: Close positions when a fixed USD target is hit.
    - Trail Close: Use Smart Trailing to lock profits and exit.
    """
    
    def __init__(self, broker, strategy_name: str = "Controller"):
        self.broker = broker
        self.strategy_name = strategy_name
        self.trailing = SmartTrailingHandler()
        self.ticket_states = {}
        self.grand_basket_state = {'peak': 0.0, 'lock': 0.0}
        self.equity_milestone_state = {'baseline_equity': 0.0, 'peak': 0.0, 'lock': 0.0, 'hits': 0}
        self._last_log_time = 0
        self.unit = "$" # Default
        
        # Persistence setup
        safe_name = "".join([c if c.isalnum() else "_" for c in strategy_name])
        self.state_file = Path(f"logs/profit_state_{safe_name}.json")
        self._load_state()

    def _load_state(self):
        """Load peaks and locks from disk"""
        try:
            if self.state_file.exists():
                with open(self.state_file, 'r') as f:
                    data = json.load(f)
                    # Convert string keys back to int tickets
                    self.ticket_states = {int(k): v for k, v in data.get('ticket_states', {}).items()}
                    self.grand_basket_state = data.get('grand_basket_state', {'peak': 0.0, 'lock': 0.0})
                    self.equity_milestone_state = data.get('equity_milestone_state', {'baseline_equity': 0.0, 'hits': 0})
                    logger.info(f"💾 {self.strategy_name} recovered {len(self.ticket_states)} trade states + Milestone logic from disk.")
        except Exception as e:
            logger.error(f"Failed to load profit state: {e}")

    def _save_state(self, force: bool = False):
        """Save peaks and locks to disk with throttling to avoid micro-delays."""
        try:
            # Throttle: Only save if forced or every 5 seconds
            now = time.time()
            if not force and now - getattr(self, '_last_disk_save', 0) < 5:
                return
            
            self.state_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Smart Pruning
            active_mt5_positions = mt5.positions_get()
            if active_mt5_positions is not None:
                all_active_tickets = {p.ticket for p in active_mt5_positions}
                # Use list() to avoid dictionary size change during iteration
                for k in list(self.ticket_states.keys()):
                    if k not in all_active_tickets:
                        del self.ticket_states[k]

            data = {
                'ticket_states': self.ticket_states,
                'grand_basket_state': self.grand_basket_state,
                'equity_milestone_state': self.equity_milestone_state
            }
            with open(self.state_file, 'w') as f:
                json.dump(data, f)
            self._last_disk_save = now
        except Exception as e:
            logger.error(f"Failed to save profit state: {e}")

    async def check_basket_profit(self, symbol: str, buy_magic: int, sell_magic: int, target_usd: float, positions: List[dict] = None) -> bool:
        """
        Check combined profit of BUY and SELL sides and close if target_usd is reached.
        """
        if target_usd <= 0:
            return False

        if positions is None:
            positions = self.broker.get_positions()
            
        grid_positions = [p for p in positions if p['symbol'] == symbol and p.get('magic') in (buy_magic, sell_magic)]
        
        if not grid_positions:
            return False

        total_profit = sum(p['profit'] for p in grid_positions)
        
        # Periodic logging
        now = time.time()
        if now - self._last_log_time > 10:
            logger.info(f"📊 {self.strategy_name} | Combined Profit: {total_profit:.2f} {self.unit} / Target: {target_usd:.2f} {self.unit}")
            self._last_log_time = now

        if total_profit >= target_usd:
            logger.info(f"🚀 BASKET TARGET HIT: ${total_profit:.2f} >= ${target_usd:.2f}. Closing all {symbol} trades!")
            await self.broker.close_all_side(symbol, 'BUY', buy_magic)
            await self.broker.close_all_side(symbol, 'SELL', sell_magic)
            await self.broker.cancel_all_pendings(symbol, buy_magic)
            await self.broker.cancel_all_pendings(symbol, sell_magic)
            self.trailing.reset('BOTH')
            return True
            
        return False

    async def monitor_trailing(self, symbol: str, buy_magic: int, sell_magic: int, positions: List = None) -> dict:
        """
        Monitor BUY and SELL sides independently for trailing profit.
        Returns a dict indicating if closures happened.
        """
        results = {'BUY': False, 'SELL': False}
        
        # Use provided positions or fetch fresh if none
        if positions is None:
            raw_positions = mt5.positions_get(symbol=symbol)
            if raw_positions is None: return results
            # Wrap in list to ensure iteration works
            positions = list(raw_positions)

        # Helper to get attributes from either object or dict
        def get_val(p, key, default=0.0):
            if hasattr(p, key): return getattr(p, key)
            if isinstance(p, dict): return p.get(key, default)
            return default

        # Check BUY side
        buy_pos = [p for p in positions if get_val(p, 'symbol') == symbol and get_val(p, 'type') in (mt5.POSITION_TYPE_BUY, 'BUY') and get_val(p, 'magic') == buy_magic]
        if buy_pos:
            buy_profit = sum(get_val(p, 'profit') + get_val(p, 'commission') + get_val(p, 'swap') for p in buy_pos)
            action = self.trailing.check_profit('BUY', buy_profit)
            if action == 'CLOSE':
                logger.info(f"🛡️ [{self.strategy_name}] BUY Trail Exit hit. Closing all BUY positions!")
                print("\n*** LAYER 2 (Side Basket) Profit Booked for BUY Side! ***\n")
                await self.broker.close_all_side(symbol, 'BUY', buy_magic)
                await self.broker.cancel_all_pendings(symbol, buy_magic)
                results['BUY'] = True

        # Check SELL side
        sell_pos = [p for p in positions if get_val(p, 'symbol') == symbol and get_val(p, 'type') in (mt5.POSITION_TYPE_SELL, 'SELL') and get_val(p, 'magic') == sell_magic]
        if sell_pos:
            sell_profit = sum(get_val(p, 'profit') + get_val(p, 'commission') + get_val(p, 'swap') for p in sell_pos)
            action = self.trailing.check_profit('SELL', sell_profit)
            if action == 'CLOSE':
                logger.info(f"🛡️ [{self.strategy_name}] SELL Trail Exit hit. Closing all SELL positions!")
                print("\n*** LAYER 2 (Side Basket) Profit Booked for SELL Side! ***\n")
                await self.broker.close_all_side(symbol, 'SELL', sell_magic)
                await self.broker.cancel_all_pendings(symbol, sell_magic)
                results['SELL'] = True
                
        # Status update logs
        now = time.time()
        if now - self._last_log_time > 15:
            buy_lock = self.trailing.get_lock('BUY')
            sell_lock = self.trailing.get_lock('SELL')
            if buy_pos or sell_pos:
                buy_info = f"{buy_profit:.2f} {self.unit} (Lock: {buy_lock:.2f} {self.unit})" if buy_pos else "Inactive"
                sell_info = f"{sell_profit:.2f} {self.unit} (Lock: {sell_lock:.2f} {self.unit})" if sell_pos else "Inactive"
                logger.info(f"🔍 [{self.strategy_name}] Trail Trace | BUY: {buy_info} | SELL: {sell_info}")
                self._last_log_time = now

        return results

    async def monitor_individual_trailing(self, positions: list, per_trade_target: float) -> list:
        """
        Monitor individual tickets for trailing profit.
        Thresholds and locks scale proportionally to lot size (base 0.01).
        Returns a list of tickets that should be closed.
        """
        to_close = []
        
        for pos in positions:
            ticket = pos.ticket
            # BUG FIX: Remove lot size scaling as per user request.
            # Trailing starts at $0.25 and locks $0.10 regardless of lot size.
            multiplier = 1.0 
            
            pnl = pos.profit + getattr(pos, 'commission', 0.0) + pos.swap
            
            if ticket not in self.ticket_states:
                # BUG FIX: Initialize peak at 0.0 not pnl.
                # If trade starts in loss (pnl < 0), a negative peak would
                # corrupt all threshold comparisons until profit is reached.
                self.ticket_states[ticket] = {'peak': 0.0, 'lock': 0.0}
            
            state = self.ticket_states[ticket]
            if pnl > state['peak']: state['peak'] = pnl

            # ── FIXED USD LOGIC (Regardless of Lot Size) ──────────────────
            # 1. Hard Take Profit: Only for Bot Trades (Magic != 0)
            # Manual trades are trailed but NOT closed at choti-machli profit targets.
            scaled_target = per_trade_target 
            if getattr(pos, 'magic', 0) != 0 and pnl >= scaled_target:
                logger.info(f"💰 Ticket {ticket} Hard TP Hit: PnL {pnl:.2f} {self.unit} >= {scaled_target:.2f} {self.unit}")
                print(f"\n*** LAYER 1 (Individual Trade) Hard TP Profit Booked! Ticket: {ticket} ***\n")
                to_close.append(pos)
                if ticket in self.ticket_states:
                    del self.ticket_states[ticket]
                continue

            # 2. Micro-Trailing: Fixed USD Levels
            micro_levels = [
                (0.25, 0.10), # Start trailing at $0.25, lock $0.10
                (0.50, 0.25), # At $0.50 profit, lock $0.25
                (0.75, 0.50), # At $0.75 profit, lock $0.50
            ]

            new_lock = state['lock']
            if pnl > 0:
                for threshold, lock_val in micro_levels:
                    if state['peak'] >= threshold:
                        if lock_val > new_lock:
                            new_lock = lock_val
                    else:
                        break

            # ── UNLIMITED FLOATING TRAIL (New Logic) ──────────────────
            # Once profit crosses $1.00, we switch to 80% Peak Profit Lock.
            # This allows trades to run to $10, $100, etc. without limits.
            if state['peak'] >= 1.0 and pnl > 0:
                floating_lock = state['peak'] * 0.80
                if floating_lock > new_lock:
                    new_lock = floating_lock

            state['lock'] = new_lock

            # Exit logic (with strict NO LOSS GUARD)
            min_exit_profit = 0.01 # Just ensure it's slightly positive for safety
            if new_lock > 0 and pnl < new_lock:
                if pnl >= min_exit_profit:
                    logger.info(f"💰 Ticket {ticket} Trail Exit: PnL {pnl:.2f} {self.unit} < Lock {new_lock:.2f} {self.unit}. Closing!")
                    print(f"\n*** LAYER 1 (Individual Trade) Trail Exit Profit Booked! Ticket: {ticket} ***\n")
                    to_close.append(pos)
                    if ticket in self.ticket_states:
                        del self.ticket_states[ticket]
                else:
                    # Logic is hit but price is too close to break-even/loss
                    # We hold for better exit or hard TP
                    pass

        # Sync states to disk
        self._save_state()
        
        return to_close

    async def monitor_grand_basket(self, positions: list, trigger_usd: float = 20.0) -> bool:
        """
        Monitor total profit of ALL active positions across ALL symbols/strategies.
        Starts trailing once combined profit >= trigger_usd ($20.0).
        """
        if not positions:
            # BUG FIX: Do NOT hard-reset peak/lock on empty list.
            # Positions may temporarily vanish due to broker lag/refresh.
            # Only reset if trailing was never activated (lock == 0).
            if hasattr(self, 'grand_basket_state') and self.grand_basket_state:
                if self.grand_basket_state.get('lock', 0.0) == 0.0:
                    self.grand_basket_state = {'peak': 0.0, 'lock': 0.0}
            return False

        if not hasattr(self, 'grand_basket_state') or self.grand_basket_state is None:
            self.grand_basket_state = {'peak': 0.0, 'lock': 0.0}

        total_profit = sum(p.profit + getattr(p, 'commission', 0.0) + p.swap for p in positions)
        state = self.grand_basket_state

        # Activate trailing when trigger hit
        if total_profit >= trigger_usd:
            if total_profit > state['peak']:
                state['peak'] = total_profit
            
            # Simple 80% lock of peak
            new_lock = state['peak'] * 0.8
            if new_lock > state['lock']:
                state['lock'] = new_lock
                logger.info(f"🛡️  GRAND BASKET LOCK: Total Profit {total_profit:.2f} {self.unit} (Inc. Fees). New Lock: {new_lock:.2f} {self.unit}")

        # Check for trailing exit (with NO LOSS GUARD)
        if state['lock'] > 0 and total_profit < state['lock']:
            if total_profit >= 1.0: # Ensure at least $1 total profit for global exit
                logger.info(f"🚀 GRAND BASKET EXIT: Combined Profit {total_profit:.2f} {self.unit} < Lock {state['lock']:.2f} {self.unit}. Closing Universe!")
                print("\n*** LAYER 2 (Grand Basket) Profit Booked! All Trades Closing. ***\n")
                self.grand_basket_state = {'peak': 0.0, 'lock': 0.0}
                self._save_state() # Save reset state
                return True
            else:
                # Profit dropped too fast, don't close in loss or near-zero
                pass

        # Save state to disk on any lock/peak update
        # (Disk I/O is throttled to 5s inside _save_state automatically)
        if total_profit >= trigger_usd or state['lock'] > 0:
            self._save_state()


        return False

    async def monitor_equity_milestone(self, current_equity: float, target_increase: float = 100.0) -> bool:
        """
        Monitor total account equity. If equity increases by target_increase ($100) 
        from the baseline, return True to trigger a global close.
        """
        if current_equity <= 0: return False

        state = self.equity_milestone_state
        if state['baseline_equity'] <= 0:
            state['baseline_equity'] = current_equity
            state['peak'] = 0.0
            state['lock'] = 0.0
            self._save_state()
            logger.info(f"🎯 Milestone Baseline Set: {current_equity:.2f} {self.unit}. Target: {current_equity + target_increase:.2f} {self.unit}")
            return False

        profit = current_equity - state['baseline_equity']

        # --- Layer 3: Multi-Tier Progressive Trailing Logic (Mazboot Version) ---
        # ─────────────────────────────────────────────────────────────────────
        #  Tier 1: $100–$130  → Lock = peak - 8% of target      (conservative)
        #  Tier 2: $130–$180  → Lock = 80% of peak              (moderate)
        #  Tier 3: $180–$250  → Lock = 86% of peak              (tight)
        #  Tier 4: $250+      → Lock = 92% of peak              (very tight)
        #
        #  Rules:
        #   • NO hard floor — lock follows pure tier percentage
        #   • Lock NEVER retreats — only moves up (ratchet principle)
        #   • Every new peak → lock recalculates and tries to advance
        # ─────────────────────────────────────────────────────────────────────
        if profit >= target_increase:
            peak = state.get('peak', 0.0)

            # First time hitting target
            if peak <= 0.0:
                state['peak'] = profit
                state['lock'] = 0.0  # No hard floor — pure tier trailing from here
                logger.info(
                    f"🏆 [LAYER 3] MILESTONE HIT! {target_increase:.2f} {self.unit} secured. "
                    f"Multi-tier trailing ACTIVATED."
                )
                peak = profit

            # Update peak (ratchet up only)
            if profit > peak:
                state['peak'] = profit
                peak = profit

            # ── Determine lock based on progressive tier ─────────────────
            T = target_increase  # shorthand

            if peak < T * 1.30:
                # Tier 1: Conservative — still near target, use buffer
                buffer = T * 0.08       # 8% of target (e.g. $8 for $100 target)
                new_lock = peak - buffer
                tier_label = "T1 (Conservative)"

            elif peak < T * 1.80:
                # Tier 2: Moderate — lock at 80% of peak
                new_lock = peak * 0.80
                tier_label = "T2 (Moderate 80%)"

            elif peak < T * 2.50:
                # Tier 3: Tight — lock at 86% of peak
                new_lock = peak * 0.86
                tier_label = "T3 (Tight 86%)"

            else:
                # Tier 4: Very Tight — lock at 92% of peak (ekdum mazboot)
                new_lock = peak * 0.92
                tier_label = "T4 (Very Tight 92%)"

            # Apply lock (ratchet — only advance, never retreat)
            if new_lock > state['lock']:
                old_lock = state['lock']
                state['lock'] = new_lock
                logger.info(
                    f"🛡️  [LAYER 3] {tier_label} | "
                    f"Peak: {peak:.2f} | Lock: {old_lock:.2f} → {new_lock:.2f} {self.unit} | "
                    f"Protecting {(new_lock/peak*100):.1f}% of peak"
                )

        # Update dashboard bridge file (Throttled to 1s)
        try:
            now = time.time()
            if now - getattr(self, '_last_bridge_update', 0) > 1:
                progress_file = Path("logs/milestone_progress.json")
                progress_file.parent.mkdir(parents=True, exist_ok=True)
                with open(progress_file, 'w') as f:
                    json.dump({
                        'current': current_equity,
                        'baseline': state['baseline_equity'],
                        'target': state['baseline_equity'] + target_increase,
                        'progress': profit,
                        'target_inc': target_increase,
                        'lock': state.get('lock', 0.0),
                        'peak': state.get('peak', 0.0),
                        'hits': state.get('hits', 0),
                        'unit': self.unit,
                        'timestamp': time.time()
                    }, f)
                self._last_bridge_update = now
        except: pass

        # ── Exit Logic: Profit dropped below the lock → CLOSE ────────────
        if state.get('lock', 0.0) > 0 and profit < state['lock']:
            locked = state['lock']
            peak_at_exit = state.get('peak', locked)
            logger.info(
                f"🚀 [LAYER 3] MILESTONE SECURED! "
                f"Profit {profit:.2f} < Lock {locked:.2f} {self.unit}. "
                f"(Peak was {peak_at_exit:.2f}) — Closing Universe!"
            )
            print(f"\n*** LAYER 3 (Account Equity) Profit Booked! Secured: {locked:.2f} {self.unit} ***\n")
            state['hits'] = state.get('hits', 0) + 1
            state['peak'] = 0.0
            state['lock'] = 0.0
            self._save_state(force=True)
            return True

        return False

    def reset_equity_milestone(self, current_equity: float):
        """Set a new baseline for the next $100 milestone cycle"""
        if current_equity > 0:
            self.equity_milestone_state['baseline_equity'] = current_equity
            self.equity_milestone_state['peak'] = 0.0
            self.equity_milestone_state['lock'] = 0.0
            self._save_state()
            logger.info(f"🔄 Milestone Baseline RESET to {current_equity:.2f} {self.unit}")

            # Clear dashboard bridge file on reset
            try:
                progress_file = Path("logs/milestone_progress.json")
                if progress_file.exists():
                    with open(progress_file, 'w') as f:
                        json.dump({
                            'current': current_equity,
                            'baseline': current_equity,
                            'target': current_equity + 100.0,
                            'progress': 0.0,
                            'lock': 0.0,
                            'hits': self.equity_milestone_state.get('hits', 0),
                            'target_inc': 100.0,
                            'unit': self.unit,
                            'timestamp': time.time()
                        }, f)
            except: pass

    def reset(self, side: str = 'BOTH'):
        self.trailing.reset(side)
        if side == 'BOTH':
            self.ticket_states = {}
            self.grand_basket_state = {'peak': 0.0, 'lock': 0.0}
            # BUG FIX: Preserve 'hits' across resets (session counter).
            # Also explicitly reset peak and lock so stale state file
            # values cannot be reloaded on next startup.
            hits = self.equity_milestone_state.get('hits', 0)
            self.equity_milestone_state = {
                'baseline_equity': 0.0,
                'peak': 0.0,
                'lock': 0.0,
                'hits': hits
            }
            self._save_state()
