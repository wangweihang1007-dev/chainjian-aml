# 链鉴 AML 分层数据仓库

SQLite 数据仓库使用标准的 `ODS → DWD → DWS → ADS` 分层，数据库文件为 `data/warehouse/aml.db`。Neo4j 仅保存资金关系图。

| 层级 | 目的 | 核心表 |
| --- | --- | --- |
| ODS | 原始数据落地、导入可追溯 | `ods_import_batches`、`ods_accounts_raw`、`ods_transactions_raw`、`ods_cases_raw` |
| ODS 评估隔离区 | 保存真值标签，禁止推理使用 | `ods_evaluation_labels_raw` |
| DWD | 清洗、标准化的明细数据 | `dim_account`、`dwd_transaction_detail`、`dwd_case_detail` |
| DWS | 账户日汇总与风险特征 | `dws_account_daily`、`dws_account_risk_features` |
| ADS | 仪表盘和页面直接查询的数据集 | `ads_dashboard_summary`、`ads_account_activity_rank`、`ads_alert_dashboard` |
| APP | 可变的预警、证据、审核和报告业务记录 | `alert_case`、`alert_evidence`、`review_record`、`audit_log`、`app_reports` |

## 已生成数据

- ODS 原始交易：4,756 条；
- DWD 清洗交易：4,756 条；
- DWS 账户日汇总：4,465 条；
- DWS 账户风险特征：3,157 条；
- ADS 仪表盘快照：1 条；
- ADS 账户活跃度排名：3,157 条。

标签被保留在 `ods_evaluation_labels_raw`，且所有 DWD、DWS、ADS 构建 SQL 都不读取该表。

## 重建

```powershell
python backend/core/warehouse.py --replace
```

`--replace` 会重建本地 SQLite 数据仓库；不影响原始 CSV 或 Neo4j 图谱。
