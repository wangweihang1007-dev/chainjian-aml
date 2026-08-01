# Neo4j 资金图谱导入

已将清洗后的 IBM AML 数据导入 Neo4j 的 `money` 数据库：

| 图元素 | 数量 |
| --- | ---: |
| `Account` 节点 | 3,157 |
| `TRANSFER` 关系 | 4,756 |

## 图模型

```text
(:Account {account_id, bank_id, account_number, ...})
  -[:TRANSFER {transaction_id, timestamp, amount_paid, payment_currency, ...}]->
(:Account)
```

- `Account.account_id` 使用 `bank_id::account_number` 作为唯一业务键；
- `TRANSFER.transaction_id` 对应原始交易 ID；
- 已创建账户唯一约束和交易关系 ID 索引；
- `labels.csv` 未导入图数据库，避免评估标签泄漏到规则、图谱或 Agent 推理。

重新导入命令：

```powershell
$env:NEO4J_PASSWORD = "<your-password>"
python graph/build_graph.py --data-dir data/cleaned
```
