"""Tests for Agent node functions"""

import pytest
from app.agents.nodes.outline_generation import (
    parse_outline,
    parse_chapter_count,
)
from app.agents.nodes.chapter_generation import (
    parse_chapter_outlines,
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


class TestChapterOutlineParsing:
    """Tests for chapter outline parsing functions"""

    def test_parse_single_chapter(self):
        """Should parse a single chapter outline"""
        response = """
第1章：初入仙门
场景：青云山脚下的小村庄
人物：林风、神秘老者
情节：少年林风在山中采药时偶遇一位神秘老者，被测试资质后发现是万年难遇的修仙奇才。
冲突：林风需要说服家人让他离开家乡去修仙。
结局：林风告别家人，随老者踏上修仙之路。
预计字数：2500
"""
        chapters = parse_chapter_outlines(response)

        assert len(chapters) == 1
        assert chapters[0]["chapter_number"] == 1
        assert chapters[0]["title"] == "初入仙门"
        assert chapters[0]["scene"] == "青云山脚下的小村庄"
        assert chapters[0]["target_words"] == 2500

    def test_parse_multiple_chapters(self):
        """Should parse multiple chapter outlines"""
        response = """
第1章：开始
场景：城市
人物：主角
情节：故事开始。
冲突：主角面临选择。
结局：主角做出决定。
预计字数：2000

第2章：冒险
场景：森林
人物：主角、伙伴
情节：主角开始冒险之旅。
冲突：遇到危险。
结局：化险为夷。
预计字数：2500

第3章：高潮
场景：城堡
人物：主角、敌人
情节：最终对决。
冲突：生死存亡。
结局：主角胜利。
预计字数：3000
"""
        chapters = parse_chapter_outlines(response)

        assert len(chapters) == 3
        assert chapters[0]["chapter_number"] == 1
        assert chapters[1]["chapter_number"] == 2
        assert chapters[2]["chapter_number"] == 3
        assert chapters[2]["title"] == "高潮"

    def test_parse_chapter_outline_partial(self):
        """Should handle partial chapter outline data"""
        response = """
第1章：测试章节
场景：测试场景
"""
        chapters = parse_chapter_outlines(response)

        assert len(chapters) == 1
        assert chapters[0]["scene"] == "测试场景"
        # Missing fields should have defaults
        assert chapters[0]["target_words"] == 3000

    def test_parse_chapter_outline_empty(self):
        """Should handle empty response"""
        chapters = parse_chapter_outlines("")
        assert chapters == []


class TestPromptTemplates:
    """Tests for prompt templates"""

    def test_outline_generation_prompt_variables(self):
        """Outline generation prompt should contain key variables"""
        from app.agents.prompts import OUTLINE_GENERATION_PROMPT

        # Check prompt contains key instructions
        assert "人物设定" in OUTLINE_GENERATION_PROMPT
        assert "世界观" in OUTLINE_GENERATION_PROMPT
        assert "情感曲线" in OUTLINE_GENERATION_PROMPT
        assert "inspiration_template" in OUTLINE_GENERATION_PROMPT

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
            inspiration_template=inspiration_template,
            chapter_count=40
        )

        assert "玄幻" in prompt
        assert "林风" in prompt
        assert "修仙世界" in prompt
        assert "40" in prompt

    def test_chapter_content_prompt_format(self):
        """Chapter content prompt should format correctly"""
        from app.agents.prompts import GENERATE_CHAPTER_CONTENT_PROMPT

        prompt = GENERATE_CHAPTER_CONTENT_PROMPT.format(
            chapter_outline="第1章：测试章节\n场景：城市",
            previous_ending="上一章的结尾...",
            genre="都市",
            main_characters="张三",
            world_setting="现代都市",
            style_preference="轻松幽默"
        )

        assert "第1章" in prompt
        assert "张三" in prompt