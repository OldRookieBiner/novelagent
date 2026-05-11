"""节点共享工具函数的单元测试"""

import pytest
from unittest.mock import MagicMock
from app.agents.nodes.utils import (
    _format_chapter_outline_str,
    format_characters_info,
    format_relations_info,
    format_evolution_info,
    format_world_setting,
)


class TestFormatChapterOutlineStr:
    """测试格式化章节大纲为字符串"""

    def test_complete_chapter_outline(self):
        """应正确格式化包含所有字段的章节大纲"""
        chapter_outline = {
            "title": "初入江湖",
            "scene": "古城集市",
            "characters": "林风、苏瑶",
            "plot": "林风初到古城，遭遇劫匪",
            "conflict": "林风与劫匪的对抗",
            "turning_point": "意外获得秘籍",
            "hook": "秘籍上的神秘符号",
        }
        result = _format_chapter_outline_str(chapter_outline)

        assert "章节名：初入江湖" in result
        assert "场景：古城集市" in result
        assert "人物：林风、苏瑶" in result
        assert "情节：林风初到古城，遭遇劫匪" in result
        assert "冲突：林风与劫匪的对抗" in result
        assert "转折：意外获得秘籍" in result
        assert "钩子：秘籍上的神秘符号" in result

    def test_missing_fields_use_defaults(self):
        """缺少字段时应使用默认值"""
        chapter_outline = {"title": "测试章节"}
        result = _format_chapter_outline_str(chapter_outline)

        assert "章节名：测试章节" in result
        assert "场景：" in result
        assert "人物：" in result
        assert "转折：无" in result

    def test_empty_dict(self):
        """空字典应全部使用默认值"""
        result = _format_chapter_outline_str({})

        assert "章节名：" in result
        assert "转折：无" in result
        assert "钩子：" in result


class TestFormatCharactersInfo:
    """测试格式化人物设定信息"""

    def test_detailed_characters(self):
        """有详细人物设定时，应格式化所有字段"""
        state = {
            "characters": [
                {
                    "name": "林风",
                    "role": "主角",
                    "appearance": "剑眉星目",
                    "personality": "坚毅果敢",
                    "background": "山村少年",
                    "skills": "剑术",
                    "goals": "成为仙帝",
                }
            ]
        }
        result = format_characters_info(state)

        assert "【详细人物设定】" in result
        assert "林风（主角）" in result
        assert "外貌：剑眉星目" in result
        assert "性格：坚毅果敢" in result
        assert "背景：山村少年" in result
        assert "能力：剑术" in result
        assert "目标：成为仙帝" in result

    def test_detailed_characters_partial_fields(self):
        """详细人物设定缺少部分字段时，只输出已有字段"""
        state = {
            "characters": [
                {
                    "name": "苏瑶",
                    "role": "女主",
                    "personality": "温柔聪慧",
                }
            ]
        }
        result = format_characters_info(state)

        assert "苏瑶（女主）" in result
        assert "性格：温柔聪慧" in result
        assert "外貌" not in result
        assert "背景" not in result

    def test_detailed_characters_default_role(self):
        """详细人物设定缺少角色时应默认为配角"""
        state = {"characters": [{"name": "路人甲"}]}
        result = format_characters_info(state)

        assert "路人甲（配角）" in result

    def test_outline_characters_fallback(self):
        """无详细人物设定时，应回退到大纲人物设定"""
        state = {
            "characters": [],
            "outline_characters": [
                {"name": "林风", "personality": "坚毅", "motivation": "复仇"},
                {"name": "苏瑶", "personality": "温柔", "motivation": "守护"},
            ],
        }
        result = format_characters_info(state)

        assert "- 林风：坚毅，动机：复仇" in result
        assert "- 苏瑶：温柔，动机：守护" in result
        assert "【详细人物设定】" not in result

    def test_collected_info_custom_protagonist(self):
        """无人物设定时，应回退到灵感采集的自定义主角"""
        state = {"collected_info": {"customProtagonist": "自定义主角描述"}}
        result = format_characters_info(state)

        assert result == "自定义主角描述"

    def test_collected_info_protagonist_fallback(self):
        """自定义主角为空时，应回退到 protagonist"""
        state = {"collected_info": {"protagonist": "主角描述"}}
        result = format_characters_info(state)

        assert result == "主角描述"

    def test_no_character_info(self):
        """完全没有人物信息时，应返回未指定"""
        result = format_characters_info({})

        assert result == "未指定"


