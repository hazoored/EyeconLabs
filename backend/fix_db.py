import sqlite3
import sys
import os

# Path to your database
DB_PATH = "/opt/eyeconlabs/data/eyeconbumps_webapp.db"

def fix_user(telegram_id):
    print(f"🔧 Attempting to fix user: {telegram_id}")
    
    if not os.path.exists(DB_PATH):
        print(f"❌ Database not found at: {DB_PATH}")
        return

    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # 1. Check current records
        cursor.execute("SELECT id, name, is_active, expires_at FROM clients WHERE telegram_id = ?", (telegram_id,))
        rows = cursor.fetchall()
        
        if not rows:
            print(f"ℹ️ No records found for user {telegram_id}.")
            return

        print(f"⚠️ Found {len(rows)} record(s) for user {telegram_id}:")
        for row in rows:
            print(f"   - ID: {row[0]}, Name: {row[1]}, Active: {row[2]}, Expires: {row[3]}")
        
        # 2. DELETE THEM ALL
        print(f"🗑️ Deleting all records for {telegram_id}...")
        cursor.execute("DELETE FROM clients WHERE telegram_id = ?", (telegram_id,))
        deleted_count = cursor.rowcount
        
        conn.commit()
        print(f"✅ Successfully deleted {deleted_count} record(s).")
        print("User should now be able to use /start and buy a plan again.")
        
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 fix_db.py <telegram_id>")
        sys.exit(1)
    
    tid = sys.argv[1]
    fix_user(tid)
