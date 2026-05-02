"""测试大纲生成失败时的工作流行为"""

from app.agents.graph import route_after_outline


def test_route_after_outline_aborts_when_outline_invalid():
    """大纲无效时工作流应直接结束"""
    state = {
        "project_id": 1,
        "outline_valid": False,
        "review_mode": "auto",
        "waiting_for_confirmation": False,
        "confirmation_type": None,
    }
    result = route_after_outline(state)
    assert result == "end"


def test_route_after_outline_continues_when_outline_valid_auto():
    """大纲有效时 auto 模式应继续执行"""
    state = {
        "project_id": 1,
        "outline_valid": True,
        "review_mode": "auto",
        "waiting_for_confirmation": False,
        "confirmation_type": None,
    }
    result = route_after_outline(state)
    assert result == "create_characters"


def test_route_after_outline_defaults_to_end_when_missing():
    """缺少 outline_valid 字段时默认为无效（中止）"""
    state = {
        "project_id": 1,
        "review_mode": "auto",
    }
    result = route_after_outline(state)
    assert result == "end"


def test_route_after_outline_waits_in_step_by_step_mode():
    """step_by_step 模式 + 有效大纲应等待确认"""
    state = {
        "project_id": 1,
        "outline_valid": True,
        "review_mode": "step_by_step",
        "waiting_for_confirmation": False,
        "confirmation_type": "outline",
    }
    result = route_after_outline(state)
    assert result == "wait_confirm"


def test_route_after_outline_continues_in_step_by_step_no_type():
    """step_by_step 模式但无 confirmation_type 应继续（但初始调用时通常有这个标志）"""
    state = {
        "project_id": 1,
        "outline_valid": True,
        "review_mode": "step_by_step",
        "waiting_for_confirmation": False,
        "confirmation_type": None,
    }
    result = route_after_outline(state)
    assert result == "create_characters"
