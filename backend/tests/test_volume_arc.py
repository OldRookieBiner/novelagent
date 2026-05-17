"""弧/卷规划节点测试"""

import pytest


class TestParseVolumeArcPlan:
    """解析 LLM 输出的弧/卷结构"""

    def test_parse_standard_format(self):
        from app.agents.nodes.volume_arc_planning import parse_volume_arc_plan

        response = """卷1《风云初起》
  弧1《初入江湖》：15章
  概要：少年学艺，初入江湖
  弧2《门派试炼》：20章
  概要：参加门派大比，崭露头角
卷2《江湖恩怨》
  弧3《恩怨起》：18章
  概要：卷入江湖纷争"""

        volumes, arcs = parse_volume_arc_plan(response, total_chapters=53)
        assert len(volumes) == 2
        assert volumes[0]["volume_number"] == 1
        assert volumes[0]["title"] == "风云初起"
        assert len(arcs) == 3
        assert arcs[0]["arc_number"] == 1
        assert arcs[0]["volume_number"] == 1
        assert arcs[0]["chapter_count"] == 15
        assert arcs[0]["title"] == "初入江湖"
        assert arcs[2]["volume_number"] == 2

    def test_parse_single_volume(self):
        from app.agents.nodes.volume_arc_planning import parse_volume_arc_plan

        response = """卷1《开篇》
  弧1《起始》：10章
  概要：故事开始"""

        volumes, arcs = parse_volume_arc_plan(response, total_chapters=10)
        assert len(volumes) == 1
        assert len(arcs) == 1

    def test_total_chapters_override(self):
        """总章节数偏差过大时，按比例调整"""
        from app.agents.nodes.volume_arc_planning import parse_volume_arc_plan

        response = """卷1《测试》
  弧1《弧1》：10章
  概要：测试"""

        volumes, arcs = parse_volume_arc_plan(response, total_chapters=50)
        # 10 vs 50，偏差 >20%，应调整
        assert arcs[0]["chapter_count"] == 50
