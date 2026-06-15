"""ContextCache 单元测试"""
import time
import pytest
from app.agents.context_cache import ContextCache


class TestContextCache:
    def test_cache_miss_returns_none(self):
        """缓存未命中返回 None"""
        cache = ContextCache()
        assert cache.get(1, "world_setting", 0) is None

    def test_cache_hit_returns_value(self):
        """缓存命中返回值"""
        cache = ContextCache()
        cache.set(1, "world_setting", 0, {"core_concept": "魔法"})
        result = cache.get(1, "world_setting", 0)
        assert result == {"core_concept": "魔法"}

    def test_version_change_causes_miss(self):
        """version_tag 变化导致缓存未命中"""
        cache = ContextCache()
        cache.set(1, "world_setting", 1, {"core_concept": "旧"})
        result = cache.get(1, "world_setting", 2)
        assert result is None

    def test_different_project_isolated(self):
        """不同项目的缓存隔离"""
        cache = ContextCache()
        cache.set(1, "world_setting", 0, {"core_concept": "A"})
        cache.set(2, "world_setting", 0, {"core_concept": "B"})
        assert cache.get(1, "world_setting", 0) == {"core_concept": "A"}
        assert cache.get(2, "world_setting", 0) == {"core_concept": "B"}

    def test_invalidate_specific_data_type(self):
        """使特定数据类型的缓存失效"""
        cache = ContextCache()
        cache.set(1, "world_setting", 0, {"a": 1})
        cache.set(1, "characters", 0, [{"name": "张三"}])
        cache.invalidate(1, "world_setting")
        assert cache.get(1, "world_setting", 0) is None
        assert cache.get(1, "characters", 0) == [{"name": "张三"}]

    def test_ttl_expiry(self):
        """TTL 过期后缓存失效"""
        cache = ContextCache(ttl_seconds=0.1)
        cache.set(1, "world_setting", 0, {"a": 1})
        time.sleep(0.15)
        assert cache.get(1, "world_setting", 0) is None

    def test_uncacheable_types_not_stored(self):
        """不缓存的类型 set 后 get 仍返回 None"""
        cache = ContextCache()
        cache.set(1, "chapters", 0, [{"content": "很长"}])
        assert cache.get(1, "chapters", 0) is None

    def test_invalidate_all_for_project(self):
        """使项目所有缓存失效"""
        cache = ContextCache()
        cache.set(1, "world_setting", 0, {"a": 1})
        cache.set(1, "characters", 0, [{"name": "张三"}])
        cache.invalidate_all(1)
        assert cache.get(1, "world_setting", 0) is None
        assert cache.get(1, "characters", 0) is None
