"""
EyeconBumps Web App - Admin API Router
Endpoints for admin dashboard
"""
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, timedelta
import asyncio

from auth import require_admin
from database import db

router = APIRouter(prefix="/admin", tags=["Admin"])

# ============ MODELS ============

class CreateClientRequest(BaseModel):
    name: str
    telegram_username: Optional[str] = None
    telegram_id: Optional[int] = None
    subscription_type: str = "basic"
    expires_days: int = 7
    notes: Optional[str] = None

class UpdateClientRequest(BaseModel):
    name: Optional[str] = None
    telegram_username: Optional[str] = None
    subscription_type: Optional[str] = None
    expires_days: Optional[int] = None
    is_active: Optional[bool] = None
    notes: Optional[str] = None

class AddAccountRequest(BaseModel):
    phone_number: str
    session_string: str
    display_name: Optional[str] = None
    is_premium: bool = False
    client_id: Optional[int] = None  # Optional - can add to pool without assigning

class UpdateAccountRequest(BaseModel):
    display_name: Optional[str] = None
    is_premium: Optional[bool] = None
    is_active: Optional[bool] = None

class AssignAccountRequest(BaseModel):
    client_id: Optional[int] = None  # None = unassign

# ============ DASHBOARD ============

@router.get("/dashboard")
async def get_dashboard(admin: dict = Depends(require_admin)):
    """Get admin dashboard overview."""
    analytics = db.get_global_analytics()
    recent_clients = db.get_all_clients()[:5]  # Last 5 clients
    
    return {
        "analytics": analytics,
        "recent_clients": recent_clients
    }

# ============ CLIENTS ============

@router.get("/clients")
async def list_clients(admin: dict = Depends(require_admin)):
    """Get all clients."""
    clients = db.get_all_clients()
    # Add account count for each client
    for client in clients:
        accounts = db.get_client_accounts(client['id'])
        client['account_count'] = len(accounts)
    return {"clients": clients}

@router.post("/clients")
async def create_client(data: CreateClientRequest, admin: dict = Depends(require_admin)):
    """Create a new client and return their access token."""
    client = db.create_client(
        name=data.name,
        telegram_username=data.telegram_username,
        telegram_id=data.telegram_id,
        subscription_type=data.subscription_type,
        expires_days=data.expires_days,
        notes=data.notes
    )
    return {
        "message": "Client created successfully",
        "client": client,
        "access_token": client['access_token']  # Highlight the token
    }

