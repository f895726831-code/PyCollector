# 多领域采集模式参考

本文档对比分析 PyCollector 框架在多种数据采集领域中的应用模式，帮助你快速判断自己的场景适用哪种模式。

---

## 领域对比矩阵

| 维度 | 分红实现率 | 万能结算利率 | 偿付能力充足率 | 资产负债表 |
|------|-----------|-------------|--------------|-----------|
| **时间维度** | 年度（`year`） | 月度（`month`） | 季度（`quarter`） | 年度（`year`） |
| **典型数据量** | 数十 ~ 数千条 | 数百 ~ 数千条 | 数条 ~ 数十条 | 数十 ~ 数百条 |
| **主要载体** | HTML / API JSON | API JSON / 分页HTML / 加密PDF | PDF / HTML | PDF |
| **反爬强度** | 中 ~ 高 | 低 ~ 中 | 低 | 低 |
| **验收冷却** | 30 分钟 | 15 分钟 | 可省略 | 可省略 |
| **数据特征** | 比率（百分比） | 利率（百分比） | 比率（百分比） | 金额（元） |
| **去重维度** | 年度 + 产品 | 月度 + 产品 + 账户类型 | 季度 + 指标名 | 年度 + 科目 |

---

## 各领域采集器对比

### 分红实现率（Dividend）

**数据特征：** 保险公司每年披露一次分红产品的实际分红与预期分红的比率。

**特有字段：**

| 字段 | 说明 |
|------|------|
| `record_period` | 分红年度（如 `2024`） |
| `product_name` | 产品名称 |
| `category` | 分红方式（现金红利/增额红利/终了红利） |
| `effective_date` | 保单生效日期区间 |
| `metric_value` | 分红实现率（如 `142%`） |

**典型数据载体：**
- `html_static`：信息公开页面的静态表格（最常见）
- `html_same_page_api`：页面通过 JS 加载 JSON 数据
- `html_inline_js`：数据内嵌在 HTML 的 `<script>` 标签中

---

### 万能结算利率（Settlement Rate）

**数据特征：** 保险公司每月发布万能险账户的结算利率。

**特有字段：**

| 字段 | 说明 |
|------|------|
| `record_period` | 结算月份（如 `2024-01`） |
| `product_name` | 产品名称 |
| `account_type` | 账户类型（通常为 `万能账户`） |
| `metric_value` | 结算利率（如 `3.5%`） |
| `announcement_date` | 公告日期 |

**与分红的差异：**

1. **时间粒度更细**：月度 vs 年度，数据量通常更大
2. **需要分页处理**：部分站点月度数据量大，需要遍历分页
3. **存在加密 PDF 场景**：部分公司的万能险数据仅在加密 PDF 中披露，需要逆向 OAuth + AES 解密流程
4. **反爬更弱**：结算利率站点的反爬通常比分红站点宽松
5. **验收冷却更短**：可缩短到 15 分钟

**典型数据载体：**
- `html_api`：HTML 页面 + API JSON
- `html_paginated`：分页表格
- `pdf_api_encrypted`：加密 API → PDF → 解析（最复杂的一类）

---

### 偿付能力充足率（Solvency Ratio）

**数据特征：** 保险公司每季度披露偿付能力指标。

**特有字段：**

| 字段 | 说明 |
|------|------|
| `record_period` | 报告季度（如 `2024-Q1`） |
| `indicator_name` | 指标名称（如 `综合偿付能力充足率`） |
| `metric_value` | 指标值（如 `215%`） |

**与分红的差异：**

1. **数据量最小**：每季度几条到几十条
2. **几乎无反爬**：偿付能力是法定披露义务，网站通常完全开放
3. **可以省略冷却期**
4. **PDF 是主要载体**：很多公司以 PDF 形式发布偿付能力报告，需要 pypdf 解析
5. **指标固定**：偿付能力指标是监管规定项，种类和名称相对标准化

**典型数据载体：**
- `pdf_directory`：PDF 报告列表
- `html_static`：静态 HTML 指标页面

**PDF 解析流程（偿付能力）：**

```
入口页面 ──GET──→ 提取 PDF 链接 + 季度标签
    │
    ↓
下载 PDF ──_http_get_bytes──→ pypdf.PdfReader 提取文本
    │
    ↓
正则匹配 ──28+ 条正则──→ 提取 (指标名, 指标值)
    │
    ↓
去重 ──按 (report_period, indicator_name)──→ 写入数据库
```

---

### 资产负债表（Balance Sheet）

**数据特征：** 保险公司每年在年报中披露资产负债表项目。

**特有字段：**

| 字段 | 说明 |
|------|------|
| `record_period` | 报告年度（如 `2024-12-31`） |
| `item_name` | 科目名称（如 `货币资金`） |
| `item_category` | 科目类别（资产/负债/所有者权益） |
| `metric_value` | 金额（元） |

**与分红的差异：**

1. **数据量大**：每年数百个科目
2. **完全依赖 PDF**：资产负债表通常在 PDF 年报中
3. **跨公司正则复用**：资产负债表科目是会计准则规定项，不同公司格式相似，正则表达式可以跨公司复用
4. **值格式复杂**：金额可能有千分位逗号、括号表示负数、单位可能是"元/千元/万元/百万元"

