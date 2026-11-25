"""
演示应用入口 — 完整的 PyCollector 应用示例。

运行方式：
    cd examples/dividend_collector_demo
    python main.py

然后访问：
    http://localhost:8000/docs          — Swagger API 文档
    http://localhost:8000/api/v1/entities  — 已注册实体列表
    http://localhost:8000/api/v1/collect?entity_code=DEMO_SITE_A  — 触发采集
    http://localhost:8000/api/v1/records?entity_code=DEMO_SITE_A  — 查询记录
"""

from pycollector.main import create_app

from .domain.enums import JobStatus
from .routes import router


def main():
    """创建并启动 FastAPI 应用。"""
    app = create_app(
        api_routers=[(router, "/api/v1", "demo")],
        title="PyCollector Demo — 分红数据采集示例",
    )

    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()