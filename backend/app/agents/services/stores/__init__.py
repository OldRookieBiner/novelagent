"""知识库实体存储模块

按领域实体分组的读写 Store，返回 dict 而非 ORM 对象。
调用方通过 KnowledgeBaseService facade 的属性式访问使用 Store。
"""

from app.agents.services.stores.base import _BaseStore
from app.agents.services.stores.outline_store import OutlineStore
from app.agents.services.stores.world_setting_store import WorldSettingStore
from app.agents.services.stores.character_store import CharacterStore
from app.agents.services.stores.plot_store import PlotStore
from app.agents.services.stores.foreshadowing_store import ForeshadowingStore
from app.agents.services.stores.style_store import StyleStore
from app.agents.services.stores.timeline_store import TimelineStore
from app.agents.services.stores.volume_store import VolumeStore
from app.agents.services.stores.chapter_store import ChapterStore
from app.agents.services.stores.change_store import ChangeStore

__all__ = [
    "_BaseStore",
    "OutlineStore",
    "WorldSettingStore",
    "CharacterStore",
    "PlotStore",
    "ForeshadowingStore",
    "StyleStore",
    "TimelineStore",
    "VolumeStore",
    "ChapterStore",
    "ChangeStore",
]
