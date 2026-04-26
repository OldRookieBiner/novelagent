"""大纲生成节点"""

import re
from typing import Dict, Any, AsyncIterator

from app.agents.state import NovelState, STAGE_OUTLINE
from app.services.prompt_loader import get_system_prompt
from app.database import SessionLocal
from app.services.llm import LLMService
from app.utils.llm import get_llm_from_state_async

# 预编译正则表达式，提升性能
# 标题匹配模式：支持多种格式
RE_TITLE = re.compile(r"(?:##\s*)?(?:\*\*)?标题(?:\*\*)?[：:]\s*(.+?)(?:\n|$)")
RE_TITLE_OUTLINE = re.compile(r"#\s*小说大纲[：:]\s*(.+?)(?:\n|$)")
RE_TITLE_BRACKET = re.compile(r"#\s*《(.+?)》")

# 概述匹配模式
RE_SUMMARY = re.compile(r"(?:##\s*)?(?:\*\*)?概述(?:\*\*)?[：:]\s*(.+?)(?=(?:##\s*)?(?:\*\*)?(?:主要情节节点|情节节点)|---|\n\d+\.)", re.DOTALL)
RE_SUMMARY_MD = re.compile(r"(?:##\s*)?(?:\*\*)?概述(?:\*\*)?\s*\n+(.+?)(?=(?:##\s*)?(?:\*\*)?(?:主要情节节点|情节节点)|$)", re.DOTALL)

# 情节节点匹配模式
RE_PLOT_BOLD = re.compile(r"\d+\.\s*(?:\*\*)?(.+?)(?:\*\*)?\s*\n", re.DOTALL)
RE_PLOT_FALLBACK = re.compile(r"\d+\.\s*(.+?)(?=\n\d+\.|$)", re.DOTALL)

# 章节数匹配模式
RE_CHAPTER_COUNT = re.compile(r"建议章节数[：:]\s*(\d+)")

# ==================== 章节数计算常量 ====================
# 根据目标字数计算章节数的配置
# 参考：超短篇 1-5万字，短篇 5-20万字，中篇 20-50万字，长篇 50-100万字，超长篇 100万字+

# 默认章节数
DEFAULT_CHAPTER_COUNT = 40

# 字数阈值（字）
WORDS_THRESHOLD_SHORT = 50000      # 超短篇上限
WORDS_THRESHOLD_MEDIUM = 200000    # 短篇上限
WORDS_THRESHOLD_LONG = 500000      # 中篇上限
WORDS_THRESHOLD_VERY_LONG = 1000000  # 长篇上限

# 每章目标字数
WORDS_PER_CHAPTER_SHORT = 3500     # 超短篇：约3500字/章
WORDS_PER_CHAPTER_MEDIUM = 4000    # 短篇：约4000字/章
WORDS_PER_CHAPTER_LONG = 5000      # 中篇：约5000字/章
WORDS_PER_CHAPTER_VERY_LONG = 6000 # 长篇：约6000字/章
WORDS_PER_CHAPTER_EPIC = 7000      # 超长篇：约7000字/章

# 最小章节数
MIN_CHAPTERS_SHORT = 5
MIN_CHAPTERS_MEDIUM = 15
MIN_CHAPTERS_LONG = 40
MIN_CHAPTERS_VERY_LONG = 80
MIN_CHAPTERS_EPIC = 150


def parse_outline(response: str) -> Dict[str, Any]:
    """从 AI 响应中解析大纲（增强版）

    返回结构：
    {
        "title": str,
        "summary": str,
        "characters": [{"name", "role", "personality", "motivation", "arc"}],
        "world_setting": {"era", "core_rules", "power_system"},
        "plot_points": [{"order", "event", "conflict", "hook"}],
        "emotional_curve": str
    }
    """
    outline = {
        "title": "",
        "summary": "",
        "characters": [],
        "world_setting": {},
        "plot_points": [],
        "emotional_curve": ""
    }

    # 提取标题 - 支持多种格式
    title_match = RE_TITLE.search(response)
    if not title_match:
        title_match = RE_TITLE_OUTLINE.search(response)
    if not title_match:
        title_match = RE_TITLE_BRACKET.search(response)
    if title_match:
        title = title_match.group(1).strip()
        # 清理标题 - 移除书名号
        if title.startswith("《") and title.endswith("》"):
            title = title[1:-1]
        outline["title"] = title

    # 提取概述
    summary_match = RE_SUMMARY.search(response)
    if not summary_match:
        summary_match = RE_SUMMARY_MD.search(response)
    if summary_match:
        outline["summary"] = summary_match.group(1).strip()

    # 提取人物设定
    characters_section = re.search(r"人物设定[：:]\s*(.+?)(?=世界观|情节节点|情感曲线|---|$)", response, re.DOTALL)
    if characters_section:
        chars_text = characters_section.group(1)
        # 匹配 "- 主角：xxx" 或 "- 配角1：xxx"
        char_matches = re.findall(r"[-•]\s*(主角|配角\d*)[：:]\s*(.+?)(?=\n[-•]|\n\n|$)", chars_text, re.DOTALL)
        for role, content in char_matches:
            # 解析 "姓名 | 性格 | 动机 | 弧线" 格式
            parts = [p.strip() for p in content.split("|")]
            char = {
                "name": parts[0] if len(parts) > 0 else "",
                "role": role,
                "personality": parts[1] if len(parts) > 1 else "",
                "motivation": parts[2] if len(parts) > 2 else "",
                "arc": parts[3] if len(parts) > 3 else ""
            }
            outline["characters"].append(char)

    # 提取世界观
    world_section = re.search(r"世界观[：:]\s*(.+?)(?=情节节点|情感曲线|---|$)", response, re.DOTALL)
    if world_section:
        world_text = world_section.group(1)
        era_match = re.search(r"时代背景[：:]\s*(.+)", world_text)
        rules_match = re.search(r"核心设定[：:]\s*(.+)", world_text)
        power_match = re.search(r"力量体系[：:]\s*(.+)", world_text)

        outline["world_setting"] = {
            "era": era_match.group(1).strip() if era_match else "",
            "core_rules": rules_match.group(1).strip() if rules_match else "",
            "power_system": power_match.group(1).strip() if power_match else ""
        }

    # 提取情节节点（增强版，包含冲突和钩子）
    plot_section = re.search(r"情节节点[：:]\s*(.+?)(?=情感曲线|---|$)", response, re.DOTALL)
    if plot_section:
        plot_text = plot_section.group(1)
        # 匹配 "N. xxx | xxx | xxx" 格式
        plot_matches = re.findall(r"(\d+)\.\s*(.+?)(?=\n\d+\.|$)", plot_text, re.DOTALL)
        for num, content in plot_matches:
            parts = [p.strip() for p in content.split("|")]
            plot = {
                "order": int(num),
                "event": parts[0] if len(parts) > 0 else content.strip(),
                "conflict": parts[1] if len(parts) > 1 else "",
                "hook": parts[2] if len(parts) > 2 else ""
            }
            outline["plot_points"].append(plot)

    # 如果上面没匹配到，尝试旧格式
    if not outline["plot_points"]:
        plot_matches = RE_PLOT_BOLD.findall(response)
        if plot_matches:
            outline["plot_points"] = [{"order": i+1, "event": p.strip(), "conflict": "", "hook": ""} for i, p in enumerate(plot_matches)]
        else:
            plot_matches = RE_PLOT_FALLBACK.findall(response)
            outline["plot_points"] = [{"order": i+1, "event": p.strip(), "conflict": "", "hook": ""} for i, p in enumerate(plot_matches)]

    # 提取情感曲线
    curve_match = re.search(r"情感曲线[：:]\s*(.+?)(?=---|$)", response, re.DOTALL)
    if curve_match:
        outline["emotional_curve"] = curve_match.group(1).strip()

    return outline


