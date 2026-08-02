# 实时仿真交易生成

项目提供 `data/generators/realtime_generator.py` 作为本地演示用实时交易流。它读取现有账户主数据，持续追加与项目交易表兼容的 CSV 记录，输出到 `data/realtime/transactions.csv`，不会修改 IBM 原始数据或清洗结果。

启动：

```powershell
python data/generators/realtime_generator.py --interval-seconds 5 --batch-size 20
```

参数：

- `--interval-seconds`：批次间隔，默认 5 秒
- `--batch-size`：普通交易批次大小，默认 20
- `--max-batches`：批次数，`0` 表示持续运行
- `--output`：输出 CSV 路径

每 5 个批次会加入循环交易、资金归集和拆分转账模式，便于规则引擎演示。当前生成器是独立数据流；如需写入 DWD、Neo4j 并自动触发预警，还需要增加消费端同步任务。

## 启动完整实时链路

先确保 Neo4j 已启动并在 `.env` 设置 `NEO4J_PASSWORD`，然后分别启动：

```powershell
python data/generators/realtime_generator.py --interval-seconds 5 --batch-size 20
python backend/core/realtime_pipeline.py --interval-seconds 5
```

同步任务会幂等写入 DWD 和 Neo4j，失败时记录 `data/realtime/pipeline.err` 并在下一轮重试。监控页面为 Streamlit 的 `monitoring` 页面，API 为 `GET /monitoring/metrics`。
