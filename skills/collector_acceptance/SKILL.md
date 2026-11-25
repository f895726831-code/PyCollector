# Collector Acceptance Skill

## Purpose

对已实现的采集器执行标准化验收流程（Step 3：真实验收）。通过首次采集 → 重复采集 → 查库核验 → 判定四阶段，确定实体是否可标记为 **verified**。

本 Skill 聚焦**验收**，不改代码。

---

## Use this skill when

使用本 Skill 的条件：

- 采集器实现已完成
- 采集器已在 Registry 中注册
- 单元测试已通过
- 下一步是真实验收
- 需要判定实体是否可标记为 verified

典型使用场景：

- 验收新实现的 HTML 静态页面型采集器
- 验收 API JSON 型采集器
- 验收 PDF 解析型采集器
- 验证幂等性（unchanged 行为）
- 验收后检查数据库分布

---

## Required inputs

调用方应提供：

```text
entity_code:              实体编码
entity_name:              实体名称
data_domain:              数据领域（如 DIVIDEND / SETTLEMENT）
data_carrier_type:        数据载体类型
allowed_path_pattern:     采集路径模式
source_url:               数据入口 URL
```

---

## Acceptance workflow

### Phase 0 — 前置检查

在触发任何真实采集之前验证：

1. **采集器已注册**：`registry.py` 中存在该实体的工厂映射
2. **数据库表存在**：目标表（如 `record_current`、`record_history`）已创建
3. **数据库可连接**：`DATABASE_URL` 配置正确，连接可达
4. **无预存数据**：`SELECT COUNT(*) FROM record_current WHERE entity_code = '<CODE>'` 返回 0

### Phase 1 — 首次真实持久化采集

触发一次真实采集任务：

```python
from pycollector.collector.registry import CollectorRegistry

# 获取采集器并执行
collector = registry.build_one(entity_code)
fetch_result = collector.fetch()
parse_result = collector.parse(fetch_result.raw_content)
```

**期望结果：**

| 指标 | 期望值 | 说明 |
|------|--------|------|
| `status` | `SUCCESS` | |
| `parsed_record_count` | > 0 | 应有有效数据输出 |
| `inserted_count` | = `parsed_record_count` | 首次全部为新记录 |
| `updated_count` | 0 | 无旧数据可更新 |
| `unchanged_count` | 0 | 无旧数据可匹配 |
| `failed_count` | 0 | |
| `warning_count` | 0 | 任何 warning 需要排查 |
| `skipped_count` | 0 | 任何 skip 需要排查 |

**红旗（出现任一需暂停排查）：**

- `warning_count > 0`：检查每个 `reason_code`。常见原因：
  - `NO_RECORDS_EXTRACTED`：页面格式与预期不匹配
  - `PARSE_WARNING`：个别字段解析异常
  - `DOWNLOAD_FAILED`：网络问题或 URL 变更
- `failed_count > 0`：严重 — 记录被丢弃
- `parsed_record_count == 0`：采集器无输出
- `status != SUCCESS`：执行抛出异常

### Phase 2 — 第二次重复采集（幂等验证）

使用相同的请求再次触发采集：

**期望结果：**

| 指标 | 期望值 | 说明 |
|------|--------|------|
| `status` | `SUCCESS` | |
| `inserted_count` | **0** | 不应有新记录 |
| `updated_count` | **0** | 不应有变更 |
| `unchanged_count` | **= 首次 `parsed_record_count`** | 100% 幂等 |
| `failed_count` | 0 | |

**红旗：**

- `inserted_count > 0`：源数据在两次采集间发生了变化（短时间窗口内不太可能）— 检查时间戳去重逻辑
- `updated_count > 0`：记录哈希变化 — 可能是数据中含有非确定性内容
- `unchanged_count < parsed_record_count`：部分记录未被识别为重复

### Phase 3 — 数据库核验

执行核验查询：

```sql
-- 行数统计
SELECT entity_code, COUNT(*) FROM record_current GROUP BY entity_code;

-- 时间维度分布
SELECT record_period, COUNT(*)
FROM record_current
WHERE entity_code = '<CODE>'
GROUP BY record_period ORDER BY record_period;

-- 值域检查
SELECT MIN(metric_value), MAX(metric_value)
FROM record_current WHERE entity_code = '<CODE>';
```

