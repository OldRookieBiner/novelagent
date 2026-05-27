"""语义检索服务

核心逻辑复用 novelskills search.py，数据源从 Markdown 文件改为 DB 查询。

架构：
  FAISS 索引（bge-m3 模型）× 0.7 + BM25 索引（jieba 分词）× 0.3
  → 混合排序 → 时间衰减 → 去重 + 截断 → 返回 top-k

索引来源（从 DB 读取）：
  - 世界观 + 角色 + 关系 + 风格约束 + 情节块 + 伏笔 + 时间线 + 场景清单
  - 时间线条目仅索引最近 50 条

索引更新策略：
  - 全量重建：每 5 章，由 post_write_update 触发
  - 查询时如果索引不存在，自动降级为关键词匹配
"""

import json
import logging
import os
import pickle
from pathlib import Path
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

# ========== 懒加载依赖 ==========

_sentence_transformers_available = False
_model = None

def _get_model():
    """懒加载 sentence-transformers 模型（bge-m3）"""
    global _sentence_transformers_available, _model
    if _model is not None:
        return _model
    try:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer("BAAI/bge-m3")
        _sentence_transformers_available = True
        return _model
    except ImportError:
        logger.warning("sentence-transformers 未安装，语义检索不可用")
        _sentence_transformers_available = False
        return None
    except Exception as e:
        logger.error(f"模型加载失败: {e}")
        _sentence_transformers_available = False
        return None


_jieba_available = False

def _tokenize_chinese(text: str) -> list[str]:
    """中文分词，jieba 不可用时退化为字符 bigram"""
    global _jieba_available
    try:
        import jieba
        _jieba_available = True
        return list(jieba.cut(text))
    except ImportError:
        _jieba_available = False
        result = []
        for i in range(len(text) - 1):
            result.append(text[i:i+2])
        return result


# ========== 文本切分 ==========

def chunk_text(text: str, min_chars: int = 50, max_chars: int = 300) -> list[str]:
    """将文本按段落切分为块，短段落合并，长段落拆分。

    复用 novelskills search.py chunk_text 逻辑。
    """
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks = []
    current = ""
    for p in paragraphs:
        if len(current) + len(p) > max_chars and current:
            chunks.append(current.strip())
            current = p
        else:
            current = current + "\n" + p if current else p
        if len(current) >= max_chars:
            chunks.append(current.strip())
            current = ""
    if current.strip():
        chunks.append(current.strip())
    return [c for c in chunks if len(c) >= min_chars]


# ========== 索引目录管理 ==========

def _index_dir(project_id: int) -> str:
    """获取项目索引目录路径"""
    base = os.environ.get("NOVELAGENT_INDEX_DIR", "/tmp/novelagent_index")
    path = os.path.join(base, str(project_id))
    os.makedirs(path, exist_ok=True)
    return path


# ========== 索引构建 ==========

