"""
EyeconBumps Web App - Main FastAPI Application
Run with: uvicorn main:app --host 0.0.0.0 --port 8000
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from config import settings
from auth import admin_login, client_login, AdminLogin, ClientLogin, TokenResponse
from routers import admin, clients
from routers import session as session_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    print(f"🚀 {settings.APP_NAME} starting...")
    print(f"📊 Database: {settings.DATABASE_PATH}")
    print(f"🔒 Debug mode: {settings.DEBUG}")
    

    from broadcaster import get_broadcaster
    from database import db
    try:
        b = get_broadcaster(db)
        # Run in background without blocking startup
        print('[API] Startup: Started campaign resume task')
    except Exception as e:
        print(f'[API] Startup Error: {e}')
    # Auto-resume campaigns
    try:
        import asyncio
        from broadcaster import get_broadcaster
        from database import db
        b = get_broadcaster(db)
        asyncio.create_task(b.resume_campaigns())
        print('[API] Startup: Resumed campaigns')
    except Exception as e:
        print(f'[API] Startup Error: {e}')
    
    yield
    
    print(f"👋 {settings.APP_NAME} shutting down...")

app = FastAPI(
    title=settings.APP_NAME,
    description="Admin dashboard and client portal for EyeconBumps Telegram Ad Agency",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============ AUTH ENDPOINTS ============

@app.post("/api/auth/admin/login", response_model=TokenResponse, tags=["Auth"])
async def login_admin(credentials: AdminLogin):
    """Admin login with username and password."""
    return admin_login(credentials)

@app.post("/api/auth/client/login", response_model=TokenResponse, tags=["Auth"])
async def login_client(credentials: ClientLogin):
    """Client login with 5-digit access token."""
    return client_login(credentials)

# ============ ROUTERS ============

app.include_router(admin.router, prefix="/api")
app.include_router(clients.router, prefix="/api")
app.include_router(session_router.router, prefix="/api")

# ============ HEALTH CHECK ============

@app.get("/api/health", tags=["Health"])
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "app": settings.APP_NAME}

@app.get("/", tags=["Root"])
async def root():
    """Root endpoint."""
    return {
        "app": settings.APP_NAME,
        "docs": "/docs",
        "health": "/api/health"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