**期望结果：**

| 检查项 | 期望值 | 说明 |
|--------|--------|------|
| `record_current` 行数 | = Phase 1 的 `inserted_count` | |
| `record_history` 行数 | 0 | 两次采集间无变更 |
| `collection_job` 行数 | 2 | 每次一个 job |
| 时间维度范围 | 覆盖合理范围 | 无意外断档 |
| 值域范围 | 在合理区间内 | 无异常值 |
| `record_hash` | 全部非空 | 幂等基础 |
| `source_url` | 全部非空 | 指向实际来源 |

**红旗：**

- 缺少 `record_hash`：哈希计算逻辑有问题
- 值域异常（如比率 > 100% 或 < 0%）：可能是数据提取错误
- 记录中含有格式残留（如 HTML 标签、特殊字符）：解析逻辑需修复
- 时间维度有意外断档：可能未全量采集
- `record_history` > 0：数据在两次采集间发生了意外变更

### Phase 4 — 验收判定

**纳入 verified 的标准：**

- 四个 Phase 全部通过，零红旗
- 首次：`status = SUCCESS`，`inserted = parsed`，`warnings = 0`，`failed = 0`
- 二次：`status = SUCCESS`，`inserted = 0`，`updated = 0`，`unchanged = parsed`
- 数据库：正确的行数，合理的值域，非空 hashes 和 source_urls
- 数据量：合理范围（非异常小，非可疑大）

---

## Output template

```markdown
## <ENTITY_NAME> — 真实验收报告

### 1. 首次真实采集结果摘要
| 指标 | 值 |
|------|-----|
| Job ID | <JOB_ID> |
| Status | SUCCESS |
| 解析记录数 | <N> |
| Inserted | <N> |
| Failed / Warnings | 0 / 0 |
| 耗时 | <Xs> |

### 2. 第二次重复采集结果摘要
| 指标 | 值 |
|------|-----|
| Job ID | <JOB_ID> |
| Status | SUCCESS |
| Inserted | 0 |
| Unchanged | <N> (100%) |

### 3. 查库核验结论
| 表 | 全库行数 | <CODE> 行数 |
|-----|---------|------------|
| record_current | <TOTAL> | <N> |
| record_history | 0 | 0 |

- 覆盖 <M> 个时间周期
- 值域范围：<MIN> ~ <MAX>
- 所有 record_hash / source_url 非空

### 4. 是否建议纳入 verified
<YES/NO> + 理由

### 5. 本轮未改代码
仅执行验收脚本，未修改 src/ 下任何源代码。
```

---

## Domain-specific concerns

### 通用核验要点

所有数据领域都适用的核验项：

| 检查项 | 方法 |
|--------|------|
| 时间连续性 | 检查时间维度是否有意外断档 |
| 值域合理性 | 检查数值是否在合理范围内 |
| 格式正确性 | 检查是否有 HTML 残留、特殊字符 |
| 哈希完整性 | 所有记录的 `record_hash` 非空 |
| 来源可追溯 | 所有记录的 `source_url` 非空 |
| 去重正确性 | 二次采集 100% unchanged |

### 按数据载体类型的特殊核验

#### HTML 静态页面型

- 检查表格解析是否遗漏行列
- 检查分页是否全部遍历（如果适用）

#### API JSON 型

- 检查 API 响应的分页参数是否正确处理
- 检查 JSON 字段映射是否完整

#### PDF 报告型

- 跨年份 PDF 格式一致性（旧年份 PDF 布局可能不同）
- 数字间距问题（PDF 文本提取可能引入多余空格）
- 多行字段是否正确合并
- 表头是否被误识别为数据

---

## Execution notes

- 使用 `PYTHONPATH=src` 运行脚本
- 数据库为 PostgreSQL — 不要覆盖 `DATABASE_URL` 为 SQLite
- `CollectionExecutionService` 需要正确的 DI 装配（参考 `main.py`）
- 验收前确认冷却期已过
- 允许 60-120 秒的完整采集时间（取决于数据量和请求数）