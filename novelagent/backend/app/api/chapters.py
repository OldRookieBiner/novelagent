"""Chapters API routes"""
from fastapi import APIRouter

router = APIRouter()


@router.get("/{project_id}/chapter-outlines")
async def list_chapter_outlines(project_id: int):
    """List chapter outlines - to be implemented"""
    pass


@router.post("/{project_id}/chapter-outlines")
async def create_chapter_outlines(project_id: int):
    """Create chapter outlines - to be implemented"""
    pass


@router.get("/{project_id}/chapters/{chapter_num}")
async def get_chapter(project_id: int, chapter_num: int):
    """Get chapter - to be implemented"""
    pass


@router.post("/{project_id}/chapters/{chapter_num}")
async def create_chapter(project_id: int, chapter_num: int):
    """Create chapter - to be implemented"""
    pass


@router.put("/{project_id}/chapters/{chapter_num}")
async def update_chapter(project_id: int, chapter_num: int):
    """Update chapter - to be implemented"""
    pass


@router.post("/{project_id}/chapters/{chapter_num}/review")
async def review_chapter(project_id: int, chapter_num: int):
    """Review chapter - to be implemented"""
    pass