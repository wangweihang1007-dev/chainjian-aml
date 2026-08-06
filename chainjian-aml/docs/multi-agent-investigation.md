# AML Multi-Agent Investigation Framework

## 调查流程

`Supervisor Agent` 首先读取 Alert 和账户风险画像，再按命中规则动态选择专业 Agent。当前编排采用“并行专家层 → 证据裁判 → 有限补查 → 报告汇总”的 DAG 流程：

- `Rule Agent`：解释 Alert 中已落库的规则命中。
- `Graph Agent`：从 Neo4j 查询账户 1–3 跳资金路径和关联账户。
- `Transaction Agent`：读取 DWD 交易和 DWS/账户画像，检查快进快出、高频和大额行为。
- `Report Agent`：汇总上述真实查询结果，生成确定性调查报告。
- `Evidence Judge`：检查证据覆盖、任务失败、数据源降级和可回溯证据 ID，必要时触发一次补查。

Rule Agent 和 Report Agent 总是执行；只有命中循环、归集、多跳或高风险案件才执行 Graph Agent；命中快进快出或账户画像存在高频/快进快出/大额特征时才执行 Transaction Agent。

## 接口

```text
POST /agent/multi-investigate
{"user_input":"分析 AL000001"}

GET /agent/multi-investigate/AL000001/tasks
```

每个任务写入 SQLite 的 `investigation_task` 表，状态为 `WAITING`、`RUNNING`、`COMPLETED` 或 `FAILED`，前端 Agent 页面会展示 Agent、任务、状态、时间和输出摘要。专家任务并行执行，报告任务在专家任务和证据裁判完成后执行。

各 Agent 的输出会归一化为统一证据对象，包含来源、证据类型、交易/规则 ID、数据源、可信度和降级标志。报告只引用 Alert、DWD、DWS、Neo4j 和账户画像查询结果；任何工具失败都会在任务表中记录，不会用模型补造交易事实。

证据裁判最多触发一轮补查，避免 Agent 无限循环。若仍然证据不足，报告会明确标记 `NEEDS_MORE_EVIDENCE`，并建议人工补充材料。
