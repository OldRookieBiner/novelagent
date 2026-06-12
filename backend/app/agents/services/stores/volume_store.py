"""卷存储

管理 Volume, CrossVolumeForeshadowing, CrossVolumeSubplot, CharacterChangeLog。
"""

import logging
from typing import Optional

from app.agents.services.stores.base import _BaseStore
from app.models.volume import Volume
from app.models.cross_volume import (
    CrossVolumeForeshadowing,
    CrossVolumeSubplot,
    CharacterChangeLog,
)

logger = logging.getLogger(__name__)


class VolumeStore(_BaseStore):
    """卷及跨卷追踪读写"""

    # ========== Volume ==========

    def list_volumes(self) -> list[dict]:
        with self.session(readonly=True) as db:
            objs = db.query(Volume).filter(
                Volume.project_id == self.project_id
            ).order_by(Volume.volume_number).all()
            return self._to_dict_list(objs)

    def get_volume(self, volume_number: int) -> Optional[dict]:
        with self.session(readonly=True) as db:
            obj = db.query(Volume).filter(
                Volume.project_id == self.project_id,
                Volume.volume_number == volume_number,
            ).first()
            return self._to_dict(obj)

    def get_current_volume(self) -> Optional[dict]:
        """获取当前（最新）卷"""
        with self.session(readonly=True) as db:
            obj = db.query(Volume).filter(
                Volume.project_id == self.project_id
            ).order_by(Volume.volume_number.desc()).first()
            return self._to_dict(obj)

    def create_volume(self, data: dict) -> dict:
        with self.session() as db:
            obj = Volume(project_id=self.project_id, **data)
            db.add(obj)
            db.flush()
            db.refresh(obj)
            return self._to_dict(obj)

    def update_volume(self, volume_id: int, data: dict) -> dict:
        with self.session() as db:
            obj = db.query(Volume).filter(
                Volume.id == volume_id,
                Volume.project_id == self.project_id,
            ).first()
            if not obj:
                raise ValueError(f"Volume {volume_id} not found")
            for key, value in data.items():
                setattr(obj, key, value)
            db.flush()
            db.refresh(obj)
            return self._to_dict(obj)

    # ========== 跨卷伏笔 ==========

    def list_cross_volume_foreshadowings(self, status: Optional[str] = None) -> list[dict]:
        with self.session(readonly=True) as db:
            query = db.query(CrossVolumeForeshadowing).filter(
                CrossVolumeForeshadowing.project_id == self.project_id
            )
            if status:
                query = query.filter(CrossVolumeForeshadowing.status == status)
            return self._to_dict_list(query.all())

    def create_cross_volume_foreshadowing(self, data: dict) -> dict:
        with self.session() as db:
            obj = CrossVolumeForeshadowing(project_id=self.project_id, **data)
            db.add(obj)
            db.flush()
            db.refresh(obj)
            return self._to_dict(obj)

    def update_cross_volume_foreshadowing(self, cvf_id: int, data: dict) -> dict:
        with self.session() as db:
            obj = db.query(CrossVolumeForeshadowing).filter(
                CrossVolumeForeshadowing.id == cvf_id,
                CrossVolumeForeshadowing.project_id == self.project_id,
            ).first()
            if not obj:
                raise ValueError(f"CrossVolumeForeshadowing {cvf_id} not found")
            for key, value in data.items():
                setattr(obj, key, value)
            db.flush()
            db.refresh(obj)
            return self._to_dict(obj)

    # ========== 跨卷支线 ==========

    def list_cross_volume_subplots(self, status: Optional[str] = None) -> list[dict]:
        with self.session(readonly=True) as db:
            query = db.query(CrossVolumeSubplot).filter(
                CrossVolumeSubplot.project_id == self.project_id
            )
            if status:
                query = query.filter(CrossVolumeSubplot.status == status)
            return self._to_dict_list(query.all())

    def create_cross_volume_subplot(self, data: dict) -> dict:
        with self.session() as db:
            obj = CrossVolumeSubplot(project_id=self.project_id, **data)
            db.add(obj)
            db.flush()
            db.refresh(obj)
            return self._to_dict(obj)

    def update_cross_volume_subplot(self, cvs_id: int, data: dict) -> dict:
        with self.session() as db:
            obj = db.query(CrossVolumeSubplot).filter(
                CrossVolumeSubplot.id == cvs_id,
                CrossVolumeSubplot.project_id == self.project_id,
            ).first()
            if not obj:
                raise ValueError(f"CrossVolumeSubplot {cvs_id} not found")
            for key, value in data.items():
                setattr(obj, key, value)
            db.flush()
            db.refresh(obj)
            return self._to_dict(obj)

    # ========== 角色变化日志 ==========

    def list_character_change_logs(self, volume_number: Optional[int] = None) -> list[dict]:
        with self.session(readonly=True) as db:
            query = db.query(CharacterChangeLog).filter(
                CharacterChangeLog.project_id == self.project_id
            )
            if volume_number is not None:
                query = query.filter(CharacterChangeLog.volume_number == volume_number)
            objs = query.order_by(
                CharacterChangeLog.volume_number,
                CharacterChangeLog.character_id,
            ).all()
            return self._to_dict_list(objs)

    def create_character_change_log(self, data: dict) -> dict:
        with self.session() as db:
            obj = CharacterChangeLog(project_id=self.project_id, **data)
            db.add(obj)
            db.flush()
            db.refresh(obj)
            return self._to_dict(obj)

    # ========== 内部方法 ==========

    def _read_volume_for_index_with_session(self, db, volume_number: int) -> dict:
        """单次 session 内批量读取指定卷数据，供 KB 编排方法使用"""
        volume = db.query(Volume).filter(
            Volume.project_id == self.project_id,
            Volume.volume_number == volume_number,
        ).first()

        cross_volume_foreshadowings = db.query(CrossVolumeForeshadowing).filter(
            CrossVolumeForeshadowing.project_id == self.project_id
        ).all()

        cross_volume_subplots = db.query(CrossVolumeSubplot).filter(
            CrossVolumeSubplot.project_id == self.project_id
        ).all()

        change_logs = db.query(CharacterChangeLog).filter(
            CharacterChangeLog.project_id == self.project_id,
            CharacterChangeLog.volume_number == volume_number,
        ).order_by(CharacterChangeLog.character_id).all()

        return {
            "volume": self._to_dict(volume),
            "cross_volume_foreshadowings": self._to_dict_list(cross_volume_foreshadowings),
            "cross_volume_subplots": self._to_dict_list(cross_volume_subplots),
            "character_change_logs": self._to_dict_list(change_logs),
        }
