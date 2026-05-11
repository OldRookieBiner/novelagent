"""章节审核节点"""

import json
import re
from typing import Dict, Any

from sqlalchemy.orm import Session

from app.agents.state import NovelState, STAGE_REVIEW
from app.database import SessionLocal
from app.services.llm import LLMService
from app.utils.llm import get_llm_from_state_async
from app.agents.nodes.utils import _format_chapter_outline_str, format_characters_info


def parse_review_result(response: str) -> Dict[str, Any]:
    """解析审核结果（优先 JSON，回退旧格式正则）"""
    # 尝试 JSON 解析
    json_match = re.search(r'\{[\s\S]*\}', response)
    if json_match:
        try:
            data = json.loads(json_match.group())
            return {
                "passed": bool(data.get("passed", False)),
                "scores": data.get("scores", {}),
                "issues": data.get("issues", []),
                "suggestions": data.get("suggestions", ""),
            }
        except json.JSONDecodeError:
            pass

    # 回退：旧格式正则解析
    return _parse_review_result_legacy(response)


def _parse_review_result_legacy(response: str) -> Dict[str, Any]:
    """旧格式回退解析（兼容期）"""
    result = {"passed": False, "scores": {}, "issues": [], "suggestions": ""}

    # 解析是否通过
    result["passed"] = "【审核结果】通过" in response

    # 解析分项评分
    score_patterns = {
        "plot_consistency": r"情节一致性[：:]\s*(\d+)/10",
        "character_consistency": r"人物一致性[：:]\s*(\d+)/10",
        "writing_quality": r"文笔质量[：:]\s*(\d+)/10",
        "emotional_tension": r"情感张力[：:]\s*(\d+)/10",
        "ai_flavor": r"AI味程度[：:]\s*(\d+)/10",
        "outline_deviation": r"大纲偏离度[：:]\s*(\d+)/10",
    }

    for key, pattern in score_patterns.items():
        match = re.search(pattern, response)
        if match:
            result["scores"][key] = int(match.group(1))

    # 解析问题列表
    issues_match = re.search(r"【问题列表】(.+?)【修改建议】", response, re.DOTALL)
    if issues_match:
        issues_text = issues_match.group(1)
        issues = [
            i.strip()
            for i in re.findall(
                r"\d+\.\s*(.+?)(?=\n\d+\.|无|$)", issues_text, re.DOTALL
            )
            if i.strip()
        ]
        if issues_text.strip() != "无":
            result["issues"] = issues

    # 解析修改建议
    suggestions_match = re.search(r"【修改建议】(.+?)(?=---|$)", response, re.DOTALL)
    if suggestions_match:
        suggestions = suggestions_match.group(1).strip()
        if suggestions != "无":
            result["suggestions"] = suggestions

    return result


async def review_chapter_node(
    state: NovelState,
    chapter_content: str,
    chapter_outline: dict,
    llm: LLMService,
    strictness: str = "standard",
    db: Session | None = None,
) -> Dict[str, Any]:
    """审核章节内容

    Args:
        state: 当前状态
        chapter_content: 章节正文
        chapter_outline: 章节大纲
        llm: LLM 服务
        strictness: 审核严格度 (loose/standard/strict)
        db: 可选的数据库会话，如果不传则内部创建

    Returns:
        审核结果字典
    """
    should_close = False
    if db is None:
        db = SessionLocal()
        should_close = True
    try:
        info = state.get("collected_info", {})

        # 格式化章节大纲（使用共享工具函数）
        outline_str = _format_chapter_outline_str(chapter_outline)

        # 格式化人物设定（使用共享工具函数）
        chars_str = format_characters_info(state)

        # 优先从 state["_prompts"] 获取，回退到 DEFAULT_PROMPTS
        prompts = state.get("_prompts", {})
        if prompts and "review" in prompts:
            prompt_template = prompts["review"]
        else:
            from app.agents.prompts import DEFAULT_PROMPTS
            prompt_template = DEFAULT_PROMPTS.get("review", "")

        prompt = prompt_template.format(
            strictness=strictness,
            chapter_outline=outline_str,
            chapter_content=chapter_content,
            genre=info.get("novelType", "未指定"),
            main_characters=chars_str,
            style_preference=info.get("stylePreference", "未指定"),
        )

        # 流式调用 LLM，使 LangGraph 能捕获 on_chat_model_stream 事件实时推送给前端
        response = ""
        async for chunk in llm.chat_stream([{"role": "user", "content": prompt}]):
            response += chunk

        result = parse_review_result(response)
        result["raw_response"] = response

        return result
    finally:
        if should_close:
            db.close()


def check_review_passed(review_result: Dict[str, Any]) -> bool:
    """检查审核是否通过

    通过条件：
    - plot/character/writing/emotional 均 ≥ 6
    - AI味 ≤ 3
    - 大纲偏离度 ≤ 4
    """
    scores = review_result.get("scores", {})

    for key in [
        "plot_consistency",
        "character_consistency",
        "writing_quality",
        "emotional_tension",
    ]:
        if scores.get(key, 0) < 6:
            return False

    if scores.get("ai_flavor", 10) > 3:
        return False

    if scores.get("outline_deviation", 0) > 4:
        return False

    return True


# ==================== LangGraph 兼容节点 ====================


async def review_node(state: NovelState) -> NovelState:
    """
    LangGraph 兼容的章节审核节点

    此节点：
    1. 从状态获取当前章节内容和章节大纲
    2. 调用 LLM 进行审核
    3. 返回更新后的状态，包含审核结果

    签名：(state: NovelState) -> NovelState
    """
    # 获取 LLM 服务（异步）
    llm = await get_llm_from_state_async(state)

    # 获取当前章节信息
    current_chapter = state.get("current_chapter", 1)
    written_chapters = state.get("written_chapters", [])
    chapter_outlines = state.get("chapter_outlines", [])

    # 找到当前章节的内容
    chapter_content = None
    for chapter in written_chapters:
        if (
            chapter.get("chapter_number") == current_chapter - 1
        ):  # current_chapter 已递增
            chapter_content = chapter.get("content", "")
            break

    if not chapter_content:
        # 如果没找到，尝试用当前章节号
        for chapter in written_chapters:
            if chapter.get("chapter_number") == current_chapter:
                chapter_content = chapter.get("content", "")
                break

    if not chapter_content:
        raise ValueError("Chapter content not found for review")

    # 找到当前章节的大纲
    chapter_outline = None
    for outline in chapter_outlines:
        if (
            outline.get("chapter_number") == current_chapter - 1
            or outline.get("chapter_number") == current_chapter
        ):
            chapter_outline = outline
            break

    if not chapter_outline:
        raise ValueError("Chapter outline not found for review")

    # 调用现有的审核函数
    review_result = await review_chapter_node(
        state, chapter_content, chapter_outline, llm
    )

    # 更新状态
    new_state: NovelState = {
        **state,
        "review_result": review_result,
        "stage": STAGE_REVIEW,
    }

    return new_state
