"""验证所有节点使用 get_prompts_from_state() 获取 prompt"""
import inspect
from app.agents.nodes import character_generation, relation_generation
from app.agents.nodes import arc_outline_generation, volume_arc_planning
from app.agents.nodes import chapter_generation


def test_character_generation_uses_get_prompts_from_state():
    source = inspect.getsource(character_generation.create_characters_from_outline_node)
    assert "get_prompts_from_state" in source
    assert 'state.get("_prompts", {})' not in source


def test_relation_generation_uses_get_prompts_from_state():
    source = inspect.getsource(relation_generation.generate_relations_node)
    assert "get_prompts_from_state" in source
    assert 'state.get("_prompts", {})' not in source


def test_arc_outline_uses_get_prompts_from_state():
    source = inspect.getsource(arc_outline_generation._build_arc_outline_messages)
    assert "get_prompts_from_state" in source
    assert 'state.get("_prompts"' not in source


def test_volume_arc_uses_get_prompts_from_state():
    source = inspect.getsource(volume_arc_planning.volume_arc_planning_node)
    assert "get_prompts_from_state" in source
    assert 'state.get("_prompts"' not in source


def test_chapter_outline_uses_get_prompts_from_state():
    source = inspect.getsource(chapter_generation.generate_single_chapter_outline)
    assert "get_prompts_from_state" in source
    assert 'state.get("_prompts", {})' not in source
