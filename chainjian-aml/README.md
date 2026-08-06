# 链鉴 AML

面向反洗钱调查的证据链审查平台。

## 1. 项目定位

链鉴 AML 是一个基于合成交易数据的反洗钱调查辅助系统。系统把交易数据、规则命中、账户画像、资金关系、风险解释、反事实分析、Agent 调查、人工审核和审计记录连接成一条可追溯的调查链路。

系统只提供调查辅助，不替代合规人员作出洗钱认定，也不会自动冻结账户、拒绝交易或提交监管报告。

当前版本是华为黑客松演示版：

- 数据：IBM AML-Data `HI-Small` 的项目演示子集；
- 主前端：React + Vite，目录为 `web/`；
- 后端：FastAPI，入口为 `backend/main.py`；
- 本地持久化：SQLite，数据库为 `data/warehouse/aml.db`；
- 图谱：Neo4j 为可选服务，不可用时部分查询降级到 SQLite；
- 模型：通过 OpenAI Compatible 接口接入，当前代码支持 MiniMax 配置；
- Streamlit：保留为辅助验证和旧版页面，不是当前主演示入口。

## 2. 当前状态

| 能力 | 状态 | 说明 |
|---|---|---|
| 数据清洗与 SQLite 数仓 | 已实现 | 支持 ODS、DWD、DWS、ADS 分层 |
| 规则检测 | 已实现 | 循环、拆分、归集、快速转移等规则 |
| 风险评分与解释 | 已实现 | 提供分项贡献和反事实分析 |
| 证据链与预警案件 | 已实现 | 规则结果可转为案件和证据 |
| 资金图谱 | 已实现/依赖配置 | Neo4j 可用时查询图谱，否则使用 SQLite 事实表 |
| Agent 调查 | 已实现/依赖配置 | 无模型时使用确定性工具和模板；模型调用需配置 API |
| 调查报告 | 已实现 | 支持网页/Markdown 形式；正式 PDF 导出仍需完善 |
| 人工审核与审计 | 已实现 | 审核人和备注必填，写入审核记录与审计日志 |
| 材料审查 | 部分实现 | 支持上传、质量检查和交叉核验；真实视觉回归集未完成 |
| 实时交易链路 | 部分实现 | 有生成器和同步代码，尚未作为默认演示链路 |
| 昇腾环境部署 | 未在本地验证 | 属于比赛目标，需在目标环境单独验证 |

## 3. 演示路径

1. 打开 React 工作台，查看预警案件和风险等级；
2. 进入案件详情，查看关键交易、规则命中和证据链；
3. 查看评分解释，理解风险分的组成；
4. 查看反事实分析，观察移除某一因素后的分数变化；
5. 进入图谱调查，查看账户、交易和资金路径；
6. 使用 Agent 生成结构化调查结论；
7. 在人工审核区域确认、驳回或要求补充调查；
8. 导出或复制 Markdown 调查报告。

## 4. 技术结构

```text
chainjian-aml/
├─ backend/                 FastAPI 后端、数据处理和接口
├─ web/                     React + Vite 主前端
├─ frontend/                Streamlit 辅助页面
├─ rules/                   反洗钱规则和规则引擎
├─ app/                     预警、证据、审核、审计服务
├─ agent/                   单 Agent、工具和调查追踪
├─ agents/                  多 Agent 调查编排
├─ graph/                   图谱导入和查询
├─ graph_intelligence/      时序图谱、角色、传播和反事实分析
├─ explainability/          风险和证据解释
├─ counterfactual/          反事实模拟
├─ evaluation/              离线指标评估
├─ monitoring/              运行监控指标
├─ data/                    数据、清洗结果和本地数仓
├─ docs/                    产品、架构、规则和运维文档
└─ tests/                   Python 测试
```

## 5. 数据说明

项目随附的演示子集统计如下，完整口径以 [data/manifest.json](data/manifest.json) 为准：

| 指标 | 数量 |
|---|---:|
| 交易 | 4,756 |
| 账户 | 3,157 |
| 洗钱案例 | 6 |
| 标记为可疑的交易 | 64 |

当前 SQLite 运行库可能包含历史重建和规则运行结果，因此数据库中的 DWD 交易数、预警案件数会与原始演示子集不同。当前本地数据库曾记录 28,805 条 DWD 交易和 1,122 个预警案件，这些数字不能代替数据集 manifest 的规模说明。

标签边界：`labels.csv` 只用于离线评估，不得进入规则检测、风险评分、图谱查询或 Agent 工具。

数据来源、生成参数、许可和校验值见 [数据集说明](data/DATASET_README.md)。

## 6. 主要接口

| 能力 | 方法和路径 |
|---|---|
| 健康检查 | `GET /health` |
| 预警列表 | `GET /alerts` |
| 预警详情 | `GET /alerts/{alert_id}` |
| 评分解释 | `GET /alerts/{alert_id}/explainability` |
| 反事实分析 | `GET /alerts/{alert_id}/counterfactual` |
| 图谱智能分析 | `GET /alerts/{alert_id}/graph-intelligence` |
| 调查报告 | `GET /reports/{alert_id}` |
| 多 Agent 调查 | `POST /agent/multi-investigate` |
| Agent 任务 | `GET /agent/multi-investigate/{alert_id}/tasks` |
| 人工审核 | `POST /alerts/{alert_id}/review` |
| 待审核案件 | `GET /reviews/pending` |
| 监控指标 | `GET /monitoring/metrics` |
| 材料上传 | `POST /alerts/{alert_id}/materials` |

