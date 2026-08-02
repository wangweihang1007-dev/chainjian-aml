# Explainability Layer

`explainability/` 提供不依赖 LLM 的三类能力：

- `EvidenceBuilder`：从 APP `alert_case`/`alert_evidence`、Neo4j `TRANSFER`、DWD 交易明细和 DWS 账户画像构建统一证据链。
- `RiskExplainer`：根据证据链生成风险原因、支持交易 ID、资金路径和置信度。
- `ScoreExplainer`：使用 `app.risk_score.RULE_WEIGHTS` 拆解规则、图谱、交易行为和账户画像贡献，并归一到 APP 保存的风险分数。

接口：

```text
GET /alerts/{alert_id}/explainability
```

单 Agent 返回 `explainability` 字段，多 Agent Supervisor 返回 `explainability` 字段，报告中增加 Evidence chain 和 Score breakdown。前端 Alert Detail 页面展示证据卡片、路径、关键交易和评分表。

所有解释均由数据库和 Neo4j 查询结果生成；工具查询失败会保留任务失败状态，不会由模型补造账户、金额、交易或路径。
