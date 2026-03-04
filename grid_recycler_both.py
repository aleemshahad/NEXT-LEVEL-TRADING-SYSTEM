#!/usr/bin/env python3
import asyncio
import yaml
import MetaTrader5 as mt5
from pathlib import Path
from loguru import logger
import sys
from mt5_broker import MT5Broker
from grid_recycler import GridRecycler
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

async def main():
    logger.remove()
    logger.add(sys.stdout, format="<green>{time:HH:mm:ss}</green> | <level>{level}</level> | <cyan>{message}</cyan>", level="INFO")
    
    logger.info("🚀 Starting GRID RECYCLER - BOTH")
    
    # Load config
    config = {}
    if Path("config.yaml").exists():
        with open("config.yaml", 'r') as f:
            config = yaml.safe_load(f)
    
    broker = MT5Broker(config.get('mt5', {}))
    if not await broker.connect():
        logger.error("Failed to connect to MT5")
        return
        
    recycler = GridRecycler(broker, config)
    recycler.mode = "BOTH"
    
    symbol = config.get('symbols', ['XAUUSDm'])[0]
    
    logger.info(f"📈 Mode: BOTH | Symbol: {symbol}")
    
    try:
        while True:
            if not await broker.is_connected():
                logger.warning("Connection lost! Reconnecting...")
                await broker.connect()
                continue
                
            tick = mt5.symbol_info_tick(symbol)
            if tick:
                # Use mid price for BOTH mode update logic
                await recycler.update(symbol, (tick.ask + tick.bid) / 2)
                
            await asyncio.sleep(10)
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        mt5.shutdown()

if __name__ == "__main__":
    asyncio.run(main())
