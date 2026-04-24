# backend/tests/test_chapter_content_clean.py
import pytest
from app.agents.nodes.chapter_generation import clean_chapter_content


class TestCleanChapterContent:
    """测试章节内容清理函数"""

    def test_removes_trailing_number_with_newlines(self):
        """测试移除结尾数字（带换行）"""
        content = "正文内容\n\n3247"
        result = clean_chapter_content(content)
        assert result == "正文内容"

    def test_removes_trailing_number_single_newline(self):
        """测试移除结尾数字（单换行）"""
        content = "正文内容\n3247"
        result = clean_chapter_content(content)
        assert result == "正文内容"

    def test_preserves_number_in_paragraph(self):
        """测试保留段落中的数字"""
        content = "正文内容3247"
        result = clean_chapter_content(content)
        assert result == "正文内容3247"

    def test_no_change_without_trailing_number(self):
        """测试无结尾数字时不变"""
        content = "正文内容"
        result = clean_chapter_content(content)
        assert result == "正文内容"

    def test_removes_multiple_trailing_numbers(self):
        """测试移除多个结尾数字行"""
        content = "正文内容\n3247\n\n5678"
        result = clean_chapter_content(content)
        assert result == "正文内容"

    def test_handles_empty_content(self):
        """测试空内容"""
        content = ""
        result = clean_chapter_content(content)
        assert result == ""

    def test_removes_trailing_number_with_spaces(self):
        """测试移除带空格的结尾数字"""
        content = "正文内容\n3247  "
        result = clean_chapter_content(content)
        assert result == "正文内容"

    def test_preserves_content_with_numbers_in_middle(self):
        """测试保留中间有数字的内容"""
        content = "正文内容\n3247字\n结尾"
        result = clean_chapter_content(content)
        assert result == "正文内容\n3247字\n结尾"
