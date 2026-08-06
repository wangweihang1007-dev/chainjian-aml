"""Stage-one AML self-iteration: monitor, evaluate, diagnose, and propose."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from evaluation.evaluate_rules import evaluate_rules
from monitoring.service import collect_metrics, latest_snapshot


def _ratio(current: float | int | None, previous: float | int | None) -> float | None:
    if previous in (None, 0) or current is None:
        return None
    return round((float(current) - float(previous)) / abs(float(previous)), 4)


def _level_from_change(change: float | None, yellow: float, red: float) -> str:
    if change is None:
        return "INFO"
    magnitude = abs(change)
    return "RED" if magnitude >= red else ("YELLOW" if magnitude >= yellow else "GREEN")


def diagnose(
    current: dict[str, Any],
    previous: dict[str, Any] | None,
    evaluation: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Apply the SOP thresholds; this function never changes production rules."""
    signals: list[dict[str, Any]] = []
    if not previous:
        signals.append({"code": "BASELINE_NOT_AVAILABLE", "level": "INFO", "message": "首次运行，仅建立监控基线。"})
    else:
        data = current.get("data_quality", {})
        if data.get("missing_field_rate", 0) > 0:
            signals.append({"code": "MISSING_FIELDS", "level": "RED", "message": f"字段缺失率为 {data['missing_field_rate']:.2%}。"})
        if data.get("duplicate_transaction_count", 0) > 0:
            signals.append({"code": "DUPLICATE_TRANSACTIONS", "level": "RED", "message": f"发现 {data['duplicate_transaction_count']} 笔重复交易。"})

        current_dist = current.get("distribution", {})
        previous_dist = previous.get("distribution", {})
        for field, label in (("amount_p90", "金额 P90"), ("amount_p99", "金额 P99")):
            change = _ratio(current_dist.get(field), previous_dist.get(field))
            level = _level_from_change(change, 0.10, 0.30)
            if change is not None and level != "GREEN":
                signals.append({"code": f"{field.upper()}_DRIFT", "level": level, "change": change, "message": f"{label} 相对基线变化 {change:.2%}。"})

        current_rules = current.get("rules", {}).get("hit_counts", {})
        previous_rules = previous.get("rules", {}).get("hit_counts", {})
        for rule in sorted(set(current_rules) | set(previous_rules)):
            change = _ratio(current_rules.get(rule, 0), previous_rules.get(rule, 0))
            level = _level_from_change(change, 0.30, 1.00)
            if level != "GREEN":
                signals.append({"code": f"RULE_{rule}_DRIFT", "level": level, "change": change, "message": f"规则 {rule} 命中量发生变化。"})

        alert_change = _ratio(current.get("rules", {}).get("total_alert_cases"), previous.get("rules", {}).get("total_alert_cases"))
        level = _level_from_change(alert_change, 0.20, 0.50)
        if alert_change is not None and level != "GREEN":
            signals.append({"code": "ALERT_VOLUME_DRIFT", "level": level, "change": alert_change, "message": f"预警总量变化 {alert_change:.2%}。"})

        review = current.get("review", {})
        review_count = review.get("review_count", 0)
        if review_count:
            reject_rate = review.get("rejected_count", 0) / review_count
            confirm_rate = review.get("confirmed_count", 0) / review_count
            if reject_rate > 0.50:
                signals.append({"code": "REJECT_RATE", "level": "RED", "message": f"审核驳回率为 {reject_rate:.2%}。"})
            elif reject_rate > 0.30:
                signals.append({"code": "REJECT_RATE", "level": "YELLOW", "message": f"审核驳回率为 {reject_rate:.2%}。"})
            if confirm_rate < 0.25:
                signals.append({"code": "CONFIRM_RATE", "level": "RED", "message": f"审核确认率为 {confirm_rate:.2%}。"})
            elif confirm_rate < 0.40:
                signals.append({"code": "CONFIRM_RATE", "level": "YELLOW", "message": f"审核确认率为 {confirm_rate:.2%}。"})

    evaluation = evaluation or {}
    if evaluation.get("warning"):
        signals.append({"code": "OFFLINE_EVALUATION_UNAVAILABLE", "level": "RED", "message": evaluation["warning"]})
    else:
        f1 = evaluation.get("overall", {}).get("f1")
        if f1 is not None and f1 < 0.40:
            signals.append({"code": "OFFLINE_F1_LOW", "level": "RED", "change": f1, "message": f"离线评估 F1={f1:.3f}，低于 0.40。"})
        elif f1 is not None and f1 < 0.60:
            signals.append({"code": "OFFLINE_F1_LOW", "level": "YELLOW", "change": f1, "message": f"离线评估 F1={f1:.3f}，低于 0.60。"})
    return signals or [{"code": "ALL_GREEN", "level": "GREEN", "message": "当前指标未触发 SOP 黄线或红线。"}]


def _proposal_markdown(run_id: str, current: dict[str, Any], evaluation: dict[str, Any], signals: list[dict[str, Any]]) -> str:
    signal_lines = "\n".join(f"- [{item['level']}] {item['code']}: {item['message']}" for item in signals)
    overall = evaluation.get("overall", {})
    return f"""# AML 自迭代诊断提案

- 运行编号：{run_id}
- 生成时间：{current.get('snapshot_at', '')}
- 状态：待人工诊断与审批
- 自动发布：禁止

## 触发信号
{signal_lines}

## 离线评估
| 指标 | 当前值 |
|---|---:|
| Precision | {overall.get('precision', 'N/A')} |
| Recall | {overall.get('recall', 'N/A')} |
| F1 | {overall.get('f1', 'N/A')} |

## 人工处理建议
1. 核验数据批次、字段完整性、重复交易与分布变化。
2. 对异常规则至少抽样 10 条，区分数据变化与规则参数问题。
3. 规则、权重、风险等级或报告口径变更必须走独立分支、评审和回归测试。
4. 未通过离线评估、冒烟测试和人工审批，不得发布。

## 合规边界
- 标签数据仅用于离线评估，不进入规则、图谱或 Agent 推理路径。
- 本提案不自动改规则、不自动发布、不自动冻结账户或报送。
- 法律法规引用需由专业人员核验现行有效性。
"""


def run_cycle(database_path: Path, proposal_dir: Path, include_graph: bool = False) -> dict[str, Any]:
    previous = latest_snapshot(database_path)
    current = collect_metrics(database_path, include_graph=include_graph)
    evaluation = evaluate_rules(database_path)
    signals = diagnose(current, previous, evaluation)
    run_id = datetime.now(timezone.utc).strftime("IT-%Y%m%d-%H%M%S")
    proposal_dir.mkdir(parents=True, exist_ok=True)
    proposal_path = proposal_dir / f"{run_id}.md"
    proposal_path.write_text(_proposal_markdown(run_id, current, evaluation, signals), encoding="utf-8")
    result = {"run_id": run_id, "monitoring": current, "evaluation": evaluation, "signals": signals, "proposal_path": str(proposal_path)}
    (proposal_dir / f"{run_id}.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the ChainJian AML self-iteration diagnostic cycle.")
    parser.add_argument("--database", type=Path, default=None, help="兼容旧参数；数据库连接由 DATABASE_URL 配置")
    parser.add_argument("--proposal-dir", type=Path, default=Path("docs/operations/iteration-proposals"))
    parser.add_argument("--include-graph", action="store_true", help="探测 Neo4j；默认仅使用可用的仓库指标")
    args = parser.parse_args()
    from core.warehouse import DEFAULT_DATABASE
    result = run_cycle(args.database or DEFAULT_DATABASE, args.proposal_dir, args.include_graph)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
