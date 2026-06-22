"""总纲生成默认草稿态测试

回归保护：初始化/生成大纲不应自动 confirmed，需作者显式确认。
"""

import asyncio
from unittest.mock import MagicMock, patch


def _run_async(coro):
    return asyncio.run(coro)


def test_generate_outline_defaults_to_unconfirmed():
    """generate_outline 写入的总纲为草稿态（confirmed=False，章节数未确认）"""
    kb = MagicMock()
    kb.outlines = MagicMock()
    kb.outlines.upsert.return_value = {"id": 1}
    with patch("app.agents.tools.utils._kb", return_value=kb):
        from app.agents.tools.creation.generate_outline import generate_outline
        result = _run_async(generate_outline.ainvoke({
            "title": "测试书名",
            "summary": "一个故事",
            "chapter_count": 30,
        }))
        assert result.get("action") == "created"
        written = kb.outlines.upsert.call_args[0][0]
        assert written["confirmed"] is False
        # chapter_count_confirmed 必须是布尔，不能误赋整数
        assert written["chapter_count_confirmed"] is False
        assert written["chapter_count_suggested"] == 30
