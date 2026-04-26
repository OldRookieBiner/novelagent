"""FastAPI application entry point"""

import time
from collections import defaultdict
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import settings
from app.database import engine, Base
from app.api import auth, projects, outline, chapters, settings as settings_api, model_configs, workflow
from app.api.system_prompts import router as system_prompts_router
from app.utils.logger import setup_logging, get_logger
from app.utils.exceptions import (
    APIError,
    api_error_handler,
    http_exception_handler,
    validation_exception_handler,
    general_exception_handler
)
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

# 初始化日志系统
setup_logging(settings.log_level)
logger = get_logger(__name__)


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
            logger.warning(f"Rate limit exceeded for IP: {client_ip}")
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={"detail": "Too many login attempts. Please try again later."}
            )

        # Record request
        self.requests[client_ip].append(current_time)

        return await call_next(request)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    logger.info("Starting NovelAgent API...")

    # Startup: Create tables if they don't exist
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables initialized")

    # Create default user if not exists
    from app.utils.auth import create_default_user
    create_default_user()
    logger.info("Default user initialized")

    yield

    # Shutdown
    logger.info("Shutting down NovelAgent API...")


app = FastAPI(
    title="NovelAgent API",
    description="AI Novel Creation Assistant API",
    version="0.7.0",
    lifespan=lifespan
)

# 注册异常处理器
app.add_exception_handler(APIError, api_error_handler)
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, general_exception_handler)

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
app.include_router(model_configs.router, prefix="/api/model_configs", tags=["model-configs"])
app.include_router(workflow.router, prefix="/api/projects", tags=["workflow"])
app.include_router(system_prompts_router, prefix="/api/system/prompts", tags=["system-prompts"])


@app.get("/")
async def root():
    """Root endpoint"""
    return {"message": "NovelAgent API", "version": "0.7.0"}


@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "healthy"}