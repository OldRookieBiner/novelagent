"""Chapter generation nodes"""

import re
from typing import Dict, Any, AsyncIterator

from app.agents.state import NovelState, STAGE_CHAPTER_OUTLINES, STAGE_WRITING
from app.agents.prompts import (
    GENERATE_SINGLE_CHAPTER_OUTLINE_PROMPT,
    GENERATE_CHAPTER_CONTENT_PROMPT,
)
from app.services.llm import LLMService
from app.utils.llm import get_llm_from_state_async
from app.agents.nodes.utils import (
    _format_chapter_outline_str,
    format_characters_info,
    format_relations_info,
    format_evolution_info,
    format_world_setting,
    parse_words_per_chapter,
)


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


def parse_single_chapter_outline(
    response: str,
    chapter_number: int,
    words_per_chapter_range: tuple[int, int] | None = None
) -> dict:
    """解析单章节大纲（增强版）

    Args:
        response: AI 返回的章节大纲文本
        chapter_number: 章节号
        words_per_chapter_range: 每章字数区间 (下限, 上限)，用于钳制 target_words

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

    # 钳制 target_words 到用户设定的每章字数区间
    if words_per_chapter_range:
        lower, upper = words_per_chapter_range
        if chapter["target_words"] < lower:
            chapter["target_words"] = lower
        elif chapter["target_words"] > upper:
            chapter["target_words"] = upper

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

    # 获取每章字数区间
    collected_info = state.get("collected_info", {})
    words_lower, words_upper, words_display = parse_words_per_chapter(collected_info)

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
        previous_chapters_info=previous_info,
        words_per_chapter=words_display
    )

    response = ""
    async for chunk in llm.chat_stream([{"role": "user", "content": prompt}]):
        response += chunk

    return parse_single_chapter_outline(response, chapter_number, (words_lower, words_upper))


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
    if chapter_count <= 0:
        return {**state, "chapter_outlines": [], "stage": STAGE_CHAPTER_OUTLINES}

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


def _calc_max_tokens(target_words: int) -> int:
    """根据目标字数计算 LLM 输出 max_tokens

    中文 1 字 ≈ 1-2 token，加上标点和格式开销，
    实际 token 数约为字数的 2-2.5 倍。设置 2.5 倍上限 + 512 冗余。
    最低 8192 以保证短章节也有足够空间。
    """
    return max(int(target_words * 2.5) + 512, 8192)


async def generate_chapter_content_stream(
    state: NovelState,
    chapter_outline: dict,
    llm: LLMService
) -> AsyncIterator[str]:
    """生成章节内容（流式，增强版）"""

    info = state.get("collected_info", {})

    # 格式化章节大纲（使用共享工具函数）
    outline_str = _format_chapter_outline_str(chapter_outline)

    # 格式化人物设定（使用共享工具函数）
    chars_str = format_characters_info(state)

    # 格式化人物关系（使用共享工具函数）
    relations_str = format_relations_info(state, chapter_outline.get("chapter_number", 1))

    # 格式化人物演变历史（使用共享工具函数）
    evolution_str, evolution_plans_str = format_evolution_info(state, chapter_outline.get("chapter_number", 1))

    # 格式化世界观（使用共享工具函数）
    world_str = format_world_setting(state)

    # 合并人物设定、关系和演变信息
    combined_characters_str = chars_str + relations_str + evolution_str + evolution_plans_str

    # 获取每章字数区间（优先使用用户设定，回退到章节大纲的 target_words）
    _, _, words_display = parse_words_per_chapter(info)
    words_per_chapter_range = words_display
    # 使用区间上限计算 max_tokens，确保不截断
    target_words_for_tokens = chapter_outline.get("target_words", 3000)

    # 获取前章结尾用于衔接
    previous_ending = ""
    written_chapters = state.get("written_chapters", [])
    chapter_number = chapter_outline.get("chapter_number", 1)
    if written_chapters:
        for ch in written_chapters:
            if ch.get("chapter_number") == chapter_number - 1:
                ch_content = ch.get("content", "")
                previous_ending = ch_content[-500:] if len(ch_content) > 500 else ch_content
                break

    prompt = GENERATE_CHAPTER_CONTENT_PROMPT.format(
        chapter_outline=outline_str,
        previous_ending=previous_ending,
        genre=info.get("novelType", "未指定"),
        main_characters=combined_characters_str,
        world_setting=world_str,
        style_preference=info.get("stylePreference", "未指定"),
        words_per_chapter_range=words_per_chapter_range
    )

    # 根据目标字数计算 max_tokens，避免截断
    max_tokens = _calc_max_tokens(target_words_for_tokens)

    async for chunk in llm.chat_stream(
        [{"role": "user", "content": prompt}],
        max_tokens=max_tokens
    ):
        yield chunk


# ==================== LangGraph 兼容节点 ====================

async def chapter_outlines_node(state: NovelState) -> NovelState:
    """
    LangGraph 兼容的章节大纲生成节点

    此节点从状态获取 LLM 服务，生成所有章节大纲，并返回更新后的状态。
    签名：(state: NovelState) -> NovelState
    """
    # 获取 LLM 服务（异步）
    llm = await get_llm_from_state_async(state)

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
    # 获取 LLM 服务（异步）
    llm = await get_llm_from_state_async(state)

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
        chapter_count = state.get("chapter_count", 0)
        raise ValueError(
            f"章节大纲未找到：第 {current_chapter} 章（共 {chapter_count} 章，"
            f"已生成 {len(chapter_outlines)} 个章节大纲）"
        )

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

    # 获取每章字数区间显示文本
    _, _, words_display = parse_words_per_chapter(info)
    words_per_chapter_range = words_display

    # 格式化章节大纲（使用共享工具函数）
    outline_str = _format_chapter_outline_str(chapter_outline)

    # 格式化人物设定（使用共享工具函数）
    chars_str = format_characters_info(state)

    # 格式化人物关系（使用共享工具函数）
    relations_str = format_relations_info(state, chapter_outline.get("chapter_number", 1))

    # 格式化人物演变历史（使用共享工具函数）
    evolution_str, _ = format_evolution_info(state, chapter_outline.get("chapter_number", 1))

    # 格式化世界观（使用共享工具函数）
    world_str = format_world_setting(state)

    # 合并人物设定、关系和演变信息（用于 prompt）
    combined_characters_str = chars_str + relations_str + evolution_str

    # 获取章节目标字数
    # 使用章节大纲的 target_words 计算 max_tokens（用于流式生成容量）
    target_words_for_tokens = chapter_outline.get("target_words", 3000)

    prompt = GENERATE_CHAPTER_CONTENT_PROMPT.format(
        chapter_outline=outline_str,
        previous_ending=previous_ending,
        genre=info.get("novelType", "未指定"),
        main_characters=combined_characters_str,
        world_setting=world_str,
        style_preference=info.get("stylePreference", "未指定"),
        words_per_chapter_range=words_per_chapter_range
    )

    # 根据目标字数计算 max_tokens，避免截断
    max_tokens = _calc_max_tokens(target_words_for_tokens)

    # 调用 LLM 流式生成内容（框架自动捕获 on_chat_model_stream）
    content = ""
    async for chunk in llm.chat_stream(
        [{"role": "user", "content": prompt}],
        max_tokens=max_tokens
    ):
        content += chunk

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
