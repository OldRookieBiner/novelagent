# core/state.py
"""项目状态持久化，JSON 文件存储"""

import json
import os
from datetime import datetime
from typing import Dict, Any, Optional, List
from config import DATA_DIR


class ProjectState:
    """单个项目的状态管理"""

    def __init__(self, project_name: str):
        self.project_name = project_name
        self.file_path = os.path.join(DATA_DIR, f"{project_name}.json")
        self.data: Dict[str, Any] = {}
        self._load_or_create()

    def _load_or_create(self) -> None:
        """加载现有状态或创建新状态"""
        if os.path.exists(self.file_path):
            with open(self.file_path, 'r', encoding='utf-8') as f:
                self.data = json.load(f)
        else:
            self.data = {
                "project_name": self.project_name,
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
                "stage": "collecting_info",  # collecting_info, generating_outline, outline_confirming, completed
                "conversation_history": [],
                "collected_info": {},
                "outline": None,
                "outline_confirmed": False
            }
            self._save()

    def _save(self) -> None:
        """保存状态到文件"""
        self.data["updated_at"] = datetime.now().isoformat()
        os.makedirs(os.path.dirname(self.file_path), exist_ok=True)
        with open(self.file_path, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)

    def get_stage(self) -> str:
        """获取当前阶段"""
        return self.data.get("stage", "collecting_info")

    def set_stage(self, stage: str) -> None:
        """设置当前阶段"""
        self.data["stage"] = stage
        self._save()

    def get_conversation_history(self) -> List[Dict[str, str]]:
        """获取对话历史"""
        return self.data.get("conversation_history", [])

    def add_conversation_message(self, role: str, content: str) -> None:
        """添加对话消息"""
        self.data["conversation_history"].append({"role": role, "content": content})
        self._save()

    def get_collected_info(self) -> Dict[str, Any]:
        """获取收集的信息"""
        return self.data.get("collected_info", {})

    def update_collected_info(self, info: Dict[str, Any]) -> None:
        """更新收集的信息"""
        self.data["collected_info"] = info
        self._save()

    def get_outline(self) -> Optional[Dict[str, Any]]:
        """获取大纲"""
        return self.data.get("outline")

    def set_outline(self, outline: Dict[str, Any]) -> None:
        """设置大纲"""
        self.data["outline"] = outline
        self._save()

    def is_outline_confirmed(self) -> bool:
        """大纲是否已确认"""
        return self.data.get("outline_confirmed", False)

    def confirm_outline(self) -> None:
        """确认大纲"""
        self.data["outline_confirmed"] = True
        self._save()

    # === 卷纲管理 ===
    def get_volumes(self) -> List[Dict[str, Any]]:
        """获取所有卷纲"""
        return self.data.get("volumes", [])

    def set_volumes(self, volumes: List[Dict[str, Any]]) -> None:
        """设置所有卷纲"""
        self.data["volumes"] = volumes
        self._save()

    def get_current_volume_index(self) -> int:
        """获取当前卷索引（0-based）"""
        return self.data.get("current_progress", {}).get("current_volume", 0)

    def set_current_volume(self, index: int) -> None:
        """设置当前卷"""
        if "current_progress" not in self.data:
            self.data["current_progress"] = {}
        self.data["current_progress"]["current_volume"] = index
        self._save()

    def update_volume(self, volume_index: int, volume_data: Dict[str, Any]) -> None:
        """更新指定卷的数据"""
        if "volumes" not in self.data:
            self.data["volumes"] = []
        while len(self.data["volumes"]) <= volume_index:
            self.data["volumes"].append({})
        self.data["volumes"][volume_index] = volume_data
        self._save()

    # === 单元纲管理 ===
    def get_current_unit_index(self) -> int:
        """获取当前单元索引（0-based）"""
        return self.data.get("current_progress", {}).get("current_unit", 0)

    def set_current_unit(self, index: int) -> None:
        """设置当前单元"""
        if "current_progress" not in self.data:
            self.data["current_progress"] = {}
        self.data["current_progress"]["current_unit"] = index
        self._save()

    # === 章节管理 ===
    def get_current_chapter_index(self) -> int:
        """获取当前章节索引（0-based）"""
        return self.data.get("current_progress", {}).get("current_chapter", 0)

    def set_current_chapter(self, index: int) -> None:
        """设置当前章节"""
        if "current_progress" not in self.data:
            self.data["current_progress"] = {}
        self.data["current_progress"]["current_chapter"] = index
        self._save()

    def get_chapter(self, volume_index: int, unit_index: int, chapter_index: int) -> Optional[Dict[str, Any]]:
        """获取指定章节"""
        try:
            return self.data["volumes"][volume_index]["units"][unit_index]["chapters"][chapter_index]
        except (KeyError, IndexError, TypeError):
            return None

    def update_chapter(self, volume_index: int, unit_index: int, chapter_index: int, chapter_data: Dict[str, Any]) -> None:
        """更新指定章节"""
        if "volumes" not in self.data:
            self.data["volumes"] = []
        while len(self.data["volumes"]) <= volume_index:
            self.data["volumes"].append({"units": []})
        if "units" not in self.data["volumes"][volume_index]:
            self.data["volumes"][volume_index]["units"] = []
        while len(self.data["volumes"][volume_index]["units"]) <= unit_index:
            self.data["volumes"][volume_index]["units"].append({"chapters": []})
        if "chapters" not in self.data["volumes"][volume_index]["units"][unit_index]:
            self.data["volumes"][volume_index]["units"][unit_index]["chapters"] = []
        while len(self.data["volumes"][volume_index]["units"][unit_index]["chapters"]) <= chapter_index:
            self.data["volumes"][volume_index]["units"][unit_index]["chapters"].append({})
        self.data["volumes"][volume_index]["units"][unit_index]["chapters"][chapter_index] = chapter_data
        self._save()

    # === 进度统计 ===
    def get_total_words(self) -> int:
        """获取总字数"""
        return self.data.get("current_progress", {}).get("total_words", 0)

    def add_words(self, count: int) -> None:
        """增加字数"""
        if "current_progress" not in self.data:
            self.data["current_progress"] = {}
        self.data["current_progress"]["total_words"] = self.get_total_words() + count
        self._save()

    def get_progress_summary(self) -> Dict[str, Any]:
        """获取进度摘要"""
        return {
            "stage": self.get_stage(),
            "current_volume": self.get_current_volume_index() + 1,
            "current_unit": self.get_current_unit_index() + 1,
            "current_chapter": self.get_current_chapter_index() + 1,
            "total_words": self.get_total_words()
        }

    def get_summary(self) -> Dict[str, Any]:
        """获取项目摘要（用于列表显示）"""
        return {
            "project_name": self.project_name,
            "stage": self.get_stage(),
            "created_at": self.data.get("created_at"),
            "updated_at": self.data.get("updated_at"),
            "outline_confirmed": self.is_outline_confirmed()
        }


def list_projects() -> List[Dict[str, Any]]:
    """列出所有项目"""
    if not os.path.exists(DATA_DIR):
        return []

    projects = []
    for filename in os.listdir(DATA_DIR):
        if filename.endswith(".json"):
            project_name = filename[:-5]
            state = ProjectState(project_name)
            projects.append(state.get_summary())

    return projects


def project_exists(project_name: str) -> bool:
    """检查项目是否存在"""
    file_path = os.path.join(DATA_DIR, f"{project_name}.json")
    return os.path.exists(file_path)