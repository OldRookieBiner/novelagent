from app.agents.prompts import DEFAULT_PROMPTS, CHAPTER_SELF_CHECK_PROMPT, CHAPTER_REFINE_PROMPT


def test_self_check_prompt_has_placeholders():
    """自检 prompt 包含 chapter_content 占位符"""
    assert "{chapter_content}" in CHAPTER_SELF_CHECK_PROMPT


def test_refine_prompt_has_placeholders():
    """精修 prompt 包含 check_result 和 draft_content 占位符"""
    assert "{check_result}" in CHAPTER_REFINE_PROMPT
    assert "{draft_content}" in CHAPTER_REFINE_PROMPT


def test_default_prompts_includes_self_check():
    """DEFAULT_PROMPTS 包含新的 prompt 键"""
    assert "chapter_self_check" in DEFAULT_PROMPTS
    assert "chapter_refine" in DEFAULT_PROMPTS
