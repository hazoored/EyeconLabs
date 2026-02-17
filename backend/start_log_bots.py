import sys
import os
import logging

# Ensure we can find database.py
sys.path.append(os.getcwd())
if os.path.basename(os.getcwd()) != 'backend' and os.path.exists('backend'):
    sys.path.append(os.path.join(os.getcwd(), 'backend'))

try:
    from database import db
except ImportError:
    print("❌ Error: Could not find 'database.py'.")
    sys.exit(1)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def start_log_bots():
    logger.info("🚀 Reactivating ONLY the Ad Logs Bot...")
    try:
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE log_bots SET is_active = 1")
            logger.info(f"✅ Reactivated {cursor.rowcount} log bots.")
            conn.commit()
        logger.info("🎉 Done. Logs will now be sent.")
    except Exception as e:
        logger.error(f"❌ Error: {e}")

if __name__ == "__main__":
    start_log_bots()
