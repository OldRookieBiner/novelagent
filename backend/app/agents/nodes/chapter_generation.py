"""Chapter generation nodes"""

import re
from typing import Dict, Any, AsyncIterator

from app.agents.state import NovelState, STAGE_CHAPTER_OUTLINES, STAGE_WRITING
from app.agents.prompts import (
    GENERATE_SINGLE_CHAPTER_OUTLINE_PROMPT,
    GENERATE_CHAPTER_CONTENT_PROMPT,
)
from app.services.llm import LLMService


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


def parse_chapter_outlines(response: str) -> list[dict]:
    """Parse chapter outlines from response (legacy, for batch parsing)"""
    chapters = []

    # Split by chapter markers - capture chapter number and title from header
    pattern = r"第(\d+)章[：:]\s*(.+?)(?=第\d+章|$)"
    matches = re.findall(pattern, response, re.DOTALL)

    for num, content in matches:
        chapter = {
            "chapter_number": int(num),
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

        # Extract title from first line if present (e.g., "初入仙门\n场景：...")
        first_line = content.split('\n')[0].strip() if content else ""
        if first_line and not first_line.startswith(('场景', '人物', '情节', '冲突', '转折', '钩子', '衔接', '结局', '预计字数', '章节名')):
            chapter["title"] = _clean_chapter_title(first_line)

        # Also check for explicit 章节名 field
        title_match = re.search(r"章节名[：:]\s*(.+)", content)
        if title_match:
            raw_title = title_match.group(1).strip()
            chapter["title"] = _clean_chapter_title(raw_title)

        scene_match = re.search(r"场景[：:]\s*(.+)", content)
        if scene_match:
            chapter["scene"] = scene_match.group(1).strip()

        characters_match = re.search(r"人物[：:]\s*(.+)", content)
        if characters_match:
            chapter["characters"] = characters_match.group(1).strip()

        plot_match = re.search(r"情节[：:]\s*(.+?)(?=冲突|转折|钩子|衔接|结局|预计字数|$)", content, re.DOTALL)
        if plot_match:
            chapter["plot"] = plot_match.group(1).strip()

        conflict_match = re.search(r"冲突[：:]\s*(.+?)(?=转折|钩子|衔接|结局|预计字数|$)", content, re.DOTALL)
        if conflict_match:
            chapter["conflict"] = conflict_match.group(1).strip()

        turning_match = re.search(r"转折[：:]\s*(.+?)(?=钩子|衔接|结局|预计字数|$)", content, re.DOTALL)
        if turning_match:
            chapter["turning_point"] = turning_match.group(1).strip()

        hook_match = re.search(r"钩子[：:]\s*(.+?)(?=衔接|结局|预计字数|$)", content, re.DOTALL)
        if hook_match:
            chapter["hook"] = hook_match.group(1).strip()

        transition_match = re.search(r"衔接[：:]\s*(.+?)(?=结局|预计字数|$)", content, re.DOTALL)
        if transition_match:
            chapter["transition"] = transition_match.group(1).strip()

        ending_match = re.search(r"结局[：:]\s*(.+?)(?=预计字数|$)", content, re.DOTALL)
        if ending_match:
            chapter["ending"] = ending_match.group(1).strip()

        words_match = re.search(r"预计字数[：:]\s*(\d+)", content)
        if words_match:
            chapter["target_words"] = int(words_match.group(1))

        chapters.append(chapter)

    return chapters


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
        previous_ending="",  # TODO: 从上一章获取
        genre=info.get("novelType", "未指定"),
        main_characters=chars_str,
        world_setting=world_str,
        style_preference=info.get("stylePreference", "未指定")
    )

    async for chunk in llm.chat_stream([{"role": "user", "content": prompt}]):
        yield chunk
