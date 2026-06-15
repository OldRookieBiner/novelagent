"""ToolResultCache 单元测试 — I1 前缀索引优化"""

import pytest
from app.agents.tools.cache import ToolResultCache


class TestToolResultCacheBasic:
    """基础缓存操作"""

    def test_set_and_get(self):
        cache = ToolResultCache()
        cache.set("knowledge_search", {"query": "test"}, {"found": True})
        result = cache.get("knowledge_search", {"query": "test"})
        assert result == {"found": True}

    def test_get_miss_returns_none(self):
        cache = ToolResultCache()
        assert cache.get("knowledge_search", {"query": "nonexist"}) is None

    def test_size_tracking(self):
        cache = ToolResultCache()
        assert cache.size == 0
        cache.set("tool_a", {"k": 1}, "result1")
        assert cache.size == 1
        cache.set("tool_b", {"k": 2}, "result2")
        assert cache.size == 2

    def test_same_tool_different_params(self):
        """同工具不同参数各有独立缓存"""
        cache = ToolResultCache()
        cache.set("tool_a", {"k": 1}, "result1")
        cache.set("tool_a", {"k": 2}, "result2")
        assert cache.get("tool_a", {"k": 1}) == "result1"
        assert cache.get("tool_a", {"k": 2}) == "result2"
        assert cache.size == 2


class TestToolResultCacheInvalidation:
    """缓存失效 — O(1) 前缀索引"""

    def test_invalidate_by_tool_name(self):
        """invalidate 按 tool_name 失效所有该工具缓存"""
        cache = ToolResultCache()
        cache.set("knowledge_search", {"q": "a"}, "result_a")
        cache.set("knowledge_search", {"q": "b"}, "result_b")
        cache.set("progress_report", {"n": 5}, "result_c")

        cache.invalidate("knowledge_search")

        assert cache.get("knowledge_search", {"q": "a"}) is None
        assert cache.get("knowledge_search", {"q": "b"}) is None
        # 其他工具不受影响
        assert cache.get("progress_report", {"n": 5}) == "result_c"

    def test_invalidate_nonexistent_tool(self):
        """invalidate 不存在的工具名不报错"""
        cache = ToolResultCache()
        cache.set("tool_a", {}, "result")
        cache.invalidate("nonexistent")
        assert cache.get("tool_a", {}) == "result"

    def test_invalidate_by_prefix_list(self):
        """invalidate_by_prefix 按前缀列表批量失效"""
        cache = ToolResultCache()
        cache.set("knowledge_search", {"q": "a"}, "r1")
        cache.set("progress_report", {"n": 5}, "r2")
        cache.set("style_analysis", {"ch": 1}, "r3")

        cache.invalidate_by_prefix(["knowledge_search", "style_analysis"])

        assert cache.get("knowledge_search", {"q": "a"}) is None
        assert cache.get("style_analysis", {"ch": 1}) is None
        # 不在列表中的不受影响
        assert cache.get("progress_report", {"n": 5}) == "r2"

    def test_invalidate_by_prefix_empty_list(self):
        """空前缀列表不做任何删除"""
        cache = ToolResultCache()
        cache.set("tool_a", {}, "result")
        cache.invalidate_by_prefix([])
        assert cache.get("tool_a", {}) == "result"


class TestToolResultCacheClear:
    """清空操作"""

    def test_clear_empties_cache(self):
        cache = ToolResultCache()
        cache.set("tool_a", {}, "r1")
        cache.set("tool_b", {}, "r2")
        cache.clear()
        assert cache.size == 0
        assert cache.get("tool_a", {}) is None

    def test_clear_also_clears_index(self):
        """clear 后索引也被清空，可以重新 set"""
        cache = ToolResultCache()
        cache.set("tool_a", {}, "r1")
        cache.clear()
        cache.set("tool_a", {}, "r2")
        assert cache.get("tool_a", {}) == "r2"
        assert cache.size == 1

    def test_invalidate_after_clear_then_set(self):
        """clear 后重新 set，invalidate 仍能正常工作"""
        cache = ToolResultCache()
        cache.set("tool_a", {}, "old")
        cache.clear()
        cache.set("tool_a", {}, "new")
        cache.invalidate("tool_a")
        assert cache.get("tool_a", {}) is None
