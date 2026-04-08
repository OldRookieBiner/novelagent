"""Outline generation nodes"""

import re
from typing import Dict, Any

from app.agents.state import NovelState, STAGE_OUTLINE_CONFIRMING, STAGE_CHAPTER_COUNT_SUGGESTING
from app.agents.prompts import (
    GENERATE_OUTLINE_PROMPT,
    SUGGEST_CHAPTER_COUNT_PROMPT
)
from app.services.llm import LLMService


def parse_outline(response: str) -> Dict[str, Any]:
    """Parse outline from response"""
    outline = {
        "title": "",
        "summary": "",
        "plot_points": []
    }

    # Extract title
    title_match = re.search(r"标题[：:]\s*(.+)", response)
    if title_match:
        outline["title"] = title_match.group(1).strip()

    # Extract summary
    summary_match = re.search(r"概述[：:]\s*(.+?)(?=主要情节节点|情节节点|$)", response, re.DOTALL)
    if summary_match:
        outline["summary"] = summary_match.group(1).strip()

    # Extract plot points
    plot_matches = re.findall(r"\d+\.\s*(.+?)(?=\d+\.|$)", response, re.DOTALL)
    outline["plot_points"] = [p.strip() for p in plot_matches]

    return outline


def parse_chapter_count(response: str) -> int:
    """Parse suggested chapter count from response"""
    match = re.search(r"建议章节数[：:]\s*(\d+)", response)
    if match:
        return int(match.group(1))
    return 10  # Default


async def generate_outline_node(state: NovelState, llm: LLMService) -> NovelState:
    """Generate outline from collected info"""

    info = state.get("collected_info", {})

    prompt = GENERATE_OUTLINE_PROMPT.format(
        genre=info.get("genre", "未指定"),
        theme=info.get("theme", "未指定"),
        main_characters=info.get("main_characters", "未指定"),
        world_setting=info.get("world_setting", "未指定"),
        style_preference=info.get("style_preference", "未指定")
    )

    response = await llm.chat([{"role": "user", "content": prompt}])

    outline = parse_outline(response)

    new_state: NovelState = {
        **state,
        "outline_title": outline["title"],
        "outline_summary": outline["summary"],
        "outline_plot_points": outline["plot_points"],
        "stage": STAGE_OUTLINE_CONFIRMING,
        "last_assistant_message": response,
    }

    return new_state


async def suggest_chapter_count_node(state: NovelState, llm: LLMService) -> NovelState:
    """Suggest chapter count"""

    outline = f"标题：{state.get('outline_title', '')}\n概述：{state.get('outline_summary', '')}"
    plot_points = state.get("outline_plot_points", [])
    if plot_points:
        outline += "\n主要情节节点：\n" + "\n".join([f"{i+1}. {p}" for i, p in enumerate(plot_points)])

    prompt = SUGGEST_CHAPTER_COUNT_PROMPT.format(outline=outline)

    response = await llm.chat([{"role": "user", "content": prompt}])

    chapter_count = parse_chapter_count(response)

    new_state: NovelState = {
        **state,
        "chapter_count_suggested": chapter_count,
        "stage": STAGE_CHAPTER_COUNT_CONFIRMING,
        "last_assistant_message": response,
    }

    return new_state