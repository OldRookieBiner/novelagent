"""AGENT_SYSTEM_PROMPT 格式化测试 —— 保护 .format() 占位符契约不被破坏"""
import re

import pytest

from app.agents.prompts import AGENT_SYSTEM_PROMPT
from app.agents.context_renderer import render_context_block


_LEGAL_PLACEHOLDERS = {
    "phase_label",
    "project_name",
    "context_block",
    "context_prerequisites_warning",
}


def _sample_project_data() -> dict:
    return {
        "outline": {"title": "测试", "summary": "一段概述"},
        "characters": [
            {
                "id": 1, "name": "林动", "role": "主角",
                "core_motivation": "复兴家族",
                "habit_action": "握拳",
                "backstory": "家道中落",
                "knowledge_boundary": "不知道宗门内幕",
            }
        ],
    }


def test_system_prompt_format_with_rendered_block():
    block = render_context_block(_sample_project_data())
    out = AGENT_SYSTEM_PROMPT.format(
        phase_label="写作",
        project_name="测试项目",
        context_block=block,
        context_prerequisites_warning="",
    )
    # 不抛异常即通过 .format()
    assert "测试项目" in out
    assert "写作" in out
    # 关键英文字段名不应再出现在最终系统 prompt 中
    # （prompt 自身的「禁止行为」段会提到这些 token 作为反例，故此处仅检查渲染区段）
    rendered_segment_start = out.find("## 项目上下文")
    rendered_segment_end = out.find("## 前置条件检测结果")
    assert rendered_segment_start != -1
    assert rendered_segment_end > rendered_segment_start
    segment = out[rendered_segment_start:rendered_segment_end]
    for forbidden in ("core_motivation", "habit_action", "backstory", "knowledge_boundary"):
        assert forbidden not in segment, f"字段名 {forbidden} 仍泄漏到项目上下文段"


def test_system_prompt_format_with_empty_block():
    """空 context_block 不应让 .format() 抛异常"""
    out = AGENT_SYSTEM_PROMPT.format(
        phase_label="孵化",
        project_name="空项目",
        context_block="",
        context_prerequisites_warning="",
    )
    assert "空项目" in out


def test_system_prompt_no_unescaped_braces():
    """除 4 个合法占位符外，AGENT_SYSTEM_PROMPT 不得包含其他 { } 字面量。

    防止后续编辑误引入花括号导致 .format() KeyError。
    """
    placeholders = set(re.findall(r"\{([^{}]*)\}", AGENT_SYSTEM_PROMPT))
    unexpected = placeholders - _LEGAL_PLACEHOLDERS
    assert not unexpected, f"AGENT_SYSTEM_PROMPT 出现非法占位符: {unexpected}"
