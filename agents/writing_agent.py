# agents/writing_agent.py
"""写作 Agent 实现"""

from typing import Dict, Any, Optional
from agents.base import BaseAgent
from core.state import ProjectState
from prompts.writing import GENERATE_CHAPTER_CONTENT_PROMPT, REWRITE_CHAPTER_CONTENT_PROMPT


class WritingAgent(BaseAgent):
    """写作 Agent：生成章节正文"""

    def __init__(self, project_state: ProjectState):
        self.project_state = project_state
        super().__init__(
            name="写作Agent",
            system_prompt="你是一个专业的小说作家，擅长写出引人入胜的故事。"
        )

    def generate_chapter_content(
        self,
        chapter_outline: Dict[str, Any],
        previous_chapter_ending: str = ""
    ) -> str:
        """
        生成章节正文

        Args:
            chapter_outline: 章节大纲
            previous_chapter_ending: 上一章结尾内容

        Returns:
            章节正文
        """
        collected_info = self.project_state.get_collected_info()

        prompt = GENERATE_CHAPTER_CONTENT_PROMPT.format(
            chapter_outline=self._format_chapter_outline(chapter_outline),
            previous_chapter_ending=previous_chapter_ending or "（这是第一章，无前文）",
            genre=collected_info.get("genre", "未指定"),
            main_characters=collected_info.get("main_characters", "未指定"),
            world_setting=collected_info.get("world_setting", "未指定"),
            style_preference=collected_info.get("style_preference", "未指定")
        )

        response = self.llm_client.chat_with_system(
            "你是一个专业的小说作家。",
            [{"role": "user", "content": prompt}]
        )

        return response

    def rewrite_chapter_content(
        self,
        chapter_outline: Dict[str, Any],
        original_content: str,
        review_feedback: str
    ) -> str:
        """
        根据审核反馈重写章节

        Args:
            chapter_outline: 章节大纲
            original_content: 原始内容
            review_feedback: 审核反馈

        Returns:
            重写后的章节正文
        """
        prompt = REWRITE_CHAPTER_CONTENT_PROMPT.format(
            chapter_outline=self._format_chapter_outline(chapter_outline),
            original_content=original_content,
            review_feedback=review_feedback
        )

        response = self.llm_client.chat_with_system(
            "你是一个专业的小说作家。",
            [{"role": "user", "content": prompt}]
        )

        return response

    def _format_chapter_outline(self, chapter: Dict[str, Any]) -> str:
        """格式化章节大纲"""
        lines = []
        lines.append(f"章节：{chapter.get('title', '未命名')}")
        lines.append(f"场景：{chapter.get('scene', '未指定')}")
        lines.append(f"人物：{chapter.get('characters', '未指定')}")
        lines.append(f"情节：{chapter.get('plot', '未指定')}")
        lines.append(f"冲突：{chapter.get('conflict', '未指定')}")
        lines.append(f"结局：{chapter.get('ending', '未指定')}")
        return "\n".join(lines)