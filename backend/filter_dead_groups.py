#!/usr/bin/env python3
"""
Dead Username Filter for EyeconBumps
====================================
Checks all usernames in grps.txt and filters out dead/invalid ones.
Outputs: grps_verified.txt (only valid groups)

Usage: python3 filter_dead_groups.py
"""

import json
import asyncio
import os
import sys
import re
import logging
from datetime import datetime

# Suppress Telethon background errors
logging.getLogger('telethon').setLevel(logging.CRITICAL)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import (
    UsernameNotOccupiedError, UsernameInvalidError, 
    FloodWaitError, ChannelPrivateError, TypeNotFoundError
)

# Configuration
API_ID = int(os.getenv("TELEGRAM_API_ID", "21219293"))
API_HASH = os.getenv("TELEGRAM_API_HASH", "cff5d321b676104840cf282a742381e0")
GRPS_FILE = os.path.join(os.path.dirname(__file__), "grps.txt")
OUTPUT_FILE = os.path.join(os.path.dirname(__file__), "grps_verified.txt")
DEAD_FILE = os.path.join(os.path.dirname(__file__), "grps_dead.txt")


# Settings
CHECK_DELAY = 1.5  # Slower checking to be safer
PROGRESS_FILE = os.path.join(os.path.dirname(__file__), "filter_progress.json")

def load_progress() -> dict:
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, 'r') as f:
            return json.load(f)
    return {"checked_count": 0, "valid": [], "dead": [], "private": [], "skipped": []}

def save_progress(data: dict):
    with open(PROGRESS_FILE, 'w') as f:
        json.dump(data, f)


def load_groups(filepath: str) -> list:
    """Load group links from file."""
    if not os.path.exists(filepath):
        print(f"❌ Error: {filepath} not found!")
        return []
    
    with open(filepath, 'r', encoding='utf-8') as f:
        links = []
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                links.append(line)
    
    # Remove duplicates
    seen = set()
    unique = []
    for link in links:
        if link not in seen:
            seen.add(link)
            unique.append(link)
    
    return unique


def parse_username(link: str) -> str:
    """Extract username from link."""
    link = link.strip()
    
    if link.startswith('@'):
        return link[1:]
    
    # Skip private invite links - can't check these easily
    if '/joinchat/' in link or '/+' in link:
        return None
    
    # Extract username from URL
    match = re.search(r't\.me/([a-zA-Z][a-zA-Z0-9_]{3,31})(?:\?|$|/)', link)
    if match:
        uname = match.group(1)
        if uname.lower() not in ['joinchat', 'addstickers', 'addtheme', 'share', 'addlist', 'c']:
            return uname
    
    # Fallback
    if '/' in link:
        parts = link.rstrip('/').split('/')
        last = parts[-1]
        if last and not last.startswith('+') and len(last) >= 4:
            return last
    
    return None


async def get_accounts():
    """Get all available accounts from database."""
    import sqlite3
    db_path = os.getenv("DATABASE_PATH")
    if not db_path:
        # Auto-detect
        candidates = [
            "/opt/eyeconlabs/data/eyeconbumps_webapp.db",
            os.path.join(os.path.dirname(__file__), "eyeconbumps_webapp.db"),
            os.path.join(os.path.dirname(__file__), "..", "data", "eyeconbumps_webapp.db"),
        ]
        for p in candidates:
            if os.path.exists(p):
                db_path = p
                break
    
    if not db_path:
        print("❌ Database not found!")
        return []

    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM client_accounts WHERE session_string IS NOT NULL")
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]
    except Exception as e:
        print(f"❌ Database error: {e}")
        return []


async def check_username(client: TelegramClient, username: str) -> tuple:
    """
    Check if username exists and is accessible.
    Returns: (is_valid, reason)
    """
    try:
        entity = await client.get_entity(username)

        # Check if it's a group/channel (not a user)
        if hasattr(entity, 'broadcast') or hasattr(entity, 'megagroup') or hasattr(entity, 'gigagroup'):
            return (True, "channel/group")
        elif hasattr(entity, 'participants_count'):
            return (True, "group")
        else:
            # It's a user, not a group
            return (False, "user_not_group")

    except UsernameNotOccupiedError:
        return (False, "not_found")
    except UsernameInvalidError:
        return (False, "invalid")
    except ChannelPrivateError:
        return (True, "private")  # Exists but private - still valid
    except TypeNotFoundError:
        return (False, "not_found") # Entity type not found, likely dead
    except FloodWaitError as e:
        return (None, f"flood:{e.seconds}")
    except Exception as e:
        error = str(e).lower()
        if "nobody is using" in error or "not found" in error:
            return (False, "not_found")
        elif "private" in error:
            return (True, "private")  # Private but exists
        return (None, str(e)[:30])