def _collect_documents_from_db(project_id: int) -> tuple[list[str], list[dict]]:
    """从 DB 收集所有知识库文本，返回 (docs, meta)

    数据来源：世界观、角色、关系、风格约束、情节块、伏笔、时间线（最近50条）、场景清单
    """
    from app.agents.services.knowledge_base import KnowledgeBaseService
    kb = KnowledgeBaseService(project_id)

    docs = []
    meta = []

    def _add(text: str, source: str):
        if not text or not text.strip():
            return
        chunks = chunk_text(text)
        for i, chunk in enumerate(chunks):
            docs.append(chunk)
            meta.append({"source": source, "chunk": i})

    # 1. 世界观
    ws = kb.get_world_setting()
    if ws:
        parts = []
        if ws.core_concept:
            parts.append(f"核心理念：{ws.core_concept}")
        if ws.tiered_settings:
            parts.append(f"分级设定：{ws.tiered_settings}")
        if ws.key_locations:
            parts.append(f"关键地点：{ws.key_locations}")
        _add("\n".join(parts), "world_setting")

    # 2. 角色
    characters = kb.get_characters()
    for char in characters:
        parts = [f"角色：{char.name}"]
        if hasattr(char, 'role') and char.role:
            parts.append(f"定位：{char.role}")
        if hasattr(char, 'core_motivation') and char.core_motivation:
            parts.append(f"核心动机：{char.core_motivation}")
        if hasattr(char, 'core_conflict') and char.core_conflict:
            parts.append(f"核心冲突：{char.core_conflict}")
        if hasattr(char, 'character_arc') and char.character_arc:
            parts.append(f"人物弧：{char.character_arc}")
        if hasattr(char, 'knowledge_boundary') and char.knowledge_boundary:
            parts.append(f"知识边界：{char.knowledge_boundary}")
        if hasattr(char, 'speech_style') and char.speech_style:
            parts.append(f"说话风格：{char.speech_style}")
        if hasattr(char, 'dialogue_samples') and char.dialogue_samples:
            parts.append(f"对话样本：{char.dialogue_samples}")
        _add("\n".join(parts), f"character/{char.name}")

    # 3. 关系
    relations = kb.get_relations()
    if relations:
        rel_parts = []
        for r in relations:
            rel_parts.append(str(r))
        _add("\n".join(rel_parts), "relations")

    # 4. 风格约束
    style = kb.get_style_constraints()
    if style:
        parts = []
        if style.taboo_words:
            parts.append(f"禁忌词：{', '.join(style.taboo_words)}")
        if style.forbidden_patterns:
            parts.append(f"禁用句式：{', '.join(style.forbidden_patterns) if isinstance(style.forbidden_patterns, list) else style.forbidden_patterns}")
        if style.style_anchor:
            parts.append(f"风格锚点：{style.style_anchor}")
        if style.abstract_rules:
            parts.append(f"抽象风格规则：{style.abstract_rules}")
        _add("\n".join(parts), "style_constraints")

    # 5. 情节块
    blocks = kb.get_plot_blocks()
    for block in blocks:
        parts = [f"情节块：{block.title}"]
        if block.must_happen:
            parts.append(f"必须事件：{', '.join(block.must_happen) if isinstance(block.must_happen, list) else block.must_happen}")
        if hasattr(block, 'questions_to_answer') and block.questions_to_answer:
            parts.append(f"要回答的问题：{', '.join(block.questions_to_answer) if isinstance(block.questions_to_answer, list) else block.questions_to_answer}")
        if hasattr(block, 'questions_to_raise') and block.questions_to_raise:
            parts.append(f"要提出的问题：{', '.join(block.questions_to_raise) if isinstance(block.questions_to_raise, list) else block.questions_to_raise}")
        _add("\n".join(parts), f"plot_block/{block.title}")

    # 6. 伏笔
    foreshadowings = kb.get_foreshadowings()
    for f in foreshadowings:
        parts = [f"伏笔：{f.content}"]
        parts.append(f"等级：{f.level}，状态：{f.status}")
        if f.planted_chapter:
            parts.append(f"埋设章节：第{f.planted_chapter}章")
        if f.expected_resolve_chapter:
            parts.append(f"预期回收：第{f.expected_resolve_chapter}章")
        _add("\n".join(parts), f"foreshadowing/{f.id}")

    # 7. 时间线（最近50条）
    timeline = kb.get_timeline()
    recent = timeline[-50:] if len(timeline) > 50 else timeline
    for t in recent:
        parts = [f"第{t.chapter_number}章"]
        if t.summary:
            parts.append(t.summary)
        if t.causal_chain:
            parts.append(f"因果链：{t.causal_chain}")
        if t.emotion_tag:
            parts.append(f"情绪：{t.emotion_tag}")
        _add(" | ".join(parts), f"timeline/{t.chapter_number}")

    # 8. 场景清单
    scenes = kb.get_scene_entries()
    if scenes:
        scene_parts = []
        for s in scenes:
            scene_parts.append(f"第{s.chapter_number}章：{s.scene_description}")
        _add("\n".join(scene_parts), "scene_entries")

    return docs, meta


