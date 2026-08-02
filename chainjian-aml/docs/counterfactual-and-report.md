# 反事实解释与调查报告优化

`counterfactual/` 只读取已有证据链和评分拆解，模拟移除关键交易或规则因子后的风险分数变化：

- `analyzer.py`：按 `alert_id` 收集证据并组织分析。
- `risk_simulator.py`：移除单个证据因素后重新计算分数，不写回 SQLite、Neo4j 或 Alert。
- `counterfactual_report.py`：生成报告第 5 节 Markdown。

接口：

```text
GET /alerts/{alert_id}/counterfactual
```

调查报告固定为七段：案件基本信息、风险结论、风险原因分析、证据链、反事实分析、人工审核建议、免责声明。单 Agent 和 Multi-Agent 都会返回 `counterfactual`，Alert Detail 页面提供在线查看和 Markdown 下载。
