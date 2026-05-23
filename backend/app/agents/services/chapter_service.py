# backend/app/agents/services/chapter_service.py
"""章节生成/审核/重写核心服务

使用与工作流模式相同的 prompt 体系和质量管道（Draft→SelfCheck→Refine）。
Agent tool 调用本模块的 generate_chapter 即可获得与工作流模式一致的生成质量。
"""

import json
from sqlalchemy.orm import Session
from app.models.outline import ChapterOutline, Outline
from app.models.chapter import Chapter
from app.models.character import Character
from app.agents.tool_context import get_model_config_id, get_user_id
from app.utils.llm import resolve_llm_service
from app.utils.logger import get_logger
from app.agents.nodes.chapter_generation import (
    _calc_max_tokens,
    _build_chapter_content_messages,
    generate_chapter_content_stream,
    _self_check_chapter,
    _refine_chapter_stream,
)
from app.agents.nodes.utils import (
    format_characters_info,
    format_relations_info,
    format_evolution_info,
    format_world_setting,
    safe_format,
    get_prompt_template,
    get_prompts_from_state,
    parse_words_per_chapter,
    _format_chapter_outline_str,
)
from app.agents.context_strategy import get_context_strategy
from app.agents.state import NovelState
from app.agents.prompts import DEFAULT_PROMPTS

logger = get_logger(__name__)


def _build_agent_novel_state(db: Session, project_id: int, chapter_number: int) -> NovelState:
    """从 DB 构建 Agent 模式下的模拟 NovelState

    Agent tool 不在 LangGraph 工作流中运行，没有现成的 state。
    从 DB 加载所有必要数据，构建与工作流模式等价的 state dict，
    确保 _build_chapter_content_messages 等函数可以正常工作。
    """
    outline = db.query(Outline).filter(Outline.project_id == project_id).first()
    characters = db.query(Character).filter(Character.project_id == project_id).all()
    chapter_outlines = (
        db.query(ChapterOutline)
        .filter(ChapterOutline.project_id == project_id)
        .order_by(ChapterOutline.chapter_number)
        .all()
    )
    chapters = (
        db.query(Chapter)
        .filter(Chapter.project_id == project_id)
        .order_by(Chapter.chapter_number)
        .all()
    )

    return {
        "outline_title": outline.title if outline else "",
        "outline_summary": outline.summary if outline else "",
        "outline_plot_points": outline.plot_points if outline else [],
        "outline_world_setting": outline.world_setting if outline else {},
        "outline_emotional_curve": outline.emotional_curve if outline else "",
        "chapter_count": outline.chapter_count_confirmed or outline.chapter_count_suggested or 10,
        "characters": [
            {
                "name": c.name,
                "role": c.role,
                "personality": c.personality or "",
                "core_motivation": c.core_motivation or "",
                "growth_arc": c.growth_arc or "",
                "background": c.background or "",
                "appearance": c.appearance or "",
                "abilities": c.abilities or "",
            }
            for c in characters
        ],
        "chapter_outlines": [
            {
                "chapter_number": co.chapter_number,
                "title": co.title,
                "scene": co.scene or "",
                "characters": co.characters or "",
                "plot": co.plot or "",
                "conflict": co.conflict or "",
                "turning_point": co.turning_point or "",
                "hook": co.hook or "",
                "transition": co.transition or "",
                "ending": co.ending or "",
                "target_words": co.target_words or 3000,
            }
            for co in chapter_outlines
        ],
        "written_chapters": [
            {
                "chapter_number": ch.chapter_number,
                "title": ch.title or "",
                "content": ch.content or "",
                "summary": ch.summary or "",
            }
            for ch in chapters if ch.content
        ],
        "collected_info": {
            "novelType": getattr(outline, 'novel_type', "") if outline else "",
            "targetWords": getattr(outline, 'target_words', 100000) if outline else 100000,
            "stylePreference": getattr(outline, 'style_preference', "") if outline else "",
            "contextStrategy": getattr(outline, 'context_strategy', None) if outline else None,
        },
        "_prompts": DEFAULT_PROMPTS,
        "arcs": [],
    }