@router.get("/clients/{client_id}")
async def get_client(client_id: int, admin: dict = Depends(require_admin)):
    """Get client details."""
    client = db.get_client_by_id(client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    
    # Get related data
    accounts = db.get_client_accounts(client_id)
    campaigns = db.get_client_campaigns(client_id)
    analytics = db.get_client_analytics(client_id)
    
    return {
        "client": client,
        "accounts": accounts,
        "campaigns": campaigns,
        "analytics": analytics
    }

@router.get("/clients/{client_id}/accounts")
async def get_client_accounts(client_id: int, admin: dict = Depends(require_admin)):
    """Get all accounts assigned to a client."""
    client = db.get_client_by_id(client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    
    accounts = db.get_client_accounts(client_id)
    return {"accounts": accounts}

@router.put("/clients/{client_id}")
async def update_client(client_id: int, data: UpdateClientRequest, admin: dict = Depends(require_admin)):
    """Update client details."""
    updates = data.dict(exclude_unset=True)
    
    # Handle expires_days -> expires_at conversion
    if 'expires_days' in updates:
        updates['expires_at'] = (datetime.now() + timedelta(days=updates.pop('expires_days'))).isoformat()
    
    success = db.update_client(client_id, **updates)
    if not success:
        raise HTTPException(status_code=404, detail="Client not found")
    
    return {"message": "Client updated successfully"}

@router.delete("/clients/{client_id}")
async def delete_client(client_id: int, admin: dict = Depends(require_admin)):
    """Delete a client."""
    success = db.delete_client(client_id)
    if not success:
        raise HTTPException(status_code=404, detail="Client not found")
    return {"message": "Client deleted successfully"}

@router.post("/clients/{client_id}/regenerate-token")
async def regenerate_token(client_id: int, admin: dict = Depends(require_admin)):
    """Generate a new access token for a client."""
    new_token = db.regenerate_client_token(client_id)
    if not new_token:
        raise HTTPException(status_code=404, detail="Client not found")
    return {"message": "Token regenerated", "new_token": new_token}

# ============ ACCOUNTS (Pool Model) ============

@router.get("/accounts")
async def list_accounts(admin: dict = Depends(require_admin)):
    """Get all accounts from the pool with running campaign status."""
    from broadcaster import get_broadcaster
    
    accounts = db.get_all_accounts()
    broadcaster = get_broadcaster(db)
    
    # Check which accounts are in running campaigns
    running_account_campaigns = {}  # account_id -> campaign_name
    
    for campaign_id, progress in broadcaster.campaign_progress.items():
        if progress.get("status") in ["running", "starting"]:
            # Check accounts in this campaign
            accounts_in_campaign = progress.get("accounts", {})
            for acc_id, acc_status in accounts_in_campaign.items():
                if acc_status.get("status") not in ["done", "removed", "error"]:
                    campaign = db.get_campaign_by_id(campaign_id)
                    if campaign:
                        running_account_campaigns[int(acc_id)] = campaign.get("name", f"Campaign {campaign_id}")
    
    # Add running status to each account
    for acc in accounts:
        acc["running_campaign"] = running_account_campaigns.get(acc["id"])
    
    return {"accounts": accounts}

@router.post("/accounts")
async def add_account(data: AddAccountRequest, admin: dict = Depends(require_admin)):
    """Add a Telegram account to the pool (optionally assign to client)."""
    # Verify client exists if specified
    if data.client_id:
        client = db.get_client_by_id(data.client_id)
        if not client:
            raise HTTPException(status_code=404, detail="Client not found")
    
    account = db.add_account(
        phone_number=data.phone_number,
        session_string=data.session_string,
        display_name=data.display_name,
        is_premium=data.is_premium,
        client_id=data.client_id
    )
    return {"message": "Account added successfully", "account": account}

@router.put("/accounts/{account_id}")
async def update_account(account_id: int, data: UpdateAccountRequest, admin: dict = Depends(require_admin)):
    """Update account details (name, premium status, active status)."""
    updates = data.dict(exclude_unset=True)
    success = db.update_account(account_id, **updates)
    if not success:
        raise HTTPException(status_code=404, detail="Account not found")
    return {"message": "Account updated successfully"}

@router.post("/accounts/{account_id}/assign")
async def assign_account(account_id: int, data: AssignAccountRequest, admin: dict = Depends(require_admin)):
    """Assign or unassign an account to a client."""
    # Verify client exists if assigning
    if data.client_id:
        client = db.get_client_by_id(data.client_id)
        if not client:
            raise HTTPException(status_code=404, detail="Client not found")
    
    success = db.assign_account_to_client(account_id, data.client_id)
    if not success:
        raise HTTPException(status_code=404, detail="Account not found")
    
    action = "assigned to client" if data.client_id else "unassigned"
    return {"message": f"Account {action} successfully"}

@router.delete("/accounts/{account_id}")
async def delete_account(account_id: int, admin: dict = Depends(require_admin)):
    """Delete an account from the pool."""
    success = db.delete_account(account_id)
    if not success:
        raise HTTPException(status_code=404, detail="Account not found")
    return {"message": "Account deleted successfully"}

@router.post("/accounts/{account_id}/refresh")
async def refresh_account_from_telegram(account_id: int, admin: dict = Depends(require_admin)):
    """Refresh account info from Telegram (display name, premium status)."""
    from telethon import TelegramClient
    from telethon.sessions import StringSession
    import os
    
    # Get account with session string
    account = db.get_account_by_id(account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    
    session_string = account.get("session_string")
    if not session_string:
        raise HTTPException(status_code=400, detail="Account has no session string")
    
    API_ID = int(os.getenv("TELEGRAM_API_ID", "21219293"))
    API_HASH = os.getenv("TELEGRAM_API_HASH", "cff5d321b676104840cf282a742381e0")
    
    try:
        client = TelegramClient(StringSession(session_string), API_ID, API_HASH)
        await client.connect()
        
        if not await client.is_user_authorized():
            await client.disconnect()
            raise HTTPException(status_code=400, detail="Session is invalid or expired")
        
        # Get account info from Telegram
        me = await client.get_me()
        
        # Get bio (about) using full user info request
        bio = ""
        try:
            from telethon.tl.functions.users import GetFullUserRequest
            full = await client(GetFullUserRequest(me))
            bio = full.full_user.about or ""
        except:
            pass
        
        await client.disconnect()
        
        # Build display name (without username)
        display_name = me.first_name or ""
        if me.last_name:
            display_name += " " + me.last_name
        
        is_premium = bool(getattr(me, 'premium', False))
        
        # Update database
        db.update_account(account_id, display_name=display_name.strip(), is_premium=is_premium)
        
        return {
            "message": "Account refreshed successfully",
            "display_name": display_name.strip(),
            "is_premium": is_premium,
            "phone_number": me.phone,
            "username": me.username,
            "first_name": me.first_name or "",
            "last_name": me.last_name or "",
            "bio": bio
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to refresh: {str(e)}")

@router.post("/accounts/{account_id}/check-spam")
async def check_account_spam_status(account_id: int, admin: dict = Depends(require_admin)):
    """Check account spam/limit status by messaging @spambot on Telegram."""
    from telethon import TelegramClient
    from telethon.sessions import StringSession
    import os
    import asyncio
    
    # Get account with session string
    account = db.get_account_by_id(account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    
    session_string = account.get("session_string")
    if not session_string:
        raise HTTPException(status_code=400, detail="Account has no session string")
    
    API_ID = int(os.getenv("TELEGRAM_API_ID", "21219293"))
    API_HASH = os.getenv("TELEGRAM_API_HASH", "cff5d321b676104840cf282a742381e0")
    
    try:
        client = TelegramClient(StringSession(session_string), API_ID, API_HASH)
        await client.connect()
        
        if not await client.is_user_authorized():
            await client.disconnect()
            raise HTTPException(status_code=400, detail="Session is invalid or expired")
        
        # Send /start to @SpamBot
        spambot = await client.get_entity("@SpamBot")
        await client.send_message(spambot, "/start")
        
        # Wait for response (up to 10 seconds)
        await asyncio.sleep(3)
        
        # Get messages from SpamBot
        messages = await client.get_messages(spambot, limit=5)
        await client.disconnect()
        
        # Parse SpamBot response
        response_text = ""
        has_limits = False
        limit_details = ""
        
        for msg in messages:
            if msg.text and not msg.out:  # Only bot's messages
                response_text = msg.text
                break
        
        if response_text:
            # Detect if account has GROUP/CHANNEL messaging limits specifically
            lower_text = response_text.lower()
            
            # Check for group/channel specific restrictions
            group_channel_restricted = (
                ("groups" in lower_text or "channels" in lower_text) and 
                ("add them to" in lower_text or "cannot" in lower_text or "not be able" in lower_text or "limited" in lower_text)
            )
            
            # Account is clean if it says "no limits" or "good news" patterns
            good_patterns = ["no limits", "good news", "your account is free", "not limited"]
            is_clean = any(pattern in lower_text for pattern in good_patterns)
            
            if is_clean and not group_channel_restricted:
                has_limits = False
                limit_details = "Account is clean - no restrictions"
            elif group_channel_restricted:
                has_limits = True
                limit_details = "Cannot send to groups/channels"
            elif "limited" in lower_text and ("send" in lower_text or "message" in lower_text):
                # General sending limitation but check if it affects groups
                has_limits = True
                limit_details = "Messaging restrictions detected"
            else:
                has_limits = False
                limit_details = "Account appears clean"
        
        return {
            "success": True,
            "has_limits": has_limits,
            "limit_details": limit_details,
            "spambot_response": response_text[:500] if response_text else "No response from SpamBot"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to check spam status: {str(e)}")

@router.get("/accounts/{account_id}/dialogs")
async def get_account_dialogs(account_id: int, admin: dict = Depends(require_admin)):
    """Get all groups/channels joined by this account with group/forum counts."""
    from broadcaster import get_broadcaster
    
    account = db.get_account_by_id(account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    
    session_string = account.get("session_string")
    if not session_string:
        raise HTTPException(status_code=400, detail="Account has no session string")
    
    broadcaster = get_broadcaster(db)
    dialogs = await broadcaster.get_all_dialogs(session_string)
    
    # Count groups vs forum topics
    groups_count = len([d for d in dialogs if not d.get('is_forum', False)])
    forums_count = len([d for d in dialogs if d.get('is_forum', False)])
    
    return {
        "account_id": account_id,
        "phone": account.get("phone_number"),
        "display_name": account.get("display_name"),
        "total": len(dialogs),
        "groups_count": groups_count,
        "forums_count": forums_count,
        "dialogs": dialogs
    }


class UpdateProfileRequest(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    bio: Optional[str] = None
    username: Optional[str] = None

@router.put("/accounts/{account_id}/profile")
async def update_account_profile(account_id: int, data: UpdateProfileRequest, admin: dict = Depends(require_admin)):
    """Update Telegram account profile (name, bio, username)."""
    from telethon import TelegramClient
    from telethon.sessions import StringSession
    from telethon.tl.functions.account import UpdateProfileRequest as TelegramUpdateProfile
    from telethon.tl.functions.account import UpdateUsernameRequest
    import os
    
    account = db.get_account_by_id(account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    
    session_string = account.get("session_string")
    if not session_string:
        raise HTTPException(status_code=400, detail="Account has no session string")
    
    API_ID = int(os.getenv("TELEGRAM_API_ID", "21219293"))
    API_HASH = os.getenv("TELEGRAM_API_HASH", "cff5d321b676104840cf282a742381e0")
    
    try:
        client = TelegramClient(StringSession(session_string), API_ID, API_HASH)
        await client.connect()
        
        if not await client.is_user_authorized():
            await client.disconnect()
            raise HTTPException(status_code=400, detail="Session is invalid or expired")
        
        results = {"updated": []}
        
        # Update profile (name, bio)
        if data.first_name is not None or data.last_name is not None or data.bio is not None:
            await client(TelegramUpdateProfile(
                first_name=data.first_name if data.first_name is not None else "",
                last_name=data.last_name if data.last_name is not None else "",
                about=data.bio if data.bio is not None else ""
            ))
            results["updated"].extend(["first_name", "last_name", "bio"])
        
        # Update username
        if data.username is not None:
            try:
                await client(UpdateUsernameRequest(username=data.username if data.username else ""))
                results["updated"].append("username")
            except Exception as e:
                results["username_error"] = str(e)
        
        # Refresh display name in DB
        me = await client.get_me()
        display_name = me.first_name or ""
        if me.last_name:
            display_name += " " + me.last_name
        db.update_account(account_id, display_name=display_name.strip())
        
        await client.disconnect()
        
        return {
            "success": True,
            "message": "Profile updated successfully",
            "results": results,
            "current_profile": {
                "first_name": me.first_name,
                "last_name": me.last_name,
                "username": me.username,
                "bio": getattr(me, 'about', None)
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update profile: {str(e)}")


@router.post("/accounts/{account_id}/photo")
async def update_account_photo(account_id: int, admin: dict = Depends(require_admin)):
    """Update Telegram account profile photo. Expects base64 image in request body."""
    from telethon import TelegramClient
    from telethon.sessions import StringSession
    from telethon.tl.functions.photos import UploadProfilePhotoRequest, DeletePhotosRequest
    from telethon.tl.functions.photos import GetUserPhotosRequest
    import os
    import base64
    import io
    from fastapi import Body
    
    # For now, just return info - photo upload requires file handling
    return {"message": "Photo upload endpoint - send POST with 'photo_base64' in body"}


@router.get("/accounts/{account_id}/otp")
async def get_account_otp(account_id: int, admin: dict = Depends(require_admin)):
    """Get recent login OTP codes from Telegram (from service account 777000)."""
    from telethon import TelegramClient
    from telethon.sessions import StringSession
    import os
    import re
    
    account = db.get_account_by_id(account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    
    session_string = account.get("session_string")
    if not session_string:
        raise HTTPException(status_code=400, detail="Account has no session string")
    
    API_ID = int(os.getenv("TELEGRAM_API_ID", "21219293"))
    API_HASH = os.getenv("TELEGRAM_API_HASH", "cff5d321b676104840cf282a742381e0")
    
    try:
        client = TelegramClient(StringSession(session_string), API_ID, API_HASH)
        await client.connect()
        
        if not await client.is_user_authorized():
            await client.disconnect()
            raise HTTPException(status_code=400, detail="Session is invalid or expired")
        
        # Get messages from Telegram service account (777000)
        # This is where login codes are sent
        codes = []
        try:
            async for message in client.iter_messages(777000, limit=10):
                if message.text:
                    # Extract OTP codes (typically 5-6 digit numbers)
                    code_match = re.search(r'\b(\d{5,6})\b', message.text)
                    if code_match:
                        codes.append({
                            "code": code_match.group(1),
                            "message": message.text[:200],
                            "date": message.date.isoformat() if message.date else None
                        })
        except Exception as e:
            # May fail if no messages from 777000
            pass
        
        await client.disconnect()
        
        return {
            "success": True,
            "account_id": account_id,
            "phone": account.get("phone_number"),
            "codes": codes,
            "latest_code": codes[0]["code"] if codes else None
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get OTP: {str(e)}")


# ============ GROUP MANAGEMENT ============

GROUPS_FOLDER = r"D:\main-app-ad\groups"

@router.get("/groups/files")
async def list_group_files(admin: dict = Depends(require_admin)):
    """List available group files."""
    import os
    
    files = []
    if os.path.exists(GROUPS_FOLDER):
        for filename in os.listdir(GROUPS_FOLDER):
            if filename.endswith(".txt"):
                filepath = os.path.join(GROUPS_FOLDER, filename)
                with open(filepath, "r", encoding="utf-8") as f:
                    # Accept lines with t.me links OR plain usernames (alphanumeric with underscores)
                    lines = [l.strip() for l in f.readlines() if l.strip() and ("t.me" in l or l.strip().replace("_", "").isalnum())]
                    files.append({
                        "filename": filename,
                        "group_count": len(lines)
                    })
    
    return {"files": files}

@router.get("/groups/files/{filename}")
async def get_group_file_contents(filename: str, admin: dict = Depends(require_admin)):
    """Get contents of a group file."""
    import os
    
    filepath = os.path.join(GROUPS_FOLDER, filename)
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="File not found")
    
    with open(filepath, "r", encoding="utf-8") as f:
        # Accept lines with t.me links OR plain usernames
        lines = [l.strip() for l in f.readlines() if l.strip() and ("t.me" in l or l.strip().replace("_", "").isalnum())]
    
    return {"filename": filename, "groups": lines}

class JoinGroupsRequest(BaseModel):
    filename: str
    delay_seconds: int = 5  # Base delay between joins (will increase on errors)
    batch_size: int = 10  # Groups per batch before longer pause

@router.post("/accounts/{account_id}/join-groups")
async def bulk_join_groups(account_id: int, data: JoinGroupsRequest, admin: dict = Depends(require_admin)):
    """
    Join multiple groups from a file with smart rate limit handling.
    
    Strategy:
    - Join in batches of batch_size groups
    - Progressive delay: starts at delay_seconds, increases on errors
    - Longer pause between batches (60s)
    - Auto-wait on FloodWait errors then continue
    - Skip already joined/failed groups silently
    """
    from telethon import TelegramClient
    from telethon.sessions import StringSession
    from telethon.tl.functions.channels import JoinChannelRequest
    from telethon.tl.functions.messages import ImportChatInviteRequest
    from telethon.errors import FloodWaitError, UserAlreadyParticipantError, ChannelPrivateError, InviteHashExpiredError
    import os
    import asyncio
    import re
    import random
    
    # Get account
    account = db.get_account_by_id(account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    
    session_string = account.get("session_string")
    if not session_string:
        raise HTTPException(status_code=400, detail="Account has no session string")
    
    # Read group file
    filepath = os.path.join(GROUPS_FOLDER, data.filename)
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="Group file not found")
    
    with open(filepath, "r", encoding="utf-8") as f:
        groups = [l.strip() for l in f.readlines() if l.strip() and (
            "t.me" in l or l.strip().replace("_", "").isalnum()
        )]
    
    if not groups:
        raise HTTPException(status_code=400, detail="No valid groups in file")
    
    API_ID = int(os.getenv("TELEGRAM_API_ID", "21219293"))
    API_HASH = os.getenv("TELEGRAM_API_HASH", "cff5d321b676104840cf282a742381e0")
    
    try:
        client = TelegramClient(StringSession(session_string), API_ID, API_HASH)
        await client.connect()
        
        if not await client.is_user_authorized():
            await client.disconnect()
            raise HTTPException(status_code=400, detail="Session is invalid or expired")
        
        results = {
            "joined": [],
            "already_member": [],
            "failed": [],
            "flood_waits": 0,
            "total_wait_time": 0
        }
        
        # Smart delay management
        current_delay = data.delay_seconds
        batch_count = 0
        consecutive_errors = 0
        
        for i, group_entry in enumerate(groups):
            try:
                # Parse group - could be t.me link, invite link, or plain username
                if "/+" in group_entry or "/joinchat/" in group_entry:
                    # Private invite link
                    hash_match = re.search(r"(?:/\+|/joinchat/)([a-zA-Z0-9_-]+)", group_entry)
                    if hash_match:
                        invite_hash = hash_match.group(1)
                        await client(ImportChatInviteRequest(invite_hash))
                        results["joined"].append(group_entry)
                elif "t.me/" in group_entry:
                    # Public t.me link
                    username = group_entry.split("/")[-1].replace("@", "")
                    entity = await client.get_entity(username)
                    await client(JoinChannelRequest(entity))
                    results["joined"].append(group_entry)
                else:
                    # Plain username
                    username = group_entry.replace("@", "").strip()
                    entity = await client.get_entity(username)
                    await client(JoinChannelRequest(entity))
                    results["joined"].append(group_entry)
                
                # Reset consecutive errors on success
                consecutive_errors = 0
                batch_count += 1
                
                # Batch handling - longer pause after every batch_size groups
                if batch_count >= data.batch_size:
                    batch_count = 0
                    # Random pause between 45-75 seconds between batches
                    batch_pause = random.randint(45, 75)
                    await asyncio.sleep(batch_pause)
                else:
                    # Normal delay with some randomness (±30%)
                    random_delay = current_delay * random.uniform(0.7, 1.3)
                    await asyncio.sleep(random_delay)
                    
            except UserAlreadyParticipantError:
                results["already_member"].append(group_entry)
                # No delay needed for already joined
                
            except FloodWaitError as e:
                # Auto-wait and continue instead of stopping
                results["flood_waits"] += 1
                results["total_wait_time"] += e.seconds
                
                # Wait the required time + extra buffer
                wait_time = e.seconds + random.randint(5, 15)
                await asyncio.sleep(wait_time)
                
                # Increase base delay after flood
                current_delay = min(current_delay * 1.5, 60)
                consecutive_errors += 1
                
                # Retry this group after waiting
                try:
                    if "/+" in group_entry or "/joinchat/" in group_entry:
                        hash_match = re.search(r"(?:/\+|/joinchat/)([a-zA-Z0-9_-]+)", group_entry)
                        if hash_match:
                            await client(ImportChatInviteRequest(hash_match.group(1)))
                            results["joined"].append(group_entry)
                    else:
                        username = group_entry.split("/")[-1].replace("@", "") if "t.me/" in group_entry else group_entry.replace("@", "").strip()
                        entity = await client.get_entity(username)
                        await client(JoinChannelRequest(entity))
                        results["joined"].append(group_entry)
                except Exception:
                    results["failed"].append({"group": group_entry, "error": "Failed after flood wait"})
                    
            except (ChannelPrivateError, InviteHashExpiredError) as e:
                results["failed"].append({"group": group_entry, "error": str(type(e).__name__)})
                
            except Exception as e:
                consecutive_errors += 1
                results["failed"].append({"group": group_entry, "error": str(e)[:80]})
                
                # Slow down on consecutive errors
                if consecutive_errors >= 3:
                    current_delay = min(current_delay * 1.5, 60)
                    await asyncio.sleep(30)  # Extra pause on many errors
        
        await client.disconnect()
        
        return {
            "success": True,
            "total": len(groups),
            "joined": len(results["joined"]),
            "already_member": len(results["already_member"]),
            "failed": len(results["failed"]),
            "flood_waits": results["flood_waits"],
            "total_wait_time": results["total_wait_time"],
            "details": results
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to join groups: {str(e)}")


@router.get("/accounts/{account_id}/chat-stats")
async def get_account_chat_stats(account_id: int, admin: dict = Depends(require_admin)):
    """Get statistics about how many groups, channels, and forums an account has joined"""
    from telethon import TelegramClient
    from telethon.sessions import StringSession
    from telethon.tl.functions.messages import GetDialogFiltersRequest
    from telethon.tl.types import Channel, Chat, User
    import os
    
    account = db.get_account_by_id(account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    
    session_string = account.get("session_string")
    if not session_string:
        raise HTTPException(status_code=400, detail="No session string for this account")
    
    API_ID = int(os.getenv("TELEGRAM_API_ID", "21219293"))
    API_HASH = os.getenv("TELEGRAM_API_HASH", "cff5d321b676104840cf282a742381e0")
    
    try:
        client = TelegramClient(StringSession(session_string), API_ID, API_HASH)
        await client.connect()
        
        if not await client.is_user_authorized():
            await client.disconnect()
            raise HTTPException(status_code=401, detail="Session expired")
        
        # Get all dialogs
        dialogs = await client.get_dialogs()
        
        stats = {
            "total_dialogs": len(dialogs),
            "groups": 0,
            "supergroups": 0,
            "channels": 0,
            "forums": 0,
            "private_chats": 0,
            "bots": 0,
        }
        
        for dialog in dialogs:
            entity = dialog.entity
            if isinstance(entity, Channel):
                if entity.megagroup:
                    if hasattr(entity, 'forum') and entity.forum:
                        stats["forums"] += 1
                    else:
                        stats["supergroups"] += 1
                elif entity.broadcast:
                    stats["channels"] += 1
            elif isinstance(entity, Chat):
                stats["groups"] += 1
            elif isinstance(entity, User):
                if entity.bot:
                    stats["bots"] += 1
                else:
                    stats["private_chats"] += 1
        
        await client.disconnect()
        
        return {
            "total_dialogs": stats["total_dialogs"],
            "groups": stats["groups"],
            "supergroups": stats["supergroups"],
            "forums": stats["forums"],
            "channels": stats["channels"],
            "private_chats": stats["private_chats"],
            "bots": stats["bots"],
            "total_groups_and_forums": stats["groups"] + stats["supergroups"] + stats["forums"]
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get chat stats: {str(e)}")

# Hardcoded folder links for joining
FOLDER_LINKS = [
    "https://t.me/addlist/QlgDHVRRo21jMTE0",
    "https://t.me/addlist/KedMVZMhcnBmYmJk",
    "https://t.me/addlist/Z3JuLCPW1-ozZmZk",
    "https://t.me/addlist/UqX2kactZ_VlMWFl",
    "https://t.me/addlist/MLYSiwlZ7uU5NzM1",
]

# Global progress tracker for background folder join operations
folder_join_progress = {}

async def _join_folders_background(account_id: int, session_string: str):
    """Background task to join folders without blocking the API"""
    from telethon import TelegramClient
    from telethon.sessions import StringSession
    from telethon.tl.functions.chatlists import CheckChatlistInviteRequest, JoinChatlistInviteRequest, LeaveChatlistRequest
    from telethon.errors import FloodWaitError
    import os
    import asyncio
    import re
    
    task_id = f"account_{account_id}"
    folder_join_progress[task_id] = {
        "status": "running",
        "progress": 0,
        "total": len(FOLDER_LINKS),
        "joined": 0,
        "failed": 0,
        "chats_added": 0,
        "current_folder": None,
        "error": None
    }
    
    API_ID = int(os.getenv("TELEGRAM_API_ID", "21219293"))
    API_HASH = os.getenv("TELEGRAM_API_HASH", "cff5d321b676104840cf282a742381e0")
    
    try:
        client = TelegramClient(StringSession(session_string), API_ID, API_HASH)
        await client.connect()
        
        if not await client.is_user_authorized():
            folder_join_progress[task_id]["status"] = "failed"
            folder_join_progress[task_id]["error"] = "Session is invalid or expired"
            await client.disconnect()
            return
        
        # Pre-clean ALL shared chatlist folders to free up slots (Telegram limit: 2-3)
        print(f"[DEBUG] === PRE-CLEANUP: Deleting existing shared folders ===")
        try:
            from telethon.tl.functions.messages import GetDialogFiltersRequest, UpdateDialogFilterRequest
            from telethon.tl.types import DialogFilterDefault, DialogFilterChatlist
            filters = await client(GetDialogFiltersRequest())
            print(f"[DEBUG] Found {len(filters.filters)} total dialog filters")
            
            deleted_count = 0
            for f in filters.filters:
                # Skip default filter (All Chats)
                if isinstance(f, DialogFilterDefault):
                    continue
                
                filter_name = f.title if hasattr(f, 'title') else "unknown"
                filter_id = f.id if hasattr(f, 'id') else None
                filter_type = type(f).__name__
                
                # Delete if it's a DialogFilterChatlist (shared folder from addlist links)
                if isinstance(f, DialogFilterChatlist) or (hasattr(f, 'chatlist_date') and f.chatlist_date):
                    print(f"[DEBUG] Deleting shared folder: '{filter_name}' (id={filter_id}, type={filter_type})")
                    try:
                        await client(UpdateDialogFilterRequest(id=filter_id, filter=None))
                        print(f"[DEBUG] ✓ Folder '{filter_name}' DELETED")
                        deleted_count += 1
                        await asyncio.sleep(2)
                    except Exception as e:
                        print(f"[DEBUG] ✗ Failed to delete '{filter_name}': {e}")
                else:
                    print(f"[DEBUG] Keeping regular folder: '{filter_name}' (type={filter_type})")
            
            print(f"[DEBUG] Pre-cleanup complete: deleted {deleted_count} shared folders")
        except Exception as e:
            print(f"[DEBUG] Pre-cleanup error: {e}")
        
        # Process each folder
        for idx, folder_link in enumerate(FOLDER_LINKS):
            folder_join_progress[task_id]["current_folder"] = folder_link
            folder_join_progress[task_id]["progress"] = idx
            
            try:
                slug_match = re.search(r"/addlist/([a-zA-Z0-9_-]+)", folder_link)
                if not slug_match:
                    folder_join_progress[task_id]["failed"] += 1
                    continue
                
                slug = slug_match.group(1)
                folder_info = await client(CheckChatlistInviteRequest(slug=slug))
                
                # Skip if already joined
                if type(folder_info).__name__ == 'ChatlistInviteAlready':
                    chats_count = len(folder_info.already_peers) if hasattr(folder_info, 'already_peers') else 0
                    folder_join_progress[task_id]["chats_added"] += chats_count
                    folder_join_progress[task_id]["joined"] += 1
                    continue
                
                # Get peers
                all_peers = []
                if hasattr(folder_info, 'peers') and folder_info.peers:
                    all_peers.extend(folder_info.peers)
                elif hasattr(folder_info, 'missing_peers') and folder_info.missing_peers:
                    all_peers.extend(folder_info.missing_peers)
                
                # Limit to 100, join the rest manually
                FOLDER_LIMIT = 100
                peers_for_folder = all_peers[:FOLDER_LIMIT]
                extra_peers = all_peers[FOLDER_LIMIT:]
                
                # Join folder
                folder_joined = False
                try:
                    print(f"[DEBUG] Joining folder with {len(peers_for_folder)} peers...")
                    join_result = await client(JoinChatlistInviteRequest(slug=slug, peers=peers_for_folder))
                    folder_joined = True
                    folder_join_progress[task_id]["chats_added"] += len(peers_for_folder)
                    print(f"[DEBUG] Folder joined successfully! Result type: {type(join_result).__name__}")
                    
                    # IMPORTANT: Delete folder IMMEDIATELY to free slot (2 folder limit)
                    # Since JoinChatlistInviteRequest returns Updates without filter info,
                    # we need to fetch all dialog filters and delete any shared chatlists
                    await asyncio.sleep(2)
                    
                    try:
                        from telethon.tl.functions.messages import GetDialogFiltersRequest, UpdateDialogFilterRequest
                        from telethon.tl.types import DialogFilterChatlist, DialogFilterDefault
                        
                        filters = await client(GetDialogFiltersRequest())
                        for f in filters.filters:
                            if isinstance(f, DialogFilterDefault):
                                continue
                            # Delete any shared chatlist folder (the one we just joined)
                            if isinstance(f, DialogFilterChatlist) or (hasattr(f, 'chatlist_date') and f.chatlist_date):
                                filter_name = f.title if hasattr(f, 'title') else "unknown"
                                print(f"[DEBUG] Deleting shared folder: '{filter_name}' (id={f.id})")
                                try:
                                    await client(UpdateDialogFilterRequest(id=f.id, filter=None))
                                    print(f"[DEBUG] ✓ Folder '{filter_name}' DELETED!")
                                    await asyncio.sleep(1)
                                except Exception as e:
                                    print(f"[DEBUG] ✗ Failed to delete folder: {e}")
                    except Exception as e:
                        print(f"[DEBUG] Error during post-join cleanup: {e}")
                        
                except Exception as join_err:
                    error_str = str(join_err)
                    print(f"[DEBUG] ✗ Folder join FAILED: {error_str}")
                    
                    # If CHATLISTS_TOO_MUCH, don't try manual joining - just skip
                    # The folders still exist from previous joins
                    if "CHATLISTS_TOO_MUCH" in error_str:
                        print(f"[DEBUG] Hit folder limit - skipping this folder (need to delete existing folders first)")
                        folder_join_progress[task_id]["failed"] += 1
                        continue
                    
                    # For other errors, try manual joining but limit to first 20 peers
                    extra_peers = all_peers[:20] if all_peers else []
                    print(f"[DEBUG] Will try manual joining for {len(extra_peers)} peers")
                
                # Manually join extra peers
                if extra_peers:
                    from telethon.tl.functions.channels import JoinChannelRequest
                    from telethon.errors import UserAlreadyParticipantError, FloodWaitError as ChannelFloodWait
                    
                    for peer in extra_peers:
                        try:
                            await client(JoinChannelRequest(peer))
                            folder_join_progress[task_id]["chats_added"] += 1
                            await asyncio.sleep(2)
                        except UserAlreadyParticipantError:
                            folder_join_progress[task_id]["chats_added"] += 1
                        except ChannelFloodWait as fw:
                            wait_time = min(fw.seconds + 5, 120)
                            await asyncio.sleep(wait_time)
                            try:
                                await client(JoinChannelRequest(peer))
                                folder_join_progress[task_id]["chats_added"] += 1
                            except:
                                pass
                        except:
                            continue
                
                if folder_joined or extra_peers:
                    folder_join_progress[task_id]["joined"] += 1
                else:
                    folder_join_progress[task_id]["failed"] += 1
                
                await asyncio.sleep(5)
                
            except FloodWaitError as e:
                folder_join_progress[task_id]["failed"] += 1
                await asyncio.sleep(min(e.seconds, 30))
            except:
                folder_join_progress[task_id]["failed"] += 1
        
        await client.disconnect()
        folder_join_progress[task_id]["status"] = "completed"
        folder_join_progress[task_id]["progress"] = len(FOLDER_LINKS)
        
    except Exception as e:
        folder_join_progress[task_id]["status"] = "failed"
        folder_join_progress[task_id]["error"] = str(e)

@router.post("/accounts/{account_id}/join-folders")
async def join_chat_folders(account_id: int, background_tasks: BackgroundTasks, admin: dict = Depends(require_admin)):
    """
    Start background task to join chat folders.
    Returns immediately with task_id to check progress.
    """
    account = db.get_account_by_id(account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    
    session_string = account.get("session_string")
    if not session_string:
        raise HTTPException(status_code=400, detail="Account has no session string")
    
    task_id = f"account_{account_id}"
    
    # Check if already running
    if task_id in folder_join_progress and folder_join_progress[task_id]["status"] == "running":
        return {
            "success": True,
            "message": "Folder join already in progress",
            "task_id": task_id,
            "status": folder_join_progress[task_id]
        }
    
    # Start background task
    background_tasks.add_task(_join_folders_background, account_id, session_string)
    
    return {
        "success": True,
        "message": "Folder join started in background",
        "task_id": task_id
    }

@router.get("/accounts/{account_id}/join-folders/status")
async def get_folder_join_status(account_id: int, admin: dict = Depends(require_admin)):
    """Get the status of a folder join operation"""
    task_id = f"account_{account_id}"
    
    if task_id not in folder_join_progress:
        return {
            "status": "not_found",
            "message": "No folder join operation found for this account"
        }
    
    return folder_join_progress[task_id]

# ============ CAMPAIGNS ============

class CreateCampaignRequest(BaseModel):
    client_id: int
    name: str
    message_content: Optional[str] = None
    message_type: str = "text"
    media_file_id: Optional[str] = None
    delay_seconds: int = 30
    target_groups: Optional[List[str]] = None
    # New fields
    send_mode: str = "send"  # "send" or "forward"
    broadcast_all: bool = True  # True = send to all account dialogs
    forward_from_chat: Optional[int] = None  # Chat ID to forward from
    forward_message_id: Optional[int] = None  # Message ID to forward
    forward_link: Optional[str] = None  # t.me/c/xxx/123 format (alternative to chat/message IDs)
    account_ids: Optional[List[int]] = None  # Specific accounts to use (None = all assigned accounts)
    template_id: Optional[int] = None  # Message template ID (for premium emoji/formatting)

class AddGroupsRequest(BaseModel):
    groups: List[str] = []  # List of group usernames or t.me links
    group_file: Optional[str] = None  # Or name of file from groups folder

@router.get("/campaigns")
async def list_campaigns(admin: dict = Depends(require_admin)):
    """Get all campaigns with details."""
    campaigns = db.get_all_campaigns()
    
    # Add group counts
    for campaign in campaigns:
        groups = db.get_campaign_groups(campaign['id'])
        campaign['group_count'] = len(groups)
        campaign['groups_sent'] = len([g for g in groups if g.get('status') == 'sent'])
    
    return {"campaigns": campaigns}

@router.post("/campaigns")
async def create_campaign(data: CreateCampaignRequest, admin: dict = Depends(require_admin)):
    """Create a new campaign."""
    # Debug: log incoming request
    print(f"[CAMPAIGN API] Creating campaign - send_mode={data.send_mode}, forward_link={data.forward_link}")
    print(f"[CAMPAIGN API] forward_from_chat={data.forward_from_chat}, forward_message_id={data.forward_message_id}")
    
    client = db.get_client_by_id(data.client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    
    # For multi-account, use first account or None
    account_id = data.account_ids[0] if data.account_ids and len(data.account_ids) == 1 else None
    
    campaign = db.create_campaign(
        client_id=data.client_id,
        name=data.name,
        target_groups=data.target_groups or [],
        message_type=data.message_type,
        message_content=data.message_content,
        delay_seconds=data.delay_seconds,
        account_id=account_id,
        template_id=data.template_id
    )
    
    # Save forward message fields and multi-account IDs
    update_data = {'id': campaign['id']}
    
    # Save send mode and forward data
    if data.send_mode:
        update_data['send_mode'] = data.send_mode
    
    # Parse forward_link if provided (format: t.me/c/CHAT_ID/MESSAGE_ID)
    forward_from_chat = data.forward_from_chat
    forward_message_id = data.forward_message_id
    
    if data.forward_link and not (forward_from_chat and forward_message_id):
        import re
        # Match t.me/c/1234567890/123 format (private channel link)
        match = re.search(r't\.me/c/(\d+)/(\d+)', data.forward_link)
        if match:
            # For private channel links, the chat ID needs to be converted to the full format
            chat_id = int(match.group(1))
            forward_from_chat = -1000000000000 - chat_id  # Convert to full channel ID format
            forward_message_id = int(match.group(2))
            print(f"[CAMPAIGN] Parsed forward link: chat={forward_from_chat}, msg={forward_message_id}")
        else:
            # Try matching public channel format: t.me/username/123
            match = re.search(r't\.me/([a-zA-Z][a-zA-Z0-9_]{3,31})/(\d+)', data.forward_link)
            if match:
                # For public channels, store the username - broadcaster will resolve it
                forward_from_username = match.group(1)
                forward_message_id = int(match.group(2))
                update_data['forward_from_username'] = forward_from_username
                print(f"[CAMPAIGN] Public channel forward: username={forward_from_username}, msg={forward_message_id}")
    
    if forward_from_chat:
        update_data['forward_from_chat'] = forward_from_chat
    if forward_message_id:
        update_data['forward_message_id'] = forward_message_id
    
    # If multiple accounts selected, store them as JSON
    if data.account_ids and len(data.account_ids) > 1:
        import json
        update_data['account_ids_json'] = json.dumps(data.account_ids)
    
    if len(update_data) > 1:  # More than just 'id'
        print(f"[CAMPAIGN API] Saving update_data: {update_data}")
        db.update_campaign(update_data)
    
    # Add groups if provided
    if data.target_groups:
        db.add_campaign_groups(campaign['id'], data.target_groups)
    
    return {"message": "Campaign created", "campaign": campaign}

@router.get("/campaigns/{campaign_id}")
async def get_campaign(campaign_id: int, admin: dict = Depends(require_admin)):
    """Get campaign details."""
    campaign = db.get_campaign_by_id(campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    groups = db.get_campaign_groups(campaign_id)
    campaign['groups'] = groups
    campaign['group_count'] = len(groups)
    
    return campaign

@router.delete("/campaigns/{campaign_id}")
async def delete_campaign(campaign_id: int, admin: dict = Depends(require_admin)):
    """Delete a campaign and its associated data."""
    campaign = db.get_campaign_by_id(campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    # Stop if running
    if campaign.get('status') == 'running':
        raise HTTPException(status_code=400, detail="Stop the campaign before deleting")
    
    # Delete campaign (cascade deletes groups)
    success = db.delete_campaign(campaign_id)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to delete campaign")
    
    return {"message": "Campaign deleted"}

@router.post("/campaigns/{campaign_id}/groups")
async def add_campaign_groups(campaign_id: int, data: AddGroupsRequest, admin: dict = Depends(require_admin)):
    """Add target groups to a campaign."""
    import os
    
    campaign = db.get_campaign_by_id(campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    groups_to_add = []
    
    # From direct list
    if data.groups:
        groups_to_add.extend(data.groups)
    
    # From file
    if data.group_file:
        filepath = os.path.join(GROUPS_FOLDER, data.group_file)
        if os.path.exists(filepath):
            with open(filepath, "r", encoding="utf-8") as f:
                file_groups = [l.strip() for l in f.readlines() if l.strip() and (
                    "t.me" in l or l.strip().replace("_", "").isalnum()
                )]
                groups_to_add.extend(file_groups)
    
    count = db.add_campaign_groups(campaign_id, groups_to_add)
    return {"message": f"Added {count} groups", "total_groups": len(db.get_campaign_groups(campaign_id))}

@router.delete("/campaigns/{campaign_id}/groups")
async def clear_campaign_groups(campaign_id: int, admin: dict = Depends(require_admin)):
    """Clear all target groups from a campaign."""
    db.clear_campaign_groups(campaign_id)
    return {"message": "Groups cleared"}

# Background task storage
running_tasks = {}

@router.post("/campaigns/{campaign_id}/start")
async def start_campaign(campaign_id: int, background_tasks: BackgroundTasks, admin: dict = Depends(require_admin)):
    """Start broadcasting a campaign."""
    from broadcaster import get_broadcaster
    
    campaign = db.get_campaign_by_id(campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    if campaign.get('status') == 'running':
        raise HTTPException(status_code=400, detail="Campaign already running")
    
    # Check client has assigned accounts
    accounts = db.get_client_accounts(campaign['client_id'])
    if not accounts:
        raise HTTPException(status_code=400, detail="No accounts assigned to this client. Assign accounts first.")
    
    active_accounts = [a for a in accounts if a.get('is_active', True)]
    if not active_accounts:
        raise HTTPException(status_code=400, detail="No active accounts. Check account status.")
    
    # Groups are optional - if no groups set, broadcaster will auto-fetch from account dialogs
    groups = db.get_campaign_groups(campaign_id)
    broadcast_mode = "auto-detect from account" if not groups else f"{len(groups)} groups"
    
    # Get broadcaster and start campaign
    broadcaster = get_broadcaster(db)
    
    async def run_campaign_task():
        try:
            # Use parallel mode for per-account status and independent sending
            await broadcaster.run_campaign_parallel(campaign_id)
        except Exception as e:
            print(f"Campaign {campaign_id} error: {e}")
            db.update_campaign_status(campaign_id, "failed")
    
    # Start as background task
    task = asyncio.create_task(run_campaign_task())
    running_tasks[campaign_id] = task
    
    db.update_campaign_status(campaign_id, "running")
    
    return {
        "message": "Campaign started",
        "campaign_id": campaign_id,
        "broadcast_mode": broadcast_mode,
        "accounts": len(active_accounts)
    }

@router.post("/campaigns/{campaign_id}/stop")
async def stop_campaign(campaign_id: int, admin: dict = Depends(require_admin)):
    """Stop a running campaign."""
    from broadcaster import get_broadcaster
    
    campaign = db.get_campaign_by_id(campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    broadcaster = get_broadcaster(db)
    broadcaster.stop_campaign(campaign_id)
    
    db.update_campaign_status(campaign_id, "stopped")
    
    return {"message": "Campaign stopped"}

@router.post("/campaigns/{campaign_id}/remove-account/{account_id}")
async def remove_account_from_campaign(campaign_id: int, account_id: int, admin: dict = Depends(require_admin)):
    """Remove an individual account from a running campaign without stopping others."""
    from broadcaster import get_broadcaster
    
    campaign = db.get_campaign_by_id(campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    broadcaster = get_broadcaster(db)
    
    if not broadcaster.is_campaign_running(campaign_id):
        raise HTTPException(status_code=400, detail="Campaign is not running")
    
    broadcaster.remove_account(campaign_id, account_id)
    
    return {"message": f"Account {account_id} removed from campaign", "account_id": account_id}


@router.get("/campaigns/{campaign_id}/status")
async def get_campaign_status(campaign_id: int, admin: dict = Depends(require_admin)):
    """Get live campaign status with real-time progress."""
    from broadcaster import get_broadcaster
    
    campaign = db.get_campaign_by_id(campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    broadcaster = get_broadcaster(db)
    is_running = broadcaster.is_campaign_running(campaign_id)
    
    # Get live progress from broadcaster
    progress = broadcaster.get_progress(campaign_id)
    
    # Calculate progress within current cycle
    total = progress.get("total", 0)
    processed = progress.get("sent", 0) + progress.get("failed", 0)
    cycle = progress.get("cycle", 1)
    
    if total > 0:
        # For continuous looping campaigns, calculate progress within current cycle
        # Use modulo to get per-cycle progress, capped at 100%
        raw_percent = (processed / total) * 100
        if cycle > 1:
            # In subsequent cycles, show progress relative to cycle start
            progress_percent = round(raw_percent % 100, 1)
            # But if we hit exactly 0%, show 100% (cycle just completed)
            if progress_percent == 0 and processed > 0:
                progress_percent = 100.0
        else:
            # First cycle - cap at 100%
            progress_percent = min(round(raw_percent, 1), 100.0)
    else:
        progress_percent = 0
    
    return {
        "campaign_id": campaign_id,
        "status": progress.get("status", campaign.get('status', 'draft')),
        "is_running": is_running,
        "mode": progress.get("mode", "sequential"),  # parallel or sequential
        "total": total,
        "sent": progress.get("sent", 0),
        "failed": progress.get("failed", 0),
        "current_index": progress.get("current_index", 0),
        "current_group": progress.get("current_group"),
        "recent_logs": progress.get("recent_logs", []),
        "accounts": progress.get("accounts", {}),  # Per-account status for parallel mode
        "cycle": cycle,
        "progress_percent": progress_percent
    }

@router.get("/campaigns/{campaign_id}/logs")
async def get_campaign_logs(campaign_id: int, limit: int = 50, admin: dict = Depends(require_admin)):
    """Get recent broadcast logs for a campaign."""
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT bl.*, ca.phone_number 
            FROM broadcast_logs bl
            LEFT JOIN client_accounts ca ON bl.account_id = ca.id
            WHERE bl.campaign_id = ?
            ORDER BY bl.sent_at DESC
            LIMIT ?
        """, (campaign_id, limit))
        logs = [dict(row) for row in cursor.fetchall()]
    
    return {"logs": logs}

# ============ ANALYTICS ============

@router.get("/analytics")
async def get_analytics(admin: dict = Depends(require_admin)):
    """Get global analytics."""
    return db.get_global_analytics()

@router.get("/analytics/client/{client_id}")
async def get_client_analytics(client_id: int, admin: dict = Depends(require_admin)):
    """Get analytics for a specific client."""
    return db.get_client_analytics(client_id)

# ============ MESSAGE TEMPLATES ============

@router.get("/templates/client/{client_id}")
async def get_client_templates(client_id: int, admin: dict = Depends(require_admin)):
    """Get all message templates for a client (collected via Telegram bot)."""
    templates = db.get_client_templates(client_id)
    return {"templates": templates}

@router.get("/templates/{template_id}")
async def get_template(template_id: int, admin: dict = Depends(require_admin)):
    """Get a specific message template."""
    template = db.get_template_by_id(template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    return {"template": template}

@router.delete("/templates/{template_id}")
async def delete_template(template_id: int, admin: dict = Depends(require_admin)):
    """Delete a message template."""
    if not db.delete_template(template_id):
        raise HTTPException(status_code=404, detail="Template not found")
    return {"message": "Template deleted"}
