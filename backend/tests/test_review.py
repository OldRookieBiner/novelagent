"""Tests for chapter review node"""

import pytest
from app.agents.nodes.review import parse_review_result, check_review_passed


class TestParseReviewResultJSON:
    """Tests for JSON format review parsing"""

    def test_parse_json_passed(self):
        """Should parse JSON format passed review"""
        response = '''```json
{
  "passed": true,
  "scores": {
    "plot_consistency": 8,
    "character_consistency": 9,
    "writing_quality": 7,
    "emotional_tension": 8,
    "ai_flavor": 2,
    "outline_deviation": 2
  },
  "issues": [],
  "suggestions": ""
}
```'''
        result = parse_review_result(response)

        assert result["passed"] is True
        assert result["scores"]["plot_consistency"] == 8
        assert result["scores"]["ai_flavor"] == 2
        assert result["scores"]["outline_deviation"] == 2
        assert result["issues"] == []

    def test_parse_json_failed(self):
        """Should parse JSON format failed review"""
        response = '''{
  "passed": false,
  "scores": {
    "plot_consistency": 5,
    "character_consistency": 4,
    "writing_quality": 6,
    "emotional_tension": 5,
    "ai_flavor": 7,
    "outline_deviation": 6
  },
  "issues": [
    {"type": "情节矛盾", "location": "第3段", "description": "转折突兀"},
    {"type": "AI味", "location": "全文", "description": "多处禁用词"}
  ],
  "suggestions": "增加过渡描写，替换AI味词汇"
}'''
        result = parse_review_result(response)

        assert result["passed"] is False
        assert result["scores"]["ai_flavor"] == 7
        assert result["scores"]["outline_deviation"] == 6
        assert len(result["issues"]) == 2
        assert result["issues"][0]["type"] == "情节矛盾"
        assert "过渡描写" in result["suggestions"]

    def test_parse_json_with_surrounding_text(self):
        """Should extract JSON from surrounding text"""
        response = '''以下是审核结果：

```json
{"passed": true, "scores": {"plot_consistency": 7}, "issues": [], "suggestions": ""}
```

以上是审核结果。'''
        result = parse_review_result(response)
        assert result["passed"] is True
        assert result["scores"]["plot_consistency"] == 7

    def test_parse_json_feedback_field(self):
        """Should extract suggestions from 'feedback' field name"""
        response = '{"passed": false, "scores": {"plot_consistency": 7}, "issues": [], "feedback": "增加过渡描写"}'
        result = parse_review_result(response)
        assert result["passed"] is False
        assert "过渡描写" in result["suggestions"]

    def test_parse_json_multiple_objects(self):
        """Should parse the first valid JSON object when multiple exist"""
        response = '分析：{"analysis": "good"}\n审核：{"passed": true, "scores": {"plot_consistency": 8}, "issues": [], "suggestions": ""}'
        result = parse_review_result(response)
        # 第一个 { 到最后一个 } 的贪婪匹配失败后，应逐层找到正确的 JSON
        assert result["passed"] is True
        assert result["scores"]["plot_consistency"] == 8

    def test_parse_json_markdown_code_block(self):
        """Should extract JSON from markdown code block"""
        response = '审核结果如下：\n```json\n{"passed": false, "scores": {"ai_flavor": 6}, "issues": [{"type": "AI味", "description": "用词生硬"}], "suggestions": "优化用词"}\n```\n以上是结果。'
        result = parse_review_result(response)
        assert result["passed"] is False
        assert result["scores"]["ai_flavor"] == 6
        assert len(result["issues"]) == 1
        assert "优化用词" in result["suggestions"]

    def test_parse_json_invalid_fallback(self):
        """Should fallback to legacy when JSON is invalid"""
        response = """【审核结果】通过
情节一致性：8/10
AI味程度：2/10"""
        result = parse_review_result(response)
        assert result["passed"] is True
        assert result["scores"]["plot_consistency"] == 8


