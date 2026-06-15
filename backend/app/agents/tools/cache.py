"""单次 SSE 请求内的工具结果缓存

以 (tool_name, params_hash) 为 key，缓存感知工具的结果。
写入类工具调用后自动使相关缓存失效。
请求结束自动清理。

I1 增强：前缀索引实现 O(1) 失效查找。
"""

import hashlib
import json
from typing import Any


class ToolResultCache:
    """单次 SSE 请求内的工具结果缓存"""

    def __init__(self):
        self._cache: dict[str, Any] = {}
        # 前缀索引：tool_name -> set of cache keys
        self._prefix_index: dict[str, set[str]] = {}

    def _key(self, tool_name: str, params: dict) -> str:
        params_json = json.dumps(params, sort_keys=True, ensure_ascii=False)
        params_hash = hashlib.md5(params_json.encode()).hexdigest()[:8]
        return f"{tool_name}:{params_hash}"

    def _add_to_index(self, tool_name: str, key: str) -> None:
        """将 key 添加到前缀索引"""
        if tool_name not in self._prefix_index:
            self._prefix_index[tool_name] = set()
        self._prefix_index[tool_name].add(key)

    def _remove_from_index(self, tool_name: str, key: str) -> None:
        """从前缀索引中移除 key"""
        if tool_name in self._prefix_index:
            self._prefix_index[tool_name].discard(key)

    def get(self, tool_name: str, params: dict) -> Any | None:
        """获取缓存结果，未命中返回 None"""
        return self._cache.get(self._key(tool_name, params))

    def set(self, tool_name: str, params: dict, result: Any) -> None:
        """设置缓存"""
        key = self._key(tool_name, params)
        self._cache[key] = result
        self._add_to_index(tool_name, key)

    def invalidate(self, tool_name: str) -> None:
        """使某工具的所有缓存失效 - O(1) 基于索引"""
        if tool_name not in self._prefix_index:
            return
        keys = self._prefix_index[tool_name]
        for k in keys:
            del self._cache[k]
        self._prefix_index[tool_name].clear()

    def invalidate_by_prefix(self, prefixes: list[str]) -> None:
        """使匹配前缀的缓存失效（如 creation 类工具写入后使 perception 缓存失效）- O(1) 基于索引"""
        keys_to_remove = []
        for prefix in prefixes:
            # prefix 可以是完整的 tool_name，如 "knowledge_search"
            if prefix in self._prefix_index:
                keys_to_remove.extend(self._prefix_index[prefix])
        # 执行删除
        for k in keys_to_remove:
            tool_name = k.split(":")[0]
            del self._cache[k]
            self._remove_from_index(tool_name, k)

    def clear(self) -> None:
        """清空全部缓存"""
        self._cache.clear()
        self._prefix_index.clear()

    @property
    def size(self) -> int:
        return len(self._cache)
