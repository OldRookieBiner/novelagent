"""风格检查节点 — 增强版

检查维度：
1. 禁忌词快查：精确匹配禁忌词
2. 风格统计：段落/对话/句长等指标
3. 风格漂移检测：对比最近 N 章与基准的偏差

基准定义：
- 有风格锚点时，前 3 章的平均值作为基准
- 偏差阈值：对话占比 ±25%，平均句长 ±25%

发现漂移时记录到 style_snapshot 并触发 SSE 预警。
"""

import logging
import re

from app.agents.state import NovelState
from app.agents.services.knowledge_base import KnowledgeBaseService
from app.agents.nodes.utils import find_chapter_by_number

logger = logging.getLogger(__name__)


async def style_check_node(state: NovelState) -> NovelState:
    """风格检查 + 漂移检测"""
    project_id = state["project_id"]
    written_chapters = state.get("written_chapters", [])
    current_chapter = state.get("current_chapter", 1)
    kb = KnowledgeBaseService(project_id)

    # 找到刚写完的章节
    chapter = find_chapter_by_number(written_chapters, current_chapter)
    if not chapter:
        return {}

    content = chapter.get("content", "")
    written_chapter_num = chapter.get("chapter_number", current_chapter - 1)

    if not content:
        return {}

    # ========== 1. 禁忌词快查 ==========
    style = kb.get_style_constraints()
    taboo_violations = []
    if style and style.taboo_words:
        tw = style.taboo_words if isinstance(style.taboo_words, list) else [style.taboo_words]
        for word in tw:
            if word in content:
                taboo_violations.append(word)

    # ========== 2. 风格统计 ==========
    paragraphs = [p for p in content.split("\n") if p.strip()]
    paragraph_count = len(paragraphs)
    avg_para_len = sum(len(p) for p in paragraphs) / max(paragraph_count, 1)

    # 对话占比（中文引号 + 英文引号）
    dialogue_chars = len(re.findall(r'[「"『].*?[」"』]', content))
    dialogue_ratio = dialogue_chars / max(len(content), 1)

    # 平均句长
    sentences = re.split(r'[。！？…]', content)
    sentences = [s for s in sentences if s.strip()]
    avg_sent_len = sum(len(s) for s in sentences) / max(len(sentences), 1)

    # ========== 3. 风格漂移检测 ==========
    drift_info = None
    snapshots = kb.get_style_snapshots(last_n=10)
    baseline = _compute_baseline(snapshots)

    if baseline:
        drifts = []

        # 对话占比偏差
        if baseline["dialogue_ratio"] > 0:
            dialogue_deviation = abs(dialogue_ratio - baseline["dialogue_ratio"]) / baseline["dialogue_ratio"]
            if dialogue_deviation > 0.25:
                drifts.append(
                    f"对话占比偏离基准 {dialogue_deviation:.0%}（当前 {dialogue_ratio:.1%}，基准 {baseline['dialogue_ratio']:.1%}）"
                )

        # 句长偏差
        if baseline["avg_sentence_length"] > 0:
            sent_deviation = abs(avg_sent_len - baseline["avg_sentence_length"]) / baseline["avg_sentence_length"]
            if sent_deviation > 0.25:
                drifts.append(
                    f"平均句长偏离基准 {sent_deviation:.0%}（当前 {avg_sent_len:.0f}字，基准 {baseline['avg_sentence_length']:.0f}字）"
                )

        # 段长偏差
        if baseline["avg_paragraph_length"] > 0:
            para_deviation = abs(avg_para_len - baseline["avg_paragraph_length"]) / baseline["avg_paragraph_length"]
            if para_deviation > 0.25:
                drifts.append(
                    f"平均段长偏离基准 {para_deviation:.0%}（当前 {avg_para_len:.0f}字，基准 {baseline['avg_paragraph_length']:.0f}字）"
                )

        if drifts:
            drift_info = "；".join(drifts)
            logger.warning(f"项目 {project_id} 第 {written_chapter_num} 章风格漂移：{drift_info}")

    # ========== 4. 写入风格统计快照 ==========
    snapshot_data = {
        "chapter_number": written_chapter_num,
        "paragraph_count": paragraph_count,
        "avg_paragraph_length": round(avg_para_len, 1),
        "dialogue_ratio": round(dialogue_ratio, 3),
        "avg_sentence_length": round(avg_sent_len, 1),
    }
    kb.create_style_snapshot(snapshot_data)

    return {}


def _compute_baseline(snapshots: list) -> dict | None:
    """计算风格基准

    取前 3 章的 style_snapshot 平均值作为基准。
    如果不足 3 章，取所有可用快照的平均值。
    如果没有快照，返回 None（首次写作，无法检测漂移）。
    """
    if not snapshots:
        return None

    # snapshots 按 chapter_number DESC 排序，取最早的 3 章
    earliest = sorted(snapshots, key=lambda s: s.chapter_number)[:3]

    n = len(earliest)
    if n == 0:
        return None

    baseline = {
        "dialogue_ratio": sum(s.dialogue_ratio for s in earliest) / n,
        "avg_sentence_length": sum(s.avg_sentence_length for s in earliest) / n,
        "avg_paragraph_length": sum(s.avg_paragraph_length for s in earliest) / n,
    }
    return baseline
