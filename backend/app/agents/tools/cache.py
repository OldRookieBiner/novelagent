"""单次 SSE 请求内的工具结果缓存

以 (tool_name, params_hash) 为 key，缓存感知工具的结果。
写入类工具调用后自动使相关缓存失效。
请求结束自动清理。
"""

import hashlib
import json
from typing import Any


class ToolResultCache:
    """单次 SSE 请求内的工具结果缓存"""

    def __init__(self):
        self._cache: dict[str, Any] = {}

    def _key(self, tool_name: str, params: dict) -> str:
        params_json = json.dumps(params, sort_keys=True, ensure_ascii=False)
        params_hash = hashlib.md5(params_json.encode()).hexdigest()[:8]
        return f"{tool_name}:{params_hash}"

    def get(self, tool_name: str, params: dict) -> Any | None:
        """获取缓存结果，未命中返回 None"""
        return self._cache.get(self._key(tool_name, params))

    def set(self, tool_name: str, params: dict, result: Any) -> None:
        """设置缓存"""
        self._cache[self._key(tool_name, params)] = result

    def invalidate(self, tool_name: str) -> None:
        """使某工具的所有缓存失效"""
        keys_to_remove = [k for k in self._cache if k.startswith(f"{tool_name}:")]
        for k in keys_to_remove:
            del self._cache[k]

    def invalidate_by_prefix(self, prefixes: list[str]) -> None:
        """使匹配前缀的缓存失效（如 creation 类工具写入后使 perception 缓存失效）"""
        keys_to_remove = []
        for k in self._cache:
            for prefix in prefixes:
                if k.startswith(prefix):
                    keys_to_remove.append(k)
                    break
        for k in keys_to_remove:
            del self._cache[k]

    def clear(self) -> None:
        """清空全部缓存"""
        self._cache.clear()

    @property
    def size(self) -> int:
        return len(self._cache)
