import asyncio
import os
import requests
from datetime import datetime
from loguru import logger

class DiscordNotifier:
    """Discord Webhook Notifier for Real-time Trading Signals & Updates (Robust requests-based)"""
    def __init__(self, webhook_url: str = None):
        self.webhook_url = webhook_url or os.getenv("DISCORD_WEBHOOK_URL")

    async def close(self):
        if self.webhook_url:
            await self.send_message("👋 Trading Session Terminated. Bot is going offline.", title="System Shutdown", color=0x888888)

    async def send_message(self, content: str, title: str = "Trading Update", color: int = 0x58a6ff) -> bool:
        if not self.webhook_url:
            return False
        
        def _send():
            try:
                payload = {
                    "embeds": [{
                        "title": title,
                        "description": content,
                        "color": color,
                        "timestamp": datetime.utcnow().isoformat()
                    }]
                }
                resp = requests.post(self.webhook_url, json=payload, timeout=10)
                if resp.status_code not in [200, 204]:
                    logger.error(f"Discord Webhook Error ({resp.status_code}): {resp.text}")
                    return False
                return True
            except Exception as e:
                logger.error(f"Discord send failed: {e}")
                return False

        # Run synchronous request in a thread to avoid blocking the event loop
        return await asyncio.to_thread(_send)

    async def send_signal(self, symbol: str, action: str, confidence: float, reasoning: str, price: float, tp: float, sl: float):
        # 🟢 Bullish for BUY, 🔴 Bearish for SELL
        color = 0x00e676 if action == "BUY" else 0xff5252
        content = (
            f"🚀 **Symbol**: `{symbol}`\n"
            f"🎯 **Action**: `{action}`\n"
            f"💎 **Confidence**: `{confidence:.2f}`\n"
            f"💰 **Entry Price**: `{price:.5f}`\n"
            f"✅ **Take Profit**: `{tp:.5f}`\n"
            f"🛡️ **Stop Loss**: `{sl:.5f}`\n\n"
            f"🧠 **Logic**: {reasoning}"
        )
        return await self.send_message(content, title=f"🚨 New ICT Signal: {action} on {symbol}", color=color)

    async def send_heartbeat(self, account_info, daily_pnl, trades_today, active_positions) -> bool:
        content = (
            f"📈 **Account Balance**: `${account_info.balance:.2f}`\n"
            f"💵 **Daily P&L**: `{'+' if daily_pnl >= 0 else ''}${daily_pnl:.2f}`\n"
            f"📊 **Trades Today**: `{trades_today}`\n"
            f"📋 **Open Positions**: `{active_positions}`\n"
            f"⚖️ **Equity**: `${account_info.equity:.2f}`\n"
            f"⚓ **Margin Level**: `{account_info.margin_level:.1f}%`"
        )
        return await self.send_message(content, title="🕒 Scheduled Hourly Update", color=0x58a6ff)
