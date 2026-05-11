"""Tests for Agent node functions"""

from app.agents.nodes.outline_generation import (
    parse_outline,
    parse_chapter_count,
)


class TestOutlineParsing:
    """Tests for outline parsing functions"""

    def test_parse_outline_complete(self):
        """Should parse complete outline"""
        response = """
标题：修仙传说
概述：一个少年从凡人成长为仙帝的故事，历经磨难，最终证道。
主要情节节点：
1. 少年林风在山村被仙人发现资质
2. 进入修仙宗门，开始修炼之路
3. 遭遇宗门危机，被迫出走
4. 在生死边缘领悟大道
5. 成为一代仙帝，守护天下
"""
        outline = parse_outline(response)

        assert outline["title"] == "修仙传说"
        assert "少年" in outline["summary"]
        assert len(outline["plot_points"]) == 5

    def test_parse_outline_no_title(self):
        """Should handle missing title"""
        response = """
概述：这是一个测试故事。
主要情节节点：
1. 开始
2. 结束
"""
        outline = parse_outline(response)

        assert outline["title"] == ""
        assert "测试" in outline["summary"]

    def test_parse_outline_empty(self):
        """Should handle empty response"""
        outline = parse_outline("")

        assert outline["title"] == ""
        assert outline["summary"] == ""
        assert outline["plot_points"] == []

    def test_parse_outline_deepseek_heading_characters(self):
        """Should parse DeepSeek heading-style character blocks"""
        response = """
# 小说大纲：《后悔药》

## 概述
少年沈墨被废掉灵脉后绑定后悔药系统。

# 三、人物设定

### 主角：沈墨 | 表面嬉皮笑脸但内心敏感自卑
- **核心动机**：证明废物也有存在的价值
- **成长弧线**：自暴自弃 → 疯狂报复 → 走出第三条路

### 核心反派：秦沧 | 曾经的挚友 | 被迫背叛主角
- 行为合理性：妹妹被宗主扣作人质

# 四、世界观与势力

### 时代背景：苍玄大陆，修仙纪元3000年
### 核心设定：灵脉决定一切

# 五、情节节点（要求埋设伏笔）
1. 沈墨绑定系统 | 冲突：寿命倒扣 | 钩子：系统来源
2. 秦沧首次后悔 | 冲突：真相难辨 | 钩子：妹妹人质

# 六、情感曲线与节奏
低谷 → 反击 → 和解
"""

        outline = parse_outline(response)

        assert "人物设定" not in outline["summary"]
        assert len(outline["characters"]) == 2
        assert outline["characters"][0]["name"] == "沈墨"
        assert outline["characters"][0]["role"] == "主角"
        assert "嬉皮笑脸" in outline["characters"][0]["personality"]
        assert "存在的价值" in outline["characters"][0]["motivation"]
        assert "第三条路" in outline["characters"][0]["arc"]
        assert outline["characters"][1]["name"] == "秦沧"
        assert "曾经的挚友" in outline["characters"][1]["personality"]
        assert outline["world_setting"]["era"] == "苍玄大陆，修仙纪元3000年"
        assert outline["world_setting"]["core_rules"] == "灵脉决定一切"
        assert len(outline["plot_points"]) == 2

    def test_parse_outline_bold_list_characters(self):
        """Should parse bold list-style character blocks"""
        response = """
# 小说大纲：《师叔别浪了》

## 概述
林渊重生后绑定情绪值系统。

# 三、人物设定
- **主角：林渊 | 表面路痴呆萌、实则冷静算死草**
  - 口头禅：我记得路
  - 核心动机：让师姐尝遍前世痛苦
  - 成长弧线：伪装复仇者 → 动摇 → 顿悟

- **重要配角：凌霄 | 林渊师兄 | 良心警报器**
  - 不可替代作用：提醒主角不要越过底线

# 四、世界观与势力
- **时代背景**：修仙界天道纪元
- **核心设定**：情绪是毒

# 五、情节节点（要求埋设伏笔）
1. 林渊觉醒系统 | 冲突：身份暴露 | 钩子：系统代价

# 六、情感曲线与节奏
压抑 → 荒诞 → 释然
"""

        outline = parse_outline(response)

        assert len(outline["characters"]) == 2
        assert outline["characters"][0]["name"] == "林渊"
        assert "路痴呆萌" in outline["characters"][0]["personality"]
        assert "我记得路" in outline["characters"][0]["personality"]
        assert "前世痛苦" in outline["characters"][0]["motivation"]
        assert outline["characters"][1]["name"] == "凌霄"
        assert "林渊师兄" in outline["characters"][1]["personality"]
        assert outline["world_setting"]["era"] == "修仙界天道纪元"
        assert outline["world_setting"]["core_rules"] == "情绪是毒"
        assert len(outline["plot_points"]) == 1

    def test_parse_chapter_count_explicit(self):
        """Should parse explicit chapter count"""
        response = """
建议章节数：15
理由：故事较长，需要足够的章节展开。
"""
        count = parse_chapter_count(response)
        assert count == 15

    def test_parse_chapter_count_with_colon(self):
        """Should parse with different colon format"""
        response = "建议章节数:20"
        count = parse_chapter_count(response)
        assert count == 20

    def test_parse_chapter_count_default(self):
        """Should return default when not found"""
        response = "这是一些文本，没有章节数建议"
        count = parse_chapter_count(response)
        assert count == 10  # Default


