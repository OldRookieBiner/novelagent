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
    ) -> str:
        """构建前文上下文文本

        Args:
            written_chapters: 已写章节列表（含 content）
            current_chapter: 当前章节号
            chapter_outlines: 章节大纲列表（远章概要的数据源，可选）
        """
        pass


class FulltextContentStrategy(ContextStrategy):
    """全文策略：所有已写章节全文放入上下文"""

    def build_previous_context(
        self,
        written_chapters: list[dict],
        current_chapter: int,
        chapter_outlines: list[dict] | None = None,
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
        self.recent_count = recent_count

    def build_previous_context(
        self,
        written_chapters: list[dict],
        current_chapter: int,
        chapter_outlines: list[dict] | None = None,
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
    """摘要策略（Phase 4 实现）"""

    def build_previous_context(self, written_chapters, current_chapter, chapter_outlines=None):
        raise NotImplementedError("SummaryContentStrategy 尚未实现")


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
