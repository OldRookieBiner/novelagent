"""Projects API routes"""
from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def list_projects():
    """List projects - to be implemented"""
    pass


@router.post("/")
async def create_project():
    """Create project - to be implemented"""
    pass


@router.get("/{project_id}")
async def get_project(project_id: int):
    """Get project - to be implemented"""
    pass


@router.put("/{project_id}")
async def update_project(project_id: int):
    """Update project - to be implemented"""
    pass


@router.delete("/{project_id}")
async def delete_project(project_id: int):
    """Delete project - to be implemented"""
    pass