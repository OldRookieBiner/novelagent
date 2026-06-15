"""章节正文存储"""

import logging
from typing import Optional

from app.agents.services.stores.base import _BaseStore
from app.models.chapter import Chapter
from app.models.outline import ChapterOutline

logger = logging.getLogger(__name__)


class ChapterStore(_BaseStore):
    """章节正文读写"""

    def get_by_number(self, chapter_number: int) -> Optional[dict]:
        """获取章节正文（含 content）"""
        with self.session(readonly=True) as db:
            co = db.query(ChapterOutline).filter(
                ChapterOutline.project_id == self.project_id,
                ChapterOutline.chapter_number == chapter_number,
            ).first()
            if not co:
                return None
            chapter = db.query(Chapter).filter(
                Chapter.chapter_outline_id == co.id
            ).first()
            if not chapter:
                return None
            result = self._to_dict(chapter)
            result["chapter_number"] = chapter_number
            result["title"] = co.title
            return result

    def save_content(self, chapter_number: int, content: str, word_count: int = 0) -> dict:
        """保存章节正文"""
        with self.session() as db:
            co = db.query(ChapterOutline).filter(
                ChapterOutline.project_id == self.project_id,
                ChapterOutline.chapter_number == chapter_number,
            ).first()
            if not co:
                raise ValueError(f"ChapterOutline for chapter {chapter_number} not found")

            chapter = db.query(Chapter).filter(
                Chapter.chapter_outline_id == co.id
            ).first()

            if chapter:
                chapter.content = content
                if word_count:
                    chapter.word_count = word_count
            else:
                chapter = Chapter(
                    chapter_outline_id=co.id,
                    content=content,
                    summary="",
                    word_count=word_count or len(content),
                )
                db.add(chapter)

            db.flush()
            db.refresh(chapter)
            result = self._to_dict(chapter)
            result["chapter_number"] = chapter_number
            return result

    def search_references(self, keywords: list[str], max_chapters: int = 50) -> list[dict]:
        """搜索包含关键词的章节段落"""
        with self.session(readonly=True) as db:
            results = []
            outlines = db.query(ChapterOutline).filter(
                ChapterOutline.project_id == self.project_id,
            ).order_by(ChapterOutline.chapter_number).limit(max_chapters).all()

            outline_ids = [co.id for co in outlines]
            chapters_map = {}
            if outline_ids:
                chapters = db.query(Chapter).filter(
                    Chapter.chapter_outline_id.in_(outline_ids),
                ).all()
                chapters_map = {ch.chapter_outline_id: ch for ch in chapters}

            for co in outlines:
                chapter = chapters_map.get(co.id)
                if not chapter or not chapter.content:
                    continue

                paragraphs = chapter.content.split("\n")
                matching = []
                for i, para in enumerate(paragraphs):
                    if not para.strip():
                        continue
                    for kw in keywords:
                        if kw in para:
                            matching.append({"index": i, "text": para[:200]})
                            break

                if matching:
                    results.append({
                        "chapter_number": co.chapter_number,
                        "title": co.title or "",
                        "matching_paragraphs": matching,
                    })
            return results


    def save_review_result(self, chapter_number: int, passed: bool, feedback: str, result: dict) -> dict:
        """保存审核结果

        Args:
            chapter_number: 章节号
            passed: 是否通过审核
            feedback: LLM 原始审核反馈文本
            result: 结构化审核结果 dict

        Returns:
            更新后的章节 dict
        """
        with self.session() as db:
            co = db.query(ChapterOutline).filter(
                ChapterOutline.project_id == self.project_id,
                ChapterOutline.chapter_number == chapter_number,
            ).first()
            if not co:
                raise ValueError(f"ChapterOutline for chapter {chapter_number} not found")

            chapter = db.query(Chapter).filter(
                Chapter.chapter_outline_id == co.id
            ).first()
            if not chapter:
                raise ValueError(f"Chapter for chapter {chapter_number} not found")

            chapter.review_passed = passed
            chapter.review_feedback = feedback
            chapter.review_result = result

            db.flush()
            db.refresh(chapter)
            r = self._to_dict(chapter)
            r["chapter_number"] = chapter_number
            return r

    def save_rewrite_result(self, chapter_number: int, new_content: str) -> dict:
        """保存重写结果，清空审核状态，递增 rewrite_count

        Args:
            chapter_number: 章节号
            new_content: 重写后的章节正文

        Returns:
            更新后的章节 dict
        """
        with self.session() as db:
            co = db.query(ChapterOutline).filter(
                ChapterOutline.project_id == self.project_id,
                ChapterOutline.chapter_number == chapter_number,
            ).first()
            if not co:
                raise ValueError(f"ChapterOutline for chapter {chapter_number} not found")

            chapter = db.query(Chapter).filter(
                Chapter.chapter_outline_id == co.id
            ).first()
            if not chapter:
                raise ValueError(f"Chapter for chapter {chapter_number} not found")

            chapter.content = new_content
            chapter.word_count = len(new_content)
            chapter.rewrite_count = (chapter.rewrite_count or 0) + 1
            chapter.review_passed = False
            chapter.review_result = None
            chapter.review_feedback = None

            db.flush()
            db.refresh(chapter)
            r = self._to_dict(chapter)
            r["chapter_number"] = chapter_number
            return r

    # --- 内部方法 ---

    def _read_with_session(self, db, chapter_number: int) -> Optional[dict]:
        co = db.query(ChapterOutline).filter(
            ChapterOutline.project_id == self.project_id,
            ChapterOutline.chapter_number == chapter_number,
        ).first()
        if not co:
            return None
        chapter = db.query(Chapter).filter(
            Chapter.chapter_outline_id == co.id
        ).first()
        if not chapter:
            return None
        result = self._to_dict(chapter)
        result["chapter_number"] = chapter_number
        result["title"] = co.title
        return result

    def _create_with_session(self, db, data: dict) -> dict:
        chapter_number = data.pop("chapter_number", None)
        co = None
        if chapter_number:
            co = db.query(ChapterOutline).filter(
                ChapterOutline.project_id == self.project_id,
                ChapterOutline.chapter_number == chapter_number,
            ).first()
            if not co:
                co = ChapterOutline(
                    project_id=self.project_id,
                    chapter_number=chapter_number,
                    title=data.get("title", ""),
                )
                db.add(co)
                db.flush()

        chapter = Chapter(
            chapter_outline_id=co.id if co else data.get("chapter_outline_id"),
            content=data.get("content", ""),
            summary=data.get("summary", ""),
            word_count=data.get("word_count", 0),
        )
        db.add(chapter)
        db.flush()
        db.refresh(chapter)
        result = self._to_dict(chapter)
        if chapter_number:
            result["chapter_number"] = chapter_number
        return result

    def _read_all_with_session(self, db) -> list[dict]:
        """单次 session 内批量读取全部章节（含 chapter_number 和 title）

        Chapter 模型没有 project_id，需通过 ChapterOutline JOIN 查询。
        """
        from app.models.chapter import Chapter as ChapterModel
        from app.models.outline import ChapterOutline

        results = []
        outlines = db.query(ChapterOutline).filter(
            ChapterOutline.project_id == self.project_id,
        ).order_by(ChapterOutline.chapter_number).all()

        outline_ids = [co.id for co in outlines]
        chapters_map = {}
        if outline_ids:
            chapters = db.query(ChapterModel).filter(
                ChapterModel.chapter_outline_id.in_(outline_ids),
            ).all()
            chapters_map = {ch.chapter_outline_id: ch for ch in chapters}

        for co in outlines:
            chapter = chapters_map.get(co.id)
            if chapter:
                result = self._to_dict(chapter)
                result["chapter_number"] = co.chapter_number
                result["title"] = co.title
                results.append(result)

        return results

    def _read_by_number_with_session(self, db, chapter_number: int) -> dict | None:
        """单次 session 内按章节号读取（需 JOIN ChapterOutline）"""
        co = db.query(ChapterOutline).filter(
            ChapterOutline.project_id == self.project_id,
            ChapterOutline.chapter_number == chapter_number,
        ).first()
        if not co:
            return None
        chapter = db.query(Chapter).filter(
            Chapter.chapter_outline_id == co.id
        ).first()
        if not chapter:
            return None
        result = self._to_dict(chapter)
        result["chapter_number"] = chapter_number
        result["title"] = co.title
        return result
