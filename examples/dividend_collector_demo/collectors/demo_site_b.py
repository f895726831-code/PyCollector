"""
演示采集器 B — API JSON 型。

数据源：https://jsonplaceholder.typicode.com/posts
载体类型：html_same_page_api
路径模式：entry_page -> same_page_api

此采集器演示了 API JSON 型采集器的标准模式：
1. fetch() — 发送 GET 请求获取 JSON
2. parse() — 解析 JSON 并映射到标准记录格式
"""

from datetime import UTC, datetime
import json
from urllib.error import HTTPError, URLError

from pycollector.collector.base import BaseCollector
from pycollector.collector.context import EntityConfig
from pycollector.collector.protocol import FetchResult, ParseResult
from pycollector.core.errors import AppError
from pycollector.domain.enums import ErrorCode


class DemoSiteBCollector(BaseCollector):
    """示例采集器：从 jsonplaceholder API 获取 posts 数据。

    此采集器展示了 API JSON 型采集器的标准模式：
    1. fetch() — GET 请求获取 JSON 数组
    2. parse() — 遍历数组，将每条 post 映射为标准记录
    3. 对结构化 JSON 的处理比对 HTML 更简单直接
    """

    def __init__(self, entity_config: EntityConfig) -> None:
        super().__init__(entity_config)

    def fetch(self) -> FetchResult:
        """从 jsonplaceholder API 获取 posts 列表。"""
        fetched_at = datetime.now(UTC)
        try:
            response = self._http_get(self.source_url)
        except (HTTPError, URLError, TimeoutError, ValueError) as exc:
            raise AppError(
                error_code=ErrorCode.SOURCE_FETCH_FAILED,
                error_message=(
                    f"无法获取 {self.entity_code} ({self.entity_name}) 数据: {exc}"
                ),
                status_code=500,
            ) from exc
        return self._build_fetch_result(response, fetched_at)

    def parse(self, raw_content: str) -> ParseResult:
        """将 JSON 数组解析为记录列表。

        每条 post 映射为一个标准记录：
        - record_id: post ID
        - record_value: post 标题
        - category: userId 分类
        - 跳过标题为空的 post
        """
        warnings: list[dict] = []
        skipped_items: list[dict] = []
        execution_steps: list[dict] = []

        # Step 1: 解析 JSON
        step_start = self._start_step()
        try:
            posts = json.loads(raw_content)
        except json.JSONDecodeError as exc:
            execution_steps.append(
                self._build_execution_step(
                    step="parse_json",
                    status=self.STEP_STATUS_FAILED,
                    message=f"JSON 解析失败: {exc}",
                    started_at=step_start,
                )
            )
            raise AppError(
                error_code=ErrorCode.PARSE_RESULT_EMPTY,
                error_message=f"{self.entity_code} 返回了无效的 JSON",
                status_code=500,
                detail={
                    "failure_step": "parse_json",
                    "execution_steps": execution_steps,
                },
            ) from exc

        if not isinstance(posts, list):
            posts = [posts]

        execution_steps.append(
            self._build_execution_step(
                step="parse_json",
                status=self.STEP_STATUS_SUCCESS,
                message=f"成功解析 {len(posts)} 条记录",
                started_at=step_start,
            )
        )

        # Step 2: 映射为标准记录
        records: list[dict] = []
        record_limit = 20  # 限制记录数以保持示例简洁

        for post in posts[:record_limit]:
            title = str(post.get("title", "")).strip()
            if not title:
                skipped_items.append(
                    self._build_skipped_item(
                        reason_code="EMPTY_TITLE",
                        message=f"跳过空的标题 (id={post.get('id')})",
                        step="map_records",
                        item_type="post",
                    )
                )
                continue

            records.append(
                self._build_standard_record(
                    record_id=f"post_{post['id']}",
                    record_value=title,
                    record_period=datetime.now(UTC).strftime("%Y"),
                    category=f"user_{post.get('userId', 'unknown')}",
                )
            )

        if len(posts) > record_limit:
            warnings.append(
                self._build_warning(
                    reason_code="TRUNCATED",
                    message=f"记录已截断（显示 {record_limit}/{len(posts)} 条）",
                    step="map_records",
                    item_type="post",
                )
            )

        return ParseResult(
            records=records,
            warnings=warnings,
            skipped_items=skipped_items,
            execution_steps=execution_steps,
        )

    def _build_standard_record(self, **fields) -> dict:
        """覆盖基类方法，添加领域专属字段。"""
        return {
            "entity_code": self.entity_code,
            "entity_name": self.entity_name,
            "source_url": self.source_url,
            "collected_at": self._resolve_collected_at(),
            **fields,
        }