"""节点级温度控制测试"""

from app.agents.constants import NODE_TEMPERATURES


def test_all_nodes_have_temperature():
    """所有生产节点都配置了温度"""
    required_nodes = [
        "outline_generation", "character_generation", "relation_generation",
        "chapter_outline_generation", "chapter_content_draft",
        "chapter_content_self_check", "chapter_content_refine",
        "review", "rewrite", "volume_arc_generation", "arc_outline_generation",
    ]
    for node in required_nodes:
        assert node in NODE_TEMPERATURES, f"Missing temperature for {node}"
        assert 0.0 <= NODE_TEMPERATURES[node] <= 2.0, f"Invalid temperature for {node}"


def test_temperature_values_reasonable():
    """温度值在合理范围"""
    # 创意任务温度较高
    assert NODE_TEMPERATURES["outline_generation"] >= 0.7
    assert NODE_TEMPERATURES["chapter_content_draft"] >= 0.7
    # 分析/审核任务温度较低
    assert NODE_TEMPERATURES["review"] <= 0.3
    assert NODE_TEMPERATURES["chapter_content_self_check"] <= 0.3
