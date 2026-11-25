"""
采集器注册 — 将实体编码映射到采集器类。

这是 PyCollector 的 Registry + Factory 模式的核心组装点：
1. 定义每个实体的 EntityConfig
2. 将实体编码映射到 Collector 类
3. 构造 CollectorRegistry 并暴露 build_all()
"""

from pycollector.collector.context import CollectorConfig, EntityConfig
from pycollector.collector.registry import CollectorRegistry

from ..domain.enums import EntityCode
from ..settings import DemoSettings
from .demo_site_a import DemoSiteACollector
from .demo_site_b import DemoSiteBCollector


def get_entity_configs(settings: DemoSettings | None = None) -> dict[str, EntityConfig]:
    """构建所有演示实体的配置。

    实际项目中可以从 settings / .env / YAML / 数据库加载。
    """
    s = settings or DemoSettings()

    return {
        EntityCode.DEMO_SITE_A.value: EntityConfig(
            entity_code=EntityCode.DEMO_SITE_A,
            entity_name=s.demo_site_a_entity_name,
            source_url=s.demo_site_a_source_url,
            collector_config=CollectorConfig(request_timeout_seconds=10),
        ),
        EntityCode.DEMO_SITE_B.value: EntityConfig(
            entity_code=EntityCode.DEMO_SITE_B,
            entity_name=s.demo_site_b_entity_name,
            source_url=s.demo_site_b_source_url,
            collector_config=CollectorConfig(request_timeout_seconds=15),
        ),
    }


# 实体编码 → 采集器类 的映射表
_COLLECTOR_FACTORIES: dict[str, type] = {
    EntityCode.DEMO_SITE_A.value: DemoSiteACollector,
    EntityCode.DEMO_SITE_B.value: DemoSiteBCollector,
}


def build_registry(settings: DemoSettings | None = None) -> CollectorRegistry:
    """构建并返回 CollectorRegistry 实例。

    调用 registry.build_all() 即可获取所有已注册的采集器实例。
    """
    entity_configs = get_entity_configs(settings)
    return CollectorRegistry(
        entity_configs=entity_configs,
        factories=_COLLECTOR_FACTORIES,
    )