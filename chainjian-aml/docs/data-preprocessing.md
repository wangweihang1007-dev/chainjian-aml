# IBM AML 原始数据预处理

预处理脚本位于 `backend/core/preprocess_ibm_aml.py`。它读取 IBM AML-Data HI-Small 原始文件，并生成项目标准数据集：

- `transactions.csv`：供规则引擎、图谱和 Agent 使用；不含洗钱标签；
- `accounts.csv`：交易涉及账户的标准化账户信息；
- `cases.csv`：用于展示的案例摘要；
- `labels.csv`：仅供离线 Precision、Recall 和 F1 评估，禁止进入推理链路；
- `manifest.json`：来源、参数、统计量与校验散列。

原始数据目录必须包含：`HI-Small_Trans.csv`、`HI-Small_accounts.csv` 与 `HI-Small_Patterns.txt`。

```powershell
python backend/core/preprocess_ibm_aml.py `
  --raw-dir D:\datasets\IBM-AML\HI-Small `
  --output-dir data
```

脚本默认拒绝覆盖已有输出。确认目标目录后，才可显式传入 `--overwrite`。