def build_index(project_id: int) -> bool:
    """为项目构建 FAISS + BM25 索引

    Returns:
        True if index built successfully, False otherwise
    """
    model = _get_model()
    if model is None:
        logger.warning(f"项目 {project_id}: 模型不可用，跳过索引构建")
        return False

    docs, meta = _collect_documents_from_db(project_id)
    if not docs:
        logger.warning(f"项目 {project_id}: 无文档可索引")
        return False

    index_path = _index_dir(project_id)

    try:
        # FAISS 索引
        embeddings = model.encode(docs, show_progress_bar=False)
        emb_array = np.array(embeddings).astype("float32")
        import faiss
        index = faiss.IndexFlatIP(emb_array.shape[1])
        faiss.normalize_L2(emb_array)
        index.add(emb_array)
        faiss.write_index(index, os.path.join(index_path, "index.faiss"))
        np.save(os.path.join(index_path, "embeddings.npy"), emb_array)

        # 元数据
        with open(os.path.join(index_path, "meta.json"), "w", encoding="utf-8") as f:
            json.dump({"docs": docs, "meta": meta}, f, ensure_ascii=False, indent=2)

        # BM25 索引
        try:
            from rank_bm25 import BM25Okapi
            tokenized_corpus = [_tokenize_chinese(d) for d in docs]
            bm25 = BM25Okapi(tokenized_corpus)
            with open(os.path.join(index_path, "bm25.pkl"), "wb") as f:
                pickle.dump(bm25, f)
        except ImportError:
            logger.warning("rank_bm25 未安装，BM25 检索不可用")

        logger.info(f"项目 {project_id}: 索引构建完成，{len(docs)} 个文档块")
        return True

    except Exception as e:
        logger.error(f"项目 {project_id}: 索引构建失败: {e}")
        return False


# ========== 检索 ==========

def search(
    project_id: int,
    query: str,
    top_k: int = 5,
) -> list[dict]:
    """混合语义检索

    FAISS × 0.7 + BM25 × 0.3，时间线条目应用时间衰减权重。
    索引不存在时自动降级为关键词匹配。

    Args:
        project_id: 项目 ID
        query: 自然语言查询
        top_k: 返回结果数

    Returns:
        [{"score": float, "source": str, "text": str}]
    """
    index_path = _index_dir(project_id)
    meta_path = os.path.join(index_path, "meta.json")
    faiss_path = os.path.join(index_path, "index.faiss")

    # 索引不存在 → 降级为关键词匹配
    if not os.path.exists(meta_path) or not os.path.exists(faiss_path):
        return _keyword_fallback(project_id, query, top_k)

    try:
        return _hybrid_search(index_path, query, top_k)
    except Exception as e:
        logger.warning(f"混合检索失败，降级为关键词匹配: {e}")
        return _keyword_fallback(project_id, query, top_k)


