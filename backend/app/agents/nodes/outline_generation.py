"""Outline generation nodes"""

import re
from typing import Dict, Any, AsyncIterator

from app.agents.state import NovelState, STAGE_OUTLINE_CONFIRMING
from app.agents.prompts import GENERATE_OUTLINE_PROMPT
from app.services.llm import LLMService


def parse_outline(response: str) -> Dict[str, Any]:
    """Parse outline from response"""
    outline = {
        "title": "",
        "summary": "",
        "plot_points": []
    }

    # Extract title - support multiple formats:
    # - "标题：xxx"
    # - "## 标题：xxx"
    # - "**标题**：xxx" (Markdown bold)
    # - "# 小说大纲：xxx"
    # - "# 《xxx》" (AI directly returns title in 《》)
    title_match = re.search(r"(?:##\s*)?(?:\*\*)?标题(?:\*\*)?[：:]\s*(.+?)(?:\n|$)", response)
    if not title_match:
        # Try format: "# 小说大纲：xxx"
        title_match = re.search(r"#\s*小说大纲[：:]\s*(.+?)(?:\n|$)", response)
    if not title_match:
        # Try format: "# 《xxx》" (title directly in brackets)
        title_match = re.search(r"#\s*《(.+?)》", response)
    if title_match:
        # Clean up the title - remove surrounding brackets if present
        title = title_match.group(1).strip()
        if title.startswith("《") and title.endswith("》"):
            title = title[1:-1]
        outline["title"] = title

    # Extract summary - support multiple formats:
    # - "概述：内容"
    # - "**概述**：内容" (Markdown bold)
    # - "## 概述\n\n内容"
    # - "概述\n内容"
    # First try: 概述 followed by colon (standard format)
    summary_match = re.search(r"(?:##\s*)?(?:\*\*)?概述(?:\*\*)?[：:]\s*(.+?)(?=(?:##\s*)?(?:\*\*)?(?:主要情节节点|情节节点)|---|\n\d+\.)", response, re.DOTALL)
    if not summary_match:
        # Second try: 概述 followed by newlines then content (Markdown format)
        summary_match = re.search(r"(?:##\s*)?(?:\*\*)?概述(?:\*\*)?\s*\n+(.+?)(?=(?:##\s*)?(?:\*\*)?(?:主要情节节点|情节节点)|$)", response, re.DOTALL)
    if summary_match:
        outline["summary"] = summary_match.group(1).strip()

    # Extract plot points - support numbered list format (1. **xxx** or 1. xxx)
    plot_matches = re.findall(r"\d+\.\s*(?:\*\*)?(.+?)(?:\*\*)?\s*\n", response, re.DOTALL)
    if plot_matches:
        outline["plot_points"] = [p.strip() for p in plot_matches]
    else:
        # Fallback: try to find all numbered items
        plot_matches = re.findall(r"\d+\.\s*(.+?)(?=\n\d+\.|$)", response, re.DOTALL)
        outline["plot_points"] = [p.strip() for p in plot_matches]

    return outline


def parse_chapter_count(response: str) -> int:
    """Parse suggested chapter count from response"""
    match = re.search(r"建议章节数[：:]\s*(\d+)", response)
    if match:
        return int(match.group(1))
    return 10  # Default


