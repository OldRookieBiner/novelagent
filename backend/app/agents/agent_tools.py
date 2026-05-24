# backend/app/agents/agent_tools.py
"""AI 搭档 Agent 的工具集

全部 async tool，调 services/ 共享能力层。
运行时上下文通过 tool_context（contextvars）传递。
"""

from langchain_core.tools import tool
from app.database import SessionLocal

from app.agents.services.outline_service import (
    read_outline as svc_read_outline,
    update_outline as svc_update_outline,
    read_chapter_outlines as svc_read_chapter_outlines,
    update_chapter_outline as svc_update_chapter_outline,
)
from app.agents.services.character_service import (
    read_characters as svc_read_characters,
    create_character as svc_create_character,
    update_character as svc_update_character,
)
from app.agents.services.relation_service import (
    read_relations as svc_read_relations,
    update_relation as svc_update_relation,
)
from app.agents.services.chapter_service import (
    generate_chapter,
    review_chapter,
    rewrite_chapter,
)
from app.agents.services.edit_service import (
    edit_paragraph as svc_edit_paragraph,
    insert_scene as svc_insert_scene,
    revise_section as svc_revise_section,
    polish_prose as svc_polish_prose,
)
from app.agents.services.inspiration_service import (
    read_inspiration_brief as svc_read_inspiration_brief,
    update_inspiration_brief as svc_update_inspiration_brief,
)


# --- 读取类 tools ---

@tool
async def read_outline(project_id: int) -> dict:
    """读取项目的大纲信息，包括标题、概述、情节节点、确认状态"""
    db = SessionLocal()
    try:
        return await svc_read_outline(db, project_id)
    finally:
        db.close()


@tool
async def read_characters(project_id: int) -> list:
    """读取项目的所有角色信息"""
    db = SessionLocal()
    try:
        return await svc_read_characters(db, project_id)
    finally:
        db.close()


@tool
async def read_chapter_outlines(project_id: int) -> list:
    """读取项目的所有章节大纲"""
    db = SessionLocal()
    try:
        return await svc_read_chapter_outlines(db, project_id)
    finally:
        db.close()


@tool
async def read_relations(project_id: int) -> list:
    """读取项目的人物关系，返回关系列表（包含角色名、关系类型、信任度等）"""
    db = SessionLocal()
    try:
        return await svc_read_relations(db, project_id)
    finally:
        db.close()


@tool
async def read_inspiration_brief(project_id: int) -> dict:
    """读取项目的灵感简报，包括写作风格、核心主题、世界观设定等创作前期收集的全部信息"""
    db = SessionLocal()
    try:
        return await svc_read_inspiration_brief(db, project_id)
    finally:
        db.close()


# --- 写入类 tools ---

@tool
async def update_outline(project_id: int, title: str = None, summary: str = None, plot_points: list = None) -> dict:
    """修改项目的大纲。可以修改标题、概述或情节节点，只传需要修改的字段"""
    db = SessionLocal()
    try:
        return await svc_update_outline(db, project_id, title, summary, plot_points)
    finally:
        db.close()


@tool
async def update_character(project_id: int, character_id: int, name: str = None, role: str = None, personality: str = None, core_motivation: str = None, growth_arc: str = None) -> dict:
    """修改指定角色的信息。只传需要修改的字段"""
    db = SessionLocal()
    try:
        return await svc_update_character(db, project_id, character_id, name, role, personality, core_motivation, growth_arc)
    finally:
        db.close()


@tool
async def create_character(project_id: int, name: str, role: str, personality: str = "", core_motivation: str = "") -> dict:
    """为项目新增一个角色"""
    db = SessionLocal()
    try:
        return await svc_create_character(db, project_id, name, role, personality, core_motivation)
    finally:
        db.close()


@tool
async def update_chapter_outline(project_id: int, chapter_outline_id: int, title: str = None, plot: str = None) -> dict:
    """修改指定章节的大纲。只传需要修改的字段"""
    db = SessionLocal()
    try:
        return await svc_update_chapter_outline(db, project_id, chapter_outline_id, title, plot)
    finally:
        db.close()


