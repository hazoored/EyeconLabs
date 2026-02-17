
import sqlite3
import os

# Define database path
DB_PATH = os.getenv("DATABASE_PATH", "eyeconbumps_webapp.db")

def diagnose_and_fix():
    print(f"Connecting to {DB_PATH}...")
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # 1. Check clients table
        print("\n--- Diagnostic: clients table ---")
        cursor.execute("PRAGMA table_info(clients)")
        clients_cols = [col[1] for col in cursor.fetchall()]
        print(f"Columns in 'clients': {clients_cols}")
        
        if 'telegram_id' not in clients_cols:
            print("❌ MISSING: 'telegram_id' in 'clients' table!")
            # We can't really fix this automatically if there are other dependencies, 
            # but we can try to add it.
            print("Attempting to add 'telegram_id' to 'clients'...")
            cursor.execute("ALTER TABLE clients ADD COLUMN telegram_id INTEGER")
            print("✅ Added 'telegram_id' column.")
        else:
            print("✅ 'telegram_id' exists in 'clients'.")

        # 2. Force drop and recreate orders table
        print("\n--- Fixing orders table ---")
        print("Dropping 'orders' table if it exists...")
        cursor.execute("DROP TABLE IF EXISTS orders")
        
        print("Creating 'orders' table...")
        cursor.execute("""
            CREATE TABLE orders (
                order_id TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                plan_name TEXT NOT NULL,
                amount REAL NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        print("Creating index...")
        cursor.execute("CREATE INDEX idx_orders_user_id ON orders (user_id)")
        
        conn.commit()
        print("\n✅ SUCCESS: 'orders' table created and verified.")
        
    except sqlite3.Error as e:
        print(f"\n❌ FATAL DATABASE ERROR: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    diagnose_and_fix()
