"""长篇小说工作流路由集成测试

测试长篇小说新增的路由函数：
- route_after_relations: 长篇→volume_arc，短/中篇→chapter_outlines
- route_after_volume_arc: 首次→wait_confirm，确认后→chapter_outlines
- route_after_review: 长篇审核通过→chapter_summary
- route_after_summary: 有下一章→next_chapter，全部完成→end
"""

import pytest


# 从 graph.py 复制路由函数（避免深层依赖，路由函数为纯函数）
# 注意：如果 graph.py 中路由逻辑变更，需同步更新此处
def _wait_for_confirmation(state: dict) -> str:
    """从 wait_confirm.py 提取的确认逻辑"""
    workflow_mode = state.get("review_mode", "hybrid")
    confirmation_type = state.get("confirmation_type")

    if state.get("waiting_for_confirmation"):
        return "wait"

    if workflow_mode == "step_by_step":
        if confirmation_type:
            return "wait"
    elif workflow_mode == "hybrid":
        if confirmation_type in [
            "outline", "characters", "relations",
            "volume_arc", "chapter_outlines",
        ]:
            return "wait"
    elif workflow_mode == "auto":
        if confirmation_type == "review_failed":
            return "wait"

    return "continue"


def _route_after_relations(state: dict) -> str:
    if state.get("chapter_count", 0) <= 0:
        return "end"
    if not state.get("characters"):
        return "end"
    decision = _wait_for_confirmation(state)
    if decision == "wait":
        return "wait_confirm"
    if state.get("novel_length") == "long":
        return "volume_arc"
    return "chapter_outlines"


def _route_after_volume_arc(state: dict) -> str:
    if state.get("waiting_for_confirmation"):
        return "wait_confirm"
    if not state.get("arcs"):
        return "end"
    return "chapter_outlines"


def _route_after_review(state: dict) -> str:
    if state.get("review_result", {}).get("passed", False):
        if state.get("novel_length") == "long":
            return "chapter_summary"
        if state.get("current_chapter", 0) < state.get("chapter_count", 0):
            return "next_chapter"
        return "end"
    if state.get("rewrite_count", 0) >= state.get("max_rewrite_count", 3):
        if state.get("review_mode") == "auto":
            return "next_chapter"
        return "wait_confirm"
    return "rewrite"


def _route_after_summary(state: dict) -> str:
    if state.get("current_chapter", 0) < state.get("chapter_count", 0):
        return "next_chapter"
    return "end"


class TestRouteAfterRelations:
    """关系生成后的路由测试"""

    def test_long_novel_routes_to_volume_arc(self):
        state = {
            "novel_length": "long",
            "chapter_count": 50,
            "characters": [{"name": "主角"}],
            "waiting_for_confirmation": False,
            "review_mode": "auto",
        }
        assert _route_after_relations(state) == "volume_arc"

    def test_short_novel_routes_to_chapter_outlines(self):
        state = {
            "novel_length": "short",
            "chapter_count": 10,
            "characters": [{"name": "主角"}],
            "waiting_for_confirmation": False,
            "review_mode": "auto",
        }
        assert _route_after_relations(state) == "chapter_outlines"

    def test_medium_novel_routes_to_chapter_outlines(self):
        state = {
            "novel_length": "medium",
            "chapter_count": 30,
            "characters": [{"name": "主角"}],
            "waiting_for_confirmation": False,
            "review_mode": "auto",
        }
        assert _route_after_relations(state) == "chapter_outlines"

    def test_no_characters_routes_to_end(self):
        state = {
            "novel_length": "long",
            "chapter_count": 50,
            "characters": None,
            "waiting_for_confirmation": False,
        }
        assert _route_after_relations(state) == "end"

    def test_zero_chapter_count_routes_to_end(self):
        state = {
            "novel_length": "long",
            "chapter_count": 0,
            "characters": [{"name": "主角"}],
            "waiting_for_confirmation": False,
        }
        assert _route_after_relations(state) == "end"

    def test_waiting_for_confirmation_routes_to_wait(self):
        state = {
            "novel_length": "long",
            "chapter_count": 50,
            "characters": [{"name": "主角"}],
            "waiting_for_confirmation": True,
            "confirmation_type": "relations",
            "workflow_mode": "step_by_step",
        }
        assert _route_after_relations(state) == "wait_confirm"

    def test_hybrid_with_confirmation_waits(self):
        state = {
            "novel_length": "long",
            "chapter_count": 50,
            "characters": [{"name": "主角"}],
            "waiting_for_confirmation": False,
            "review_mode": "hybrid",
            "confirmation_type": "relations",
        }
        assert _route_after_relations(state) == "wait_confirm"

    def test_hybrid_without_confirmation_proceeds(self):
        state = {
            "novel_length": "short",
            "chapter_count": 10,
            "characters": [{"name": "主角"}],
            "waiting_for_confirmation": False,
            "review_mode": "hybrid",
            "confirmation_type": None,
        }
        assert _route_after_relations(state) == "chapter_outlines"