class TestFormatRelationsInfo:
    """测试格式化人物关系信息"""

    def test_no_relations(self):
        """无人物关系时应返回空字符串"""
        result = format_relations_info({"relations": []}, 1)

        assert result == ""

    def test_relations_without_description(self):
        """有人物关系但无描述时，应正确格式化"""
        state = {
            "relations": [
                {
                    "character1": "林风",
                    "character2": "苏瑶",
                    "relationship_type": "师徒",
                }
            ]
        }
        result = format_relations_info(state, 1)

        assert "【人物关系】" in result
        assert "林风 与 苏瑶：师徒" in result
        assert "（" not in result

    def test_relations_with_description(self):
        """有人物关系且有描述时，应包含描述"""
        state = {
            "relations": [
                {
                    "character1": "林风",
                    "character2": "苏瑶",
                    "relationship_type": "恋人",
                    "description": "青梅竹马，互相扶持",
                }
            ]
        }
        result = format_relations_info(state, 1)

        assert "林风 与 苏瑶：恋人（青梅竹马，互相扶持）" in result

    def test_multiple_relations(self):
        """多条人物关系都应格式化"""
        state = {
            "relations": [
                {
                    "character1": "林风",
                    "character2": "苏瑶",
                    "relationship_type": "师徒",
                },
                {
                    "character1": "林风",
                    "character2": "魔尊",
                    "relationship_type": "仇敌",
                    "description": "杀父之仇",
                },
            ]
        }
        result = format_relations_info(state, 1)

        assert "林风 与 苏瑶：师徒" in result
        assert "林风 与 魔尊：仇敌（杀父之仇）" in result

    def test_missing_relations_key(self):
        """state 中无 relations 键时应返回空字符串"""
        result = format_relations_info({}, 1)

        assert result == ""

    def test_relations_with_id_based_fields(self):
        """关系数据使用 character_a_id/character_b_id/relation_type/current_status 时应正确解析"""
        state = {
            "characters": [
                {"id": 1, "name": "林风", "role": "主角"},
                {"id": 2, "name": "苏瑶", "role": "女主"},
            ],
            "relations": [
                {
                    "character_a_id": 1,
                    "character_b_id": 2,
                    "relation_type": "师徒",
                    "current_status": "青梅竹马",
                }
            ],
        }
        result = format_relations_info(state, 1)

        assert "【人物关系】" in result
        assert "林风 与 苏瑶：师徒（青梅竹马）" in result

    def test_relations_mixed_field_formats(self):
        """两种字段命名混合时，有 character1/character2 优先使用"""
        state = {
            "characters": [
                {"id": 1, "name": "林风"},
            ],
            "relations": [
                {
                    "character1": "张三",
                    "character2": "李四",
                    "relationship_type": "敌对",
                    "character_a_id": 1,
                    "character_b_id": 2,
                    "relation_type": "合作",
                    "description": "表面合作",
                    "current_status": "暗中对抗",
                }
            ],
        }
        result = format_relations_info(state, 1)

        # character1/character2 优先于 ID 映射
        assert "张三 与 李四：敌对（表面合作）" in result

    def test_relations_id_fields_without_characters(self):
        """关系数据只有 ID 但 characters 为空时，应显示未知"""
        state = {
            "characters": [],
            "relations": [
                {
                    "character_a_id": 1,
                    "character_b_id": 2,
                    "relation_type": "敌对",
                    "current_status": "不共戴天",
                }
            ],
        }
        result = format_relations_info(state, 1)

        assert "未知 与 未知：敌对（不共戴天）" in result


