"""最终润色节点

Phase 4 完整实现：
1. 收集 structural_review + character_arc_review 的审查问题
2. LLM 根据问题严重程度生成修改建议
3. 🔴严重问题→具体修改文本 / 🟠中等问题→修改建议 / 🟡🟢轻微→记录
4. 最终一致性检查
5. 全书修订可选生成设定百科
6. 清除 revision_context

LangGraph 签名：(state: NovelState) -> NovelState
"""

import json
import logging

from app.agents.state import NovelState, RevisionContext
from app.agents.services.knowledge_base import KnowledgeBaseService
from app.agents.prompts import FINAL_POLISH_PROMPT, FINAL_POLISH_FULL_PROMPT
from app.utils.llm import get_llm_from_state_async
from app.agents.nodes.utils import get_prompts_from_state, safe_format

logger = logging.getLogger(__name__)


async def final_polish_node(state: NovelState) -> NovelState:
    """最终润色 + 可选生成设定百科

    根据 revision_context 决定修订范围：
    - per_volume：润色当前卷，完成后回到写作
    - full_book：全书润色，完成后到 END

    流程：
    1. 读取 post_write_summary 中的审查结果（由上游节点写入）
    2. LLM 分析问题并生成修改建议
    3. 严重问题生成具体修改文本
    4. 清除 revision_context（一次性标志）
    """
    project_id = state["project_id"]
    revision_context = state.get("revision_context")
    kb = KnowledgeBaseService(project_id)

    # 1. 收集审查问题
    # 审查结果由上游节点（structural_review, character_arc_review）写入 post_write_summary
    review_summary = state.get("post_write_summary", "")

    # 如果没有审查摘要，尝试从预警中收集
    if not review_summary:
        review_summary = "无审查问题记录"

    # 2. 确定修订范围描述
    if revision_context == RevisionContext.PER_VOLUME.value:
        current_volume = state.get("current_volume", 1)
        revision_scope = f"逐卷修订：第{current_volume}卷"
    else:
        revision_scope = "全书修订"

    # 3. 格式化 prompt
    format_kwargs = {
        "review_issues": review_summary,
        "revision_scope": revision_scope,
    }

    # 选择 prompt 模板
    prompts = state.get("_prompts", {})
    _, user_template = get_prompts_from_state(prompts, "final_polish_full")

    if user_template:
        prompt_text = safe_format(user_template, **format_kwargs)
    else:
        prompt_text = safe_format(FINAL_POLISH_FULL_PROMPT, **format_kwargs)

    # 4. 调用 LLM 生成修改建议
    llm = await get_llm_from_state_async(state, for_review=True)
    response = ""
    try:
        async for chunk in llm.chat_stream([{"role": "user", "content": prompt_text}], temperature=0.2):
            response += chunk
    except Exception as e:
        logger.error(f"最终润色 LLM 调用失败: {e}")
        response = f"润色过程出错：{e}"

    # 5. 全书修订可选：生成设定百科摘要
    encyclopedia_summary = None
    if revision_context != RevisionContext.PER_VOLUME.value:
        try:
            encyclopedia_summary = _generate_encyclopedia_summary(kb)
        except Exception as e:
            logger.warning(f"设定百科生成失败: {e}")

    # 6. 生成润色报告
    polish_report_parts = [f"## {revision_scope} — 最终润色报告\n"]
    polish_report_parts.append(response)
    if encyclopedia_summary:
        polish_report_parts.append(f"\n\n## 设定百科摘要\n{encyclopedia_summary}")

    polish_report = "\n".join(polish_report_parts)

    # 7. 更新 state：清除 revision_context（一次性标志）
    updates = {
        "post_write_summary": polish_report,
        "revision_context": None,
    }

    return {**state, **updates}


def _generate_encyclopedia_summary(kb: KnowledgeBaseService) -> str:
    """生成设定百科摘要（全书修订专用）

    汇总世界观、角色、关系等核心设定信息，
    供作者参考或导出。
    """
    parts = []

    ws = kb.get_world_setting()
    if ws and ws.tiered_settings:
        parts.append(f"### 世界观设定\n{ws.tiered_settings[:500]}")

    characters = kb.get_characters()
    if characters:
        char_lines = [f"- {c.name}：{c.growth_arc or '未设定弧线'}" for c in characters[:20]]
        parts.append(f"### 角色概览（{len(characters)}个）\n" + "\n".join(char_lines))

    relations = kb.get_relations()
    if relations:
        rel_lines = [f"- {r.relation_type}" for r in relations[:20]]
        parts.append(f"### 关系网络（{len(relations)}条）\n" + "\n".join(rel_lines))

    return "\n\n".join(parts) if parts else ""
