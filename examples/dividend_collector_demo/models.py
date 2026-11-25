"""
SQLAlchemy ORM 模型 — current（当前记录）和 history（变更历史）。

设计原则：
- current 表持有每个业务唯一键的最新一条记录
- history 表记录每次变更的完整快照
- record_hash 由业务字段计算，用于判断记录是否变更
"""

import hashlib
import json

from sqlalchemy import Column, DateTime, Integer, String, Text
from sqlalchemy.sql import func

from pycollector.db.base import Base


def compute_record_hash(entity_code: str, record_id: str, value: str) -> str:
    """基于业务字段计算记录哈希值。

    哈希用于判断记录是否发生实质性变化，是实现幂等写入的关键。
    """
    raw = json.dumps(
        [entity_code, record_id, value],
        ensure_ascii=False,
        sort_keys=True,
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class DemoRecordCurrent(Base):
    """当前有效记录表。

    业务唯一键：(entity_code, record_id)
    """

    __tablename__ = "demo_record_current"

    id = Column(Integer, primary_key=True, autoincrement=True)
    entity_code = Column(String(50), nullable=False, index=True)
    entity_name = Column(String(200), nullable=False)
    record_id = Column(String(500), nullable=False)
    record_value = Column(Text, nullable=False)
    record_period = Column(String(50), nullable=True)
    category = Column(String(200), nullable=True)
    source_url = Column(Text, nullable=False)
    collected_at = Column(DateTime(timezone=True), nullable=False)
    record_hash = Column(String(64), nullable=False)

    __table_args__ = (
        # 业务唯一键：同一实体的同一 record_id 只保留一条
        {"sqlite_autoincrement": True},
    )

    def __repr__(self) -> str:
        return (
            f"DemoRecordCurrent(entity_code={self.entity_code!r}, "
            f"record_id={self.record_id!r})"
        )


class DemoRecordHistory(Base):
    """记录变更历史表。

    每次 current 表中的记录发生实质性变化时，旧版本被写入此表。
    """

    __tablename__ = "demo_record_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    entity_code = Column(String(50), nullable=False, index=True)
    entity_name = Column(String(200), nullable=False)
    record_id = Column(String(500), nullable=False)
    record_value = Column(Text, nullable=False)
    record_period = Column(String(50), nullable=True)
    category = Column(String(200), nullable=True)
    source_url = Column(Text, nullable=False)
    collected_at = Column(DateTime(timezone=True), nullable=False)
    record_hash = Column(String(64), nullable=False)
    superseded_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        {"sqlite_autoincrement": True},
    )

    def __repr__(self) -> str:
        return (
            f"DemoRecordHistory(entity_code={self.entity_code!r}, "
            f"record_id={self.record_id!r})"
        )