"""FastAPI application entry point"""

import time
from collections import defaultdict
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import settings
from app.database import engine, Base
from app.api import auth, projects, outline, chapters, settings as settings_api


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Simple IP-based rate limiting for authentication endpoints"""

    def __init__(self, app, requests_limit: int = 5, window_seconds: int = 60):
        super().__init__(app)
        self.requests_limit = requests_limit
        self.window_seconds = window_seconds
        self.requests = defaultdict(list)

    async def dispatch(self, request: Request, call_next):
        # Only rate limit auth endpoints
        if not request.url.path.startswith("/api/auth/login"):
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        current_time = time.time()

        # Clean old requests
        self.requests[client_ip] = [
            t for t in self.requests[client_ip]
            if current_time - t < self.window_seconds
        ]

        # Check limit
        if len(self.requests[client_ip]) >= self.requests_limit:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many login attempts. Please try again later."
            )

        # Record request
        self.requests[client_ip].append(current_time)

        return await call_next(request)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    # Startup: Create tables if they don't exist
    Base.metadata.create_all(bind=engine)

    # Create default user if not exists
    from app.utils.auth import create_default_user
    create_default_user()

    yield

    # Shutdown
    pass


app = FastAPI(
    title="NovelAgent API",
    description="AI Novel Creation Assistant API",
    version="0.2.0",
    lifespan=lifespan
)

# Rate limiting middleware
app.add_middleware(
    RateLimitMiddleware,
    requests_limit=settings.auth_rate_limit_requests,
    window_seconds=settings.auth_rate_limit_seconds
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)

# Include routers
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(projects.router, prefix="/api/projects", tags=["projects"])
app.include_router(outline.router, prefix="/api/projects", tags=["outline"])
app.include_router(chapters.router, prefix="/api/projects", tags=["chapters"])
app.include_router(settings_api.router, prefix="/api/settings", tags=["settings"])


@app.get("/")
async def root():
    """Root endpoint"""
    return {"message": "NovelAgent API", "version": "0.2.0"}


@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "healthy"}