async def main():

    print("""
╔══════════════════════════════════════════════════════════════╗
║           DEAD USERNAME FILTER v2.1 (STABLE)                 ║
║  Checks usernames across multiple accounts to avoid bans     ║
╚══════════════════════════════════════════════════════════════╝
    """)

    # Load groups
    groups = load_groups(GRPS_FILE)
    if not groups:
        return
    print(f"📋 Loaded {len(groups)} groups")

    # Load progress
    progress = load_progress()
    start_idx = progress["checked_count"]
    valid_groups = progress.get("valid", [])
    dead_groups = progress.get("dead", [])
    private_groups = progress.get("private", [])
    skipped = progress.get("skipped", [])

    if start_idx > 0:
        print(f"🔄 Resuming from index {start_idx} (Valid: {len(valid_groups)}, Dead: {len(dead_groups)})")

    # Get all accounts
    all_accounts = await get_accounts()
    if not all_accounts:
        print("❌ No accounts found!")
        return

    print(f"👥 Loaded {len(all_accounts)} accounts for rotation")

    # Connect clients
    clients = []
    for acc in all_accounts:
        try:
            client = TelegramClient(StringSession(acc['session_string']), API_ID, API_HASH)
            await client.connect()
            if await client.is_user_authorized():
                clients.append({"client": client, "id": acc['id'], "flood_until": 0})
            else:
                await client.disconnect()
        except:
            pass

    print(f"✅ {len(clients)} clients connected and ready")
    if not clients:
        return

    # Processing loop
    current_client_idx = 0

    try:
        for i in range(start_idx, len(groups)):
            link = groups[i]

            # Rotate client if needed
            attempts = 0
            found_client = False
            while attempts < len(clients) + 1: # +1 to allow one full rotation before waiting
                c = clients[current_client_idx]
                now = asyncio.get_event_loop().time()

                # Check flood wait
                if now < c["flood_until"]:
                    current_client_idx = (current_client_idx + 1) % len(clients)
                    attempts += 1
                else:
                    found_client = True
                    break # Found a valid client

            if not found_client:
                 # All clients flooded
                wait_time = min((cl["flood_until"] for cl in clients), default=now) - now
                if wait_time > 0:
                    print(f"⏳ All accounts flooded. Waiting {int(wait_time)}s...")
                    await asyncio.sleep(wait_time + 1)
                # Reset attempts? No, just use current client after wait

            # Use current client (guaranteed to be ready or we waited)
            c = clients[current_client_idx]

            username = parse_username(link)

            if not username:
                if link not in skipped:
                    skipped.append(link)
                #print(f"⏩ [{i+1}/{len(groups)}] Skipped (invite): {link[:30]}")
            else:
                try:
                    is_valid, reason = await check_username(c["client"], username)

                    if is_valid is None:
                        # FloodWait or Error - Switch account, RETRY same group
                        if reason.startswith("flood:"):
                            wait_sec = int(reason.split(":")[1])
                            print(f"⏳ Acc {c['id']} flood wait: {wait_sec}s -> Switching")
                            c["flood_until"] = asyncio.get_event_loop().time() + wait_sec
                        else:
                            print(f"⚠️  Acc {c['id']} error: {reason} -> Switching")

                        # Move to next client and retry checking THIS group
                        current_client_idx = (current_client_idx + 1) % len(clients)
                        i -= 1 # Stay on this index (retry)

                        # Add a small penalty to avoid rapid loops on errors
                        await asyncio.sleep(1)
                        continue

                    if is_valid:
                        if link not in valid_groups:
                            valid_groups.append(link)
                            if reason == "private":
                                if link not in private_groups:
                                    private_groups.append(link)
                                print(f"🔒 [{i+1}/{len(groups)}] Private: @{username}")
                            else:
                                print(f"✅ [{i+1}/{len(groups)}] Valid: @{username}")
                    else:
                        if link not in dead_groups:
                            dead_groups.append(link)
                            print(f"❌ [{i+1}/{len(groups)}] Dead: @{username} ({reason})")

                except Exception as e:
                     # Catch-all for Telethon errors (like TypeNotFoundError)
                    print(f"⚠️  Acc {c['id']} CRITICAL error check: {e} -> Switching")
                    current_client_idx = (current_client_idx + 1) % len(clients)
                    i -= 1 # Retry
                    await asyncio.sleep(1)
                    continue

            # Progress update
            # We only increment if we didn't 'continue' above
            progress["checked_count"] = i + 1
            progress["valid"] = valid_groups
            progress["dead"] = dead_groups
            progress["private"] = private_groups
            progress["skipped"] = skipped

            if i % 20 == 0:
                save_progress(progress)

            await asyncio.sleep(CHECK_DELAY)

    except KeyboardInterrupt:
        print("\n🛑 Stopped by user. Progress saved.")
    except Exception as e:
        print(f"\n❌ Script crashed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print("💾 Saving final progress...")
        save_progress(progress)
        print("🔌 Disconnecting clients...")
        for c in clients:
            try:
                await c["client"].disconnect()
            except:
                pass

    # Final Save
    total_valid = valid_groups + skipped

    try:
        with open(OUTPUT_FILE, 'w') as f:
            for link in total_valid:
                f.write(f"{link}\n")
    except Exception as e:
        print(f"❌ Failed to write output file: {e}")

    try:
        with open(DEAD_FILE, 'w') as f:
            for link in dead_groups:
                f.write(f"{link}\n")
    except:
        pass

    print(f"""
{'='*60}
📊 FILTER COMPLETE
{'='*60}
✅ Valid groups:     {len(valid_groups)}
🔒 Private groups:   {len(private_groups)} (included in valid)
⏩ Invite links:     {len(skipped)} (kept - can't verify)
❌ Dead groups:      {len(dead_groups)}
{'='*60}
📄 Valid saved to:   {OUTPUT_FILE}
📄 Dead saved to:    {DEAD_FILE}
{'='*60}

Now use grps_verified.txt instead of grps.txt!
    """)


if __name__ == "__main__":
    asyncio.run(main())
