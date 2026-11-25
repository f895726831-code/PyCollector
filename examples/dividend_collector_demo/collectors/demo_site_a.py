"""
演示采集器 A — HTML 静态页面型。

数据源：https://example.com
载体类型：html_static
路径模式：entry_page_only

这是一个最简单的采集器示例，演示了从 HTML 页面中提取信息的基本流程。
"""

import re
from datetime import UTC, datetime
from urllib.error import HTTPError, URLError

from pycollector.collector.base import BaseCollector
from pycollector.collector.context import EntityConfig
from pycollector.collector.protocol import FetchResult, ParseResult
from pycollector.core.errors import AppError
from pycollector.domain.enums import ErrorCode


class DemoSiteACollector(BaseCollector):
    """示例采集器：从 example.com 提取页面信息。

    此采集器展示了 HTML 静态页面型采集器的标准模式：
    1. fetch() — 发送 GET 请求获取 HTML
    2. parse() — 用正则提取结构化字段
    3. 通过 _build_standard_record() 构造标准记录
    """

    def __init__(self, entity_config: EntityConfig) -> None:
        super().__init__(entity_config)

    def fetch(self) -> FetchResult:
        """获取 example.com 首页 HTML。"""
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
        """从 HTML 中提取标题和元信息。

        解析逻辑：
        - 提取 <title> 标签内容作为 record_value
        - 提取第一个 <p> 标签内容作为补充信息
        - 使用页面内容长度作为辅助指标
        """
        warnings: list[dict] = []
        execution_steps: list[dict] = []

        # Step 1: 提取标题
        step_start = self._start_step()
        title_match = re.search(r"<title>(.*?)</title>", raw_content, re.IGNORECASE)
        title = title_match.group(1).strip() if title_match else "未找到标题"
        execution_steps.append(
            self._build_execution_step(
                step="extract_title",
                status=self.STEP_STATUS_SUCCESS,
                message=f"提取到标题: {title}",
                started_at=step_start,
            )
        )

        # Step 2: 提取正文摘要
        step_start = self._start_step()
        para_match = re.search(r"<p>(.*?)</p>", raw_content, re.IGNORECASE | re.DOTALL)
        description = (
            re.sub(r"<[^>]+>", "", para_match.group(1)).strip()[:200]
            if para_match
            else "无正文"
        )
        execution_steps.append(
            self._build_execution_step(
                step="extract_description",
                status=self.STEP_STATUS_SUCCESS,
                message=f"提取到描述: {description[:50]}...",
                started_at=step_start,
            )
        )

        # 构造记录
        records = [
            self._build_standard_record(
                record_id="page_info",
                record_value=title,
                record_period=datetime.now(UTC).strftime("%Y"),
                category="page_title",
            ),
            self._build_standard_record(
                record_id="page_description",
                record_value=description,
                record_period=datetime.now(UTC).strftime("%Y"),
                category="page_description",
            ),
        ]

        return ParseResult(
            records=records,
            warnings=warnings,
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