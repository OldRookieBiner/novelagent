"""Outline API routes"""
from fastapi import APIRouter

router = APIRouter()


@router.get("/{project_id}/outline")
async def get_outline(project_id: int):
    """Get outline - to be implemented"""
    pass


@router.post("/{project_id}/outline")
async def create_outline(project_id: int):
    """Create outline - to be implemented"""
    pass


@router.put("/{project_id}/outline")
async def update_outline(project_id: int):
    """Update outline - to be implemented"""
    pass


@router.post("/{project_id}/outline/confirm")
async def confirm_outline(project_id: int):
    """Confirm outline - to be implemented"""
    pass