async def generate_chapter(db: Session, project_id: int, chapter_number: int) -> dict:
    """生成章节正文——使用与工作流模式相同的 prompt 体系和质量管道"""
    outline = db.query(ChapterOutline).filter(
        ChapterOutline.project_id == project_id,
        ChapterOutline.chapter_number == chapter_number,
    ).first()
    if not outline:
        return {"error": f"第{chapter_number}章大纲不存在"}

    state = _build_agent_novel_state(db, project_id, chapter_number)
    llm = resolve_llm_service(get_model_config_id(), get_user_id())

    chapter_outline = {
        "chapter_number": chapter_number,
        "title": outline.title,
        "scene": outline.scene or "",
        "characters": outline.characters or "",
        "plot": outline.plot or "",
        "conflict": outline.conflict or "",
        "turning_point": outline.turning_point or "",
        "hook": outline.hook or "",
        "transition": outline.transition or "",
        "ending": outline.ending or "",
        "target_words": outline.target_words or 3000,
    }

    # Phase 1: Draft
    draft_content = ""
    try:
        async for chunk in generate_chapter_content_stream(state, chapter_outline, llm):
            draft_content += chunk
    except Exception as e:
        logger.error(f"Chapter draft generation failed: {e}")
        return {"error": f"生成失败: {str(e)}"}

    if not draft_content.strip():
        return {"error": "生成结果为空，请重试"}

    # Phase 2: SelfCheck
    try:
        check_result = await _self_check_chapter(llm, draft_content, state)
    except Exception as e:
        logger.warning(f"Chapter self-check failed, using draft: {e}")
        check_result = {"paragraphs": []}

    # Phase 3: Refine
    info = state.get("collected_info", {})
    min_words, _ = parse_words_per_chapter(info)

    if check_result.get("paragraphs"):
        final_content = ""
        try:
            async for chunk in _refine_chapter_stream(llm, draft_content, check_result, min_words, state):
                final_content += chunk
        except Exception as e:
            logger.warning(f"Chapter refine failed, using draft: {e}")
            final_content = draft_content
    else:
        final_content = draft_content

    # 写入 DB
    try:
        chapter = db.query(Chapter).filter(
            Chapter.project_id == project_id,
            Chapter.chapter_number == chapter_number,
        ).first()
        if chapter:
            chapter.content = final_content
        else:
            chapter = Chapter(
                project_id=project_id,
                chapter_number=chapter_number,
                title=outline.title,
                content=final_content,
                target_words=outline.target_words or 3000,
            )
            db.add(chapter)
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to save chapter: {e}")
        return {"error": f"保存失败: {str(e)}"}

    word_count = len(final_content)
    preview = final_content[:200] + ("..." if word_count > 200 else "")
    return {
        "success": True,
        "message": f"第{chapter_number}章「{outline.title}」已生成（{word_count}字）",
        "chapter_number": chapter_number,
        "title": outline.title,
        "word_count": word_count,
        "preview": preview,
    }