async def generate_outline_node(state: NovelState, llm: LLMService) -> NovelState:
    """Generate outline from inspiration template"""

    # 获取灵感模板
    inspiration_template = state.get("inspiration_template", "")
    collected_info = state.get("collected_info", {})

    # 计算章节数（基于目标字数）
    chapter_count = 40  # 默认值
    target_words = collected_info.get("targetWords", 100000)
    if isinstance(target_words, int):
        # 根据目标字数计算章节数
        # 超短篇: 1万-5万字 -> 5-15章
        # 短篇: 5万-20万字 -> 15-40章
        # 中篇: 20万-50万字 -> 40-80章
        # 长篇: 50万-100万字 -> 80-150章
        # 超长篇: 100万字以上 -> 150+章
        if target_words <= 50000:
            chapter_count = max(5, int(target_words / 3500))  # 约3500字/章
        elif target_words <= 200000:
            chapter_count = max(15, int(target_words / 4000))
        elif target_words <= 500000:
            chapter_count = max(40, int(target_words / 5000))
        elif target_words <= 1000000:
            chapter_count = max(80, int(target_words / 6000))
        else:
            chapter_count = max(150, int(target_words / 7000))

    # 如果没有灵感模板，从 collected_info 生成基本信息
    if not inspiration_template:
        novel_type = collected_info.get("novelType", "未指定")
        core_theme = collected_info.get("coreTheme", "未指定")
        protagonist = collected_info.get("customProtagonist") or collected_info.get("protagonist", "未指定")
        world_setting = collected_info.get("customWorldSetting") or collected_info.get("worldSetting", "未指定")
        style = collected_info.get("stylePreference", "未指定")
        target_words_display = f"{target_words}字" if isinstance(target_words, int) else "未指定"

        inspiration_template = f"""# 小说创作灵感

## 基本信息
- **小说类型**：{novel_type}
- **核心主题**：{core_theme}
- **目标字数**：{target_words_display}

## 世界设定
- **世界观**：{world_setting}

## 人物设定
- **主角**：{protagonist}

## 风格
- **风格偏好**：{style}
"""

    prompt = GENERATE_OUTLINE_PROMPT.format(
        inspiration_template=inspiration_template,
        chapter_count=chapter_count
    )

    response = await llm.chat([{"role": "user", "content": prompt}])

    outline = parse_outline(response)

    new_state: NovelState = {
        **state,
        "outline_title": outline["title"],
        "outline_summary": outline["summary"],
        "outline_plot_points": outline["plot_points"],
        "chapter_count_suggested": chapter_count,
        "stage": STAGE_OUTLINE_CONFIRMING,
        "last_assistant_message": response,
    }

    return new_state


def prepare_outline_prompt(state: NovelState) -> tuple[str, int]:
    """Prepare outline generation prompt and chapter count from state"""
    inspiration_template = state.get("inspiration_template", "")
    collected_info = state.get("collected_info", {})

    # 计算章节数（基于目标字数）
    chapter_count = 40  # 默认值
    target_words = collected_info.get("targetWords", 100000)
    if isinstance(target_words, int):
        if target_words <= 50000:
            chapter_count = max(5, int(target_words / 3500))
        elif target_words <= 200000:
            chapter_count = max(15, int(target_words / 4000))
        elif target_words <= 500000:
            chapter_count = max(40, int(target_words / 5000))
        elif target_words <= 1000000:
            chapter_count = max(80, int(target_words / 6000))
        else:
            chapter_count = max(150, int(target_words / 7000))

    # 如果没有灵感模板，从 collected_info 生成基本信息
    if not inspiration_template:
        novel_type = collected_info.get("novelType", "未指定")
        core_theme = collected_info.get("coreTheme", "未指定")
        protagonist = collected_info.get("customProtagonist") or collected_info.get("protagonist", "未指定")
        world_setting = collected_info.get("customWorldSetting") or collected_info.get("worldSetting", "未指定")
        style = collected_info.get("stylePreference", "未指定")
        target_words_display = f"{target_words}字" if isinstance(target_words, int) else "未指定"

        inspiration_template = f"""# 小说创作灵感

## 基本信息
- **小说类型**：{novel_type}
- **核心主题**：{core_theme}
- **目标字数**：{target_words_display}

## 世界设定
- **世界观**：{world_setting}

## 人物设定
- **主角**：{protagonist}

## 风格
- **风格偏好**：{style}
"""

    prompt = GENERATE_OUTLINE_PROMPT.format(
        inspiration_template=inspiration_template,
        chapter_count=chapter_count
    )

    return prompt, chapter_count


async def generate_outline_stream(
    state: NovelState,
    llm: LLMService
) -> AsyncIterator[str]:
    """Generate outline with streaming"""
    prompt, _ = prepare_outline_prompt(state)

    async for chunk in llm.chat_stream([{"role": "user", "content": prompt}]):
        yield chunk