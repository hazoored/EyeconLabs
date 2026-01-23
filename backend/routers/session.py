"""
EyeconBumps Web App - Session Generator Router
Generate Telethon session strings via web UI
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import (
    PhoneNumberInvalidError,
    PhoneCodeInvalidError,
    PhoneCodeExpiredError,
    SessionPasswordNeededError
)
import asyncio
from typing import Optional
import os

router = APIRouter(prefix="/session", tags=["Session Generator"])

# Temporary storage for pending sessions (in production, use Redis)
pending_sessions = {}

# Get API credentials from environment or use the ones from 4main/config.py
API_ID = int(os.getenv("TELEGRAM_API_ID", "21219293"))
API_HASH = os.getenv("TELEGRAM_API_HASH", "cff5d321b676104840cf282a742381e0")

class SendCodeRequest(BaseModel):
    phone_number: str

class VerifyCodeRequest(BaseModel):
    phone_number: str
    code: str
    password: Optional[str] = None  # For 2FA

class SessionResponse(BaseModel):
    success: bool
    message: str
    session_string: Optional[str] = None
    requires_2fa: Optional[bool] = False

@router.post("/send-code", response_model=SessionResponse)
async def send_code(data: SendCodeRequest):
    """Send verification code to phone number."""
    phone = data.phone_number.strip()
    
    if not phone.startswith("+"):
        phone = "+" + phone
    
    try:
        # Create a new client with empty session
        client = TelegramClient(StringSession(), API_ID, API_HASH)
        await client.connect()
        
        # Send the code
        sent_code = await client.send_code_request(phone)
        
        # Store the client for verification step
        pending_sessions[phone] = {
            "client": client,
            "phone_code_hash": sent_code.phone_code_hash
        }
        
        return SessionResponse(
            success=True,
            message=f"Code sent to {phone}. Check your Telegram app."
        )
        
    except PhoneNumberInvalidError:
        return SessionResponse(
            success=False,
            message="Invalid phone number format. Use international format like +1234567890"
        )
    except Exception as e:
        return SessionResponse(
            success=False,
            message=f"Error: {str(e)}"
        )

@router.post("/verify-code", response_model=SessionResponse)
async def verify_code(data: VerifyCodeRequest):
    """Verify code and get session string."""
    phone = data.phone_number.strip()
    if not phone.startswith("+"):
        phone = "+" + phone
    
    if phone not in pending_sessions:
        return SessionResponse(
            success=False,
            message="No pending verification. Send code first."
        )
    
    session_data = pending_sessions[phone]
    client = session_data["client"]
    phone_code_hash = session_data["phone_code_hash"]
    
    try:
        # Try to sign in with the code
        await client.sign_in(
            phone=phone,
            code=data.code,
            phone_code_hash=phone_code_hash
        )
        
        # Success! Get the session string
        session_string = client.session.save()
        
        # Clean up
        del pending_sessions[phone]
        await client.disconnect()
        
        return SessionResponse(
            success=True,
            message="Session generated successfully!",
            session_string=session_string
        )
        
    except SessionPasswordNeededError:
        # 2FA is enabled
        if data.password:
            try:
                await client.sign_in(password=data.password)
                session_string = client.session.save()
                
                del pending_sessions[phone]
                await client.disconnect()
                
                return SessionResponse(
                    success=True,
                    message="Session generated successfully!",
                    session_string=session_string
                )
            except Exception as e:
                return SessionResponse(
                    success=False,
                    message=f"2FA password incorrect: {str(e)}"
                )
        else:
            return SessionResponse(
                success=False,
                message="This account has 2FA enabled. Please provide your password.",
                requires_2fa=True
            )
            
    except PhoneCodeInvalidError:
        return SessionResponse(
            success=False,
            message="Invalid code. Please try again."
        )
        
    except PhoneCodeExpiredError:
        del pending_sessions[phone]
        return SessionResponse(
            success=False,
            message="Code expired. Please request a new one."
        )
        
    except Exception as e:
        return SessionResponse(
            success=False,
            message=f"Error: {str(e)}"
        )

@router.post("/cancel")
async def cancel_session(data: SendCodeRequest):
    """Cancel pending session generation."""
    phone = data.phone_number.strip()
    if not phone.startswith("+"):
        phone = "+" + phone
    
    if phone in pending_sessions:
        client = pending_sessions[phone]["client"]
        await client.disconnect()
        del pending_sessions[phone]
    
    return {"success": True, "message": "Cancelled"}


class CheckAccountRequest(BaseModel):
    session_string: str

class AccountInfoResponse(BaseModel):
    success: bool
    message: str
    is_premium: Optional[bool] = None
    phone_number: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    username: Optional[str] = None

@router.post("/check-account", response_model=AccountInfoResponse)
async def check_account(data: CheckAccountRequest):
    """Check account info from session string (including premium status)."""
    try:
        client = TelegramClient(StringSession(data.session_string), API_ID, API_HASH)
        await client.connect()
        
        if not await client.is_user_authorized():
            await client.disconnect()
            return AccountInfoResponse(
                success=False,
                message="Session is invalid or expired"
            )
        
        # Get the user's own info
        me = await client.get_me()
        
        await client.disconnect()
        
        return AccountInfoResponse(
            success=True,
            message="Account info retrieved",
            is_premium=bool(getattr(me, 'premium', False)),
            phone_number=me.phone,
            first_name=me.first_name,
            last_name=me.last_name,
            username=me.username
        )
        
    except Exception as e:
        return AccountInfoResponse(
            success=False,
            message=f"Error: {str(e)}"
        )
