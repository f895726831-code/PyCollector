# PyCollector 扩展指南

本文档覆盖 PyCollector 框架的全部扩展点，说明如何在不修改框架核心代码的前提下适配你的业务需求。

---

## 目录

1. [新增数据领域](#1-新增数据领域)
2. [新增实体采集器](#2-新增实体采集器)
3. [自定义错误码](#3-自定义错误码)
4. [自定义配置](#4-自定义配置)
5. [自定义调度策略](#5-自定义调度策略)
6. [自定义仓储](#6-自定义仓储)
7. [数据载体类型参考](#7-数据载体类型参考)

---

## 1. 新增数据领域

PyCollector 默认提供了一个通用的采集器协议。如果你需要采集与默认示例不同类型的数据（例如从"分红数据"扩展到"结算利率"），只需要 4 步：

### 1.1 定义 Protocol

在 `collector/protocol.py` 中，`Collector` Protocol 定义了最小接口：

```python
class Collector(Protocol):
    def fetch(self) -> FetchResult: ...
    def parse(self, raw_content: str) -> ParseResult: ...
```

你可以直接使用这个通用 Protocol，也可以在你的应用中定义更具体的子 Protocol：

```python
# myapp/collector/protocol.py
from pycollector.collector.protocol import Collector, FetchResult, ParseResult
from typing import Protocol

class MyDomainCollector(Collector, Protocol):
    """我的领域专属采集器协议。"""

    def fetch(self) -> FetchResult: ...

    def parse(self, raw_content: str) -> ParseResult: ...

    # 可选的领域专属方法
    def detect_available_periods(self) -> set[str]:
        """检测当前可用的时间周期。"""
        ...
```

### 1.2 继承 BaseCollector

`BaseCollector` 提供了所有 HTTP 工具和错误处理基础设施。你通常只需要覆盖 `fetch()` 和 `parse()`：

```python
# myapp/collector/my_collector.py
from pycollector.collector.base import BaseCollector

class MyCollector(BaseCollector):
    def fetch(self):
        fetched_at = self._utc_now()
        response = self._http_get(self.source_url)
        return self._build_fetch_result(response, fetched_at)

    def parse(self, raw_content: str) -> ParseResult:
        # 你的解析逻辑
        records = [self._build_standard_record(...)]
        return ParseResult(records=records)
```

### 1.3 创建 CollectorRegistry

```python
# myapp/collector/registry.py
from pycollector.collector.registry import CollectorRegistry
from pycollector.collector.context import EntityConfig

entity_configs = {
    "ENTITY_A": EntityConfig(
        entity_code=MyEntityCode.ENTITY_A,
        entity_name="实体 A",
        source_url="https://example.com/data",
    ),
}

factories = {
    "ENTITY_A": MyCollectorA,
}

registry = CollectorRegistry(entity_configs, factories)
collectors = registry.build_all()
```

### 1.4 添加 API 路由

```python
# myapp/routes.py
from fastapi import APIRouter
from .collector.registry import registry

router = APIRouter()

@router.post("/collect/{entity_code}")
def collect(entity_code: str):
    collector = registry.build_one(entity_code)
    fetch_result = collector.fetch()
    parse_result = collector.parse(fetch_result.raw_content)
    return {"record_count": len(parse_result.records)}
```

### 1.5 完整示例

参考 `examples/dividend_collector_demo/`，这是一个完整的、可运行的端到端示例。

---

## 2. 新增实体采集器

新增一个具体的实体采集器（例如接入一个新的数据源）只需 3 步：

### 2.1 创建 Collector 类

从模板开始（`pycollector/collector/templates/new_collector.py`）：

```python
from pycollector.collector.base import BaseCollector
from pycollector.collector.context import EntityConfig

class NewDataSourceCollector(BaseCollector):
    def __init__(self, entity_config: EntityConfig) -> None:
        super().__init__(entity_config)

    def fetch(self):
        # 你的 HTTP 请求逻辑
        ...

    def parse(self, raw_content: str):
        # 你的解析逻辑
        ...
```

### 2.2 注册到 Registry

```python
# registry.py
from .new_data_source import NewDataSourceCollector

_COLLECTOR_FACTORIES["NEW_SOURCE"] = NewDataSourceCollector

entity_configs["NEW_SOURCE"] = EntityConfig(
    entity_code=MyEntityCode.NEW_SOURCE,
    entity_name="新数据源",
    source_url="https://new-source.example.com/data",
)
```

### 2.3 配置环境变量

在 `.env` 或环境变量中添加新实体的配置：

```bash
NEW_SOURCE_ENTITY_CODE=NEW_SOURCE
NEW_SOURCE_ENTITY_NAME=新数据源
NEW_SOURCE_SOURCE_URL=https://new-source.example.com/data
NEW_SOURCE_SCHEDULER_ENABLED=false
```

### 2.4 编写测试

为每个采集器编写单元测试，覆盖以下场景：

- 正常解析：有效输入产生预期记录
- 空输入：无数据时抛出 `PARSE_RESULT_EMPTY`
- 跳过规则：应跳过的数据不被纳入记录
- 异常输入：格式错误的数据产生 warning 而非崩溃

参考 `examples/dividend_collector_demo/` 中的采集器实现了解测试的结构。

---

## 3. 自定义错误码

`pycollector.domain.enums.ErrorCode` 提供了通用错误码。你可以通过继承来添加领域专属错误码：

```python
# myapp/domain/enums.py
from pycollector.domain.enums import ErrorCode

class MyErrorCode(ErrorCode):
    """应用专属错误码。"""

    # 业务错误
    RATE_OUT_OF_RANGE = "RATE_OUT_OF_RANGE"
    DUPLICATE_ENTITY = "DUPLICATE_ENTITY"

    # 数据错误
    PDF_CORRUPTED = "PDF_CORRUPTED"
    JSON_SCHEMA_MISMATCH = "JSON_SCHEMA_MISMATCH"
```

使用自定义错误码：

```python
from pycollector.core.errors import AppError
from myapp.domain.enums import MyErrorCode

raise AppError(
    error_code=MyErrorCode.RATE_OUT_OF_RANGE,
    error_message="结算利率超出合理范围 (0%-10%)",
    status_code=422,
    detail={"value": 15.5, "entity_code": "SOURCE_A"},
)
```

---

## 4. 自定义配置

### 4.1 继承 BaseCollectorSettings

```python
# myapp/settings.py
from pydantic import Field
from pycollector.core.settings import BaseCollectorSettings

class MySettings(BaseCollectorSettings):
    """应用专属配置。"""

    # 基础字段从 BaseCollectorSettings 继承（app_name, database_url, scheduler_* 等）

    # 自定义业务字段
    my_feature_enabled: bool = Field(default=False, alias="MY_FEATURE_ENABLED")
    my_api_key: str = Field(default="", alias="MY_API_KEY")

    # 按实体扩展的配置
    source_a_url: str = Field(default="https://...", alias="SOURCE_A_URL")
    source_a_timeout: int = Field(default=30, alias="SOURCE_A_TIMEOUT")
```

### 4.2 .env 文件映射

```bash
# .env
APP_NAME=my-collector
DATABASE_URL=postgresql+psycopg://user:pass@localhost:5432/mydb
MY_FEATURE_ENABLED=true
MY_API_KEY=sk-xxxxx
SOURCE_A_URL=https://source-a.example.com/api
SOURCE_A_TIMEOUT=60
```

---

## 5. 自定义调度策略

### 5.1 调整调度时间

```python
from pycollector.scheduler.service import (
    WeeklyScheduleConfig,
    RetryPolicyConfig,
    parse_weekday,
)

weekly = WeeklyScheduleConfig(
    enabled=True,
    weekday=parse_weekday("MONDAY"),  # 每周一
    hour=8,                            # 早上 8 点
    minute=0,
    poll_interval_seconds=60,          # 每分钟检查一次
)

retry = RetryPolicyConfig(
    max_retry_count=3,                 # 最多重试 3 次
    retry_interval_seconds=300,        # 每次间隔 5 分钟
)
```

### 5.2 注入自定义回调

`CollectionSchedulerService` 通过回调注入实现与业务逻辑的解耦：

```python
scheduler = CollectionSchedulerService(
    weekly_schedule=weekly,
    retry_policy=retry,
    entity_schedules=entity_schedules,
    create_scheduled_job=my_create_job,       # 你的任务创建逻辑
    run_job=my_run_job,                       # 你的任务执行逻辑
    update_job_detail=my_update_detail,        # 你的状态更新逻辑
    find_existing_scheduled_job=my_find_job,  # 可选：持久化去重
)
```

---

## 6. 自定义仓储

### 6.1 继承 BaseRepository

```python
from pycollector.repository.base import BaseRepository
from myapp.models import MyModel

class MyRepository(BaseRepository[MyModel]):
    """我的领域仓储。"""

    def __init__(self, session):
        super().__init__(session, MyModel)

    def find_by_code(self, code: str) -> MyModel | None:
        """按业务编码查找。"""
        return (
            self._session.query(MyModel)
            .filter(MyModel.code == code)
            .first()
        )

    def upsert(self, record: MyModel) -> str:
        """自定义 upsert 逻辑。"""
        existing = self.find_by_code(record.code)
        if existing is None:
            self.add(record)
            return "inserted"
        if existing.hash == record.hash:
            return "unchanged"
        self.delete(existing)
        self.add(record)
        return "updated"
```

详细实现参考 `examples/dividend_collector_demo/repository.py`。

---

## 7. 数据载体类型参考

选择合适的采集策略取决于数据源的载体类型。以下是框架支持的常见类型：

| 类型 | 描述 | 采集方式 | 复杂度 |
|------|------|---------|--------|
| `html_static` | 静态 HTML 页面，数据在 `<table>` 中 | `_http_get` → BeautifulSoup/正则 | 低 |
| `html_inline_js` | HTML 中内嵌 JSON/JS 变量 | `_http_get` → 正则提取 JSON | 低 |
| `html_same_page_api` | JS 调用同域 API | Network 面板抓取 API URL → 模拟请求 | 中 |
| `html_paginated` | 分页表格 | `_http_get` → 解析分页参数 → 循环遍历 | 中 |
| `pdf_directory` | PDF 文件列表 | `_http_get` → 提取 PDF 链接 → `_http_get_bytes` → pypdf | 中 |
| `pdf_api_encrypted` | API 加密后返回 PDF | 逆向 OAuth/AES → 解密 → pypdf | 高 |
| `html_directory_plus_detail` | 列表页 + 详情页 | `_http_get` 列表 → 提取详情链接 → 逐条请求 | 中 |
| `entry_html_inline_json` | 入口 HTML 包含 `<script type="application/json">` | `_http_get` → JSON 解析 | 低 |
| `html_annual_directory_plus_product_select_plus_detail` | 年份目录 → 产品 → 详情 | 多级遍历 | 高 |

### 路径模式与请求量估算

| 路径模式 | 单次采集请求数 | 适用场景 |
|---------|-------------|---------|
| `entry_page_only` | 1 | 所有数据在入口页面 |
| `entry_page -> same_page_api` | 1~2 | 入口页 + 1 个 API |
| `entry_page -> annual_pdf` | 1 + N | 入口页 + N 个 PDF |
| `entry_page -> one_detail_page` | 1 + N | 列表 + N 个详情 |
| `entry_page -> iframe` | 2 | iframe 内嵌数据 |
| `entry_page -> annual_directory -> product_select -> product_detail` | 1 + Y + P | 年份数 × 产品数 |

> 更多多领域对比分析见 [DOMAIN_PATTERNS.md](DOMAIN_PATTERNS.md)。