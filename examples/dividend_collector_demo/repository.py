"""
仓储实现 — 基于 BaseRepository 扩展的 upsert + history 追踪。

核心逻辑：
1. 按业务唯一键 (entity_code, record_id) 查找 current 记录
2. 比较 record_hash：相同 → unchanged / 不同 → 迁移到 history + 更新 current
3. 不存在 → 插入 current
"""

from datetime import datetime, timezone

from sqlalchemy import and_
from sqlalchemy.orm import Session

from pycollector.repository.base import BaseRepository

from .models import DemoRecordCurrent, DemoRecordHistory, compute_record_hash


class DemoRecordRepository(BaseRepository[DemoRecordCurrent]):
    """演示记录仓储，支持 upsert 与变更历史追踪。"""

    def __init__(self, session: Session) -> None:
        super().__init__(session, DemoRecordCurrent)

    def find_by_entity_and_record(
        self, entity_code: str, record_id: str
    ) -> DemoRecordCurrent | None:
        """按业务唯一键查找当前记录。"""
        return (
            self._session.query(DemoRecordCurrent)
            .filter(
                and_(
                    DemoRecordCurrent.entity_code == entity_code,
                    DemoRecordCurrent.record_id == record_id,
                )
            )
            .first()
        )

    def upsert(self, record: DemoRecordCurrent) -> str:
        """插入或更新一条记录。

        Returns:
            "inserted" / "updated" / "unchanged"
        """
        existing = self.find_by_entity_and_record(
            record.entity_code, record.record_id
        )

        if existing is None:
            # 新记录 — 直接插入
            self._session.add(record)
            self._session.flush()
            return "inserted"

        if existing.record_hash == record.record_hash:
            # 哈希未变 — 记录未变化
            return "unchanged"

        # 哈希变化 — 将旧记录移至 history，更新 current
        self._archive_to_history(existing)
        # 更新 current 的字段
        existing.entity_name = record.entity_name
        existing.record_value = record.record_value
        existing.record_period = record.record_period
        existing.category = record.category
        existing.source_url = record.source_url
        existing.collected_at = record.collected_at
        existing.record_hash = record.record_hash
        self._session.flush()
        return "updated"

    def _archive_to_history(self, current: DemoRecordCurrent) -> None:
        """将一条 current 记录归档到 history 表。"""
        history = DemoRecordHistory(
            entity_code=current.entity_code,
            entity_name=current.entity_name,
            record_id=current.record_id,
            record_value=current.record_value,
            record_period=current.record_period,
            category=current.category,
            source_url=current.source_url,
            collected_at=current.collected_at,
            record_hash=current.record_hash,
            superseded_at=datetime.now(timezone.utc),
        )
        self._session.add(history)

    def count_by_entity(self, entity_code: str) -> int:
        """统计某实体的当前记录数。"""
        return (
            self._session.query(DemoRecordCurrent)
            .filter(DemoRecordCurrent.entity_code == entity_code)
            .count()
        )

    def list_by_entity(
        self, entity_code: str, limit: int = 100, offset: int = 0
    ) -> list[DemoRecordCurrent]:
        """分页查询某实体的当前记录。"""
        return (
            self._session.query(DemoRecordCurrent)
            .filter(DemoRecordCurrent.entity_code == entity_code)
            .order_by(DemoRecordCurrent.record_id)
            .limit(limit)
            .offset(offset)
            .all()
        )