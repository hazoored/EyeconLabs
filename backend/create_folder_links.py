#!/usr/bin/env python3
"""
Folder Link Generator for EyeconBumps
=====================================
This script:
1. Logs into 3 accounts from the database
2. Joins all groups from grps.txt (distributed across accounts to avoid rate limits)
3. Creates 6 chat folders per account (18 total) with shareable links
4. Ensures no duplicates across folders
5. Verifies all groups are from grps.txt

Usage: python3 create_folder_links.py
"""

import asyncio
import os
import sys
import re
import json
from datetime import datetime
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.tl.functions.channels import JoinChannelRequest
from telethon.tl.functions.messages import (
    ImportChatInviteRequest, 
    CreateChatlistRequest,
    ExportChatlistInviteRequest,
    GetDialogFiltersRequest,
    UpdateDialogFilterRequest
)
from telethon.tl.types import (
    InputChatlistDialogFilter,
    DialogFilter,
    InputPeerChannel,
    InputPeerChat
)
from telethon.errors import (
    FloodWaitError, UserAlreadyParticipantError, ChannelPrivateError,
    InviteHashExpiredError, InviteHashInvalidError, UserBannedInChannelError,
    ChannelsTooMuchError
)

# Configuration
API_ID = int(os.getenv("TELEGRAM_API_ID", "21219293"))
API_HASH = os.getenv("TELEGRAM_API_HASH", "cff5d321b676104840cf282a742381e0")
GRPS_FILE = os.path.join(os.path.dirname(__file__), "grps.txt")
PROGRESS_FILE = os.path.join(os.path.dirname(__file__), "join_progress.json")
FOLDER_LINKS_FILE = os.path.join(os.path.dirname(__file__), "folder_links.txt")

# Settings
ACCOUNTS_TO_USE = 3  # Use first 3 accounts
FOLDERS_PER_ACCOUNT = 6  # Create 6 folders per account
GROUPS_PER_FOLDER = 100  # Max 100 groups per folder (Telegram limit)
JOIN_DELAY = 3  # Seconds between joins (conservative)
FLOOD_WAIT_BUFFER = 1.2  # Multiply flood wait by this


def load_group_links(filepath: str) -> list:
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
    
    # Remove duplicates while preserving order
    seen = set()
    unique = []
    for link in links:
        if link not in seen:
            seen.add(link)
            unique.append(link)
    
    return unique


def parse_group_link(link: str) -> dict:
    """Parse a Telegram group link."""
    link = link.strip()
    
    if link.startswith('@'):
        return {"type": "username", "value": link[1:]}
    
    # Private invite
    joinchat = re.search(r't\.me/joinchat/([a-zA-Z0-9_-]+)', link)
    if joinchat:
        return {"type": "invite", "value": joinchat.group(1)}
    
    plus = re.search(r't\.me/\+([a-zA-Z0-9_-]+)', link)
    if plus:
        return {"type": "invite", "value": plus.group(1)}
    
    # Public username
    username = re.search(r't\.me/([a-zA-Z][a-zA-Z0-9_]{3,31})(?:\?|$|/)', link)
    if username:
        uname = username.group(1)
        if uname.lower() not in ['joinchat', 'addstickers', 'addtheme', 'share', 'addlist', 'c']:
            return {"type": "username", "value": uname}
    
    # Fallback
    if '/' in link:
        parts = link.rstrip('/').split('/')
        last = parts[-1]
        if last and not last.startswith('+') and len(last) >= 4:
            return {"type": "username", "value": last}
    
    return {"type": "unknown", "value": link}


def load_progress() -> dict:
    """Load join progress from file."""
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, 'r') as f:
            return json.load(f)
    return {"joined_groups": [], "joined_by_account": {}, "folders_created": []}


def save_progress(progress: dict):
    """Save join progress to file."""
    with open(PROGRESS_FILE, 'w') as f:
        json.dump(progress, f, indent=2)


