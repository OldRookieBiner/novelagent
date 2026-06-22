"""nodes_utils.extract_json_block 健壮性测试"""

from app.agents.nodes_utils import extract_json_block


class TestExtractJsonBlock:
    def test_json_fenced_object(self):
        text = '随便说点\n```json\n{"a": 1, "b": "x"}\n```\n结尾'
        assert extract_json_block(text) == {"a": 1, "b": "x"}

    def test_json_fenced_array(self):
        text = '```json\n[{"name": "甲"}, {"name": "乙"}]\n```'
        result = extract_json_block(text)
        assert isinstance(result, list) and len(result) == 2

    def test_bare_fence(self):
        text = '```\n{"k": [1, 2, 3]}\n```'
        assert extract_json_block(text) == {"k": [1, 2, 3]}

    def test_bare_braces_no_fence(self):
        text = '这是输出：{"title": "测试", "n": 3} 多余文字'
        assert extract_json_block(text) == {"title": "测试", "n": 3}

    def test_bare_brackets_no_fence(self):
        text = '结果 [1, 2, {"x": "y"}] 后续'
        assert extract_json_block(text) == [1, 2, {"x": "y"}]

    def test_braces_inside_string_not_confused(self):
        # 字符串内部的右花括号不应提前结束扫描
        text = '{"desc": "包含 } 符号的文本", "ok": true}'
        assert extract_json_block(text) == {"desc": "包含 } 符号的文本", "ok": True}

    def test_escaped_quote_in_string(self):
        text = r'{"q": "他说\"你好\"", "n": 1}'
        assert extract_json_block(text) == {"q": '他说"你好"', "n": 1}

    def test_truncated_unclosed_returns_none(self):
        text = '```json\n{"a": 1, "b": [1, 2,'  # 未闭合
        assert extract_json_block(text) is None

    def test_multiple_code_blocks_takes_first_valid(self):
        text = '```json\n{"first": 1}\n```\n```json\n{"second": 2}\n```'
        assert extract_json_block(text) == {"first": 1}

    def test_empty_and_none(self):
        assert extract_json_block("") is None
        assert extract_json_block("   ") is None
        assert extract_json_block(None) is None

    def test_no_json_returns_none(self):
        assert extract_json_block("这里完全没有 JSON 内容") is None


class TestExtractJsonBlockRepair:
    """中文大模型高频 JSON 瑕疵的修复式重试（直击大纲内容缺失根因）"""

    def test_bare_newline_in_string_value(self):
        # 根因场景：500-800 字概述里 LLM 直接换行，产生未转义控制字符
        text = '```json\n{"title": "测试", "summary": "第一行\n第二行"}\n```'
        result = extract_json_block(text)
        assert result == {"title": "测试", "summary": "第一行\n第二行"}

    def test_trailing_comma_object(self):
        text = '```json\n{"title": "测试", "summary": "x",}\n```'
        assert extract_json_block(text) == {"title": "测试", "summary": "x"}

    def test_trailing_comma_array(self):
        text = '```json\n{"items": [1, 2, 3,]}\n```'
        assert extract_json_block(text) == {"items": [1, 2, 3]}

    def test_fullwidth_quotes(self):
        # LLM 偶尔用中文全角引号做结构定界
        text = '```json\n{“title”: "测试", "n": 1}\n```'
        assert extract_json_block(text) == {"title": "测试", "n": 1}

    def test_bare_tab_in_string(self):
        text = '```json\n{"title": "测\t试", "n": 1}\n```'
        assert extract_json_block(text) == {"title": "测\t试", "n": 1}

    def test_bare_carriage_return_in_string(self):
        text = '```json\n{"title": "上\r下", "n": 1}\n```'
        assert extract_json_block(text) == {"title": "上\r下", "n": 1}

    def test_repair_on_bare_braces_path(self):
        # 无围栏 + 字符串内裸换行，走括号配对扫描后的修复分支
        text = '输出：{"title": "测试", "summary": "甲\n乙"}'
        assert extract_json_block(text) == {"title": "测试", "summary": "甲\n乙"}

    def test_combined_defects(self):
        # 裸换行 + 尾随逗号 + 全角引号叠加
        text = '```json\n{“title”: "测试", "summary": "甲\n乙",}\n```'
        assert extract_json_block(text) == {"title": "测试", "summary": "甲\n乙"}

    def test_valid_json_with_legitimate_escaped_newline_unaffected(self):
        # 已正确转义的内容不应被二次破坏
        text = '```json\n{"summary": "甲\\n乙"}\n```'
        assert extract_json_block(text) == {"summary": "甲\n乙"}

    def test_single_quotes_known_unsupported(self):
        # 单引号转换风险高（误伤合法撇号），有意不修复，保持降级
        text = "```json\n{'title': '测试'}\n```"
        assert extract_json_block(text) is None
