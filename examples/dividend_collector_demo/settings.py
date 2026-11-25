"""
演示应用配置 — 继承 BaseCollectorSettings 添加实体专属字段。
"""

from pydantic import Field
from pycollector.core.settings import BaseCollectorSettings


class DemoSettings(BaseCollectorSettings):
    """演示应用配置。

    在 BaseCollectorSettings 的基础上增加了两个演示实体的专属配置。
    所有字段均可通过 .env 文件或环境变量覆盖。
    """

    model_config = BaseCollectorSettings.model_config

    # 演示实体 A（example.com — HTML 静态页）
    demo_site_a_entity_code: str = Field(
        default="DEMO_SITE_A",
        alias="DEMO_SITE_A_ENTITY_CODE",
    )
    demo_site_a_entity_name: str = Field(
        default="Demo Site A (HTML 静态页)",
        alias="DEMO_SITE_A_ENTITY_NAME",
    )
    demo_site_a_source_url: str = Field(
        default="https://example.com",
        alias="DEMO_SITE_A_SOURCE_URL",
    )
    demo_site_a_scheduler_enabled: bool = Field(
        default=False,
        alias="DEMO_SITE_A_SCHEDULER_ENABLED",
    )

    # 演示实体 B（jsonplaceholder — API JSON）
    demo_site_b_entity_code: str = Field(
        default="DEMO_SITE_B",
        alias="DEMO_SITE_B_ENTITY_CODE",
    )
    demo_site_b_entity_name: str = Field(
        default="Demo Site B (API JSON)",
        alias="DEMO_SITE_B_ENTITY_NAME",
    )
    demo_site_b_source_url: str = Field(
        default="https://jsonplaceholder.typicode.com/posts",
        alias="DEMO_SITE_B_SOURCE_URL",
    )
    demo_site_b_scheduler_enabled: bool = Field(
        default=False,
        alias="DEMO_SITE_B_SCHEDULER_ENABLED",
    )