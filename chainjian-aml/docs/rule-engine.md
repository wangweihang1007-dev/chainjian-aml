# AML Rule Engine v1

规则引擎以 Neo4j `TRANSFER` 关系和 SQLite DWS 风险特征为输入，并将标准化预警写入 APP 层。

## 当前规则集

`CycleRule` 从 Neo4j 使用 Cypher 查询账户与交易关系，然后在 Python 中检测满足以下条件的简单闭环：

- 至少 3 跳、最多 8 跳；
- 交易时间单调递增，总时窗不超过 96 小时；
- 中间账户不可重复；
- 相邻转账金额变化不超过 35%，以减少背景交易分支导致的假循环；
- 使用交易 ID 生成稳定告警 ID，重复运行不会重复写入。

循环预警风险分为 `80 + 跳数 × 1.5 + 对手方广度加分`，上限为 100，当前均归为高风险。

同时已启用以下首版检测：

- `StructuringRule`：24 小时内向至少三个不同账户发起多笔小额转账；
- `FanInRule`：48 小时内至少四个不同来源账户向同一账户归集资金；
- `MultiHopRule`：72 小时内金额连续、时间递增的四跳资金链路。

所有规则都设有时间窗、去重和结果上限，避免对图谱进行无界路径枚举。

标准输出为 `Alert`：`alert_id`、`account_id`、`risk_score`、`risk_level`、`rule_hits`、`evidence`、`created_time`、`status`。

Rule Engine 只输出标准化规则结果；APP Alert Layer 将其写入 `alert_case` 与 `alert_evidence`，以保持结构化查询和证据可追溯。评估标签不会被读取。
