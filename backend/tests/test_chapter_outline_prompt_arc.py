"""测试章节大纲 Prompt 弧纲整合"""


def test_chapter_outline_prompt_has_arc_context():
    """章节大纲 prompt 包含 arc_context 占位符"""
    from app.agents.prompts import GENERATE_SINGLE_CHAPTER_OUTLINE_PROMPT
    assert "{arc_context}" in GENERATE_SINGLE_CHAPTER_OUTLINE_PROMPT


def test_chapter_outline_prompt_arc_integration():
    """弧纲整合到 prompt 模板中"""
    from app.agents.prompts import GENERATE_SINGLE_CHAPTER_OUTLINE_PROMPT
    assert "弧归属" in GENERATE_SINGLE_CHAPTER_OUTLINE_PROMPT


def test_chapter_outline_prompt_arc_must_complete():
    """弧纲提示要求完成弧纲核心任务"""
    from app.agents.prompts import GENERATE_SINGLE_CHAPTER_OUTLINE_PROMPT
    assert "核心任务" in GENERATE_SINGLE_CHAPTER_OUTLINE_PROMPT


def test_build_arc_context_no_arcs():
    """无弧纲时返回短/中篇提示"""
    from app.agents.nodes.chapter_generation import _build_arc_context
    result = _build_arc_context([], 1, 10)
    assert "短/中篇" in result


def test_build_arc_context_finds_current_arc():
    """能根据章节号找到对应弧"""
    from app.agents.nodes.chapter_generation import _build_arc_context
    arcs = [
        {"arc_number": 1, "title": "起势", "chapter_count": 3, "outline": "开头概要", "summary": "起势摘要"},
        {"arc_number": 2, "title": "高潮", "chapter_count": 4, "outline": "中段概要", "summary": "高潮摘要"},
    ]
    result = _build_arc_context(arcs, 4, 7)
    assert "高潮" in result
    assert "第4-7章" in result


def test_build_arc_context_first_chapter_in_arc():
    """弧内首章提示建立基调"""
    from app.agents.nodes.chapter_generation import _build_arc_context
    arcs = [
        {"arc_number": 1, "title": "起势", "chapter_count": 3},
    ]
    result = _build_arc_context(arcs, 1, 3)
    assert "首章" in result or "基调" in result


def test_build_arc_context_last_chapter_in_arc():
    """弧内末章提示弧线收束"""
    from app.agents.nodes.chapter_generation import _build_arc_context
    arcs = [
        {"arc_number": 1, "title": "起势", "chapter_count": 3},
    ]
    result = _build_arc_context(arcs, 3, 3)
    assert "末章" in result or "收束" in result