class TestFormatEvolutionInfo:
    """测试格式化人物演变信息"""

    def test_no_evolution(self):
        """无演变记录和规划时应返回空字符串元组"""
        evolution_str, plans_str = format_evolution_info({}, 1)

        assert evolution_str == ""
        assert plans_str == ""

    def test_evolution_records_only_last_three(self):
        """演变历史应只取最近3条"""
        state = {
            "evolution_records": [
                {"chapter_number": 1, "actual_changes": "觉醒"},
                {"chapter_number": 2, "actual_changes": "突破"},
                {"chapter_number": 3, "actual_changes": "蜕变"},
                {"chapter_number": 4, "actual_changes": "大成"},
                {"chapter_number": 5, "actual_changes": "飞升"},
            ]
        }
        evolution_str, _ = format_evolution_info(state, 5)

        assert "【人物演变（历史）】" in evolution_str
        assert "第3章" in evolution_str
        assert "第4章" in evolution_str
        assert "第5章" in evolution_str
        assert "第1章" not in evolution_str
        assert "第2章" not in evolution_str

    def test_evolution_plans_nearby(self):
        """演变规划应只包含当前章节前后2章内的计划"""
        state = {
            "evolution_plans": [
                {"chapter_number": 1, "changes": "初遇"},
                {"chapter_number": 5, "changes": "关系转折"},
                {"chapter_number": 8, "changes": "决裂"},
                {"chapter_number": 10, "changes": "和解"},
            ]
        }
        _, plans_str = format_evolution_info(state, 5)

        # 当前章节5，前后2章范围：3~7
        assert "即将发生的关系变化" in plans_str
        assert "第5章" in plans_str
        assert "第1章" not in plans_str
        assert "第8章" not in plans_str
        assert "第10章" not in plans_str

    def test_evolution_plans_no_nearby(self):
        """当前章节附近无演变规划时，规划字符串应为空"""
        state = {
            "evolution_plans": [
                {"chapter_number": 1, "changes": "初遇"},
                {"chapter_number": 20, "changes": "决裂"},
            ]
        }
        _, plans_str = format_evolution_info(state, 10)

        assert plans_str == ""

    def test_both_evolution_records_and_plans(self):
        """同时有演变历史和规划时都应格式化"""
        state = {
            "evolution_records": [
                {"chapter_number": 3, "actual_changes": "觉醒"},
            ],
            "evolution_plans": [
                {"chapter_number": 5, "changes": "蜕变"},
            ],
        }
        evolution_str, plans_str = format_evolution_info(state, 5)

        assert "【人物演变（历史）】" in evolution_str
        assert "第3章：觉醒" in evolution_str
        assert "即将发生的关系变化" in plans_str
        assert "第5章：蜕变" in plans_str


class TestFormatWorldSetting:
    """测试格式化世界观设定"""

    def test_with_world_setting(self):
        """有大纲世界观设定时，应格式化时代和核心设定"""
        state = {
            "outline_world_setting": {
                "era": "上古时期",
                "core_rules": "灵气复苏，万族林立",
            }
        }
        result = format_world_setting(state)

        assert "时代：上古时期" in result
        assert "核心设定：灵气复苏，万族林立" in result

    def test_fallback_to_custom_world_setting(self):
        """无大纲世界观时，应回退到自定义世界观"""
        state = {"collected_info": {"customWorldSetting": "自定义世界观描述"}}
        result = format_world_setting(state)

        assert result == "自定义世界观描述"

    def test_fallback_to_world_setting(self):
        """自定义世界观为空时，应回退到 worldSetting"""
        state = {"collected_info": {"worldSetting": "修仙世界"}}
        result = format_world_setting(state)

        assert result == "修仙世界"

    def test_no_world_setting(self):
        """完全没有世界观信息时，应返回未指定"""
        result = format_world_setting({})

        assert result == "未指定"

    def test_empty_world_setting_dict(self):
        """世界观字典为空时应回退"""
        state = {
            "outline_world_setting": {},
            "collected_info": {"worldSetting": "默认世界"},
        }
        result = format_world_setting(state)

        assert result == "默认世界"


