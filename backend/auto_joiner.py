import sys
import os
import asyncio
import re
import random
import httpx
import sqlite3
from datetime import datetime

# --- SYSTEM SETTINGS ---
os.environ["DATABASE_PATH"] = "/opt/eyeconlabs/data/eyeconbumps_webapp.db"
VPS_BACKEND_DIR = '/opt/eyeconlabs/backend'
if VPS_BACKEND_DIR not in sys.path:
    sys.path.insert(0, VPS_BACKEND_DIR)

try:
    from database import db
    from config import settings
except ImportError:
    # Manual fallback for different environments
    sys.path.append('/opt/eyeconlabs/backend')
    from database import db
    from config import settings

from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.tl.functions.messages import GetDialogFiltersRequest, UpdateDialogFilterRequest
from telethon.tl.functions.chatlists import CheckChatlistInviteRequest, JoinChatlistInviteRequest
from telethon.tl.types import DialogFilterDefault, DialogFilterChatlist
from telethon.tl.types.chatlists import ChatlistInviteAlready, ChatlistInvite
from telethon.errors import FloodWaitError
from telethon.tl.types import Channel, Chat, User
from telethon.tl.functions.channels import LeaveChannelRequest, JoinChannelRequest
from telethon.tl.functions.messages import DeleteChatRequest, DeleteHistoryRequest

# --- CONFIGURATION ---
DISCORD_WEBHOOK = "https://discord.com/api/webhooks/1467246755434332411/Z5MfbbPBGHYuQsBXx-2yeRIa4N0lar8EnC790MVQ2zyX7ilz8_fqk9fMNnRaBqxnixgN"
DISCORD_USER_ID = "1352574941085564950"

FOLDER_LINKS = [
    "https://t.me/addlist/JC_cD1R7ibYwZmI0",
    "https://t.me/addlist/QWI8F3wV5Ok2YjJk",
    "https://t.me/addlist/MLYSiwlZ7uU5NzM1",
    "https://t.me/addlist/In__y5M3f-hhYWE1",
    "https://t.me/addlist/wRrLc8l31iI4MDQ0",
    "https://t.me/addlist/_at1nLRF6ABjYjc1",
    "https://t.me/addlist/aRtYnq1CSL42NTM0",
    "https://t.me/addlist/2r-oeCI0E-FiNTg0",
    "https://t.me/addlist/QlgDHVRRo21jMTE0",
    "https://t.me/addlist/KedMVZMhcnBmYmJk",
    "https://t.me/addlist/uqkQLkmqHeI1MTZk",
    "https://t.me/addlist/7gkl4lRYEtNmMjk0",
    "https://t.me/addlist/db7XGRc0JPZhNmNk",
    "https://t.me/addlist/2fHSP9aB-Ck4MTc0",
    "https://t.me/addlist/6xZiJrhtLPs2MWY0"
]

API_ID = int(os.getenv("TELEGRAM_API_ID", "21219293"))
API_HASH = os.getenv("TELEGRAM_API_HASH", "cff5d321b676104840cf282a742381e0")

async def send_discord_summary(results, debug_info=""):
    mention = f"<@{DISCORD_USER_ID}>"
    total_accounts = len(results)
    
    desc = f"🚀 **Automation Summary for {total_accounts} Accounts**\n\n"
    
    if not results:
        desc += "❓ **No accounts were processed.**\n"
        if debug_info:
            desc += f"```\n[DEBUG INFO]\n{debug_info}\n```"

    for r in results:
        status_emoji = "✅" if r['success'] else "❌"
        account_info = f"{status_emoji} **{r['display_name']}** ({r['phone']}): **{r['final_count']}** chats, **{r['folders_joined']}**/15 folders.\n"
        if not r['success']:
            account_info += f"   *Error: {r['error_msg'][:60]}*\n"
        desc += account_info

    payload = {
        "content": f"{mention} **Folder Joiner Automation Update**",
        "embeds": [{
            "title": "EyeconLabs Global Joiner Results",
            "description": desc,
            "color": 0x00ff00 if results else 0xff0000,
            "timestamp": datetime.now().isoformat()
        }]
    }
    
    try:
        async with httpx.AsyncClient() as client:
            await client.post(DISCORD_WEBHOOK, json=payload)
    except Exception as e:
        print(f"Failed to send Discord webhook: {e}")

