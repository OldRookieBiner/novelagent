"""重写工具函数（从 nodes/rewrite.py 和 nodes/chapter_generation.py 迁移）

仅供 Agent 工具使用。_build_rewrite_messages 接受 dict 参数（旧版 NovelState 格式）。
"""

import re

from app.agents.nodes_utils import (
    format_characters_info,
    format_relations_info,
    format_evolution_info,
    format_world_setting,
)


def clean_chapter_content(content: str) -> str:
    """清理章节内容，移除 LLM 可能添加的结尾数字"""
    if not content:
        return content

    result = content.strip()
    pattern = re.compile(r'\n+\s*\d+\s*$')
    while pattern.search(result):
        result = pattern.sub('', result)
    return result


def _build_rewrite_messages(
    state: dict,
    chapter_outline: dict,
    original_content: str,
    review_feedback: str,
) -> list[dict]:
    """构建重写的 system/user 消息列表

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
    output_tokens = 8192
    prompts = state.get("_prompts", {})
    rewrite_prompts = prompts.get("rewrite", {})
    system_template = rewrite_prompts.get("system", "") if isinstance(rewrite_prompts, dict) else ""
    user_template_partial = rewrite_prompts.get("user", "") if isinstance(rewrite_prompts, dict) else ""
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
    system_template, user_template = _get_rewrite_prompts(state)

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
        chapter_outline=outline_str,
        review_feedback=review_feedback,
        original_content=original_content,
        genre=info.get("novelType", "未指定"),
    )
    messages.append({"role": "user", "content": user_content})

    return messages


# ========== 内部辅助函数 ==========


def _format_chapter_outline_str(chapter_outline: dict) -> str:
    """格式化章节大纲为字符串"""
    parts = [f"第{chapter_outline.get('chapter_number', '')}章：{chapter_outline.get('title', '')}"]
    for field, label in [("scene", "场景"), ("characters", "出场人物"), ("plot", "情节要点"),
                         ("conflict", "冲突"), ("turning_point", "转折"), ("hook", "悬念钩子"),
                         ("ending", "结尾"), ("transition", "过渡")]:
        val = chapter_outline.get(field)
        if val:
            parts.append(f"  {label}：{val}")
    return "\n".join(parts)


def _get_rewrite_prompts(state: dict) -> tuple[str, str]:
    """获取重写 prompt 模板"""
    prompts = state.get("_prompts", {})
    rewrite = prompts.get("rewrite", {})

    if isinstance(rewrite, dict):
        system = rewrite.get("system", "")
        user = rewrite.get("user", "")
    elif isinstance(rewrite, str):
        system = ""
        user = rewrite
    else:
        from app.agents.prompts import DEFAULT_PROMPTS
        default = DEFAULT_PROMPTS.get("rewrite", {})
        system = default.get("system", "") if isinstance(default, dict) else ""
        user = default.get("user", "") if isinstance(default, dict) else str(default)

    return system, user


def _safe_format(template: str, **kwargs) -> str:
    """安全格式化模板，缺失 key 不报错"""
    try:
        return template.format(**kwargs)
    except KeyError:
        result = template
        for k, v in kwargs.items():
            result = result.replace("{" + k + "}", str(v) if v else "")
        return result
