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
        token_budget: int | None = None,
    ) -> str:
        """构建前文上下文文本

        Args:
            written_chapters: 已写章节列表（含 content）
            current_chapter: 当前章节号
            chapter_outlines: 章节大纲列表（远章概要的数据源，可选）
            arcs: 弧纲列表（弧线摘要策略使用，可选）
            chapter_summaries: 章节摘要列表（弧线摘要策略使用，可选）
            token_budget: 可用于前文上下文的 token 预算，None 表示不限制
        """
        pass


class FulltextContentStrategy(ContextStrategy):
    """全文策略：所有已写章节全文放入上下文

    当 token_budget 不为 None 时，从最近的章节开始逆序填充，
    超出预算则截断较早的章节。
    """

    def build_previous_context(
        self,
        written_chapters: list[dict],
        current_chapter: int,
        chapter_outlines: list[dict] | None = None,
        arcs: list[dict] | None = None,
        chapter_summaries: list[dict] | None = None,
        token_budget: int | None = None,
    ) -> str:
        from app.agents.token_budget import estimate_tokens

        context_parts = []
        used_tokens = 0

        # 逆序遍历，优先保留最近章节
        for chapter in reversed(written_chapters):
            ch_num = chapter.get("chapter_number", 0)
            if ch_num >= current_chapter:
                continue
            content = chapter.get("content", "")
            if not content:
                continue
            title = chapter.get("title", "")
            part = f"第{ch_num}章《{title}》\n{content}"
            part_tokens = estimate_tokens(part)

            if token_budget is not None:
                if used_tokens + part_tokens > token_budget:
                    break
                used_tokens += part_tokens

            context_parts.append(part)

        if not context_parts:
            return "（这是第一章，没有前文）"

        context_parts.reverse()
        return "\n\n---\n\n".join(context_parts)


