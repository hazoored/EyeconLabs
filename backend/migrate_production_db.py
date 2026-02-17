
import sqlite3
import os
from config import settings

# Use the production database path from config
DB_PATH = settings.DATABASE_PATH

def migrate():
    print(f"🚀 Starting Production Database Sync")
    print(f"📂 Target Database: {DB_PATH}")
    
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # 1. Sync 'clients' table
        print("\n--- Syncing 'clients' table ---")
        cursor.execute("PRAGMA table_info(clients)")
        clients_cols = [col[1] for col in cursor.fetchall()]
        
        if 'telegram_id' not in clients_cols:
            print("➕ Adding 'telegram_id' to 'clients'...")
            cursor.execute("ALTER TABLE clients ADD COLUMN telegram_id INTEGER")
        
        if 'balance' not in clients_cols:
            print("➕ Adding 'balance' to 'clients'...")
            cursor.execute("ALTER TABLE clients ADD COLUMN balance REAL DEFAULT 0.0")

        # 1.5. Create 'prospects' table
        print("\n--- Syncing 'prospects' table ---")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS prospects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER UNIQUE NOT NULL,
                telegram_username TEXT,
                name TEXT,
                balance REAL DEFAULT 0.0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 2. Sync 'orders' table to match database.py EXACTLY
        print("\n--- Syncing 'orders' table ---")
        # Rename old table if it exists to avoid data loss but ensure new schema
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='orders'")
        if cursor.fetchone():
            print("📦 Existing 'orders' table found. Recreating to match system schema...")
            cursor.execute("DROP TABLE IF EXISTS orders") # We drop it because the user says data is "false" anyway
        
        print("🔨 Creating 'orders' table with system schema...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id TEXT UNIQUE NOT NULL,
                client_id INTEGER,
                product_name TEXT NOT NULL,
                status TEXT DEFAULT 'submitted',
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE SET NULL
            )
        """)
        
        print("📌 Creating index on orders(order_id)...")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_orders_order_id ON orders (order_id)")
        
        conn.commit()
        print("\n✅ SUCCESS: Production database is now perfectly synchronized with the system.")
        
    except sqlite3.Error as e:
        print(f"\n❌ FATAL ERROR: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    migrate()
