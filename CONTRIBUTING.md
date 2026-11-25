# Contributing to PyCollector

感谢你对 PyCollector 的关注！无论是报告 Bug、提出改进建议、提交代码，还是完善文档，你的贡献都非常有价值。

---

## 行为准则

本项目遵循 [Contributor Covenant](https://www.contributor-covenant.org/version/2/1/code_of_conduct/) 行为准则。参与即表示你同意遵守其条款。

---

## 如何贡献

### 报告 Bug

1. 在 [Issues](https://github.com/pycollector/pycollector/issues) 中搜索，确认该 Bug 未被报告过。
2. 使用 **Bug Report** 模板创建 Issue。
3. 尽可能提供：
   - Python 版本和操作系统
   - 最小复现步骤
   - 期望行为 vs 实际行为
   - 相关日志或错误信息

### 提出新功能

1. 在 [Issues](https://github.com/pycollector/pycollector/issues) 中搜索，确认该功能未被提议过。
2. 使用 **Feature Request** 模板创建 Issue。
3. 说明：
   - 你希望解决什么问题
   - 建议的解决方案
   - 是否有替代方案

### 提交代码

1. **Fork** 本仓库。
2. 从 `master` 分支创建你的功能分支：
   ```bash
   git checkout -b feature/my-feature
   ```
3. 编写代码和测试。
4. 确保测试通过：
   ```bash
   pytest
   ```
5. 提交你的修改：
   ```bash
   git commit -m "feat: add my feature"
   ```
6. 推送到你的 Fork：
   ```bash
   git push origin feature/my-feature
   ```
7. 创建 **Pull Request**。

### 提交信息规范

本项目使用 [Conventional Commits](https://www.conventionalcommits.org/) 规范：

| 前缀 | 用途 |
|------|------|
| `feat:` | 新功能 |
| `fix:` | Bug 修复 |
| `docs:` | 文档变更 |
| `test:` | 测试相关 |
| `refactor:` | 重构（无功能变更） |
| `chore:` | 构建/工具链变更 |

---

## 开发环境搭建

```bash
# 克隆仓库
git clone https://github.com/pycollector/pycollector.git
cd pycollector

# 创建虚拟环境
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 安装开发依赖
pip install -e ".[dev]"

# 复制环境配置
cp .env.example .env

# 运行测试
pytest
```

---

## 代码风格

- 遵循 [PEP 8](https://peps.python.org/pep-0008/)
- 类型注解使用 Python 3.11+ 语法（`list[dict]` 而非 `List[Dict]`）
- 公共 API 使用 Google 风格的 docstring
- 最大行宽 100 字符

## 测试

- 新增功能必须包含测试
- Bug 修复应包含回归测试
- 使用项目自带的 `conftest.py` 夹具（内存 SQLite + TestClient）
- 运行 `pytest` 确保全部测试通过

## 项目结构

提交 PR 前，请确保你的代码遵循项目的分层架构：

```
src/pycollector/
├── core/        # 不依赖外部库的基础设施
├── db/          # 数据库层
├── domain/      # 纯领域逻辑，不依赖任何框架
├── api/         # FastAPI 路由
├── collector/   # 采集器框架
├── scheduler/   # 调度器
└── repository/  # 仓储层
```

- `domain/` 不 import 其他层
- `core/` 不 import 业务模块
- `collector/` 通过 Protocol 与业务解耦

---

## 许可

贡献的代码将采用与项目相同的 [MIT License](LICENSE)。