from app.agents.nodes.utils import parse_words_per_chapter


class TestParseWordsPerChapter:
    """测试解析每章字数区间"""

    def test_range_format(self):
        """range 格式应正确解析上下限"""
        lower, upper, display = parse_words_per_chapter({"wordsPerChapter": "2000-2500"})
        assert lower == 2000
        assert upper == 2500
        assert display == "2000-2500字"

    def test_custom_format(self):
        """自定义字数应上下浮动 10%"""
        lower, upper, display = parse_words_per_chapter({
            "wordsPerChapter": "custom",
            "customWordsPerChapter": 3000
        })
        assert lower == 2700
        assert upper == 3300
        assert display == "约3000字"

    def test_custom_without_value(self):
        """自定义模式但无值时应使用默认值"""
        lower, upper, display = parse_words_per_chapter({
            "wordsPerChapter": "custom"
        })
        assert lower == 2000
        assert upper == 3000
        assert "字" in display

    def test_empty_words_per_chapter(self):
        """空值应使用默认值"""
        lower, upper, display = parse_words_per_chapter({})
        assert lower == 2000
        assert upper == 3000

    def test_invalid_range_format(self):
        """无效的 range 字符串应使用默认值"""
        lower, upper, display = parse_words_per_chapter({"wordsPerChapter": "abc"})
        assert lower == 2000
        assert upper == 3000

    def test_single_number_range(self):
        """纯数字字符串（非 range）应解析为上下限相同"""
        lower, upper, display = parse_words_per_chapter({"wordsPerChapter": "3000"})
        assert lower == 3000
        assert upper == 3000
        assert display == "3000字"

    def test_none_collected_info(self):
        """None 输入应使用默认值"""
        lower, upper, display = parse_words_per_chapter(None)
        assert lower == 2000
        assert upper == 3000


class TestGetLlmFromStateAsync:
    """测试 get_llm_from_state_async 的可选 db 参数"""

    @pytest.mark.asyncio
    async def test_accepts_db_param(self):
        """get_llm_from_state_async 应接受可选的 db 参数"""
        from app.utils.llm import get_llm_from_state_async

        mock_db = MagicMock()
        state = {"project_id": 1, "llm_config_id": None}

        # 验证函数签名支持 db 参数（即使实际调用会失败因为 mock 不完整）
        # 这测试的是接口，不是完整行为
        import inspect
        sig = inspect.signature(get_llm_from_state_async)
        params = list(sig.parameters.keys())
        assert "db" in params, f"get_llm_from_state_async should have 'db' parameter, got: {params}"


