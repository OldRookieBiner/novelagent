"""FastAPI application entry point"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import engine, Base
from app.api import auth, projects, outline, chapters, settings as settings_api


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

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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