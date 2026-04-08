"""Settings API routes"""
from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def get_settings():
    """Get settings - to be implemented"""
    pass


@router.put("/")
async def update_settings():
    """Update settings - to be implemented"""
    pass