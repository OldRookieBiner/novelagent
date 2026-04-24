"""Chapter generation nodes"""

import re
from typing import Dict, Any, AsyncIterator

from app.agents.state import NovelState, STAGE_CHAPTER_OUTLINES, STAGE_WRITING
from app.agents.prompts import (
    GENERATE_SINGLE_CHAPTER_OUTLINE_PROMPT,
    GENERATE_CHAPTER_CONTENT_PROMPT,
)
from app.services.llm import LLMService, get_llm_service_from_config, get_llm_service


def _clean_chapter_title(title: str) -> str:
    """Clean chapter title by removing chapter number prefix and book title marks.

    Examples:
    - "主动嵌入" -> "主动嵌入"
    - "第3章《被迫入局》" -> "被迫入局"
    - "第六章：《残响与追猎》" -> "残响与追猎"
    - "第十二章 破茧" -> "破茧"
    """
    title = title.strip()

    # Remove chapter number prefix patterns:
    # - "第N章" (Arabic numerals: 第1章, 第12章)
    # - "第X章" (Chinese numerals: 第一章, 第十二章)
    # - Optional colon after 章节名: or ： separators
    title = re.sub(r'^第[一二三四五六七八九十百千万\d]+章[：:]*\s*', '', title)

    # Remove book title marks 《》 if present
    title = re.sub(r'^《(.+)》$', r'\1', title)

    return title.strip()


def clean_chapter_content(content: str) -> str:
    """清理章节内容，移除 LLM 可能添加的结尾数字

    某些 LLM 会在生成内容末尾添加字数统计等数字，此函数移除这些多余的数字。
    只移除独立成行的数字，不移除段落中的数字。

    Args:
        content: 原始章节内容

    Returns:
        清理后的章节内容

    Examples:
        >>> clean_chapter_content("正文内容\\n\\n3247")
        '正文内容'
        >>> clean_chapter_content("正文内容3247")
        '正文内容3247'
    """
    if not content:
        return content

    result = content.strip()

    # 循环移除结尾的纯数字行，直到没有更多匹配
    # 使用循环处理多个连续的结尾数字行
    pattern = re.compile(r'\n+\s*\d+\s*$')
    while pattern.search(result):
        result = pattern.sub('', result)

    return result


def parse_single_chapter_outline(response: str, chapter_number: int) -> dict:
    """解析单章节大纲（增强版）

    返回结构：
    {
        "chapter_number": int,
        "title": str,
        "scene": str,
        "characters": str,
        "plot": str,
        "conflict": str,
        "turning_point": str,  # 新增
        "hook": str,
        "transition": str,  # 新增
        "ending": str,
        "target_words": int
    }
    """
    chapter = {
        "chapter_number": chapter_number,
        "title": "",
        "scene": "",
        "characters": "",
        "plot": "",
        "conflict": "",
        "turning_point": "",
        "hook": "",
        "transition": "",
        "ending": "",
        "target_words": 3000
    }

    # Extract title
    title_match = re.search(r"章节名[：:]\s*(.+)", response)
    if title_match:
        raw_title = title_match.group(1).strip()
        chapter["title"] = _clean_chapter_title(raw_title)

    # Extract scene
    scene_match = re.search(r"场景[：:]\s*(.+)", response)
    if scene_match:
        chapter["scene"] = scene_match.group(1).strip()

    # Extract characters
    characters_match = re.search(r"人物[：:]\s*(.+)", response)
    if characters_match:
        chapter["characters"] = characters_match.group(1).strip()

    # Extract plot
    plot_match = re.search(r"情节[：:]\s*(.+?)(?=冲突|转折|钩子|衔接|结局|预计字数|$)", response, re.DOTALL)
    if plot_match:
        chapter["plot"] = plot_match.group(1).strip()

    # Extract conflict
    conflict_match = re.search(r"冲突[：:]\s*(.+?)(?=转折|钩子|衔接|结局|预计字数|$)", response, re.DOTALL)
    if conflict_match:
        chapter["conflict"] = conflict_match.group(1).strip()

    # Extract turning_point（新增）
    turning_match = re.search(r"转折[：:]\s*(.+?)(?=钩子|衔接|结局|预计字数|$)", response, re.DOTALL)
    if turning_match:
        chapter["turning_point"] = turning_match.group(1).strip()

    # Extract hook
    hook_match = re.search(r"钩子[：:]\s*(.+?)(?=衔接|结局|预计字数|$)", response, re.DOTALL)
    if hook_match:
        chapter["hook"] = hook_match.group(1).strip()

    # Extract transition（新增）
    transition_match = re.search(r"衔接[：:]\s*(.+?)(?=结局|预计字数|$)", response, re.DOTALL)
    if transition_match:
        chapter["transition"] = transition_match.group(1).strip()

    # Extract ending
    ending_match = re.search(r"结局[：:]\s*(.+?)(?=预计字数|$)", response, re.DOTALL)
    if ending_match:
        chapter["ending"] = ending_match.group(1).strip()

    # Extract target words
    words_match = re.search(r"预计字数[：:]\s*(\d+)", response)
    if words_match:
        chapter["target_words"] = int(words_match.group(1))

    return chapter


