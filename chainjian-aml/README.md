# 链鉴 AML

## React 审查工作台（推荐）

`web/` 是新的前后端分离前端，采用 React + Vite + Phosphor Icons，实现第三套「证据审查工作台」视觉方案。它与现有 FastAPI 接口兼容，Streamlit 页面保留用于回归演示。

```powershell
# 终端 1：启动 FastAPI
$env:NEO4J_PASSWORD="你的 Neo4j 密码"
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000

# 终端 2：启动 React
cd web
Copy-Item .env.example .env.local
npm install
npm run dev -- --host 0.0.0.0 --port 4173
```

浏览器访问 `http://127.0.0.1:4173`。前端默认通过 `VITE_API_URL=http://127.0.0.1:8000` 调用后端；后端不可用时会自动进入演示数据模式，并明确显示连接状态。

面向合规审核人员的、可解释的反洗钱智能审查演示系统。

## 技术栈

- Python + FastAPI：分析服务与接口；
- Pandas：数据导入、清洗和特征计算；
- NetworkX：交易图谱与资金路径查询；
- Streamlit：演示界面；
- SQLite：演示环境中的预警、审核与审计记录存储。

`data/labels.csv` 仅用于离线评估，禁止参与预警推理。详见 [PRD](docs/PRD.md)。

若需从 IBM AML 原始数据重新生成标准 CSV，请参阅 [数据预处理说明](docs/data-preprocessing.md)。

执行 `python backend/core/data_cleaning.py` 可生成可供应用读取的 `data/cleaned/` 数据集和[数据清洗报告](docs/data-cleaning-report.md)。

清洗后的数据可通过 SQLite 数据仓库存储业务数据，详见 [数据仓库说明](docs/data-warehouse.md)。

## Neo4j 图谱数据库

项目通过环境变量连接 Neo4j，示例见 [backend/.env.example](backend/.env.example)。默认数据库为 `money`；密码不得写入代码或提交到仓库。

图谱导入结果与模型说明见 [Neo4j 资金图谱](docs/neo4j-graph.md)。

AML 规则引擎 MVP 与预警持久化说明见 [规则引擎说明](docs/rule-engine.md)。

面向前端、人工审核和 Agent 的预警案件与接口见 [Alert Layer](docs/alert-layer.md)。

调查工具链与报告生成见 [AML Investigation Agent](docs/investigation-agent.md)。

人工审核闭环和离线规则评估见 [审核与评估说明](docs/review-and-evaluation.md)。

当前 Rule Engine 已包含循环交易、拆分转账、资金归集和四跳资金链路检测；所有规则结果均进入 APP 预警案件层。

## 运行界面

```powershell
cd backend
python -m pip install -r requirements.txt
streamlit run ../frontend/app.py
```

工作台包含仪表盘、预警中心、预警详情与 Agent 调查页。启动前请确保 Neo4j 已启动，并在当前终端设置 `NEO4J_PASSWORD`。

## 完整演示顺序

```powershell
# 1. 清洗与数仓（首次或重置数据时执行）
python backend/core/data_cleaning.py
python backend/core/warehouse.py --replace

# 2. 导入 Neo4j 图谱并生成预警
$env:NEO4J_PASSWORD = "<your-password>"
python graph/build_graph.py --data-dir data/cleaned
python rules/rule_engine.py --warehouse data/warehouse/aml.db

# 3. 启动 API 和工作台（二选一或同时启动）
uvicorn main:app --app-dir backend --reload
streamlit run frontend/app.py
```
# 前后端分离启动

FastAPI 后端和 Streamlit 前端现在通过 HTTP API 通信，前端不再直接连接 SQLite、Neo4j 或业务 Service。

```powershell
# 终端 1：后端
$env:NEO4J_PASSWORD="你的Neo4j密码"
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000

# 终端 2：前端
$env:AML_BACKEND_URL="http://127.0.0.1:8000"
python -m streamlit run frontend/app.py --server.port 8501
```

也可以在项目 `.env` 中配置 `AML_BACKEND_URL`。前端页面通过 `/alerts`、`/agent`、`/dashboard`、`/graph`、`/reviews` 等 FastAPI 接口获取数据。
