"""Agent nodes

导出创作智能体节点函数。
旧版节点函数（generate_outline_node 等）已移除，
保留解析函数以兼容旧 API。
"""

from app.agents.nodes.outline_generation import outline_generation_node
from app.agents.nodes.character_generation import (
    character_generation_node,
    parse_character_generation_response,
)
from app.agents.nodes.relation_generation import (
    relation_generation_node,
    parse_relations_response,
)

__all__ = [
    # 创作智能体节点
    "outline_generation_node",
    "character_generation_node",
    "relation_generation_node",
    # 解析工具（旧 API 兼容）
    "parse_character_generation_response",
    "parse_relations_response",
]
