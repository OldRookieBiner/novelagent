"""章节审核节点"""

import re
from typing import Dict, Any

from app.agents.state import NovelState, STAGE_REVIEW
from app.agents.prompts import REVIEW_CHAPTER_PROMPT
from app.services.llm import LLMService, get_llm_service_from_config, get_llm_service


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


# ==================== LangGraph 兼容节点 ====================

def _get_llm_from_state(state: NovelState) -> LLMService:
    """
    从状态获取 LLM 服务

    根据状态中的 llm_config_id 或 project_id 获取对应的 LLM 服务。
    此函数需要在调用时获取数据库会话。
    """
    from app.database import SessionLocal
    from app.models.user import UserSettings
    from app.models.model_config import ModelConfig

    db = SessionLocal()
    try:
        llm_config_id = state.get("llm_config_id")
        project_id = state.get("project_id")

        # 获取项目以获取 user_id
        from app.models.project import Project
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise ValueError(f"Project {project_id} not found")

        user_id = project.user_id

        # 如果指定了模型配置 ID，使用该配置
        if llm_config_id:
            model_config = db.query(ModelConfig).filter(
                ModelConfig.id == llm_config_id,
                ModelConfig.user_id == user_id,
                ModelConfig.is_enabled == True
            ).first()
            if model_config:
                return get_llm_service_from_config(model_config, user_id)

        # 否则使用用户的默认模型配置
        default_config = db.query(ModelConfig).filter(
            ModelConfig.user_id == user_id,
            ModelConfig.is_default == True,
            ModelConfig.is_enabled == True
        ).first()

        if default_config:
            return get_llm_service_from_config(default_config, user_id)

        # 回退到用户设置
        user_settings = db.query(UserSettings).filter(
            UserSettings.user_id == user_id
        ).first()

        if not user_settings:
            raise ValueError(f"User settings not found for user {user_id}")

        return get_llm_service(user_settings)

    finally:
        db.close()


async def review_node(state: NovelState) -> NovelState:
    """
    LangGraph 兼容的章节审核节点

    此节点：
    1. 从状态获取当前章节内容和章节大纲
    2. 调用 LLM 进行审核
    3. 返回更新后的状态，包含审核结果

    签名：(state: NovelState) -> NovelState
    """
    # 获取 LLM 服务
    llm = _get_llm_from_state(state)

    # 获取当前章节信息
    current_chapter = state.get("current_chapter", 1)
    written_chapters = state.get("written_chapters", [])
    chapter_outlines = state.get("chapter_outlines", [])

    # 找到当前章节的内容
    chapter_content = None
    for chapter in written_chapters:
        if chapter.get("chapter_number") == current_chapter - 1:  # current_chapter 已递增
            chapter_content = chapter.get("content", "")
            break

    if not chapter_content:
        # 如果没找到，尝试用当前章节号
        for chapter in written_chapters:
            if chapter.get("chapter_number") == current_chapter:
                chapter_content = chapter.get("content", "")
                break

    if not chapter_content:
        raise ValueError(f"Chapter content not found for review")

    # 找到当前章节的大纲
    chapter_outline = None
    for outline in chapter_outlines:
        if outline.get("chapter_number") == current_chapter - 1 or outline.get("chapter_number") == current_chapter:
            chapter_outline = outline
            break

    if not chapter_outline:
        raise ValueError(f"Chapter outline not found for review")

    # 调用现有的审核函数
    review_result = await review_chapter_node(
        state,
        chapter_content,
        chapter_outline,
        llm
    )

    # 更新状态
    new_state: NovelState = {
        **state,
        "review_result": review_result,
        "stage": STAGE_REVIEW,
    }

    return new_state
