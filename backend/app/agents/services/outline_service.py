# backend/app/agents/services/outline_service.py
"""大纲与章节大纲服务

为 agent_tools.py 提取共享的业务逻辑。
所有函数都是 async def，保持接口一致性。
写操作返回 changes 列表用于审计追踪。
"""

from sqlalchemy.orm import Session
from app.models.outline import Outline, ChapterOutline


async def read_outline(db: Session, project_id: int) -> dict:
    """读取项目大纲"""
    outline = db.query(Outline).filter(Outline.project_id == project_id).first()
    if not outline:
        return {"error": "大纲不存在"}
    return {
        "title": outline.title,
        "summary": outline.summary,
        "plot_points": outline.plot_points or [],
        "chapter_count_suggested": outline.chapter_count_suggested,
        "chapter_count_confirmed": outline.chapter_count_confirmed,
        "confirmed": outline.confirmed,
        "characters": outline.characters or [],
        "world_setting": outline.world_setting or {},
        "emotional_curve": outline.emotional_curve,
    }


async def update_outline(db: Session, project_id: int, updates: dict) -> dict:
    """更新项目大纲，返回 changes 审计列表"""
    outline = db.query(Outline).filter(Outline.project_id == project_id).first()
    if not outline:
        return {"error": "大纲不存在"}

    changes = []
    field_labels = {
        "title": "标题",
        "summary": "概述",
        "plot_points": "情节要点",
        "characters": "人物设定",
        "world_setting": "世界观设定",
        "emotional_curve": "情感曲线",
        "chapter_count_suggested": "建议章节数",
        "chapter_count_confirmed": "章节数确认",
        "confirmed": "大纲确认",
    }

    for key, value in updates.items():
        if hasattr(outline, key):
            old_val = getattr(outline, key)
            if old_val != value:
                setattr(outline, key, value)
                label = field_labels.get(key, key)
                # 对于简单值显示新旧对比，对于复杂对象只显示已更新
                if isinstance(value, (list, dict)):
                    changes.append(f"{label}已更新")
                elif isinstance(old_val, bool) or isinstance(value, bool):
                    changes.append(f"{label}: {'是' if old_val else '否'} → {'是' if value else '否'}")
                else:
                    old_str = str(old_val)[:50] if old_val else "空"
                    new_str = str(value)[:50] if value else "空"
                    changes.append(f"{label}: {old_str} → {new_str}")

    if changes:
        try:
            db.commit()
        except Exception:
            db.rollback()
            return {"error": "保存失败"}

    return {"success": True, "changes": changes}


async def read_chapter_outlines(db: Session, project_id: int) -> list[dict]:
    """读取项目所有章节大纲"""
    outlines = (
        db.query(ChapterOutline)
        .filter(ChapterOutline.project_id == project_id)
        .order_by(ChapterOutline.chapter_number)
        .all()
    )
    return [
        {
            "id": o.id,
            "chapter_number": o.chapter_number,
            "title": o.title,
            "scene": o.scene,
            "characters": o.characters,
            "plot": o.plot,
            "conflict": o.conflict,
            "turning_point": o.turning_point,
            "hook": o.hook,
            "transition": o.transition,
            "ending": o.ending,
            "opening_state": o.opening_state,
            "emotional_arc": o.emotional_arc,
            "key_scenes": o.key_scenes,
            "pacing_note": o.pacing_note,
            "target_words": o.target_words,
            "confirmed": o.confirmed,
        }
        for o in outlines
    ]


async def update_chapter_outline(db: Session, project_id: int, chapter_number: int, updates: dict) -> dict:
    """更新单章大纲，返回 changes 审计列表"""
    outline = (
        db.query(ChapterOutline)
        .filter(
            ChapterOutline.project_id == project_id,
            ChapterOutline.chapter_number == chapter_number,
        )
        .first()
    )
    if not outline:
        return {"error": f"第{chapter_number}章大纲不存在"}

    changes = []
    field_labels = {
        "title": "标题",
        "scene": "场景",
        "characters": "出场人物",
        "plot": "情节要点",
        "conflict": "冲突",
        "turning_point": "转折点",
        "hook": "悬念钩子",
        "transition": "过渡衔接",
        "ending": "结尾",
        "opening_state": "开场状态",
        "emotional_arc": "情绪弧线",
        "key_scenes": "核心场景",
        "pacing_note": "节奏标注",
        "target_words": "目标字数",
        "confirmed": "确认",
    }

    for key, value in updates.items():
        if hasattr(outline, key):
            old_val = getattr(outline, key)
            if old_val != value:
                setattr(outline, key, value)
                label = field_labels.get(key, key)
                if isinstance(old_val, bool) or isinstance(value, bool):
                    changes.append(f"{label}: {'是' if old_val else '否'} → {'是' if value else '否'}")
                elif isinstance(value, (list, dict)):
                    changes.append(f"{label}已更新")
                else:
                    old_str = str(old_val)[:50] if old_val else "空"
                    new_str = str(value)[:50] if value else "空"
                    changes.append(f"{label}: {old_str} → {new_str}")

    if changes:
        try:
            db.commit()
        except Exception:
            db.rollback()
            return {"error": "保存失败"}

    return {"success": True, "changes": changes}
