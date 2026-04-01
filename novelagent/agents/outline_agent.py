# agents/outline_agent.py
"""大纲 Agent 实现"""

import re
from typing import Dict, Any, Tuple, List
from agents.base import BaseAgent
from core.state import ProjectState
from prompts.outline import (
    COLLECT_INFO_SYSTEM_PROMPT,
    CHECK_INFO_PROMPT,
    GENERATE_OUTLINE_SYSTEM_PROMPT,
    GENERATE_OUTLINE_USER_PROMPT,
    MODIFY_OUTLINE_SYSTEM_PROMPT,
    GENERATE_VOLUMES_PROMPT,
    MODIFY_VOLUMES_PROMPT,
    GENERATE_UNITS_PROMPT,
    MODIFY_UNITS_PROMPT,
    GENERATE_CHAPTERS_PROMPT,
    MODIFY_CHAPTERS_PROMPT
)
from config import INFO_REQUIRED_FIELDS


class OutlineAgent(BaseAgent):
    """大纲 Agent：收集信息、生成大纲/卷纲/单元纲/章节纲"""

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

    def _check_info_status(self) -> Tuple[bool, str]:
        """检查信息是否充足"""
        info = self.project_state.get_collected_info()

        check_prompt = CHECK_INFO_PROMPT.format(
            collected_info=self._format_collected_info()
        )

        response = self.llm_client.chat_with_system(
            "你是一个信息分析助手，只做分析不做创作。",
            [{"role": "user", "content": check_prompt}]
        )

        if "信息已充足" in response:
            return True, "充足"

        return False, response

    # === 主处理方法 ===

    def process_user_input(self, user_input: str) -> str:
        """处理用户输入"""
        stage = self.project_state.get_stage()

        if stage == "collecting_info":
            return self._handle_collecting_info(user_input)
        elif stage == "generating_outline":
            return self._handle_generating_outline(user_input)
        elif stage == "outline_confirming":
            return self._handle_outline_confirming(user_input)
        elif stage == "volumes_generating":
            return self._generate_volumes()
        elif stage == "volumes_confirming":
            return self._handle_volumes_confirming(user_input)
        elif stage == "units_generating":
            vol_idx = self.project_state.get_current_volume_index()
            return self._generate_units_for_volume(vol_idx)
        elif stage == "units_confirming":
            return self._handle_units_confirming(user_input)
        elif stage == "chapters_outline_generating":
            vol_idx = self.project_state.get_current_volume_index()
            unit_idx = self.project_state.get_current_unit_index()
            return self._generate_chapters_for_unit(vol_idx, unit_idx)
        elif stage == "chapters_outline_confirming":
            return self._handle_chapters_outline_confirming(user_input)
        elif stage == "chapter_writing":
            return "大纲阶段已完成，正在进行章节写作。请使用'继续'命令。"
        elif stage == "completed":
            return "小说创作已完成！"
        else:
            return f"当前阶段：{stage}"

    # === 信息收集阶段 ===

    def _handle_collecting_info(self, user_input: str) -> str:
        """处理信息收集阶段的用户输入"""

        if "开始生成大纲" in user_input or "可以开始" in user_input:
            is_sufficient, status = self._check_info_status()
            if is_sufficient:
                self.project_state.set_stage("generating_outline")
                return self._generate_outline()
            else:
                return f"信息还不够充足，请先补充：\n{status}"

        if "信息充足" in user_input or "够了" in user_input or "可以了" in user_input:
            is_sufficient, status = self._check_info_status()
            if is_sufficient:
                return "好的，信息已充足。请回复'开始生成大纲'来进入下一阶段。"
            else:
                return f"信息还不够充足，缺失的部分：\n{status}\n\n请继续补充。"

        response = self.chat(user_input)

        self.project_state.add_conversation_message("user", user_input)
        self.project_state.add_conversation_message("assistant", response)

        self._update_info_from_user_input(user_input)

        return response

    def _update_info_from_user_input(self, user_input: str) -> None:
        """从用户输入中提取信息并更新"""
        info = self.project_state.get_collected_info()

        keywords = {
            "genre": ["题材", "类型", "武侠", "科幻", "都市", "言情", "悬疑", "奇幻"],
            "theme": ["主题", "主线", "故事", "核心"],
            "main_characters": ["主角", "人物", "角色", "名字"],
            "world_setting": ["背景", "时代", "世界观", "设定"],
            "style_preference": ["风格", "字数", "篇幅", "轻松", "严肃"]
        }

        for field, kw_list in keywords.items():
            for kw in kw_list:
                if kw in user_input and field not in info:
                    info[field] = user_input
                    break

        self.project_state.update_collected_info(info)

    # === 大纲阶段 ===

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

        self.project_state.set_outline({"raw": response})
        self.project_state.set_stage("outline_confirming")

        self.project_state.add_conversation_message("user", user_prompt)
        self.project_state.add_conversation_message("assistant", response)

        return f"已生成大纲，请查看并提出修改意见，或回复'确认大纲'继续：\n\n{response}"

    def _handle_outline_confirming(self, user_input: str) -> str:
        """处理大纲确认阶段的用户输入"""

        if "确认大纲" in user_input or "确认" in user_input or "满意" in user_input:
            self.project_state.confirm_outline()
            self.project_state.set_stage("volumes_generating")
            return "大纲已确认！开始生成卷纲...\n\n" + self._generate_volumes()

        current_outline = self.project_state.get_outline()
        if current_outline:
            response = self.llm_client.chat_with_system(
                MODIFY_OUTLINE_SYSTEM_PROMPT.format(
                    current_outline=current_outline.get("raw", ""),
                    user_feedback=user_input
                ),
                [{"role": "user", "content": "请根据我的意见修改大纲。"}]
            )

            self.project_state.set_outline({"raw": response})
            self.project_state.add_conversation_message("user", user_input)
            self.project_state.add_conversation_message("assistant", response)

            return f"已修改大纲，请继续提出意见或回复'确认大纲'继续：\n\n{response}"

        return "当前没有大纲，请重新生成。"

    # === 卷纲阶段 ===

    def _generate_volumes(self) -> str:
        """生成所有卷纲"""
        outline = self.project_state.get_outline()
        if not outline:
            return "请先生成大纲。"

        prompt = GENERATE_VOLUMES_PROMPT.format(
            outline=outline.get("raw", "")
        )

        response = self.llm_client.chat_with_system(
            "你是一个专业的小说大纲策划师。",
            [{"role": "user", "content": prompt}]
        )

        volumes = self._parse_volumes(response)
        self.project_state.set_volumes(volumes)
        self.project_state.set_stage("volumes_confirming")

        return f"已生成 {len(volumes)} 卷纲，请查看并提出修改意见，或回复'确认卷纲'继续：\n\n{response}"

    def _parse_volumes(self, text: str) -> List[Dict[str, Any]]:
        """解析卷纲文本为结构化数据"""
        volumes = []
        pattern = r'第(\d+)卷[：:]\s*(.+?)(?=第\d+卷|$)'
        matches = re.findall(pattern, text, re.DOTALL)

        for num, content in matches:
            volumes.append({
                "volume_id": int(num),
                "raw": f"第{num}卷：{content.strip()}",
                "confirmed": False,
                "units": []
            })

        if not volumes:
            volumes.append({"volume_id": 1, "raw": text, "confirmed": False, "units": []})

        return volumes

    def _handle_volumes_confirming(self, user_input: str) -> str:
        """处理卷纲确认"""
        if "确认卷纲" in user_input or "确认" in user_input:
            volumes = self.project_state.get_volumes()
            for v in volumes:
                v["confirmed"] = True
            self.project_state.set_volumes(volumes)

            self.project_state.set_current_volume(0)
            self.project_state.set_stage("units_generating")
            return "卷纲已确认！开始生成第一卷的单元纲...\n\n" + self._generate_units_for_volume(0)

        volumes = self.project_state.get_volumes()
        if volumes:
            response = self.llm_client.chat_with_system(
                MODIFY_VOLUMES_PROMPT.format(
                    current_volumes="\n".join([v.get("raw", "") for v in volumes]),
                    user_feedback=user_input
                ),
                [{"role": "user", "content": "请根据我的意见修改卷纲。"}]
            )

            new_volumes = self._parse_volumes(response)
            self.project_state.set_volumes(new_volumes)

            return f"已修改卷纲，请继续提出意见或回复'确认卷纲'继续：\n\n{response}"

        return "当前没有卷纲，请重新生成。"

    # === 单元纲阶段 ===

    def _generate_units_for_volume(self, volume_index: int) -> str:
        """为指定卷生成单元纲"""
        volumes = self.project_state.get_volumes()
        if volume_index >= len(volumes):
            return "卷索引超出范围"

        volume = volumes[volume_index]
        outline = self.project_state.get_outline()

        prompt = GENERATE_UNITS_PROMPT.format(
            volume_outline=volume.get("raw", ""),
            novel_outline=outline.get("raw", "") if outline else ""
        )

        response = self.llm_client.chat_with_system(
            "你是一个小说大纲策划师。",
            [{"role": "user", "content": prompt}]
        )

        units = self._parse_units(response)
        volume["units"] = units
        volumes[volume_index] = volume
        self.project_state.set_volumes(volumes)
        self.project_state.set_stage("units_confirming")

        return f"已生成第{volume_index + 1}卷的 {len(units)} 个单元纲，请查看并提出修改意见，或回复'确认单元纲'继续：\n\n{response}"

    def _parse_units(self, text: str) -> List[Dict[str, Any]]:
        """解析单元纲文本为结构化数据"""
        units = []
        pattern = r'第(\d+)单元[：:]\s*(.+?)(?=第\d+单元|$)'
        matches = re.findall(pattern, text, re.DOTALL)

        for num, content in matches:
            units.append({
                "unit_id": int(num),
                "raw": f"第{num}单元：{content.strip()}",
                "confirmed": False,
                "chapters": []
            })

        if not units:
            units.append({"unit_id": 1, "raw": text, "confirmed": False, "chapters": []})

        return units

    def _handle_units_confirming(self, user_input: str) -> str:
        """处理单元纲确认"""
        if "确认单元纲" in user_input or "确认" in user_input:
            vol_idx = self.project_state.get_current_volume_index()
            volumes = self.project_state.get_volumes()
            if vol_idx < len(volumes) and volumes[vol_idx].get("units"):
                for u in volumes[vol_idx]["units"]:
                    u["confirmed"] = True
                self.project_state.set_volumes(volumes)

            self.project_state.set_current_unit(0)
            self.project_state.set_stage("chapters_outline_generating")
            return "单元纲已确认！开始生成第一个单元的章节纲...\n\n" + self._generate_chapters_for_unit(vol_idx, 0)

        vol_idx = self.project_state.get_current_volume_index()
        volumes = self.project_state.get_volumes()
        if vol_idx < len(volumes) and volumes[vol_idx].get("units"):
            units = volumes[vol_idx]["units"]
            response = self.llm_client.chat_with_system(
                MODIFY_UNITS_PROMPT.format(
                    current_units="\n".join([u.get("raw", "") for u in units]),
                    volume_outline=volumes[vol_idx].get("raw", ""),
                    user_feedback=user_input
                ),
                [{"role": "user", "content": "请根据我的意见修改单元纲。"}]
            )

            new_units = self._parse_units(response)
            volumes[vol_idx]["units"] = new_units
            self.project_state.set_volumes(volumes)

            return f"已修改单元纲，请继续提出意见或回复'确认单元纲'继续：\n\n{response}"

        return "当前没有单元纲，请重新生成。"

    # === 章节纲阶段 ===

    def _generate_chapters_for_unit(self, volume_index: int, unit_index: int) -> str:
        """为指定单元生成章节纲"""
        volumes = self.project_state.get_volumes()
        if volume_index >= len(volumes):
            return "卷索引超出范围"

        volume = volumes[volume_index]
        if unit_index >= len(volume.get("units", [])):
            return "单元索引超出范围"

        unit = volume["units"][unit_index]

        prompt = GENERATE_CHAPTERS_PROMPT.format(
            unit_outline=unit.get("raw", ""),
            volume_outline=volume.get("raw", "")
        )

        response = self.llm_client.chat_with_system(
            "你是一个小说章节策划师。",
            [{"role": "user", "content": prompt}]
        )

        chapters = self._parse_chapters(response)
        unit["chapters"] = chapters
        volumes[volume_index]["units"][unit_index] = unit
        self.project_state.set_volumes(volumes)
        self.project_state.set_stage("chapters_outline_confirming")

        return f"已生成第{unit_index + 1}单元的 {len(chapters)} 个章节纲，请查看并提出修改意见，或回复'确认章节纲'开始写作：\n\n{response}"

    def _parse_chapters(self, text: str) -> List[Dict[str, Any]]:
        """解析章节纲文本为结构化数据"""
        chapters = []
        pattern = r'第(\d+)章[：:]\s*(.+?)(?=第\d+章|$)'
        matches = re.findall(pattern, text, re.DOTALL)

        for num, content in matches:
            chapters.append({
                "chapter_id": int(num),
                "raw": f"第{num}章：{content.strip()}",
                "title": self._extract_title(content),
                "confirmed": False,
                "content": None,
                "review_passed": False
            })

        if not chapters:
            chapters.append({"chapter_id": 1, "raw": text, "title": "第一章", "confirmed": False, "content": None, "review_passed": False})

        return chapters

    def _extract_title(self, content: str) -> str:
        """从章节内容中提取标题"""
        match = re.search(r'章节名[：:]\s*(.+)', content)
        if match:
            return match.group(1).strip()
        # 尝试提取第一行作为标题
        first_line = content.strip().split('\n')[0]
        if first_line and len(first_line) < 20:
            return first_line
        return "未命名章节"

    def _handle_chapters_outline_confirming(self, user_input: str) -> str:
        """处理章节纲确认"""
        if "确认章节纲" in user_input or "确认" in user_input:
            vol_idx = self.project_state.get_current_volume_index()
            unit_idx = self.project_state.get_current_unit_index()
            volumes = self.project_state.get_volumes()

            if vol_idx < len(volumes) and unit_idx < len(volumes[vol_idx].get("units", [])):
                for c in volumes[vol_idx]["units"][unit_idx].get("chapters", []):
                    c["confirmed"] = True
                self.project_state.set_volumes(volumes)

            self.project_state.set_current_chapter(0)
            self.project_state.set_stage("chapter_writing")
            return "章节纲已确认！准备开始写作，请回复'开始写作'生成第一章正文。"

        vol_idx = self.project_state.get_current_volume_index()
        unit_idx = self.project_state.get_current_unit_index()
        volumes = self.project_state.get_volumes()

        if vol_idx < len(volumes) and unit_idx < len(volumes[vol_idx].get("units", [])):
            chapters = volumes[vol_idx]["units"][unit_idx].get("chapters", [])
            response = self.llm_client.chat_with_system(
                MODIFY_CHAPTERS_PROMPT.format(
                    current_chapters="\n".join([c.get("raw", "") for c in chapters]),
                    unit_outline=volumes[vol_idx]["units"][unit_idx].get("raw", ""),
                    user_feedback=user_input
                ),
                [{"role": "user", "content": "请根据我的意见修改章节纲。"}]
            )

            new_chapters = self._parse_chapters(response)
            volumes[vol_idx]["units"][unit_idx]["chapters"] = new_chapters
            self.project_state.set_volumes(volumes)

            return f"已修改章节纲，请继续提出意见或回复'确认章节纲'开始写作：\n\n{response}"

        return "当前没有章节纲，请重新生成。"