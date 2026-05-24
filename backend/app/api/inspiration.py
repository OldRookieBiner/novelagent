"""灵感确认 API"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.outline import Outline
from app.models.user import User
from app.utils.auth import get_current_user
from app.utils.project import get_project_for_user

router = APIRouter(prefix="/api/projects/{project_id}/inspiration", tags=["inspiration"])


class ConfirmRequest(BaseModel):
    inspiration_data: dict[str, Any]


@router.post("/confirm")
def confirm_inspiration(
    project_id: int,
    request: ConfirmRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """确认灵感采集结果，写入 collected_info"""
    project = get_project_for_user(project_id, current_user.id, db)

    outline = db.query(Outline).filter(Outline.project_id == project_id).first()
    if not outline:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="大纲不存在",
        )

    collected_info = outline.collected_info or {}
    collected_info.update(request.inspiration_data)
    collected_info.pop("_extracted", None)
    outline.collected_info = collected_info
    db.commit()

    return {"status": "ok", "collected_info": collected_info}
