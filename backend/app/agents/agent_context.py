# backend/app/agents/agent_context.py
"""Agent 上下文构建器

按优先级将项目数据注入 Agent system message，受 token budget 约束。
与 agent_graph.py 分离，方便独立测试。
"""

import json
import re

from app.database import SessionLocal
from app.models.outline import Outline, ChapterOutline
from app.models.character import Character
from app.models.chapter import Chapter


class BudgetTracker:
    """Token 预算追踪器"""

    def __init__(self, max_tokens: int):
        self.max = max_tokens
        self.used = 0

    def can_add(self, tokens: int) -> bool:
        return self.used + tokens <= self.max

    def add(self, tokens: int):
        self.used += tokens

    def remaining(self) -> int:
        return max(0, self.max - self.used)


def estimate_tokens(text: str) -> int:
    """粗略估算 token 数：中文字数 × 2，英文单词数 × 1.3"""
    chinese_chars = len(re.findall(r'[一-鿿]', text))
    english_words = len(re.findall(r'[a-zA-Z]+', text))
    return int(chinese_chars * 2 + english_words * 1.3)


def build_project_context(
    project_id: int,
    current_chapter_number: int | None = None,
    max_tokens: int = 12000,
) -> dict:
    """构建项目上下文，按优先级注入原文，受 token budget 约束

    优先级：
    P1: 当前章节完整正文
    P2: 完整大纲
    P3: 角色列表
    P4: 当前章节大纲
    P5: 所有章节标题+状态
    P6: 前后章节摘要
    """
    db = SessionLocal()
    try:
        budget = BudgetTracker(max_tokens)
        context: dict = {}

        # P1: 当前章节完整正文
        if current_chapter_number:
            chapter = db.query(Chapter).filter(
                Chapter.project_id == project_id,
                Chapter.chapter_number == current_chapter_number,
            ).first()
            if chapter and chapter.content:
                content_tokens = estimate_tokens(chapter.content)
                if budget.can_add(content_tokens):
                    context["current_chapter"] = {
                        "chapter_number": current_chapter_number,
                        "title": chapter.title,
                        "content": chapter.content,
                    }
                    budget.add(content_tokens)

        # P2: 完整大纲
        outline = db.query(Outline).filter(Outline.project_id == project_id).first()
        if outline:
            outline_data = {
                "title": outline.title,
                "summary": outline.summary or "",
                "plot_points": outline.plot_points or [],
                "chapter_count": outline.chapter_count_confirmed or outline.chapter_count_suggested or 0,
                "confirmed": outline.confirmed,
            }
            outline_json = json.dumps(outline_data, ensure_ascii=False)
            outline_tokens = estimate_tokens(outline_json)
            if budget.can_add(outline_tokens):
                context["outline"] = outline_data
                budget.add(outline_tokens)

        # P3: 角色列表
        characters = db.query(Character).filter(Character.project_id == project_id).all()
        char_list = []
        for c in characters:
            char_info = f"{c.name}（{c.role}）：{c.personality or ''}。动机：{c.core_motivation or ''}"
            char_tokens = estimate_tokens(char_info)
            if budget.can_add(char_tokens):
                char_list.append({
                    "id": c.id,
                    "name": c.name,
                    "role": c.role,
                    "personality": c.personality or "",
                    "core_motivation": c.core_motivation or "",
                    "growth_arc": c.growth_arc or "",
                })
                budget.add(char_tokens)
        context["characters"] = char_list

        # P4: 当前章节大纲
        if current_chapter_number:
            co = db.query(ChapterOutline).filter(
                ChapterOutline.project_id == project_id,
                ChapterOutline.chapter_number == current_chapter_number,
            ).first()
            if co:
                co_data = {
                    "title": co.title,
                    "plot": co.plot or "",
                    "conflict": co.conflict or "",
                    "ending": co.ending or "",
                    "target_words": co.target_words or 3000,
                }
                co_json = json.dumps(co_data, ensure_ascii=False)
                if budget.can_add(estimate_tokens(co_json)):
                    context["current_outline"] = co_data
                    budget.add(estimate_tokens(co_json))

        # P5: 所有章节标题+状态
        chapter_outlines = db.query(ChapterOutline).filter(
            ChapterOutline.project_id == project_id
        ).order_by(ChapterOutline.chapter_number).all()
        all_chapters = []
        for co in chapter_outlines:
            chapter = db.query(Chapter).filter(
                Chapter.project_id == project_id,
                Chapter.chapter_number == co.chapter_number,
            ).first()
            entry = f"第{co.chapter_number}章《{co.title}》"
            if chapter and chapter.content:
                entry += f"（已写，{len(chapter.content)}字）"
            else:
                entry += "（待写）"
            entry_tokens = estimate_tokens(entry)
            if budget.can_add(entry_tokens):
                all_chapters.append(entry)
                budget.add(entry_tokens)
        context["all_chapters"] = all_chapters

        # P6: 前后章节摘要
        if current_chapter_number:
            adjacent = []
            for offset in [-2, -1, 1]:
                cn = current_chapter_number + offset
                if cn < 1:
                    continue
                ch = db.query(Chapter).filter(
                    Chapter.project_id == project_id,
                    Chapter.chapter_number == cn,
                ).first()
                if ch and ch.content:
                    summary_text = f"第{cn}章：{ch.content[:150]}"
                    adj_tokens = estimate_tokens(summary_text)
                    if budget.can_add(adj_tokens):
                        adjacent.append(summary_text)
                        budget.add(adj_tokens)
            if adjacent:
                context["adjacent_summaries"] = adjacent

        context["_budget_used"] = budget.used
        return context
    finally:
        db.close()
