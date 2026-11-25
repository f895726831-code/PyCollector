# 四步入驻流程指南

> 修订日期：2026-06-25 | 适用于 PyCollector 框架

---

## 概述

四步流程是 PyCollector 框架中**从零接入一个数据源到生产就绪**的标准化工作流。

### 核心原则

**侦察阶段最多 3 个 HTTP 请求，一眼定生死。**

- Step 1 只判断"能不能做"，不做任何数据提取
- Step 2 优先复用 Step 1 的响应体作为测试 fixture，避免重复请求
- Step 3 执行前强制冷却期，降低被封锁概率

### 适用场景

| 数据载体类型 | 典型来源 | 复杂度 |
|-------------|---------|--------|
| 静态 HTML 页面 | 信息公开栏目中的表格 | 低 |
| API JSON | 页面 JS 调用的后端接口 | 中 |
| PDF 报告 | 年度/季度信息披露 PDF | 中 |
| JS 内嵌数据 | HTML 中 `window.__DATA__` 等 | 中 |
| JS 渲染页面 | SPA 应用 | 高（不推荐） |

---

## Step 1：可行性判定（≤3 个 HTTP 请求）

### 目标

1-2 个请求内判断能不能做。不做数据提取、不做字段映射、不爬全站。

### 输入

- `entity_code`：实体编码（如 `SOURCE_A`）
- `entity_name`：实体名称
- `source_url`：数据入口 URL

### 硬性约束

- 最多 **3 个 HTTP 请求**
- 超过 3 个仍无法判定 → 结论为 **C（放弃）**，转人工处理
- 不解析任何数据内容，只判断"链路是否稳定可达"

### 输出格式

```markdown
## 可行性判定报告

### 1. 结论
可行 / 不可行（原因）

### 2. data_carrier_type（推断）
html_static / html_inline_js / html_same_page_api /
pdf_directory / html_directory_plus_detail /
html_annual_directory_plus_product_select_plus_detail /
entry_html_inline_json / html_paginated / pdf_api_encrypted

### 3. allowed_path_pattern（推断）
entry_page_only / entry_page -> same_page_api /
entry_page -> annual_pdf / entry_page -> one_detail_page /
entry_page -> iframe -> same_page_api /
entry_page -> annual_directory -> product_select -> product_detail /
entry_page -> iframe

### 4. 反爬/WAF 风险
无 / 低 / 高 / 已确认封锁

### 5. 下一步
A. 进入实现 / B. 需补充侦察 / C. 放弃
```

### 禁止事项

- 不做 OCR
- 不做浏览器自动化
- 不下载 PDF
- 不解析表格内容
- 不爬全站链接

### 判定决策树

```
请求 source_url
├── HTTP 200 + Content-Type: text/html
│   ├── 响应包含 <table> → data_carrier_type = html_static
│   ├── 响应包含 window.__DATA__ = {...} → html_inline_js
│   ├── 响应包含 <iframe> → 检查 iframe src，判定子类型
│   ├── 响应包含 <a href="*.pdf"> → pdf_directory
│   └── 响应为空壳 + JS 渲染 → 标记为高反爬风险，倾向 C
├── HTTP 200 + Content-Type: application/json
│   └── 检查是否包含目标字段 → html_same_page_api
├── HTTP 403 / 503 / 超时
│   └── 已确认封锁 → C
└── 其他 → 补发第 2 个请求进一步判定
```

---

## Step 2：实现 + 测试

### 目标

基于 Step 1 的判定结果实现采集器，优先复用 Step 1 的响应体作为测试 fixture。不改数据库结构、不改业务模型。

### 输入

- Step 1 的判定报告
- 已确定的 `data_carrier_type` 和 `allowed_path_pattern`
- Step 1 的原始 HTTP 响应体

### 要求

1. 新增采集器类并接入主链路（Registry + 路由）
2. 补充测试：覆盖产品提取、解析逻辑、跳过规则、首次写入 / unchanged / history
3. 最小更新文档（AGENTS.md / README.md）

### 真实请求约束

- **优先用 Step 1 已获取的响应体做 fixture**，不重新请求
- 仅在 Step 1 响应不完整时，**补发 1 次请求**
- 禁止重复 Step 1 已完成的探测请求

### 禁止事项

- 不做 OCR
- 不做浏览器自动化
- 不扩散站内链接
- 不改其他实体的采集器

### 输出格式

```markdown
## 实现报告

### 改动摘要
- 新增文件：xxx_collector.py
- 修改文件：registry.py, routes.py
- 新增测试：tests/unit/test_xxx_collector.py

### 实现说明
（简述采集链路：fetch → parse → transform）

### 字段映射说明
| 源字段 | 目标字段 | 转换逻辑 |
|--------|---------|---------|
| ...    | ...     | ...     |

### 测试结果
（pytest 输出摘要）

### 风险说明
（已知问题、边界情况）

### 真实请求次数
- Step 1：N 次
- Step 2：M 次（其中 K 次复用 Step 1 响应）
- 合计新请求：M - K 次
```

---

## Step 3：真实验收

### 冷却期规则

| 情况 | 冷却时长 |
|------|---------|
| Step 1 + 2 合计真实请求 ≤ 3 次 | **30 分钟** |
| Step 1 已触发反爬/WAF | **2 小时** |
| 验收前确认 | 冷却期已过，目标站未被封锁 |

### 执行流程

1. **首次真实持久化采集**
2. **第二次重复采集**（幂等验证）
3. **查库核验**
4. **验收判定**

### 核验矩阵

