# agents/outline_agent.py
"""大纲 Agent 实现"""

import json
import re
from typing import Dict, Any, Tuple
from agents.base import BaseAgent
from core.state import ProjectState
from prompts.outline import (
    COLLECT_INFO_SYSTEM_PROMPT,
    CHECK_INFO_PROMPT,
    GENERATE_OUTLINE_SYSTEM_PROMPT,
    GENERATE_OUTLINE_USER_PROMPT,
    MODIFY_OUTLINE_SYSTEM_PROMPT
)
from config import INFO_REQUIRED_FIELDS


class OutlineAgent(BaseAgent):
    """大纲 Agent：收集信息、生成大纲、确认修改"""

    def __init__(self, project_state: ProjectState):
        self.project_state = project_state
        super().__init__(
            name="大纲Agent",
            system_prompt=COLLECT_INFO_SYSTEM_PROMPT.format(
                collected_info=self._format_collected_info()
            )
        )

        # 加载已有对话历史
        history = self.project_state.get_conversation_history()
        if history:
            self.load_conversation(history)

    def _format_collected_info(self) -> str:
        """格式化已收集的信息"""
        info = self.project_state.get_collected_info()
        if not info:
            return "(尚未收集任何信息)"

        lines = []
        for key, value in info.items():
            lines.append(f"- {key}: {value}")
        return "\n".join(lines)

    def _parse_collected_info(self, response: str) -> Dict[str, Any]:
        """
        从 LLM 回复中解析收集的信息

        尝试从回复中提取关键信息更新到 collected_info
        """
        current_info = self.project_state.get_collected_info()

        # 简单的关键词匹配提取（后续可以改进）
        # 这里不做复杂解析，让 LLM 在对话中自然积累信息
        # 实际信息由用户输入和 Agent 提问交互产生

        return current_info

    def _check_info_status(self) -> Tuple[bool, str]:
        """
        检查信息是否充足

        Returns:
            (是否充足, 缺失信息描述或"充足")
        """
        info = self.project_state.get_collected_info()

        # 使用 LLM 判断信息充足度
        check_prompt = CHECK_INFO_PROMPT.format(
            collected_info=self._format_collected_info()
        )

        # 单独调用，不影响主对话历史
        response = self.llm_client.chat_with_system(
            "你是一个信息分析助手，只做分析不做创作。",
            [{"role": "user", "content": check_prompt}]
        )

        # 解析回复判断是否充足
        if "信息已充足" in response:
            return True, "充足"

        # 提取缺失信息和问题
        return False, response

    def process_user_input(self, user_input: str) -> str:
        """
        处理用户输入

        Args:
            user_input: 用户输入的内容

        Returns:
            Agent 的回复
        """
        stage = self.project_state.get_stage()

        if stage == "collecting_info":
            return self._handle_collecting_info(user_input)
        elif stage == "generating_outline":
            return self._handle_generating_outline(user_input)
        elif stage == "outline_confirming":
            return self._handle_outline_confirming(user_input)
        else:
            return "项目已完成大纲阶段，请使用写作Agent继续。"

    def _handle_collecting_info(self, user_input: str) -> str:
        """处理信息收集阶段的用户输入"""

        # 用户确认开始生成大纲
        if "开始生成大纲" in user_input or "可以开始" in user_input:
            # 先检查信息是否真的充足
            is_sufficient, status = self._check_info_status()
            if is_sufficient:
                self.project_state.set_stage("generating_outline")
                return self._generate_outline()
            else:
                return f"信息还不够充足，请先补充：\n{status}"

        # 检查用户是否想确认信息充足
        if "信息充足" in user_input or "够了" in user_input or "可以了" in user_input:
            is_sufficient, status = self._check_info_status()
            if is_sufficient:
                return "好的，信息已充足。请回复'开始生成大纲'来进入下一阶段。"
            else:
                return f"信息还不够充足，缺失的部分：\n{status}\n\n请继续补充。"

        # 正常对话，收集信息
        response = self.chat(user_input)

        # 更新对话历史到状态
        self.project_state.add_conversation_message("user", user_input)
        self.project_state.add_conversation_message("assistant", response)

        # 尝试更新收集的信息（简单实现：让用户明确提供时更新）
        self._update_info_from_user_input(user_input)

        return response

    def _update_info_from_user_input(self, user_input: str) -> None:
        """从用户输入中提取信息并更新"""
        info = self.project_state.get_collected_info()

        # 简单的关键词匹配（可后续优化）
        keywords = {
            "genre": ["题材", "类型", "武侠", "科幻", "都市", "言情", "悬疑", "奇幻"],
            "theme": ["主题", "主线", "故事", "核心"],
            "main_characters": ["主角", "人物", "角色", "名字"],
            "world_setting": ["背景", "时代", "世界观", "设定"],
            "style_preference": ["风格", "字数", "篇幅", "轻松", "严肃"]
        }

        # 如果用户输入包含关键词，保存整句作为该字段的信息
        # 这是一个简化实现，后续可以用 LLM 来精确提取
        for field, kw_list in keywords.items():
            for kw in kw_list:
                if kw in user_input and field not in info:
                    info[field] = user_input
                    break

        self.project_state.update_collected_info(info)

    def _generate_outline(self) -> str:
        """生成大纲"""
        info = self.project_state.get_collected_info()

        user_prompt = GENERATE_OUTLINE_USER_PROMPT.format(
            genre=info.get("genre", "未指定"),
            theme=info.get("theme", "未指定"),
            main_characters=info.get("main_characters", "未指定"),
            world_setting=info.get("world_setting", "未指定"),
            style_preference=info.get("style_preference", "未指定")
        )

        response = self.llm_client.chat_with_system(
            GENERATE_OUTLINE_SYSTEM_PROMPT,
            [{"role": "user", "content": user_prompt}]
        )

        # 保存大纲
        self.project_state.set_outline({"raw": response})
        self.project_state.set_stage("outline_confirming")

        # 记录到对话历史
        self.project_state.add_conversation_message("user", user_prompt)
        self.project_state.add_conversation_message("assistant", response)

        return f"已生成大纲，请查看并提出修改意见，或回复'确认大纲'完成：\n\n{response}"

    def _handle_outline_confirming(self, user_input: str) -> str:
        """处理大纲确认阶段的用户输入"""

        if "确认大纲" in user_input or "确认" in user_input or "满意" in user_input:
            self.project_state.confirm_outline()
            self.project_state.set_stage("completed")
            return "大纲已确认完成！阶段1结束，可以继续阶段2添加卷纲和单元纲。"

        # 用户提出修改意见
        current_outline = self.project_state.get_outline()
        if current_outline:
            response = self.llm_client.chat_with_system(
                MODIFY_OUTLINE_SYSTEM_PROMPT.format(
                    current_outline=current_outline.get("raw", ""),
                    user_feedback=user_input
                ),
                [{"role": "user", "content": "请根据我的意见修改大纲。"}]
            )

            # 更新大纲
            self.project_state.set_outline({"raw": response})

            # 记录对话
            self.project_state.add_conversation_message("user", user_input)
            self.project_state.add_conversation_message("assistant", response)

            return f"已修改大纲，请继续提出意见或回复'确认大纲'完成：\n\n{response}"

        return "当前没有大纲，请重新生成。"