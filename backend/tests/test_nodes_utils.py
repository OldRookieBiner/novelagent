"""节点共享工具函数的单元测试"""

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
