"""上下文策略 — 管理章节生成时的前文上下文构建方式"""

from abc import ABC, abstractmethod


class ContextStrategy(ABC):
    """上下文策略基类"""

    @abstractmethod
    def build_previous_context(self, written_chapters: list[dict], current_chapter: int) -> str:
        """构建前文上下文文本"""
        pass


class FulltextContentStrategy(ContextStrategy):
    """全文策略：所有已写章节全文放入上下文"""

    def build_previous_context(self, written_chapters: list[dict], current_chapter: int) -> str:
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
    """混合策略（Phase 4 实现）"""
    def build_previous_context(self, written_chapters, current_chapter):
        raise NotImplementedError("HybridContentStrategy 尚未实现")


class SummaryContentStrategy(ContextStrategy):
    """摘要策略（Phase 4 实现）"""
    def build_previous_context(self, written_chapters, current_chapter):
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
    # 回退：根据目标字数自动选择
    if target_words <= 100000:
        return FulltextContentStrategy()
    else:
        return FulltextContentStrategy()
