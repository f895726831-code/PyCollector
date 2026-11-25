"""
领域枚举 — 实体编码与数据领域定义。
"""

from enum import StrEnum


class EntityCode(StrEnum):
    """演示实体编码。"""
    DEMO_SITE_A = "DEMO_SITE_A"
    DEMO_SITE_B = "DEMO_SITE_B"


class DataDomain(StrEnum):
    """数据领域。"""
    DEMO = "DEMO"


class JobStatus(StrEnum):
    """采集任务状态。"""
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


class TriggerType(StrEnum):
    """触发类型。"""
    MANUAL = "MANUAL"
    SCHEDULED = "SCHEDULED"