async def get_accounts():
    """Get accounts from database using sqlite3 directly."""
    import sqlite3
    
    # Try to find the database
    db_path = os.getenv("DATABASE_PATH")
    if not db_path or not os.path.exists(db_path):
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
        print("❌ Database not found! Please set DATABASE_PATH env var.")
        return []

    print(f"📂 Using database: {db_path}")
    
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM client_accounts WHERE session_string IS NOT NULL LIMIT ?", (ACCOUNTS_TO_USE,))
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    except Exception as e:
        print(f"❌ Database error: {e}")
        return []


async def join_group(client: TelegramClient, link: str, parsed: dict) -> tuple:
    """
    Join a single group. Returns (success, entity_or_error).
    """
    try:
        if parsed["type"] == "username":
            result = await client(JoinChannelRequest(parsed["value"]))
            entity = await client.get_entity(parsed["value"])
            return (True, entity)
        
        elif parsed["type"] == "invite":
            result = await client(ImportChatInviteRequest(parsed["value"]))
            # For invites, the result contains the chat
            if hasattr(result, 'chats') and result.chats:
                return (True, result.chats[0])
            return (True, None)
        
        return (False, "Unknown link format")
    
    except UserAlreadyParticipantError:
        # Already joined - get entity
        try:
            if parsed["type"] == "username":
                entity = await client.get_entity(parsed["value"])
                return (True, entity)
        except:
            pass
        return (True, None)
    
    except FloodWaitError as e:
        return (False, f"FLOOD:{e.seconds}")
    
    except ChannelsTooMuchError:
        return (False, "LIMIT")
    
    except (ChannelPrivateError, InviteHashExpiredError, InviteHashInvalidError, UserBannedInChannelError) as e:
        return (False, str(e)[:50])
    
    except Exception as e:
        return (False, str(e)[:50])


async def create_folder(client: TelegramClient, folder_name: str, peer_ids: list) -> str:
    """
    Create a chat folder and return the shareable link.
    """
    try:
        # First, get existing filters to find next available ID
        filters = await client(GetDialogFiltersRequest())
        filters_list = filters if isinstance(filters, list) else getattr(filters, 'filters', [])
        
        # Find next available filter ID (start from 2, 0 and 1 are reserved)
        used_ids = {getattr(f, 'id', 0) for f in filters_list}
        new_id = 2
        while new_id in used_ids:
            new_id += 1
        
        # Convert peer IDs to InputPeerChannel
        input_peers = []
        for peer_id in peer_ids:
            try:
                entity = await client.get_entity(peer_id)
                if hasattr(entity, 'access_hash'):
                    input_peers.append(InputPeerChannel(
                        channel_id=entity.id,
                        access_hash=entity.access_hash
                    ))
            except Exception as e:
                print(f"    ⚠️  Could not get entity for {peer_id}: {e}")
        
        if not input_peers:
            return None
        
        # Create the folder as a shareable chatlist
        print(f"    📁 Creating folder '{folder_name}' with {len(input_peers)} chats...")
        
        # Use CreateChatlistRequest to create a shareable folder
        result = await client(ExportChatlistInviteRequest(
            chatlist=InputChatlistDialogFilter(filter_id=new_id),
            title=folder_name,
            peers=input_peers[:100]  # Max 100 peers
        ))
        
        if hasattr(result, 'invite') and hasattr(result.invite, 'url'):
            return result.invite.url
        
        return None
        
    except Exception as e:
        print(f"    ❌ Failed to create folder: {e}")
        
        # Fallback: Try creating a regular filter first, then export
        try:
            new_filter = DialogFilter(
                id=new_id,
                title=folder_name,
                pinned_peers=[],
                include_peers=input_peers[:100],
                exclude_peers=[],
                contacts=False,
                non_contacts=False,
                groups=True,
                broadcasts=True,
                bots=False,
                exclude_muted=False,
                exclude_read=False,
                exclude_archived=False
            )
            
            await client(UpdateDialogFilterRequest(id=new_id, filter=new_filter))
            await asyncio.sleep(1)
            
            # Now export it
            result = await client(ExportChatlistInviteRequest(
                chatlist=InputChatlistDialogFilter(filter_id=new_id),
                title=folder_name,
                peers=input_peers[:100]
            ))
            
            if hasattr(result, 'invite') and hasattr(result.invite, 'url'):
                return result.invite.url
                
        except Exception as e2:
            print(f"    ❌ Fallback also failed: {e2}")
        
        return None


