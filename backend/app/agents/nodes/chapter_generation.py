"""Chapter generation nodes"""

import logging
import re
from typing import AsyncIterator

from app.agents.state import NovelState, STAGE_CHAPTER_OUTLINES, STAGE_WRITING
from app.services.llm import LLMService
from app.utils.llm import get_llm_from_state_async
from app.agents.context_strategy import get_context_strategy
from app.agents.nodes.utils import (
    _format_chapter_outline_str,
    format_characters_info,
    format_relations_info,
    format_evolution_info,
    format_world_setting,
    get_prompts_from_state,
    parse_words_per_chapter,
)

logger = logging.getLogger(__name__)


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
    min_words: int | None = None
) -> dict:
    """解析单章节大纲（增强版）

    Args:
        response: AI 返回的章节大纲文本
        chapter_number: 章节号
        min_words: 每章最低字数，用于保底 target_words

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

    # 保底 target_words 不低于用户设定的最低字数
    if min_words and chapter["target_words"] < min_words:
        chapter["target_words"] = min_words

    return chapter


async def generate_single_chapter_outline(
    state: NovelState,
    chapter_number: int,
    llm: LLMService,
    previous_chapters: list[dict] = None,
    arc_info: str = "",
) -> dict:
    """Generate a single chapter outline"""

    outline = f"标题：{state.get('outline_title', '')}\n概述：{state.get('outline_summary', '')}"
    plot_points = state.get("outline_plot_points", [])
    plot_points_str = "\n".join([f"{i+1}. {p}" for i, p in enumerate(plot_points)]) if plot_points else "无"

    chapter_count = state.get("chapter_count", 10)

    # 获取每章最低字数
    collected_info = state.get("collected_info", {})
    min_words, _ = parse_words_per_chapter(collected_info)

    # 构建已生成章节大纲的上下文（全部章节，完整字段）
    previous_info = ""
    if previous_chapters and len(previous_chapters) > 0:
        parts = []
        for c in previous_chapters:
            part = f"第{c['chapter_number']}章《{c.get('title', '')}》\n"
            part += f"场景：{c.get('scene', '')}\n"
            part += f"人物：{c.get('characters', '')}\n"
            part += f"情节：{c.get('plot', '')}\n"
            part += f"冲突：{c.get('conflict', '')}\n"
            part += f"转折：{c.get('turning_point', '无')}\n"
            part += f"钩子：{c.get('hook', '')}\n"
            part += f"衔接：{c.get('transition', '')}\n"
            part += f"结局：{c.get('ending', '')}"
            parts.append(part)
        previous_info = "已生成章节大纲：\n" + "\n\n".join(parts)

    # 格式化人物设定
    chars_str = format_characters_info(state)

    # 格式化人物关系和演变计划
    relations_str = format_relations_info(state, chapter_number)
    evolution_str, _ = format_evolution_info(state, chapter_number)
    combined_chars = chars_str + relations_str + evolution_str

    # 格式化世界观（使用共享工具函数）
    world_str = format_world_setting(state)

    # 获取情感曲线
    emotional_curve = state.get("outline_emotional_curve", "") or "未提供"

    # 从 state 获取预加载的 prompts（LangGraph 合规）
    prompts = state.get("_prompts", {})
    if prompts and "chapter_outline_generation" in prompts:
        prompt_template = prompts["chapter_outline_generation"]
    else:
        from app.agents.prompts import DEFAULT_PROMPTS
        prompt_template = DEFAULT_PROMPTS.get("chapter_outline_generation", "")

    prompt = prompt_template.format(
        outline=outline,
        plot_points=plot_points_str,
        characters=combined_chars,
        world_setting=world_str,
        emotional_curve=emotional_curve,
        chapter_count=chapter_count,
        chapter_number=chapter_number,
        previous_chapters_info=previous_info,
        min_words=min_words,
    )

    # 长篇模式：追加弧归属信息
    if arc_info:
        prompt += f"\n\n{arc_info}"

    response = ""
    async for chunk in llm.chat_stream([{"role": "user", "content": prompt}]):
        response += chunk

    return parse_single_chapter_outline(response, chapter_number, min_words)


async def generate_chapter_outlines_stream(
    state: NovelState,
    llm: LLMService
) -> AsyncIterator[dict]:
    """Generate chapter outlines one by one with streaming progress"""

    chapter_count = state.get("chapter_count", 10)
    generated_chapters = []

    # 长篇模式：构建弧归属分配表
    arc_assignments = []  # [(start_chapter, end_chapter, volume_number, arc_number, arc_title, arc_summary)]
    arcs = state.get("arcs", [])
    if state.get("novel_length") == "long" and arcs:
        sorted_arcs = sorted(arcs, key=lambda a: (a.get("volume_number", 1), a.get("arc_number", 0)))
        cumulative = 0
        for arc in sorted_arcs:
            start = cumulative + 1
            end = cumulative + arc.get("chapter_count", 0)
            arc_assignments.append((
                start, end,
                arc.get("volume_number", 1),
                arc.get("arc_number", 0),
                arc.get("title", ""),
                arc.get("summary", ""),
            ))
            cumulative = end

    for chapter_num in range(1, chapter_count + 1):
        # 构建弧归属信息和提示
        arc_info = ""
        for start, end, vol_num, arc_num, arc_title, arc_summary in arc_assignments:
            if start <= chapter_num <= end:
                pos_in_arc = chapter_num - start + 1
                parts = [f"当前弧：第{arc_num}弧《{arc_title}》，本章是本弧第{pos_in_arc}章"]
                if arc_summary:
                    parts.append(f"弧概要：{arc_summary}")
                arc_info = "\n".join(parts)
                break

        chapter_outline = await generate_single_chapter_outline(
            state,
            chapter_num,
            llm,
            generated_chapters,
            arc_info=arc_info,
        )

        # 长篇模式：在章节大纲中记录弧归属
        for start, end, vol_num, arc_num, _, _ in arc_assignments:
            if start <= chapter_num <= end:
                chapter_outline["volume_number"] = vol_num
                chapter_outline["arc_number"] = arc_num
                break

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

    # 长篇模式：构建弧归属分配表
    arc_assignments = []
    arcs = state.get("arcs", [])
    if state.get("novel_length") == "long" and arcs:
        sorted_arcs = sorted(arcs, key=lambda a: (a.get("volume_number", 1), a.get("arc_number", 0)))
        cumulative = 0
        for arc in sorted_arcs:
            start = cumulative + 1
            end = cumulative + arc.get("chapter_count", 0)
            arc_assignments.append((
                start, end,
                arc.get("volume_number", 1),
                arc.get("arc_number", 0),
                arc.get("title", ""),
                arc.get("summary", ""),
            ))
            cumulative = end

    for chapter_num in range(1, chapter_count + 1):
        # 构建弧归属信息
        arc_info = ""
        for start, end, vol_num, arc_num, arc_title, arc_summary in arc_assignments:
            if start <= chapter_num <= end:
                pos_in_arc = chapter_num - start + 1
                parts = [f"当前弧：第{arc_num}弧《{arc_title}》，本章是本弧第{pos_in_arc}章"]
                if arc_summary:
                    parts.append(f"弧概要：{arc_summary}")
                arc_info = "\n".join(parts)
                break

        chapter_outline = await generate_single_chapter_outline(
            state,
            chapter_num,
            llm,
            generated_chapters,
            arc_info=arc_info,
        )

        # 长篇模式：在章节大纲中记录弧归属
        for start, end, vol_num, arc_num, _, _ in arc_assignments:
            if start <= chapter_num <= end:
                chapter_outline["volume_number"] = vol_num
                chapter_outline["arc_number"] = arc_num
                break

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


def _get_chapter_content_prompts(state: NovelState) -> tuple[str, str]:
    """获取章节正文生成的 system/user 模板"""
    return get_prompts_from_state(state, "chapter_content_generation")


def _build_chapter_content_messages(
    state: NovelState,
    chapter_outline: dict,
) -> list[dict]:
    """构建章节正文生成的 system/user 消息列表

    将角色定位、写作规则、禁用词、前文上下文、人物、世界观放入 system message，
    章节大纲、前章结尾、题材/字数/风格放入 user message。
    """
    info = state.get("collected_info", {})
    written_chapters = state.get("written_chapters", [])
    chapter_number = chapter_outline.get("chapter_number", 1)

    # 格式化章节大纲
    outline_str = _format_chapter_outline_str(chapter_outline)

    # 格式化人物设定、关系、演变
    chars_str = format_characters_info(state)
    relations_str = format_relations_info(state, chapter_number)
    evolution_str, _ = format_evolution_info(state, chapter_number)
    combined_characters_str = chars_str + relations_str + evolution_str

    # 格式化世界观
    world_str = format_world_setting(state)

    # 每章最低字数
    min_words, _ = parse_words_per_chapter(info)
    suggested_max = int(min_words * 1.5)

    # 前章结尾（用于 user message 中的衔接参考）
    previous_ending = ""
    if written_chapters:
        for ch in written_chapters:
            if ch.get("chapter_number") == chapter_number - 1:
                ch_content = ch.get("content", "")
                previous_ending = ch_content[-500:] if len(ch_content) > 500 else ch_content
                break

    # 上下文策略：构建前文上下文
    target_words = info.get("targetWords", 100000)
    if isinstance(target_words, str):
        target_words = int(target_words)
    # 优先使用用户选择的策略
    # 回退1：长篇自动选 summary 策略
    strategy_name = info.get("contextStrategy")
    if not strategy_name and state.get("novel_length") == "long":
        strategy_name = "summary"
    # 回退2：长篇但无 arcs 数据时降级为 hybrid（避免 summary 策略在无 arcs 时丢失大量远章上下文）
    if strategy_name == "summary" and not state.get("arcs"):
        logger.warning("Summary strategy selected but no arcs data, falling back to hybrid")
        strategy_name = "hybrid"
    strategy = get_context_strategy(target_words, strategy_name)
    previous_context = strategy.build_previous_context(
        written_chapters, chapter_number,
        chapter_outlines=state.get("chapter_outlines", []),
        arcs=state.get("arcs", []),
        chapter_summaries=state.get("chapter_summaries", []),
    )

    # 获取 system/user 模板
    system_template, user_template = _get_chapter_content_prompts(state)

    # 格式化 system message（角色定位 + 规则 + 上下文 + 人物 + 世界观）
    messages = []
    if system_template:
        system_content = system_template.format(
            previous_context=previous_context,
            main_characters=combined_characters_str,
            world_setting=world_str,
        )
        messages.append({"role": "system", "content": system_content})

    # 格式化 user message（具体任务输入）
    user_content = user_template.format(
        chapter_outline=outline_str,
        previous_ending=previous_ending,
        genre=info.get("novelType", "未指定"),
        min_words=min_words,
        suggested_max=suggested_max,
        style_preference=info.get("stylePreference", "未指定"),
    )
    messages.append({"role": "user", "content": user_content})

    return messages


async def generate_chapter_content_stream(
    state: NovelState,
    chapter_outline: dict,
    llm: LLMService
) -> AsyncIterator[str]:
    """生成章节内容（流式，使用 system/user 双层消息 + 上下文策略）"""

    info = state.get("collected_info", {})
    min_words, _ = parse_words_per_chapter(info)

    # 构建 system/user 消息
    messages = _build_chapter_content_messages(state, chapter_outline)

    # 根据最低字数的 2 倍计算 max_tokens，确保不截断
    max_tokens = _calc_max_tokens(min_words * 2)

    async for chunk in llm.chat_stream(messages, max_tokens=max_tokens):
        yield chunk


# ==================== 弧式章节大纲生成 ====================

def _build_chapter_outline_prompt(
    state: NovelState,
    chapter_number: int,
    previous_chapters: list[dict],
    arc_info: str,
    min_words: int,
) -> str:
    """构建章节大纲生成的 prompt 文本

    从 generate_single_chapter_outline 中提取的 prompt 构建逻辑，
    不包含 LLM 调用，只返回 prompt 字符串。
    """
    outline = f"标题：{state.get('outline_title', '')}\n概述：{state.get('outline_summary', '')}"
    plot_points = state.get("outline_plot_points", [])
    plot_points_str = "\n".join([f"{i+1}. {p}" for i, p in enumerate(plot_points)]) if plot_points else "无"

    chapter_count = state.get("chapter_count", 10)

    # 构建已生成章节大纲的上下文
    previous_info = ""
    if previous_chapters and len(previous_chapters) > 0:
        parts = []
        for c in previous_chapters:
            part = f"第{c['chapter_number']}章《{c.get('title', '')}》\n"
            part += f"场景：{c.get('scene', '')}\n"
            part += f"人物：{c.get('characters', '')}\n"
            part += f"情节：{c.get('plot', '')}\n"
            part += f"冲突：{c.get('conflict', '')}\n"
            part += f"转折：{c.get('turning_point', '无')}\n"
            part += f"钩子：{c.get('hook', '')}\n"
            part += f"衔接：{c.get('transition', '')}\n"
            part += f"结局：{c.get('ending', '')}"
            parts.append(part)
        previous_info = "已生成章节大纲：\n" + "\n\n".join(parts)

    # 格式化人物设定
    chars_str = format_characters_info(state)
    relations_str = format_relations_info(state, chapter_number)
    evolution_str, _ = format_evolution_info(state, chapter_number)
    combined_chars = chars_str + relations_str + evolution_str

    # 格式化世界观
    world_str = format_world_setting(state)

    # 情感曲线
    emotional_curve = state.get("outline_emotional_curve", "") or "未提供"

    # 获取 prompt 模板
    prompts = state.get("_prompts", {})
    if prompts and "chapter_outline_generation" in prompts:
        prompt_template = prompts["chapter_outline_generation"]
    else:
        from app.agents.prompts import DEFAULT_PROMPTS
        prompt_template = DEFAULT_PROMPTS.get("chapter_outline_generation", "")

    prompt = prompt_template.format(
        outline=outline,
        plot_points=plot_points_str,
        characters=combined_chars,
        world_setting=world_str,
        emotional_curve=emotional_curve,
        chapter_count=chapter_count,
        chapter_number=chapter_number,
        previous_chapters_info=previous_info,
        min_words=min_words,
    )

    # 长篇模式：追加弧归属信息
    if arc_info:
        prompt += f"\n\n{arc_info}"

    return prompt


async def _generate_chapter_outlines_by_arc(state: NovelState, llm: LLMService) -> dict:
    """长篇模式：为当前弧生成章节大纲

    通过 get_stream_writer() 发送结构化流式事件：
        chapter_outline_chunk: {content, chapter_number, arc_index} — 流式文本
        chapter_outline_progress: {chapter_number, total_in_arc, arc_index, chapter} — 单章完成

    每弧生成后暂停等待确认（waiting_for_confirmation=True）。
    """

    from langgraph.config import get_stream_writer

    writer = get_stream_writer()
    arcs = state.get("arcs", [])
    current_arc_index = state.get("current_arc_index", 0)

    if current_arc_index >= len(arcs):
        # 所有弧已完成
        return {
            "stage": STAGE_CHAPTER_OUTLINES,
            "waiting_for_confirmation": False,
        }

    arc = arcs[current_arc_index]
    chapter_count_in_arc = arc.get("chapter_count", 10)

    # 计算当前弧的起始章节号（前面弧的章节数之和 + 1）
    start_chapter = sum(a.get("chapter_count", 0) for a in arcs[:current_arc_index]) + 1

    # 获取已有章节大纲（前面弧的）作为上下文
    existing_outlines = list(state.get("chapter_outlines", []))
    previous_for_context = existing_outlines

    # 获取每章最低字数
    collected_info = state.get("collected_info", {})
    min_words, _ = parse_words_per_chapter(collected_info)

    generated_for_arc = []

    for i in range(chapter_count_in_arc):
        chapter_num = start_chapter + i
        pos_in_arc = i + 1

        # 构建弧归属信息
        arc_info_parts = [
            f"当前弧：第{arc.get('arc_number', 1)}弧《{arc.get('title', '')}》，",
            f"本章是本弧第{pos_in_arc}章（共{chapter_count_in_arc}章）",
        ]
        # 弧纲作为额外上下文
        arc_outline = arc.get("outline", "")
        if arc_outline:
            arc_info_parts.append(f"弧纲：{arc_outline}")
        arc_info = "\n".join(arc_info_parts)

        # 流式生成单章节大纲
        prompt = _build_chapter_outline_prompt(state, chapter_num, previous_for_context, arc_info, min_words)
        messages = [{"role": "user", "content": prompt}]

        response = ""
        async for chunk in llm.chat_stream(messages):
            response += chunk
            # 发送流式文本事件
            writer({
                "type": "chapter_outline_chunk",
                "content": chunk,
                "chapter_number": chapter_num,
                "arc_index": current_arc_index,
            })

        # 解析完整响应
        chapter_outline = parse_single_chapter_outline(response, chapter_num, min_words)
        chapter_outline["volume_number"] = arc.get("volume_number")
        chapter_outline["arc_number"] = arc.get("arc_number")
        generated_for_arc.append(chapter_outline)
        existing_outlines.append(chapter_outline)

        # 发送单章完成事件（含结构化数据）
        writer({
            "type": "chapter_outline_progress",
            "chapter_number": chapter_num,
            "total_in_arc": chapter_count_in_arc,
            "arc_index": current_arc_index,
            "chapter": chapter_outline,
        })

        # 更新上下文（后续章节参考已生成的章节）
        previous_for_context = existing_outlines

    # 当前弧完成，暂停等待确认
    return {
        "chapter_outlines": existing_outlines,
        "current_arc_index": current_arc_index + 1,
        "stage": STAGE_CHAPTER_OUTLINES,
        "waiting_for_confirmation": True,
        "confirmation_type": "arc_chapter_outlines",
    }


# ==================== LangGraph 兼容节点 ====================

async def chapter_outlines_node(state: NovelState) -> NovelState:
    """章节大纲生成节点

    短篇/中篇：全量生成（行为不变）
    长篇：按弧生成，每弧完成后暂停等待确认
    """

    llm = await get_llm_from_state_async(state)
    novel_length = state.get("novel_length", "short")
    arcs = state.get("arcs", [])

    # 短篇/中篇：全量生成（行为不变）
    if novel_length != "long" or not arcs:
        return await generate_chapter_outlines_node(state, llm)

    # 长篇：按弧生成
    return await _generate_chapter_outlines_by_arc(state, llm)


async def generate_chapter_content_node(state: NovelState) -> NovelState:
    """
    LangGraph 兼容的章节内容生成节点

    此节点：
    1. 获取当前章节号 (current_chapter)
    2. 获取章节大纲列表 (chapter_outlines)
    3. 构建 system/user 双层消息（含上下文策略）
    4. 调用 LLM 生成章节内容
    5. 返回更新后的状态，包含新章节

    签名：(state: NovelState) -> NovelState
    """
    # 获取 LLM 服务（异步）
    llm = await get_llm_from_state_async(state)

    # 获取当前章节信息
    current_chapter = state.get("current_chapter", 1)
    chapter_outlines = state.get("chapter_outlines", [])

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

    # 准备字数信息
    info = state.get("collected_info", {})
    min_words, _ = parse_words_per_chapter(info)

    # 构建 system/user 消息
    messages = _build_chapter_content_messages(state, chapter_outline)

    # 根据最低字数的 2 倍计算 max_tokens，确保不截断
    max_tokens = _calc_max_tokens(min_words * 2)

    # 调用 LLM 流式生成内容（框架自动捕获 on_chat_model_stream）
    content = ""
    async for chunk in llm.chat_stream(messages, max_tokens=max_tokens):
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
