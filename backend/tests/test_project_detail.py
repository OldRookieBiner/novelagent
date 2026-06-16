"""测试 ProjectDetailResponse 的 is_completed 和 is_busy 计算逻辑"""
import pytest
from app.schemas.project import (
    ProjectDetailResponse,
    ProjectListResponse,
    WorkflowStateResponse,
)
from datetime import datetime, timezone


def _make_workflow_state(project_id=1):
    return WorkflowStateResponse(
        id=1,
        project_id=project_id,
        stage="writing",
        current_chapter=1,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


def test_is_completed_when_all_chapters_done():
    """所有章节审核通过 → is_completed=True"""
    resp = ProjectDetailResponse(
        id=1, user_id=1, name="test", target_words=100000,
        total_words=50000, created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        workflow_state=_make_workflow_state(),
        chapter_count=10, completed_chapters=10,
        progress_percentage=100.0,
        is_completed=True, is_busy=False,
    )
    assert resp.is_completed is True


def test_is_completed_false_when_no_chapters():
    """无章节 → is_completed=False（不能误判新项目为已完结）"""
    resp = ProjectDetailResponse(
        id=1, user_id=1, name="test", target_words=100000,
        total_words=0, created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        workflow_state=_make_workflow_state(),
        chapter_count=0, completed_chapters=0,
        progress_percentage=0.0,
        is_completed=False, is_busy=False,
    )
    assert resp.is_completed is False


def test_is_completed_false_when_incomplete():
    """部分章节完成 → is_completed=False"""
    resp = ProjectDetailResponse(
        id=1, user_id=1, name="test", target_words=100000,
        total_words=50000, created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        workflow_state=_make_workflow_state(),
        chapter_count=10, completed_chapters=5,
        progress_percentage=50.0,
        is_completed=False, is_busy=False,
    )
    assert resp.is_completed is False


def test_is_busy_reflects_project_state():
    """is_busy 应正确反映项目的 busy 状态"""
    resp = ProjectDetailResponse(
        id=1, user_id=1, name="test", target_words=100000,
        total_words=50000, created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        workflow_state=_make_workflow_state(),
        chapter_count=10, completed_chapters=5,
        progress_percentage=50.0,
        is_completed=False, is_busy=True,
    )
    assert resp.is_busy is True


def test_list_response_accepts_detail():
    """ProjectListResponse.projects 应接受 ProjectDetailResponse"""
    detail = ProjectDetailResponse(
        id=1, user_id=1, name="test", target_words=100000,
        total_words=0, created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        workflow_state=_make_workflow_state(),
        chapter_count=0, completed_chapters=0,
        progress_percentage=0.0,
        is_completed=False, is_busy=False,
    )
    resp = ProjectListResponse(projects=[detail], total=1)
    assert len(resp.projects) == 1
    assert isinstance(resp.projects[0], ProjectDetailResponse)


def test_list_projects_returns_is_completed_and_is_busy(client, auth_headers):
    """GET /api/projects/ 应返回 is_completed 和 is_busy 字段"""
    # 先创建项目
    response = client.post(
        "/api/projects/",
        json={"name": "test project", "target_words": 100000},
        headers=auth_headers,
    )
    assert response.status_code == 201

    # 列表接口
    response = client.get("/api/projects/", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1
    project = data["projects"][0]
    assert "is_completed" in project
    assert "is_busy" in project
    assert project["is_completed"] is False
    assert project["is_busy"] is False