class TestRelationGenerationNode:
    """测试 relation_generation_node 的重构"""

    def test_accepts_config_param(self):
        """generate_relations_node 应接受可选的 config 参数"""
        from app.agents.nodes.relation_generation import generate_relations_node
        import inspect

        sig = inspect.signature(generate_relations_node)
        params = list(sig.parameters.keys())
        assert "config" in params, f"generate_relations_node should have 'config' parameter, got: {params}"

    @pytest.mark.asyncio
    async def test_uses_state_characters_with_ids(self):
        """generate_relations_node 应从 state['characters'] 读取角色（带 id），不查询 DB"""
        from app.agents.nodes.relation_generation import generate_relations_node
        from unittest.mock import patch, AsyncMock, MagicMock

        state = {
            "project_id": 1,
            "characters": [
                {"id": 1, "name": "Alice", "role": "主角", "personality": "Brave", "core_motivation": "Save"},
                {"id": 2, "name": "Bob", "role": "配角", "personality": "Cautious", "core_motivation": "Protect"},
            ],
            "outline_world_setting": {"era": "现代"},
            "outline_summary": "A story",
        }

        config = {
            "configurable": {
                "prompts": {
                    "relation_generation": "Generate relations for: {characters_text}"
                }
            }
        }

        # Mock LLM
        with patch("app.agents.nodes.relation_generation.get_llm_from_state_async") as mock_llm:
            mock_llm_instance = AsyncMock()
            mock_llm_instance.chat = AsyncMock(return_value="- Alice | Bob | 信任 | 80 | Friends | 稳定")
            mock_llm.return_value = mock_llm_instance

            result = await generate_relations_node(state, config=config)

        assert "relations" in result
        assert len(result["relations"]) >= 1
        # 验证使用的是 state 中的角色 id
        if result["relations"]:
            assert result["relations"][0]["character_a_id"] in [1, 2]
            assert result["relations"][0]["character_b_id"] in [1, 2]

    @pytest.mark.asyncio
    async def test_uses_config_prompts(self):
        """generate_relations_node 应从 config['prompts'] 读取 prompt"""
        from app.agents.nodes.relation_generation import generate_relations_node
        from unittest.mock import patch, AsyncMock

        state = {
            "project_id": 1,
            "characters": [
                {"id": 1, "name": "Alice", "role": "主角", "personality": "", "core_motivation": ""},
                {"id": 2, "name": "Bob", "role": "配角", "personality": "", "core_motivation": ""},
            ],
            "outline_world_setting": {},
            "outline_summary": "Test",
        }

        custom_prompt = "CUSTOM_PROMPT_TEMPLATE: {characters_text}"

        config = {
            "configurable": {
                "prompts": {
                    "relation_generation": custom_prompt
                }
            }
        }

        with patch("app.agents.nodes.relation_generation.get_llm_from_state_async") as mock_llm:
            mock_llm_instance = AsyncMock()
            mock_llm_instance.chat = AsyncMock(return_value="- Alice | Bob | 信任 | 50 | Test | 稳定")
            mock_llm.return_value = mock_llm_instance

            await generate_relations_node(state, config=config)

            # 验证 LLM chat 被调用，且 prompt 包含自定义模板内容
            mock_llm_instance.chat.assert_called_once()
            call_args = mock_llm_instance.chat.call_args
            # call_args[0][0] 是消息列表，[0] 是第一条消息，["content"] 是内容
            prompt_used = call_args[0][0][0]["content"]
            assert "CUSTOM_PROMPT_TEMPLATE" in prompt_used


class TestCharacterGenerationNode:
    """测试 character_generation_node 的重构"""

    def test_accepts_config_param(self):
        """create_characters_from_outline_node 应接受可选的 config 参数"""
        from app.agents.nodes.character_generation import create_characters_from_outline_node
        import inspect

        sig = inspect.signature(create_characters_from_outline_node)
        params = list(sig.parameters.keys())
        assert "config" in params, f"create_characters_from_outline_node should have 'config' parameter, got: {params}"

    @pytest.mark.asyncio
    async def test_uses_config_prompts(self):
        """create_characters_from_outline_node 应从 config['prompts'] 读取 prompt"""
        from app.agents.nodes.character_generation import create_characters_from_outline_node
        from unittest.mock import patch, AsyncMock

        state = {
            "project_id": 1,
            "outline_summary": "A story about heroes",
            "outline_world_setting": {"era": "古代"},
        }

        custom_prompt = "CUSTOM_CHARACTER_PROMPT: {outline_summary} in {world_era}"

        config = {
            "configurable": {
                "prompts": {
                    "character_generation": custom_prompt
                }
            }
        }

        with patch("app.agents.nodes.character_generation.get_llm_from_state_async") as mock_llm:
            mock_llm_instance = AsyncMock()
            mock_llm_instance.chat = AsyncMock(return_value="- 主角 | 主角描述")
            mock_llm.return_value = mock_llm_instance

            await create_characters_from_outline_node(state, config=config)

            # 验证 LLM chat 被调用，且 prompt 包含自定义模板内容
            mock_llm_instance.chat.assert_called_once()
            call_args = mock_llm_instance.chat.call_args
            # call_args[0][0] 是消息列表，[0] 是第一条消息，["content"] 是内容
            prompt_used = call_args[0][0][0]["content"]
            assert "CUSTOM_CHARACTER_PROMPT" in prompt_used

