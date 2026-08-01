# APP 风险预警层（Alert Layer）

Alert Layer 将 Rule Engine 的标准化规则结果转换为可展示、可审核、可调查的预警案件。

## 流程

```text
Neo4j + DWS 特征 → Rule Engine → 风险评分 → Alert Case → SQLite APP 层
```

风险评分按不同规则累加：循环交易 40、拆分交易 30、资金归集 25、多跳转移 20；`HIGH ≥ 80`、`MEDIUM ≥ 50`、其余为 `LOW`。

## 表

- `alert_case`：案件编号、账户、分数、等级、状态、命中规则；
- `alert_evidence`：资金路径、交易 ID、时间、金额等可追溯证据。

状态为 `PENDING`、`CONFIRMED` 或 `REJECTED`。相同账户、规则集合和交易证据会生成稳定指纹，重复生成不会创建重复案件。

## API

- `POST /alerts/generate`：执行 Rule Engine 并生成/更新预警；
- `GET /alerts`：查询全部预警；
- `GET /alerts/{alert_id}`：查询包含规则、交易证据和资金路径的预警详情。
