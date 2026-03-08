## 金融投资助手（Financial Investment Agent）

一个面向真实场景的智能投资 Agent 系统，基于 LangChain 与大语言模型，支持通过自然语言完成市场信息查询、新闻检索、策略分析与回测等操作。项目以工程化落地为目标，强调清晰的分层架构、可扩展的 Tool 体系和接近企业级的安全与工程规范。

---

## 功能特性

- **对话式智能投资助手**：
  - 基于 LangChain 的 ReAct + OpenAI Function Calling Agent。
  - 支持多轮对话，利用会话内存理解上下文。
  - 通过 Tool 调用完成行情查询、新闻检索、策略分析等任务。

- **行情与 K 线数据服务**：
  - 支持虚拟货币交易对 OHLCV K 线查询（如 `BTC/USDT` 等）。
  - 支持 A 股股票日线 K 线查询，内部自动处理股票名称与代码映射。
  - 数据以结构化 JSON 格式返回，便于进一步分析或绘图。

- **新闻抓取与查询**：
  - 独立的 `news_worker` 模块负责新闻采集与入库：
    - 使用 akshare 基于“股票中文名”进行新闻搜索，提升相关度。
    - 结合本地股票代码映射，将新闻入库时统一存为股票代码（symbol）。
    - 自动访问新闻详情页并解析 HTML 正文，尽可能获取完整内容。
  - `src/services/news_service.py` 提供从本地 SQLite 数据库按股票、时间范围等维度查询新闻的服务。
  - `src/tools/news_tool.py` 暴露 LangChain Tool 供 Agent 在对话中按需调用。

- **策略与回测工具（示例）**：
  - 提供基础的策略信息查询 Tool（如策略参数说明、常见技术指标等）。
  - 提供回测相关 Tool，支持在对话中触发回测逻辑（具体能力可按需要扩展）。

- **工程化与可扩展性**：
  - 清晰分层：Agent 层 / Tool 层 / 服务层 / 基础设施层。
  - `src/tools/registry.py` 提供 Tool 注册中心，自动发现并注册所有 Tool：
    - 新增 Tool 只需在 `src.tools` 下定义，无需修改 Agent 代码。
  - 使用本地 CSV 缓存股票代码-名称映射，减少对 akshare 的重复拉取。
  - 配置与代码解耦，通过 `.env` 和 `configs/*.yaml` 管理环境和业务参数。

---

## 系统架构

整体上采用“Agent + Tool + 服务 + Infra”的分层架构，示意如下：

```text
UI / API 层
  - CLI 对话交互
  - 后续可扩展 FastAPI / Web 前端

Agent 层（src/agents）
  - ReAct + Function Calling Agent
  - 会话级内存管理（短期记忆）
  - System Prompt 约束与工具调度

Tool 层（src/tools）
  - 新闻查询 Tool
  - 行情 / K 线查询 Tool（加密货币 / A 股）
  - 策略信息与回测 Tool
  - 统一通过注册中心自动加载

服务层（src/services）
  - `news_service`：从本地新闻数据库按 symbol / 时间范围 / 条数查询新闻
  - `market_data_service`：封装加密货币与股票 K 线查询，提供统一 JSON 输出

基础设施层（src/infra）
  - HTTP 客户端封装（统一重试、超时与错误处理）
  - 行情数据获取（加密货币 / A 股日线）
  - 股票代码-名称映射与本地缓存
  - 数据库访问（当前主要是 SQLite 新闻库）
```

---

## 目录结构

（略去虚拟环境与编译产物，仅保留核心目录）

```text
.
├── configs/                 # 全局配置（风险、LLM 等）
├── data/
│   └── news/               # 新闻 SQLite 数据库等
├── news_worker/             # 新闻采集与入库 Worker
│   ├── collector.py         # 调用 akshare + HTML 解析抓取新闻
│   ├── processor.py         # 新闻清洗与去重
│   ├── repository.py        # 新闻库初始化与写入
│   ├── scheduler.py         # 简单调度器，周期执行采集任务
│   ├── sentiment.py         # 情感分析相关逻辑（可按需扩展）
│   ├── config.yaml          # 新闻采集配置（股票关键词、频率等）
│   └── run.py               # Worker 启动入口
├── src/
│   ├── agents/              # Agent 构建、Prompt 与会话内存
│   ├── api/                 # API 层（如 FastAPI），按需扩展
│   ├── common/              # 配置加载、日志等通用工具
│   ├── data/                # 本地数据（如股票元数据 CSV 等）
│   ├── infra/               # HTTP、行情、股票映射等基础设施
│   ├── services/            # 领域服务：新闻查询、行情查询等
│   ├── tools/               # LangChain Tool 实现与注册中心
│   └── main.py              # 应用启动入口（日志验证）
├── scripts/                 # 开发与运维辅助脚本
├── requirements.txt
└── README.md
```