async def generate_single_chapter_outline(
    state: NovelState,
    chapter_number: int,
    llm: LLMService,
    previous_chapters: list[dict] = None
) -> dict:
    """Generate a single chapter outline"""

    outline = f"标题：{state.get('outline_title', '')}\n概述：{state.get('outline_summary', '')}"
    plot_points = state.get("outline_plot_points", [])
    plot_points_str = "\n".join([f"{i+1}. {p}" for i, p in enumerate(plot_points)]) if plot_points else "无"

    chapter_count = state.get("chapter_count", 10)

    # Build previous chapters info for context
    previous_info = ""
    if previous_chapters and len(previous_chapters) > 0:
        # Only show last 3 chapters for context
        recent = previous_chapters[-3:]
        previous_info = "前几章概要：\n" + "\n".join([
            f"- 第{c['chapter_number']}章《{c.get('title', '')}》：{c.get('plot', '')[:50]}..."
            for c in recent
        ])

    prompt = GENERATE_SINGLE_CHAPTER_OUTLINE_PROMPT.format(
        outline=outline,
        plot_points=plot_points_str,
        chapter_count=chapter_count,
        chapter_number=chapter_number,
        previous_chapters_info=previous_info
    )

    response = await llm.chat([{"role": "user", "content": prompt}])

    return parse_single_chapter_outline(response, chapter_number)


async def generate_chapter_outlines_stream(
    state: NovelState,
    llm: LLMService
) -> AsyncIterator[dict]:
    """Generate chapter outlines one by one with streaming progress"""

    chapter_count = state.get("chapter_count", 10)
    generated_chapters = []

    for chapter_num in range(1, chapter_count + 1):
        chapter_outline = await generate_single_chapter_outline(
            state,
            chapter_num,
            llm,
            generated_chapters
        )
        generated_chapters.append(chapter_outline)

        # Yield progress event
        yield {
            "type": "progress",
            "chapter_number": chapter_num,
            "total": chapter_count,
            "chapter": chapter_outline
        }

    # Yield completion event
    yield {
        "type": "done",
        "chapter_outlines": generated_chapters
    }


async def generate_chapter_outlines_node(state: NovelState, llm: LLMService) -> NovelState:
    """Generate all chapter outlines (legacy synchronous version)"""

    chapter_count = state.get("chapter_count", 10)
    generated_chapters = []

    for chapter_num in range(1, chapter_count + 1):
        chapter_outline = await generate_single_chapter_outline(
            state,
            chapter_num,
            llm,
            generated_chapters
        )
        generated_chapters.append(chapter_outline)

    new_state: NovelState = {
        **state,
        "chapter_outlines": generated_chapters,
        "stage": STAGE_CHAPTER_OUTLINES,
    }

    return new_state


async def generate_chapter_content_stream(
    state: NovelState,
    chapter_outline: dict,
    llm: LLMService
) -> AsyncIterator[str]:
    """生成章节内容（流式，增强版）"""

    info = state.get("collected_info", {})
    characters = state.get("outline_characters", [])
    world_setting = state.get("outline_world_setting", {})

    # 格式化章节大纲（包含新字段）
    outline_str = f"""
章节名：{chapter_outline['title']}
场景：{chapter_outline['scene']}
人物：{chapter_outline['characters']}
情节：{chapter_outline['plot']}
冲突：{chapter_outline['conflict']}
转折：{chapter_outline.get('turning_point', '无')}
钩子：{chapter_outline.get('hook', '')}
"""

    # 格式化人物设定
    if characters:
        chars_str = "\n".join([
            f"- {c.get('name', '')}：{c.get('personality', '')}，动机：{c.get('motivation', '')}"
            for c in characters
        ])
    else:
        chars_str = info.get("customProtagonist") or info.get("protagonist", "未指定")

    # 格式化世界观
    if world_setting:
        world_str = f"时代：{world_setting.get('era', '')}，核心设定：{world_setting.get('core_rules', '')}"
    else:
        world_str = info.get("customWorldSetting") or info.get("worldSetting", "未指定")

    prompt = GENERATE_CHAPTER_CONTENT_PROMPT.format(
        chapter_outline=outline_str,
        previous_ending="",
        genre=info.get("novelType", "未指定"),
        main_characters=chars_str,
        world_setting=world_str,
        style_preference=info.get("stylePreference", "未指定")
    )

    async for chunk in llm.chat_stream([{"role": "user", "content": prompt}]):
        yield chunk


# ==================== LangGraph 兼容节点 ====================

