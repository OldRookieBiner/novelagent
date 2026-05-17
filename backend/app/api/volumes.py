"""Volume and Arc API routes"""

from typing import List
from fastapi import APIRouter, HTTPException, status, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.models.volume import Volume
from app.models.arc import Arc
from app.schemas.volume import (
    VolumeResponse,
    VolumeUpdate,
    ArcResponse,
    ArcUpdate,
    VolumeWithArcsResponse,
)
from app.utils.auth import get_current_user
from app.utils.project import get_project_for_user

router = APIRouter()


@router.get("/{project_id}/volumes", response_model=List[VolumeWithArcsResponse])
async def list_volumes(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取项目的卷列表（含弧）"""
    get_project_for_user(project_id, current_user.id, db)

    volumes = db.query(Volume).filter(
        Volume.project_id == project_id
    ).order_by(Volume.volume_number).all()

    result = []
    for v in volumes:
        arcs = db.query(Arc).filter(
            Arc.volume_id == v.id
        ).order_by(Arc.arc_number).all()

        result.append(VolumeWithArcsResponse(
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
                    chapter_count=a.chapter_count,
                )
                for a in arcs
            ],
        ))

    return result


@router.put("/{project_id}/volumes/{volume_id}", response_model=VolumeResponse)
async def update_volume(
    project_id: int,
    volume_id: int,
    request: VolumeUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """编辑卷名/概要"""
    get_project_for_user(project_id, current_user.id, db)

    volume = db.query(Volume).filter(
        Volume.id == volume_id,
        Volume.project_id == project_id,
    ).first()

    if not volume:
        raise HTTPException(status_code=404, detail="Volume not found")

    if request.title is not None:
        volume.title = request.title
    if request.summary is not None:
        volume.summary = request.summary
    db.commit()
    db.refresh(volume)

    return volume


@router.put("/{project_id}/arcs/{arc_id}", response_model=ArcResponse)
async def update_arc(
    project_id: int,
    arc_id: int,
    request: ArcUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """编辑弧名/概要"""
    get_project_for_user(project_id, current_user.id, db)

    arc = db.query(Arc).filter(
        Arc.id == arc_id,
    ).first()

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
    db.commit()
    db.refresh(arc)

    return arc


@router.put("/{project_id}/chapters/{chapter_id}/summary")
async def update_chapter_summary(
    project_id: int,
    chapter_id: int,
    request: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """编辑章节摘要"""
    from app.models.chapter import Chapter

    get_project_for_user(project_id, current_user.id, db)

    chapter = db.query(Chapter).filter(Chapter.id == chapter_id).first()
    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found")

    chapter.summary = request.get("summary")
    db.commit()

    return {"message": "Summary updated"}
