"""Chapter generation nodes"""

import json
import logging
import re
from typing import AsyncIterator

from app.agents.state import NovelState, STAGE_CHAPTER_OUTLINES, STAGE_WRITING
from app.agents.constants import NODE_TEMPERATURES
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
    get_prompt_template,
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

    # Extract scene（截断至 500 字符，匹配 DB 列 String(500)）
    scene_match = re.search(r"场景[：:]\s*(.+)", response)
    if scene_match:
        chapter["scene"] = scene_match.group(1).strip()[:500]

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
    previous_chapters: list[dict] = None
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

    # 从 state 获取预加载的 prompts（统一使用 get_prompts_from_state）
    system_template, user_template = get_prompts_from_state(state, "chapter_outline_generation")
    prompt_template = get_prompt_template(system_template, user_template)

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

    response = ""
    async for chunk in llm.chat_stream([{"role": "user", "content": prompt}], temperature=NODE_TEMPERATURES["chapter_outline_generation"]):
        response += chunk

    return parse_single_chapter_outline(response, chapter_number, min_words)


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


def _get_chapter_content_prompts(state: NovelState) -> tuple[str, str]:
    """获取章节正文生成的 system/user 模板"""
    return get_prompts_from_state(state, "chapter_content_generation")


def _select_style_exemplars(chapter_outline: dict) -> str:
    """根据章节大纲内容动态选择 2-3 条最相关的风格示例"""
    from app.agents.constants import STYLE_EXEMPLARS, STYLE_EXEMPLAR_RULES, STYLE_EXEMPLAR_DEFAULT

    selected_categories = []
    chapter_number = chapter_outline.get("chapter_number", 1)

    if chapter_number == 1:
        selected_categories = ["opening", "dialogue"]
    else:
        for field, keywords, categories in STYLE_EXEMPLAR_RULES:
            field_text = chapter_outline.get(field, "")
            if any(kw in field_text for kw in keywords):
                selected_categories = categories
                break
        if not selected_categories:
            selected_categories = STYLE_EXEMPLAR_DEFAULT

    parts = []
    for cat in selected_categories:
        exemplars = STYLE_EXEMPLARS.get(cat, [])
        if exemplars:
            label = {"action": "动作", "dialogue": "对话", "emotion": "情感", "environment": "环境", "opening": "开篇"}.get(cat, cat)
            parts.append(f"【{label}】{exemplars[0]}")

    return "\n\n".join(parts)


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
    # 优先使用用户选择的策略，否则根据目标字数自动选择
    strategy_name = info.get("contextStrategy")
    strategy = get_context_strategy(target_words, strategy_name)
    previous_context = strategy.build_previous_context(written_chapters, chapter_number, state.get("chapter_outlines", []))

    # 获取 system/user 模板
    system_template, user_template = _get_chapter_content_prompts(state)

    # 动态选择正面风格示例
    style_exemplars = _select_style_exemplars(chapter_outline)

    # 格式化 system message（角色定位 + 规则 + 上下文 + 人物 + 世界观）
    messages = []
    if system_template:
        system_content = system_template.format(
            previous_context=previous_context,
            main_characters=combined_characters_str,
            world_setting=world_str,
            style_exemplars=style_exemplars,
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

    async for chunk in llm.chat_stream(messages, max_tokens=max_tokens, temperature=NODE_TEMPERATURES["chapter_content_draft"]):
        yield chunk


async def _self_check_chapter(llm: LLMService, draft_content: str) -> dict:
    """对章节初稿做段落级自检

    调用自检 Prompt，要求 LLM 以 JSON 格式返回有问题的段落列表。
    解析 JSON 时兼容代码块包裹和裸 JSON 两种格式。

    Args:
        llm: LLM 服务实例
        draft_content: 章节初稿内容

    Returns:
        解析后的字典，格式为 {"paragraphs": [{"index": int, "issue": str, "suggestion": str}]}
    """
    from app.agents.prompts import DEFAULT_PROMPTS

    prompt_template = DEFAULT_PROMPTS.get("chapter_self_check", "")
    prompt = prompt_template.format(chapter_content=draft_content)

    response = ""
    async for chunk in llm.chat_stream(
        [{"role": "user", "content": prompt}],
        temperature=NODE_TEMPERATURES["chapter_content_self_check"],
        max_tokens=2048,
    ):
        response += chunk

    # 解析 JSON 响应（兼容代码块包裹和裸 JSON）
    try:
        code_match = re.search(r'```(?:json)?\s*(\{[\s\S]*?\})\s*```', response)
        if code_match:
            data = json.loads(code_match.group(1))
        else:
            brace_start = response.find('{')
            if brace_start != -1:
                depth = 0
                for i in range(brace_start, len(response)):
                    if response[i] == '{':
                        depth += 1
                    elif response[i] == '}':
                        depth -= 1
                        if depth == 0:
                            data = json.loads(response[brace_start:i + 1])
                            break
                else:
                    data = {"paragraphs": []}
            else:
                data = {"paragraphs": []}
        return data
    except (json.JSONDecodeError, UnboundLocalError):
        return {"paragraphs": []}


async def _refine_chapter_stream(
    llm: LLMService,
    draft_content: str,
    check_result: dict,
    min_words: int,
) -> AsyncIterator[str]:
    """基于自检结果精修章节（流式版本）

    仅当自检发现问题段落时调用。将初稿和质检结果一起输入精修 Prompt，
    流式输出修改后的完整章节正文。

    Args:
        llm: LLM 服务实例
        draft_content: 章节初稿内容
        check_result: 自检结果，格式为 {"paragraphs": [...]}
        min_words: 每章最低字数，用于计算 max_tokens

    Yields:
        精修后的文本片段
    """
    from app.agents.prompts import DEFAULT_PROMPTS

    paragraphs = check_result.get("paragraphs", [])
    if not paragraphs:
        yield draft_content
        return

    prompt_template = DEFAULT_PROMPTS.get("chapter_refine", "")
    check_result_str = json.dumps(check_result, ensure_ascii=False, indent=2)
    prompt = prompt_template.format(
        check_result=check_result_str,
        draft_content=draft_content,
    )

    async for chunk in llm.chat_stream(
        [{"role": "user", "content": prompt}],
        temperature=NODE_TEMPERATURES["chapter_content_refine"],
        max_tokens=_calc_max_tokens(min_words * 2),
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
    LangGraph 兼容的章节内容生成节点（Draft→SelfCheck→Refine）

    此节点执行三阶段流程：
    1. Draft：静默生成章节初稿（不流式输出）
    2. SelfCheck：对初稿做段落级质检（静默）
    3. Refine：如果自检发现问题，精修并流式输出；否则直接流式输出初稿

    通过 refinement_enabled 字段控制是否启用自检-精修流程。

    签名：(state: NovelState) -> NovelState
    """
    from langgraph.config import get_stream_writer

    writer = get_stream_writer()

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

    # 是否启用自检-精修
    refinement_enabled = state.get("refinement_enabled", True)

    # ===== Phase 1: Draft（静默生成初稿）=====
    draft_content = ""
    async for chunk in llm.chat_stream(
        messages, max_tokens=max_tokens,
        temperature=NODE_TEMPERATURES["chapter_content_draft"],
    ):
        draft_content += chunk

    # 后处理：移除结尾的纯数字
    draft_content = clean_chapter_content(draft_content)

    # ===== Phase 2 & 3: SelfCheck + Refine =====
    if refinement_enabled and draft_content:
        # 自检：对初稿做段落级质检
        check_result = await _self_check_chapter(llm, draft_content)
        paragraphs = check_result.get("paragraphs", [])

        logger.info(f"SelfCheck found {len(paragraphs)} issues for chapter {current_chapter}")

        if paragraphs:
            # 有问题 → 精修并流式输出
            final_content = ""
            async for chunk in _refine_chapter_stream(
                llm, draft_content, check_result, min_words
            ):
                final_content += chunk
                writer({
                    "type": "chapter_content_chunk",
                    "content": chunk,
                    "chapter_number": current_chapter,
                })
            # 精修结果后处理；如果精修失败则回退到初稿
            final_content = clean_chapter_content(final_content) if final_content else draft_content
        else:
            # 无问题 → 流式输出初稿
            final_content = draft_content
            writer({
                "type": "chapter_content_chunk",
                "content": final_content,
                "chapter_number": current_chapter,
            })
    else:
        # 未启用精修或初稿为空 → 流式输出初稿
        final_content = draft_content
        writer({
            "type": "chapter_content_chunk",
            "content": final_content,
            "chapter_number": current_chapter,
        })

    # 计算字数
    word_count = len(final_content)

    # 创建新章节
    new_chapter = {
        "chapter_number": current_chapter,
        "title": chapter_outline.get("title", ""),
        "content": final_content,
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
