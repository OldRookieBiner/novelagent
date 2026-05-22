from app.agents.constants import STYLE_EXEMPLARS, STYLE_EXEMPLAR_RULES, STYLE_EXEMPLAR_DEFAULT


def test_style_exemplars_has_all_categories():
    required = ["action", "dialogue", "emotion", "environment", "opening"]
    for cat in required:
        assert cat in STYLE_EXEMPLARS
        assert len(STYLE_EXEMPLARS[cat]) >= 1


def test_style_exemplar_rules_format():
    for field, keywords, categories in STYLE_EXEMPLAR_RULES:
        assert isinstance(field, str)
        assert isinstance(keywords, list) and len(keywords) > 0
        assert isinstance(categories, list) and len(categories) > 0
        for cat in categories:
            assert cat in STYLE_EXEMPLARS


def test_select_style_exemplars_first_chapter():
    from app.agents.nodes.chapter_generation import _select_style_exemplars
    result = _select_style_exemplars({"chapter_number": 1, "conflict": "", "hook": ""})
    assert "开篇" in result or "对话" in result


def test_select_style_exemplars_action_conflict():
    from app.agents.nodes.chapter_generation import _select_style_exemplars
    result = _select_style_exemplars({"chapter_number": 5, "conflict": "两人打斗", "hook": ""})
    assert "动作" in result


def test_select_style_exemplars_default():
    from app.agents.nodes.chapter_generation import _select_style_exemplars
    result = _select_style_exemplars({"chapter_number": 5, "conflict": "日常争执", "hook": "情感转变"})
    assert len(result) > 0
