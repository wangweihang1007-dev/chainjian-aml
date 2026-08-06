# 链鉴 AML 演示数据集说明

## 1. 数据集定位

项目当前使用 IBM AML-Data `HI-Small` 的合成数据子集，用于规则检测、资金图谱、风险排序、Agent 调查和报告演示。数据不对应真实银行客户或真实交易。

当前仓库内的演示数据文件为：

- `transactions.csv`：应用加载的交易表，不包含评估答案标签；
- `accounts.csv`：账户与实体元数据；
- `labels.csv`：离线评估标签；
- `cases.csv`：洗钱案例摘要和模式类型；
- `manifest.json`：生成参数、规模、时间范围、来源许可和 SHA-256 校验值。

## 2. 当前规模

以 `manifest.json` 为准：

| 指标 | 数量 |
|---|---:|
| 交易 | 4,756 |
| 洗钱交易 | 64 |
| 正常交易 | 4,692 |
| 账户 | 3,157 |
| 案例 | 6 |

包含的案例模式为：`CYCLE`、`FAN-OUT`、`FAN-IN`、`GATHER-SCATTER`、`SCATTER-GATHER` 和 `BIPARTITE`，每类一个案例。

## 3. 标签隔离

`labels.csv` 只允许离线评估模块读取，用于计算 Precision、Recall、F1 等指标。规则引擎、风险评分、图谱查询和 Agent 工具只能读取 `transactions.csv`、`accounts.csv` 及其清洗后的数仓数据。

## 4. 数据生成

项目内预处理脚本为：

```text
backend/core/preprocess_ibm_aml.py
```

该脚本需要外部准备 IBM AML-Data 原始文件。原始数据未随项目提交时，不能直接按本说明重新生成数据；应以仓库中现有 CSV 和 `manifest.json` 作为当前演示输入。

典型命令如下，从 `chainjian-aml` 目录执行：

```powershell
python backend/core/preprocess_ibm_aml.py `
  --raw-dir <原始数据目录> `
  --output-dir data/generated
```

具体参数以脚本的 `--help` 输出为准，不再依赖某一台电脑的 `D:\Desktop` 固定路径。

## 5. 项目内清洗

生成或替换输入数据后，可执行：

```powershell
python backend/core/data_cleaning.py
python backend/core/warehouse.py --replace
```

清洗结果默认写入 `data/cleaned/`，SQLite 数仓默认写入 `data/warehouse/aml.db`。

## 6. 来源与许可

数据来源： [IBM AML-Data Kaggle 页面](https://www.kaggle.com/datasets/ealtman2019/ibm-transactions-for-anti-money-laundering-aml)。

当前 `manifest.json` 记录的许可为 `Community Data License Agreement – Sharing – Version 1.0（CDLA-Sharing-1.0）`。正式发布或对外分发前，应按数据源页面和许可文本再次核验使用条件。
