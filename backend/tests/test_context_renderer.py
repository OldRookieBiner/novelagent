"""上下文中文化渲染层测试"""
import json
import logging

import pytest

from app.agents.context_renderer import (
    FIELD_LABELS,
    render_context_block,
    render_context_block_compact,
)


def test_render_character_fields_translated():
    """角色字段英文 key → 中文标签 + 不再出现原 key"""
    data = {
        "characters": [
            {
                "id": 1,
                "name": "林动",
                "role": "主角",
                "core_motivation": "复兴家族",
                "habit_action": "握拳",
                "backstory": "家道中落，少年立志",
                "deep_fear": "再次被遗弃",
                "knowledge_boundary": "不知道：宗门内斗的真相",
                "speech_style": "果决、简短、带乡音",
            }
        ]
    }
    text = render_context_block(data)
    # 中文标签出现
    assert "核心动机" in text
    assert "习惯动作" in text
    assert "背景故事" in text
    assert "深层恐惧" in text
    assert "知识边界" in text
    assert "语言风格" in text
    # 英文字段名不应出现
    for forbidden in (
        "core_motivation",
        "habit_action",
        "backstory",
        "deep_fear",
        "knowledge_boundary",
        "speech_style",
    ):
        assert forbidden not in text, f"未翻译字段 {forbidden} 仍然出现在输出中"
    # 顶层标题
    assert "## 角色" in text


def test_render_world_setting_translated():
    data = {
        "world_setting": {
            "core_concept": "灵气与机械并存的近代奇幻",
            "tiered_settings": {
                "red": ["不可用灵气直接杀人"],
                "yellow": ["可突破宗门戒律，代价是流放"],
                "green": ["民间流传剑客故事"],
            },
            "key_locations": ["王城：政治中心", "灵渊：力量源头"],
        }
    }
    text = render_context_block(data)
    assert "## 世界观" in text
    assert "核心设定" in text
    assert "红线规则（不可违反）" in text
    assert "黄线规则（可突破有代价）" in text
    assert "绿色装饰设定" in text
    assert "关键地点" in text
    # 英文 key 不应出现
    for forbidden in ("core_concept", "tiered_settings", "key_locations", "red", "yellow", "green"):
        assert forbidden not in text


def test_render_outline_with_nested_plot_points():
    data = {
        "outline": {
            "title": "测试小说",
            "summary": "一段概述",
            "plot_points": [
                {
                    "order": 1,
                    "event": "开篇",
                    "conflict": "家族危机",
                    "hook": "陌生信件",
                    "foreshadowing_label": "V1",
                    "foreshadowing_content": "信件指向上古秘辛",
                }
            ],
            "emotional_curve": "悬念→紧张→爆发→沉静",
            "theme": "命运与抗争",
        }
    }
    text = render_context_block(data)
    assert "## 大纲" in text
    assert "情节节点" in text
    assert "伏笔编号" in text
    assert "伏笔内容" in text
    assert "情感曲线" in text
    assert "主题" in text
    for forbidden in ("foreshadowing_label", "foreshadowing_content", "plot_points", "emotional_curve"):
        assert forbidden not in text


def test_render_skips_empty_but_keeps_zero_and_false():
    """0 和 False 是合法值不应跳过；空字符串/None/[]/{} 应跳过整行"""
    data = {
        "current_chapter_outline": {
            "chapter_number": 0,           # 合法 0
            "confirmed": False,            # 合法 False
            "title": "",                   # 跳过
            "scene": None,                 # 跳过
            "key_scenes": [],              # 跳过
            "pacing_note": "缓",            # 保留
        }
    }
    text = render_context_block(data)
    assert "章节号：0" in text
    assert "已确认：否" in text
    assert "节奏说明：缓" in text
    # 空值字段名不应出现
    assert "标题" not in text
    assert "场景" not in text
    assert "关键场景" not in text


def test_render_truncates_long_values():
    long_text = "一" * 1500
    data = {"characters": [{"id": 1, "name": "甲", "backstory": long_text}]}
    text = render_context_block(data)
    assert "……" in text
    # 截断后不应包含完整 1500 字
    assert long_text not in text


def test_render_skips_prerequisites_key():
    """prerequisites 由独立通道展示，渲染器须跳过"""
    data = {
        "prerequisites": {
            "blocked": [{"type": "outline", "message": "大纲缺失", "severity": "error"}],
            "warnings": [],
            "validated": True,
        },
        "characters": [{"id": 1, "name": "甲", "role": "主角"}],
    }
    text = render_context_block(data)
    # 顶层标签「前置条件」不应出现（防止双重展示）
    assert "前置条件" not in text
    assert "## 角色" in text