---

## 核心模块说明

### Agent 与工具体系（`src/agents` 与 `src/tools`）

- **Agent 主入口**：
  - `src/agents/agent_executor.py` 提供 `run_query` 和 `create_agent_executor`：
    - 使用 `ChatOpenAI` 构建 LLM 客户端（支持 OpenAI / 阿里云百炼等 OpenAI 兼容接口）。
    - 采用 ReAct + Tools 模式，根据工具 schema 与 System Prompt 自动决定是否调用 Tool。
    - 内置简单的会话级内存，支持多轮对话上下文。

- **Tool 注册中心**：
  - `src/tools/registry.py` 自动遍历 `src.tools` 包，收集所有 `BaseTool` 实例到 `ALL_TOOLS`。
  - Agent 构建时直接 `tools = list(ALL_TOOLS.values())`，无需手动维护工具列表。

- **已实现的主要 Tool（示例）**：
  - `news_tool.py`：
    - Tool 名称类似 `query_stock_news`，基于 Pydantic 输入模型校验参数。
    - 调用 `news_service.fetch_news`，按股票名称/代码、时间范围、最大条数返回新闻列表。
  - `crypto_kline_tool.py`：
    - 按交易对（如 `BTC/USDT`）、时间尺度和时间范围返回加密货币 OHLCV 数据。
  - `stock_kline_tool.py`：
    - 支持按“股票名或代码 + 时间范围”查询 A 股日线 K 线。
    - 内部使用股票映射自动解析名称为代码，调用 A 股行情 Infra。
  - 其他策略 / 回测相关 Tool：
    - 用于查询策略信息或触发回测流程，作为完整 Agent 能力的一部分样例。

### 长期记忆（摘要 & 用户画像）

- **位置与作用**：
  - 位于 `src/agents/memory` 包中，提供 `MemoryManager` 统一管理长期记忆。
  - 当前实现两类长期记忆：Summary Memory（摘要记忆）和 User Profile（用户画像）。
- **存储文件**：
  - 摘要：`data/memory/summary.txt`
  - 用户画像：`data/memory/user_profile.json`
- **更新策略**：
  - 默认每累计约 10 轮对话（约 20 条消息）触发一次摘要和用户画像更新，以降低 LLM 调用开销。
- **重置长期记忆**：
  - 手动删除 `data/memory/summary.txt` 和 `data/memory/user_profile.json` 即可清空长期记忆。
  - 下次对话时，系统会自动重新创建这些文件。

### 新闻 Worker（`news_worker`）

- **采集逻辑（`collector.py`）**：
  - 输入配置中的“股票关键词”（推荐使用中文股票名）。
  - 使用股票名通过 akshare 拉取新闻列表。
  - 使用股票名-代码映射模块，将入库时的 `symbol` 统一为 6 位股票代码。
  - 对部分内容不完整的新闻，自动访问详情页并解析 HTML，提取正文文本。

- **处理与存储**：
  - `processor.py`：负责去重、基础清洗与字段标准化。
  - `repository.py`：负责新闻 SQLite 数据库的初始化与批量插入。
  - `scheduler.py`：提供简单的轮询调度能力，支持按固定时间间隔反复采集。
  - `config.yaml`：配置采集的股票关键词、单次最大条数、采集间隔等。

- **运行方式**：
  - 在项目根目录执行：

    ```bash
    python -m news_worker.run
    ```

  - Worker 启动后会：
    - 初始化新闻数据库；
    - 读取配置文件中的股票关键词与频率；
    - 立即执行一次采集，并按配置频率持续运行。

### 行情与 K 线服务（`src/infra` 与 `src/services/market_data_service.py`）

