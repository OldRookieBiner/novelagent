"""章节重写节点"""

from typing import Dict, Any

from app.agents.state import NovelState
from app.agents.prompts import REWRITE_CHAPTER_PROMPT
from app.services.llm import LLMService


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
