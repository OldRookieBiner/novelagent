"""章节重写节点"""

from typing import Dict, Any

from app.agents.state import NovelState, Phase
from app.agents.services.knowledge_base import KnowledgeBaseService
from app.agents.constants import NODE_TEMPERATURES
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
    safe_format,
)
from app.agents.nodes.chapter_generation import clean_chapter_content

def _build_rewrite_messages(
    state: NovelState,
    chapter_outline: dict,
    original_content: str,
    review_feedback: str,
) -> list[dict]:
    """构建重写的 system/user 消息列表

    将前文上下文、人物档案、世界观、修改原则放入 system message，
    章节大纲、审核反馈、原始章节、题材放入 user message。
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
    output_tokens = 8192  # 重写输出约一章
    system_template, user_template_partial = get_prompts_from_state(state, "rewrite")
    system_tokens = estimate_tokens(system_template) if system_template else 0
    user_tokens = estimate_tokens(user_template_partial) if user_template_partial else 0
    budget = calculate_context_budget(context_window, output_tokens, system_tokens, user_tokens)

    previous_context = strategy.build_previous_context(
        written_chapters=written_chapters,
        current_chapter=chapter_number,
        chapter_outlines=chapter_outlines_list,
        token_budget=budget,
    )

    # 获取 system/user 模板
    system_template, user_template = get_prompts_from_state(state, "rewrite")

    # 构建 messages
    messages = []
    if system_template:
        system_content = safe_format(system_template,
            previous_context=previous_context,
            main_characters=combined_characters_str,
            world_setting=world_str,
        )
        messages.append({"role": "system", "content": system_content})

    user_content = safe_format(user_template,
        chapter_outline=outline_str,
        review_feedback=review_feedback,
        original_content=original_content,
        genre=info.get("novelType", "未指定"),
    )
    messages.append({"role": "user", "content": user_content})

    return messages


async def rewrite_chapter_node(
    state: NovelState,
    chapter_outline: dict,
    original_content: str,
    review_feedback: str,
    llm: LLMService,
) -> str:
    """根据审核反馈重写章节（使用 system/user 双层消息 + 前文上下文）"""
    # 构建 system/user 消息
    messages = _build_rewrite_messages(state, chapter_outline, original_content, review_feedback)

    # 流式调用 LLM
    response = ""
    async for chunk in llm.chat_stream(messages, temperature=NODE_TEMPERATURES["rewrite"]):
        response += chunk

    # 清理 LLM 可能添加的结尾数字
    return clean_chapter_content(response)


async def rewrite_with_retry(
    state: NovelState,
    chapter_outline: dict,
    original_content: str,
    llm: LLMService,
    max_retries: int = 3,
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
            state, current_content, chapter_outline, llm
        )

        if check_review_passed(review_result):
            return {
                "content": current_content,
                "review_result": review_result,
                "rewrite_count": rewrite_count,
                "passed": True,
            }

        # 如果还有重试机会，进行重写
        if attempt < max_retries:
            feedback = review_result.get("raw_response", "")
            current_content = await rewrite_chapter_node(
                state, chapter_outline, current_content, feedback, llm
            )
            rewrite_count += 1

    # 超过最大重试次数
    return {
        "content": current_content,
        "review_result": review_result,
        "rewrite_count": rewrite_count,
        "passed": False,
    }


# ==================== LangGraph 兼容节点 ====================


async def rewrite_node(state: NovelState) -> NovelState:
    """
    LangGraph 兼容的章节重写节点

    此节点：
    1. 从状态获取审核反馈和原始章节内容
    2. 调用 LLM 进行重写
    3. 返回更新后的状态，包含重写后的章节

    签名：(state: NovelState) -> NovelState
    """
    # 获取 LLM 服务（异步）
    llm = await get_llm_from_state_async(state)

    # 获取审核结果和章节信息
    review_result = state.get("review_result", {})
    current_chapter = state.get("current_chapter", 1)
    written_chapters = state.get("written_chapters", [])
    chapter_outlines = state.get("chapter_outlines", [])
    rewrite_count = state.get("rewrite_count", 0)

    # 获取审核反馈
    review_feedback = review_result.get("raw_response", "")
    if not review_feedback:
        review_feedback = review_result.get("suggestions", "")

    # 找到当前章节的内容（current_chapter 已递增，指向下一个待写章节）
    chapter = find_chapter_by_number(written_chapters, current_chapter)
    if not chapter:
        raise ValueError("Chapter content not found for rewrite")
    chapter_content = chapter.get("content", "")

    # 找到当前章节的大纲
    chapter_outline = find_chapter_outline_by_number(chapter_outlines, current_chapter)
    if not chapter_outline:
        raise ValueError("Chapter outline not found for rewrite")

    # 调用现有的重写函数
    rewritten_content = await rewrite_chapter_node(
        state, chapter_outline, chapter_content, review_feedback, llm
    )

    # 创建重写后的章节
    chapter_num = current_chapter - 1 if current_chapter > 1 else current_chapter
    rewritten_chapter = {
        "chapter_number": chapter_num,
        "title": chapter_outline.get("title", ""),
        "content": rewritten_content,
        "word_count": len(rewritten_content),
    }

    # 保存重写内容到 DB
    kb = KnowledgeBaseService(state["project_id"])
    kb.save_chapter_content(chapter_num, rewritten_content, len(rewritten_content))

    # 更新状态
    new_state: NovelState = {
        "written_chapters": [
            rewritten_chapter
        ],  # 使用 Annotated[List, add] 会自动追加/替换
        "rewrite_count": rewrite_count + 1,
        "stage": Phase.WRITING.value,
    }

    return new_state