@tool
async def update_relations(project_id: int, relation_id: int, relation_type: str = None, direction: str = None, current_status: str = None, trust_level: int = None) -> dict:
    """修改人物关系。可修改关系类型、方向、状态描述、信任度，只传需要修改的字段"""
    db = SessionLocal()
    try:
        return await svc_update_relation(db, project_id, relation_id, relation_type, direction, current_status, trust_level)
    finally:
        db.close()


@tool
async def update_inspiration_brief(project_id: int, brief: str) -> dict:
    """更新项目的灵感简报。brief 为完整的灵感简报 Markdown 文本，会完全替换现有内容"""
    db = SessionLocal()
    try:
        return await svc_update_inspiration_brief(db, project_id, brief)
    finally:
        db.close()


# --- 生成类 tools ---

@tool
async def generate_chapter_content(project_id: int, chapter_number: int) -> dict:
    """生成指定章节的正文内容。生成完成后自动保存，可在写作面板查看完整内容。返回生成摘要和预览。"""
    db = SessionLocal()
    try:
        return await generate_chapter(db, project_id, chapter_number)
    finally:
        db.close()


@tool
async def review_chapter(project_id: int, chapter_number: int) -> dict:
    """审核指定章节的内容，返回结构化审核结果（分数、问题列表、改进建议）。"""
    db = SessionLocal()
    try:
        return await review_chapter(db, project_id, chapter_number)
    finally:
        db.close()


@tool
async def rewrite_chapter(project_id: int, chapter_number: int, review_feedback: str) -> dict:
    """根据审核意见重写指定章节。重写完成后自动保存，可在写作面板查看。review_feedback 填写审核意见摘要。"""
    db = SessionLocal()
    try:
        return await rewrite_chapter(db, project_id, chapter_number, review_feedback)
    finally:
        db.close()


# --- 编辑类 tools ---

@tool
async def edit_paragraph(project_id: int, chapter_number: int, paragraph_index: int, new_content: str) -> dict:
    """替换指定章节的某个段落。paragraph_index 从 0 开始计数。"""
    db = SessionLocal()
    try:
        return await svc_edit_paragraph(db, project_id, chapter_number, paragraph_index, new_content)
    finally:
        db.close()


@tool
async def insert_scene(project_id: int, chapter_number: int, position: int, scene_content: str) -> dict:
    """在章节的指定位置插入新场景。position=0 表示开头，position=N 表示末尾。"""
    db = SessionLocal()
    try:
        return await svc_insert_scene(db, project_id, chapter_number, position, scene_content)
    finally:
        db.close()


@tool
async def revise_section(project_id: int, chapter_number: int, instruction: str, start_para: int = 0, end_para: int = -1) -> dict:
    """按指令修改章节中的段落范围。start_para 和 end_para 从 0 开始计数，-1 表示到末尾。instruction 用自然语言描述修改要求。"""
    db = SessionLocal()
    try:
        return await svc_revise_section(db, project_id, chapter_number, instruction, start_para, end_para)
    finally:
        db.close()


@tool
async def polish_prose(project_id: int, chapter_number: int, style_instruction: str = "") -> dict:
    """润色章节文笔，保持情节不变。style_instruction 可选，指定风格方向。"""
    db = SessionLocal()
    try:
        return await svc_polish_prose(db, project_id, chapter_number, style_instruction)
    finally:
        db.close()


# 所有 tools 列表
AGENT_TOOLS = [
    read_outline,
    read_characters,
    read_chapter_outlines,
    read_relations,
    read_inspiration_brief,
    update_outline,
    update_character,
    create_character,
    update_chapter_outline,
    update_relations,
    update_inspiration_brief,
    generate_chapter_content,
    review_chapter,
    rewrite_chapter,
    edit_paragraph,
    insert_scene,
    revise_section,
    polish_prose,
]
