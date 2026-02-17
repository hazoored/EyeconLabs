"""
Topics Scanner Script - Deep Analysis Version
Scans all groups for specific topics and provides detailed diagnostics.
"""
import asyncio
import os
import sys
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.tl.functions.channels import GetForumTopicsRequest
from telethon.tl.types import Channel, Chat
import unicodedata
import re

# Target Platforms to look for
PLATFORM_TOPICS = [
    "Instagram", "Telegram", "Discord", "Twitter", "Facebook", 
    "TikTok", "WhatsApp", "YouTube", "Snapchat", "Steam", 
    "Roblox", "GFX", "Netflix", "Spotify", "Apple"
]

# Target Market niches to find more topics
MARKET_TOPICS = [
    "Sales", "Buying", "Selling", "Trade", "Market", "Community", 
    "Support", "Main", "General", "Verify", "Trust", "Reviews", 
    "Feedback", "Exchange", "Bulk", "Panel", "SMM"
]

TARGET_TOPICS = PLATFORM_TOPICS + MARKET_TOPICS

def standardize_topic_name(name: str) -> str:
    """Smartly map topic names to standard versions and remove fancy fonts/emojis."""
    if not name: return ""
    
    # 1. Normalize fancy fonts (Unicode NFKC)
    # This converts 𝐈𝐧𝐬𝐭𝐚𝐠𝐫𝐚𝐦 -> Instagram, 𝕏 -> X, etc.
    n = unicodedata.normalize('NFKC', name)
    
    # 2. Strip emojis and non-standard characters
    n = re.sub(r'[^\x00-\x7F]+', ' ', n)
    
    # 3. Basic cleanup
    n = n.lower().strip()
    
    # Platform Mappings (Most important)
    if "instagram" in n: return "Instagram"
    if "telegram" in n: return "Telegram"
    if "discord" in n or "dicord" in n: return "Discord"
    if "twitter" in n or n == "x" or " x " in n or "/x" in n or "x/" in n or n.startswith("x "): 
        return "Twitter"
    if "tiktok" in n or "tik tok" in n or "tixtok" in n: return "TikTok"
    if "whatsapp" in n or "whatsaap" in n or "what's app" in n: return "WhatsApp"
    if "youtube" in n or "you tube" in n: return "YouTube"
    if "snapchat" in n or "snapchap" in n: return "Snapchat"
    if "facebook" in n or "face book" in n: return "Facebook"
    
    # Fallback / General Mappings
    if "general" in n or n == "main" or "chat" == n or n == "welcome": 
        return "General"
    
    if "other" in n or "service" in n or "account" in n or n == "misc" or n == "bulk":
        return "Others"

    # Common Niche Mappings
    if "exchange" in n: return "Exchange"
    if "graphic" in n or "gfx" in n: return "GFX"
    if "panel" in n: return "Panel"
    if "gaming" in n: return "Gaming"
    if "steam" in n: return "Steam"
    if "roblox" in n: return "Roblox"
    if "verify" in n or "verification" in n: return "Verify"
    
    # Handle capitalize for others
    return n.capitalize() if len(n) > 1 else n.upper()

