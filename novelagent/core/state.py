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