async def main():
    print("""
╔══════════════════════════════════════════════════════════════╗
║       EYECONBUMPS FOLDER LINK GENERATOR v1.0                 ║
║                                                              ║
║  This script will:                                           ║
║  1. Join all groups from grps.txt (distributed across 3 accs)║
║  2. Create 6 shareable folder links per account (18 total)   ║
║  3. Save folder links to folder_links.txt                    ║
╚══════════════════════════════════════════════════════════════╝
    """)
    
    # Load groups
    groups = load_group_links(GRPS_FILE)
    if not groups:
        print("❌ No groups found in grps.txt!")
        return
    
    print(f"📋 Loaded {len(groups)} unique groups from grps.txt")
    
    # Load progress
    progress = load_progress()
    already_joined = set(progress.get("joined_groups", []))
    print(f"📊 Already joined: {len(already_joined)} groups")
    
    # Get accounts
    accounts = await get_accounts()
    if not accounts:
        print("❌ No accounts found in database!")
        return
    
    print(f"👥 Using {len(accounts)} accounts")
    
    # Connect all clients
    clients = []
    for acc in accounts:
        client = TelegramClient(
            StringSession(acc['session_string']),
            API_ID,
            API_HASH
        )
        await client.connect()
        
        if await client.is_user_authorized():
            me = await client.get_me()
            print(f"  ✅ Account {acc['id']}: {me.first_name} (@{me.username or 'N/A'})")
            clients.append({
                "client": client,
                "account": acc,
                "me": me,
                "joined": [],
                "flood_until": 0
            })
        else:
            print(f"  ❌ Account {acc['id']}: Session expired")
            await client.disconnect()
    
    if not clients:
        print("❌ No valid clients!")
        return
    
    # ============================================
    # PHASE 1: JOIN ALL GROUPS
    # ============================================
    print(f"\n{'='*60}")
    print("PHASE 1: JOINING GROUPS")
    print(f"{'='*60}")
    
    groups_to_join = [g for g in groups if g not in already_joined]
    print(f"📊 Groups to join: {len(groups_to_join)}")
    
    if groups_to_join:
        # Distribute groups across accounts round-robin
        client_idx = 0
        joined_count = 0
        failed_count = 0
        
        for i, link in enumerate(groups_to_join):
            # Find next available client (not in flood wait)
            attempts = 0
            while attempts < len(clients):
                c = clients[client_idx]
                if datetime.now().timestamp() >= c["flood_until"]:
                    break
                client_idx = (client_idx + 1) % len(clients)
                attempts += 1
            
            if attempts >= len(clients):
                # All clients in flood wait, wait for shortest
                min_wait = min(c["flood_until"] for c in clients) - datetime.now().timestamp()
                if min_wait > 0:
                    print(f"\n⏳ All accounts in flood wait. Waiting {min_wait:.0f}s...")
                    await asyncio.sleep(min_wait + 1)
            
            c = clients[client_idx]
            parsed = parse_group_link(link)
            
            success, result = await join_group(c["client"], link, parsed)
            
            if success:
                joined_count += 1
                progress["joined_groups"].append(link)
                c["joined"].append({"link": link, "entity": result})
                print(f"✅ [{i+1}/{len(groups_to_join)}] Acc{c['account']['id']}: Joined {parsed.get('value', link)[:30]}")
                await asyncio.sleep(JOIN_DELAY)
            
            elif isinstance(result, str) and result.startswith("FLOOD:"):
                wait = int(result.split(":")[1]) * FLOOD_WAIT_BUFFER
                c["flood_until"] = datetime.now().timestamp() + wait
                print(f"⏳ [{i+1}/{len(groups_to_join)}] Acc{c['account']['id']}: FloodWait {wait:.0f}s")
                # Don't increment failed, retry with next account
            
            elif result == "LIMIT":
                print(f"🛑 [{i+1}/{len(groups_to_join)}] Acc{c['account']['id']}: Channel limit reached!")
                # Remove this client from rotation
                clients = [x for x in clients if x != c]
                if not clients:
                    print("❌ All accounts hit channel limit!")
                    break
            
            else:
                failed_count += 1
                print(f"❌ [{i+1}/{len(groups_to_join)}] Acc{c['account']['id']}: {result}")
                await asyncio.sleep(0.5)
            
            # Move to next client
            if clients:
                client_idx = (client_idx + 1) % len(clients)
            
            # Save progress every 50 joins
            if (i + 1) % 50 == 0:
                save_progress(progress)
                print(f"💾 Progress saved: {joined_count} joined, {failed_count} failed")
        
        save_progress(progress)
        print(f"\n📊 PHASE 1 COMPLETE: {joined_count} joined, {failed_count} failed")
    
    # ============================================
    # PHASE 2: CREATE FOLDER LINKS
    # ============================================
    print(f"\n{'='*60}")
    print("PHASE 2: CREATING FOLDER LINKS")
    print(f"{'='*60}")
    
    # Get all joined groups from all clients
    all_joined_entities = []
    for c in clients:
        # Fetch dialogs to get all joined groups
        print(f"  📥 Fetching dialogs for Account {c['account']['id']}...")
        dialogs = await c["client"].get_dialogs(limit=2000)
        
        for d in dialogs:
            if d.is_group or d.is_channel:
                all_joined_entities.append({
                    "client": c,
                    "entity": d.entity,
                    "id": d.entity.id,
                    "name": d.name
                })
    
    print(f"  📊 Total groups/channels found: {len(all_joined_entities)}")
    
    # Filter to only groups from grps.txt
    # Build a set of usernames from grps.txt for verification
    grps_usernames = set()
    for link in groups:
        parsed = parse_group_link(link)
        if parsed["type"] == "username":
            grps_usernames.add(parsed["value"].lower())
    
    # Filter entities to only those in grps.txt
    verified_entities = []
    for e in all_joined_entities:
        username = getattr(e["entity"], 'username', None)
        if username and username.lower() in grps_usernames:
            verified_entities.append(e)
    
    print(f"  ✅ Verified groups (in grps.txt): {len(verified_entities)}")
    
    # Distribute verified entities across 18 folders (6 per account)
    total_folders = len(clients) * FOLDERS_PER_ACCOUNT
    groups_per_folder = (len(verified_entities) // total_folders) + 1
    
    print(f"  📁 Creating {total_folders} folders ({FOLDERS_PER_ACCOUNT} per account)")
    print(f"  📊 ~{groups_per_folder} groups per folder")
    
    folder_links = []
    entity_idx = 0
    
    for client_idx, c in enumerate(clients):
        print(f"\n  👤 Account {c['account']['id']} ({c['me'].first_name}):")
        
        for folder_num in range(FOLDERS_PER_ACCOUNT):
            # Get groups for this folder
            folder_entities = verified_entities[entity_idx:entity_idx + GROUPS_PER_FOLDER]
            entity_idx += GROUPS_PER_FOLDER
            
            if not folder_entities:
                break
            
            folder_name = f"EyeconBumps {client_idx + 1}-{folder_num + 1}"
            
            # Get peer IDs
            peer_ids = [e["id"] for e in folder_entities]
            
            # Create folder and get link
            link = await create_folder(c["client"], folder_name, peer_ids)
            
            if link:
                folder_links.append(link)
                print(f"    ✅ Folder '{folder_name}': {link}")
            else:
                print(f"    ❌ Failed to create folder '{folder_name}'")
            
            await asyncio.sleep(2)  # Delay between folder creations
    
    # Save folder links
    with open(FOLDER_LINKS_FILE, 'w') as f:
        for link in folder_links:
            f.write(f"{link}\n")
    
    print(f"\n{'='*60}")
    print(f"✅ DONE! Created {len(folder_links)} folder links")
    print(f"📄 Saved to: {FOLDER_LINKS_FILE}")
    print(f"{'='*60}")
    
    # Cleanup
    for c in clients:
        await c["client"].disconnect()


if __name__ == "__main__":
    asyncio.run(main())
