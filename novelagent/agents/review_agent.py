# agents/review_agent.py
"""审核 Agent 实现"""

from typing import Dict, Any, Tuple
from agents.base import BaseAgent
from core.state import ProjectState
from prompts.review import REVIEW_CHAPTER_PROMPT


class ReviewAgent(BaseAgent):
    """审核 Agent：检查章节质量"""

    def __init__(self, project_state: ProjectState):
        self.project_state = project_state
        super().__init__(
            name="审核Agent",
            system_prompt="你是一个专业的小说编辑，擅长发现文稿中的问题。"
        )

    def review_chapter(
        self,
        chapter_outline: Dict[str, Any],
        chapter_content: str
    ) -> Tuple[bool, str]:
        """
        审核章节

        Args:
            chapter_outline: 章节大纲
            chapter_content: 章节正文

        Returns:
            (是否通过, 审核结果详情)
        """
        collected_info = self.project_state.get_collected_info()

        prompt = REVIEW_CHAPTER_PROMPT.format(
            chapter_outline=self._format_chapter_outline(chapter_outline),
            chapter_content=chapter_content,
            genre=collected_info.get("genre", "未指定"),
            main_characters=collected_info.get("main_characters", "未指定"),
            style_preference=collected_info.get("style_preference", "未指定")
        )

        response = self.llm_client.chat_with_system(
            "你是一个专业的小说编辑。",
            [{"role": "user", "content": prompt}]
        )

        # 解析审核结果
        passed = "【审核结果】通过" in response

        return passed, response

    def _format_chapter_outline(self, chapter: Dict[str, Any]) -> str:
        """格式化章节大纲"""
        lines = []
        lines.append(f"章节：{chapter.get('title', '未命名')}")
        lines.append(f"情节：{chapter.get('plot', '未指定')}")
        return "\n".join(lines)