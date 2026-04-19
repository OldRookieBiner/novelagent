"""Chapter generation nodes"""

import re
from typing import Dict, Any, AsyncIterator

from app.agents.state import NovelState, STAGE_CHAPTER_OUTLINES_CONFIRMING, STAGE_CHAPTER_WRITING
from app.agents.prompts import (
    GENERATE_SINGLE_CHAPTER_OUTLINE_PROMPT,
    GENERATE_CHAPTER_CONTENT_PROMPT,
    REVIEW_CHAPTER_PROMPT
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
    """Parse a single chapter outline from response"""
    chapter = {
        "chapter_number": chapter_number,
        "title": "",
        "scene": "",
        "characters": "",
        "plot": "",
        "conflict": "",
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
    plot_match = re.search(r"情节[：:]\s*(.+?)(?=冲突|结局|预计字数|$)", response, re.DOTALL)
    if plot_match:
        chapter["plot"] = plot_match.group(1).strip()

    # Extract conflict
    conflict_match = re.search(r"冲突[：:]\s*(.+?)(?=结局|预计字数|$)", response, re.DOTALL)
    if conflict_match:
        chapter["conflict"] = conflict_match.group(1).strip()

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
            "ending": "",
            "target_words": 3000
        }

        # Extract title from first line if present (e.g., "初入仙门\n场景：...")
        first_line = content.split('\n')[0].strip() if content else ""
        if first_line and not first_line.startswith(('场景', '人物', '情节', '冲突', '结局', '预计字数', '章节名')):
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

        plot_match = re.search(r"情节[：:]\s*(.+?)(?=冲突|结局|预计字数|$)", content, re.DOTALL)
        if plot_match:
            chapter["plot"] = plot_match.group(1).strip()

        conflict_match = re.search(r"冲突[：:]\s*(.+?)(?=结局|预计字数|$)", content, re.DOTALL)
        if conflict_match:
            chapter["conflict"] = conflict_match.group(1).strip()

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

    chapter_count = state.get("chapter_count_suggested", 10)

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

    chapter_count = state.get("chapter_count_suggested", 10)
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

    chapter_count = state.get("chapter_count_suggested", 10)
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
        "stage": STAGE_CHAPTER_OUTLINES_CONFIRMING,
    }

    return new_state


async def generate_chapter_content_stream(
    state: NovelState,
    chapter_outline: dict,
    llm: LLMService
) -> AsyncIterator[str]:
    """Generate chapter content with streaming"""

    info = state.get("collected_info", {})

    # Format chapter outline
    outline_str = f"""
第{chapter_outline['chapter_number']}章：{chapter_outline['title']}
场景：{chapter_outline['scene']}
人物：{chapter_outline['characters']}
情节：{chapter_outline['plot']}
冲突：{chapter_outline['conflict']}
结局：{chapter_outline['ending']}
"""

    prompt = GENERATE_CHAPTER_CONTENT_PROMPT.format(
        chapter_outline=outline_str,
        previous_ending="",  # TODO: Get from previous chapter
        genre=info.get("genre", "未指定"),
        main_characters=info.get("main_characters", "未指定"),
        world_setting=info.get("world_setting", "未指定"),
        style_preference=info.get("style_preference", "未指定")
    )

    async for chunk in llm.chat_stream([{"role": "user", "content": prompt}]):
        yield chunk


async def review_chapter_node(
    state: NovelState,
    chapter_content: str,
    chapter_outline: dict,
    llm: LLMService,
    strictness: str = "standard"
) -> Dict[str, Any]:
    """Review chapter content"""

    info = state.get("collected_info", {})

    outline_str = f"第{chapter_outline['chapter_number']}章：{chapter_outline['title']}\n情节：{chapter_outline['plot']}"

    prompt = REVIEW_CHAPTER_PROMPT.format(
        strictness=strictness,
        chapter_outline=outline_str,
        chapter_content=chapter_content,
        genre=info.get("genre", "未指定"),
        main_characters=info.get("main_characters", "未指定"),
        style_preference=info.get("style_preference", "未指定")
    )

    response = await llm.chat([{"role": "user", "content": prompt}])

    # Parse result
    passed = "【审核结果】通过" in response

    # Extract issues
    issues = []
    issues_match = re.search(r"【问题列表】(.+?)【修改建议】", response, re.DOTALL)
    if issues_match:
        issues_text = issues_match.group(1)
        issues = [i.strip() for i in re.findall(r"\d+\.\s*(.+)", issues_text) if i.strip()]

    # Extract suggestions
    suggestions = ""
    suggestions_match = re.search(r"【修改建议】(.+?)(?=---|$)", response, re.DOTALL)
    if suggestions_match:
        suggestions = suggestions_match.group(1).strip()

    return {
        "passed": passed,
        "issues": issues,
        "feedback": response,
        "suggestions": suggestions
    }
