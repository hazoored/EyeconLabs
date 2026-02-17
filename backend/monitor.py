
import os
import asyncio
import logging
from datetime import datetime
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.tl.functions.account import GetAuthorizationsRequest
from telethon.tl.functions.auth import ResetAuthorizationsRequest
from telethon.tl.types import Authorization
import telegram

# Import database and settings
from database import db
from config import settings

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Bot config
BOT_TOKEN = os.getenv("MANAGER_BOT_TOKEN", "7952018847:AAHsCvGPxxgUT4F9rC4dbnj2FHbk03Z_byA")
ADMIN_TO_NOTIFY = 6926297956

API_ID = int(os.getenv("TELEGRAM_API_ID", "21219293"))
API_HASH = os.getenv("TELEGRAM_API_HASH", "cff5d321b676104840cf282a742381e0")

async def notify_admin(bot, message):
    """Send alert to admin via Telegram."""
    try:
        await bot.send_message(chat_id=ADMIN_TO_NOTIFY, text=message, parse_mode='HTML')
    except Exception as e:
        logger.error(f"Failed to notify admin: {e}")

async def monitor_iteration(bot):
    """One monitoring pass for all active monitored accounts."""
    logger.info("🛡 Starting monitoring iteration...")
    active_monitored = db.get_active_monitored_accounts()
    
    if not active_monitored:
        logger.info("No accounts currently under active monitoring.")
        return

    for entry in active_monitored:
        acc_id = entry['account_id']
        session_str = entry['session_string']
        phone = entry['phone_number']
        
        try:
            async with TelegramClient(StringSession(session_str), API_ID, API_HASH) as client:
                auths = await client(GetAuthorizationsRequest())
                
                # If more than 1 session, check them
                # Note: The current script connection counts as 1.
                if len(auths.authorizations) > 1:
                    logger.warning(f"⚠️ Account {phone} ({acc_id}) has {len(auths.authorizations)} active sessions!")
                    
                    # Log intruders (any authorization that is NOT current)
                    # Telethon's current authorization usually has 'current' attribute or similar
                    # But easiest is to use ResetAuthorizationsRequest to kick everyone else
                    
                    await client(ResetAuthorizationsRequest())
                    logger.info(f"✅ Reset authorizations for account {phone}.")
                    
                    alert = (
                        f"🛡 <b>Security Alert: Account {phone}</b>\n\n"
                        f"⚠️ <b>Detected:</b> {len(auths.authorizations) - 1} unauthorized session(s).\n"
                        f"⚡ <b>Action taken:</b> Terminated all other sessions instantly.\n"
                        f"🤖 <i>Account is still under 30-day watch.</i>"
                    )
                    await notify_admin(bot, alert)
                    
        except Exception as e:
            logger.error(f"Error monitoring account {phone}: {e}")
            if "database is locked" in str(e).lower():
                await asyncio.sleep(1) # Wait if DB is busy

async def main():
    """Main loop for the monitor service."""
    logger.info("🛡 EyeconBumps Session Monitor Service starting...")
    bot = telegram.Bot(token=BOT_TOKEN)
    
    # Send startup notification
    await notify_admin(bot, "🛡 <b>Session Monitor Service: ONLINE</b>")
    
    while True:
        try:
            await monitor_iteration(bot)
        except Exception as e:
            logger.error(f"Fatal error in monitor loop: {e}")
            
        # Wait 12 hours
        logger.info("⏳ Sleeping for 12 hours...")
        await asyncio.sleep(12 * 60 * 60)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Session monitor stopped by user.")
