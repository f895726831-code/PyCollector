"""
PDF 解析采集示例

演示如何使用 PyCollector 从 PDF 文件中提取结构化数据。

核心模式：
1. fetch() — _http_get_bytes() 下载 PDF
2. parse() — pypdf.PdfReader 提取文本
3. 正则匹配 — 从文本中提取结构化字段
4. 去重 — 按 (report_period, indicator_name) 去重
5. 输出 — 构建 ParseResult

依赖：pip install pypdf>=6.0.0

注意：
- 此示例使用一个公开的、不含敏感信息的 PDF URL
- 实际使用时替换 source_url 和正则模式
- PDF 文本提取可能因格式不同而需要调整正则
"""

from datetime import UTC, datetime
import re
from urllib.error import HTTPError, URLError

from pycollector.collector.base import BaseCollector
from pycollector.collector.context import CollectorConfig, EntityConfig
from pycollector.collector.protocol import FetchResult, ParseResult
from pycollector.core.errors import AppError
from pycollector.domain.enums import ErrorCode


class PdfCollector(BaseCollector):
    """通用 PDF 解析采集器。

    此采集器展示 PDF 解析的标准模式：
    1. 使用 _http_get_bytes() 下载 PDF（而非 _http_get() 获取 HTML）
    2. 使用 pypdf 提取文本
    3. 使用正则表达式匹配目标数据
    4. 按业务唯一键去重
    """

    def __init__(self, entity_config: EntityConfig) -> None:
        super().__init__(entity_config)

    def fetch(self) -> FetchResult:
        """下载 PDF 文件。

        使用 _http_get_bytes() 而非 _http_get()：
        - _http_get() 返回解码后的文本（适合 HTML/JSON）
        - _http_get_bytes() 返回原始字节（适合 PDF/图片等二进制文件）
        """
        fetched_at = datetime.now(UTC)
        try:
            response = self._http_get_bytes(self.source_url)
        except (HTTPError, URLError, TimeoutError, ValueError) as exc:
            raise AppError(
                error_code=ErrorCode.SOURCE_FETCH_FAILED,
                error_message=f"PDF 下载失败: {exc}",
                status_code=500,
            ) from exc
        return self._build_fetch_result(response, fetched_at)

    def parse(self, raw_content: str) -> ParseResult:
        """从 PDF 字节内容中提取结构化数据。

        注意：raw_content 在这里实际上是 PDF 的二进制内容
        以字符串形式传递。实际处理时需要将其转回 bytes。
        """
        execution_steps: list[dict] = []
        warnings: list[dict] = []

        # Step 1: 使用 pypdf 提取文本
        step_start = self._start_step()
        try:
            from pypdf import PdfReader
            import io

            # raw_content 可能包含 PDF 二进制数据
            # 如果 _http_get_bytes 返回的 content 是 bytes，直接使用
            # 如果是 str（通过 _build_fetch_result 转换），需要 encode 回去
            # 实际项目中建议重写 _build_fetch_result 以保留原始 bytes
            pdf_bytes = (
                raw_content.encode("latin-1")
                if isinstance(raw_content, str)
                else raw_content
            )
            reader = PdfReader(io.BytesIO(pdf_bytes))
            full_text = ""
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    full_text += page_text + "\n"

            page_count = len(reader.pages)
        except Exception as exc:
            execution_steps.append(
                self._build_execution_step(
                    step="pdf_extract_text",
                    status=self.STEP_STATUS_FAILED,
                    message=f"PDF 文本提取失败: {exc}",
                    started_at=step_start,
                )
            )
            raise AppError(
                error_code=ErrorCode.PARSE_RESULT_EMPTY,
                error_message=f"PDF 解析失败: {exc}",
                status_code=500,
                detail={
                    "failure_step": "pdf_extract_text",
                    "execution_steps": execution_steps,
                },
            ) from exc

        execution_steps.append(
            self._build_execution_step(
                step="pdf_extract_text",
                status=self.STEP_STATUS_SUCCESS,
                message=f"提取了 {page_count} 页文本，共 {len(full_text)} 字符",
                started_at=step_start,
            )
        )

        # Step 2: 正则匹配目标数据
        # ---------------------------------------------------------------
        # 以下正则模式是示例，实际使用时替换为你需要提取的字段
        # ---------------------------------------------------------------
        step_start = self._start_step()

        # 示例模式：匹配 "指标名：数值" 格式
        # 实际项目中，不同 PDF 的布局不同，需要根据具体格式调整
        patterns = {
            "total_assets": r"资产总计[：:]\s*([\d,]+\.?\d*)",
            "total_liabilities": r"负债总计[：:]\s*([\d,]+\.?\d*)",
            "equity": r"所有者权益[：:]\s*([\d,]+\.?\d*)",
            "revenue": r"营业[总收]*入[：:]\s*([\d,]+\.?\d*)",
            "net_profit": r"净利润[：:]\s*([\d,]+\.?\d*)",
        }

        records: list[dict] = []
        matched_count = 0

        for indicator_name, pattern in patterns.items():
            match = re.search(pattern, full_text)
            if match:
                # 清理数值（移除千分位逗号）
                raw_value = match.group(1).replace(",", "")
                records.append(
                    self._build_standard_record(
                        record_id=f"pdf_indicator_{indicator_name}",
                        record_value=raw_value,
                        record_period=datetime.now(UTC).strftime("%Y"),
                        category=indicator_name,
                    )
                )
                matched_count += 1
            else:
                warnings.append(
                    self._build_warning(
                        reason_code="PATTERN_NOT_MATCHED",
                        message=f"PDF 中未找到指标: {indicator_name}",
                        step="regex_match",
                        item_type="indicator",
                        indicator_name=indicator_name,
                    )
                )

        execution_steps.append(
            self._build_execution_step(
                step="regex_match",
                status=(
                    self.STEP_STATUS_SUCCESS
                    if matched_count > 0
                    else self.STEP_STATUS_FAILED
                ),
                message=f"匹配到 {matched_count}/{len(patterns)} 个指标",
                started_at=step_start,
            )
        )

        if not records:
            raise AppError(
                error_code=ErrorCode.PARSE_RESULT_EMPTY,
                error_message="PDF 中未匹配到任何指标",
                status_code=500,
                detail={
                    "failure_step": "regex_match",
                    "execution_steps": execution_steps,
                },
            )

        return ParseResult(
            records=records,
            warnings=warnings,
            execution_steps=execution_steps,
        )

    def _build_standard_record(self, **fields) -> dict:
        """覆盖基类方法，添加 PDF 来源的元信息。"""
        return {
            "entity_code": self.entity_code,
            "entity_name": self.entity_name,
            "source_url": self.source_url,
            "collected_at": self._resolve_collected_at(),
            **fields,
        }


