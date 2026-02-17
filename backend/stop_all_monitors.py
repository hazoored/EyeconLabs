import sys
import os
import logging

# Ensure we can find database.py even if run from parent directory
sys.path.append(os.getcwd())
if os.path.basename(os.getcwd()) != 'backend' and os.path.exists('backend'):
    sys.path.append(os.path.join(os.getcwd(), 'backend'))

try:
    from database import db
except ImportError:
    print("❌ Error: Could not find 'database.py'.")
    print("👉 Please make sure you are in the 'backend' directory:")
    print("   cd /opt/eyeconlabs/backend")
    sys.exit(1)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def stop_all_monitoring():
    """
    Stops all monitoring activities in the database and provides commands 
    to stop VPS services.
    """
    logger.info("🛑 Starting the process to stop all monitoring activities...")

    try:
        with db.get_connection() as conn:
            cursor = conn.cursor()

            # 1. Deactivate Monitored Accounts
            # We check if the table exists first to avoid errors on different environments
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='monitored_accounts'")
            if cursor.fetchone():
                cursor.execute("UPDATE monitored_accounts SET is_active = 0 WHERE is_active = 1")
                logger.info(f"✅ Deactivated {cursor.rowcount} monitored accounts.")
            else:
                logger.info("ℹ️ 'monitored_accounts' table does not exist. Skipping.")

            # 2. Deactivate Log Bots
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='log_bots'")
            if cursor.fetchone():
                cursor.execute("UPDATE log_bots SET is_active = 0 WHERE is_active = 1")
                logger.info(f"✅ Deactivated {cursor.rowcount} log bots.")
            else:
                logger.info("ℹ️ 'log_bots' table does not exist. Skipping.")

            # 3. Stop Running Campaigns
            cursor.execute("UPDATE campaigns SET status = 'stopped' WHERE status = 'running'")
            logger.info(f"✅ Stopped {cursor.rowcount} running campaigns.")

            # 4. Deactivate Auto Reply History (Optional but safe)
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='auto_reply_history'")
            if cursor.fetchone():
                # Note: This is history, so we don't necessarily "deactivate" it, 
                # but if there were an is_active flag, we'd set it. 
                # For now, just logging that it exists.
                logger.info("ℹ️ 'auto_reply_history' table found.")

            conn.commit()

        logger.info("🎉 Database updates completed successfully.")

    except Exception as e:
        logger.error(f"❌ Error during database update: {e}")

if __name__ == "__main__":
    stop_all_monitoring()
    
    print("\n" + "="*50)
    print("📋 NEXT STEPS TO COMPLETE ON VPS:")
    print("="*50)
    print("Run these commands to stop the active services:")
    print("  sudo systemctl stop eyeconlabs-manager-bot")
    print("  sudo systemctl stop eyeconlabs-monitor")
    print("  sudo systemctl stop eyeconlabs-auto-reply")
    print("\nTo disable them from starting on boot:")
    print("  sudo systemctl disable eyeconlabs-manager-bot")
    print("  sudo systemctl disable eyeconlabs-monitor")
    print("  sudo systemctl disable eyeconlabs-auto-reply")
    print("="*50 + "\n")