async def process_account(account_summary):
    """Refactored: Fetch full details including session string per account"""
    acc_id = account_summary['id']
    
    # Fetch full account data to get the session string
    # This keeps database.py unchanged
    account = db.get_account_by_id(acc_id)
    if not account:
        return {
            "display_name": account_summary.get('display_name', 'Unknown'),
            "phone": account_summary.get('phone_number', 'Unknown'),
            "success": False,
            "error_msg": "Could not fetch full details from DB",
            "final_count": 0,
            "folders_joined": 0
        }

    phone = account['phone_number']
    display_name = account['display_name'] or phone
    session = account.get('session_string')
    
    result = {
        "display_name": display_name,
        "phone": phone,
        "success": False,
        "final_count": 0,
        "folders_joined": 0,
        "error_msg": ""
    }

    if not session:
        result['error_msg'] = "No session string found"
        return result
    
    client = TelegramClient(StringSession(session), API_ID, API_HASH, connection_retries=5)
    try:
        print(f"\n[AUTO] processing {display_name} ({phone})...")
        await asyncio.wait_for(client.connect(), timeout=15)
        
        if not await client.is_user_authorized():
            result['error_msg'] = "Session invalid"
            return result

        # --- PHASE 0: NUCLEAR WIPE ---
        for p in range(2):
            dialogs = await client.get_dialogs()
            if not dialogs: break
            for d in dialogs:
                try:
                    if isinstance(d.entity, Channel): await client(LeaveChannelRequest(d.entity))
                    elif isinstance(d.entity, Chat): await client(DeleteChatRequest(d.entity.id))
                    elif isinstance(d.entity, User): await client(DeleteHistoryRequest(d.entity, max_id=0, just_clear=False, revoke=True))
                    await asyncio.sleep(0.04)
                except: pass
            await asyncio.sleep(1)

        # --- PHASE 1: BULK FOLDERS ---
        master_chats = {}
        folders_done = 0
        for idx, link in enumerate(FOLDER_LINKS):
            slug = link.split('/')[-1]
            try:
                res = await asyncio.wait_for(client(CheckChatlistInviteRequest(slug=slug)), timeout=20)
                if hasattr(res, 'chats'):
                    for c in res.chats: master_chats[c.id] = c
                raw_peers = []
                if isinstance(res, ChatlistInvite): raw_peers = res.peers
                elif isinstance(res, ChatlistInviteAlready): raw_peers = getattr(res, 'missing_peers', [])
                if raw_peers:
                    await asyncio.wait_for(client(JoinChatlistInviteRequest(slug=slug, peers=raw_peers)), timeout=40)
                await asyncio.sleep(1)
                filters = await client(GetDialogFiltersRequest())
                for f in filters:
                    if isinstance(f, DialogFilterChatlist):
                        await client(UpdateDialogFilterRequest(id=f.id, filter=None))
                folders_done += 1
                await asyncio.sleep(0.5)
            except: pass
        
        # --- PHASE 2: MANUAL SWEEP ---
        await asyncio.sleep(8)
        current_dialogs = await client.get_dialogs()
        joined_ids = {d.id for d in current_dialogs}
        for c_id, chat in master_chats.items():
            if c_id not in joined_ids:
                try:
                    await client(JoinChannelRequest(chat))
                    joined_ids.add(c_id)
                    await asyncio.sleep(random.uniform(0.7, 1.3))
                except Exception as e:
                    if "CHANNELS_TOO_MUCH" in str(e): break
                    await asyncio.sleep(1.2)

        final_dialogs = await client.get_dialogs()
        result['final_count'] = final_dialogs.total
        result['folders_joined'] = folders_done
        result['success'] = True
        print(f"[DONE] {display_name}: {result['final_count']} chats")

    except Exception as e:
        result['error_msg'] = str(e)
    finally:
        await client.disconnect()
    
    return result

async def main():
    print("\n" + "="*50)
    print("      EYECON LABS AUTOMATION: GLOBAL JOINER")
    print("="*50 + "\n")
    
    db_path = settings.DATABASE_PATH
    abs_db_path = os.path.abspath(db_path)
    print(f"DEBUG: Configured DB Path: {db_path}")
    print(f"DEBUG: Resolved DB Path: {abs_db_path}")
    print(f"DEBUG: File Exists: {os.path.exists(abs_db_path)}")
    
    debug_status = f"Resolved Path: {abs_db_path}\nFile Exists: {os.path.exists(abs_db_path)}"
    
    # Try manual inspect if it keeps failing
    try:
        conn = sqlite3.connect(abs_db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [t[0] for t in cursor.fetchall()]
        print(f"DEBUG: Detected Tables: {tables}")
        debug_status += f"\nTables: {tables}"
        
        if 'client_accounts' in tables:
            cursor.execute("SELECT count(*) FROM client_accounts;")
            c = cursor.fetchone()[0]
            print(f"DEBUG: Entry count in client_accounts: {c}")
            debug_status += f"\nRow Count: {c}"
        conn.close()
    except Exception as e:
        print(f"DEBUG: sqlite3 inspection failed: {e}")
        debug_status += f"\nInspection Error: {e}"

    try:
        accounts_list = db.get_all_accounts()
    except Exception as e:
        print(f"CRITICAL: db.get_all_accounts() failed: {e}")
        accounts_list = []
        debug_status += f"\nAPI Error: {e}"

    print(f"Processing {len(accounts_list)} accounts...")
    
    if not accounts_list:
        print("No accounts found. Sending notification...")
        await send_discord_summary([], debug_status)
        return

    results = []
    for acc in accounts_list:
        res = await process_account(acc)
        results.append(res)
        await asyncio.sleep(5)

    print("Success! Sending results to Discord.")
    await send_discord_summary(results)

if __name__ == "__main__":
    asyncio.run(main())
