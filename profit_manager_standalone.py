#!/usr/bin/env python3
import asyncio
import yaml
import MetaTrader5 as mt5
from pathlib import Path
from loguru import logger
import sys
from mt5_broker import MT5Broker
from profit_controller import ProfitController
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

async def main():
    logger.remove()
    logger.add(sys.stdout, format="<green>{time:HH:mm:ss}</green> | <level>{level}</level> | <cyan>{message}</cyan>", level="INFO")
    
    logger.info("🚀 Starting STANDALONE PROFIT CONTROLLER")
    
    # Load config
    config = {}
    if Path("config.yaml").exists():
        with open("config.yaml", 'r') as f:
            config = yaml.safe_load(f)
    
    broker = MT5Broker(config.get('mt5', {}))
    if not await broker.connect():
        logger.error("Failed to connect to MT5")
        return
        
    # We can monitor all positions or specific ones
    # For now, let's monitor standard Grid magic numbers from config or defaults
    buy_magic = 20001
    sell_magic = 20002
    symbol = config.get('symbols', ['XAUUSDm'])[0]
    
    # Target USD for Basket TP (Paste Close)
    target_usd = config.get('profit_target_usd', 10.0)
    
    controller = ProfitController(broker, "Standalone-Manager")
    
    logger.info(f"🔍 Monitoring {symbol} | Target: ${target_usd:.2f} | Magic: {buy_magic}/{sell_magic}")
    logger.info("🛡️ Trailing is ACTIVE with progressive locking.")

    try:
        while True:
            if not await broker.is_connected():
                logger.warning("Connection lost! Reconnecting...")
                await broker.connect()
                continue
            
            # 1. Basket Profit Check (Paste Close)
            balance_info = mt5.account_info()
            balance = balance_info.balance if balance_info else 0
            
            # This will close if target hit
            closed = await controller.check_basket_profit(symbol, buy_magic, sell_magic, target_usd, balance)
            
            # 2. Trailing Profit Check (Trail Close)
            # This monitors sides independently
            if not closed:
                await controller.monitor_trailing(symbol, buy_magic, sell_magic)
                
            await asyncio.sleep(5)
            
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        mt5.shutdown()

if __name__ == "__main__":
    asyncio.run(main())
