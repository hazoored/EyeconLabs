"""
EyeconBumps Web App - Configuration
"""
import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    model_config = {"extra": "ignore"}

    # App settings
    APP_NAME: str = "EyeconBumps Web App"
    DEBUG: bool = False
    
    # Security
    SECRET_KEY: str = os.getenv("SECRET_KEY", "eyeconbumps-super-secret-key-change-in-production")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours for admin
    CLIENT_TOKEN_EXPIRE_DAYS: int = 7  # 7 days for clients
    
    # Admin credentials (change in production)
    ADMIN_USERNAME: str = os.getenv("ADMIN_USERNAME", "admin")
    ADMIN_PASSWORD: str = os.getenv("ADMIN_PASSWORD", "atmkb69")
    
    # Database
    DATABASE_PATH: str = os.getenv("DATABASE_PATH", "eyeconbumps_webapp.db")
    
    # CORS
    CORS_ORIGINS: list = [
        "http://localhost:3000", 
        "http://127.0.0.1:3000",
        "https://app.eyeconlabs.com",
        "https://eyeconlabs.com",
        "https://www.eyeconlabs.com"
    ]

settings = Settings()
