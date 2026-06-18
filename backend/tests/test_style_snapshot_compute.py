"""_compute_style_snapshot 单测 — 覆盖 P1.3 新增 ai_marker_density 与 sentence_variety"""
import pytest

from app.agents.tools.creation.generate_chapter_content import _compute_style_snapshot


def test_compute_style_snapshot_empty_returns_zero_metrics():
    snap = _compute_style_snapshot("")
    assert snap["paragraph_count"] == 0
    assert snap["dialogue_ratio"] == 0.0
    assert snap["ai_marker_density"] == 0.0
    assert snap["sentence_variety"] == 0.0


def test_compute_style_snapshot_includes_ai_marker_density():
    """命中 FORBIDDEN_WORDS 字符占比应被计入 ai_marker_density"""
    # "不禁" 命中 1 次（2 字符），文本长度约 50 字符
    text = "他走在路上。心里不禁想着许多事情。这是日常的一天。"
    snap = _compute_style_snapshot(text)
    assert snap["ai_marker_density"] > 0.0
    # 最多不超过 1.0
    assert snap["ai_marker_density"] <= 1.0


def test_compute_style_snapshot_sentence_variety_is_zero_for_uniform_lengths():
    """每句长度相同时句长标准差为 0"""
    # 三句各 5 字（不含句号），变异性应近 0
    text = "他走在路上。她看着远方。我读着书本。"
    snap = _compute_style_snapshot(text)
    assert snap["sentence_variety"] == pytest.approx(0.0, abs=0.01)


def test_compute_style_snapshot_sentence_variety_positive_for_varied_lengths():
    text = "他来。她坐在窗前的木椅上望着远方思考着这一切。短。"
    snap = _compute_style_snapshot(text)
    assert snap["sentence_variety"] > 0.0


def test_compute_style_snapshot_returns_all_expected_keys():
    snap = _compute_style_snapshot("一句话。")
    for key in (
        "paragraph_count",
        "avg_paragraph_length",
        "dialogue_ratio",
        "avg_sentence_length",
        "ai_marker_density",
        "sentence_variety",
    ):
        assert key in snap
