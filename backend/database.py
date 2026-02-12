"""
EyeconBumps Web App - Database Models and Connection
SQLite3 with enhanced schema for web features
"""
import sqlite3
import json
import random
import string
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from contextlib import contextmanager
import threading

from config import settings

DATABASE_LOCK = threading.Lock()

class Database:
    def __init__(self, db_path: str = "eyeconbumps_webapp.db"):
        self.db_path = db_path
        self._init_db()
    
    @contextmanager
    def get_connection(self):
        """Thread-safe database connection context manager."""
        with DATABASE_LOCK:
            conn = sqlite3.connect(self.db_path, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            try:
                yield conn
                conn.commit()
            except Exception as e:
                conn.rollback()
                raise e
            finally:
                conn.close()
    
    def _init_db(self):
        """Initialize database tables."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Clients table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS clients (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    telegram_username TEXT,
                    telegram_id INTEGER,
                    access_token TEXT UNIQUE NOT NULL,
                    subscription_type TEXT DEFAULT 'starter',
                    expires_at TIMESTAMP,
                    is_active INTEGER DEFAULT 1,
                    notes TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Telegram accounts pool (can be assigned to clients later)
            # First check if we need to migrate the old table (with NOT NULL constraint)
            cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='client_accounts'")
            table_info = cursor.fetchone()
            
            if table_info and 'client_id INTEGER NOT NULL' in (table_info[0] or ''):
                # Need to migrate: old table has NOT NULL constraint
                cursor.execute("ALTER TABLE client_accounts RENAME TO client_accounts_old")
                cursor.execute("""
                    CREATE TABLE client_accounts (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        client_id INTEGER,
                        phone_number TEXT NOT NULL,
                        session_string TEXT NOT NULL,
                        display_name TEXT,
                        is_premium INTEGER DEFAULT 0,
                        is_active INTEGER DEFAULT 1,
                        settings TEXT DEFAULT '{}',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE SET NULL
                    )
                """)
                cursor.execute("""
                    INSERT INTO client_accounts (id, client_id, phone_number, session_string, display_name, is_active, settings, created_at)
                    SELECT id, client_id, phone_number, session_string, display_name, is_active, settings, created_at
                    FROM client_accounts_old
                """)
                cursor.execute("DROP TABLE client_accounts_old")
            elif not table_info:
                # Create new table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS client_accounts (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        client_id INTEGER,
                        phone_number TEXT NOT NULL,
                        session_string TEXT NOT NULL,
                        display_name TEXT,
                        is_premium INTEGER DEFAULT 0,
                        is_active INTEGER DEFAULT 1,
                        settings TEXT DEFAULT '{}',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE SET NULL
                    )
                """)
            
            # Add is_premium column if it doesn't exist (migration)
            try:
                cursor.execute("ALTER TABLE client_accounts ADD COLUMN is_premium INTEGER DEFAULT 0")
            except:
                pass  # Column already exists
            
            # Campaigns
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS campaigns (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    client_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    status TEXT DEFAULT 'draft',
                    target_groups TEXT DEFAULT '[]',
                    message_type TEXT DEFAULT 'text',
                    message_content TEXT,
                    forward_data TEXT,
                    delay_seconds INTEGER DEFAULT 30,
                    is_active INTEGER DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE CASCADE
                )
            """)
            
            # Broadcast logs
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS broadcast_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    campaign_id INTEGER,
                    account_id INTEGER,
                    client_id INTEGER,
                    group_name TEXT,
                    status TEXT,
                    error_message TEXT,
                    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (campaign_id) REFERENCES campaigns(id) ON DELETE SET NULL,
                    FOREIGN KEY (account_id) REFERENCES client_accounts(id) ON DELETE SET NULL,
                    FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE CASCADE
                )
            """)
            
            # Analytics summary (daily aggregates)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS analytics_daily (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    client_id INTEGER NOT NULL,
                    date TEXT NOT NULL,
                    total_broadcasts INTEGER DEFAULT 0,
                    successful_sends INTEGER DEFAULT 0,
                    failed_sends INTEGER DEFAULT 0,
                    groups_reached INTEGER DEFAULT 0,
                    FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE CASCADE,
                    UNIQUE(client_id, date)
                )
            """)
            
            # Admin sessions
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS admin_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    token TEXT UNIQUE NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    expires_at TIMESTAMP NOT NULL,
                    is_valid INTEGER DEFAULT 1
                )
            """)
            
            # Message templates for reusable ad content
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS message_templates (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    client_id INTEGER,
                    name TEXT NOT NULL,
                    content TEXT,
                    media_type TEXT DEFAULT 'text',
                    media_file_id TEXT,
                    is_active INTEGER DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE CASCADE
                )
            """)
            
            # Campaign target groups
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS campaign_groups (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    campaign_id INTEGER NOT NULL,
                    group_username TEXT NOT NULL,
                    group_name TEXT,
                    is_forum INTEGER DEFAULT 0,
                    topic_id INTEGER,
                    status TEXT DEFAULT 'pending',
                    last_sent_at TIMESTAMP,
                    FOREIGN KEY (campaign_id) REFERENCES campaigns(id) ON DELETE CASCADE
                )
            """)
            
            # Add new columns to campaigns table (migration)
            try:
                cursor.execute("ALTER TABLE campaigns ADD COLUMN scheduled_at TIMESTAMP")
            except:
                pass
            try:
                cursor.execute("ALTER TABLE campaigns ADD COLUMN accounts_used TEXT DEFAULT '[]'")
            except:
                pass
            try:
                cursor.execute("ALTER TABLE campaigns ADD COLUMN total_sent INTEGER DEFAULT 0")
            except:
                pass
            try:
                cursor.execute("ALTER TABLE campaigns ADD COLUMN total_failed INTEGER DEFAULT 0")
            except:
                pass
            try:
                cursor.execute("ALTER TABLE campaigns ADD COLUMN current_index INTEGER DEFAULT 0")
            except:
                pass
            # Add forward message columns
            try:
                cursor.execute("ALTER TABLE campaigns ADD COLUMN send_mode TEXT DEFAULT 'send'")
            except:
                pass
            try:
                cursor.execute("ALTER TABLE campaigns ADD COLUMN forward_from_chat INTEGER")
            except:
                pass
            try:
                cursor.execute("ALTER TABLE campaigns ADD COLUMN forward_message_id INTEGER")
            except:
                pass
            try:
                cursor.execute("ALTER TABLE campaigns ADD COLUMN forward_from_username TEXT")
            except:
                pass
            
            # Log bots configuration for real-time Telegram logs
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS log_bots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    client_id INTEGER UNIQUE NOT NULL,
                    bot_token TEXT NOT NULL,
                    target_id TEXT NOT NULL,
                    is_active INTEGER DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE CASCADE
                )
            """)
            
            # Broadcast logs for detailed tracking
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS broadcast_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    campaign_id INTEGER,
                    account_id INTEGER,
                    client_id INTEGER,
                    group_name TEXT,
                    status TEXT,
                    error_message TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE CASCADE
                )
            """)

            # Orders table for tracking services
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
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_orders_order_id ON orders (order_id)")
            
            # Add created_at to broadcast_logs if it doesn't exist
            try:
                cursor.execute("ALTER TABLE broadcast_logs ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
            except:
                pass
            
            conn.commit()
    
    # ============ CLIENT METHODS ============
    
    def generate_access_token(self) -> str:
        """Generate a unique 5-character alphanumeric token."""
        chars = string.ascii_uppercase + string.digits
        # Exclude confusing characters
        chars = chars.replace('O', '').replace('0', '').replace('I', '').replace('1', '')
        while True:
            token = ''.join(random.choices(chars, k=5))
            # Check uniqueness
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT id FROM clients WHERE access_token = ?", (token,))
                if not cursor.fetchone():
                    return token
    
    def create_client(self, name: str, telegram_username: str = None, 
                      telegram_id: int = None, subscription_type: str = "starter",
                      expires_days: int = 30, notes: str = None) -> Dict[str, Any]:
        """Create a new client with a unique access token."""
        access_token = self.generate_access_token()
        expires_at = datetime.now() + timedelta(days=expires_days)
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO clients (name, telegram_username, telegram_id, access_token, 
                                    subscription_type, expires_at, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (name, telegram_username, telegram_id, access_token, 
                  subscription_type, expires_at, notes))
            client_id = cursor.lastrowid
            
            return {
                "id": client_id,
                "name": name,
                "telegram_username": telegram_username,
                "access_token": access_token,
                "subscription_type": subscription_type,
                "expires_at": expires_at.isoformat(),
                "is_active": True
            }
    
    def get_client_by_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Get client by access token."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM clients WHERE access_token = ? AND is_active = 1
            """, (token,))
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None
    
    def get_client_by_id(self, client_id: int) -> Optional[Dict[str, Any]]:
        """Get client by ID."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM clients WHERE id = ?", (client_id,))
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None
    
    def get_all_clients(self) -> List[Dict[str, Any]]:
        """Get all clients."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM clients ORDER BY created_at DESC")
            return [dict(row) for row in cursor.fetchall()]
    
    def update_client(self, client_id: int, **kwargs) -> bool:
        """Update client details."""
        allowed_fields = ['name', 'telegram_username', 'telegram_id', 
                         'subscription_type', 'expires_at', 'is_active', 'notes']
        updates = {k: v for k, v in kwargs.items() if k in allowed_fields}
        
        if not updates:
            return False
        
        updates['updated_at'] = datetime.now().isoformat()
        set_clause = ', '.join([f"{k} = ?" for k in updates.keys()])
        values = list(updates.values()) + [client_id]
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"UPDATE clients SET {set_clause} WHERE id = ?", values)
            return cursor.rowcount > 0
    
    def delete_client(self, client_id: int) -> bool:
        """Delete a client and all related data."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM clients WHERE id = ?", (client_id,))
            return cursor.rowcount > 0
    
    def regenerate_client_token(self, client_id: int) -> Optional[str]:
        """Generate a new access token for a client."""
        new_token = self.generate_access_token()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE clients SET access_token = ?, updated_at = ? WHERE id = ?
            """, (new_token, datetime.now().isoformat(), client_id))
            if cursor.rowcount > 0:
                return new_token
            return None
    
    # ============ ACCOUNT METHODS ============
    
    def add_account(self, phone_number: str, session_string: str, 
                    display_name: str = None, is_premium: bool = False,
                    client_id: int = None) -> Dict[str, Any]:
        """Add a Telegram account to the pool (optionally assign to client)."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO client_accounts (client_id, phone_number, session_string, display_name, is_premium)
                VALUES (?, ?, ?, ?, ?)
            """, (client_id, phone_number, session_string, display_name, 1 if is_premium else 0))
            return {
                "id": cursor.lastrowid,
                "client_id": client_id,
                "phone_number": phone_number,
                "display_name": display_name,
                "is_premium": is_premium,
                "is_active": True
            }
    
    def add_client_account(self, client_id: int, phone_number: str, 
                          session_string: str, display_name: str = None) -> Dict[str, Any]:
        """Legacy: Add account directly to a client."""
        return self.add_account(phone_number, session_string, display_name, False, client_id)
    
    def assign_account_to_client(self, account_id: int, client_id: int = None) -> bool:
        """Assign or unassign an account to a client."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE client_accounts SET client_id = ? WHERE id = ?
            """, (client_id, account_id))
            return cursor.rowcount > 0
    
    def update_account(self, account_id: int, **kwargs) -> bool:
        """Update account details."""
        allowed_fields = ['display_name', 'is_premium', 'is_active', 'client_id']
        updates = {k: v for k, v in kwargs.items() if k in allowed_fields}
        
        if not updates:
            return False
        
        set_clause = ', '.join([f"{k} = ?" for k in updates.keys()])
        values = list(updates.values()) + [account_id]
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"UPDATE client_accounts SET {set_clause} WHERE id = ?", values)
            return cursor.rowcount > 0
    
    def get_unassigned_accounts(self) -> List[Dict[str, Any]]:
        """Get accounts not assigned to any client."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, phone_number, display_name, is_premium, is_active, created_at
                FROM client_accounts WHERE client_id IS NULL
                ORDER BY created_at DESC
            """)
            return [dict(row) for row in cursor.fetchall()]
    
    def get_client_accounts(self, client_id: int) -> List[Dict[str, Any]]:
        """Get all accounts for a client including session strings for broadcasting."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, client_id, phone_number, display_name, is_active, is_premium, session_string, settings, created_at
                FROM client_accounts WHERE client_id = ?
            """, (client_id,))
            return [dict(row) for row in cursor.fetchall()]
    
    def get_all_accounts(self) -> List[Dict[str, Any]]:
        """Get all accounts with client info."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT a.id, a.client_id, a.phone_number, a.display_name, a.is_active, 
                       a.is_premium, a.created_at, c.name as client_name
                FROM client_accounts a
                LEFT JOIN clients c ON a.client_id = c.id
                ORDER BY a.created_at DESC
            """)
            return [dict(row) for row in cursor.fetchall()]
    
    def get_account_by_id(self, account_id: int) -> Optional[Dict[str, Any]]:
        """Get account by ID including session string."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, client_id, phone_number, session_string, display_name, 
                       is_premium, is_active, created_at
                FROM client_accounts WHERE id = ?
            """, (account_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def delete_account(self, account_id: int) -> bool:
        """Delete an account."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM client_accounts WHERE id = ?", (account_id,))
            return cursor.rowcount > 0
    
    # ============ CAMPAIGN METHODS ============
    
    def create_campaign(self, client_id: int, name: str, target_groups: List[str] = None,
                       message_type: str = "text", message_content: str = None,
                       delay_seconds: int = 30, account_id: int = None, template_id: int = None) -> Dict[str, Any]:
        """Create a new campaign with optional specific account and message template."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO campaigns (client_id, name, target_groups, message_type, 
                                       message_content, delay_seconds, account_id, template_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (client_id, name, json.dumps(target_groups or []), message_type, 
                  message_content, delay_seconds, 
                  account_id if account_id and account_id > 0 else None,
                  template_id if template_id and template_id > 0 else None))
            return {
                "id": cursor.lastrowid,
                "client_id": client_id,
                "name": name,
                "status": "draft",
                "account_id": account_id,
                "template_id": template_id
            }
    
    def get_client_campaigns(self, client_id: int) -> List[Dict[str, Any]]:
        """Get all campaigns for a client."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM campaigns WHERE client_id = ? ORDER BY created_at DESC
            """, (client_id,))
            campaigns = []
            for row in cursor.fetchall():
                campaign = dict(row)
                campaign['target_groups'] = json.loads(campaign.get('target_groups', '[]'))
                campaigns.append(campaign)
            return campaigns
    
    def get_all_campaigns(self) -> List[Dict[str, Any]]:
        """Get all campaigns with client info."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT c.*, cl.name as client_name
                FROM campaigns c
                LEFT JOIN clients cl ON c.client_id = cl.id
                ORDER BY c.created_at DESC
            """)
            campaigns = []
            for row in cursor.fetchall():
                campaign = dict(row)
                campaign['target_groups'] = json.loads(campaign.get('target_groups', '[]'))
                campaigns.append(campaign)
            return campaigns
    
    def update_campaign_status(self, campaign_id: int, status: str) -> bool:
        """Update campaign status (draft, running, paused, completed)."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE campaigns SET status = ?, updated_at = ? WHERE id = ?
            """, (status, datetime.now().isoformat(), campaign_id))
            return cursor.rowcount > 0
    
    def update_campaign(self, data: dict) -> bool:
        """Update campaign with arbitrary fields."""
        if 'id' not in data:
            return False
        
        campaign_id = data.pop('id')
        if not data:
            return False
        
        # Build SET clause
        set_parts = []
        values = []
        for key, value in data.items():
            set_parts.append(f"{key} = ?")
            values.append(value)
        
        values.append(datetime.now().isoformat())
        values.append(campaign_id)
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"""
                UPDATE campaigns SET {', '.join(set_parts)}, updated_at = ? WHERE id = ?
            """, values)
            return cursor.rowcount > 0
    
    def get_campaign_by_id(self, campaign_id: int) -> Optional[Dict[str, Any]]:
        """Get a single campaign by ID."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM campaigns WHERE id = ?", (campaign_id,))
            row = cursor.fetchone()
            if row:
                campaign = dict(row)
                campaign['target_groups'] = json.loads(campaign.get('target_groups', '[]'))
                return campaign
            return None
    
    def delete_campaign(self, campaign_id: int) -> bool:
        """Delete a campaign and its associated data (groups, logs)."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            # Delete associated groups
            cursor.execute("DELETE FROM campaign_groups WHERE campaign_id = ?", (campaign_id,))
            # Delete associated logs
            cursor.execute("DELETE FROM broadcast_logs WHERE campaign_id = ?", (campaign_id,))
            # Delete campaign
            cursor.execute("DELETE FROM campaigns WHERE id = ?", (campaign_id,))
            return cursor.rowcount > 0
    
    def get_campaign_groups(self, campaign_id: int) -> List[Dict[str, Any]]:
        """Get target groups for a campaign."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM campaign_groups WHERE campaign_id = ? ORDER BY id
            """, (campaign_id,))
            return [dict(row) for row in cursor.fetchall()]
    
    def add_campaign_groups(self, campaign_id: int, groups: List[str]) -> int:
        """Add target groups to a campaign. Returns count added."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            count = 0
            for group in groups:
                group = group.strip()
                if not group:
                    continue
                # Extract username from t.me link if needed
                if 't.me/' in group:
                    group = group.split('/')[-1]
                cursor.execute("""
                    INSERT OR IGNORE INTO campaign_groups (campaign_id, group_username)
                    VALUES (?, ?)
                """, (campaign_id, group))
                count += cursor.rowcount
            return count
    
    def clear_campaign_groups(self, campaign_id: int):
        """Clear all target groups for a campaign."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM campaign_groups WHERE campaign_id = ?", (campaign_id,))
    
    def update_campaign_progress(self, campaign_id: int, sent: int, failed: int, current_index: int):
        """Update campaign progress counters."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE campaigns SET 
                    total_sent = ?, 
                    total_failed = ?,
                    current_index = ?,
                    updated_at = ?
                WHERE id = ?
            """, (sent, failed, current_index, datetime.now().isoformat(), campaign_id))
    
    def update_analytics(self, client_id: int, broadcasts: int, success: int, failed: int):
        """Update daily analytics for a client."""
        today = datetime.now().strftime('%Y-%m-%d')
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO analytics_daily (client_id, date, total_broadcasts, successful_sends, failed_sends)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(client_id, date) DO UPDATE SET
                    total_broadcasts = total_broadcasts + ?,
                    successful_sends = successful_sends + ?,
                    failed_sends = failed_sends + ?
            """, (client_id, today, broadcasts, success, failed, broadcasts, success, failed))
    
    # ============ ANALYTICS METHODS ============
    
    def log_broadcast(self, campaign_id: int, account_id: int, client_id: int,
                     group_name: str, status: str, error_message: str = None):
        """Log a broadcast attempt."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO broadcast_logs (campaign_id, account_id, client_id, 
                                           group_name, status, error_message)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (campaign_id, account_id, client_id, group_name, status, error_message))
            
            # Update daily analytics
            today = datetime.now().strftime('%Y-%m-%d')
            # Status is 'sent' for success (from broadcaster), not 'success'
            if status == 'sent':
                cursor.execute("""
                    INSERT INTO analytics_daily (client_id, date, successful_sends, total_broadcasts)
                    VALUES (?, ?, 1, 1)
                    ON CONFLICT(client_id, date) DO UPDATE SET
                    successful_sends = successful_sends + 1,
                    total_broadcasts = total_broadcasts + 1
                """, (client_id, today))
            elif status == 'skipped':
                # Skipped groups don't count as failed or towards total broadcasts
                pass
            else:
                cursor.execute("""
                    INSERT INTO analytics_daily (client_id, date, failed_sends, total_broadcasts)
                    VALUES (?, ?, 1, 1)
                    ON CONFLICT(client_id, date) DO UPDATE SET
                    failed_sends = failed_sends + 1,
                    total_broadcasts = total_broadcasts + 1
                """, (client_id, today))
    
    def get_client_analytics(self, client_id: int, days: int = 30) -> Dict[str, Any]:
        """Get analytics for a client."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Get daily stats
            cursor.execute("""
                SELECT * FROM analytics_daily 
                WHERE client_id = ? AND date >= date('now', ?)
                ORDER BY date DESC
            """, (client_id, f'-{days} days'))
            daily_stats = [dict(row) for row in cursor.fetchall()]
            
            # Get totals
            cursor.execute("""
                SELECT 
                    COALESCE(SUM(total_broadcasts), 0) as total_broadcasts,
                    COALESCE(SUM(successful_sends), 0) as successful_sends,
                    COALESCE(SUM(failed_sends), 0) as failed_sends
                FROM analytics_daily WHERE client_id = ?
            """, (client_id,))
            totals = dict(cursor.fetchone())
            
            return {
                "daily": daily_stats,
                "totals": totals
            }
    
    def get_client_group_stats(self, client_id: int, days: int = 30, limit: int = 10) -> Dict[str, Any]:
        """Get top groups by performance for a client."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Top groups by success (all-time, no date filter for compatibility)
            cursor.execute("""
                SELECT group_name, 
                       COUNT(*) as total,
                       SUM(CASE WHEN status = 'sent' THEN 1 ELSE 0 END) as successful,
                       SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed
                FROM broadcast_logs 
                WHERE client_id = ?
                GROUP BY group_name
                ORDER BY successful DESC
                LIMIT ?
            """, (client_id, limit))
            top_groups = [dict(row) for row in cursor.fetchall()]
            
            # Problem groups (most failures, all-time)
            cursor.execute("""
                SELECT group_name, 
                       COUNT(*) as total,
                       SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed,
                       error_message
                FROM broadcast_logs 
                WHERE client_id = ? AND status = 'failed'
                GROUP BY group_name
                ORDER BY failed DESC
                LIMIT ?
            """, (client_id, limit))
            problem_groups = [dict(row) for row in cursor.fetchall()]
            
            return {
                "top_groups": top_groups,
                "problem_groups": problem_groups
            }
    
    def get_client_account_stats(self, client_id: int, days: int = 30) -> List[Dict[str, Any]]:
        """Get per-account performance stats."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT 
                    ca.id,
                    ca.phone_number,
                    ca.display_name,
                    COUNT(bl.id) as total_sends,
                    SUM(CASE WHEN bl.status = 'sent' THEN 1 ELSE 0 END) as successful,
                    SUM(CASE WHEN bl.status = 'failed' THEN 1 ELSE 0 END) as failed,
                    ROUND(100.0 * SUM(CASE WHEN bl.status = 'sent' THEN 1 ELSE 0 END) / 
                          NULLIF(COUNT(bl.id), 0), 1) as success_rate
                FROM client_accounts ca
                LEFT JOIN broadcast_logs bl ON ca.id = bl.account_id
                WHERE ca.client_id = ?
                GROUP BY ca.id
                ORDER BY successful DESC
            """, (client_id,))
            
            return [dict(row) for row in cursor.fetchall()]
    
    def get_client_hourly_stats(self, client_id: int, days: int = 7) -> List[Dict[str, Any]]:
        """Get hourly broadcast patterns."""
        # Return empty for hourly stats since created_at column doesn't exist yet
        # Future broadcasts will have this data
        return []
    
    def get_client_campaign_history(self, client_id: int, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent campaigns with stats."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT 
                    c.id, c.name, c.status, c.created_at,
                    COUNT(bl.id) as total_sends,
                    SUM(CASE WHEN bl.status = 'sent' THEN 1 ELSE 0 END) as successful,
                    SUM(CASE WHEN bl.status = 'failed' THEN 1 ELSE 0 END) as failed
                FROM campaigns c
                LEFT JOIN broadcast_logs bl ON c.id = bl.campaign_id
                WHERE c.client_id = ?
                GROUP BY c.id
                ORDER BY c.created_at DESC
                LIMIT ?
            """, (client_id, limit))
            
            return [dict(row) for row in cursor.fetchall()]
    
    def get_global_analytics(self) -> Dict[str, Any]:
        """Get global analytics for admin."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Total clients
            cursor.execute("SELECT COUNT(*) as count FROM clients WHERE is_active = 1")
            total_clients = cursor.fetchone()['count']
            
            # Total accounts
            cursor.execute("SELECT COUNT(*) as count FROM client_accounts WHERE is_active = 1")
            total_accounts = cursor.fetchone()['count']
            
            # Total campaigns
            cursor.execute("SELECT COUNT(*) as count FROM campaigns")
            total_campaigns = cursor.fetchone()['count']
            
            # Active campaigns
            cursor.execute("SELECT COUNT(*) as count FROM campaigns WHERE status = 'running'")
            active_campaigns = cursor.fetchone()['count']
            
            # Today's stats
            today = datetime.now().strftime('%Y-%m-%d')
            cursor.execute("""
                SELECT 
                    COALESCE(SUM(total_broadcasts), 0) as today_broadcasts,
                    COALESCE(SUM(successful_sends), 0) as today_success,
                    COALESCE(SUM(failed_sends), 0) as today_failed
                FROM analytics_daily WHERE date = ?
            """, (today,))
            today_stats = dict(cursor.fetchone())
            
            return {
                "total_clients": total_clients,
                "total_accounts": total_accounts,
                "total_campaigns": total_campaigns,
                "active_campaigns": active_campaigns,
                "today": today_stats
            }
    
    # ============ MESSAGE TEMPLATES ============
    
    def get_client_templates(self, client_id: int) -> List[Dict[str, Any]]:
        """Get all message templates for a client."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, name, text_content, entities_json, has_media, media_type, created_at
                FROM message_templates WHERE client_id = ?
                ORDER BY created_at DESC
            """, (client_id,))
            return [dict(row) for row in cursor.fetchall()]
    
    def get_template_by_id(self, template_id: int) -> Optional[Dict[str, Any]]:
        """Get a message template by ID with all data for broadcasting."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM message_templates WHERE id = ?
            """, (template_id,))
            row = cursor.fetchone()
            if row:
                template = dict(row)
                # Parse entities JSON
                if template.get('entities_json'):
                    template['entities'] = json.loads(template['entities_json'])
                return template
            return None
    
    def delete_template(self, template_id: int) -> bool:
        """Delete a message template."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM message_templates WHERE id = ?", (template_id,))
            return cursor.rowcount > 0

    # ============ LOG BOT METHODS ============
    
    def get_all_log_bots(self) -> List[Dict[str, Any]]:
        """Get all log bot configurations with client names."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT lb.*, c.name as client_name 
                FROM log_bots lb
                JOIN clients c ON lb.client_id = c.id
                ORDER BY lb.created_at DESC
            """)
            return [dict(row) for row in cursor.fetchall()]

    def save_log_bot(self, client_id: int, bot_token: str, target_id: str, is_active: bool = True) -> bool:
        """Save or update a log bot configuration."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO log_bots (client_id, bot_token, target_id, is_active, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(client_id) DO UPDATE SET
                    bot_token = excluded.bot_token,
                    target_id = excluded.target_id,
                    is_active = excluded.is_active,
                    updated_at = excluded.updated_at
            """, (client_id, bot_token, target_id, 1 if is_active else 0, datetime.now().isoformat()))
            return cursor.rowcount > 0

    def delete_log_bot(self, client_id: int) -> bool:
        """Remove a log bot configuration."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM log_bots WHERE client_id = ?", (client_id,))
            return cursor.rowcount > 0

    def get_log_bot_by_client(self, client_id: int) -> Optional[Dict[str, Any]]:
        """Get log bot config for a specific client."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM log_bots WHERE client_id = ?", (client_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    # ============ ORDER METHODS ============

    def get_all_orders(self) -> List[Dict[str, Any]]:
        """Get all orders with client names."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT o.*, c.name as client_name 
                FROM orders o
                LEFT JOIN clients c ON o.client_id = c.id
                ORDER BY o.created_at DESC
            """)
            return [dict(row) for row in cursor.fetchall()]
            
    def create_order(self, product_name: str, client_id: Optional[int] = None, notes: Optional[str] = None) -> Dict[str, Any]:
        """Create a new order."""
        import uuid
        order_id = str(uuid.uuid4())[:8]
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO orders (order_id, client_id, product_name, notes, status)
                VALUES (?, ?, ?, ?, 'submitted')
            """, (order_id, client_id, product_name, notes))
            
            order_db_id = cursor.lastrowid
            
            # Fetch created order
            cursor.execute("""
                SELECT o.*, c.name as client_name 
                FROM orders o
                LEFT JOIN clients c ON o.client_id = c.id
                WHERE o.id = ?
            """, (order_db_id,))
            return dict(cursor.fetchone())

    def update_order(self, order_id: str, **kwargs) -> bool:
        """Update an order by its public order_id."""
        valid_fields = ['status', 'notes', 'product_name', 'client_id']
        updates = {k: v for k, v in kwargs.items() if k in valid_fields}
        
        if not updates:
            return False
            
        updates['updated_at'] = datetime.now().isoformat()
        
        set_clause = ", ".join([f"{k} = ?" for k in updates.keys()])
        values = list(updates.values())
        values.append(order_id)
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"UPDATE orders SET {set_clause} WHERE order_id = ?", tuple(values))
            return cursor.rowcount > 0

    def delete_order(self, order_id: str) -> bool:
        """Delete an order by its public order_id."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM orders WHERE order_id = ?", (order_id,))
            return cursor.rowcount > 0

    def get_order_by_id(self, order_id: str) -> Optional[Dict[str, Any]]:
        """Get specific order details."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT o.*, c.name as client_name 
                FROM orders o
                LEFT JOIN clients c ON o.client_id = c.id
                WHERE o.order_id = ?
            """, (order_id,))
            row = cursor.fetchone()
            return dict(row) if row else None


# Global database instance
db = Database(settings.DATABASE_PATH)
