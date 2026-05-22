"""AI 搭档 Agent 的工具集"""

from langchain_core.tools import tool
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models.outline import Outline, ChapterOutline
from app.models.character import Character


def _get_db() -> Session:
    """获取数据库 Session，确保调用方负责关闭"""
    return SessionLocal()


@tool
def read_outline(project_id: int) -> dict:
    """读取项目的大纲信息，包括标题、概述、情节节点、确认状态"""
    db = _get_db()
    try:
        outline = db.query(Outline).filter(Outline.project_id == project_id).first()
        if not outline:
            return {"error": "大纲不存在"}
        return {
            "title": outline.title,
            "summary": outline.summary,
            "plot_points": outline.plot_points,
            "chapter_count_suggested": outline.chapter_count_suggested,
            "confirmed": outline.confirmed,
        }
    finally:
        db.close()


@tool
def update_outline(project_id: int, title: str = None, summary: str = None, plot_points: list = None) -> dict:
    """修改项目的大纲。可以修改标题、概述或情节节点，只传需要修改的字段"""
    db = _get_db()
    try:
        outline = db.query(Outline).filter(Outline.project_id == project_id).first()
        if not outline:
            return {"error": "大纲不存在"}
        if title is not None:
            outline.title = title
        if summary is not None:
            outline.summary = summary
        if plot_points is not None:
            outline.plot_points = plot_points
        db.commit()
        return {"success": True, "message": "大纲已更新"}
    except Exception as e:
        db.rollback()
        return {"error": str(e)}
    finally:
        db.close()


@tool
def read_characters(project_id: int) -> list:
    """读取项目的所有角色信息"""
    db = _get_db()
    try:
        characters = db.query(Character).filter(Character.project_id == project_id).all()
        return [
            {
                "id": c.id,
                "name": c.name,
                "role": c.role,
                "personality": c.personality,
                "core_motivation": c.core_motivation,
                "growth_arc": c.growth_arc,
            }
            for c in characters
        ]
    finally:
        db.close()


@tool
def update_character(project_id: int, character_id: int, name: str = None, role: str = None, personality: str = None, core_motivation: str = None, growth_arc: str = None) -> dict:
    """修改指定角色的信息。只传需要修改的字段"""
    db = _get_db()
    try:
        character = db.query(Character).filter(
            Character.id == character_id,
            Character.project_id == project_id
        ).first()
        if not character:
            return {"error": "角色不存在"}
        if name is not None:
            character.name = name
        if role is not None:
            character.role = role
        if personality is not None:
            character.personality = personality
        if core_motivation is not None:
            character.core_motivation = core_motivation
        if growth_arc is not None:
            character.growth_arc = growth_arc
        db.commit()
        return {"success": True, "message": f"角色「{character.name}」已更新"}
    except Exception as e:
        db.rollback()
        return {"error": str(e)}
    finally:
        db.close()


@tool
def create_character(project_id: int, name: str, role: str, personality: str = "", core_motivation: str = "") -> dict:
    """为项目新增一个角色"""
    db = _get_db()
    try:
        character = Character(
            project_id=project_id,
            name=name,
            role=role,
            personality=personality,
            core_motivation=core_motivation,
        )
        db.add(character)
        db.commit()
        return {"success": True, "message": f"角色「{name}」已创建", "id": character.id}
    except Exception as e:
        db.rollback()
        return {"error": str(e)}
    finally:
        db.close()


@tool
def read_chapter_outlines(project_id: int) -> list:
    """读取项目的所有章节大纲"""
    db = _get_db()
    try:
        outlines = db.query(ChapterOutline).filter(ChapterOutline.project_id == project_id).order_by(ChapterOutline.chapter_number).all()
        return [
            {
                "id": co.id,
                "chapter_number": co.chapter_number,
                "title": co.title,
                "plot": co.plot,
                "confirmed": co.confirmed,
            }
            for co in outlines
        ]
    finally:
        db.close()


@tool
def update_chapter_outline(project_id: int, chapter_outline_id: int, title: str = None, plot: str = None) -> dict:
    """修改指定章节的大纲。只传需要修改的字段"""
    db = _get_db()
    try:
        outline = db.query(ChapterOutline).filter(
            ChapterOutline.id == chapter_outline_id,
            ChapterOutline.project_id == project_id
        ).first()
        if not outline:
            return {"error": "章节大纲不存在"}
        if title is not None:
            outline.title = title
        if plot is not None:
            outline.plot = plot
        db.commit()
        return {"success": True, "message": f"第{outline.chapter_number}章大纲已更新"}
    except Exception as e:
        db.rollback()
        return {"error": str(e)}
    finally:
        db.close()


# 所有 tools 列表，供 agent_graph.py 使用
AGENT_TOOLS = [
    read_outline,
    update_outline,
    read_characters,
    update_character,
    create_character,
    read_chapter_outlines,
    update_chapter_outline,
]
