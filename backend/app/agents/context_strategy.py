"""上下文策略 — 管理章节生成时的前文上下文构建方式"""

from abc import ABC, abstractmethod


class ContextStrategy(ABC):
    """上下文策略基类"""

    @abstractmethod
    def build_previous_context(
        self,
        written_chapters: list[dict],
        current_chapter: int,
        chapter_outlines: list[dict] | None = None,
        arcs: list[dict] | None = None,
        chapter_summaries: list[dict] | None = None,
    ) -> str:
        """构建前文上下文文本

        Args:
            written_chapters: 已写章节列表（含 content）
            current_chapter: 当前章节号
            chapter_outlines: 章节大纲列表（远章概要的数据源，可选）
            arcs: 弧列表（长篇摘要策略使用，可选）
            chapter_summaries: 章节摘要列表（长篇摘要策略使用，可选）
        """
        pass


class FulltextContentStrategy(ContextStrategy):
    """全文策略：所有已写章节全文放入上下文"""

    def build_previous_context(
        self,
        written_chapters: list[dict],
        current_chapter: int,
        chapter_outlines: list[dict] | None = None,
        arcs: list[dict] | None = None,
        chapter_summaries: list[dict] | None = None,
    ) -> str:
        parts = []
        for ch in written_chapters:
            ch_num = ch.get("chapter_number", 0)
            if ch_num < current_chapter:
                title = ch.get("title", "")
                content = ch.get("content", "")
                if content:
                    parts.append(f"第{ch_num}章《{title}》\n{content}")
        if not parts:
            return "（这是第一章，没有前文）"
        return "\n\n---\n\n".join(parts)


class HybridContentStrategy(ContextStrategy):
    """混合策略：近 N 章全文 + 远章大纲概要

    近章提供完整的语言风格和衔接参考，
    远章提供情节线索和伏笔追踪（从 chapter_outlines 提取，无需 LLM 调用）。
    """

    def __init__(self, recent_count: int = 3):
        # 防御性校验：近章数量限制在 [1, 10]
        self.recent_count = max(1, min(recent_count, 10))

    def build_previous_context(
        self,
        written_chapters: list[dict],
        current_chapter: int,
        chapter_outlines: list[dict] | None = None,
        arcs: list[dict] | None = None,
        chapter_summaries: list[dict] | None = None,
    ) -> str:
        if not written_chapters:
            return "（这是第一章，没有前文）"

        # 分离近章和远章
        recent = []
        distant_nums = []
        for ch in written_chapters:
            ch_num = ch.get("chapter_number", 0)
            if ch_num < current_chapter:
                if current_chapter - ch_num <= self.recent_count:
                    recent.append(ch)
                else:
                    distant_nums.append(ch_num)

        parts = []

        # 远章：从 chapter_outlines 提取概要
        if distant_nums and chapter_outlines:
            outline_map = {co.get("chapter_number"): co for co in chapter_outlines}
            distant_parts = []
            for ch_num in sorted(distant_nums):
                co = outline_map.get(ch_num, {})
                title = co.get("title", "")
                plot = co.get("plot", "")
                conflict = co.get("conflict", "")
                hook = co.get("hook", "")
                summary = f"第{ch_num}章《{title}》"
                if plot:
                    summary += f"\n情节：{plot[:200]}"
                if conflict:
                    summary += f"\n冲突：{conflict}"
                if hook:
                    summary += f"\n钩子：{hook}"
                distant_parts.append(summary)
            if distant_parts:
                parts.append("【前文概要】\n" + "\n\n".join(distant_parts))

        # 近章：全文
        if recent:
            recent_parts = []
            for ch in sorted(recent, key=lambda x: x.get("chapter_number", 0)):
                title = ch.get("title", "")
                content = ch.get("content", "")
                recent_parts.append(f"第{ch.get('chapter_number', 0)}章《{title}》\n{content}")
            parts.append("【近期全文】\n" + "\n\n---\n\n".join(recent_parts))

        return "\n\n---\n\n".join(parts) if parts else "（这是第一章，没有前文）"