def _hybrid_search(index_path: str, query: str, top_k: int) -> list[dict]:
    """FAISS + BM25 混合检索

    核心逻辑复用 novelskills search.py _search_index，权重调整：
    - FAISS (dense): 0.7
    - BM25 (sparse): 0.3
    - 时间线条目应用时间衰减（0.5 ~ 1.0）
    """
    import faiss

    model = _get_model()
    if model is None:
        return []

    # 加载索引
    with open(os.path.join(index_path, "meta.json"), "r", encoding="utf-8") as f:
        data = json.load(f)

    docs = data["docs"]
    meta_list = data["meta"]
    n_docs = len(docs)
    if n_docs == 0:
        return []

    # 向量检索
    query_emb = model.encode([query]).astype("float32")
    faiss.normalize_L2(query_emb)

    index = faiss.read_index(os.path.join(index_path, "index.faiss"))
    all_scores, _ = index.search(query_emb, n_docs)
    dense_scores = all_scores[0]

    # 归一化到 [0, 1]
    d_min, d_max = dense_scores.min(), dense_scores.max()
    dense_norm = (dense_scores - d_min) / (d_max - d_min + 1e-8)

    # 时间衰减：时间线条目越新权重越高
    source_list = [m["source"] for m in meta_list]
    decay = np.ones(n_docs, dtype="float32")
    timeline_indices = [i for i, src in enumerate(source_list) if src.startswith("timeline/")]
    if timeline_indices:
        for rank, i in enumerate(timeline_indices):
            decay[i] = 0.5 + 0.5 * (rank / max(len(timeline_indices) - 1, 1))

    # BM25 混合
    bm25_path = os.path.join(index_path, "bm25.pkl")
    bm25_ok = os.path.exists(bm25_path)

    if bm25_ok:
        try:
            with open(bm25_path, "rb") as f:
                bm25 = pickle.load(f)
            tokenized_query = _tokenize_chinese(query)
            bm25_scores = np.array(bm25.get_scores(tokenized_query), dtype="float32")
            b_max = bm25_scores.max()
            bm25_norm = bm25_scores / (b_max + 1e-8) if b_max > 0 else np.zeros(n_docs, dtype="float32")

            hybrid = 0.3 * bm25_norm + 0.7 * dense_norm
            hybrid *= decay
            top_indices = np.argsort(hybrid)[::-1][:top_k]
            scores_used = hybrid[top_indices]
            method = "hybrid"
        except Exception:
            dense_norm *= decay
            top_indices = np.argsort(dense_norm)[::-1][:top_k]
            scores_used = dense_norm[top_indices]
            method = "dense"
    else:
        dense_norm *= decay
        top_indices = np.argsort(dense_norm)[::-1][:top_k]
        scores_used = dense_norm[top_indices]
        method = "dense"

    results = []
    for score, idx in zip(scores_used, top_indices):
        if idx < n_docs:
            results.append({
                "score": round(float(score), 4),
                "source": meta_list[idx]["source"],
                "text": docs[idx],
            })
    return results


def _keyword_fallback(project_id: int, query: str, top_k: int) -> list[dict]:
    """索引不可用时的关键词匹配降级方案

    从 DB 直接读取关键词相关的知识库条目。
    """
    from app.agents.services.knowledge_base import KnowledgeBaseService
    kb = KnowledgeBaseService(project_id)

    results = []
    query_lower = query.lower()

    # 搜索角色
    characters = kb.get_characters()
    for char in characters:
        char_text = f"{char.name} {getattr(char, 'core_motivation', '')} {getattr(char, 'knowledge_boundary', '')} {getattr(char, 'speech_style', '')}"
        if any(kw in char_text for kw in query_lower.split()):
            results.append({
                "score": 0.5,
                "source": f"character/{char.name}",
                "text": f"角色：{char.name}，核心动机：{getattr(char, 'core_motivation', '未设定')}，知识边界：{getattr(char, 'knowledge_boundary', '未设定')}",
            })

    # 搜索世界观
    ws = kb.get_world_setting()
    if ws and ws.core_concept:
        if any(kw in ws.core_concept for kw in query_lower.split()):
            results.append({
                "score": 0.5,
                "source": "world_setting",
                "text": f"核心理念：{ws.core_concept}",
            })

    # 搜索伏笔
    foreshadowings = kb.get_foreshadowings()
    for f in foreshadowings:
        if any(kw in f.content for kw in query_lower.split()):
            results.append({
                "score": 0.4,
                "source": f"foreshadowing/{f.id}",
                "text": f"伏笔：{f.content}（{f.level}/{f.status}）",
            })

    return results[:top_k]


# ========== 公共接口 ==========

class RetrievalService:
    """语义检索服务

    封装索引构建和检索操作，供 LangGraph 节点和 Agent 工具使用。
    """

    def __init__(self, project_id: int):
        self.project_id = project_id

    def rebuild_index(self) -> bool:
        """全量重建索引"""
        return build_index(self.project_id)

    def search(self, query: str, top_k: int = 5) -> list[dict]:
        """语义检索

        Args:
            query: 自然语言查询
            top_k: 返回结果数

        Returns:
            [{"score": float, "source": str, "text": str}]
        """
        return search(self.project_id, query, top_k)

    def is_index_available(self) -> bool:
        """检查索引是否可用"""
        index_path = _index_dir(self.project_id)
        return (
            os.path.exists(os.path.join(index_path, "meta.json"))
            and os.path.exists(os.path.join(index_path, "index.faiss"))
        )
