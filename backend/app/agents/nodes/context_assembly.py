"""上下文组装节点（感知）—— 按需检索版 + 前章收束画面

写作循环的第一步：按需加载当前章节所需的所有上下文。
使用 RetrievalService 语义检索替代全文加载：
- 始终加载：当前情节块目标 + 风格约束 + 风格锚点
- 语义检索：涉及角色 + 涉及设定（由章节点中的关键词触发）
- 直接检查：待回收伏笔 + 问题链
- 前文上下文：通过 context_strategy 加载
- 前章收束画面：提取上章最后 300 字原文，确保下章开头精准衔接

组装结果写入 state["assembled_context"]，供下游 chapter_planning_node 使用。
"""

import logging

from app.agents.state import NovelState, Phase
from app.agents.services.knowledge_base import KnowledgeBaseService
from app.agents.services.retrieval import RetrievalService

logger = logging.getLogger(__name__)

# 前章收束画面截取长度（字符数）
_PREVIOUS_CHAPTER_CLOSING_LENGTH = 300


async def context_assembly_node(state: NovelState) -> NovelState:
    """组装当前章节的上下文（按需检��）

    替代旧版全文加载，改为：
    1. 始终加载：当前情节块 + 风格约束（这两项始终需要且体积小）
    2. 语义检索：涉及角色/设定/伏笔（按需，不是全文）
    3. 直接检查：待回收伏笔 + 待回答问题（精确查询，不走检索）
    4. 前章收束画面：提取上章最后 300 字原文
    """
    project_id = state["project_id"]
    current_chapter = state.get("current_chapter", 1)
    current_volume = state.get("current_volume", 1)
    kb = KnowledgeBaseService(project_id)
    retrieval = RetrievalService(project_id)

    context_parts = []

    # ========== 0. 前章收束画面（新增）==========
    last_chapter_closing_scene = ""
    if current_chapter > 1:
        # 读取上章完整内容
        previous_chapter = kb.get_chapter_by_number(current_chapter - 1)
        if previous_chapter and previous_chapter.content:
            content = previous_chapter.content
            # 提取最后 300 字
            last_chapter_closing_scene = content[-_PREVIOUS_CHAPTER_CLOSING_LENGTH:] if len(content) > _PREVIOUS_CHAPTER_CLOSING_LENGTH else content
            # 清理首尾空白
            last_chapter_closing_scene = last_chapter_closing_scene.strip()
            
            if last_chapter_closing_scene:
                closing_info = f"【上章收束画面】\n{last_chapter_closing_scene}"
                context_parts.append(closing_info)
                logger.debug(f"已提取第 {current_chapter - 1} 章收束画面，长度: {len(last_chapter_closing_scene)} 字")

    # ========== 1. 始终加载 ==========

    # 当前情节块
    current_block = kb.get_current_plot_block(current_chapter)
    if current_block:
        block_info = f"【当前情节块】{current_block.title}"
        if current_block.must_happen:
            must = current_block.must_happen if isinstance(current_block.must_happen, list) else [current_block.must_happen]
            block_info += f"\n必须事件：{', '.join(must)}"
        if hasattr(current_block, 'questions_to_answer') and current_block.questions_to_answer:
            qa = current_block.questions_to_answer if isinstance(current_block.questions_to_answer, list) else [current_block.questions_to_answer]
            block_info += f"\n需回答问题：{', '.join(qa)}"
        if hasattr(current_block, 'questions_to_raise') and current_block.questions_to_raise:
            qr = current_block.questions_to_raise if isinstance(current_block.questions_to_raise, list) else [current_block.questions_to_raise]
            block_info += f"\n需提出问题：{', '.join(qr)}"
        if hasattr(current_block, 'expected_mood') and current_block.expected_mood:
            block_info += f"\n预期情绪：{current_block.expected_mood}"
        context_parts.append(block_info)

    # 风格约束
    style = kb.get_style_constraints()
    if style:
        style_info = "【风格约束】"
        style_parts = []
        if style.taboo_words:
            tw = style.taboo_words if isinstance(style.taboo_words, list) else [style.taboo_words]
            style_parts.append(f"禁忌词：{', '.join(tw)}")
        if style.forbidden_patterns:
            fp = style.forbidden_patterns if isinstance(style.forbidden_patterns, list) else [style.forbidden_patterns]
            style_parts.append(f"禁用句式：{', '.join(fp)}")
        if style.style_anchor:
            style_parts.append(f"风格锚点：{style.style_anchor[:200]}")
        if style.abstract_rules:
            ar = style.abstract_rules if isinstance(style.abstract_rules, list) else [style.abstract_rules]
            style_parts.append(f"抽象规则：{'; '.join(ar)}")
        if style_parts:
            context_parts.append(style_info + "\n" + "\n".join(style_parts))

    # ========== 2. 语义检索 ==========

    # 构建检索查询：从当前情节块目标中提取关键词
    search_queries = []
    if current_block:
        search_queries.append(current_block.title)
        if hasattr(current_block, 'must_happen') and current_block.must_happen:
            must = current_block.must_happen if isinstance(current_block.must_happen, list) else [current_block.must_happen]
            search_queries.extend(must[:3])

    if search_queries:
        query = " ".join(search_queries)
        results = retrieval.search(query, top_k=8, volume_number=current_volume)

        if results:
            retrieval_parts = ["【相关知识库（语义检索）】"]
            for r in results:
                retrieval_parts.append(f"- [{r['source']}] {r['text'][:200]}")
            context_parts.append("\n".join(retrieval_parts))

    # ========== 3. 待回收伏笔 + 问题链 ==========

    overdue = kb.get_overdue_foreshadowings(current_chapter)
    pending = kb.get_pending_foreshadowings()

    if overdue:
        foreshadowing_info = "⚠️【超期伏笔】\n"
        for f in overdue[:5]:
            overdue_by = current_chapter - f.expected_resolve_chapter if f.expected_resolve_chapter else 0
            foreshadowing_info += f"- {f.content}（超期{overdue_by}章，等级：{f.level}）\n"
        context_parts.append(foreshadowing_info.rstrip())

    if pending:
        pending_info = "【待回收伏笔】\n"
        for f in pending[:5]:
            pending_info += f"- {f.content}（预期第{f.expected_resolve_chapter}章回收）\n"
        context_parts.append(pending_info.rstrip())

    questions = kb.get_questions_for_chapter(current_chapter)
    if questions:
        q_info = "【待回答问题】\n"
        for q in questions[:3]:
            q_info += f"- {q.question_text}\n"
        context_parts.append(q_info.rstrip())

    # ========== 4. 前文上下文 ==========

    # 加载最近 2 章的时间线摘要作为前文上下文
    recent_timeline = kb.get_timeline(chapter_range=(max(1, current_chapter - 2), current_chapter - 1))
    if recent_timeline:
        timeline_info = "【前文摘要】\n"
        for t in recent_timeline:
            timeline_info += f"第{t.chapter_number}章：{t.summary[:100]}\n"
        context_parts.append(timeline_info.rstrip())

    # ========== 5. 写作约束（来自 feedback_router）==========
    writing_constraints = state.get("writing_constraints")
    if writing_constraints:
        constraints_info = "【本章写作约束】\n" + "\n".join(f"- {c}" for c in writing_constraints)
        context_parts.append(constraints_info)

    # ========== 组装 ==========

    assembled_context = "\n\n".join(context_parts) if context_parts else "（无额外上下文）"

    # 初始化新字段的默认值
    result = {
        "phase": Phase.WRITING.value,
        "assembled_context": assembled_context,
        "last_chapter_closing_scene": last_chapter_closing_scene,
    }

    # 首次运行时初始化新字段
    if "scene_directions" not in state:
        result["scene_directions"] = None
    if "pov_character" not in state:
        result["pov_character"] = None
    if "rewrite_count" not in state:
        result["rewrite_count"] = 0
    if "issue_accumulator" not in state:
        result["issue_accumulator"] = {}
    if "volume_plans" not in state:
        result["volume_plans"] = None
    if "index_stale" not in state:
        result["index_stale"] = False

    return result
