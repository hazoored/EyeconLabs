import asyncio
import time
import httpx
from datetime import datetime
from typing import Optional, List, Dict, Any

class LogService:
    """
    Service for sending real-time broadcast logs to Telegram bots.
    Matches the exact format requested by the user.
    """
    BOT_API_URL = "https://api.telegram.org/bot{token}/sendMessage"
    
    def __init__(self):
        self.client = httpx.AsyncClient(timeout=10.0)
        self._error_log_times = {} # Rate-limit error logging

    async def send_log(self, bot_token: str, target_id: str, 
                       group_name: str, account_username: str, 
                       campaign_name: str, message_link: str = None):
        """
        Send a formatted log message to the target Telegram ID.
        """
        timestamp = datetime.now().strftime("%I:%M %p")
        
        # ✅ Successfully forwarded to: [Group Name]
        # Ad account: [Account Username]
        #
        # Ad Campaign: [Campaign Name]... [Timestamp]
        
        text = (
            f"✅ <b>Successfully forwarded to:</b> {group_name}\n"
            f"<b>Ad account:</b> {account_username}\n\n"
            f"<i>Ad Campaign: {campaign_name}...</i> <code>{timestamp}</code>"
        )
        
        payload = {
            "chat_id": target_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True
        }
        
        # Add "View Message" button if link provided
        if message_link:
            payload["reply_markup"] = {
                "inline_keyboard": [[
                    {"text": "View Message ↗️", "url": message_link}
                ]]
            }
        
        try:
            url = self.BOT_API_URL.format(token=bot_token)
            response = await self.client.post(url, json=payload)
            
            if response.status_code == 429:
                # Too Many Requests
                retry_after = response.json().get("parameters", {}).get("retry_after", 1)
                print(f"[LOG_SERVICE] Rate limited (429). Retry after {retry_after}s. Skipping this log.")
                return False
                
            if response.status_code != 200:
                # Rate-limit error logging: only print once per 60s per target_id
                now = time.time()
                last_log = self._error_log_times.get(target_id, 0)
                if now - last_log > 60:
                    print(f"[LOG_SERVICE] Failed to send log to {target_id}: {response.text}")
                    self._error_log_times[target_id] = now
            return response.status_code == 200
        except Exception as e:
            print(f"[LOG_SERVICE] Error sending log: {e}")
            return False

    async def send_raw_message(self, bot_token: str, target_id: int, message: str):
        """
        Send a raw text message to a Telegram user/chat.
        Used for alerts like frozen account notifications.
        """
        payload = {
            "chat_id": target_id,
            "text": message,
            "parse_mode": "Markdown",
            "disable_web_page_preview": True
        }
        
        try:
            url = self.BOT_API_URL.format(token=bot_token)
            response = await self.client.post(url, json=payload)
            
            if response.status_code != 200:
                print(f"[LOG_SERVICE] Failed to send raw message: {response.text}")
            return response.status_code == 200
        except Exception as e:
            print(f"[LOG_SERVICE] Error sending raw message: {e}")
            return False

    async def close(self):
        await self.client.aclose()

# Global log service instance
log_service = LogService()
