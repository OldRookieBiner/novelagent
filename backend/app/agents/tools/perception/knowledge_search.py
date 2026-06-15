"""知识库语义检索工具

支持 FAISS + BM25 混合检索，索引不存在时降级为关键词匹配。
A4 增强：DB fallback 路径新增子情节、关系、风格快照搜索。
R7/R21 修正：降级路径使用 tokenize_chinese 替代 .split()，
每种子类型最多返回 10 条，大数据集返回 truncated 标记。
C1 增强：降级路径 token 预算控制 + 关系匹配优化。
"""

from langchain_core.tools import tool

from app.agents.tool_context import get_project_id
from app.agents.services.retrieval import RetrievalService
from app.agents.tools.utils import _kb
from app.agents.token_budget import estimate_tokens

# 降级截断：每种子类型最多返回的条目数
_MAX_ITEMS_PER_TYPE = 10
# 降级路径最大 token 数
MAX_FALLBACK_TOKENS = 4000


@tool
async def knowledge_search(query: str, target: str = "all") -> dict:
    """搜索知识库中的特定信息。

    当用户询问小说的设定、角色、情节、风格等任何方面时使用。
    优先使用语义检索，不可用时降级为关键词匹配。

    Args:
        query: 自然语言搜索查询（如"主角的魔法限制"、"世界观核心规则"）
        target: 搜索范围 - "world_setting"(世界观), "characters"(角色),
                "foreshadowing"(伏笔), "timeline"(时间线), "plot"(情节),
                "style"(风格), 或 "all"(全部)
    """
    project_id = get_project_id()
    if project_id is None:
        raise ValueError("project_id not set in tool context")

    # 优先语义检索（FAISS+BM25 混合）
    retrieval = RetrievalService(project_id)
    if retrieval.is_index_available():
        results = retrieval.search(query, top_k=8)
        if results:
            return {"found": True, "method": "semantic", "results": results}

    # 降级为结构化 DB 查询，带 token 预算控制
    kb = _kb()
    results = {}
    truncated = False
    current_tokens = 0

    # 定义查询步骤
    query_steps = [
        ("world_setting", lambda: kb.world_setting.get()),
        ("characters", lambda: kb.characters.list_characters()),
        ("foreshadowing", lambda: kb.foreshadowings.list_foreshadowings()),
        ("timeline", lambda: kb.timelines.list_timeline()),
        ("plot_blocks", lambda: kb.plots.list_plot_blocks()),
        ("plot_questions", lambda: kb.plots.list_plot_questions()),
        ("subplots", lambda: kb.plots.list_subplots()),
    ]

    def estimate_data_tokens(data) -> int:
        """估算数据的 token 数"""
        if isinstance(data, dict):
            return estimate_tokens(str(data))
        elif isinstance(data, list):
            return sum(estimate_tokens(str(item)) for item in data)
        return estimate_tokens(str(data))

    # 执行查询步骤，带 token 预算控制
    chars_data = None
    for step_name, step_fn in query_steps:
        # 检查 token 预算
        if current_tokens >= MAX_FALLBACK_TOKENS:
            truncated = True
            break

        # 跳过不相关的 target
        if target != "all" and not any(t in step_name for t in target.split("_")):
            if target == "plot" and step_name not in ("plot_blocks", "plot_questions", "subplots"):
                continue
            if target not in step_name:
                continue

        try:
            data = step_fn()
            if data is None:
                continue

            # 截断大数据集
            if isinstance(data, list):
                data_len = len(data)
                if data_len > _MAX_ITEMS_PER_TYPE:
                    data = data[:_MAX_ITEMS_PER_TYPE]
                    truncated = True

            # 估算 token 并累加
            step_tokens = estimate_data_tokens(data)
            if current_tokens + step_tokens > MAX_FALLBACK_TOKENS:
                # 当前步骤会导致超限，截断并停止
                if isinstance(data, list) and len(data) > 1:
                    data = data[:max(1, len(data) - 1)]
                    truncated = True
                step_tokens = estimate_data_tokens(data)

            current_tokens += step_tokens

            # 存储结果
            if step_name == "world_setting":
                results["world_setting"] = data
            elif step_name == "characters":
                chars_data = data
                results["characters"] = data
                results["characters_total"] = data_len if 'data_len' in dir() else len(data)
            elif step_name == "foreshadowing":
                results["foreshadowings"] = data
                results["foreshadowings_total"] = len(data) if isinstance(data, list) else 1
            elif step_name == "timeline":
                results["timeline"] = data
                results["timeline_total"] = len(data) if isinstance(data, list) else 1
            elif step_name == "plot_blocks":
                results["plot_blocks"] = data
            elif step_name == "plot_questions":
                results["plot_questions"] = data
            elif step_name == "subplots":
                results["subplots"] = data
        except Exception:
            continue

    # 风格单独处理（数据量小，不截断）
    if target in ("all", "style") and current_tokens < MAX_FALLBACK_TOKENS:
        style = kb.styles.get_constraints()
        snapshots = kb.styles.list_snapshots(last_n=5)
        results["style_constraints"] = style if style else {}
        results["recent_style_snapshots"] = snapshots

    # 关键词匹配补充（使用 tokenize_chinese 替代 .split()）
    from app.utils.text import tokenize_chinese
    query_words = [w for w in tokenize_chinese(query.lower()) if len(w) >= 2]

    # 为大数据集建议精确 target
    if target == "all" and truncated:
        results["suggestion"] = "数据量较大，建议使用精确的 target 参数（如 'characters'、'plot'）获取更精准的结果"

    # 关系匹配优化：���在 results 中已有 characters 数据时执行，且只匹配结果中已有角色
    if target in ("all", "characters") and chars_data:
        chars_for_map = {c["id"]: c["name"] for c in chars_data}
        if query_words and chars_for_map:
            # 只获取与已有角色相关的关系
            char_ids = set(chars_for_map.keys())
            relations = kb.characters.list_relations()
            # 过滤只保留涉及结果中角色的关系
            filtered_relations = [
                r for r in relations
                if r.get("character_a_id") in char_ids or r.get("character_b_id") in char_ids
            ]
            relation_matches = []
            for r in filtered_relations[:_MAX_ITEMS_PER_TYPE]:
                rel_text = f"{chars_for_map.get(r.get('character_a_id'), '')} {chars_for_map.get(r.get('character_b_id'), '')} {r.get('relation_type') or ''} {r.get('current_status') or ''}"
                if any(kw in rel_text for kw in query_words):
                    relation_matches.append({
                        "id": r["id"],
                        "character_a": chars_for_map.get(r.get("character_a_id"), ""),
                        "character_b": chars_for_map.get(r.get("character_b_id"), ""),
                        "relation_type": r.get("relation_type"),
                        "current_status": r.get("current_status"),
                    })
            if relation_matches:
                results["relation_matches"] = relation_matches

    filtered = {k: v for k, v in results.items() if v}
    if truncated:
        filtered["truncated"] = True
    if not filtered:
        return {"found": False, "message": f"未找到与「{query}」相关的知识库内容"}
    return {"found": True, "results": filtered}