async def scan_topics(api_id, api_hash, logout=False):
    session_path = os.path.join(os.path.dirname(__file__), "admin_topics")
    
    if logout:
        if os.path.exists(f"{session_path}.session"):
            os.remove(f"{session_path}.session")
            print(f"Logged out. Session file deleted: {session_path}.session")
        else:
            print("Already logged out.")
        return

    print("Connecting to Telegram...")
    client = TelegramClient(session_path, api_id, api_hash)
    await client.start()
    
    if not await client.is_user_authorized():
        print("Error: Could not authorize.")
        return

    print("Fetching all dialogs...")
    dialogs = await client.get_dialogs()
    total_count = len(dialogs)
    print(f"Found {total_count} total dialogs.")

    print("\nStarting Deep Analysis Scan...")
    print("-" * 50)
    
    groups_config = {}
    lower_targets = [t.lower() for t in TARGET_TOPICS]
    
    stats = {
        "regular_groups": 0,
        "forums_total": 0,
        "forums_matched": 0,
        "forums_no_match": 0,
        "errors": 0,
        "private": 0
    }
    
    for dialog in dialogs:
        entity = dialog.entity
        
        # Skip private users/bots early
        if not (isinstance(entity, Channel) or isinstance(entity, Chat)):
            stats["private"] += 1
            continue

        title = getattr(entity, 'title', dialog.name)
        username = getattr(entity, 'username', None)
        identifier = username if username else str(entity.id)
        
        # Check if it is a forum
        is_forum = getattr(entity, 'forum', False)
        
        if not is_forum:
            stats["regular_groups"] += 1
            # print(f"[DEBUG] Skipping regular group: {title}")
            continue

        stats["forums_total"] += 1
        
        try:
            topics = await client(GetForumTopicsRequest(
                channel=entity,
                offset_date=None,
                offset_id=0,
                offset_topic=0,
                limit=500
            ))
            
            if not topics or not topics.topics:
                print(f"[FORUM] {title}: No topics found or accessible")
                stats["forums_no_match"] += 1
                continue

            found_topics = {}
            for topic in topics.topics:
                t_title = getattr(topic, 'title', "")
                t_id = topic.id
                if t_title:
                    # Apply standardization
                    std_name = standardize_topic_name(t_title)
                    found_topics[std_name] = t_id
                        
            if found_topics:
                groups_config[identifier] = found_topics
                stats["forums_matched"] += 1
                print(f"[✅ SAVED] {title}: Captured {len(found_topics)} topics (Standardized)")
            else:
                stats["forums_no_match"] += 1
                print(f"[❌ EMPTY] {title}: Forum has no topics defined")
                
        except Exception as e:
            stats["errors"] += 1
            print(f"[ERROR] {title}: {str(e)[:50]}")
            
    await client.disconnect()
    
    # Generate Config Content
    content = "# Auto-generated by topics.py (Deep Analysis Mode)\n\n"
    for topic in TARGET_TOPICS:
        content += f'{topic.upper().replace(" ", "_")} = "{topic}"\n'
    
    content += "\nGROUPS_CONFIG = {\n"
    for identifier, topics_map in groups_config.items():
        content += f'    "{identifier}": {{\n'
        for t_name, t_id in topics_map.items():
            content += f'        "{t_name}": {t_id},\n'
        content += "    },\n"
    content += "}\n"
    
    outfile = os.path.join(os.path.dirname(__file__), "groups_config.py")
    with open(outfile, "w") as f:
        f.write(content)
        
    print("\n" + "=" * 50)
    print("DEEP ANALYSIS SUMMARY")
    print("=" * 50)
    print(f"Total Dialogs Scanned: {total_count}")
    print(f"Private Chats / Bots:  {stats['private']}")
    print(f"Regular Groups:        {stats['regular_groups']} (Ignored by Topic Scanner)")
    print(f"Total Forums Found:    {stats['forums_total']}")
    print("-" * 50)
    print(f"Forums with Matches:   {stats['forums_matched']} (Saved to config)")
    print(f"Forums with NO Match:  {stats['forums_no_match']}")
    print(f"Scan Errors/Blocked:   {stats['errors']}")
    print("=" * 50)
    
    if stats['forums_matched'] > 0:
        print(f"\nSUCCESS: Saved {stats['forums_matched']} groups to {outfile}")
    else:
        print(f"\nFinished. No matching topics found.")

if __name__ == "__main__":
    API_ID = int(os.getenv("TELEGRAM_API_ID", "21219293"))
    API_HASH = os.getenv("TELEGRAM_API_HASH", "cff5d321b676104840cf282a742381e0")
    LOGOUT = "--logout" in sys.argv
    asyncio.run(scan_topics(API_ID, API_HASH, logout=LOGOUT))
