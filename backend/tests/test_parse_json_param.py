"""parse_json_param 单元测试"""
import pytest
from app.agents.tools.utils import parse_json_param


class TestParseJsonParam:
    """覆盖正常/类型不匹配/解析失败三种场景"""

    def test_already_target_type_list(self):
        result, warning = parse_json_param([1, 2, 3], [], "test_param")
        assert result == [1, 2, 3]
        assert warning is None

    def test_already_target_type_dict(self):
        result, warning = parse_json_param({"a": 1}, {}, "test_param")
        assert result == {"a": 1}
        assert warning is None

    def test_valid_json_string_list(self):
        result, warning = parse_json_param("[1,2,3]", [], "items")
        assert result == [1, 2, 3]
        assert warning is None

    def test_valid_json_string_dict(self):
        result, warning = parse_json_param('{"red":[]}', {}, "settings")
        assert result == {"red": []}
        assert warning is None

    def test_invalid_json_string(self):
        result, warning = parse_json_param("not json", [], "items")
        assert result == []
        assert "items" in warning
        assert "解析失败" in warning

    def test_json_type_mismatch(self):
        """JSON 解析成功但类型与 default 不匹配"""
        result, warning = parse_json_param('{"a":1}', [], "items")
        assert result == []
        assert "items" in warning
        assert "类型不匹配" in warning

    def test_unsupported_type_int(self):
        result, warning = parse_json_param(123, [], "items")
        assert result == []
        assert "items" in warning
        assert "类型不支持" in warning

    def test_empty_string_list(self):
        result, warning = parse_json_param("", [], "items")
        assert result == []
        assert warning is not None

    def test_empty_string_dict(self):
        result, warning = parse_json_param("", {}, "settings")
        assert result == {}
        assert warning is not None

    def test_param_name_in_warning(self):
        result, warning = parse_json_param("bad", [], "my_field")
        assert "my_field" in warning
