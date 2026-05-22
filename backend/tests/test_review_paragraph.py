"""段落级审核定位测试"""

from app.agents.nodes.review import _extract_review_fields


def test_extract_review_fields_new_format():
    """新格式 issues 包含 paragraph_start"""
    data = {
        "passed": False,
        "scores": {
            "plot_consistency": 7,
            "character_consistency": 8,
            "writing_quality": 6,
            "emotional_tension": 7,
            "ai_flavor": 5,
            "outline_deviation": 2,
        },
        "issues": [
            {
                "type": "AI味",
                "paragraph_start": "他眼神复杂地看着她",
                "suggestion": "改为具体动作描写",
            },
        ],
        "suggestions": "整体不错，但需降低AI味",
    }
    result = _extract_review_fields(data)
    assert result["issues"][0]["paragraph_start"] == "他眼神复杂地看着她"
    assert result["issues"][0]["suggestion"] == "改为具体动作描写"
    assert result["issues"][0]["type"] == "AI味"


def test_extract_review_fields_old_format_compatible():
    """旧格式 issues 含 location 和 description 仍可解析"""
    data = {
        "passed": False,
        "scores": {
            "plot_consistency": 7,
            "character_consistency": 8,
            "writing_quality": 6,
            "emotional_tension": 7,
            "ai_flavor": 2,
            "outline_deviation": 1,
        },
        "issues": [
            {
                "type": "AI味",
                "location": "第三段",
                "description": "使用了模板化表达",
                "suggestion": "修改",
            },
        ],
    }
    result = _extract_review_fields(data)
    assert result["issues"][0]["location"] == "第三段"
    assert result["issues"][0]["description"] == "使用了模板化表达"
    assert "paragraph_start" not in result["issues"][0]


def test_extract_review_fields_mixed_format():
    """新旧格式混合的 issues 列表"""
    data = {
        "passed": False,
        "scores": {
            "plot_consistency": 5,
            "character_consistency": 8,
            "writing_quality": 6,
            "emotional_tension": 7,
            "ai_flavor": 4,
            "outline_deviation": 2,
        },
        "issues": [
            {
                "type": "AI味",
                "paragraph_start": "他缓缓地叹了口气",
                "suggestion": "替换为具体动作",
            },
            {
                "type": "逻辑",
                "location": "第五段",
                "description": "时间线矛盾",
                "suggestion": "修正时间",
            },
        ],
    }
    result = _extract_review_fields(data)
    # 新格式
    assert result["issues"][0]["paragraph_start"] == "他缓缓地叹了口气"
    assert "location" not in result["issues"][0]
    # 旧格式
    assert result["issues"][1]["location"] == "第五段"
    assert "paragraph_start" not in result["issues"][1]


def test_extract_review_fields_string_issue():
    """旧格式 issues 为纯字符串时仍可解析"""
    data = {
        "passed": False,
        "scores": {},
        "issues": ["文笔质量偏弱", "节奏稍慢"],
    }
    result = _extract_review_fields(data)
    assert len(result["issues"]) == 2
    assert result["issues"][0]["description"] == "文笔质量偏弱"


def test_review_prompt_requests_paragraph_start():
    """审核 prompt 要求 paragraph_start 字段"""
    from app.agents.prompts import REVIEW_USER_PROMPT

    assert "paragraph_start" in REVIEW_USER_PROMPT
