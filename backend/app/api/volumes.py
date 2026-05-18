"""卷/弧 API 路由"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app.utils.auth import get_current_user
from app.utils.project import get_project_for_user
from app.models.user import User
from app.models.volume import Volume
from app.models.arc import Arc
from app.schemas.volume import ArcResponse, ArcUpdate, VolumeResponse

router = APIRouter()


@router.get("/{project_id}/volumes", response_model=List[VolumeResponse])
async def list_volumes(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取项目的卷/弧结构"""
    get_project_for_user(project_id, current_user.id, db)

    volumes = db.query(Volume).filter(
        Volume.project_id == project_id
    ).order_by(Volume.volume_number).all()

    return [
        VolumeResponse(
            id=v.id,
            project_id=v.project_id,
            volume_number=v.volume_number,
            title=v.title,
            summary=v.summary,
            arcs=[
                ArcResponse(
                    id=a.id,
                    volume_id=a.volume_id,
                    arc_number=a.arc_number,
                    title=a.title,
                    summary=a.summary,
                    outline=a.outline,
                    outline_confirmed=a.outline_confirmed,
                    chapter_count=a.chapter_count,
                )
                for a in sorted(v.arcs, key=lambda x: x.arc_number)
            ],
        )
        for v in volumes
    ]


@router.put("/{project_id}/arcs/{arc_id}", response_model=ArcResponse)
async def update_arc(
    project_id: int,
    arc_id: int,
    request: ArcUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """更新弧信息（含弧纲编辑）"""
    get_project_for_user(project_id, current_user.id, db)

    arc = db.query(Arc).filter(Arc.id == arc_id).first()
    if not arc:
        raise HTTPException(status_code=404, detail="Arc not found")

    # 验证弧属于该项目
    volume = db.query(Volume).filter(
        Volume.id == arc.volume_id,
        Volume.project_id == project_id,
    ).first()
    if not volume:
        raise HTTPException(status_code=404, detail="Arc not found in project")

    if request.title is not None:
        arc.title = request.title
    if request.summary is not None:
        arc.summary = request.summary
    if request.outline is not None:
        arc.outline = request.outline
    if request.outline_confirmed is not None:
        arc.outline_confirmed = request.outline_confirmed
    if request.chapter_count is not None:
        arc.chapter_count = request.chapter_count

    db.commit()

    return ArcResponse(
        id=arc.id,
        volume_id=arc.volume_id,
        arc_number=arc.arc_number,
        title=arc.title,
        summary=arc.summary,
        outline=arc.outline,
        outline_confirmed=arc.outline_confirmed,
        chapter_count=arc.chapter_count,
    )


@router.put("/{project_id}/arcs/{arc_id}/confirm-outline", response_model=ArcResponse)
async def confirm_arc_outline(
    project_id: int,
    arc_id: int,
    request: ArcUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """确认弧纲（可同时编辑弧纲内容）"""
    get_project_for_user(project_id, current_user.id, db)

    arc = db.query(Arc).filter(Arc.id == arc_id).first()
    if not arc:
        raise HTTPException(status_code=404, detail="Arc not found")

    # 验证弧属于该项目
    volume = db.query(Volume).filter(
        Volume.id == arc.volume_id,
        Volume.project_id == project_id,
    ).first()
    if not volume:
        raise HTTPException(status_code=404, detail="Arc not found in project")

    # 更新弧纲内容（如有修改）
    if request.outline is not None:
        arc.outline = request.outline
    # 确认弧纲
    arc.outline_confirmed = True
    db.commit()

    return ArcResponse(
        id=arc.id,
        volume_id=arc.volume_id,
        arc_number=arc.arc_number,
        title=arc.title,
        summary=arc.summary,
        outline=arc.outline,
        outline_confirmed=arc.outline_confirmed,
        chapter_count=arc.chapter_count,
    )
