"""知识库语义检索工具

支持 FAISS + BM25 混合检索，索引不存在时降级为关键词匹配。
A4 增强：DB fallback 路径新增子情节、关系、风格快照搜索。
Store 返回 dict，无需 _serialize。
"""

from langchain_core.tools import tool

from app.agents.tool_context import get_project_id
from app.agents.services.retrieval import RetrievalService
from app.agents.tools.utils import _kb


@tool
async def knowledge_search(query: str, target: str = "all") -> dict:
    """Search the knowledge base for specific information.

    Use when the user asks about any aspect of the novel's settings,
    characters, plot, or style. Uses semantic retrieval when available,
    falls back to structured DB queries.

    Args:
        query: Natural language search query (e.g., "主角的魔法限制", "世界观核心规则")
        target: Which part to search - "world_setting", "characters",
                "foreshadowing", "timeline", "plot", "style", or "all"
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

    # 降级为结构化 DB 查询
    kb = _kb()
    results = {}

    if target in ("all", "world_setting"):
        ws = kb.world_setting.get()
        if ws:
            results["world_setting"] = ws

    # 角色 + 关系（复用查询结果）
    chars_for_map = {}
    if target in ("all", "characters"):
        chars = kb.characters.list_characters()
        results["characters"] = chars
        chars_for_map = {c["id"]: c["name"] for c in chars}

    if target in ("all", "foreshadowing"):
        foreshadowings = kb.foreshadowings.list_foreshadowings()
        results["foreshadowings"] = foreshadowings

    if target in ("all", "timeline"):
        timeline = kb.timelines.list_timeline()
        results["timeline"] = timeline

    # 情节块 + 子情节
    subplots = []
    if target in ("all", "plot"):
        blocks = kb.plots.list_plot_blocks()
        questions = kb.plots.list_plot_questions()
        subplots = kb.plots.list_subplots()
        results["plot_blocks"] = blocks
        results["plot_questions"] = questions
        results["subplots"] = subplots

    # 风格 + 快照
    snapshots = []
    if target in ("all", "style"):
        style = kb.styles.get_constraints()
        snapshots = kb.styles.list_snapshots(last_n=5)
        results["style_constraints"] = style if style else {}
        results["recent_style_snapshots"] = snapshots

    # A4 增强：关键词匹配补充
    query_lower = query.lower()
    query_words = [w for w in query_lower.split() if len(w) >= 2]

    if query_words:
        # 子情节搜索
        if target in ("all", "plot") and subplots:
            for s in subplots:
                subplot_text = f"{s.get('name', '')} {s.get('current_status') or ''}"
                if any(kw in subplot_text for kw in query_words):
                    results.setdefault("subplot_matches", []).append({
                        "id": s["id"],
                        "name": s.get("name"),
                        "current_status": s.get("current_status"),
                    })

        # 关系搜索
        if target in ("all", "characters") and chars_for_map:
            relations = kb.characters.list_relations()
            for r in relations:
                rel_text = f"{chars_for_map.get(r.get('character_a_id'), '')} {chars_for_map.get(r.get('character_b_id'), '')} {r.get('relation_type') or ''} {r.get('current_status') or ''}"
                if any(kw in rel_text for kw in query_words):
                    results.setdefault("relation_matches", []).append({
                        "id": r["id"],
                        "character_a": chars_for_map.get(r.get("character_a_id"), ""),
                        "character_b": chars_for_map.get(r.get("character_b_id"), ""),
                        "relation_type": r.get("relation_type"),
                        "current_status": r.get("current_status"),
                    })

        # 风格快照搜索
        if target in ("all", "style") and not snapshots:
            snapshots = kb.styles.list_snapshots(last_n=10)
            if snapshots:
                results["style_snapshots"] = snapshots

    filtered = {k: v for k, v in results.items() if v}
    if not filtered:
        return {"found": False, "message": f"未找到与「{query}」相关的知识库内容"}
    return {"found": True, "results": filtered}