class SummaryContentStrategy(ContextStrategy):
    """摘要策略：前面弧概要 + 当前弧章节摘要 + 近N章全文"""

    def __init__(self, recent_count: int = 3):
        self.recent_count = max(1, min(recent_count, 10))

    def build_previous_context(
        self,
        written_chapters: list[dict],
        current_chapter: int,
        chapter_outlines: list[dict] | None = None,
        arcs: list[dict] | None = None,
        chapter_summaries: list[dict] | None = None,
    ) -> str:
        if not written_chapters:
            return "（这是第一章，没有前文）"

        parts = []

        # 1. 前面弧：只取弧概要
        if arcs:
            current_arc = self._find_arc_for_chapter(arcs, current_chapter)
            if current_arc:
                current_key = (current_arc.get("volume_number", 1), current_arc.get("arc_number", 0))
                sorted_arcs = sorted(arcs, key=lambda a: (a.get("volume_number", 1), a.get("arc_number", 0)))
                previous_arcs = [a for a in sorted_arcs if (a.get("volume_number", 1), a.get("arc_number", 0)) < current_key]
                if previous_arcs:
                    arc_parts = []
                    for a in previous_arcs:
                        summary = f"《{a.get('title', '')}》"
                        if a.get("summary"):
                            summary += f"\n{a['summary']}"
                        arc_parts.append(summary)
                    parts.append("【前弧概要】\n" + "\n\n".join(arc_parts))

        # 2. 当前弧内已写章节：从 chapter_summaries 取摘要（排除近N章）
        if arcs:
            current_arc = self._find_arc_for_chapter(arcs, current_chapter)
            if current_arc:
                current_arc_chapters = [
                    ch for ch in written_chapters
                    if ch.get("chapter_number", 0) < current_chapter
                    and self._is_in_arc(ch, current_arc, arcs, chapter_outlines)
                    and current_chapter - ch.get("chapter_number", 0) > self.recent_count
                ]
                if current_arc_chapters:
                    summary_map = {}
                    if chapter_summaries:
                        summary_map = {s.get("chapter_number"): s.get("summary") for s in chapter_summaries if s.get("summary")}
                    summary_parts = []
                    for ch in sorted(current_arc_chapters, key=lambda x: x.get("chapter_number", 0)):
                        ch_num = ch.get("chapter_number", 0)
                        text = f"第{ch_num}章"
                        ch_summary = summary_map.get(ch_num)
                        if ch_summary:
                            text += f"\n{ch_summary}"
                        else:
                            outline = self._find_outline(ch, chapter_outlines)
                            if outline and outline.get("plot"):
                                text += f"\n（大纲）{outline['plot'][:200]}"
                        summary_parts.append(text)
                    parts.append("【当前弧摘要】\n" + "\n\n".join(summary_parts))

        # 3. 近N章：取 content 全文
        recent = [
            ch for ch in written_chapters
            if ch.get("chapter_number", 0) < current_chapter
            and current_chapter - ch.get("chapter_number", 0) <= self.recent_count
        ]
        if recent:
            recent_parts = []
            for ch in sorted(recent, key=lambda x: x.get("chapter_number", 0)):
                title = ch.get("title", "")
                content = ch.get("content", "")
                recent_parts.append(f"第{ch.get('chapter_number', 0)}章《{title}》\n{content}")
            parts.append("【近期全文】\n" + "\n\n---\n\n".join(recent_parts))

        return "\n\n---\n\n".join(parts) if parts else "（这是第一章，没有前文）"

    def _find_arc_for_chapter(self, arcs: list[dict], chapter_number: int) -> dict | None:
        """根据章节号找到所属弧（通过累积 chapter_count 推算）"""
        sorted_arcs = sorted(arcs, key=lambda a: (a.get("volume_number", 1), a.get("arc_number", 0)))
        cumulative = 0
        for arc in sorted_arcs:
            cumulative += arc.get("chapter_count", 0)
            if chapter_number <= cumulative:
                return arc
        return sorted_arcs[-1] if sorted_arcs else None

    def _is_in_arc(self, chapter: dict, arc: dict, arcs: list[dict], chapter_outlines: list[dict] | None = None) -> bool:
        """判断章节是否属于指定弧

        通过 (volume_number, arc_number) 元组比较匹配，
        因为 state 中的 arcs 是纯 dict（无 DB id），arc_id 匹配不可靠。
        """
        actual_arc = self._find_arc_for_chapter(arcs, chapter.get("chapter_number", 0))
        if actual_arc is None:
            return False
        actual_key = (actual_arc.get("volume_number", 1), actual_arc.get("arc_number", 0))
        target_key = (arc.get("volume_number", 1), arc.get("arc_number", 0))
        return actual_key == target_key

    def _find_outline(self, chapter: dict, chapter_outlines: list[dict] | None) -> dict | None:
        if not chapter_outlines:
            return None
        for co in chapter_outlines:
            if co.get("chapter_number") == chapter.get("chapter_number"):
                return co
        return None


# 策略名到类的映射
_STRATEGY_MAP = {
    "fulltext": FulltextContentStrategy,
    "hybrid": HybridContentStrategy,
    "summary": SummaryContentStrategy,
}


def get_context_strategy(target_words: int, strategy_name: str | None = None) -> ContextStrategy:
    """根据策略名或目标字数选择上下文策略

    Args:
        target_words: 目标字数（仅当 strategy_name 为 None 时用作回退）
        strategy_name: 用户选择的策略名（fulltext/hybrid/summary），优先级高于 target_words
    """
    if strategy_name and strategy_name in _STRATEGY_MAP:
        return _STRATEGY_MAP[strategy_name]()
    # 回退：当前默认全文策略
    return FulltextContentStrategy()
