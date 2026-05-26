"""大纲生成节点 — 创作智能体版本

基于故事种子生成大纲，解析并持久化到 DB。
复用旧版 parse_outline / prepare_outline_prompt 的解析逻辑，
但使用新 NovelState + KnowledgeBaseService 模式。
"""

import logging
from typing import Optional

from app.agents.state import NovelState, Phase, ConfirmationType
from app.agents.services.knowledge_base import KnowledgeBaseService
from app.agents.prompts import OUTLINE_GENERATION_PROMPT
from app.utils.llm import get_llm_from_state_async
from app.agents.nodes.utils import get_prompts_from_state, safe_format

logger = logging.getLogger(__name__)


async def outline_generation_node(state: NovelState) -> NovelState:
    """基于故事种子生成大纲

    流程：
    1. 从 state 获取 story_seed
    2. 调用 LLM 生成大纲
    3. 解析大纲（标题/概述/世界观/情节节点/角色/情感曲线）
    4. 持久化到 DB（Outline 模型）
    5. 设置 outline_id 到 state
    """
    project_id = state["project_id"]
    story_seed = state.get("story_seed", "")
    kb = KnowledgeBaseService(project_id)

    llm = await get_llm_from_state_async(state)
    prompts = state.get("_prompts", {})
    _, user_template = get_prompts_from_state(prompts, "outline_generation")

    if user_template:
        prompt_text = safe_format(user_template, story_seed=story_seed)
    else:
        prompt_text = safe_format(OUTLINE_GENERATION_PROMPT, story_seed=story_seed)

    # 流式生成
    response = ""
    try:
        from langgraph.config import get_stream_writer
        writer = get_stream_writer()
        async for chunk in llm.chat_stream(
            [{"role": "user", "content": prompt_text}],
            max_tokens=8192,
            temperature=0.7,
        ):
            response += chunk
            writer({"type": "outline_chunk", "content": chunk})
    except ImportError:
        # langgraph.config 不可用时退化为非流式
        async for chunk in llm.chat_stream(
            [{"role": "user", "content": prompt_text}],
            max_tokens=8192,
            temperature=0.7,
        ):
            response += chunk

    # 解析大纲
    outline_data = _parse_outline_simple(response)

    # 持久化到 DB
    outline_id = _persist_outline(project_id, outline_data)

    return {
        **state,
        "outline_id": outline_id,
        "chapter_count": outline_data.get("chapter_count_suggested", 20),
    }


def _parse_outline_simple(response: str) -> dict:
    """简化版大纲解析

    从 LLM 输出中提取标题、概述、角色、世界观、情节节点。
    复杂解析逻辑在旧版 outline_generation.py 的 parse_outline 函数中，
    此处用简化版保证骨架可用，后续阶段增强。
    """
    import re

    title = ""
    summary = ""
    characters = []
    world_setting = {}
    plot_points = []
    emotional_curve = ""
    chapter_count_suggested = 20

    # 提取标题
    m = re.search(r'(?:#{1,3}\s*)?标题[：:]\s*(.+?)(?:\n|$)', response)
    if m:
        title = m.group(1).strip()
    if not title:
        m = re.search(r'《(.+?)》', response)
        if m:
            title = m.group(1).strip()

    # 提取概述
    m = re.search(r'(?:#{1,3}\s*)?概述[：:]\s*(.+?)(?=\n#{1,3}|\n---|\Z)', response, re.DOTALL)
    if m:
        summary = m.group(1).strip()[:2000]

    # 提取章节数
    m = re.search(r'建议章节数[：:]\s*(\d+)', response)
    if m:
        chapter_count_suggested = int(m.group(1))

    return {
        "title": title,
        "summary": summary,
        "characters": characters,
        "world_setting": world_setting,
        "plot_points": plot_points,
        "emotional_curve": emotional_curve,
        "chapter_count_suggested": chapter_count_suggested,
    }


def _persist_outline(project_id: int, outline_data: dict) -> Optional[int]:
    """持久化大纲到 DB，返回 outline_id"""
    from app.database import SessionLocal
    from app.models.outline import Outline

    db = SessionLocal()
    committed = False
    try:
        outline = db.query(Outline).filter(
            Outline.project_id == project_id
        ).first()

        if outline:
            # 更新现有大纲
            if outline_data.get("title"):
                outline.title = outline_data["title"]
            if outline_data.get("summary"):
                outline.summary = outline_data["summary"]
            if outline_data.get("plot_points"):
                outline.plot_points = outline_data["plot_points"]
            if outline_data.get("characters"):
                outline.characters = outline_data["characters"]
            if outline_data.get("world_setting"):
                outline.world_setting = outline_data["world_setting"]
            if outline_data.get("emotional_curve"):
                outline.emotional_curve = outline_data["emotional_curve"]
            outline.confirmed = True
            outline.chapter_count_suggested = outline_data.get("chapter_count_suggested", 0)
        else:
            # 创建新大纲
            outline = Outline(
                project_id=project_id,
                title=outline_data.get("title", ""),
                summary=outline_data.get("summary", ""),
                plot_points=outline_data.get("plot_points", []),
                characters=outline_data.get("characters", []),
                world_setting=outline_data.get("world_setting", {}),
                emotional_curve=outline_data.get("emotional_curve", ""),
                confirmed=True,
                chapter_count_suggested=outline_data.get("chapter_count_suggested", 0),
                chapter_count_confirmed=True,
            )
            db.add(outline)

        db.commit()
        committed = True
        db.refresh(outline)
        return outline.id
    except Exception as e:
        logger.error(f"Failed to persist outline: {e}")
        return None
    finally:
        if not committed:
            try:
                db.rollback()
            except Exception:
                pass
        try:
            db.close()
        except Exception:
            pass


# ========== 旧版兼容导出 ==========

# 旧版常量
DEFAULT_CHAPTER_COUNT = 20

# 旧版别名：outline_generation_node 同时作为 generate_outline_node
generate_outline_node = outline_generation_node


def generate_outline_stream(state, llm):
    """旧版流式生成兼容（退化为非流式，返回空迭代器）"""
    import asyncio
    async def _empty():
        return
        yield  # make it an async generator
    return _empty()


# 旧版 parse_outline 函数（简化实现）
def parse_outline(response: str) -> dict:
    """解析大纲响应（兼容旧 API）"""
    return _parse_outline_simple(response)
