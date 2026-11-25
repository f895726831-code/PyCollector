# PyCollector

**基于整洁架构的 Python Web 数据采集框架。**

PyCollector 提供了构建多源 Web 数据采集系统所需的基础设施——定时抓取、解析、存储——同时保持业务逻辑的整洁与可测试性。

## 架构

PyCollector 遵循 **领域驱动设计（DDD）+ 端口与适配器**（六边形架构）模式：

```
┌─────────────────────────────────────────────────────────┐
│                   API 层 (FastAPI)                       │
│               路由、DTO、请求校验                         │
├─────────────────────────────────────────────────────────┤
│                   应用服务层                              │
│            采集执行、任务编排                             │
├─────────────────────────────────────────────────────────┤
│                     领域层                               │
│            枚举、领域模型、纯业务逻辑                      │
├──────────────────────┬──────────────────────────────────┤
│     仓储层            │      适配器 / 采集器层             │
│   SQLAlchemy 模型,   │   BaseCollector、Protocol、       │
│   通用 CRUD 基类     │   Registry、各实体采集器           │
└──────────────────────┴──────────────────────────────────┘
```

## 特性

- **可插拔采集器** — 定义 Protocol 接口，注册"实体→采集器"映射，框架负责实例化与生命周期管理。
- **采集器基类** — 内置 HTTP 工具（GET/POST/字节流）、SSL 上下文、执行步骤追踪、结构化警告/跳过项构建器、错误标准化。
- **注册器 + 工厂模式** — 将实体编码映射到采集器工厂；启动时一键构建全部已注册采集器。
- **后台调度器** — 周期调度（按周/月/季度），支持按实体启停、槽位去重、可配置重试、工作线程执行。
- **结构化可观测性** — JSON 结构化日志、告警富化（严重级别 + 告警编码）、适用于监控看板的可观测性摘要。
- **错误处理框架** — `AppError` 配合枚举错误码与预置的 FastAPI 异常处理器，输出一致的 JSON 错误响应。
- **数据库层** — SQLAlchemy 2.0，懒加载引擎/会话单例，FastAPI 依赖注入生成器，通用 `BaseRepository`。
- **类型安全配置** — Pydantic-settings 配合 `.env` 文件，`@lru_cache` 单例模式。
- **测试基础设施** — Pytest 夹具，支持内存 SQLite 和 FastAPI `TestClient`。

## 安装

```bash
pip install pycollector
```

开发依赖：
```bash
pip install pycollector[dev]
```

PostgreSQL 支持：
```bash
pip install pycollector[postgres]
```

## 快速开始

### 1. 定义你的领域

```python
# myapp/domain/enums.py
from enum import StrEnum
from pycollector.domain.enums import ErrorCode

class MyEntityCode(StrEnum):
    SOURCE_A = "SOURCE_A"
    SOURCE_B = "SOURCE_B"

# 按需扩展错误码
class MyErrorCode(ErrorCode):
    CUSTOM_ERROR = "CUSTOM_ERROR"
```

### 2. 创建采集器

```python
# myapp/collectors/source_a.py
from pycollector.collector.base import BaseCollector
from pycollector.collector.protocol import ParseResult
from pycollector.collector.context import EntityConfig

class SourceACollector(BaseCollector):
    def __init__(self, entity_config: EntityConfig) -> None:
        super().__init__(entity_config)

    def fetch(self):
        fetched_at = self._utc_now()
        response = self._http_get(self.source_url)
        return self._build_fetch_result(response, fetched_at)

    def parse(self, raw_content: str) -> ParseResult:
        # 在此编写你的解析逻辑
        records = [self._build_standard_record(name="item1", value="42")]
        return ParseResult(records=records, warnings=[])
```

### 3. 注册采集器

```python
# myapp/registry.py
from pycollector.collector.registry import CollectorRegistry
from pycollector.collector.context import EntityConfig
from myapp.collectors.source_a import SourceACollector
from myapp.domain.enums import MyEntityCode

entity_configs = {
    "SOURCE_A": EntityConfig(
        entity_code=MyEntityCode.SOURCE_A,
        entity_name="数据源 A",
        source_url="https://example.com/data",
    ),
}

factories = {
    "SOURCE_A": SourceACollector,
}

registry = CollectorRegistry(entity_configs, factories)
collectors = registry.build_all()  # {"SOURCE_A": SourceACollector(...)}
```

### 4. 组装应用

```python
# myapp/main.py
from pycollector.main import create_app

app = create_app(
    api_routers=[
        # (your_router, "/api/v1", "your_tag"),
    ],
)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

## 推荐项目结构

```
your-project/
├── pyproject.toml
├── .env
├── src/
│   └── your_app/
│       ├── main.py              # 应用工厂 + 依赖组装
│       ├── core/                # 你的配置（继承 BaseCollectorSettings）
│       ├── api/
│       │   └── routes/          # FastAPI 路由模块
│       ├── domain/
│       │   ├── enums.py         # 实体编码、错误码
│       │   └── models.py        # Pydantic 领域模型
│       ├── application/
│       │   └── services/        # 采集执行、编排
│       ├── collector/
│       │   ├── source_a.py      # 各实体采集器
│       │   └── registry.py      # CollectorRegistry 组装
│       ├── repository/
│       │   ├── models.py        # SQLAlchemy ORM 模型
│       │   └── repos.py         # 具体仓储实现
│       └── scheduler/
│           └── config.py        # 调度与重试配置构建器
├── docs/                        # 项目文档
│   ├── ONBOARDING_GUIDE.md       # 四步入驻流程指南
│   ├── EXTENDING.md             # 框架扩展指南
│   └── DOMAIN_PATTERNS.md       # 多领域采集模式参考
├── skills/                      # Claude Code Skill 定义
│   ├── collector_onboarding/    # 可行性判定 Skill
│   └── collector_acceptance/    # 真实验收 Skill
├── examples/                    # 示例项目
│   ├── minimal_app.py           # 最小化应用示例
│   ├── pdf_collector_demo.py    # PDF 解析采集示例
│   └── dividend_collector_demo/ # 完整分红采集 Demo
└── tests/
    ├── conftest.py
    ├── unit/
    └── integration/
