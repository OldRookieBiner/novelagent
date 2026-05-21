"""测试大纲 Prompt 强化：三层矛盾结构、主题内核、情感曲线章节区间、自检项"""


def test_outline_prompt_has_three_layer_conflict():
    """大纲 prompt 要求三层矛盾结构"""
    from app.agents.prompts import OUTLINE_GENERATION_PROMPT
    assert "表面冲突" in OUTLINE_GENERATION_PROMPT


def test_outline_prompt_has_theme_core():
    """大纲 prompt 包含主题内核板块"""
    from app.agents.prompts import OUTLINE_GENERATION_PROMPT
    assert "主题内核" in OUTLINE_GENERATION_PROMPT


def test_outline_prompt_has_chapter_range_in_curve():
    """大纲 prompt 情感曲线要求标注章节区间"""
    from app.agents.prompts import OUTLINE_GENERATION_PROMPT
    assert "章节区间" in OUTLINE_GENERATION_PROMPT


def test_outline_prompt_summary_word_count():
    """概述字数要求 500-800"""
    from app.agents.prompts import OUTLINE_GENERATION_PROMPT
    assert "500" in OUTLINE_GENERATION_PROMPT and "800" in OUTLINE_GENERATION_PROMPT


def test_outline_prompt_self_check_includes_conflict_layers():
    """自检清单包含三层矛盾结构检查"""
    from app.agents.prompts import OUTLINE_GENERATION_PROMPT
    assert "三层矛盾结构" in OUTLINE_GENERATION_PROMPT


def test_outline_prompt_self_check_includes_chapter_range():
    """自检清单包含章节区间检查"""
    from app.agents.prompts import OUTLINE_GENERATION_PROMPT
    # 检查自检清单中是否有关于章节区间的检查项
    assert "章节区间" in OUTLINE_GENERATION_PROMPT


def test_outline_prompt_has_seven_sections():
    """大纲 prompt 现在有七大板块"""
    from app.agents.prompts import OUTLINE_GENERATION_PROMPT
    assert "七大板块" in OUTLINE_GENERATION_PROMPT