async def review_chapter(db: Session, project_id: int, chapter_number: int) -> dict:
    """审核章节——使用系统 prompt 模板"""
    chapter = db.query(Chapter).filter(
        Chapter.project_id == project_id,
        Chapter.chapter_number == chapter_number,
    ).first()
    if not chapter or not chapter.content:
        return {"error": f"第{chapter_number}章内容不存在，请先生成"}

    state = _build_agent_novel_state(db, project_id, chapter_number)
    llm = resolve_llm_service(get_model_config_id(), get_user_id())

    outline = db.query(ChapterOutline).filter(
        ChapterOutline.project_id == project_id,
        ChapterOutline.chapter_number == chapter_number,
    ).first()

    # 构建章节大纲字符串（供 prompt 模板使用）
    chapter_outline_data = {
        "title": outline.title if outline else "",
        "scene": outline.scene or "",
        "characters": outline.characters or "",
        "plot": outline.plot or "",
        "conflict": outline.conflict or "",
        "turning_point": outline.turning_point or "",
        "ending": outline.ending or "",
    }
    chapter_outline_str = _format_chapter_outline_str(chapter_outline_data)

    # 使用 get_prompts_from_state 正确解析 prompt（处理 dict/string 两种格式）
    system_template, user_template = get_prompts_from_state(state, "review")
    prompt_template = get_prompt_template(system_template, user_template)

    # 获取题材/风格信息
    info = state.get("collected_info", {})
    genre = info.get("novelType", "")

    prompt = safe_format(prompt_template,
        strictness="standard",
        chapter_outline=chapter_outline_str,
        chapter_content=chapter.content,
        genre=genre,
        style_preference=info.get("stylePreference", ""),
    )

    try:
        result_text = await llm.chat(
            [{"role": "user", "content": prompt}],
            max_tokens=2048,
        )
        result_text = result_text.strip()
        if result_text.startswith("```"):
            result_text = result_text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
        review_result = json.loads(result_text)
        return {"success": True, "review": review_result}
    except json.JSONDecodeError:
        return {"success": True, "review": {"passed": True, "raw": result_text}, "warning": "审核结果解析不完整"}
    except Exception as e:
        logger.error(f"Review failed: {e}")
        return {"error": f"审核失败: {str(e)}"}


async def rewrite_chapter(db: Session, project_id: int, chapter_number: int, review_feedback: str) -> dict:
    """根据审核意见重写章节——使用 prompt 模板"""
    chapter = db.query(Chapter).filter(
        Chapter.project_id == project_id,
        Chapter.chapter_number == chapter_number,
    ).first()
    if not chapter or not chapter.content:
        return {"error": f"第{chapter_number}章内容不存在"}

    state = _build_agent_novel_state(db, project_id, chapter_number)
    llm = resolve_llm_service(get_model_config_id(), get_user_id())

    outline = db.query(ChapterOutline).filter(
        ChapterOutline.project_id == project_id,
        ChapterOutline.chapter_number == chapter_number,
    ).first()

    # 构建章节大纲字符串
    chapter_outline_data = {
        "title": outline.title if outline else "",
        "scene": outline.scene or "",
        "characters": outline.characters or "",
        "plot": outline.plot or "",
        "conflict": outline.conflict or "",
        "turning_point": outline.turning_point or "",
        "ending": outline.ending or "",
    }
    chapter_outline_str = _format_chapter_outline_str(chapter_outline_data)

    # 使用 get_prompts_from_state 正确解析 prompt
    system_template, user_template = get_prompts_from_state(state, "rewrite")
    prompt_template = get_prompt_template(system_template, user_template)

    info = state.get("collected_info", {})
    genre = info.get("novelType", "")

    prompt = safe_format(prompt_template,
        chapter_outline=chapter_outline_str,
        review_feedback=review_feedback,
        original_content=chapter.content,
        genre=genre,
    )

    max_tokens = _calc_max_tokens(outline.target_words if outline else 3000)

    full_content = ""
    try:
        async for chunk in llm.chat_stream(
            [{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
        ):
            if chunk:
                full_content += chunk
    except Exception as e:
        logger.error(f"Rewrite failed: {e}")
        return {"error": f"重写失败: {str(e)}"}

    if not full_content.strip():
        return {"error": "重写结果为空，请重试"}

    try:
        chapter.content = full_content
        db.commit()
    except Exception as e:
        db.rollback()
        return {"error": f"保存失败: {str(e)}"}

    word_count = len(full_content)
    preview = full_content[:200] + ("..." if word_count > 200 else "")
    return {
        "success": True,
        "message": f"第{chapter_number}章已重写（{word_count}字）",
        "chapter_number": chapter_number,
        "title": outline.title if outline else f"第{chapter_number}章",
        "word_count": word_count,
        "preview": preview,
    }
