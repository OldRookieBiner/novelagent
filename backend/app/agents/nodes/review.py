"""章节审核节点"""

import json
import re
from typing import Dict, Any

from sqlalchemy.orm import Session

from app.agents.state import NovelState, STAGE_REVIEW
from app.agents.constants import NODE_TEMPERATURES
from app.database import SessionLocal
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
    find_chapter_by_number,
    find_chapter_outline_by_number,
)


def parse_review_result(response: str) -> Dict[str, Any]:
    """解析审核结果（优先 JSON，回退旧格式正则）

    JSON 解析策略：
    1. 先尝试从 markdown 代码块中提取 JSON（```json ... ```）
    2. 再尝试直接匹配最外层花括号（逐层尝试，避免贪婪匹配跨对象）
    3. 以上都失败则回退旧格式正则解析
    """
    # 策略 1：从 markdown 代码块中提取 JSON
    code_block_match = re.search(r'```(?:json)?\s*(\{[\s\S]*?\})\s*```', response)
    if code_block_match:
        try:
            data = json.loads(code_block_match.group(1))
            if "passed" in data:
                return _extract_review_fields(data)
        except json.JSONDecodeError:
            pass

    # 策略 2：直接匹配花括号（非贪婪，找到包含审核字段的 JSON 对象）
    brace_start = response.find('{')
    while brace_start != -1:
        # 找到与起始花括号配对的结束花括号
        depth = 0
        for i in range(brace_start, len(response)):
            if response[i] == '{':
                depth += 1
            elif response[i] == '}':
                depth -= 1
                if depth == 0:
                    candidate = response[brace_start:i + 1]
                    try:
                        data = json.loads(candidate)
                        # 验证是否为审核结果（必须含 passed 字段）
                        if "passed" in data:
                            return _extract_review_fields(data)
                    except json.JSONDecodeError:
                        pass
                    break
        # 此位置无法解析或不含审核字段，尝试下一个 { 的位置
        brace_start = response.find('{', brace_start + 1)

    # 策略 3：回退旧格式正则解析
    return _parse_review_result_legacy(response)


def _extract_review_fields(data: dict) -> Dict[str, Any]:
    """从 JSON 解析结果中提取审核字段

    兼容 LLM 可能使用的不同字段名：
    - suggestions / feedback / 改进建议 → suggestions
    - issues / problems / 问题列表 → issues
    """
    # 提取修改建议（兼容多种字段名）
    suggestions = (
        data.get("suggestions")
        or data.get("feedback")
        or data.get("改进建议")
        or ""
    )

    # 提取问题列表
    issues = data.get("issues") or data.get("problems") or []

    return {
        "passed": bool(data.get("passed", False)),
        "scores": data.get("scores", {}),
        "issues": issues,
        "suggestions": suggestions,
    }


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


def _build_review_messages(
    state: NovelState,
    chapter_content: str,
    chapter_outline: dict,
    strictness: str = "standard",
) -> list[dict]:
    """构建审核的 system/user 消息列表

    将前文上下文、人物档案、世界观、审核维度放入 system message，
    章节大纲、章节正文、题材/风格/严格度放入 user message。
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

    # 上下文策略：构建前文上下文
    target_words = info.get("targetWords", 100000)
    if isinstance(target_words, str):
        target_words = int(target_words)
    strategy_name = info.get("contextStrategy")
    strategy = get_context_strategy(target_words, strategy_name)
    chapter_outlines_list = state.get("chapter_outlines", [])

    # 计算上下文 token 预算（动态截断，防止超出模型窗口）
    from app.agents.token_budget import calculate_context_budget, estimate_tokens
    context_window = state.get("_context_window", 32000)
    output_tokens = 2048  # 审核输出较短
    system_template, _ = get_prompts_from_state(state, "review")
    system_tokens = estimate_tokens(system_template) if system_template else 0
    budget = calculate_context_budget(context_window, output_tokens, system_tokens)

    previous_context = strategy.build_previous_context(
        written_chapters=written_chapters,
        current_chapter=chapter_number,
        chapter_outlines=chapter_outlines_list,
        token_budget=budget,
    )

    # 获取 system/user 模板
    system_template, user_template = get_prompts_from_state(state, "review")

    # 构建 messages
    messages = []
    if system_template:
        system_content = system_template.format(
            previous_context=previous_context,
            main_characters=combined_characters_str,
            world_setting=world_str,
        )
        messages.append({"role": "system", "content": system_content})

    user_content = user_template.format(
        strictness=strictness,
        chapter_outline=outline_str,
        chapter_content=chapter_content,
        genre=info.get("novelType", "未指定"),
        style_preference=info.get("stylePreference", "未指定"),
    )
    messages.append({"role": "user", "content": user_content})

    return messages


async def review_chapter_node(
    state: NovelState,
    chapter_content: str,
    chapter_outline: dict,
    llm: LLMService,
    strictness: str = "standard",
    db: Session | None = None,
) -> Dict[str, Any]:
    """审核章节内容（使用 system/user 双层消息 + 前文上下文）"""
    should_close = False
    if db is None:
        db = SessionLocal()
        should_close = True
    try:
        # 构建 system/user 消息
        messages = _build_review_messages(state, chapter_content, chapter_outline, strictness)

        # 流式调用 LLM
        response = ""
        async for chunk in llm.chat_stream(messages, temperature=NODE_TEMPERATURES["review"]):
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
    # 获取 LLM 服务（审核专用，优先使用 review_llm_config_id）
    llm = await get_llm_from_state_async(state, for_review=True)

    # 获取当前章节信息
    current_chapter = state.get("current_chapter", 1)
    written_chapters = state.get("written_chapters", [])
    chapter_outlines = state.get("chapter_outlines", [])

    # 找到当前章节的内容（current_chapter 已递增，指向下一个待写章节）
    chapter = find_chapter_by_number(written_chapters, current_chapter)
    if not chapter:
        raise ValueError("Chapter content not found for review")
    chapter_content = chapter.get("content", "")

    # 找到当前章节的大纲
    chapter_outline = find_chapter_outline_by_number(chapter_outlines, current_chapter)
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
