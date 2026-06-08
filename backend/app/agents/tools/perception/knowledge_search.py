"""知识库语义检索工具

支持 FAISS + BM25 混合检索，索引不存在时降级为关键词匹配。
A4 增强：DB fallback 路径新增子情节、关系、风格快照搜索。
"""

from langchain_core.tools import tool

from app.agents.tool_context import get_project_id
from app.agents.services.retrieval import RetrievalService
from app.agents.tools.utils import _kb, _serialize


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

    # Try semantic retrieval first (FAISS+BM25 hybrid)
    retrieval = RetrievalService(project_id)
    if retrieval.is_index_available():
        results = retrieval.search(query, top_k=8)
        if results:
            return {"found": True, "method": "semantic", "results": results}

    # Fallback to structured DB queries
    kb = _kb()
    results = {}

    if target in ("all", "world_setting"):
        ws = kb.get_world_setting()
        if ws:
            results["world_setting"] = _serialize(ws)

    if target in ("all", "characters"):
        chars = kb.get_characters()
        results["characters"] = _serialize(chars)

    if target in ("all", "foreshadowing"):
        foreshadowings = kb.get_foreshadowings()
        results["foreshadowings"] = _serialize(foreshadowings)

    if target in ("all", "timeline"):
        timeline = kb.get_timeline()
        results["timeline"] = _serialize(timeline)

    if target in ("all", "plot"):
        blocks = kb.get_plot_blocks()
        questions = kb.get_plot_questions()
        subplots = kb.get_subplots()
        results["plot_blocks"] = _serialize(blocks)
        results["plot_questions"] = _serialize(questions)
        results["subplots"] = _serialize(subplots)

    if target in ("all", "style"):
        style = kb.get_style_constraints()
        snapshots = kb.get_style_snapshots(last_n=5)
        results["style_constraints"] = _serialize(style) if style else {}
        results["recent_style_snapshots"] = _serialize(snapshots)

    # A4 增强：DB fallback 路径中新增子情节、关系、风格快照的关键词搜索
    query_lower = query.lower()
    query_words = [w for w in query_lower.split() if len(w) >= 2]

    # 子情节搜索：匹配 s.name 和 s.current_status（Subplot 模型无 description 字段）
    if target in ("all", "plot") and query_words:
        subplots = kb.get_subplots()
        for s in subplots:
            subplot_text = f"{s.name} {s.current_status or ''}"
            if any(kw in subplot_text for kw in query_words):
                results.setdefault("subplot_matches", []).append({
                    "id": s.id,
                    "name": s.name,
                    "current_status": s.current_status,
                })

    # 关系搜索：只访问 Column 属性，不访问 lazy-loaded relationship
    if target in ("all", "characters") and query_words:
        relations = kb.get_relations()
        # 构建 ID→name 映射，避免访问 r.character_a.name（DetachedInstanceError）
        chars_for_map = kb.get_characters()
        char_name_map = {c.id: c.name for c in chars_for_map}
        for r in relations:
            rel_text = f"{char_name_map.get(r.character_a_id, '')} {char_name_map.get(r.character_b_id, '')} {r.relation_type or ''} {r.current_status or ''}"
            if any(kw in rel_text for kw in query_words):
                results.setdefault("relation_matches", []).append({
                    "id": r.id,
                    "character_a": char_name_map.get(r.character_a_id, ""),
                    "character_b": char_name_map.get(r.character_b_id, ""),
                    "relation_type": r.relation_type,
                    "current_status": r.current_status,
                })

    # 风格快照搜索：按章节号匹配
    if target in ("all", "style") and query_words:
        if "recent_style_snapshots" not in results:
            snapshots = kb.get_style_snapshots(last_n=10)
            results["style_snapshots"] = _serialize(snapshots)

    filtered = {k: v for k, v in results.items() if v}
    if not filtered:
        return {"found": False, "message": f"未找到与「{query}」相关的知识库内容"}
    return {"found": True, "results": filtered}
