"""
采集执行服务 — 协调 fetch → parse → write 全链路。

这是应用层的核心编排逻辑：
1. 从 Registry 获取采集器
2. 执行 fetch() 获取原始数据
3. 执行 parse() 解析为结构化记录
4. 转换记录为 ORM 模型
5. 逐条 upsert（自动处理 insert/update/unchanged + history）
6. 返回统计摘要
"""

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from pycollector.collector.registry import CollectorRegistry

from .domain.enums import JobStatus
from .models import DemoRecordCurrent, compute_record_hash
from .repository import DemoRecordRepository


class CollectionExecutionService:
    """采集执行服务。

    Parameters
    ----------
    registry:
        CollectorRegistry 实例。
    session:
        当前数据库会话。
    """

    def __init__(self, registry: CollectorRegistry, session: Session) -> None:
        self._registry = registry
        self._repo = DemoRecordRepository(session)

    def execute(self, entity_code: str) -> dict:
        """对单个实体执行一次完整的采集流程。

        Returns:
            dict: 包含 status, entity_code, 各类计数和记录的统计摘要。
        """
        collector = self._registry.build_one(entity_code)
        collected_at = datetime.now(timezone.utc)

        # Step 1: 获取原始数据
        fetch_result = collector.fetch()

        # Step 2: 解析为结构化记录
        parse_result = collector.parse(fetch_result.raw_content)

        # Step 3: 转换 + 写入
        stats = {"inserted": 0, "updated": 0, "unchanged": 0}
        records_out: list[dict] = []

        for record_dict in parse_result.records:
            # 计算业务哈希
            record_hash = compute_record_hash(
                entity_code=str(record_dict.get("entity_code", entity_code)),
                record_id=str(record_dict.get("record_id", "")),
                value=str(record_dict.get("record_value", "")),
            )

            # 构造 ORM 模型
            model = DemoRecordCurrent(
                entity_code=str(record_dict.get("entity_code", entity_code)),
                entity_name=str(record_dict.get("entity_name", "")),
                record_id=str(record_dict.get("record_id", "")),
                record_value=str(record_dict.get("record_value", "")),
                record_period=str(record_dict.get("record_period", "")) or None,
                category=str(record_dict.get("category", "")) or None,
                source_url=str(
                    record_dict.get("source_url", fetch_result.source_url)
                ),
                collected_at=record_dict.get("collected_at", collected_at),
                record_hash=record_hash,
            )

            # Upsert（insert / update / unchanged）
            result = self._repo.upsert(model)
            stats[result] += 1

            records_out.append(
                {
                    "record_id": model.record_id,
                    "record_value": model.record_value[:80],
                    "result": result,
                }
            )

        return {
            "status": JobStatus.SUCCESS.value,
            "entity_code": entity_code,
            "entity_name": collector.entity_name,
            "source_url": fetch_result.source_url,
            "http_status": fetch_result.http_status,
            "collected_at": collected_at.isoformat(),
            "parsed_count": len(parse_result.records),
            "inserted_count": stats["inserted"],
            "updated_count": stats["updated"],
            "unchanged_count": stats["unchanged"],
            "warning_count": len(parse_result.warnings),
            "skipped_count": len(parse_result.skipped_items),
            "warnings": [
                {"code": w.get("reason_code"), "message": w.get("message")}
                for w in parse_result.warnings
            ],
            "skipped_items": [
                {"code": s.get("reason_code"), "message": s.get("message")}
                for s in parse_result.skipped_items
            ],
            "records": records_out,
        }