def _get_llm_from_state(state: NovelState) -> LLMService:
    """
    从状态获取 LLM 服务

    根据状态中的 llm_config_id 或 project_id 获取对应的 LLM 服务。
    此函数需要在调用时获取数据库会话。
    """
    from app.database import SessionLocal
    from app.models.user import UserSettings
    from app.models.model_config import ModelConfig

    db = SessionLocal()
    try:
        llm_config_id = state.get("llm_config_id")
        project_id = state.get("project_id")

        # 获取项目以获取 user_id
        from app.models.project import Project
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise ValueError(f"Project {project_id} not found")

        user_id = project.user_id

        # 如果指定了模型配置 ID，使用该配置
        if llm_config_id:
            model_config = db.query(ModelConfig).filter(
                ModelConfig.id == llm_config_id,
                ModelConfig.user_id == user_id,
                ModelConfig.is_enabled == True
            ).first()
            if model_config:
                return get_llm_service_from_config(model_config, user_id)

        # 否则使用用户的默认模型配置
        default_config = db.query(ModelConfig).filter(
            ModelConfig.user_id == user_id,
            ModelConfig.is_default == True,
            ModelConfig.is_enabled == True
        ).first()

        if default_config:
            return get_llm_service_from_config(default_config, user_id)

        # 回退到用户设置
        user_settings = db.query(UserSettings).filter(
            UserSettings.user_id == user_id
        ).first()

        if not user_settings:
            raise ValueError(f"User settings not found for user {user_id}")

        return get_llm_service(user_settings)

    finally:
        db.close()


async def chapter_outlines_node(state: NovelState) -> NovelState:
    """
    LangGraph 兼容的章节大纲生成节点

    此节点从状态获取 LLM 服务，生成所有章节大纲，并返回更新后的状态。
    签名：(state: NovelState) -> NovelState
    """
    # 获取 LLM 服务
    llm = _get_llm_from_state(state)

    # 调用现有的章节大纲生成函数
    return await generate_chapter_outlines_node(state, llm)


async def generate_chapter_content_node(state: NovelState) -> NovelState:
    """
    LangGraph 兼容的章节内容生成节点

    此节点：
    1. 获取当前章节号 (current_chapter)
    2. 获取章节大纲列表 (chapter_outlines)
    3. 获取已写章节用于上下文 (written_chapters)
    4. 调用 LLM 生成章节内容
    5. 返回更新后的状态，包含新章节

    签名：(state: NovelState) -> NovelState
    """
    # 获取 LLM 服务
    llm = _get_llm_from_state(state)

    # 获取当前章节信息
    current_chapter = state.get("current_chapter", 1)
    chapter_outlines = state.get("chapter_outlines", [])
    written_chapters = state.get("written_chapters", [])

    # 找到当前章节的大纲
    chapter_outline = None
    for outline in chapter_outlines:
        if outline.get("chapter_number") == current_chapter:
            chapter_outline = outline
            break

    if not chapter_outline:
        raise ValueError(f"Chapter outline not found for chapter {current_chapter}")

    # 获取上一章的结尾用于衔接
    previous_ending = ""
    if written_chapters:
        # 找到上一章的内容
        for chapter in written_chapters:
            if chapter.get("chapter_number") == current_chapter - 1:
                content = chapter.get("content", "")
                # 取最后 500 字作为衔接参考
                previous_ending = content[-500:] if len(content) > 500 else content
                break

    # 准备提示词
    info = state.get("collected_info", {})
    characters = state.get("outline_characters", [])
    world_setting = state.get("outline_world_setting", {})

    # 格式化章节大纲
    outline_str = f"""
章节名：{chapter_outline.get('title', '')}
场景：{chapter_outline.get('scene', '')}
人物：{chapter_outline.get('characters', '')}
情节：{chapter_outline.get('plot', '')}
冲突：{chapter_outline.get('conflict', '')}
转折：{chapter_outline.get('turning_point', '无')}
钩子：{chapter_outline.get('hook', '')}
"""

    # 格式化人物设定
    if characters:
        chars_str = "\n".join([
            f"- {c.get('name', '')}：{c.get('personality', '')}，动机：{c.get('motivation', '')}"
            for c in characters
        ])
    else:
        chars_str = info.get("customProtagonist") or info.get("protagonist", "未指定")

    # 格式化世界观
    if world_setting:
        world_str = f"时代：{world_setting.get('era', '')}，核心设定：{world_setting.get('core_rules', '')}"
    else:
        world_str = info.get("customWorldSetting") or info.get("worldSetting", "未指定")

    prompt = GENERATE_CHAPTER_CONTENT_PROMPT.format(
        chapter_outline=outline_str,
        previous_ending=previous_ending,
        genre=info.get("novelType", "未指定"),
        main_characters=chars_str,
        world_setting=world_str,
        style_preference=info.get("stylePreference", "未指定")
    )

    # 调用 LLM 生成内容
    content = await llm.chat([{"role": "user", "content": prompt}])

    # 后处理：移除结尾的纯数字（可能是 LLM 自动添加的字数）
    content = clean_chapter_content(content)

    # 计算字数
    word_count = len(content)

    # 创建新章节
    new_chapter = {
        "chapter_number": current_chapter,
        "title": chapter_outline.get("title", ""),
        "content": content,
        "word_count": word_count
    }

    # 更新状态
    new_state: NovelState = {
        **state,
        "written_chapters": [new_chapter],  # 使用 Annotated[List, add] 会自动追加
        "current_chapter": current_chapter + 1,
        "stage": STAGE_WRITING,
    }

    return new_state
