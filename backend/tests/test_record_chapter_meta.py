"""record_chapter_meta 工具测试 — 重点覆盖 P1.1B 未回收伏笔提醒"""
import pytest
from unittest.mock import patch, MagicMock

from app.agents.tools.creation.record_chapter_meta import record_chapter_meta


def _build_mock_kb(due_or_overdue: list[dict] | None = None):
    """构造一个 KB mock，仅覆盖本测试用到的方法。"""
    kb = MagicMock()
    # 时间线 — upsert 路径：existing=None → create
    kb.timelines.get_by_chapter_number.return_value = None
    kb.timelines.create_timeline_entry.return_value = {"id": 1}
    kb.timelines.update_timeline_entry.return_value = {"id": 1}
    # 伏笔
    kb.foreshadowings.create.return_value = {"id": 99, "content": "x"}
    kb.foreshadowings.update.return_value = {"id": 99}
    kb.foreshadowings.list_due_or_overdue.return_value = due_or_overdue or []
    return kb


@pytest.mark.asyncio
async def test_warning_appended_when_due_foreshadowings_unreclaimed():
    """到期但本次未传入回收 ID 时，warnings 含 unreclaimed_foreshadowings"""
    due = [
        {"id": 5, "content": "未回收的到期伏笔", "expected_resolve_chapter": 3, "status": "active"}
    ]
    kb = _build_mock_kb(due_or_overdue=due)
    with patch("app.agents.tools.creation.record_chapter_meta._kb", return_value=kb):
        result = await record_chapter_meta.ainvoke({
            "chapter_number": 3,
            "timeline_summary": "第三章",
            "reclaimed_foreshadowing_ids": "[]",
        })

    warnings = result.get("warnings", [])
    steps = [w.get("step") for w in warnings]
    assert "unreclaimed_foreshadowings" in steps
    target = next(w for w in warnings if w.get("step") == "unreclaimed_foreshadowings")
    assert target["unreclaimed_preview"][0]["id"] == 5


@pytest.mark.asyncio
async def test_no_warning_when_due_foreshadowing_is_reclaimed():
    """到期伏笔在本次提交的 reclaimed_ids 中时，不应产生 warning"""
    due = [
        {"id": 5, "content": "已经被本次回收", "expected_resolve_chapter": 3, "status": "active"}
    ]
    kb = _build_mock_kb(due_or_overdue=due)
    with patch("app.agents.tools.creation.record_chapter_meta._kb", return_value=kb):
        result = await record_chapter_meta.ainvoke({
            "chapter_number": 3,
            "timeline_summary": "第三章",
            "reclaimed_foreshadowing_ids": "[5]",
        })
    steps = [w.get("step") for w in result.get("warnings", [])]
    assert "unreclaimed_foreshadowings" not in steps


@pytest.mark.asyncio
async def test_no_warning_when_no_due_foreshadowings():
    """没有到期伏笔时不产生 warning"""
    kb = _build_mock_kb(due_or_overdue=[])
    with patch("app.agents.tools.creation.record_chapter_meta._kb", return_value=kb):
        result = await record_chapter_meta.ainvoke({
            "chapter_number": 1,
            "timeline_summary": "第一章",
        })
    steps = [w.get("step") for w in result.get("warnings", [])]
    assert "unreclaimed_foreshadowings" not in steps


@pytest.mark.asyncio
async def test_unreclaimed_check_failure_does_not_block():
    """list_due_or_overdue 抛错时仍返回结果（捕获为 unreclaimed_foreshadowings_check warning）"""
    kb = _build_mock_kb()
    kb.foreshadowings.list_due_or_overdue.side_effect = RuntimeError("db down")
    with patch("app.agents.tools.creation.record_chapter_meta._kb", return_value=kb):
        result = await record_chapter_meta.ainvoke({
            "chapter_number": 3,
            "timeline_summary": "第三章",
        })
    steps = [w.get("step") for w in result.get("warnings", [])]
    assert "unreclaimed_foreshadowings_check" in steps
    assert "chapter_number" in result
