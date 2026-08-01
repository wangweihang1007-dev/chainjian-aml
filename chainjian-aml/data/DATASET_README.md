# IBM AML-Data 比赛演示数据集

本交付物从 IBM AML-Data 的 `HI-Small` 预生成数据中，抽取适合“链鉴 AML”演示的小型交易子集。它保留完整的洗钱案例交易，并加入相关账户的正常交易上下文和随机正常背景交易，适用于规则检测、资金图谱、风险排序、Agent 调查和报告生成。

## 目录

- 原始数据：`D:\Desktop\IBM-AML-Data\raw`
- 生成数据：`D:\Desktop\IBM-AML-Data\demo`
- 预处理脚本：`D:\Desktop\IBM-AML-Data\preprocess_ibm_aml_demo.py`

生成目录包含：

- `transactions.csv`：应用实际加载的交易表，不包含答案标签。
- `accounts.csv`：子集涉及的账户与实体元数据。
- `labels.csv`：离线评估标签，仅供 Precision、Recall、F1 等指标计算。
- `cases.csv`：所选完整洗钱案例的摘要及模式类型。
- `manifest.json`：参数、规模、时间范围、来源许可和 SHA-256 校验值。

## 默认抽样策略

默认保留六类适合图谱演示的模式，每类一个完整案例：

1. `CYCLE`：循环转账；
2. `FAN-OUT`：单点向多账户分散；
3. `FAN-IN`：多账户向单点归集；
4. `GATHER-SCATTER`：先归集再分散；
5. `SCATTER-GATHER`：先分散再归集；
6. `BIPARTITE`：两组账户之间的多对多转账。

脚本选择接近演示友好规模的中等案例，避免只有一两条边、无法呈现多跳结构的极小案例。对每个案例涉及的账户，脚本保留案例前后默认两天内的正常交易；最多保留 3,500 条关联上下文，并以蓄水池抽样补充 1,500 条正常背景交易。随机种子固定，因此结果可复现。

## 运行方式

```powershell
python D:\Desktop\IBM-AML-Data\preprocess_ibm_aml_demo.py `
  --raw-dir D:\Desktop\IBM-AML-Data\raw `
  --output-dir D:\Desktop\IBM-AML-Data\demo
```

如需扩大数据规模：

```powershell
python D:\Desktop\IBM-AML-Data\preprocess_ibm_aml_demo.py `
  --raw-dir D:\Desktop\IBM-AML-Data\raw `
  --output-dir D:\Desktop\IBM-AML-Data\demo-large `
  --cases-per-pattern 2 `
  --context-days 3 `
  --max-context-transactions 10000 `
  --background-transactions 5000
```

## 防止标签泄漏

`transactions.csv` 中没有 `Is Laundering` 字段。检测规则、风险评分、图谱查询和 Agent 工具只能读取 `transactions.csv` 与 `accounts.csv`。`labels.csv` 必须放在独立的评估模块中，并且只能在检测结果产生后读取。

## 数据来源与许可

数据来源为 IBM AML-Data 的 Kaggle 发布版本：

<https://www.kaggle.com/datasets/ealtman2019/ibm-transactions-for-anti-money-laundering-aml>

实际数据采用 `Community Data License Agreement – Sharing – Version 1.0（CDLA-Sharing-1.0）`。本数据完全为合成数据，不对应真实银行客户或真实交易。
