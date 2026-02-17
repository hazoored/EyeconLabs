import sqlite3
import os

DB_PATH = '/opt/eyeconlabs/backend/eyeconbumps_webapp.db'

try:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(campaigns)")
    columns = [row[1] for row in cursor.fetchall()]
    print(f"Columns in campaigns: {columns}")
    
    needed = ['send_mode', 'forward_link', 'forward_from_chat', 'forward_message_id', 'forward_from_username']
    missing = [c for c in needed if c not in columns]
    
    if missing:
        print(f"MISSING COLUMNS: {missing}")
    else:
        print("ALL COLUMNS PRESENT")
        
except Exception as e:
    print(f"Error: {e}")