# ---------------------------------------------------------------------------
# PDF 解析实用技巧（从生产经验中提炼）
# ---------------------------------------------------------------------------

"""
## 常见 PDF 解析问题与解决方案

### 1. 数字间距问题
PDF 文本提取可能在数字中插入空格：
  "2 0 2 4 年" → 需要清理为 "2024年"
  "1 4 2 %"   → 需要清理为 "142%"

解决方法：
  text = re.sub(r"(\d)\s+(\d)", r"\1\2", text)

### 2. 多行字段合并
表格中的长文本可能跨越多行：
  "货币资金                                          100,000
   交易性金融资产                                     50,000"

解决方法：
  使用 re.DOTALL 模式，匹配时包容换行

### 3. 表头误识别
PDF 的表头行（如"项目""金额"）可能被正则匹配为数据。

解决方法：
  添加黑名单过滤：
  HEADER_TERMS = {"项目", "金额", "序号", "item", "amount"}

### 4. 千分位逗号
金额字段可能包含千分位分隔符：
  "1,234,567" → 需要移除逗号后转为数字

解决方法：
  value = raw.replace(",", "")

### 5. 括号表示负数
某些财务 PDF 用括号表示负数：
  "(1,234)" → -1234

解决方法：
  if raw.startswith("(") and raw.endswith(")"):
      value = "-" + raw[1:-1].replace(",", "")

### 6. 跨年份格式不一致
同一个公司的不同年份 PDF 可能使用不同的排版格式。

解决方法：
  - 为每个年份编写适配器（if year >= 2020: ... else: ...）
  - 或者使用更宽松的正则（包容多种格式变体）

### 7. 加密 PDF 处理
部分 PDF 需要密码或有 DRM 保护。

解决方法（仅限合法授权的场景）：
  reader = PdfReader(file)
  if reader.is_encrypted:
      reader.decrypt("password")
"""


# ---------------------------------------------------------------------------
# 使用示例
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    """
    运行此示例前请确保：
    1. pip install pypdf
    2. 替换 source_url 为一个实际可访问的 PDF URL
    """

    # 示例：使用 W3C 的一个公开 PDF
    config = EntityConfig(
        entity_code="PDF_DEMO",
        entity_name="PDF Demo",
        source_url="https://www.w3.org/WAI/ER/tests/xhtml/testfiles/resources/pdf/dummy.pdf",
        collector_config=CollectorConfig(request_timeout_seconds=30),
    )

    collector = PdfCollector(config)
    print(f"采集器: {collector.collector_component_name}")
    print(f"目标: {collector.source_url}")

    try:
        fetch_result = collector.fetch()
        print(f"下载完成: HTTP {fetch_result.http_status}")
        print(f"文件大小: {len(fetch_result.raw_content)} bytes")

        parse_result = collector.parse(fetch_result.raw_content)
        print(f"解析完成: {len(parse_result.records)} 条记录")
        for record in parse_result.records:
            print(f"  - {record['record_id']}: {record['record_value']}")

        if parse_result.warnings:
            print(f"警告: {len(parse_result.warnings)} 条")
            for w in parse_result.warnings:
                print(f"  - [{w['reason_code']}] {w['message']}")

    except AppError as e:
        print(f"采集失败 [{e.error_code}]: {e.error_message}")