"""章节重写节点"""

from typing import Dict, Any

from app.agents.state import NovelState, STAGE_WRITING
from app.agents.prompts import REWRITE_CHAPTER_PROMPT
from app.services.llm import LLMService, get_llm_service_from_config, get_llm_service


async def rewrite_chapter_node(
    state: NovelState,
    chapter_outline: dict,
    original_content: str,
    review_feedback: str,
    llm: LLMService
) -> str:
    """根据审核反馈重写章节

    Args:
        state: 当前状态
        chapter_outline: 章节大纲
        original_content: 原始章节内容
        review_feedback: 审核反馈
        llm: LLM 服务

    Returns:
        重写后的章节内容
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
            f"- {c.get('name', '')}：{c.get('personality', '')}"
            for c in characters
        ])
    else:
        chars_str = info.get("customProtagonist") or info.get("protagonist", "未指定")

    prompt = REWRITE_CHAPTER_PROMPT.format(
        chapter_outline=outline_str,
        original_content=original_content,
        review_feedback=review_feedback,
        genre=info.get("novelType", "未指定"),
        main_characters=chars_str,
        world_setting=info.get("customWorldSetting") or info.get("worldSetting", "未指定")
    )

    response = await llm.chat([{"role": "user", "content": prompt}])

    return response


async def rewrite_with_retry(
    state: NovelState,
    chapter_outline: dict,
    original_content: str,
    llm: LLMService,
    max_retries: int = 3
) -> Dict[str, Any]:
    """带重试的重写流程

    Args:
        state: 当前状态
        chapter_outline: 章节大纲
        original_content: 原始内容
        llm: LLM 服务
        max_retries: 最大重试次数

    Returns:
        包含最终内容和审核结果的字典
    """
    from app.agents.nodes.review import review_chapter_node, check_review_passed

    current_content = original_content
    rewrite_count = 0

    for attempt in range(max_retries + 1):
        # 审核当前内容
        review_result = await review_chapter_node(
            state,
            current_content,
            chapter_outline,
            llm
        )

        if check_review_passed(review_result):
            return {
                "content": current_content,
                "review_result": review_result,
                "rewrite_count": rewrite_count,
                "passed": True
            }

        # 如果还有重试机会，进行重写
        if attempt < max_retries:
            feedback = review_result.get("raw_response", "")
            current_content = await rewrite_chapter_node(
                state,
                chapter_outline,
                current_content,
                feedback,
                llm
            )
            rewrite_count += 1

    # 超过最大重试次数
    return {
        "content": current_content,
        "review_result": review_result,
        "rewrite_count": rewrite_count,
        "passed": False
    }


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


async def rewrite_node(state: NovelState) -> NovelState:
    """
    LangGraph 兼容的章节重写节点

    此节点：
    1. 从状态获取审核反馈和原始章节内容
    2. 调用 LLM 进行重写
    3. 返回更新后的状态，包含重写后的章节

    签名：(state: NovelState) -> NovelState
    """
    # 获取 LLM 服务
    llm = _get_llm_from_state(state)

    # 获取审核结果和章节信息
    review_result = state.get("review_result", {})
    current_chapter = state.get("current_chapter", 1)
    written_chapters = state.get("written_chapters", [])
    chapter_outlines = state.get("chapter_outlines", [])
    rewrite_count = state.get("rewrite_count", 0)
    max_rewrite_count = state.get("max_rewrite_count", 3)

    # 获取审核反馈
    review_feedback = review_result.get("raw_response", "")
    if not review_feedback:
        review_feedback = review_result.get("suggestions", "")

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
        raise ValueError(f"Chapter content not found for rewrite")

    # 找到当前章节的大纲
    chapter_outline = None
    for outline in chapter_outlines:
        if outline.get("chapter_number") == current_chapter - 1 or outline.get("chapter_number") == current_chapter:
            chapter_outline = outline
            break

    if not chapter_outline:
        raise ValueError(f"Chapter outline not found for rewrite")

    # 调用现有的重写函数
    rewritten_content = await rewrite_chapter_node(
        state,
        chapter_outline,
        chapter_content,
        review_feedback,
        llm
    )

    # 创建重写后的章节
    rewritten_chapter = {
        "chapter_number": current_chapter - 1 if current_chapter > 1 else current_chapter,
        "title": chapter_outline.get("title", ""),
        "content": rewritten_content,
        "word_count": len(rewritten_content)
    }

    # 更新状态
    new_state: NovelState = {
        **state,
        "written_chapters": [rewritten_chapter],  # 使用 Annotated[List, add] 会自动追加/替换
        "rewrite_count": rewrite_count + 1,
        "stage": STAGE_WRITING,
    }

    return new_state