## 7. 本地启动

以下命令均从 `chainjian-aml` 目录执行。

### 7.1 安装后端依赖

```powershell
python -m pip install -r backend/requirements.txt
```

### 7.2 启动后端

```powershell
python -m uvicorn main:app --app-dir backend --host 127.0.0.1 --port 8000
```

检查：

```powershell
Invoke-WebRequest http://127.0.0.1:8000/health
```

### 7.3 启动 React 前端

```powershell
cd web
npm install
npm run dev -- --host 127.0.0.1 --port 4173
```

访问 `http://127.0.0.1:4173/`。

### 7.4 重建数据

```powershell
cd ..
python backend/core/data_cleaning.py
python backend/core/warehouse.py --replace
```

如需使用 Neo4j：

```powershell
$env:NEO4J_PASSWORD = "你的 Neo4j 密码"
python graph/build_graph.py --data-dir data/cleaned
```

### 7.5 配置模型

模型调用不是启动后端的必需条件。需要使用模型时，再配置项目实际读取的环境变量和模型服务地址；不要把 API Key、密码或登录密钥写入文档、代码或提交记录。

## 8. 验证状态

截至本 README 更新时，项目文档不能宣称“全量测试通过”。当前从项目目录执行：

```powershell
python -m pytest -q
```

测试尚未通过，主要问题包括：

- `risk_profile/profile_service.py` 当前存在缩进错误；
- 部分模块使用 `core`、`api` 等绝对导入，测试环境下无法完整解析；
- 因收集阶段失败，不能把旧的 `15 passed` 作为当前验证结果。

前端构建和接口冒烟也应在代码修复后重新执行，结果以最新命令输出为准。

## 9. 文档索引

- [产品需求文档](docs/PRD.md)
- [总体架构](docs/architecture/aml-overall-architecture.md)
- [系统技术设计文档](docs/architecture/链鉴AML_系统技术设计文档.md)
- [图谱智能分析方案](docs/architecture/链鉴AML_图谱智能分析方案.md)
- [规则引擎](docs/rule-engine.md)
- [图谱说明](docs/neo4j-graph.md)
- [调查 Agent](docs/investigation-agent.md)
- [多 Agent 调查](docs/multi-agent-investigation.md)
- [审核与评估](docs/review-and-evaluation.md)
- [上线监控指标](docs/operations/上线监控指标表.md)
- [自迭代 SOP](docs/operations/自迭代SOP.md)

## 10. 演示边界与后续工作

当前系统只适合合成数据上的技术演示和调查辅助，不代表生产级反洗钱系统，也不构成洗钱认定、法律意见或监管报送依据。

后续优先级：

1. 修复 Python 包路径和测试收集问题，恢复可重复验证；
2. 完成真实图片材料审查回归集；
3. 完善报告版本管理和真正的 PDF 文件导出；
4. 增加 Agent 任务批次隔离、取消和权限控制；
5. 统一 Neo4j 与 SQLite 的数据源状态展示；
6. 在昇腾目标环境完成模型部署和性能验证；
7. 建立 CI、前端交互测试和性能回归。

## 11. 核心创新点：证据约束的上下文工程

链鉴 AML 不把大模型直接放在风险判断链路中，而是通过上下文工程把案件相关事实组织成“最小必要上下文”，再交给 Agent 生成调查建议。上下文由规则命中、关键交易、时序资金路径、账户画像、反事实结果和调查状态共同构成，并经过证据优先级排序与质量校验。

核心创新包括：

- **动态上下文编排**：根据预警类型和调查阶段，自动选择当前任务需要的证据和工具结果；
- **上下文压缩**：优先保留直接命中证据和关键资金路径，减少无关交易与模型输入成本；
- **权限隔离**：按案件、角色和数据来源限制上下文可见范围，生产化时扩展到字段级和租户级权限；
- **结果校验**：证据质量门检查证据来源、证据 ID 和降级数据源，证据不足时补查或转人工；
- **全链路追溯**：关联工具调用、调查步骤、模型输出、人工审核和审计日志，支持调查过程回放。

当前演示版已实现证据子图裁剪、证据质量判断、调查步骤追踪、人工审核和审计留痕。上下文 Token 统计、细粒度权限和多租户隔离需在生产化阶段补充，并以实测指标为准。

## 12. 商业化路径

目标客户包括银行、支付机构、证券及保险机构的反洗钱、合规和内审团队。产品可按私有化部署、项目实施和持续服务收费：

- **私有化部署**：提供本地化数据接入、规则配置、图谱分析和模型适配；
- **项目实施**：按数据治理、规则迁移、知识库建设和上下文工程改造收取实施费用；
- **持续服务**：提供规则迭代、模型评测、案件复盘、审计报表和运维支持。

产品价值可用误报率、调查耗时、关键证据召回率、报告事实一致性和单案件处理成本衡量。系统定位为调查辅助工具，最终风险判断和监管报送仍由机构合规人员完成。
