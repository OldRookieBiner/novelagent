"""跨请求 LRU 缓存 — 同项目连续对话时减少 DB 查询

缓存层：进程内 dict，key = (project_id, data_type, version_tag)
version_tag：由 _BaseStore._bump_version 管理，写入时 +1
TTL：默认 60 秒自动过期
不缓存：章节正文、伏笔状态（变化频率高）
"""

import time
import threading
from typing import Any

# 不缓存的数据类型（变化频率高或数据量过大）
_UNCACHEABLE_TYPES = frozenset({"chapters", "foreshadowing_status", "chapter_outlines"})


class ContextCache:
    """跨请求 LRU 缓存"""

    def __init__(self, ttl_seconds: int = 60, max_size: int = 200):
        self._store: dict[tuple[int, str, int], tuple[Any, float]] = {}
        self._ttl = ttl_seconds
        self._max_size = max_size
        self._lock = threading.Lock()

    def get(self, project_id: int, data_type: str, version_tag: int) -> Any | None:
        """获取缓存值，未命中或过期返回 None"""
        if data_type in _UNCACHEABLE_TYPES:
            return None

        key = (project_id, data_type, version_tag)
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            value, ts = entry
            if time.time() - ts > self._ttl:
                del self._store[key]
                return None
            return value

    def set(self, project_id: int, data_type: str, version_tag: int, value: Any) -> None:
        """设置缓存值"""
        if data_type in _UNCACHEABLE_TYPES:
            return

        key = (project_id, data_type, version_tag)
        with self._lock:
            if len(self._store) >= self._max_size:
                self._evict_oldest()
            self._store[key] = (value, time.time())

    def invalidate(self, project_id: int, data_type: str) -> None:
        """使指定项目+数据类型的所有版本缓存失效"""
        with self._lock:
            keys_to_remove = [
                k for k in self._store
                if k[0] == project_id and k[1] == data_type
            ]
            for k in keys_to_remove:
                del self._store[k]

    def invalidate_all(self, project_id: int) -> None:
        """使指定项目的所有缓存失效"""
        with self._lock:
            keys_to_remove = [
                k for k in self._store if k[0] == project_id
            ]
            for k in keys_to_remove:
                del self._store[k]

    def _evict_oldest(self) -> None:
        """驱逐最旧的缓存条目"""
        if not self._store:
            return
        oldest_key = min(self._store, key=lambda k: self._store[k][1])
        del self._store[oldest_key]


# 全局单例
context_cache = ContextCache()
