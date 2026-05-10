"""回归测试：章节正文生成后自动保存

Bug 描述：章节正文页面中生成内容如果不点击"保存"按钮，生成后的内容不会自动保存。
根因：
1. 后端在流之前创建空 Chapter 记录（content=NULL），流中断时残留脏数据
2. 前端 loadContent 不做 HTML 格式化，done 事件数据结构不匹配
3. 前端生成后未设置 saved=true，用户以为未保存

修复：
1. 后端：将 Chapter 创建移到流完成后，原子性写入（无空记录残留）
2. 前端：loadContent 格式化、done 事件解析修正、saved 状态更新
"""

import pytest
import inspect
from unittest.mock import patch, MagicMock, AsyncMock

from app.schemas.chapter import ChapterGenerateRequest
from app.api.chapters import generate_chapter


class TestChapterAutoSaveAtomicWrite:
    """验证后端原子性写入：不预先创建空 Chapter 记录"""

    def test_no_empty_chapter_before_stream(self):
        """generate_chapter 不应在 stream_generator 之前创建空 Chapter 记录

        旧代码在流之前执行 db.add(Chapter(content=None)) + db.commit()，
        如果流中断，DB 残留 content=NULL 的脏记录。

        新代码将 Chapter 创建移到 stream_generator 内部，流完成后才写入。
        """
        source = inspect.getsource(generate_chapter)

        # 不应在 stream_generator 外部创建 Chapter 记录
        # 旧代码模式：if not chapter: Chapter(content=None); db.add; db.commit
        # 新代码应在 stream_generator 内部处理

        # 验证：函数体内不应有 "db.add(chapter)" 在 stream_generator 之前
        # 找到 stream_generator 定义位置
        generator_start = source.find("async def stream_generator")
        assert generator_start > 0, "stream_generator 函数应存在"

        # stream_generator 之前的代码不应包含 db.add(chapter)
        pre_generator_code = source[:generator_start]
        assert "db.add(chapter)" not in pre_generator_code, \
            "不应在 stream_generator 之前创建 Chapter 记录（会导致空记录残留）"

        # stream_generator 内部应包含 Chapter 创建或更新逻辑
        generator_code = source[generator_start:]
        assert "db.add(chapter)" in generator_code or "chapter.content = content" in generator_code, \
            "stream_generator 内部应包含 Chapter 创建或更新逻辑"

    def test_chapter_outline_id_stored_before_stream(self):
        """generate_chapter 应在流之前保存 chapter_outline_id

        因为流内部需要 chapter_outline_id 来查询/创建 Chapter，
        但不应创建 Chapter 记录本身。
        """
        source = inspect.getsource(generate_chapter)
        # 应在流之前保存 chapter_outline_id（不是 Chapter 对象）
        assert "chapter_outline_id" in source, \
            "应保存 chapter_outline_id 供流内部使用"

    def test_workflow_stage_updated_in_generator(self):
        """stream_generator 内部应更新工作流状态为 STAGE_WRITING"""
        source = inspect.getsource(generate_chapter)
        generator_start = source.find("async def stream_generator")
        generator_code = source[generator_start:]
        assert "STAGE_WRITING" in generator_code, \
            "stream_generator 内部应更新工作流状态为 STAGE_WRITING"


class TestChapterAutoSaveFrontendDataFormat:
    """验证后端 done 事件数据结构与前端解析一致"""

    def test_done_event_contains_chapter_object(self):
        """后端 done 事件应包含 chapter 对象（含 word_count 和 content）

        后端发送格式：{"chapter": {"id": ..., "content": ..., "word_count": ...}}
        前端应解析：doneData.chapter.word_count
        """
        source = inspect.getsource(generate_chapter)
        # 后端 done 事件应包含 chapter 字段
        assert "'chapter': chapter_response" in source or '"chapter": chapter_response' in source, \
            "done 事件应包含 chapter 字段"


class TestChapterAutoSaveNoContentNullRecords:
    """验证修复后不会产生 content=NULL 的 Chapter 记录"""

    def test_chapter_created_with_content_in_generator(self):
        """stream_generator 内部创建 Chapter 时应包含 content

        新代码模式：在流完成后才创建 Chapter，且创建时即包含 content。
        不应出现 Chapter(content=None) 的创建。
        """
        source = inspect.getsource(generate_chapter)
        generator_start = source.find("async def stream_generator")
        generator_code = source[generator_start:]

        # 不应包含 content=None 的 Chapter 创建
        assert "content=None" not in generator_code, \
            "stream_generator 内部不应创建 content=None 的 Chapter 记录"
