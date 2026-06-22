"""Outline API 测试 — confirmed 降级为展示书签后的行为

方案 2：confirmed 不再作为编辑门禁，仅标记「作者定稿」。
回归保护：已确认大纲仍可编辑；confirm 幂等；章节数无需先确认。
"""

import pytest
from app.models.project import Project
from app.models.outline import Outline


@pytest.fixture
def project_with_outline(db, test_user):
    """创建一个带已确认大纲的项目"""
    project = Project(user_id=test_user.id, name="测试项目")
    db.add(project)
    db.commit()
    db.refresh(project)

    outline = Outline(
        project_id=project.id,
        title="原标题",
        summary="原摘要",
        plot_points=[{"order": 1, "event": "开端"}],
        chapter_count_suggested=20,
        chapter_count_confirmed=True,
        confirmed=True,
    )
    db.add(outline)
    db.commit()
    db.refresh(outline)
    return project, outline


def test_update_confirmed_outline_succeeds(client, auth_headers, project_with_outline):
    """已确认大纲仍可通过 PUT 编辑（不再返回 400）"""
    project, _ = project_with_outline
    resp = client.put(
        f"/api/projects/{project.id}/outline",
        json={"title": "新标题", "summary": "新摘要"},
        headers=auth_headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["title"] == "新标题"
    assert data["summary"] == "新摘要"
    # confirmed 标记保持不变（编辑不重置定稿状态）
    assert data["confirmed"] is True


def test_update_collected_info_on_confirmed_outline(client, auth_headers, project_with_outline):
    """已确认大纲仍可更新 collected_info"""
    project, _ = project_with_outline
    resp = client.put(
        f"/api/projects/{project.id}/outline/collected-info",
        json={"genre": "科幻"},
        headers=auth_headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["collected_info"]["genre"] == "科幻"


def test_confirm_is_idempotent(client, auth_headers, project_with_outline):
    """重复确认已确认大纲不再报错（幂等）"""
    project, _ = project_with_outline
    resp = client.put(
        f"/api/projects/{project.id}/outline/confirm",
        headers=auth_headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["confirmed"] is True


def test_set_chapter_count_without_confirm(client, auth_headers, db, test_user):
    """未确认大纲也能设置章节数（不再要求先确认）"""
    project = Project(user_id=test_user.id, name="草稿项目")
    db.add(project)
    db.commit()
    db.refresh(project)
    outline = Outline(
        project_id=project.id, title="草稿", summary="草稿摘要", confirmed=False
    )
    db.add(outline)
    db.commit()

    resp = client.put(
        f"/api/projects/{project.id}/outline/chapter-count",
        json={"chapter_count": 12},
        headers=auth_headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["chapter_count_suggested"] == 12
