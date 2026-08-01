# 人工审核与规则评估

## 审核闭环

`ReviewService` 将审核记录写入 `review_record`，并在同一事务中写入 `audit_log`。操作如下：

- `CONFIRM`：`PENDING → CONFIRMED`；
- `REJECT`：`PENDING → REJECTED`；
- `NEED_MORE_INFO`：保持当前状态，仅记录补充调查要求。

接口：

- `POST /alerts/{alert_id}/review`
- `GET /alerts/{alert_id}/reviews`

## 离线评估

`evaluation/evaluate_rules.py` 始终先运行 Rule Engine 取得预测结果，再在独立代码路径读取 `ods_evaluation_labels_raw` 计算 Precision、Recall 和 F1。标签不传入规则、Neo4j 查询或 Agent 工具。

当前循环、拆分、归集和多跳规则均可参与总体评估；规则级报告保留与标签模式可直接对齐的 Cycle、Fan-in、Fan-out 指标。

接口：`GET /evaluation/metrics`。
