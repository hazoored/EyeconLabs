"""
EyeconBumps Web App - Broadcasting Engine
Handles message sending to Telegram groups with smart rate limiting
"""
import asyncio
import random
import re
import os
from datetime import datetime
from typing import Optional, List, Dict, Any, Callable
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.tl.functions.channels import GetForumTopicsRequest
from telethon.tl.functions.messages import SendMessageRequest
from telethon.tl.types import (
    ForumTopic, InputPeerChannel,
    MessageEntityBold, MessageEntityItalic, MessageEntityCode,
    MessageEntityStrike, MessageEntityUnderline, MessageEntityUrl,
    MessageEntityTextUrl, MessageEntityMention, MessageEntityHashtag,
    MessageEntityCustomEmoji, MessageEntityPre, MessageEntitySpoiler
)
from telethon.errors import (
    FloodWaitError, 
    ChatWriteForbiddenError,
    ChannelPrivateError,
    SlowModeWaitError,
    UserBannedInChannelError,
    ChatAdminRequiredError,
    MessageTooLongError,
    PeerIdInvalidError,
    RPCError
)


def convert_entities_to_telethon(json_entities: list) -> list:
    """
    Convert python-telegram-bot style JSON entities to Telethon MessageEntity objects.
    This enables premium emojis and text formatting in broadcasts.
    """
    if not json_entities:
        return None
    
    telethon_entities = []
    entity_map = {
        'bold': MessageEntityBold,
        'italic': MessageEntityItalic,
        'code': MessageEntityCode,
        'strikethrough': MessageEntityStrike,
        'underline': MessageEntityUnderline,
        'url': MessageEntityUrl,
        'text_link': MessageEntityTextUrl,
        'mention': MessageEntityMention,
        'hashtag': MessageEntityHashtag,
        'custom_emoji': MessageEntityCustomEmoji,
        'pre': MessageEntityPre,
        'spoiler': MessageEntitySpoiler,
    }
    
    for entity in json_entities:
        entity_type = entity.get('type', '')
        offset = entity.get('offset', 0)
        length = entity.get('length', 0)
        
        if entity_type in entity_map:
            try:
                if entity_type == 'text_link':
                    telethon_entities.append(
                        MessageEntityTextUrl(offset=offset, length=length, url=entity.get('url', ''))
                    )
                elif entity_type == 'custom_emoji':
                    # Premium emoji - get document_id
                    document_id = entity.get('custom_emoji_id')
                    if document_id:
                        telethon_entities.append(
                            MessageEntityCustomEmoji(offset=offset, length=length, document_id=int(document_id))
                        )
                elif entity_type == 'pre':
                    telethon_entities.append(
                        MessageEntityPre(offset=offset, length=length, language=entity.get('language', ''))
                    )
                else:
                    telethon_entities.append(
                        entity_map[entity_type](offset=offset, length=length)
                    )
            except Exception as e:
                print(f"[ENTITIES] Error converting entity {entity_type}: {e}")
    
    return telethon_entities if telethon_entities else None


class BroadcastResult:
    """Result of a single broadcast attempt."""
    def __init__(self, group: str, status: str, error: str = None):
        self.group = group
        self.status = status  # 'sent', 'failed', 'skipped', 'flood_wait'
        self.error = error
        self.timestamp = datetime.now()


class AccountWorker:
    """
    Independent worker for a single account in parallel broadcasting.
    Each account manages its own groups, delays, and status.
    """
    
    def __init__(self, account: Dict[str, Any], api_id: int, api_hash: str):
        self.account = account
        self.account_id = account['id']
        self.phone = account.get('phone_number', 'Unknown')
        self.session_string = account.get('session_string')
        self.api_id = api_id
        self.api_hash = api_hash
        
        # Status tracking
        self.status = "idle"  # idle, running, flood_wait, limited, error
        self.flood_wait_until = None
        self.error_count = 0
        self.success_count = 0
        self.consecutive_errors = 0
        
        # Delay management - fixed 60 second delay
        self.base_delay = 60
        self.current_delay = 60
        self.min_delay = 60
        self.max_delay = 60
        
        # Groups to process
        self.groups = []
        self.current_group_index = 0
        self.current_group_name = None
        
        # Results
        self.sent = 0
        self.failed = 0
        self.recent_logs = []
    
    def get_status_display(self) -> str:
        """Get human-readable status."""
        if self.status == "flood_wait" and self.flood_wait_until:
            remaining = (self.flood_wait_until - datetime.now()).total_seconds()
            if remaining > 0:
                return f"flood_wait ({int(remaining)}s)"
        return self.status
    
    def calculate_delay(self, success: bool, flood_wait: int = None) -> float:
        """Calculate next delay - fixed 60 seconds like adbot."""
        if flood_wait:
            # FloodWait: wait exactly the required time (no extra buffer)
            self.flood_wait_until = datetime.now() + timedelta(seconds=flood_wait)
            self.status = "flood_wait"
            return flood_wait
        
        # Reset status on success
        if success:
            self.consecutive_errors = 0
            self.status = "running"
        
        # Fixed 60 second delay like adbot
        return 60
    
    def add_log(self, group: str, status: str, error: str = None):
        """Add to recent logs."""
        self.recent_logs.append({
            "group": group[:40] if group else "Unknown",
            "status": status,
            "error": error[:30] if error else None,
            "time": datetime.now().strftime("%H:%M:%S"),
            "account": self.phone  # Add account phone for display
        })
        if len(self.recent_logs) > 10:
            self.recent_logs.pop(0)



