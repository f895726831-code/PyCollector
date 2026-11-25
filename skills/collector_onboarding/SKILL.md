# Collector Onboarding Skill

## Purpose

对新数据源执行四步流程中的 **Step 1：可行性判定**。目标是 1-2 个 HTTP 请求内判定该数据源是否可用 PyCollector 框架采集。

本 Skill 聚焦**判定**，不执行数据提取、不解析内容、不实现任何代码。

---

## Use this skill when

使用本 Skill 的条件：

- 接收到一个新的数据源 URL
- 需要判定该数据源是否能通过 PyCollector 框架采集
- 尚未开始任何代码实现
- 需要输出标准化的可行性判定报告

典型使用场景：

- 评估一个新的 HTML 静态页面数据源
- 评估一个 API JSON 数据源
- 评估一个 PDF 报告型数据源
- 判断目标站点是否有反爬/WAF 保护

---

## Required inputs

调用方应提供：

```text
entity_code:       实体编码（如 SOURCE_A）
entity_name:       实体名称
source_url:        数据入口 URL
```

---

## Workflow

### Step 1 — 发送探测请求

向 `source_url` 发送 1 个 GET 请求：

```
GET source_url
User-Agent: Mozilla/5.0
```

分析响应：

| 检查项 | 判别方法 |
|--------|---------|
| HTTP 状态码 | 200 / 301 / 403 / 503 |
| Content-Type | text/html / application/json / application/pdf |
| 页面大小 | 空壳页面还是包含数据的完整页面 |
| `<table>` 标签 | 是否存在数据表格 |
| `<script>` 标签 | 是否内嵌 JSON/JS 变量 |
| `<a href="*.pdf">` | 是否存在 PDF 链接 |
| `<iframe>` | 是否通过 iframe 加载数据 |
| 分页控件 | 是否有分页按钮或 `page=` 参数 |

### Step 2 — 判定 data_carrier_type

根据响应特征，推断数据载体类型：

| 响应特征 | data_carrier_type |
|---------|-------------------|
| `<table>` 包含目标数据 | `html_static` |
| `<script>` 中有 `var data =` 或 `window.__DATA__` | `html_inline_js` |
| Network 中有 XHR 返回 JSON | `html_same_page_api` |
| `<a href="*.pdf">` 链接 | `pdf_directory` |
| 列表 + 详情链接 | `html_directory_plus_detail` |
| `<script type="application/json">` | `entry_html_inline_json` |
| 分页参数或分页按钮 | `html_paginated` |
| 需要年份→产品→详情多级导航 | `html_annual_directory_plus_product_select_plus_detail` |
| API 响应为加密内容 | `pdf_api_encrypted` |

### Step 3 — 判定 allowed_path_pattern

根据 carrier type 推断采集路径：

| carrier type | 典型 path pattern |
|-------------|-------------------|
| `html_static` | `entry_page_only` |
| `html_inline_js` | `entry_page_only` |
| `html_same_page_api` | `entry_page -> same_page_api` |
| `pdf_directory` | `entry_page -> annual_pdf` |
| `html_directory_plus_detail` | `entry_page -> one_detail_page` |
| `entry_html_inline_json` | `entry_page_only` |
| `html_paginated` | `entry_page_only`（含分页遍历） |

### Step 4 — 评估反爬风险

| 指标 | 风险等级 |
|------|---------|
| 无任何反爬措施 | 无 |
| 有 User-Agent 检查但可绕过 | 低 |
| 有频率限制 / 需要 Referer | 高 |
| 返回 403 / 503 / 验证码 | 已确认封锁 |
| 需要浏览器执行 JS | 高（不推荐） |

### Step 5 — 输出判定结论

- **A（进入实现）**：链路稳定可达，载体类型明确，无封锁风险
- **B（需补充侦察）**：部分信息不明，需要 1 次补充请求
- **C（放弃）**：已封锁、需要浏览器自动化、数据量不合理

---

## 硬性约束

- 最多 **3 个** HTTP 请求。超过 3 个仍无法判定 → 直接归为 C
- 不做 OCR
- 不做浏览器自动化
- 不下载 PDF
- 不解析表格内容
- 不爬全站链接

---

## Output template

```markdown
## 可行性判定报告

### 1. 结论
<可行/不可行> — <原因>

### 2. 基本信息
- entity_code: <CODE>
- entity_name: <NAME>
- source_url: <URL>
- HTTP 状态码: <STATUS>
- Content-Type: <TYPE>

### 3. data_carrier_type
<类型> — <判定依据>

### 4. allowed_path_pattern
<模式> — <判定依据>

### 5. 反爬/WAF 风险
<无/低/高/已确认封锁> — <判定依据>

### 6. 下一步
<A/B/C> — <理由>

### 7. HTTP 请求记录
| # | URL | 方法 | 状态码 | 用途 |
|---|-----|------|--------|------|
| 1 | ... | GET | ... | 探测入口 |
| 2 | ... | ... | ... | 补充探测（如有） |

### 8. 备注
<额外发现、注意事项>
```

---

## Execution notes

- 使用 `pycollector.collector.base.BaseCollector._http_get()` 发起请求
- 或使用 `curl -s -o /dev/null -w "%{http_code}" URL` 快速探测
- 不要用浏览器打开目标页面（可能触发 JS 执行和额外请求）
- 如果页面需要 cookie，在第一次请求中携带空的 cookie jar，观察是否重定向