| 指标 | 首次期望 | 二次期望 | 说明 |
|------|---------|---------|------|
| `status` | `SUCCESS` | `SUCCESS` | |
| `parsed_record_count` | > 0 | > 0 | 应有有效数据 |
| `inserted_count` | = parsed | **0** | 二次不应有新记录 |
| `updated_count` | 0 | **0** | 二次不应有变更 |
| `unchanged_count` | 0 | = parsed | 100% 幂等 |
| `failed_count` | 0 | 0 | |
| `warning_count` | 0 | 0 | 任何 warning 需排查 |
| `skipped_count` | 0 | 0 | 任何 skip 需排查 |

### 首次采集红旗（出现任一需暂停排查）

- `warning_count > 0`：检查每个 `reason_code`
- `failed_count > 0`：记录被丢弃
- `parsed_record_count == 0`：采集器无输出
- `status != SUCCESS`：执行抛出异常

### 查库核验重点

- 时间维度覆盖范围是否合理
- 各字段值域是否正常（无异常值、无格式错误）
- 无效值（不适用/空值/-）是否未误入库
- 所有记录的 `record_hash` 非空（幂等基础）
- 所有记录的 `source_url` 指向实际来源

### 输出格式

```markdown
## 真实验收报告

### 1. 首次真实采集结果摘要
| 指标 | 值 |
|------|-----|
| Job ID | xxx |
| Status | SUCCESS |
| 解析记录数 | N |
| Inserted | N |
| Failed / Warnings | 0 / 0 |
| 耗时 | Xs |

### 2. 第二次重复采集结果摘要
| 指标 | 值 |
|------|-----|
| Job ID | xxx |
| Status | SUCCESS |
| Inserted | 0 |
| Unchanged | N (100%) |

### 3. 查库核验结论
- 覆盖范围：YYYY ~ YYYY
- 值域检查：正常
- record_hash / source_url 非空：通过

### 4. 是否建议纳入 verified
YES / NO + 理由

### 5. 本轮未改代码
仅执行验收，未修改 src/ 下任何源代码。
```

---

## Step 4：文档收口 + Git 提交

### 目标

本轮只做文档收口，不改代码、不改数据库、不写 migration。

### 要求

1. 更新 AGENTS.md / README.md
2. 更新 CHANGELOG / RELEASE_NOTE
3. 更新 verified entities 列表和计数
4. Git 提交

### 输出

```markdown
## 文档收口报告

### 改动摘要
- 更新了哪些文档
- verified 列表和数量如何变化

### 明确说明
本轮未改代码。
```

---

## 附录 A：data_carrier_type 枚举参考

| 类型 | 特征 | 典型判别方法 |
|------|------|-------------|
| `html_static` | 静态 HTML 表格 | `<table>` 标签包含目标数据 |
| `html_inline_js` | HTML 中内嵌 JSON/JS 变量 | `window.__DATA__` 或 `<script>` 中的 `var data =` |
| `html_same_page_api` | 页面通过 JS 调用同域 API | Network 面板看到 XHR 返回 JSON |
| `pdf_directory` | PDF 文件列表 | `<a href="*.pdf">` 链接 |
| `html_directory_plus_detail` | 列表页 + 详情页 | 列表页链向多个详情页 |
| `entry_html_inline_json` | 入口 HTML 直接包含 JSON | `<script type="application/json">` |
| `html_paginated` | 分页表格 | URL 中有 `page=` 参数或分页按钮 |
| `html_annual_directory_plus_product_select_plus_detail` | 年份页 → 产品选择 → 详情 | 多级导航结构 |
| `pdf_api_encrypted` | API 加密后返回 PDF | 需要 OAuth + AES 解密 |

## 附录 B：allowed_path_pattern 枚举参考

| 模式 | 请求路径 | 典型场景 |
|------|---------|---------|
| `entry_page_only` | 1 请求 | 所有数据在入口页面上 |
| `entry_page -> same_page_api` | 2 请求 | 入口页 → API 端点 |
| `entry_page -> annual_pdf` | 2 请求/年 | 入口页 → 下载 PDF |
| `entry_page -> one_detail_page` | N+1 请求 | 列表 → 每条详情 |
| `entry_page -> iframe -> same_page_api` | 3 请求 | 入口页 → iframe → API |
| `entry_page -> annual_directory -> product_select -> product_detail` | 多级 | 年份目录 → 产品 → 详情 |
| `entry_page -> iframe` | 2 请求 | iframe 内嵌完整数据 |

---

## 适用性评估：能否用于其他数据领域？

四步流程框架完全适用，但每步的核验口径需要按领域替换。

| 步骤 | 通用口径 | 结算利率差异 | 偿付能力差异 |
|------|---------|-------------|-------------|
| Step 1 可行性判定 | data_carrier_type 枚举 | 增加 `html_paginated`（分页表格）、`pdf_api_encrypted`（加密 PDF） | 增加 `pdf_directory` |
| Step 2 实现 | 通用字段映射 | settlement_month（月度）、account_type | quarter（季度）、ratio_type |
| Step 3 验收冷却 | 30 分钟 / 2 小时 | 可缩短到 **15 分钟**（结算站点反爬更弱） | **可省略**（数据量小，通常无反爬） |
| Step 3 查库核验 | 时间连续性 + 值域 | 月度连续，利率 0%-6% | 季度连续，ratio > 0 |
| Step 4 文档收口 | 同上 | 更新结算利率相关章节 | 更新偿付能力相关章节 |

> 详细的多领域对比分析见 [DOMAIN_PATTERNS.md](DOMAIN_PATTERNS.md)。