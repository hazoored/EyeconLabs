import sqlite3
import os

DB_PATH = "/opt/eyeconlabs/data/eyeconbumps_webapp.db"

def fix_db():
    if not os.path.exists(DB_PATH):
        print(f"Error: Database not found at {DB_PATH}")
        return

    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        print("Checking for auto_reply_history table...")
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS auto_reply_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id INTEGER NOT NULL,
                target_user_id INTEGER NOT NULL,
                replied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(account_id, target_user_id)
            )
        """)
        
        conn.commit()
        print("✅ SUCCESS: auto_reply_history table created (or already existed).")
        conn.close()
        
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    fix_db()
