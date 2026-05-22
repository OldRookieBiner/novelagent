from app.agents.prompts import DEFAULT_PROMPTS, INSPIRATION_EXTRACTION_PROMPT, INSPIRATION_QUESTION_PROMPT
from app.agents.constants import FIELD_INFERENCE_RULES, INSPIRATION_REQUIRED_FIELDS


def test_extraction_prompt_has_placeholders():
    assert "{free_text}" in INSPIRATION_EXTRACTION_PROMPT
    assert "{extracted_fields}" in INSPIRATION_EXTRACTION_PROMPT
    assert "{missing_fields}" in INSPIRATION_EXTRACTION_PROMPT


def test_question_prompt_has_placeholders():
    assert "{conversation_history}" in INSPIRATION_QUESTION_PROMPT
    assert "{user_message}" in INSPIRATION_QUESTION_PROMPT


def test_default_prompts_includes_inspiration():
    assert "inspiration_extraction" in DEFAULT_PROMPTS
    assert "inspiration_question" in DEFAULT_PROMPTS


def test_field_inference_rules_format():
    for keywords, fields in FIELD_INFERENCE_RULES:
        assert isinstance(keywords, list) and len(keywords) > 0
        assert isinstance(fields, dict) and len(fields) > 0


def test_required_fields_defined():
    assert len(INSPIRATION_REQUIRED_FIELDS) >= 4
    assert "novelType" in INSPIRATION_REQUIRED_FIELDS