**PDF 解析流程（资产负债表）：**

```
入口页面 ──GET──→ 提取年报 PDF 链接（匹配"信息披露报告"类文本）
    │
    ↓
下载 PDF ──_http_get_bytes──→ pypdf.PdfReader 提取文本
    │
    ↓
正则匹配 ──通用正则集──→ 提取 (科目名, 金额, 类别)
    │
    ↓
清洗 ──过滤千分位 / 括号取负 / 单位换算──→ 写入数据库
```

---

## 数据载体类型完整枚举

| 类型 | 特征 | 判别方法 | 典型采集策略 |
|------|------|---------|-------------|
| `html_static` | 静态 HTML 表格 | `<table>` 标签 + 目标数据 | BeautifulSoup / 正则 |
| `html_inline_js` | HTML 中内嵌 `var data =` | `<script>` 中有变量定义 | 正则提取 JSON |
| `html_same_page_api` | JS 调同域 API | Network 面板 XHR | 模拟 API 请求 |
| `html_paginated` | URL 含 `?page=` | 分页按钮或参数 | 循环遍历分页 |
| `pdf_directory` | `<a href="*.pdf">` | PDF 链接列表 | 下载 → pypdf |
| `pdf_api_encrypted` | 加密 PDF | API 返回加密内容 | 逆向 OAuth → 解密 → pypdf |
| `html_directory_plus_detail` | 列表 → 详情 | 列表页有 `href` | 遍历详情链接 |
| `entry_html_inline_json` | `<script type="application/json">` | JSON-LD 格式 | `json.loads()` |
| `html_annual_directory_plus_product_select_plus_detail` | 年份 → 产品 → 详情 | 多级 `<select>` | 多级遍历 |

## allowed_path_pattern 图解

```
entry_page_only
  ┌──────────┐
  │ 入口页面  │ → 解析 → 记录
  └──────────┘
  1 次请求

entry_page -> same_page_api
  ┌──────────┐     ┌──────────┐
  │ 入口页面  │ ──→ │ API 端点  │ → 解析 → 记录
  └──────────┘     └──────────┘
  2 次请求

entry_page -> annual_pdf
  ┌──────────┐     ┌──────────┐
  │ 入口页面  │ ──→ │ PDF_2024 │ → 解析 → 记录
  │          │ ──→ │ PDF_2023 │ → 解析 → 记录
  │          │ ──→ │ PDF_2022 │ → 解析 → 记录
  └──────────┘     └──────────┘
  1 + N 次请求（N = PDF 文件数）

entry_page -> one_detail_page
  ┌──────────┐     ┌──────────┐
  │ 入口页面  │ ──→ │ 详情页 1  │ → 解析 → 记录
  │ (列表)   │ ──→ │ 详情页 2  │ → 解析 → 记录
  │          │ ──→ │ 详情页 3  │ → 解析 → 记录
  └──────────┘     └──────────┘
  1 + N 次请求（N = 详情页数）

entry_page -> annual_directory -> product_select -> product_detail
  ┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐
  │ 入口页面  │ ──→ │ 年份目录  │ ──→ │ 产品选择  │ ──→ │ 产品详情  │ → 记录
  └──────────┘     └──────────┘     └──────────┘     └──────────┘
  1 + Y + P 次请求（Y = 年份数，P = 产品数）
```

---

## 新领域接入决策树

收到一个新数据领域需求时，按以下流程判断：

```
1. 数据在哪里？
   ├── HTML 页面 ──→ 2
   ├── API JSON ──→ 直接使用 html_same_page_api 模式
   └── PDF 文件 ──→ 3

2. HTML 页面的结构？
   ├── 数据在入口页 ──→ entry_page_only（最简单）
   ├── 入口页只有索引 ──→ html_directory_plus_detail
   ├── 数据在 iframe 中 ──→ entry_page -> iframe
   ├── 页面 JS 加载数据 ──→ html_same_page_api
   └── 页面需要浏览器渲染 ──→ ⚠️ 高复杂度，考虑放弃

3. PDF 如何获取？
   ├── 页面直接链接 ──→ pdf_directory
   ├── 通过 API 获取 ──→ html_same_page_api + pypdf
   └── 加密获取 ──→ ⚠️ pdf_api_encrypted，需要逆向工程

4. 确认时间维度
   ├── 年度 ──→ record_period = "YYYY"
   ├── 月度 ──→ record_period = "YYYY-MM"
   └── 季度 ──→ record_period = "YYYY-QN"

5. 确认去重维度
   └── 选择哪些字段组合构成业务唯一键
```

---

## 参考实现

| 领域 | 示例文件 | 说明 |
|------|---------|------|
| 通用框架 | `pycollector/collector/` | 核心 Protocol + BaseCollector + Registry |
| 分红示例 | `examples/dividend_collector_demo/` | 完整可运行 Demo（HTML + API JSON） |
| PDF 解析 | `examples/pdf_collector_demo.py` | 最小化 PDF 采集示例 |
| 入驻流程 | `docs/ONBOARDING_GUIDE.md` | 四步标准化入驻流程 |