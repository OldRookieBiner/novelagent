"""知识库 API 路由"""

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db
from app.models.user import User
from app.utils.auth import get_current_user
from app.utils.project import get_project_for_user
from app.agents.services.knowledge_base import KnowledgeBaseService
from app.schemas.knowledge import (
    WorldSettingResponse,
    WorldSettingUpdate,
    StyleConstraintsResponse,
    StyleConstraintsUpdate,
    PlotBlockResponse,
    ForeshadowingResponse,
    TimelineEntryResponse,
    StyleSnapshotResponse,
)

router = APIRouter()


def _get_kb(project_id: int) -> KnowledgeBaseService:
    return KnowledgeBaseService(project_id)


# ========== 世界观 ==========

@router.get("/projects/{project_id}/world-setting", response_model=WorldSettingResponse)
def get_world_setting(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = get_project_for_user(project_id, current_user.id, db)
    kb = _get_kb(project.id)
    setting = kb.get_world_setting()
    if not setting:
        raise HTTPException(status_code=404, detail="World setting not found")
    return setting


@router.put("/projects/{project_id}/world-setting", response_model=WorldSettingResponse)
def update_world_setting(
    project_id: int,
    data: WorldSettingUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = get_project_for_user(project_id, current_user.id, db)
    kb = _get_kb(project.id)
    setting = kb.get_world_setting()
    if not setting:
        raise HTTPException(status_code=404, detail="World setting not found")
    updated = kb.update_world_setting(setting.id, data.model_dump(exclude_none=True))
    return updated


# ========== 风格约束 ==========

@router.get("/projects/{project_id}/style-constraints", response_model=StyleConstraintsResponse)
def get_style_constraints(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = get_project_for_user(project_id, current_user.id, db)
    kb = _get_kb(project.id)
    constraints = kb.get_style_constraints()
    if not constraints:
        raise HTTPException(status_code=404, detail="Style constraints not found")
    return constraints


@router.put("/projects/{project_id}/style-constraints", response_model=StyleConstraintsResponse)
def update_style_constraints(
    project_id: int,
    data: StyleConstraintsUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = get_project_for_user(project_id, current_user.id, db)
    kb = _get_kb(project.id)
    # 风格约束不存在则创建
    constraints = kb.get_style_constraints()
    if constraints:
        updated = kb.update_style_constraints(constraints.id, data.model_dump(exclude_none=True))
    else:
        updated = kb.create_style_constraints(data.model_dump(exclude_none=True))
    return updated


# ========== 情节块 ==========

@router.get("/projects/{project_id}/plot-blocks", response_model=list[PlotBlockResponse])
def get_plot_blocks(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = get_project_for_user(project_id, current_user.id, db)
    kb = _get_kb(project.id)
    return kb.get_plot_blocks()


# ========== 伏笔 ==========

@router.get("/projects/{project_id}/foreshadowings", response_model=list[ForeshadowingResponse])
def get_foreshadowings(
    project_id: int,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = get_project_for_user(project_id, current_user.id, db)
    kb = _get_kb(project.id)
    return kb.get_foreshadowings(status=status)


# ========== 时间线 ==========

@router.get("/projects/{project_id}/timeline", response_model=list[TimelineEntryResponse])
def get_timeline(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = get_project_for_user(project_id, current_user.id, db)
    kb = _get_kb(project.id)
    return kb.get_timeline()


# ========== 风格统计 ==========

@router.get("/projects/{project_id}/style-snapshots", response_model=list[StyleSnapshotResponse])
def get_style_snapshots(
    project_id: int,
    last_n: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = get_project_for_user(project_id, current_user.id, db)
    kb = _get_kb(project.id)
    return kb.get_style_snapshots(last_n=last_n)