class TestParseReviewResultLegacy:
    """Tests for legacy format review parsing (fallback)"""

    def test_parse_passed_result(self):
        """Should parse a passed review result"""
        response = """
【审核结果】通过

【评分】
情节一致性：8/10
人物一致性：9/10
文笔质量：7/10
情感张力：8/10
AI味程度：2/10

【问题列表】
无

【修改建议】
无
---
"""
        result = parse_review_result(response)

        assert result["passed"] is True
        assert result["scores"]["plot_consistency"] == 8
        assert result["scores"]["character_consistency"] == 9
        assert result["scores"]["writing_quality"] == 7
        assert result["scores"]["emotional_tension"] == 8
        assert result["scores"]["ai_flavor"] == 2
        assert result["issues"] == []
        assert result["suggestions"] == ""

    def test_parse_failed_result(self):
        """Should parse a failed review result"""
        response = """
【审核结果】不通过

【评分】
情节一致性：5/10
人物一致性：4/10
文笔质量：6/10
情感张力：5/10
AI味程度：7/10

【问题列表】
1. 情节转折过于突兀
2. 人物行为前后矛盾
3. AI痕迹明显，缺乏真实感

【修改建议】
建议增加过渡描写，使情节更自然流畅。
---
"""
        result = parse_review_result(response)

        assert result["passed"] is False
        assert result["scores"]["plot_consistency"] == 5
        assert result["scores"]["character_consistency"] == 4
        assert result["scores"]["ai_flavor"] == 7
        assert len(result["issues"]) == 3
        assert "过渡描写" in result["suggestions"]

    def test_parse_partial_scores(self):
        """Should handle partial scores"""
        response = """
【审核结果】通过
情节一致性：7/10
文笔质量：8/10
"""
        result = parse_review_result(response)

        assert result["passed"] is True
        assert result["scores"]["plot_consistency"] == 7
        assert result["scores"]["writing_quality"] == 8
        assert "character_consistency" not in result["scores"]

    def test_parse_empty_response(self):
        """Should handle empty response"""
        result = parse_review_result("")

        assert result["passed"] is False
        assert result["scores"] == {}
        assert result["issues"] == []
        assert result["suggestions"] == ""

    def test_parse_colon_format(self):
        """Should handle different colon formats"""
        response = """
情节一致性: 8/10
人物一致性：9/10
"""
        result = parse_review_result(response)

        assert result["scores"]["plot_consistency"] == 8
        assert result["scores"]["character_consistency"] == 9

    def test_parse_legacy_with_outline_deviation(self):
        """Should parse outline_deviation from legacy format"""
        response = """【审核结果】通过
情节一致性：8/10
大纲偏离度：3/10"""
        result = parse_review_result(response)
        assert result["scores"]["outline_deviation"] == 3


class TestCheckReviewPassed:
    """Tests for check_review_passed function"""

    def test_all_scores_pass(self):
        """Should pass when all scores meet threshold"""
        result = {
            "scores": {
                "plot_consistency": 8,
                "character_consistency": 7,
                "writing_quality": 6,
                "emotional_tension": 7,
                "ai_flavor": 2,
                "outline_deviation": 2,
            }
        }
        assert check_review_passed(result) is True

    def test_fail_on_low_plot_consistency(self):
        """Should fail on low plot consistency"""
        result = {
            "scores": {
                "plot_consistency": 5,
                "character_consistency": 8,
                "writing_quality": 8,
                "emotional_tension": 8,
                "ai_flavor": 2,
                "outline_deviation": 2,
            }
        }
        assert check_review_passed(result) is False

    def test_fail_on_high_ai_flavor(self):
        """Should fail on high AI flavor"""
        result = {
            "scores": {
                "plot_consistency": 8,
                "character_consistency": 8,
                "writing_quality": 8,
                "emotional_tension": 8,
                "ai_flavor": 5,
                "outline_deviation": 2,
            }
        }
        assert check_review_passed(result) is False

    def test_fail_on_high_outline_deviation(self):
        """Should fail on high outline deviation"""
        result = {
            "scores": {
                "plot_consistency": 8,
                "character_consistency": 8,
                "writing_quality": 8,
                "emotional_tension": 8,
                "ai_flavor": 2,
                "outline_deviation": 5,
            }
        }
        assert check_review_passed(result) is False

    def test_fail_on_missing_scores(self):
        """Should fail when scores are missing"""
        result = {"scores": {"plot_consistency": 8}}
        assert check_review_passed(result) is False

    def test_pass_at_boundary(self):
        """Should pass at boundary values"""
        result = {
            "scores": {
                "plot_consistency": 6,
                "character_consistency": 6,
                "writing_quality": 6,
                "emotional_tension": 6,
                "ai_flavor": 3,
                "outline_deviation": 4,
            }
        }
        assert check_review_passed(result) is True

    def test_fail_just_below_boundary(self):
        """Should fail just below boundary"""
        result = {
            "scores": {
                "plot_consistency": 5,
                "character_consistency": 6,
                "writing_quality": 6,
                "emotional_tension": 6,
                "ai_flavor": 3,
                "outline_deviation": 4,
            }
        }
        assert check_review_passed(result) is False


class TestReviewNodeIntegration:
    """Integration tests for review node"""

    @pytest.mark.asyncio
    async def test_review_node_structure(self):
        """Test that review_node has correct signature"""
        from app.agents.nodes.review import review_node
        import inspect

        # 验证是异步函数
        assert inspect.iscoroutinefunction(review_node)

        # 验证参数签名
        sig = inspect.signature(review_node)
        params = list(sig.parameters.keys())
        assert "state" in params
