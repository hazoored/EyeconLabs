"""
Add balance column to clients table
Run this script once to add the balance column to existing database
"""

import sqlite3
import os

DB_PATH = os.getenv("DATABASE_PATH", "eyeconbumps_webapp.db")

def add_balance_column():
    """Add balance column to clients table if it doesn't exist."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Try to add the balance column
        cursor.execute("ALTER TABLE clients ADD COLUMN balance REAL DEFAULT 0.0")
        conn.commit()
        print("✅ Successfully added 'balance' column to clients table")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e).lower():
            print("ℹ️  'balance' column already exists")
        else:
            print(f"❌ Error: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    print("Adding balance column to database...")
    add_balance_column()
    print("Done!")
