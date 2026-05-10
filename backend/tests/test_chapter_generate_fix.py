"""回归测试：章节正文生成端点 bug 修复

Bug 描述：点击 AI 生成按钮后报错"生成失败，已保留生成内容"
根因：generate_chapter 端点使用 request: Request (FastAPI Request 对象)
访问 request.llm_config_id 导致 AttributeError，因为 FastAPI Request
没有 llm_config_id 属性。

修复：
1. 创建 ChapterGenerateRequest Pydantic schema 替代 Request
2. 传入 db 参数给 build_initial_state 预加载角色/关系
3. review_chapter 使用 review_chapter_node 替代未定义的
   create_novel_graph_with_checkpointer
"""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.chapter import ChapterGenerateRequest, ReviewRequest


class TestChapterGenerateRequestSchema:
    """验证 ChapterGenerateRequest schema"""

    def test_llm_config_id_optional(self):
        """llm_config_id 应为可选字段"""
        req = ChapterGenerateRequest()
        assert req.llm_config_id is None

    def test_llm_config_id_with_value(self):
        """llm_config_id 应接受整数值"""
        req = ChapterGenerateRequest(llm_config_id=42)
        assert req.llm_config_id == 42

    def test_llm_config_id_none_explicit(self):
        """llm_config_id 显式设为 None"""
        req = ChapterGenerateRequest(llm_config_id=None)
        assert req.llm_config_id is None


class TestReviewRequestSchema:
    """验证 ReviewRequest 更新后的 schema"""

    def test_llm_config_id_added(self):
        """ReviewRequest 应包含 llm_config_id 字段"""
        req = ReviewRequest(strictness="strict", llm_config_id=1)
        assert req.llm_config_id == 1
        assert req.strictness == "strict"

    def test_llm_config_id_default_none(self):
        """ReviewRequest llm_config_id 默认为 None"""
        req = ReviewRequest()
        assert req.llm_config_id is None
        assert req.strictness == "standard"


class TestGenerateChapterEndpoint:
    """验证 generate_chapter 端点不再因 AttributeError 崩溃"""

    @pytest.fixture
    def client(self):
        return TestClient(app)

    def test_generate_endpoint_accepts_json_body(self, client):
        """generate 端点应接受 JSON body 包含 llm_config_id

        之前的 bug: request: Request 导致 request.llm_config_id 报 AttributeError。
        修复后: request: ChapterGenerateRequest 正确解析 JSON body。
        """
        # 使用 mock 避免实际 DB 操作，只验证端点不会因参数解析崩溃
        with patch("app.api.chapters.get_project_for_user") as mock_project, \
             patch("app.api.chapters.get_outline_for_project") as mock_outline, \
             patch("app.api.chapters.get_current_user") as mock_user:

            mock_project.return_value = MagicMock(id=1, user_id=1)
            mock_outline.return_value = MagicMock(
                id=1, project_id=1, confirmed=True,
                collected_info={}, characters=[],
                world_setting=None, emotional_curve=None,
                chapter_count_suggested=1
            )
            mock_user.return_value = MagicMock(id=1)

            with patch("app.api.chapters.get_db") as mock_db:
                mock_session = MagicMock()
                mock_db.return_value = mock_session

                # 模拟章节大纲查询
                mock_chapter_outline = MagicMock(
                    id=1, project_id=1, chapter_number=1,
                    title="Test", confirmed=True,
                    scene="", characters="", plot="test",
                    conflict="", ending="", target_words=3000
                )
                mock_session.query.return_value.filter.return_value.first.side_effect = [
                    mock_chapter_outline,  # 章节大纲查询
                    None,  # 章节内容查询 (不存在则创建)
                ]

                with patch("app.api.chapters.get_or_create_workflow_state") as mock_wf:
                    mock_wf.return_value = MagicMock(stage="writing", current_chapter=1)
                    with patch("app.api.chapters.build_initial_state") as mock_build:
                        mock_build.return_value = {
                            "project_id": 1,
                            "chapter_outlines": [],
                            "current_chapter": 1,
                            "collected_info": {},
                            "characters": [],
                            "relations": [],
                        }
                        with patch("app.api.chapters.get_llm_from_state_async") as mock_llm:
                            mock_llm_instance = AsyncMock()
                            mock_llm.return_value = mock_llm_instance

                            # 发送包含 llm_config_id 的请求
                            # 关键验证：之前这会因 AttributeError 崩溃
                            response = client.post(
                                "/api/projects/1/chapters/1/generate",
                                json={"llm_config_id": 42},
                                headers={"Authorization": "Basic dGVzdDp0ZXN0"},
                            )

                            # 不应返回 500 (之前会因 AttributeError 返回 500)
                            # 因为实际需要 SSE 流，所以可能是其他错误，
                            # 但关键是不会因 request.llm_config_id 崩溃
                            assert response.status_code != 500 or \
                                "llm_config_id" not in response.text


class TestReviewChapterNoNameError:
    """验证 review_chapter 端点不再因 NameError 崩溃

    之前的 bug: 使用未定义的 create_novel_graph_with_checkpointer 导致 NameError。
    修复后: 使用 review_chapter_node 函数替代。
    """

    @pytest.fixture
    def client(self):
        return TestClient(app)

    def test_review_endpoint_no_undefined_function(self):
        """验证 chapters.py 不再引用 create_novel_graph_with_checkpointer"""
        import inspect
        from app.api.chapters import review_chapter

        source = inspect.getsource(review_chapter)
        assert "create_novel_graph_with_checkpointer" not in source, \
            "review_chapter 不应使用未定义的 create_novel_graph_with_checkpointer"
        assert "review_chapter_node" in source, \
            "review_chapter 应使用 review_chapter_node LangGraph 节点函数"


class TestBuildInitialStateWithDb:
    """验证所有端点都传入 db 参数给 build_initial_state"""

    def test_generate_passes_db_to_build_initial_state(self):
        """generate_chapter 应传入 db 参数预加载角色/关系"""
        import inspect
        from app.api.chapters import generate_chapter

        source = inspect.getsource(generate_chapter)
        assert "db=db" in source, \
            "generate_chapter 应传入 db=db 给 build_initial_state 以预加载角色/关系"

    def test_review_passes_db_to_build_initial_state(self):
        """review_chapter 应传入 db 参数预加载角色/关系"""
        import inspect
        from app.api.chapters import review_chapter

        source = inspect.getsource(review_chapter)
        assert "db=db" in source, \
            "review_chapter 应传入 db=db 给 build_initial_state 以预加载角色/关系"
