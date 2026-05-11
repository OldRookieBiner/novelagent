"""Tests for workflow API and LangGraph integration"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.checkpoint import WorkflowCheckpoint
from app.agents.graph import create_novel_graph


class TestWorkflowGraph:
    """Tests for LangGraph workflow"""

    def test_create_graph(self):
        """Should create workflow graph successfully"""
        graph = create_novel_graph()
        assert graph is not None

    def test_graph_nodes_exist(self):
        """Should have all required nodes"""
        graph = create_novel_graph()
        # 验证节点存在
        # LangGraph 编译后的图通过 nodes 属性获取节点
        node_names = list(graph.nodes.keys())
        assert "outline_generation_node" in node_names
        assert "chapter_outlines_node" in node_names
        assert "generate_chapter_content_node" in node_names
        assert "review_node" in node_names


class TestCheckpointSaver:
    """Tests for PostgreSQL checkpoint saver"""

    def test_checkpoint_saver_creation(self):
        """Should create checkpoint saver"""
        from app.agents.checkpointer import PostgresCheckpointSaver

        saver = PostgresCheckpointSaver(project_id=1, thread_id="test")
        assert saver.project_id == 1
        assert saver.thread_id == "test"


class TestWorkflowAPI:
    """Tests for workflow API endpoints"""

    @pytest.fixture
    def project_with_outline(self, client: TestClient, auth_headers: dict) -> int:
        """创建项目并返回 ID"""
        response = client.post(
            "/api/projects/", json={"name": "Test Novel"}, headers=auth_headers
        )
        return response.json()["id"]

    def test_get_workflow_state_no_checkpoint(
        self, client: TestClient, auth_headers: dict, project_with_outline: int
    ):
        """Should return state without checkpoint"""
        response = client.get(
            f"/api/projects/{project_with_outline}/workflow/state", headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["has_checkpoint"] is False

    def test_get_workflow_state_with_checkpoint(
        self,
        client: TestClient,
        auth_headers: dict,
        project_with_outline: int,
        db: Session,
    ):
        """Should return state with checkpoint"""
        # 创建测试检查点
        checkpoint = WorkflowCheckpoint(
            project_id=project_with_outline,
            thread_id="main",
            checkpoint={
                "channel_values": {
                    "stage": "writing",
                    "current_chapter": 3,
                    "chapter_count": 10,
                    "written_chapters": [{"chapter_number": 1}, {"chapter_number": 2}],
                }
            },
        )
        db.add(checkpoint)
        db.commit()

        response = client.get(
            f"/api/projects/{project_with_outline}/workflow/state", headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["has_checkpoint"] is True
        # 验证 current_state 中包含检查点数据
        current_state = data["current_state"]
        assert current_state is not None
        assert current_state.get("current_chapter") == 3
        assert len(current_state.get("written_chapters", [])) == 2

    def test_cancel_workflow(
        self,
        client: TestClient,
        auth_headers: dict,
        project_with_outline: int,
        db: Session,
    ):
        """Should cancel workflow and delete checkpoint"""
        # 创建测试检查点
        checkpoint = WorkflowCheckpoint(
            project_id=project_with_outline,
            thread_id="main",
            checkpoint={"channel_values": {"stage": "outline"}},
        )
        db.add(checkpoint)
        db.commit()

        # 取消工作流
        response = client.post(
            f"/api/projects/{project_with_outline}/workflow/cancel",
            headers=auth_headers,
        )

        assert response.status_code == 200
        assert response.json()["message"] == "Workflow cancelled"

        # 验证检查点已删除
        remaining = (
            db.query(WorkflowCheckpoint)
            .filter(WorkflowCheckpoint.project_id == project_with_outline)
            .count()
        )
        assert remaining == 0

    def test_cleanup_workflow(
        self,
        client: TestClient,
        auth_headers: dict,
        project_with_outline: int,
        db: Session,
    ):
        """Should cleanup workflow checkpoints"""
        # 创建测试检查点
        checkpoint = WorkflowCheckpoint(
            project_id=project_with_outline,
            thread_id="default",
            checkpoint={"channel_values": {"stage": "outline"}},
        )
        db.add(checkpoint)
        db.commit()

        # 清理工作流
        response = client.post(
            f"/api/projects/{project_with_outline}/workflow/cleanup",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["deleted"] >= 1

        # 验证检查点已删除
        remaining = (
            db.query(WorkflowCheckpoint)
            .filter(WorkflowCheckpoint.project_id == project_with_outline)
            .count()
        )
        assert remaining == 0

    def test_replan_workflow_clears_data(
        self,
        client: TestClient,
        auth_headers: dict,
        project_with_outline: int,
        db: Session,
    ):
        """Should clear checkpoints, characters, relations, chapter outlines on replan"""
        from app.models.outline import Outline, ChapterOutline
        from app.models.character import Character, Relation

        # 创建检查点
        checkpoint = WorkflowCheckpoint(
            project_id=project_with_outline,
            thread_id="default",
            checkpoint={"channel_values": {"stage": "relations"}},
        )
        db.add(checkpoint)

        # 创建大纲（带生成数据）
        outline = db.query(Outline).filter(Outline.project_id == project_with_outline).first()
        if outline:
            outline.title = "测试大纲"
            outline.summary = "测试概述"
            outline.confirmed = True

        # 创建人物
        character = Character(
            project_id=project_with_outline,
            name="测试人物",
            role="主角",
        )
        db.add(character)
        db.flush()

        # 创建关系
        relation = Relation(
            project_id=project_with_outline,
            character_a_id=character.id,
            character_b_id=character.id,
            relation_type="测试",
        )
        db.add(relation)

        # 创建章节大纲
        chapter_outline = ChapterOutline(
            project_id=project_with_outline,
            chapter_number=1,
            title="第一章",
        )
        db.add(chapter_outline)
        db.commit()

        # 调用 replan
        response = client.post(
            f"/api/projects/{project_with_outline}/workflow/replan",
            headers=auth_headers,
            json={},
        )

        # replan 返回 SSE 流（200）或因 LLM 报错
        # 无论哪种，数据清理应已完成
        # 验证检查点已删除
        remaining_checkpoints = (
            db.query(WorkflowCheckpoint)
            .filter(WorkflowCheckpoint.project_id == project_with_outline)
            .count()
        )
        assert remaining_checkpoints == 0

        # 验证人物已删除
        remaining_characters = (
            db.query(Character)
            .filter(Character.project_id == project_with_outline)
            .count()
        )
        assert remaining_characters == 0

        # 验证章节大纲已删除
        remaining_outlines = (
            db.query(ChapterOutline)
            .filter(ChapterOutline.project_id == project_with_outline)
            .count()
        )
        assert remaining_outlines == 0

        # 验证大纲生成字段已清除，但 collected_info 保留
        db.refresh(outline)
        assert outline.title is None
        assert outline.summary is None
        assert outline.confirmed is False
        assert outline.collected_info is not None

    def test_workflow_not_found(self, client: TestClient, auth_headers: dict):
        """Should return 404 for non-existent project"""
        response = client.get(
            "/api/projects/99999/workflow/state", headers=auth_headers
        )
        assert response.status_code == 404
