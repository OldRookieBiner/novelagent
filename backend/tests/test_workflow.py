"""Tests for workflow API and LangGraph integration"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.project import Project
from app.models.outline import Outline
from app.models.checkpoint import WorkflowCheckpoint
from app.agents.state import NovelState, WORKFLOW_MODE_HYBRID
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
        assert "generate_outline" in node_names
        assert "generate_chapter_outlines" in node_names
        assert "generate_chapter_content" in node_names
        assert "review_chapter" in node_names


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
            "/api/projects/",
            json={"name": "Test Novel"},
            headers=auth_headers
        )
        return response.json()["id"]

    def test_get_workflow_state_no_checkpoint(self, client: TestClient, auth_headers: dict, project_with_outline: int):
        """Should return state without checkpoint"""
        response = client.get(
            f"/api/projects/{project_with_outline}/workflow/state",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["has_checkpoint"] is False

    def test_get_workflow_state_with_checkpoint(
        self,
        client: TestClient,
        auth_headers: dict,
        project_with_outline: int,
        db: Session
    ):
        """Should return state with checkpoint"""
        # 创建测试检查点
        checkpoint = WorkflowCheckpoint(
            project_id=project_with_outline,
            thread_id="default",
            checkpoint={
                "channel_values": {
                    "stage": "writing",
                    "current_chapter": 3,
                    "chapter_count": 10,
                    "written_chapters": [{"chapter_number": 1}, {"chapter_number": 2}]
                }
            }
        )
        db.add(checkpoint)
        db.commit()

        response = client.get(
            f"/api/projects/{project_with_outline}/workflow/state",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["has_checkpoint"] is True
        # 验证 current_state 中包含检查点数据
        current_state = data["current_state"]
        assert current_state is not None
        assert current_state.get("current_chapter") == 3
        assert len(current_state.get("written_chapters", [])) == 2

    def test_cancel_workflow(self, client: TestClient, auth_headers: dict, project_with_outline: int, db: Session):
        """Should cancel workflow and delete checkpoint"""
        # 创建测试检查点
        checkpoint = WorkflowCheckpoint(
            project_id=project_with_outline,
            thread_id="default",
            checkpoint={"channel_values": {"stage": "outline"}}
        )
        db.add(checkpoint)
        db.commit()

        # 取消工作流
        response = client.post(
            f"/api/projects/{project_with_outline}/workflow/cancel",
            headers=auth_headers
        )

        assert response.status_code == 200
        assert response.json()["message"] == "Workflow cancelled"

        # 验证检查点已删除
        remaining = db.query(WorkflowCheckpoint).filter(
            WorkflowCheckpoint.project_id == project_with_outline
        ).count()
        assert remaining == 0

    def test_workflow_not_found(self, client: TestClient, auth_headers: dict):
        """Should return 404 for non-existent project"""
        response = client.get(
            "/api/projects/99999/workflow/state",
            headers=auth_headers
        )
        assert response.status_code == 404
