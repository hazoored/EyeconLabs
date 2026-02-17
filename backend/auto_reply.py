import random
import asyncio
import gc
import os
import logging
from telethon import TelegramClient
from telethon.sessions import StringSession
from database import Database
from config import settings

# Configure logging
logging.basicConfig(
    format='[%(asctime)s] %(levelname)s: %(message)s',
    level=logging.INFO
)
logging.getLogger('telethon').setLevel(logging.WARNING)
logging.getLogger('telethon.network.mtprotosender').setLevel(logging.CRITICAL)

logger = logging.getLogger(__name__)

# Telegram API Credentials
API_ID = int(os.getenv("TELEGRAM_API_ID", "21219293"))
API_HASH = os.getenv("TELEGRAM_API_HASH", "cff5d321b676104840cf282a742381e0")

# Polling interval (seconds) - Increased to 10 minutes to avoid rate-limiting
POLL_INTERVAL = 600

class AutoReplyBot:
    def __init__(self):
        logger.info(f"Using database: {settings.DATABASE_PATH}")
        self.db = Database(db_path=settings.DATABASE_PATH)
        self.bad_accounts = set()  # Cache invalid accounts to prevent retries
        self.failure_counters = {} # acc_id -> consecutive failures
        self.running = False

    async def start(self):
        """Main loop: poll all accounts periodically."""
        self.running = True
        logger.info(f"AutoReplyBot started (polling mode, interval={POLL_INTERVAL}s)")

        while self.running:
            try:
                accounts = self.db.get_all_accounts()
                active_accounts = [
                    a for a in accounts
                    if a.get('is_active')
                    and a.get('session_string')
                    and a.get('id') not in self.bad_accounts
                ]

                if active_accounts:
                    logger.info(f"Polling {len(active_accounts)} accounts for unread PMs...")

                for acc in active_accounts:
                    if not self.running:
                        break
                    
                    try:
                        # Random delay between accounts (5-10s) to avoid bulk connection spike
                        await asyncio.sleep(random.uniform(5, 10))
                        await self.poll_account(acc)
                    except Exception as e:
                        logger.error(f"Error polling account {acc.get('phone_number')}: {e}")

                    # Force garbage collection after each account
                    gc.collect()

            except Exception as e:
                logger.error(f"Error in main loop: {e}")

            await asyncio.sleep(POLL_INTERVAL)

    async def poll_account(self, account):
        """Connect to one account, check for unread PMs, reply, disconnect."""
        phone = account.get('phone_number', '???')
        session = account.get('session_string')
        account_id = account.get('id')
        client_tg = account.get('telegram_username', '')
        mention = f"@{client_tg}" if client_tg else "the support team"

        client = TelegramClient(StringSession(session), API_ID, API_HASH)
        try:
            await client.connect()

            if not await client.is_user_authorized():
                # Increment failure counter
                cnt = self.failure_counters.get(account_id, 0) + 1
                self.failure_counters[account_id] = cnt
                
                logger.warning(f"Account {phone} not authorized (Attempt {cnt}/3)")
                
                if cnt >= 3:
                    logger.error(f"Account {phone} failed 3 times, marking as bad.")
                    self.bad_accounts.add(account_id)
                    try:
                        self.db.set_account_active(account_id, False)
                    except Exception as de:
                        logger.error(f"DB Update failed for {phone}: {de}")
                return

            # Success! Reset counter
            self.failure_counters[account_id] = 0

            # Get dialogs — only need users with unread messages
            dialogs = await client.get_dialogs(limit=None, ignore_migrated=True)

            replied = 0
            for d in dialogs:
                if not d.is_user: continue
                if d.entity.bot or d.entity.is_self: continue
                if d.unread_count <= 0: continue

                sender_id = d.entity.id

                # Already replied check
                if self.db.has_replied_to_user(account_id, sender_id):
                    try:
                        await client.send_read_acknowledge(d.entity)
                    except Exception: pass
                    continue

                # Send auto-reply
                try:
                    reply_text = (
                        f"**Automation**\n"
                        f"Welcome! This is just a bot account for the purpose of running ADs. "
                        f"Messages or inquiries sent here will not receive a response. "
                        f"Kindly contact me at {mention}"
                    )
                    await client.send_message(d.entity, reply_text)
                    self.db.log_auto_reply(account_id, sender_id)
                    await client.send_read_acknowledge(d.entity)
                    replied += 1

                    sender_name = getattr(d.entity, 'username', None) or \
                        f"{getattr(d.entity, 'first_name', '')} {getattr(d.entity, 'last_name', '')}".strip() or \
                        str(sender_id)
                    logger.info(f"[{phone}] Replied to {sender_name}")

                except Exception as e:
                    logger.error(f"[{phone}] Failed to reply to {sender_id}: {e}")

            if replied > 0:
                logger.info(f"[{phone}] Sent {replied} auto-replies this cycle")

        except Exception as e:
            logger.error(f"[{phone}] Connection error: {e}")
            # Do NOT deactivate on generic connection errors
        finally:
            try:
                await client.disconnect()
            except Exception: pass
            del client

if __name__ == "__main__":
    bot = AutoReplyBot()
    try:
        asyncio.run(bot.start())
    except KeyboardInterrupt:
        print("\nStopped by user")
