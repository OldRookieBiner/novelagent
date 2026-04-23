"""章节审核节点"""

import re
from typing import Dict, Any

from app.agents.state import NovelState
from app.agents.prompts import REVIEW_CHAPTER_PROMPT
from app.services.llm import LLMService


def parse_review_result(response: str) -> Dict[str, Any]:
    """解析审核结果"""
    result = {
        "passed": False,
        "scores": {},
        "issues": [],
        "suggestions": ""
    }

    # 解析是否通过
    result["passed"] = "【审核结果】通过" in response

    # 解析分项评分
    score_patterns = {
        "plot_consistency": r"情节一致性[：:]\s*(\d+)/10",
        "character_consistency": r"人物一致性[：:]\s*(\d+)/10",
        "writing_quality": r"文笔质量[：:]\s*(\d+)/10",
        "emotional_tension": r"情感张力[：:]\s*(\d+)/10",
        "ai_flavor": r"AI味程度[：:]\s*(\d+)/10"
    }

    for key, pattern in score_patterns.items():
        match = re.search(pattern, response)
        if match:
            result["scores"][key] = int(match.group(1))

    # 解析问题列表
    issues_match = re.search(r"【问题列表】(.+?)【修改建议】", response, re.DOTALL)
    if issues_match:
        issues_text = issues_match.group(1)
        issues = [i.strip() for i in re.findall(r"\d+\.\s*(.+?)(?=\n\d+\.|无|$)", issues_text, re.DOTALL) if i.strip()]
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
    strictness: str = "standard"
) -> Dict[str, Any]:
    """审核章节内容

    Args:
        state: 当前状态
        chapter_content: 章节正文
        chapter_outline: 章节大纲
        llm: LLM 服务
        strictness: 审核严格度 (loose/standard/strict)

    Returns:
        审核结果字典
    """
    info = state.get("collected_info", {})
    characters = state.get("outline_characters", [])

    # 格式化章节大纲
    outline_str = f"""章节名：{chapter_outline.get('title', '')}
场景：{chapter_outline.get('scene', '')}
人物：{chapter_outline.get('characters', '')}
情节：{chapter_outline.get('plot', '')}
冲突：{chapter_outline.get('conflict', '')}
钩子：{chapter_outline.get('hook', '')}"""

    # 格式化人物设定
    if characters:
        chars_str = "\n".join([
            f"- {c.get('name', '')}：{c.get('personality', '')}，动机：{c.get('motivation', '')}"
            for c in characters
        ])
    else:
        chars_str = info.get("customProtagonist") or info.get("protagonist", "未指定")

    prompt = REVIEW_CHAPTER_PROMPT.format(
        strictness=strictness,
        chapter_outline=outline_str,
        chapter_content=chapter_content,
        genre=info.get("novelType", "未指定"),
        main_characters=chars_str,
        style_preference=info.get("stylePreference", "未指定")
    )

    response = await llm.chat([{"role": "user", "content": prompt}])

    result = parse_review_result(response)
    result["raw_response"] = response

    return result


def check_review_passed(review_result: Dict[str, Any]) -> bool:
    """检查审核是否通过

    通过条件：
    - 所有评分 >= 6
    - AI味 <= 3
    """
    scores = review_result.get("scores", {})

    for key in ["plot_consistency", "character_consistency", "writing_quality", "emotional_tension"]:
        if scores.get(key, 0) < 6:
            return False

    if scores.get("ai_flavor", 10) > 3:
        return False

    return True