def test_render_unmapped_key_falls_back_silently(caplog):
    data = {"unknown_field": "测试值"}
    with caplog.at_level(logging.WARNING, logger="app.agents.context_renderer"):
        text = render_context_block(data)
    # 不加 [未映射] 标记
    assert "[未映射]" not in text
    # 原 key 作为 fallback 标签
    assert "unknown_field" in text
    # logger.warning 已触发
    assert any("unmapped key=unknown_field" in r.message for r in caplog.records)


def test_render_compact_only_whitelisted():
    data = {
        "outline": {"title": "X"},
        "style_constraints": {"taboo_words": ["不禁"]},
        "current_plot_block": {"title": "第一幕"},
        "pending_foreshadowings": [{"id": 1, "content": "伏笔A"}],
        "overdue_foreshadowings": [],   # 空 list → 跳过
        "characters": [{"id": 1, "name": "应排除"}],
        "world_setting": {"core_concept": "应排除"},
    }
    text = render_context_block_compact(data)
    assert "## 大纲" in text
    assert "## 风格约束" in text
    assert "## 当前情节块" in text
    assert "## 待回收伏笔" in text
    # 不在白名单
    assert "## 角色" not in text
    assert "## 世界观" not in text
    assert "应排除" not in text


def test_render_output_size_within_budget():
    """中文 Markdown 输出不得明显超过原 JSON 长度（防映射表膨胀）。

    使用一份接近真实的 project_data 样本，断言新格式 ≤ 旧 JSON 1.3 倍。
    """
    data = {
        "outline": {
            "title": "测试小说",
            "summary": "一段 200 字以内的概述" * 3,
            "chapter_count_confirmed": 30,
            "emotional_curve": "悬念→紧张→爆发→沉静",
            "theme": "命运与抗争",
        },
        "world_setting": {
            "core_concept": "灵气与机械并存",
            "tiered_settings": {"red": ["不可滥用灵气"], "yellow": ["突破代价：流放"], "green": ["民间传说"]},
            "key_locations": ["王城", "灵渊"],
        },
        "characters": [
            {"id": 1, "name": "林动", "role": "主角", "core_motivation": "复仇",
             "personality": "坚韧", "knowledge_boundary": "不知道宗门内幕",
             "speech_style": "果决"},
            {"id": 2, "name": "应欢欢", "role": "女主", "core_motivation": "守护宗门",
             "personality": "温婉", "speech_style": "温润"},
        ],
        "foreshadowings": [
            {"id": 1, "content": "古剑铭文", "planted_chapter": 3,
             "expected_resolve_chapter": 12, "status": "planted"},
        ],
        "plot_blocks": [
            {"id": 1, "title": "开篇", "chapter_start": 1, "chapter_end": 6,
             "expected_mood": "悬念"},
        ],
        "style_constraints": {
            "taboo_words": ["不禁", "竟然", "下意识"],
            "forbidden_patterns": ["以……开头"],
            "abstract_rules": ["每段结尾不做总结"],
        },
        "current_chapter_outline": {
            "chapter_number": 5, "title": "暗夜来访",
            "scene": "夜雨中的客栈", "emotional_arc": "警觉→震惊",
            "target_words": 3000, "confirmed": True,
        },
        "recent_timeline": [
            {"chapter": 4, "summary": "林动初遇神秘人", "emotion_tag": "悬疑"},
        ],
    }
    rendered = render_context_block(data)
    json_text = json.dumps(data, ensure_ascii=False, default=str)
    ratio = len(rendered) / max(len(json_text), 1)
    assert ratio < 1.3, f"渲染输出膨胀过多：{len(rendered)} / {len(json_text)} = {ratio:.2f}"


def test_field_labels_cover_core_top_keys():
    """快速契约测试：核心顶层 key 必须在 FIELD_LABELS 中。

    防止后续编辑 FIELD_LABELS 时误删核心映射。
    """
    required = {
        "outline", "world_setting", "characters", "plot_blocks",
        "foreshadowings", "pending_foreshadowings", "overdue_foreshadowings",
        "style_constraints", "current_chapter_outline", "previous_chapter_closing",
        "current_plot_block", "recent_timeline", "phase", "current_chapter_number",
        "critical_rules",
    }
    missing = required - set(FIELD_LABELS.keys())
    assert not missing, f"FIELD_LABELS 缺失核心顶层 key: {missing}"