class HybridContentStrategy(ContextStrategy):
    """混合策略：近 N 章全文 + 远章大纲概要

    近章提供完整的语言风格和衔接参考，
    远章提供情节线索和伏笔追踪（从 chapter_outlines 提取，无需 LLM 调用）。

    当 token_budget 不为 None 时：
    - 近章全文占 60% 预算，从最近章节逆序填充
    - 远章概要占剩余预算
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
        token_budget: int | None = None,
    ) -> str:
        from app.agents.token_budget import estimate_tokens

        if not written_chapters:
            return "（这是第一章，没有前文）"

        effective_budget = token_budget if token_budget is not None else float('inf')
        fulltext_budget = int(effective_budget * 0.6) if token_budget is not None else None

        # 近章全文（逆序填充，优先最近）
        recent_parts = []
        covered_numbers = set()
        used_tokens = 0

        for chapter in reversed(written_chapters):
            ch_num = chapter.get("chapter_number", 0)
            if ch_num >= current_chapter:
                continue
            # 无预算时用 recent_count 控制
            if not token_budget and current_chapter - ch_num > self.recent_count:
                continue

            content = chapter.get("content", "")
            if not content:
                continue
            title = chapter.get("title", "")
            part = f"第{ch_num}章《{title}》\n{content}"
            part_tokens = estimate_tokens(part)

            if fulltext_budget and used_tokens + part_tokens > fulltext_budget:
                break
            used_tokens += part_tokens
            covered_numbers.add(ch_num)
            recent_parts.append(part)

            # 无预算时限制近章数量
            if not token_budget and len(recent_parts) >= self.recent_count:
                break

        recent_parts.reverse()

        # 远章概要
        outline_parts = []
        if chapter_outlines:
            outline_map = {co.get("chapter_number"): co for co in chapter_outlines}
            # 找出不在近章范围内的远章号
            distant_nums = []
            for ch in written_chapters:
                ch_num = ch.get("chapter_number", 0)
                if ch_num < current_chapter and ch_num not in covered_numbers:
                    distant_nums.append(ch_num)

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
                summary_tokens = estimate_tokens(summary)

                if token_budget and used_tokens + summary_tokens > effective_budget:
                    break
                used_tokens += summary_tokens
                outline_parts.append(summary)

        # 组装结果
        parts = []
        if outline_parts:
            parts.append("【前文概要】\n" + "\n\n".join(outline_parts))
        if recent_parts:
            parts.append("【近期全文】\n" + "\n\n---\n\n".join(recent_parts))

        return "\n\n---\n\n".join(parts) if parts else "（这是第一章，没有前文）"


class SummaryContentStrategy(ContextStrategy):
    """摘要策略：近章全文 + 当前弧摘要 + 前弧摘要

    三级上下文结构：
    1. 近章全文（40% 预算）：提供语言风格和衔接参考
    2. 当前弧摘要（70% 预算）：当前弧纲概要 + 弧内章节摘要
    3. 前弧摘要（100% 预算）：之前弧的概要信息
    """

    def __init__(self, recent_count: int = 2):
        self.recent_count = max(1, min(recent_count, 5))

    def build_previous_context(
        self,
        written_chapters: list[dict],
        current_chapter: int,
        chapter_outlines: list[dict] | None = None,
        arcs: list[dict] | None = None,
        chapter_summaries: list[dict] | None = None,
        token_budget: int | None = None,
    ) -> str:
        from app.agents.token_budget import estimate_tokens

        effective_budget = token_budget if token_budget is not None else float('inf')
        used_tokens = 0
        result_parts = []

        # ===== Phase 1: 近章全文（40% 预算）=====
        fulltext_budget = int(effective_budget * 0.4) if token_budget is not None else None
        fulltext_parts = []
        covered_numbers = set()

        for chapter in reversed(written_chapters):
            ch_num = chapter.get("chapter_number", 0)
            if ch_num >= current_chapter:
                continue
            # 无预算时用 recent_count 控制
            if not token_budget and current_chapter - ch_num > self.recent_count:
                continue

            content = chapter.get("content", "")
            if not content:
                continue
            title = chapter.get("title", "")
            part = f"第{ch_num}章《{title}》\n{content}"
            part_tokens = estimate_tokens(part)

            if fulltext_budget and used_tokens + part_tokens > fulltext_budget:
                break
            used_tokens += part_tokens
            covered_numbers.add(ch_num)
            fulltext_parts.append(part)

            # 无预算时限制近章数量
            if not token_budget and len(fulltext_parts) >= self.recent_count:
                break

        fulltext_parts.reverse()
        result_parts.extend(fulltext_parts)

        # ===== Phase 2: 当前弧摘要（70% 预算）=====
        arc_budget = int(effective_budget * 0.7) if token_budget is not None else None
        if arcs and chapter_summaries:
            # 查找当前弧
            current_arc = None
            for arc in arcs:
                arc_start = arc.get("start_chapter", 0)
                arc_end = arc.get("end_chapter", 999999)
                if arc_start <= current_chapter <= arc_end:
                    current_arc = arc
                    break

            if current_arc:
                arc_title = current_arc.get("title", "")
                arc_summary = current_arc.get("summary", "")
                arc_part = f"## 当前弧：{arc_title}\n{arc_summary}"
                arc_tokens = estimate_tokens(arc_part)

                if not arc_budget or used_tokens + arc_tokens <= arc_budget:
                    used_tokens += arc_tokens
                    result_parts.append(arc_part)

                # 弧内章节摘要（排除已有全文的章节）
                for cs in chapter_summaries:
                    cn = cs.get("chapter_number", 0)
                    if cn >= current_chapter or cn in covered_numbers:
                        continue
                    summary_text = f"第{cn}章摘要：{cs.get('summary', '')}"
                    summary_tokens = estimate_tokens(summary_text)
                    if arc_budget and used_tokens + summary_tokens > arc_budget:
                        break
                    used_tokens += summary_tokens
                    result_parts.append(summary_text)

        # ===== Phase 3: 前弧摘要（100% 预算）=====
        if arcs:
            for arc in arcs:
                arc_end = arc.get("end_chapter", 0)
                if arc_end >= current_chapter:
                    continue
                arc_title = arc.get("title", "")
                arc_summary = arc.get("summary", "")
                arc_text = f"弧《{arc_title}》：{arc_summary}"
                arc_tokens = estimate_tokens(arc_text)
                if token_budget and used_tokens + arc_tokens > effective_budget:
                    break
                used_tokens += arc_tokens
                result_parts.append(arc_text)

        if not result_parts:
            return "（这是第一章，没有前文）"

        return "\n\n---\n\n".join(result_parts)


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
