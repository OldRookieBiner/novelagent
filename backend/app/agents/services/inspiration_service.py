# backend/app/agents/services/inspiration_service.py
"""灵感简报服务

为 agent_tools.py 提供灵感简报（inspiration_template）的读写能力。
灵感简报存储于 Outline.inspiration_template 字段中。
"""

from sqlalchemy.orm import Session
from app.models.outline import Outline


async def read_inspiration_brief(db: Session, project_id: int) -> dict:
    """读取项目的灵感简报"""
    outline = db.query(Outline).filter(Outline.project_id == project_id).first()
    if not outline:
        return {"error": "大纲不存在，无法读取灵感简报"}
    return {
        "inspiration_template": outline.inspiration_template or "",
    }


async def update_inspiration_brief(db: Session, project_id: int, brief: str) -> dict:
    """更新项目的灵感简报，返回 changes 审计列表"""
    outline = db.query(Outline).filter(Outline.project_id == project_id).first()
    if not outline:
        return {"error": "大纲不存在，无法更新灵感简报"}

    old_brief = outline.inspiration_template or ""
    if old_brief == brief:
        return {"success": True, "changes": []}

    outline.inspiration_template = brief
    try:
        db.commit()
    except Exception:
        db.rollback()
        return {"error": "保存灵感简报失败"}

    # 生成友好变更描述
    if not old_brief:
        changes = ["灵感简报已创建"]
    elif not brief:
        changes = ["灵感简报已清空"]
    else:
        changes = ["灵感简报已更新"]

    return {"success": True, "changes": changes}
