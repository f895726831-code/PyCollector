"""
API 路由 — 演示采集系统的 REST API 端点。

提供三个端点：
- GET  /entities       — 列出所有已注册实体
- POST /collect        — 触发一次采集
- GET  /records        — 查询采集记录
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from pycollector.db.session import get_db_session

from .collectors.registry import build_registry
from .domain.enums import EntityCode, JobStatus
from .repository import DemoRecordRepository
from .service import CollectionExecutionService

router = APIRouter()


@router.get("/entities")
def list_entities():
    """列出所有已注册的实体及其配置信息。"""
    registry = build_registry()
    return {
        code: {
            "entity_code": reg.entity.entity_code.value,
            "entity_name": reg.entity.entity_name,
            "source_url": reg.entity.source_url,
            "collector_class": reg.collector_factory.__name__,
        }
        for code, reg in registry.get_registrations().items()
    }


@router.post("/collect")
def trigger_collection(
    entity_code: str = Query(..., description="实体编码，如 DEMO_SITE_A"),
    db: Session = Depends(get_db_session),
):
    """触发一次实时采集。

    执行完整的 fetch → parse → write 链路，返回统计摘要。
    支持幂等：对同一实体重复采集，不会产生重复记录。
    """
    # 验证实体编码
    valid_codes = [e.value for e in EntityCode]
    if entity_code not in valid_codes:
        raise HTTPException(
            status_code=400,
            detail={
                "error_code": "INVALID_ENTITY_CODE",
                "error_message": (
                    f"未知的实体编码: {entity_code}。"
                    f"有效值: {', '.join(valid_codes)}"
                ),
            },
        )

    try:
        registry = build_registry()
        service = CollectionExecutionService(registry, db)
        result = service.execute(entity_code)
        db.commit()
        return result
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail={
                "error_code": "INTERNAL_ERROR",
                "error_message": str(exc),
            },
        ) from exc


@router.get("/records")
def list_records(
    entity_code: str = Query(..., description="实体编码"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db_session),
):
    """分页查询某实体的采集记录。"""
    repo = DemoRecordRepository(db)
    records = repo.list_by_entity(entity_code, limit=limit, offset=offset)
    total = repo.count_by_entity(entity_code)
    return {
        "entity_code": entity_code,
        "total": total,
        "limit": limit,
        "offset": offset,
        "records": [
            {
                "record_id": r.record_id,
                "record_value": r.record_value,
                "record_period": r.record_period,
                "category": r.category,
                "collected_at": r.collected_at.isoformat() if r.collected_at else None,
            }
            for r in records
        ],
    }