class Broadcaster:
    """
    Core broadcasting engine for sending messages to Telegram groups.
    
    Features:
    - Smart rate limiting with adaptive delays
    - Forum topic detection
    - Multi-account support with rotation
    - Auto-recovery from FloodWait
    - Detailed logging and analytics
    """
    
    API_ID = int(os.getenv("TELEGRAM_API_ID", "21219293"))
    API_HASH = os.getenv("TELEGRAM_API_HASH", "cff5d321b676104840cf282a742381e0")
    
    def __init__(self, db):
        self.db = db
        self.running_campaigns = {}  # campaign_id -> asyncio.Task
        self.stop_flags = {}  # campaign_id -> bool
        self.removed_accounts = {}  # campaign_id -> set of account_ids to remove
        self.campaign_progress = {}  # campaign_id -> { sent, failed, total, current_group, recent_logs, status }
    
    def remove_account(self, campaign_id: int, account_id: int) -> bool:
        """Remove an account from a running campaign without stopping others."""
        if campaign_id not in self.removed_accounts:
            self.removed_accounts[campaign_id] = set()
        self.removed_accounts[campaign_id].add(account_id)
        print(f"[BROADCASTER] Account {account_id} marked for removal from campaign {campaign_id}")
        return True
    
    def is_account_removed(self, campaign_id: int, account_id: int) -> bool:
        """Check if an account has been removed from a campaign."""
        return account_id in self.removed_accounts.get(campaign_id, set())
    
    def get_progress(self, campaign_id: int) -> Dict[str, Any]:
        """Get live progress for a campaign."""
        return self.campaign_progress.get(campaign_id, {
            "sent": 0,
            "failed": 0,
            "total": 0,
            "current_group": None,
            "recent_logs": [],
            "status": "idle"
        })
    
    async def get_all_dialogs(self, session_string: str) -> List[Dict[str, Any]]:
        """
        Get all groups/channels/supergroups from an account.
        This fetches all dialogs where the account can send messages.
        """
        if not session_string:
            print(f"[GET_DIALOGS] No session string provided!")
            return []
            
        try:
            print(f"[GET_DIALOGS] Connecting with session string (length: {len(session_string)})...")
            client = TelegramClient(StringSession(session_string), self.API_ID, self.API_HASH)
            await client.connect()
            print(f"[GET_DIALOGS] Connected, checking authorization...")
            
            if not await client.is_user_authorized():
                print(f"[GET_DIALOGS] User NOT authorized! Session may be invalid.")
                await client.disconnect()
                return []
            
            print(f"[GET_DIALOGS] Authorized, fetching dialogs...")
            dialogs = []
            async for dialog in client.iter_dialogs():
                # Only include groups and channels (not private chats)
                if dialog.is_group or dialog.is_channel:
                    entity = dialog.entity
                    is_forum = getattr(entity, 'forum', False)
                    
                    dialogs.append({
                        "id": dialog.id,
                        "name": dialog.name or str(dialog.id),
                        "username": getattr(entity, 'username', None),
                        "is_channel": dialog.is_channel,
                        "is_group": dialog.is_group,
                        "is_forum": is_forum,
                        "unread_count": dialog.unread_count
                    })
            
            print(f"[GET_DIALOGS] Found {len(dialogs)} groups/channels")
            await client.disconnect()
            return dialogs
            
        except Exception as e:
            print(f"[GET_DIALOGS] ERROR: {type(e).__name__}: {e}")
            return []
    
    async def forward_to_group(
        self,
        client: TelegramClient,
        group,  # Can be entity, id, or username
        from_chat: int,
        message_id: int
    ) -> BroadcastResult:
        """
        Forward a message to a group (matches original adbot implementation).
        """
        import random
        from telethon.tl.functions.messages import ForwardMessagesRequest
        
        try:
            # Get the target entity
            try:
                if isinstance(group, dict):
                    entity = await client.get_entity(group.get('id') or group.get('username'))
                    group_id = group.get('id')
                else:
                    entity = await client.get_entity(group)
                    group_id = entity.id
            except Exception as e:
                return BroadcastResult(str(group), 'failed', f'Cannot access target: {str(e)[:50]}')
            
            # PRE-CHECK: Detect slow mode BEFORE attempting to forward
            try:
                from telethon.tl.functions.channels import GetFullChannelRequest
                full_channel = await client(GetFullChannelRequest(entity))
                slowmode_seconds = getattr(full_channel.full_chat, 'slowmode_seconds', 0) or 0
                slowmode_next_send = getattr(full_channel.full_chat, 'slowmode_next_send_date', None)
                
                if slowmode_seconds > 0:
                    import time
                    current_time = int(time.time())
                    
                    # Check if we need to wait before sending
                    if slowmode_next_send:
                        wait_time = slowmode_next_send - current_time
                        if wait_time > 0:
                            print(f"[FORWARD] Slow mode: must wait {wait_time}s for {group_id}")
                            return BroadcastResult(str(group), 'failed', f'Slow mode: wait {wait_time}s')
                    
                    print(f"[FORWARD] Slow mode enabled ({slowmode_seconds}s) for {group_id}, attempting forward...")
            except Exception as e:
                # If we can't check slow mode, continue anyway
                print(f"[FORWARD] Could not pre-check slow mode: {e}")
            
            # Try to access source to verify permissions
            try:
                await client.get_entity(from_chat)
            except:
                try:
                    await client.get_messages(from_chat, limit=1)
                except:
                    return BroadcastResult(str(group), 'failed', 'Cannot access forward source')
            
            # Check if it's a forum
            is_forum = getattr(entity, 'forum', False)
            topic_id = None
            
            if is_forum:
                try:
                    topics = await client(GetForumTopicsRequest(
                        channel=entity,
                        offset_date=None,
                        offset_id=0,
                        offset_topic=0,
                        limit=20  # Fetch more to find an open topic
                    ))
                    
                    # First try to find an open General topic
                    for topic in topics.topics:
                        if isinstance(topic, ForumTopic):
                            is_closed = getattr(topic, 'closed', False)
                            if not is_closed and (topic.title.lower() == 'general' or topic.id == 1):
                                topic_id = topic.id
                                print(f"[FORWARD] Using open General topic {topic_id}")
                                break
                    
                    # If General is closed, find any open topic
                    if not topic_id:
                        for topic in topics.topics:
                            if isinstance(topic, ForumTopic):
                                is_closed = getattr(topic, 'closed', False)
                                if not is_closed:
                                    topic_id = topic.id
                                    print(f"[FORWARD] General closed, using open topic {topic_id}: {topic.title}")
                                    break
                    
                    # All topics are closed
                    if not topic_id:
                        print(f"[FORWARD] All topics closed for {group_id}")
                        return BroadcastResult(str(group), 'failed', 'All forum topics closed')
                        
                except Exception as e:
                    print(f"[FORWARD] Could not get topics: {e}")
                    topic_id = 1  # Fallback
            
            # Forward the message - match original adbot exactly
            sent_msg = None
            if topic_id:
                # For forums: use ForwardMessagesRequest with top_msg_id (same as original adbot)
                result = await client(ForwardMessagesRequest(
                    from_peer=from_chat,
                    id=[message_id],  # Must be a list
                    to_peer=entity,
                    top_msg_id=topic_id,
                    random_id=[random.randint(0, 2**63 - 1)]
                ))
                # Get message from result
                if hasattr(result, 'updates') and result.updates:
                    for update in result.updates:
                        if hasattr(update, 'message') and hasattr(update.message, 'id'):
                            sent_msg = update.message
                            break
                print(f"[FORWARD] Forum: forwarded to {entity.id} topic {topic_id}")
            else:
                # For regular groups: use simple forward_messages (same as original adbot)
                sent_msg = await client.forward_messages(entity, message_id, from_chat)
                if isinstance(sent_msg, list):
                    sent_msg = sent_msg[0] if sent_msg else None
                print(f"[FORWARD] Regular: forwarded to {entity.id}")
            
            group_name = group.get('name', str(group)) if isinstance(group, dict) else str(group)
            return BroadcastResult(group_name, 'sent')
            
        except FloodWaitError as e:
            return BroadcastResult(str(group), 'flood_wait', f'Wait {e.seconds}s')
        except SlowModeWaitError as e:
            return BroadcastResult(str(group), 'failed', f'Slow mode: {e.seconds}s')
        except ChatWriteForbiddenError:
            return BroadcastResult(str(group), 'failed', 'Write forbidden')
        except UserBannedInChannelError:
            return BroadcastResult(str(group), 'failed', 'Banned')
        except Exception as e:
            print(f"[FORWARD] Error: {e}")
            return BroadcastResult(str(group), 'failed', str(e)[:80])
    
    async def send_to_group(
        self, 
        client: TelegramClient, 
        group, 
        message: str,
        media_file_id: str = None,
        message_type: str = "send",  # "send" or "forward"
        forward_from_chat: int = None,
        forward_message_id: int = None,
        forward_from_username: str = None,  # For public channels
        formatting_entities: list = None  # Telethon entities for premium emoji/formatting
    ) -> BroadcastResult:
        """
        Send or forward a message to a single group.
        Handles forum detection and various error cases.
        If formatting_entities provided, uses them for premium emojis/formatting.
        """
        # Debug: Log forward mode check
        print(f"[SEND_TO_GROUP] message_type={message_type}, forward_from_chat={forward_from_chat}, forward_message_id={forward_message_id}, username={forward_from_username}")
        
        # Resolve forward_from_username to channel entity if needed
        from_entity = None
        if message_type == "forward" and forward_message_id and not forward_from_chat and forward_from_username:
            try:
                from_entity = await client.get_entity(forward_from_username)
                # For channels/supergroups, format the ID properly with -100 prefix (same as original adbot)
                if hasattr(from_entity, 'broadcast') or hasattr(from_entity, 'megagroup'):
                    # It's a channel or supergroup - use -100 prefix
                    forward_from_chat = int(f"-100{from_entity.id}")
                else:
                    forward_from_chat = from_entity.id
                print(f"[SEND_TO_GROUP] Resolved username '{forward_from_username}' to chat ID {forward_from_chat}")
            except Exception as e:
                print(f"[SEND_TO_GROUP] Failed to resolve username '{forward_from_username}': {e}")
                return BroadcastResult(str(group), 'failed', f'Cannot resolve forward source: {str(e)[:50]}')
        
        # If forward mode
        if message_type == "forward" and forward_from_chat and forward_message_id:
            print(f"[SEND_TO_GROUP] >>> Using FORWARD mode! from_chat={forward_from_chat}, msg_id={forward_message_id}")
            return await self.forward_to_group(client, group, forward_from_chat, forward_message_id)
        else:
            print(f"[SEND_TO_GROUP] >>> Using SEND mode")
        
        try:
            # Get the entity
            try:
                if isinstance(group, dict):
                    entity = await client.get_entity(group.get('id') or group.get('username'))
                    group_name = group.get('name', str(group.get('id')))
                else:
                    entity = await client.get_entity(group)
                    group_name = str(group)
            except PeerIdInvalidError:
                return BroadcastResult(str(group), 'failed', 'Invalid group')
            except ChannelPrivateError:
                return BroadcastResult(str(group), 'failed', 'Private channel')
            except Exception as e:
                return BroadcastResult(str(group), 'failed', f'Cannot access: {str(e)[:50]}')
            
            # PRE-FILTER: Check if we have permission to send messages
            try:
                # Check if messages are restricted for regular users
                default_banned = getattr(entity, 'default_banned_rights', None)
                if default_banned and getattr(default_banned, 'send_messages', False):
                    # Check if we have admin rights that override
                    admin_rights = getattr(entity, 'admin_rights', None)
                    if not admin_rights:
                        return BroadcastResult(group_name, 'skipped', 'No posting permission')
                
                # Check if we're explicitly banned from sending
                banned_rights = getattr(entity, 'banned_rights', None)
                if banned_rights and getattr(banned_rights, 'send_messages', False):
                    return BroadcastResult(group_name, 'skipped', 'Banned from posting')
            except Exception as perm_err:
                # If permission check fails, continue and try to send anyway
                print(f"[BROADCASTER] Permission check failed for {group_name}: {perm_err}")
            
            # PRE-FILTER: Check for slow mode
            slowmode_seconds = getattr(entity, 'slowmode_seconds', 0)
            if slowmode_seconds and slowmode_seconds > 0:
                return BroadcastResult(group_name, 'skipped', f'Slow mode: {slowmode_seconds}s')
            
            # Check if it's a forum
            is_forum = getattr(entity, 'forum', False)
            
            if is_forum:
                # FORUM: Send to ALL topics
                results = []
                try:
                    topics = await client(GetForumTopicsRequest(
                        channel=entity,
                        offset_date=None,
                        offset_id=0,
                        offset_topic=0,
                        limit=100  # Get more topics
                    ))
                    
                    # Send to each topic
                    for topic in topics.topics:
                        if not isinstance(topic, ForumTopic):
                            continue
                        
                        # Skip closed topics
                        if getattr(topic, 'closed', False):
                            continue
                        
                        topic_name = f"{group_name} > {topic.title}"
                        
                        try:
                            if media_file_id:
                                await client.send_file(
                                    entity,
                                    media_file_id,
                                    caption=message,
                                    reply_to=topic.id,
                                    formatting_entities=formatting_entities if formatting_entities else None,
                                    parse_mode=None if formatting_entities else 'html'
                                )
                            else:
                                await client.send_message(
                                    entity,
                                    message,
                                    reply_to=topic.id,
                                    formatting_entities=formatting_entities if formatting_entities else None,
                                    parse_mode=None if formatting_entities else 'html'
                                )
                            results.append(BroadcastResult(topic_name, 'sent'))
                            
                            # 1 minute delay between topics (same as between groups)
                            await asyncio.sleep(60)
                            
                        except SlowModeWaitError as e:
                            # Slow mode on ANY topic = skip entire forum (as skipped, not failed)
                            results.append(BroadcastResult(group_name, 'skipped', f'Forum slow mode: {e.seconds}s'))
                            break  # Skip remaining topics
                        except RPCError as e:
                            error_str = str(e).lower()
                            # If banned or forbidden, leave and rejoin the group
                            if 'banned' in error_str or 'forbidden' in error_str or 'restricted' in error_str:
                                try:
                                    from telethon.tl.functions.channels import LeaveChannelRequest, JoinChannelRequest
                                    await client(LeaveChannelRequest(entity))
                                    print(f"[BROADCASTER] Left banned group: {group_name}, attempting rejoin...")
                                    await asyncio.sleep(2)
                                    await client(JoinChannelRequest(entity))
                                    print(f"[BROADCASTER] Rejoined group: {group_name}")
                                    results.append(BroadcastResult(group_name, 'failed', 'Banned - rejoined'))
                                except Exception as rejoin_err:
                                    print(f"[BROADCASTER] Rejoin failed: {rejoin_err}")
                                    results.append(BroadcastResult(group_name, 'failed', 'Banned - rejoin failed'))
                                break  # Skip remaining topics, will retry next cycle
                            elif 'TOPIC_CLOSED' in str(e) or 'TOPIC_DELETED' in str(e):
                                results.append(BroadcastResult(topic_name, 'failed', 'Topic closed'))
                            else:
                                results.append(BroadcastResult(topic_name, 'failed', str(e)[:50]))
                        except Exception as e:
                            error_str = str(e).lower()
                            # Also check general exceptions for banned
                            if 'banned' in error_str or 'forbidden' in error_str:
                                try:
                                    from telethon.tl.functions.channels import LeaveChannelRequest
                                    await client(LeaveChannelRequest(entity))
                                    print(f"[BROADCASTER] Left banned group: {group_name}")
                                    results.append(BroadcastResult(group_name, 'failed', 'Banned - left group'))
                                except:
                                    results.append(BroadcastResult(group_name, 'failed', 'Banned'))
                                break
                            results.append(BroadcastResult(topic_name, 'failed', str(e)[:50]))
                    
                    # Return list of results for all topics
                    return results if results else [BroadcastResult(group_name, 'failed', 'No accessible topics')]
                    
                except Exception as e:
                    return BroadcastResult(group_name, 'failed', f'Forum error: {str(e)[:50]}')
            else:
                # Regular group/channel - send normally
                if media_file_id:
                    await client.send_file(
                        entity,
                        media_file_id,
                        caption=message,
                        formatting_entities=formatting_entities if formatting_entities else None,
                        parse_mode=None if formatting_entities else 'html'
                    )
                else:
                    await client.send_message(
                        entity,
                        message,
                        formatting_entities=formatting_entities if formatting_entities else None,
                        parse_mode=None if formatting_entities else 'html'
                    )
                
                return BroadcastResult(group_name, 'sent')
            
        except FloodWaitError as e:
            return BroadcastResult(str(group), 'flood_wait', f'Wait {e.seconds}s')
        except SlowModeWaitError as e:
            # Slow mode - mark as skipped so it doesn't count as failed
            return BroadcastResult(str(group), 'skipped', f'Slow mode: {e.seconds}s')
        except (ChatWriteForbiddenError, UserBannedInChannelError) as e:
            # Banned or forbidden - try leave, rejoin, and retry
            try:
                from telethon.tl.functions.channels import LeaveChannelRequest, JoinChannelRequest
                
                # Step 1: Leave the group
                await client(LeaveChannelRequest(entity))
                print(f"[BROADCASTER] Left banned group: {group}, attempting rejoin...")
                
                # Step 2: Wait a moment
                await asyncio.sleep(2)
                
                # Step 3: Rejoin the group
                await client(JoinChannelRequest(entity))
                print(f"[BROADCASTER] Rejoined group: {group}, retrying message...")
                
                # Step 4: Wait and retry sending
                await asyncio.sleep(1)
                
                if media_file_id:
                    await client.send_file(
                        entity,
                        media_file_id,
                        caption=message,
                        formatting_entities=formatting_entities if formatting_entities else None,
                        parse_mode=None if formatting_entities else 'html'
                    )
                else:
                    await client.send_message(
                        entity,
                        message,
                        formatting_entities=formatting_entities if formatting_entities else None,
                        parse_mode=None if formatting_entities else 'html'
                    )
                
                print(f"[BROADCASTER] Retry successful after rejoin: {group}")
                return BroadcastResult(str(group), 'sent')
                
            except Exception as rejoin_err:
                # Even if send failed, the group is still joined - mark as such
                print(f"[BROADCASTER] Send after rejoin failed: {rejoin_err}")
                return BroadcastResult(str(group), 'failed', 'Rejoined - send pending')
        except ChatAdminRequiredError:
            return BroadcastResult(str(group), 'failed', 'Admin required')
        except MessageTooLongError:
            return BroadcastResult(str(group), 'failed', 'Message too long')
        except Exception as e:
            error_str = str(e).lower()
            # Check for banned in general exceptions
            if 'banned' in error_str or 'forbidden' in error_str:
                try:
                    from telethon.tl.functions.channels import LeaveChannelRequest
                    await client(LeaveChannelRequest(entity))
                    print(f"[BROADCASTER] Left banned group: {group}")
                    return BroadcastResult(str(group), 'failed', 'Banned - left group')
                except:
                    pass
            return BroadcastResult(str(group), 'failed', str(e)[:80])
    
    async def _account_worker_task(
        self,
        worker: AccountWorker,
        campaign: Dict[str, Any],
        campaign_id: int,
        message_content: str,
        template_entities,
        db
    ) -> Dict[str, Any]:
        """
        Run broadcasting for a single account.
        This runs independently and concurrently with other account workers.
        """
        results = {"sent": 0, "failed": 0, "account_id": worker.account_id, "phone": worker.phone}
        
        worker.status = "fetching_groups"
        
        # Fetch this account's dialogs (groups it's joined)
        try:
            groups = await self.get_all_dialogs(worker.session_string)
            worker.groups = groups
            print(f"[WORKER {worker.phone}] Found {len(groups)} groups")
        except Exception as e:
            print(f"[WORKER {worker.phone}] Error fetching groups: {e}")
            worker.status = "error"
            return results
        
        if not groups:
            worker.status = "no_groups"
            return results
        
        # Update total count in progress
        worker.total_groups = len(groups)
        if campaign_id in self.campaign_progress:
            # Update overall total
            self.campaign_progress[campaign_id]["total"] += len(groups)
            # Update per-account total
            if worker.account_id in self.campaign_progress[campaign_id].get("accounts", {}):
                self.campaign_progress[campaign_id]["accounts"][worker.account_id]["total"] = len(groups)
        
        worker.status = "running"
        
        # Process each group this account has access to
        cycle = 0
        while not self.stop_flags.get(campaign_id, False):
            cycle += 1
            
            # Update cycle count in progress at START of each cycle
            # Use max() so faster workers don't get overwritten by slower workers
            if campaign_id in self.campaign_progress:
                current_cycle = self.campaign_progress[campaign_id].get("cycle", 1)
                self.campaign_progress[campaign_id]["cycle"] = max(current_cycle, cycle)
            
            for i, group in enumerate(groups):
                if self.stop_flags.get(campaign_id, False):
                    break
                
                # Check if this account was removed from the campaign
                if self.is_account_removed(campaign_id, worker.account_id):
                    print(f"[WORKER {worker.phone}] Removed from campaign, stopping...")
                    worker.status = "removed"
                    return results
                
                # Check if worker is limited
                if worker.status == "limited":
                    print(f"[WORKER {worker.phone}] Limited, pausing 10 minutes...")
                    await asyncio.sleep(600)
                    worker.status = "running"
                    worker.consecutive_errors = 0
                
                # Check flood wait
                if worker.status == "flood_wait" and worker.flood_wait_until:
                    remaining = (worker.flood_wait_until - datetime.now()).total_seconds()
                    if remaining > 0:
                        print(f"[WORKER {worker.phone}] FloodWait: waiting {int(remaining)}s")
                        await asyncio.sleep(remaining)
                    worker.status = "running"
                    worker.flood_wait_until = None
                
                group_name = group.get('name', str(group.get('id', 'Unknown'))) if isinstance(group, dict) else str(group)
                worker.current_group_name = group_name
                worker.current_group_index = i + 1
                
                # Connect and send
                try:
                    client = TelegramClient(
                        StringSession(worker.session_string),
                        self.API_ID,
                        self.API_HASH
                    )
                    await client.connect()
                    
                    if not await client.is_user_authorized():
                        worker.status = "unauthorized"
                        await client.disconnect()
                        break
                    
                    # Send message to this group
                    result = await self.send_to_group(
                        client=client,
                        group=group,
                        message=message_content,
                        formatting_entities=template_entities,
                        message_type=campaign.get('send_mode', 'send'),  # send_mode column: "send" or "forward"
                        forward_from_chat=campaign.get('forward_from_chat'),
                        forward_message_id=campaign.get('forward_message_id'),
                        forward_from_username=campaign.get('forward_from_username')
                    )
                    
                    await client.disconnect()
                    
                    # Process result
                    result_list = result if isinstance(result, list) else [result]
                    
                    for res in result_list:
                        if res.status == 'sent':
                            results["sent"] += 1
                            worker.sent += 1
                            worker.success_count += 1
                            
                            # Log broadcast
                            db.log_broadcast(
                                campaign_id=campaign_id,
                                account_id=worker.account_id,
                                client_id=campaign['client_id'],
                                group_name=res.group[:100],
                                status='sent'
                            )
                            
                            delay = worker.calculate_delay(success=True)
                            
                        elif res.status == 'flood_wait':
                            # Extract wait time
                            wait_match = re.search(r'(\d+)', res.error or '')
                            wait_time = int(wait_match.group(1)) if wait_match else 60
                            
                            delay = worker.calculate_delay(success=False, flood_wait=wait_time)
                        
                        elif res.status == 'skipped':
                            # Pre-filtered group - no posting permission, skip quickly
                            db.log_broadcast(
                                campaign_id=campaign_id,
                                account_id=worker.account_id,
                                client_id=campaign['client_id'],
                                group_name=res.group[:100],
                                status='skipped',
                                error_message=res.error
                            )
                            # Minimal delay for skipped groups (no actual send attempt)
                            delay = 1
                            
                        else:  # Failed
                            results["failed"] += 1
                            worker.failed += 1
                            
                            db.log_broadcast(
                                campaign_id=campaign_id,
                                account_id=worker.account_id,
                                client_id=campaign['client_id'],
                                group_name=res.group[:100],
                                status='failed',
                                error_message=res.error
                            )
                            
                            delay = worker.calculate_delay(success=False)
                        
                        worker.add_log(res.group, res.status, res.error)
                    
                    # Apply delay before next group
                    if not self.stop_flags.get(campaign_id, False):
                        await asyncio.sleep(delay)
                    
                except Exception as e:
                    print(f"[WORKER {worker.phone}] Error: {e}")
                    results["failed"] += 1
                    worker.failed += 1
                    worker.calculate_delay(success=False)
            
            # Cycle complete - random 10-15 minute break before next cycle
            if not self.stop_flags.get(campaign_id, False) and not self.is_account_removed(campaign_id, worker.account_id):
                # Update cycle count in progress (use max to not overwrite faster workers)
                if campaign_id in self.campaign_progress:
                    current_cycle = self.campaign_progress[campaign_id].get("cycle", 1)
                    self.campaign_progress[campaign_id]["cycle"] = max(current_cycle, cycle)
                
                cycle_pause = random.randint(600, 900)  # Random 10-15 minutes
                pause_mins = cycle_pause // 60
                worker.status = f"cycle_break (cycle {cycle}, next in {pause_mins}m)"
                print(f"[WORKER {worker.phone}] Cycle {cycle} complete, taking {pause_mins} min break...")
                
                # Wait in chunks to check stop flag
                pause_chunks = cycle_pause // 10
                for _ in range(pause_chunks):
                    if self.stop_flags.get(campaign_id, False) or self.is_account_removed(campaign_id, worker.account_id):
                        break
                    await asyncio.sleep(10)
                
                worker.status = "running"
        
        worker.status = "stopped"
        return results
    
    async def run_campaign_parallel(
        self,
        campaign_id: int,
        on_progress: Callable[[int, int, str], None] = None
    ) -> Dict[str, Any]:
        """
        Run campaign with ALL accounts broadcasting simultaneously.
        Each account sends to its OWN groups in parallel.
        """
        from database import db
        
        print(f"[BROADCASTER] Starting PARALLEL campaign {campaign_id}")
        
        # Initialize progress with per-account tracking
        self.campaign_progress[campaign_id] = {
            "sent": 0,
            "failed": 0,
            "total": 0,
            "current_group": "Initializing parallel workers...",
            "recent_logs": [],
            "status": "starting",
            "mode": "parallel",
            "cycle": 1,  # Track cycle count
            "accounts": {}  # account_id -> {status, sent, failed, current_group}
        }
        
        # Get campaign
        campaign = db.get_campaign_by_id(campaign_id)
        if not campaign:
            self.campaign_progress[campaign_id]["status"] = "error"
            return {"error": "Campaign not found"}
        
        # Load template if set
        template_entities = None
        template_id = campaign.get('template_id')
        if template_id:
            template = db.get_template_by_id(template_id)
            if template:
                json_entities = template.get('entities')
                if json_entities:
                    template_entities = convert_entities_to_telethon(json_entities)
                if template.get('text_content'):
                    campaign['message_content'] = template['text_content']
        
        message_content = campaign.get('message_content', '')
        
        # Debug: Log forward message settings
        send_mode = campaign.get('send_mode', 'send')
        forward_from_chat = campaign.get('forward_from_chat')
        forward_message_id = campaign.get('forward_message_id')
        print(f"[BROADCASTER] Campaign {campaign_id}: send_mode={send_mode}, forward_from_chat={forward_from_chat}, forward_message_id={forward_message_id}")
        print(f"[BROADCASTER] message_content length: {len(message_content) if message_content else 0}")
        
        # Get accounts - use campaign-specific accounts if set, otherwise all client accounts
        all_accounts = db.get_client_accounts(campaign['client_id'])
        if not all_accounts:
            self.campaign_progress[campaign_id]["status"] = "error"
            return {"error": "No accounts available"}
        
        # Filter to campaign-assigned accounts
        accounts = []
        
        # Check for multiple accounts (JSON array)
        import json
        account_ids_json = campaign.get('account_ids_json')
        if account_ids_json:
            try:
                account_ids = json.loads(account_ids_json)
                accounts = [a for a in all_accounts if a['id'] in account_ids]
            except:
                pass
        
        # Check for single account assignment
        if not accounts and campaign.get('account_id'):
            accounts = [a for a in all_accounts if a['id'] == campaign['account_id']]
        
        # If no specific accounts assigned, use all client accounts
        if not accounts:
            accounts = all_accounts
        
        active_accounts = [a for a in accounts if a.get('is_active', True)]
        if not active_accounts:
            self.campaign_progress[campaign_id]["status"] = "error"
            return {"error": "No active accounts"}
        
        print(f"[BROADCASTER] Launching {len(active_accounts)} parallel workers")
        
        # Create workers for each account
        workers: List[AccountWorker] = []
        for acc in active_accounts:
            worker = AccountWorker(acc, self.API_ID, self.API_HASH)
            workers.append(worker)
            
            # Initialize progress tracking for this account
            self.campaign_progress[campaign_id]["accounts"][acc['id']] = {
                "phone": acc.get('phone_number', 'Unknown'),
                "status": "starting",
                "sent": 0,
                "failed": 0,
                "total": 0,
                "current_group": None
            }
        
        # Initialize campaign state
        self.stop_flags[campaign_id] = False
        db.update_campaign_status(campaign_id, "running")
        self.campaign_progress[campaign_id]["status"] = "running"
        
        # Create background task to update progress
        async def update_progress():
            while not self.stop_flags.get(campaign_id, False):
                total_sent = sum(w.sent for w in workers)
                total_failed = sum(w.failed for w in workers)
                
                self.campaign_progress[campaign_id]["sent"] = total_sent
                self.campaign_progress[campaign_id]["failed"] = total_failed
                
                # Update per-account status
                for w in workers:
                    self.campaign_progress[campaign_id]["accounts"][w.account_id] = {
                        "phone": w.phone,
                        "status": w.get_status_display(),
                        "sent": w.sent,
                        "failed": w.failed,
                        "current_group": w.current_group_name,
                        "delay": round(w.current_delay, 1)
                    }
                
                # Aggregate recent logs from all workers
                all_logs = []
                for w in workers:
                    for log in w.recent_logs:
                        all_logs.append({**log, "account": w.phone[-4:]})
                all_logs.sort(key=lambda x: x.get('time', ''), reverse=True)
                self.campaign_progress[campaign_id]["recent_logs"] = all_logs[:30]
                
                await asyncio.sleep(2)
        
        # Start progress updater
        progress_task = asyncio.create_task(update_progress())
        
        # Launch all workers simultaneously
        try:
            worker_tasks = [
                self._account_worker_task(w, campaign, campaign_id, message_content, template_entities, db)
                for w in workers
            ]
            
            results = await asyncio.gather(*worker_tasks, return_exceptions=True)
            
        except Exception as e:
            print(f"[BROADCASTER] Parallel execution error: {e}")
        finally:
            self.stop_flags[campaign_id] = True
            progress_task.cancel()
        
        # Aggregate results
        total_sent = sum(w.sent for w in workers)
        total_failed = sum(w.failed for w in workers)
        
        db.update_campaign_status(campaign_id, "stopped")
        self.campaign_progress[campaign_id]["status"] = "stopped"
        
        # Cleanup
        if campaign_id in self.stop_flags:
            del self.stop_flags[campaign_id]
        
        return {
            "sent": total_sent,
            "failed": total_failed,
            "accounts": len(workers),
            "mode": "parallel"
        }
    

    async def run_campaign(
        self, 
        campaign_id: int,
        on_progress: Callable[[int, int, str], None] = None
    ) -> Dict[str, Any]:
        """
        Run a complete campaign broadcast.
        
        Args:
            campaign_id: ID of the campaign to run
            on_progress: Optional callback for progress updates (sent, total, status)
        
        Returns:
            Dict with broadcast results and statistics
        """
        from database import db
        
        print(f"[BROADCASTER] Starting campaign {campaign_id}")
        
        # Initialize progress early so UI can see errors
        self.campaign_progress[campaign_id] = {
            "sent": 0,
            "failed": 0,
            "total": 0,
            "current_group": "Initializing...",
            "recent_logs": [],
            "status": "starting",
            "cycle": 1
        }
        
        # Get campaign details
        campaign = db.get_campaign_by_id(campaign_id)
        if not campaign:
            print(f"[BROADCASTER] Campaign {campaign_id} not found!")
            self.campaign_progress[campaign_id]["status"] = "error"
            self.campaign_progress[campaign_id]["current_group"] = "Error: Campaign not found"
            db.update_campaign_status(campaign_id, "failed")
            return {"error": "Campaign not found"}
        
        print(f"[BROADCASTER] Campaign: {campaign.get('name')}, client_id: {campaign.get('client_id')}")
        
        # Load message template if set (for premium emojis/formatting)
        template_entities = None
        template_id = campaign.get('template_id')
        if template_id:
            template = db.get_template_by_id(template_id)
            if template:
                print(f"[BROADCASTER] Using template: {template.get('name')} with entities")
                # Convert JSON entities to Telethon format for premium emoji support
                json_entities = template.get('entities')
                if json_entities:
                    template_entities = convert_entities_to_telethon(json_entities)
                    print(f"[BROADCASTER] Converted {len(json_entities)} entities to Telethon format")
                # Also update message content from template if needed
                if template.get('text_content'):
                    campaign['message_content'] = template['text_content']
            else:
                print(f"[BROADCASTER] Template {template_id} not found, using plain message")
        
        # Get accounts for this client
        accounts = db.get_client_accounts(campaign['client_id'])
        print(f"[BROADCASTER] Found {len(accounts) if accounts else 0} accounts for client")
        if not accounts:
            print(f"[BROADCASTER] No accounts available!")
            self.campaign_progress[campaign_id]["status"] = "error"
            self.campaign_progress[campaign_id]["current_group"] = "Error: No accounts assigned"
            db.update_campaign_status(campaign_id, "failed")
            return {"error": "No accounts available"}
        
        # Filter active accounts
        active_accounts = [a for a in accounts if a.get('is_active', True)]
        print(f"[BROADCASTER] Active accounts: {len(active_accounts)}")
        if not active_accounts:
            print(f"[BROADCASTER] No active accounts!")
            self.campaign_progress[campaign_id]["status"] = "error"
            self.campaign_progress[campaign_id]["current_group"] = "Error: No active accounts"
            db.update_campaign_status(campaign_id, "failed")
            return {"error": "No active accounts"}
        
        # Determine which account to use
        selected_account_id = campaign.get('account_id')
        if selected_account_id:
            # Use specifically selected account
            selected_account = next((a for a in active_accounts if a['id'] == selected_account_id), None)
            if not selected_account:
                print(f"[BROADCASTER] Selected account {selected_account_id} not found in active accounts")
                self.campaign_progress[campaign_id]["status"] = "error"
                self.campaign_progress[campaign_id]["current_group"] = f"Error: Selected account not found or inactive"
                db.update_campaign_status(campaign_id, "failed")
                return {"error": "Selected account not found or inactive"}
            broadcast_account = selected_account
            print(f"[BROADCASTER] Using SELECTED account: {broadcast_account.get('phone_number')}")
        else:
            # Use first account (default behavior)
            broadcast_account = active_accounts[0]
            print(f"[BROADCASTER] Using FIRST account: {broadcast_account.get('phone_number')}")
        
        # Determine target groups
        send_mode = campaign.get('send_mode', 'send')
        broadcast_all = True  # Default to broadcast_all
        
        # Check if we should use database groups or fetch from account
        db_groups = db.get_campaign_groups(campaign_id)
        print(f"[BROADCASTER] DB groups: {len(db_groups) if db_groups else 0}")
        
        if db_groups:
            # Use groups from database
            groups = [{"id": g.get('group_username'), "name": g.get('group_username')} for g in db_groups]
        else:
            # Broadcast to all dialogs from the selected account
            self.campaign_progress[campaign_id]["current_group"] = f"Fetching groups from {broadcast_account.get('phone_number')}..."
            print(f"[BROADCASTER] Fetching dialogs from account: {broadcast_account.get('phone_number')}")
            
            try:
                groups = await self.get_all_dialogs(broadcast_account.get('session_string'))
            except Exception as e:
                print(f"[BROADCASTER] Error fetching dialogs: {e}")
                self.campaign_progress[campaign_id]["status"] = "error"
                self.campaign_progress[campaign_id]["current_group"] = f"Error: Failed to connect - {str(e)[:50]}"
                db.update_campaign_status(campaign_id, "failed")
                return {"error": f"Failed to fetch dialogs: {e}"}
            
            print(f"[BROADCASTER] Got {len(groups) if groups else 0} groups from account")
            if not groups:
                print(f"[BROADCASTER] No groups found on account!")
                self.campaign_progress[campaign_id]["status"] = "error"
                self.campaign_progress[campaign_id]["current_group"] = "Error: Account has no joined groups"
                db.update_campaign_status(campaign_id, "failed")
                return {"error": "No groups found on account"}
        
        # Get forward settings
        forward_from_chat = campaign.get('forward_from_chat')
        forward_message_id = campaign.get('forward_message_id')
        forward_from_username = campaign.get('forward_from_username')
        
        # Initialize campaign state
        self.stop_flags[campaign_id] = False
        results = {
            "sent": 0,
            "failed": 0,
            "skipped": 0,
            "flood_waits": 0,
            "total_wait_time": 0,
            "details": []
        }
        
        # Update campaign status
        db.update_campaign_status(campaign_id, "running")
        
        # =============================================
        # SMART ANTI-SPAM RATE LIMITING SYSTEM
        # =============================================
        # Based on Telegram's known limits and best practices:
        # - ~30 msgs/sec bulk limit (we use much slower for safety)
        # - Exponential backoff on errors
        # - Account rotation on failures
        # - Variable delays to appear human-like
        # - Rest periods after batches
        
        # Base settings - SAFE values that won't trigger bans
        BASE_DELAY = 25  # 25 seconds base - safe window
        MIN_DELAY = 15   # Never go below 15s
        MAX_DELAY = 120  # Cap at 2 minutes
        
        # Jitter - makes timing look human (±30%)
        JITTER_PERCENT = 0.30
        
        # Batch rest - longer pause every N messages
        BATCH_SIZE = random.randint(8, 12)  # Randomize batch size
        BATCH_REST_MIN = 60   # 1 minute minimum rest
        BATCH_REST_MAX = 180  # 3 minutes maximum rest
        
        # Cycle pause (between full loops)
        CYCLE_PAUSE = random.randint(480, 720)  # 8-12 minutes
        
        # Account health tracking
        account_failures = {}  # account_id -> consecutive_failures
        MAX_FAILURES_BEFORE_ROTATE = 3
        
        # Current delay (adaptive)
        current_delay = BASE_DELAY
        success_streak = 0
        failure_streak = 0
        batch_count = 0
        account_index = 0
        messages_this_hour = 0
        hour_start = datetime.now()
        
        # Process groups
        total = len(groups)
        cycle_count = 0
        
        # Initialize live progress
        self.campaign_progress[campaign_id] = {
            "sent": 0,
            "failed": 0,
            "total": total,
            "current_group": None,
            "current_index": 0,
            "recent_logs": [],
            "status": "running",
            "cycle": 1,
            "delay": current_delay
        }
        
        # Continuous cycling loop - runs until stopped
        while not self.stop_flags.get(campaign_id, False):
            cycle_count += 1
            self.campaign_progress[campaign_id]["cycle"] = cycle_count
            self.campaign_progress[campaign_id]["current_index"] = 0
            
            for i, group_data in enumerate(groups):
                # Check stop flag
                if self.stop_flags.get(campaign_id, False):
                    break
                
                # Get group info (can be dict from dialogs or string)
                if isinstance(group_data, dict):
                    group = group_data
                else:
                    group = group_data
                
                # Choose account: use selected account if specified, else rotate
                if selected_account_id:
                    # Use only the selected account
                    account = broadcast_account
                else:
                    # Rotate through all active accounts
                    account = active_accounts[account_index % len(active_accounts)]
                session_string = account.get('session_string')
                
                if not session_string:
                    account_index += 1
                    continue
                
                # Update progress - sending to this group
                group_name = group.get('name', str(group)) if isinstance(group, dict) else str(group)
                self.campaign_progress[campaign_id]["current_group"] = group_name
                self.campaign_progress[campaign_id]["current_index"] = i + 1
                
                # Connect client
                try:
                    client = TelegramClient(
                        StringSession(session_string),
                        self.API_ID,
                        self.API_HASH
                    )
                    await client.connect()
                    
                    if not await client.is_user_authorized():
                        account_index += 1
                        results["skipped"] += 1
                        await client.disconnect()
                        continue
                    
                    # Send or forward message
                    result = await self.send_to_group(
                        client,
                        group,
                        campaign.get('message_content', ''),
                        campaign.get('media_file_id'),
                        message_type=send_mode,
                        forward_from_chat=forward_from_chat,
                        forward_message_id=forward_message_id,
                        forward_from_username=forward_from_username,
                        formatting_entities=template_entities
                    )
                    
                    await client.disconnect()
                    
                    # Process result(s) - forums return a list, regular groups return single result
                    result_list = result if isinstance(result, list) else [result]
                    
                    for res in result_list:
                        if res.status == 'sent':
                            results["sent"] += 1
                            
                            # Log broadcast
                            db.log_broadcast(
                                campaign_id=campaign_id,
                                account_id=account['id'],
                                client_id=campaign['client_id'],
                                group_name=res.group[:100],  # Use actual topic name
                                status='sent'
                            )
                            
                            # Track success streak
                            success_streak += 1
                            failure_streak = 0
                            
                        elif res.status == 'flood_wait':
                            results["flood_waits"] += 1
                            
                            # Extract wait time
                            wait_match = re.search(r'(\d+)', res.error or '')
                            wait_time = int(wait_match.group(1)) if wait_match else 60
                            results["total_wait_time"] += wait_time
                            
                            # Format wait time for display
                            if wait_time >= 3600:
                                wait_display = f"{wait_time // 3600}h {(wait_time % 3600) // 60}m"
                            elif wait_time >= 60:
                                wait_display = f"{wait_time // 60}m {wait_time % 60}s"
                            else:
                                wait_display = f"{wait_time}s"
                            
                            # SMART FLOOD HANDLING:
                            # If wait > 5 min, SKIP this group and rotate account
                            # Don't block the entire campaign for hours!
                            if wait_time > 300:  # More than 5 minutes
                                print(f"[BROADCASTER] FloodWait {wait_display} - SKIPPING group, rotating account")
                                self.campaign_progress[campaign_id]["status"] = f"flood_skip ({wait_display})"
                                # Mark this group as failed due to flood
                                db.log_broadcast(
                                    campaign_id=campaign_id,
                                    account_id=account['id'],
                                    client_id=campaign['client_id'],
                                    group_name=res.group[:100],
                                    status='failed',
                                    error_message=f"FloodWait {wait_display} - skipped"
                                )
                                results["failed"] += 1
                                # Rotate to next account immediately
                                account_index += 1
                                await asyncio.sleep(5)  # Brief pause before continuing
                            else:
                                # Short wait - we can wait it out
                                self.campaign_progress[campaign_id]["status"] = f"flood_wait ({wait_display})"
                                await asyncio.sleep(wait_time + random.randint(5, 15))
                            
                            self.campaign_progress[campaign_id]["status"] = "running"
                            
                            # Rotate to next account
                            account_index += 1
                            
                        else:
                            results["failed"] += 1
                            db.log_broadcast(
                                campaign_id=campaign_id,
                                account_id=account['id'],
                                client_id=campaign['client_id'],
                                group_name=res.group[:100],
                                status='failed',
                                error_message=res.error
                            )
                            failure_streak += 1
                            success_streak = 0
                        
                        # Add to recent logs (keep last 30 for forums)
                        log_entry = {
                            "group": res.group[:40],
                            "status": res.status,
                            "error": res.error[:30] if res.error else None,
                            "index": i + 1,
                            "cycle": cycle_count
                        }
                        self.campaign_progress[campaign_id]["recent_logs"].append(log_entry)
                        if len(self.campaign_progress[campaign_id]["recent_logs"]) > 30:
                            self.campaign_progress[campaign_id]["recent_logs"].pop(0)
                    
                    # Update live progress after processing all results
                    self.campaign_progress[campaign_id]["sent"] = results["sent"]
                    self.campaign_progress[campaign_id]["failed"] = results["failed"]
                    
                    # Progress callback
                    if on_progress:
                        on_progress(i + 1, total, result_list[-1].status if result_list else 'unknown')
                    
                    # =============================================
                    # SMART DELAY CALCULATION
                    # =============================================
                    
                    if result.status == 'sent':
                        success_streak += 1
                        failure_streak = 0
                        batch_count += 1
                        messages_this_hour += 1
                        
                        # SUCCESS: Gradually decrease delay (reward good behavior)
                        if success_streak >= 5:
                            current_delay = max(MIN_DELAY, current_delay * 0.95)  # 5% faster
                        
                        # Reset account failure count
                        account_failures[account['id']] = 0
                        
                    elif result.status == 'flood_wait':
                        success_streak = 0
                        failure_streak += 1
                        
                        # FLOOD: Exponential backoff
                        current_delay = min(MAX_DELAY, current_delay * 2.0)
                        
                        # Track account issues
                        account_failures[account['id']] = account_failures.get(account['id'], 0) + 1
                        
                        # Rotate account if too many failures
                        if account_failures[account['id']] >= MAX_FAILURES_BEFORE_ROTATE:
                            account_index += 1
                            
                    else:  # Failed
                        success_streak = 0
                        failure_streak += 1
                        
                        # FAILED: Increase delay slightly
                        current_delay = min(MAX_DELAY, current_delay * 1.25)
                        
                        # Track failures
                        account_failures[account['id']] = account_failures.get(account['id'], 0) + 1
                    
                    # Check hourly limit - rotate account every ~50 messages
                    if messages_this_hour >= 50:
                        # Check if hour has passed
                        if (datetime.now() - hour_start).seconds < 3600:
                            # Still within the hour, rotate account
                            account_index += 1
                            messages_this_hour = 0
                        else:
                            # New hour started
                            hour_start = datetime.now()
                            messages_this_hour = 0
                    
                    # Update progress with current delay
                    self.campaign_progress[campaign_id]["delay"] = round(current_delay, 1)
                    
                    # Apply delay (only if not stopping and more groups)
                    if not self.stop_flags.get(campaign_id, False) and i < total - 1:
                        # Check if batch rest needed
                        if batch_count >= BATCH_SIZE:
                            batch_count = 0
                            BATCH_SIZE = random.randint(8, 12)  # Randomize for next batch
                            rest_time = random.randint(BATCH_REST_MIN, BATCH_REST_MAX)
                            self.campaign_progress[campaign_id]["status"] = f"batch_rest_{rest_time}s"
                            await asyncio.sleep(rest_time)
                            self.campaign_progress[campaign_id]["status"] = "running"
                        else:
                            # Apply jitter to delay (±30%)
                            jitter = current_delay * JITTER_PERCENT
                            actual_delay = current_delay + random.uniform(-jitter, jitter)
                            actual_delay = max(MIN_DELAY, actual_delay)  # Never below minimum
                            await asyncio.sleep(actual_delay)
                        
                except Exception as e:
                    results["failed"] += 1
                    failure_streak += 1
                    current_delay = min(MAX_DELAY, current_delay * 1.5)
                    results["details"].append({
                        "group": group_name if 'group_name' in dir() else str(group),
                        "status": "failed",
                        "error": str(e)[:80]
                    })
            
            # Cycle completed - check if should continue
            if self.stop_flags.get(campaign_id, False):
                break
            
            # Update analytics after each cycle
            db.update_analytics(
                client_id=campaign['client_id'],
                broadcasts=results["sent"] + results["failed"],
                success=results["sent"],
                failed=results["failed"]
            )
            
            # Cycle pause with randomized duration (10-15 minutes)
            CYCLE_PAUSE = random.randint(600, 900)
            self.campaign_progress[campaign_id]["status"] = "cycle_pause"
            self.campaign_progress[campaign_id]["current_group"] = f"Cycle {cycle_count} done. Next in {CYCLE_PAUSE//60}m..."
            
            # Wait in chunks so we can check stop flag
            for _ in range(CYCLE_PAUSE // 10):
                if self.stop_flags.get(campaign_id, False):
                    break
                await asyncio.sleep(10)
            
            # Reset delay for new cycle
            current_delay = BASE_DELAY
            success_streak = 0
            
            if not self.stop_flags.get(campaign_id, False):
                self.campaign_progress[campaign_id]["status"] = "running"
        
        # Campaign stopped
        db.update_campaign_status(campaign_id, "stopped")
        
        if campaign_id in self.campaign_progress:
            self.campaign_progress[campaign_id]["status"] = "stopped"
        
        # Cleanup
        if campaign_id in self.stop_flags:
            del self.stop_flags[campaign_id]
        
        return results
    
    def stop_campaign(self, campaign_id: int):
        """Signal a running campaign to stop."""
        self.stop_flags[campaign_id] = True
    
    async def start_campaign_async(self, campaign_id: int, parallel: bool = True) -> asyncio.Task:
        """
        Start a campaign as a background task.
        
        Args:
            campaign_id: ID of the campaign to run
            parallel: If True (default), run all accounts simultaneously.
                     If False, use sequential rotation mode.
        """
        if parallel:
            task = asyncio.create_task(self.run_campaign_parallel(campaign_id))
        else:
            task = asyncio.create_task(self.run_campaign(campaign_id))
        self.running_campaigns[campaign_id] = task
        return task
    
    def is_campaign_running(self, campaign_id: int) -> bool:
        """Check if a campaign is currently running."""
        task = self.running_campaigns.get(campaign_id)
        return task is not None and not task.done()


# Global broadcaster instance
broadcaster = None

def get_broadcaster(db):
    """Get or create broadcaster instance."""
    global broadcaster
    if broadcaster is None:
        broadcaster = Broadcaster(db)
    return broadcaster