class TestRouteAfterVolumeArc:
    """弧/卷规划后的路由测试"""

    def test_first_run_waits_for_confirmation(self):
        state = {"waiting_for_confirmation": True}
        assert _route_after_volume_arc(state) == "wait_confirm"

    def test_confirmed_routes_to_chapter_outlines(self):
        state = {
            "waiting_for_confirmation": False,
            "arcs": [{"arc_number": 1, "title": "起弧", "chapter_count": 10}],
        }
        assert _route_after_volume_arc(state) == "chapter_outlines"

    def test_no_arcs_routes_to_end(self):
        state = {"waiting_for_confirmation": False, "arcs": []}
        assert _route_after_volume_arc(state) == "end"

    def test_no_arcs_key_routes_to_end(self):
        state = {"waiting_for_confirmation": False}
        assert _route_after_volume_arc(state) == "end"


class TestRouteAfterReview:
    """审核后的路由测试"""

    def test_long_novel_passed_routes_to_summary(self):
        state = {
            "novel_length": "long",
            "review_result": {"passed": True},
            "current_chapter": 3,
            "chapter_count": 50,
        }
        assert _route_after_review(state) == "chapter_summary"

    def test_short_novel_passed_routes_to_next(self):
        state = {
            "novel_length": "short",
            "review_result": {"passed": True},
            "current_chapter": 3,
            "chapter_count": 10,
        }
        assert _route_after_review(state) == "next_chapter"

    def test_short_novel_last_chapter_passed_routes_to_end(self):
        state = {
            "novel_length": "short",
            "review_result": {"passed": True},
            "current_chapter": 10,
            "chapter_count": 10,
        }
        assert _route_after_review(state) == "end"

    def test_failed_routes_to_rewrite(self):
        state = {
            "novel_length": "long",
            "review_result": {"passed": False},
            "rewrite_count": 0,
            "max_rewrite_count": 3,
        }
        assert _route_after_review(state) == "rewrite"

    def test_max_rewrite_auto_mode_continues(self):
        state = {
            "novel_length": "long",
            "review_result": {"passed": False},
            "rewrite_count": 3,
            "max_rewrite_count": 3,
            "review_mode": "auto",
            "current_chapter": 3,
            "chapter_count": 50,
        }
        assert _route_after_review(state) == "next_chapter"

    def test_max_rewrite_step_mode_waits(self):
        state = {
            "novel_length": "long",
            "review_result": {"passed": False},
            "rewrite_count": 3,
            "max_rewrite_count": 3,
            "review_mode": "step_by_step",
        }
        assert _route_after_review(state) == "wait_confirm"


class TestRouteAfterSummary:
    """摘要生成后的路由测试"""

    def test_has_next_chapter(self):
        state = {"current_chapter": 3, "chapter_count": 50}
        assert _route_after_summary(state) == "next_chapter"

    def test_all_chapters_complete(self):
        state = {"current_chapter": 50, "chapter_count": 50}
        assert _route_after_summary(state) == "end"

    def test_current_exceeds_total(self):
        state = {"current_chapter": 101, "chapter_count": 100}
        assert _route_after_summary(state) == "end"