def parse_chapter_count(response: str) -> int:
    """从响应中解析建议章节数"""
    match = RE_CHAPTER_COUNT.search(response)
    if match:
        return int(match.group(1))
    return 10  # 默认值


async def generate_outline_node(state: NovelState, llm: LLMService) -> NovelState:
    """从灵感模板生成大纲"""
    prompt, chapter_count = prepare_outline_prompt(state)

    response = await llm.chat([{"role": "user", "content": prompt}])

    outline = parse_outline(response)

    new_state: NovelState = {
        **state,
        "outline_title": outline["title"],
        "outline_summary": outline["summary"],
        "outline_characters": outline["characters"],  # 新增：人物设定
        "outline_world_setting": outline["world_setting"],  # 新增：世界观
        "outline_plot_points": outline["plot_points"],
        "outline_emotional_curve": outline["emotional_curve"],  # 新增：情感曲线
        "chapter_count": chapter_count,
        "stage": STAGE_OUTLINE,
    }

    return new_state


def prepare_outline_prompt(state: NovelState) -> tuple[str, int]:
    """准备大纲生成提示词和章节数"""
    db = SessionLocal()
    inspiration_template = state.get("inspiration_template", "")
    collected_info = state.get("collected_info", {})

    # 根据目标字数计算章节数（使用常量）
    chapter_count = DEFAULT_CHAPTER_COUNT
    target_words = collected_info.get("targetWords", 100000)
    if isinstance(target_words, int):
        if target_words <= WORDS_THRESHOLD_SHORT:
            chapter_count = max(MIN_CHAPTERS_SHORT, int(target_words / WORDS_PER_CHAPTER_SHORT))
        elif target_words <= WORDS_THRESHOLD_MEDIUM:
            chapter_count = max(MIN_CHAPTERS_MEDIUM, int(target_words / WORDS_PER_CHAPTER_MEDIUM))
        elif target_words <= WORDS_THRESHOLD_LONG:
            chapter_count = max(MIN_CHAPTERS_LONG, int(target_words / WORDS_PER_CHAPTER_LONG))
        elif target_words <= WORDS_THRESHOLD_VERY_LONG:
            chapter_count = max(MIN_CHAPTERS_VERY_LONG, int(target_words / WORDS_PER_CHAPTER_VERY_LONG))
        else:
            chapter_count = max(MIN_CHAPTERS_EPIC, int(target_words / WORDS_PER_CHAPTER_EPIC))

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

    prompt = get_system_prompt(db, "outline_generation").format(
        inspiration_template=inspiration_template,
        chapter_count=chapter_count
    )

    db.close()
    return prompt, chapter_count


async def generate_outline_stream(
    state: NovelState,
    llm: LLMService
) -> AsyncIterator[str]:
    """Generate outline with streaming"""
    prompt, _ = prepare_outline_prompt(state)

    async for chunk in llm.chat_stream([{"role": "user", "content": prompt}]):
        yield chunk


# ==================== LangGraph 兼容节点 ====================

async def outline_generation_node(state: NovelState) -> NovelState:
    """
    LangGraph 兼容的大纲生成节点

    此节点从状态获取 LLM 服务，生成大纲，并返回更新后的状态。
    签名：(state: NovelState) -> NovelState
    """
    # 获取 LLM 服务（异步）
    llm = await get_llm_from_state_async(state)

    # 调用现有的大纲生成函数
    return await generate_outline_node(state, llm)