# AML Investigation Agent

Agent 按固定工具链调查预警案件，所有报告事实均来自工具返回：

1. `get_alert_detail(alert_id)`：从 APP `alert_case` 和 `alert_evidence` 查询案件；
2. `get_transaction_path(account_id)`：从 Neo4j 查询 1–3 跳出向资金路径；
3. `get_transaction_evidence(alert_id)`：从 DWD 查询预警证据交易的金额、时间和账户；
4. `generate_report(data)`：仅使用以上结果生成结构化 Markdown 调查报告。

默认生成器是确定性模板，以保证不编造交易事实。若部署了经审批的 LLM，可通过 `InvestigationAgent(llm=...)` 注入调用器；它只会收到同一份受限工具数据和严格提示词。

## 输入示例

```python
from agent.agent import InvestigationAgent

result = InvestigationAgent().run("分析 AL000001")
print(result["report"])
```

## API

`POST /agent/investigate`

```json
{"user_input": "分析 AL000001"}
```

返回 Alert、路径、交易证据及调查报告。报告包含案件编号、风险信息、命中规则、账户、资金路径、交易证据、风险解释、人工核查事项与免责声明。
