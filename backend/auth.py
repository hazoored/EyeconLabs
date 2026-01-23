"""
EyeconBumps Web App - Authentication
Admin password + Client token authentication with JWT
"""
from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel

from config import settings
from database import db

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# HTTP Bearer for JWT
security = HTTPBearer()

# ============ MODELS ============

class AdminLogin(BaseModel):
    username: str
    password: str

class ClientLogin(BaseModel):
    token: str  # 5-digit access token

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_type: str  # "admin" or "client"
    expires_in: int  # seconds

# ============ PASSWORD UTILS ============

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

# ============ JWT UTILS ============

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

def decode_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except JWTError:
        return None

# ============ ADMIN AUTH ============

def authenticate_admin(username: str, password: str) -> Optional[dict]:
    """Authenticate admin with username/password."""
    # For simplicity, using config-based admin credentials
    # In production, you might want to store hashed password in DB
    if username == settings.ADMIN_USERNAME and password == settings.ADMIN_PASSWORD:
        return {"type": "admin", "username": username}
    return None

def admin_login(credentials: AdminLogin) -> TokenResponse:
    """Admin login endpoint logic."""
    admin = authenticate_admin(credentials.username, credentials.password)
    if not admin:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )
    
    expires_delta = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": credentials.username, "type": "admin"},
        expires_delta=expires_delta
    )
    
    return TokenResponse(
        access_token=access_token,
        user_type="admin",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )

# ============ CLIENT AUTH ============

def client_login(credentials: ClientLogin) -> TokenResponse:
    """Client login with 5-digit token."""
    client = db.get_client_by_token(credentials.token.upper())
    
    if not client:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid access token"
        )
    
    # Check if subscription expired
    if client.get('expires_at'):
        expires_at = datetime.fromisoformat(client['expires_at']) if isinstance(client['expires_at'], str) else client['expires_at']
        if expires_at < datetime.now():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Subscription expired. Contact admin to renew."
            )
    
    expires_delta = timedelta(days=settings.CLIENT_TOKEN_EXPIRE_DAYS)
    access_token = create_access_token(
        data={
            "sub": str(client['id']),
            "type": "client",
            "client_id": client['id'],
            "name": client['name']
        },
        expires_delta=expires_delta
    )
    
    return TokenResponse(
        access_token=access_token,
        user_type="client",
        expires_in=settings.CLIENT_TOKEN_EXPIRE_DAYS * 24 * 60 * 60
    )

# ============ AUTH DEPENDENCIES ============

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    """Verify JWT token and return user info."""
    token = credentials.credentials
    payload = decode_token(token)
    
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token"
        )
    
    return payload

async def require_admin(current_user: dict = Depends(get_current_user)) -> dict:
    """Require admin role."""
    if current_user.get("type") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return current_user

async def require_client(current_user: dict = Depends(get_current_user)) -> dict:
    """Require client role."""
    if current_user.get("type") != "client":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Client access required"
        )
    
    # Verify client still exists and is active
    client_id = current_user.get("client_id")
    client = db.get_client_by_id(client_id)
    
    if not client or not client.get('is_active'):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account deactivated"
        )
    
    current_user['client'] = client
    return current_user

async def get_current_admin_or_client(current_user: dict = Depends(get_current_user)) -> dict:
    """Allow either admin or client."""
    if current_user.get("type") == "client":
        client_id = current_user.get("client_id")
        client = db.get_client_by_id(client_id)
        if client:
            current_user['client'] = client
    return current_user