- **基础设施层（`src/infra/data` 等）**：
  - 提供加密货币行情获取函数（OHLCV）。
  - 提供 A 股日线行情获取函数，支持按股票代码、日期区间拉取数据。
  - `stock_mapping.py` 使用 akshare 获取 A 股代码-名称表，并支持：
    - 代码 → 名称；
    - 名称 → 代码（精确 / 模糊）；
    - 关键字解析为最佳匹配代码。
  - 加入本地 CSV 缓存（例如 `data/stock_meta/a_stock_code_name.csv`），减少拉取开销。

- **服务层（`market_data_service.py`）**：
  - 封装统一的 K 线查询接口，返回列表形式的 JSON 对象：
    - `get_crypto_ohlcv(symbol, timeframe, start_time, end_time, limit)`
    - `get_stock_ohlcv(symbol_or_name, timeframe, start_date, end_date, limit)`
  - 对于 A 股，支持先输入中文股票名，内部通过映射确定具体代码。

### 新闻查询服务（`src/services/news_service.py`）

- 直接基于本地 SQLite 数据库实现新闻查询逻辑，与 `news_worker` 模块解耦：
  - 根据 symbol 与可选时间范围读取新闻记录。
  - 提供友好的返回模型（包括标题、内容、发布时间、来源、URL、情感分析结果等）。
  - 提供统一的 `fetch_news` 接口供 Tool 层调用。

---

## 快速开始

### 1. 环境准备

- **Python 版本**：推荐 Python 3.10 及以上。
- **克隆仓库**：

  ```bash
  git clone <your-repo-url>.git
  cd Investment_Agent
  ```

- **创建并激活虚拟环境（Windows 示例）**：

  ```bash
  python -m venv invesAgentVenv
  .\invesAgentVenv\Scripts\activate
  ```

- **安装依赖**：

  ```bash
  pip install -r requirements.txt
  ```

- **配置环境变量**：
  - 将 `.env.example` 复制为 `.env`，并根据实际情况填入：
    - `OPENAI_API_KEY` 或 `BAILIAN_API_KEY`（阿里云百炼）
    - 其他与 LLM、日志等级等相关的配置。

### 2. 启动 Agent 对话（CLI 示例）

- 在项目根目录执行：

  ```bash
  python -m src.agents.agent_executor
  ```

- 终端中会出现提示，输入自然语言问题即可与 Agent 交互，如：
  - “帮我看一下最近一周贵州茅台的股价走势。”
  - “查询最近三天关于浦发银行的新闻，并给出简要总结。”

### 3. 启动新闻采集 Worker

- 配置采集参数：编辑 `news_worker/config.yaml`，例如：

  ```yaml
  news:
    per_symbol_limit: 50
    fetch_interval_seconds: 600
    symbols:
      - "浦发银行"   # 例如 600000
      - "贵州茅台"   # 例如 600519
  ```

- 在项目根目录执行：

  ```bash
  python -m news_worker.run
  ```

- Worker 会按配置定期抓取新闻并写入本地 SQLite 数据库，供 Agent 查询使用。

---

## 开发与扩展指南

### 新增一个 Tool

1. 在 `src/tools` 下新建文件，例如 `my_new_tool.py`。
2. 使用 Pydantic 定义输入模型，并实现一个返回 JSON 的函数。
3. 使用 LangChain 的 `StructuredTool.from_function` 封装为 Tool 实例。
4. 确保模块级变量（如 `my_new_tool = StructuredTool(...)`）存在即可。
5. 不需要修改 Agent 构建代码，注册中心会自动发现并加载这个 Tool。

### 扩展服务层

- 将具体业务能力（如新的行情源、风险控制逻辑、组合分析等）封装在 `src/services` 中：
  - 对外暴露干净的 Python 函数接口；
  - 内部调用 `src/infra` 中的基础设施（HTTP、数据库、数据源等）。
- Tool 层只负责：
  - 参数校验（Pydantic）；
  - 调用对应服务函数；
  - 对结果进行适度整理与描述，返回结构化 JSON。

---

## 未来规划

- **更完善的交易执行与风险控制**：
  - 区分模拟盘与实盘环境，完善权限与确认机制。
- **多 Agent 协同**：
  - 区分分析型 Agent、执行型 Agent 与风控 Agent，支持协作工作流。
- **策略管理与评估**：
  - 策略版本管理、回测结果存档与可视化展示。
- **部署与运维**：
  - 容器化（Docker）、自动化部署（CI/CD）、监控与告警。

本项目定位为一个“工程化的智能投资系统原型”，既可作为个人量化/投资助手，也可以作为在企业环境中落地 LLM + Agent 系统的参考实现基础。