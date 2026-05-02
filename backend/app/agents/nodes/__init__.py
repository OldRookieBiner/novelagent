"""Agent nodes"""

from app.agents.nodes.outline_generation import (
    generate_outline_node,
    generate_outline_stream,
    parse_outline,
)
from app.agents.nodes.chapter_generation import (
    generate_single_chapter_outline,
    generate_chapter_outlines_stream,
    generate_chapter_content_stream,
    parse_single_chapter_outline,
)
from app.agents.nodes.review import (
    review_chapter_node,
    parse_review_result,
    check_review_passed,
)
from app.agents.nodes.rewrite import rewrite_chapter_node, rewrite_with_retry
from app.agents.nodes.character_generation import (
    create_characters_from_outline_node,
    extract_characters_from_outline,
)
from app.agents.nodes.relation_generation import (
    generate_relations_node,
    parse_relations_response,
)

__all__ = [
    # Outline
    "generate_outline_node",
    "generate_outline_stream",
    "parse_outline",
    # Chapter outline
    "generate_single_chapter_outline",
    "generate_chapter_outlines_stream",
    "parse_single_chapter_outline",
    # Chapter content
    "generate_chapter_content_stream",
    # Review
    "review_chapter_node",
    "parse_review_result",
    "check_review_passed",
    # Rewrite
    "rewrite_chapter_node",
    "rewrite_with_retry",
    # Character generation
    "create_characters_from_outline_node",
    "extract_characters_from_outline",
    # Relation generation
    "generate_relations_node",
    "parse_relations_response",
]