class TestPromptTemplates:
    """Tests for prompt templates"""

    def test_outline_generation_prompt_variables(self):
        """Outline generation prompt should contain key variables
        Note: 人物设定 has been moved to CHARACTER_GENERATION_PROMPT as part of
        the character prompt split feature (v0.8.2).
        """
        from app.agents.prompts import OUTLINE_GENERATION_PROMPT

        # Check prompt contains key instructions
        assert "世界观" in OUTLINE_GENERATION_PROMPT
        assert "情感曲线" in OUTLINE_GENERATION_PROMPT
        assert "inspiration_template" in OUTLINE_GENERATION_PROMPT

    def test_character_generation_prompt_variables(self):
        """Character generation prompt should contain key variables
        Note: The prompt uses 角色 (role/character) terminology for character design,
        consistent with the character prompt split feature (v0.8.2).
        """
        from app.agents.prompts import CHARACTER_GENERATION_PROMPT

        # Check prompt contains key instructions
        assert "角色" in CHARACTER_GENERATION_PROMPT
        assert "outline" in CHARACTER_GENERATION_PROMPT
        assert "world_era" in CHARACTER_GENERATION_PROMPT or "outline_summary" in CHARACTER_GENERATION_PROMPT

    def test_generate_outline_prompt_format(self):
        """Outline generation prompt should format correctly"""
        from app.agents.prompts import OUTLINE_GENERATION_PROMPT

        inspiration_template = """# 小说创作灵感

## 基本信息
- **小说类型**：玄幻
- **核心主题**：成长与复仇

## 人物设定
- **主角**：林风，少年天才

## 世界设定
- **世界观**：修仙世界
"""

        prompt = OUTLINE_GENERATION_PROMPT.format(
            inspiration_template=inspiration_template, chapter_count=40
        )

        assert "玄幻" in prompt
        assert "林风" in prompt
        assert "修仙世界" in prompt
        assert "40" in prompt

    def test_chapter_content_prompt_format(self):
        """Chapter content prompt should format correctly with system/user dict"""
        from app.agents.prompts import DEFAULT_PROMPTS

        # chapter_content_generation 是 dict 格式：{"system": ..., "user": ...}
        prompt_data = DEFAULT_PROMPTS["chapter_content_generation"]
        assert isinstance(prompt_data, dict), "chapter_content_generation should be dict"
        assert "system" in prompt_data, "Should have system key"
        assert "user" in prompt_data, "Should have user key"

        # 格式化 user 模板（用户可自定义部分）
        user_prompt = prompt_data["user"].format(
            chapter_outline="第1章：测试章节\n场景：城市",
            previous_ending="上一章的结尾...",
            genre="都市",
            min_words=3000,
            suggested_max=4500,
            style_preference="轻松幽默",
        )

        # 格式化 system 模板（角色定位+规则+上下文）
        system_prompt = prompt_data["system"].format(
            previous_context="前文内容...",
            main_characters="张三",
            world_setting="现代都市",
            forbidden_words="禁用词列表",
        )

        assert "第1章" in user_prompt
        assert "张三" in system_prompt
        assert "茅盾文学奖" in system_prompt
