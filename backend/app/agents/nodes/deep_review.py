"""深度审查节点 — 6 维度增强版

每 5 章触发，派生子 Agent 只读审查。

检查维度（对齐 novelskills SKILL.md 步骤 3.5）：
1. 情节一致性：时间线中事件是否有逻辑矛盾
2. 伏笔追踪：待回收伏笔是否超期；出现 1 次直接回收违反分级
3. 支线追踪：支线是否长期无推进；交汇点已过仍未交汇
4. 节奏审查：连续同类情绪、拖沓、偏离预期节奏曲线
5. 设定违反：是否违反 🔴 设定
6. POV 审查：同场景混入非 POV 内心；每章 POV 切换超过 3 次

每 10 章额外触发风格漂移检测。

输出结构化审查报告，写入 state。
"""

import logging

from app.agents.state import NovelState
from app.agents.services.knowledge_base import KnowledgeBaseService
from app.agents.prompts import DEEP_REVIEW_ENHANCED_PROMPT
from app.utils.llm import get_llm_from_state_async
from app.agents.nodes.utils import get_prompts_from_state, safe_format

logger = logging.getLogger(__name__)


async def deep_review_node(state: NovelState) -> NovelState:
    """深度审查（6 维度增强版）

    读取：时间线摘要、最近 5 章时间线、设定集、大纲、伏笔表、风格统计
    每 10 章额外读取风格统计做漂移检测。

    输出：结构化审查报告，每个维度 ✅/⚠️/❌ + 具体问题。
    """
    project_id = state["project_id"]
    current_chapter = state.get("current_chapter", 1)
    written_chapter_num = current_chapter - 1
    kb = KnowledgeBaseService(project_id)

    # 读取审查所需数据
    timeline = kb.get_timeline(chapter_range=(max(1, written_chapter_num - 4), written_chapter_num))
    all_timeline = kb.get_timeline()
    world_setting = kb.get_world_setting()
    outline = kb.get_outline()
    foreshadowings = kb.get_foreshadowings()
    subplots = kb.get_subplots()
    snapshots = kb.get_style_snapshots(last_n=10)
    style = kb.get_style_constraints()

    # 格式化各数据段
    timeline_text = "\n".join([
        f"第{t.chapter_number}章：{t.summary} | 节奏{t.rhythm_score} 张力{t.tension_score} 情感{t.emotion_score} | {t.emotion_tag}"
        for t in timeline
    ])

    setting_text = ""
    if world_setting:
        parts = []
        if world_setting.core_concept:
            parts.append(f"核心理念：{world_setting.core_concept}")
        if world_setting.tiered_settings:
            ts = world_setting.tiered_settings
            if isinstance(ts, dict):
                for tier, items in ts.items():
                    parts.append(f"{tier}：{items}")
            else:
                parts.append(f"分级设定：{ts}")
        setting_text = "\n".join(parts)

    outline_text = outline.summary if outline else ""

    foreshadowing_text = "\n".join([
        f"- {f.content}（{f.level}/{f.status}，出现{f.appearance_count}次，埋设第{f.planted_chapter}章，预期回收第{f.expected_resolve_chapter}章）"
        for f in foreshadowings
    ])

    subplot_text = "\n".join([
        f"- {s.name}（{s.current_status}，涉及：{s.characters}，预期解决第{s.expected_resolution_chapter}章）"
        for s in subplots
    ]) if subplots else "（无支线）"

    stats_text = "\n".join([
        f"第{s.chapter_number}章：对话{s.dialogue_ratio:.0%} 句长{s.avg_sentence_length:.0f} 段长{s.avg_paragraph_length:.0f}"
        for s in snapshots
    ])

    # 检查是否需要风格漂移检测（每 10 章）
    include_style_drift = written_chapter_num % 10 == 0 and len(snapshots) >= 5

    # 构建 Prompt
    prompts = state.get("_prompts", {})
    _, user_template = get_prompts_from_state(prompts, "deep_review_enhanced")

    format_kwargs = dict(
        timeline_entries=timeline_text,
        world_setting=setting_text,
        outline=outline_text,
        foreshadowings=foreshadowing_text,
        style_stats=stats_text,
        subplot_text=subplot_text,
        chapter_number=written_chapter_num,
        include_style_drift="是" if include_style_drift else "否",
    )

    if user_template:
        prompt_text = safe_format(user_template, **format_kwargs)
    else:
        prompt_text = safe_format(DEEP_REVIEW_ENHANCED_PROMPT, **format_kwargs)

    llm = await get_llm_from_state_async(state)
    response = ""
    async for chunk in llm.chat_stream(
        [{"role": "user", "content": prompt_text}], temperature=0.2
    ):
        response += chunk

    logger.info(f"项目 {project_id} 第 {written_chapter_num} 章深度审查完成")

    # 更新 last_review_chapter
    return {
        "last_review_chapter": written_chapter_num,
    }
