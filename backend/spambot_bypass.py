import asyncio
import re
from telethon import TelegramClient

class SpamBotBypass:
    def __init__(self, client: TelegramClient):
        self.client = client
        self.bot_username = 'SpamBot'
        
    async def run_bypass(self):
        """
        Executes the full SpamBot appeal flow.
        Returns: strict tuple (status: str, message: str, unban_at: int or None)
        status: 'success', 'failed', 'not_limited', 'error'
        """
        import datetime
        unban_at = None
        
        try:
            print(f"[SPAMBOT] Starting bypass check...")
            
            # Step 1: Start the bot
            async with self.client.conversation(self.bot_username, timeout=20) as conv:
                await conv.send_message('/start')
                response = await conv.get_response()
                text = response.text
                
                print(f"[SPAMBOT] Initial response: {text[:50]}...")
                
                # Try to extract unban date if present
                # Format: "until 20 Feb 2026, 23:48 UTC"
                date_match = re.search(r'until (\d+ \w+ \d+, \d+:\d+ UTC)', text)
                if date_match:
                    date_str = date_match.group(1)
                    try:
                        # Attempt to parse date
                        dt = datetime.datetime.strptime(date_str, "%d %b %Y, %H:%M UTC")
                        # Add UTC timezone info
                        dt = dt.replace(tzinfo=datetime.timezone.utc)
                        unban_at = int(dt.timestamp())
                        print(f"[SPAMBOT] Extracted unban timestamp: {unban_at} ({date_str})")
                    except Exception as e:
                        print(f"[SPAMBOT] Date parsing failed: {e}")

                if "good news" in text.lower() or "no limits" in text.lower() or "not limited" in text.lower():
                    print("[SPAMBOT] Account is NOT limited.")
                    return "not_limited", "Account is free of limitations.", None
                
                print("[SPAMBOT] Account appears limited (or response unclear). Starting appeal...")
                
                # Step 2: "OK, go ahead."
                await asyncio.sleep(2)
                await conv.send_message("OK, go ahead.")
                try:
                    response = await conv.get_response()
                except:
                    pass
                
                # Step 3: "No, I’ll never do any of this!"
                await asyncio.sleep(2)
                await conv.send_message("No, I’ll never do any of this!")
                try:
                    response = await conv.get_response()
                except:
                    pass

                # Step 4: Final Appeal Paragraph
                appeal_text = (
                    "I was forwarding a message to my friend and it said \"Your account is banned from participating in groups\" "
                    "Please help me I have never done unsolicited advertising of any kind nor Promotional messages "
                    "kindly remove the limit asap or I will face serious financial consequences."
                )
                await asyncio.sleep(2)
                await conv.send_message(appeal_text)
                
                response = await conv.get_response()
                final_text = response.text
                
                print(f"[SPAMBOT] Final response: {final_text[:50]}...")
                
                if "supervisor" in final_text.lower() or "submitted" in final_text.lower():
                    return "success", "Appeal submitted successfully.", unban_at
                else:
                    return "failed", f"Appeal response unclear: {final_text[:50]}...", unban_at
                    
        except asyncio.TimeoutError:
            print("[SPAMBOT] Timeout waiting for bot response.")
            return "error", "SpamBot timed out.", None
        except Exception as e:
            print(f"[SPAMBOT] Error: {e}")
            return "error", f"SpamBot error: {e}", None