```

## 核心概念

### Collector Protocol（采集器协议）

每个采集器必须实现：

| 方法 | 返回值 | 用途 |
|--------|---------|---------|
| `fetch()` | `FetchResult` | 从数据源获取原始数据 |
| `parse(raw_content)` | `ParseResult` | 将原始数据解析为结构化记录 |
| `detect_available_items()` | `set[str]` | *可选* — 轻量级检测当前可用数据 |

### BaseCollector（采集器基类）

`BaseCollector` 提供以下内置能力：

- `_http_get(url, headers)` / `_http_post_json(url, payload, headers)` / `_http_get_bytes(url, headers)` — HTTP 请求工具
- `_build_execution_step(step, status, ...)` — 带计时的执行步骤追踪
- `_build_warning(...)` / `_build_skipped_item(...)` — 结构化问题追踪
- `_build_parse_error(...)` / `_build_request_failure_error(...)` — 标准化错误构造
- `_build_failure_detail(...)` — 聚合失败上下文
- `_standardize_app_error(...)` — 合并并富化错误详情
- `_log_collector_issue(...)` — 结构化日志输出

### Scheduler（调度器）

`CollectionSchedulerService` 以守护线程方式运行：

1. 按可配置间隔轮询。
2. 到达调度时间时，遍历已启用的实体。
3. 通过内存槽位键 + 可选的持久化检查进行去重。
4. 创建任务记录，然后分发到工作线程执行。
5. 失败任务自动重试（次数与间隔均可配置）。
6. 重试耗尽后产生 `RETRY_EXHAUSTED` 告警事件。

### Observability（可观测性）

每个调度任务产生：

- **告警富化**：`severity`（严重级别）、`alert_code`（告警编码）、`alert_candidate`（是否需关注）、`retry_exhausted`（重试是否耗尽）
- **可观测性摘要**：扁平的计数字典（解析数、新增数、更新数、去重数、失败数、HTTP 请求数、重试次数、执行步骤数）——适用于监控看板和告警规则
- **结构化 JSON 日志**：每行日志为单个 JSON 对象，包含 `event`、`event_category` 及领域载荷

## 文档与示例

### 文档

| 文档 | 说明 |
|------|------|
| [docs/ONBOARDING_GUIDE.md](docs/ONBOARDING_GUIDE.md) | 四步入驻流程指南（可行性判定→实现→验收→收口） |
| [docs/EXTENDING.md](docs/EXTENDING.md) | 框架扩展指南（新领域/新实体/配置/调度/仓储） |
| [docs/DOMAIN_PATTERNS.md](docs/DOMAIN_PATTERNS.md) | 多领域采集模式参考（分红/结算/偿付能力/资产负债） |

### 示例项目

| 示例 | 说明 |
|------|------|
| [examples/minimal_app.py](examples/minimal_app.py) | 最小化应用 — 5 分钟快速上手 |
| [examples/dividend_collector_demo/](examples/dividend_collector_demo/) | 完整分红采集 Demo — 包含 ORM、仓储、API、两种采集器 |
| [examples/pdf_collector_demo.py](examples/pdf_collector_demo.py) | PDF 解析采集示例 — pypdf 提取 + 正则匹配 |

### Skills

| Skill | 说明 |
|-------|------|
| [skills/collector_onboarding/](skills/collector_onboarding/SKILL.md) | 可行性判定 — Step 1（≤3 个 HTTP 请求） |
| [skills/collector_acceptance/](skills/collector_acceptance/SKILL.md) | 真实验收 — Step 3（采集→幂等→核验→判定） |

## 配置

所有配置项从环境变量或 `.env` 文件读取：

| 变量 | 默认值 | 说明 |
|----------|---------|-------------|
| `APP_NAME` | `pycollector` | 应用名称 |
| `APP_ENV` | `local` | 运行环境（local、staging、production） |
| `DATABASE_URL` | `sqlite+pysqlite:///./local_dev.db` | 数据库连接串 |
| `SCHEDULER_ENABLED` | `false` | 是否启用后台调度器 |
| `SCHEDULER_WEEKLY_DAY` | `MONDAY` | 每周执行日 |
| `SCHEDULER_WEEKLY_HOUR` | `9` | 执行小时（0-23） |
| `SCHEDULER_MAX_RETRY_COUNT` | `1` | 最大重试次数 |
| `SCHEDULER_RETRY_INTERVAL_SECONDS` | `60` | 重试间隔（秒） |
| `COLLECTOR_HTTP_TIMEOUT_SECONDS` | `30` | 默认 HTTP 请求超时（秒） |

在你的应用中继承 `BaseCollectorSettings` 即可添加实体专属配置字段。

## 测试

```bash
# 运行全部测试
pytest

# 带覆盖率报告
pytest --cov=pycollector

# 运行指定测试文件
pytest tests/unit/test_collector.py
```

框架内置 `conftest.py`，提供内存 SQLite 和 FastAPI `TestClient` 夹具。

## 许可证

MIT — 详见 [LICENSE](LICENSE)。

## 致谢

PyCollector 提炼自一个生产级保险数据采集平台，该平台管理 48+ 家保险公司、横跨 5 个数据领域的数据源。本框架是该项目的通用可复用基础设施部分。

---

🤖 Generated with [Claude Code](https://claude.com/claude-code)