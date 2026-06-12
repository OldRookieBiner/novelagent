"""审核工具函数（从 nodes/review.py 迁移）

仅供 Agent 工具使用。_build_review_messages 接受 dict 参数（旧版 NovelState 格式），
由调用方（如 agent_tools.py 的 _build_state_for_review）构造。
"""

import json
import re
from typing import Dict, Any

from app.agents.nodes_utils import (
    format_characters_info,
    format_relations_info,
    format_evolution_info,
    format_world_setting,
)


def parse_review_result(response: str) -> Dict[str, Any]:
    """解析审核结果（优先 JSON，回退旧格式正则）"""
    # 策略 1：从 markdown 代码块中提取 JSON
    code_block_match = re.search(r'```(?:json)?\s*(\{[\s\S]*?\})\s*```', response)
    if code_block_match:
        try:
            data = json.loads(code_block_match.group(1))
            if "passed" in data:
                return _extract_review_fields(data)
        except json.JSONDecodeError:
            pass

    # 策略 2：直接匹配花括号
    brace_start = response.find('{')
    while brace_start != -1:
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
                        if "passed" in data:
                            return _extract_review_fields(data)
                    except json.JSONDecodeError:
                        pass
                    break
        brace_start = response.find('{', brace_start + 1)

    # 策略 3：回退旧格式正则解析
    return _parse_review_result_legacy(response)


def _extract_review_fields(data: dict) -> Dict[str, Any]:
    """从 JSON 解析结果中提取审核字段"""
    suggestions = (
        data.get("suggestions")
        or data.get("feedback")
        or data.get("改进建议")
        or ""
    )

    raw_issues = data.get("issues") or data.get("problems") or []
    normalized_issues = []
    for issue in raw_issues:
        if isinstance(issue, str):
            normalized_issues.append({"type": "", "suggestion": "", "description": issue})
            continue
        normalized = {
            "type": issue.get("type", ""),
            "suggestion": issue.get("suggestion", ""),
        }
        if "paragraph_start" in issue:
            normalized["paragraph_start"] = issue["paragraph_start"]
        if "location" in issue:
            normalized["location"] = issue["location"]
        if "description" in issue:
            normalized["description"] = issue["description"]
        normalized_issues.append(normalized)

    return {
        "passed": bool(data.get("passed", False)),
        "scores": data.get("scores", {}),
        "issues": normalized_issues,
        "suggestions": suggestions,
    }


def _parse_review_result_legacy(response: str) -> Dict[str, Any]:
    """旧格式回退解析"""
    result = {"passed": False, "scores": {}, "issues": [], "suggestions": ""}

    result["passed"] = "【审核结果】通过" in response

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

    issues_match = re.search(r"【问题列表】(.+?)【修改建议】", response, re.DOTALL)
    if issues_match:
        issues_text = issues_match.group(1)
        issues = [
            i.strip()
            for i in re.findall(r"\d+\.\s*(.+?)(?=\n\d+\.|无|$)", issues_text, re.DOTALL)
            if i.strip()
        ]
        if issues_text.strip() != "无":
            result["issues"] = issues

    suggestions_match = re.search(r"【修改建议】(.+?)(?=---|$)", response, re.DOTALL)
    if suggestions_match:
        suggestions = suggestions_match.group(1).strip()
        if suggestions != "无":
            result["suggestions"] = suggestions

    return result


def _build_review_messages(
    state: dict,
    chapter_content: str,
    chapter_outline: dict,
    strictness: str = "standard",
) -> list[dict]:
    """构建审核的 system/user 消息列表

    state 参数为旧版 NovelState 格式字典，由 _build_state_for_review 构造。
    """
    from app.agents.context_strategy import get_context_strategy
    from app.agents.token_budget import calculate_context_budget, estimate_tokens

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

    # 上下文策略
    target_words = info.get("targetWords", 100000)
    if isinstance(target_words, str):
        target_words = int(target_words)
    strategy_name = info.get("contextStrategy")
    strategy = get_context_strategy(target_words, strategy_name)
    chapter_outlines_list = state.get("chapter_outlines", [])

    # 计算上下文 token 预算
    context_window = state.get("_context_window", 32000)
    output_tokens = 2048
    prompts = state.get("_prompts", {})
    review_prompts = prompts.get("review", {})
    system_template = review_prompts.get("system", "") if isinstance(review_prompts, dict) else ""
    system_tokens = estimate_tokens(system_template) if system_template else 0
    budget = calculate_context_budget(context_window, output_tokens, system_tokens)

    previous_context = strategy.build_previous_context(
        written_chapters=written_chapters,
        current_chapter=chapter_number,
        chapter_outlines=chapter_outlines_list,
        token_budget=budget,
    )

    # 获取 system/user 模板
    system_template, user_template = _get_review_prompts(state)

    # 构建 messages
    messages = []
    if system_template:
        system_content = _safe_format(system_template,
            previous_context=previous_context,
            main_characters=combined_characters_str,
            world_setting=world_str,
        )
        messages.append({"role": "system", "content": system_content})

    user_content = _safe_format(user_template,
        strictness=strictness,
        chapter_outline=outline_str,
        chapter_content=chapter_content,
        genre=info.get("novelType", "未指定"),
        style_preference=info.get("stylePreference", "未指定"),
    )
    messages.append({"role": "user", "content": user_content})

    return messages


def check_review_passed(review_result: Dict[str, Any]) -> bool:
    """检查审核是否通过"""
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


# ========== 内部辅助函数 ==========


def _format_chapter_outline_str(chapter_outline: dict) -> str:
    """格式化章节大纲为字符串"""
    parts = [f"第{chapter_outline.get('chapter_number', '')}章：{chapter_outline.get('title', '')}"]
    for field, label in [("scene", "场景"), ("characters", "出场人物"), ("plot", "情节要点"),
                         ("conflict", "冲突"), ("turning_point", "转折"), ("hook", "悬念钩子"),
                         ("ending", "结尾"), ("transition", "过渡"),
                         ("opening_state", "开场状态"), ("emotional_arc", "情绪弧线"), ("pacing_note", "节奏标注")]:
        val = chapter_outline.get(field)
        if val:
            parts.append(f"  {label}：{val}")
    scenes = chapter_outline.get("key_scenes")
    if scenes and isinstance(scenes, list):
        for s in scenes:
            seq = s.get("seq", "")
            desc = s.get("desc", "")
            mood = s.get("mood", "")
            parts.append(f"  场景{seq}：{desc}（{mood}）")
    return "\n".join(parts)


def _get_review_prompts(state: dict) -> tuple[str, str]:
    """获取审核 prompt 模板"""
    prompts = state.get("_prompts", {})
    review = prompts.get("review", {})

    if isinstance(review, dict):
        system = review.get("system", "")
        user = review.get("user", "")
    elif isinstance(review, str):
        system = ""
        user = review
    else:
        from app.agents.prompts import DEFAULT_PROMPTS
        default = DEFAULT_PROMPTS.get("review", {})
        system = default.get("system", "") if isinstance(default, dict) else ""
        user = default.get("user", "") if isinstance(default, dict) else str(default)

    return system, user


def _safe_format(template: str, **kwargs) -> str:
    """安全格式化模板，缺失 key 不报错"""
    try:
        return template.format(**kwargs)
    except KeyError:
        # 逐个替换
        result = template
        for k, v in kwargs.items():
            result = result.replace("{" + k + "}", str(v) if v else "")
        return result
