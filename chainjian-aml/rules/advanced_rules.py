"""Additional explainable AML behavior and topology rules."""

from __future__ import annotations

import hashlib
from collections import defaultdict
from datetime import timedelta
from pathlib import Path

from core.neo4j_client import run_read
from rules.cycle_rule import TRANSFER_QUERY, to_datetime
from rules.models import Alert, Evidence, RuleHit


def _rows() -> list[dict]:
    result = []
    for raw in run_read(TRANSFER_QUERY):
        row = dict(raw); row["event_time"] = to_datetime(row["timestamp"]); row["amount"] = float(row["amount_paid"] or 0)
        result.append(row)
    return result


def _alert(code: str, account: str, rows: list[dict], evidence_type: str, details: dict, score: float = 60.0) -> Alert:
    ids = sorted({str(row["transaction_id"]) for row in rows})
    fingerprint = hashlib.sha256(f"{code}|{account}|{'|'.join(ids)}".encode()).hexdigest()[:16]
    evidence = Evidence(evidence_type, ids, [account], details)
    return Alert(f"ALT-{code[:10]}-{fingerprint}", account, score, "medium", [RuleHit(code, 3, f"Detected {evidence_type} behavior with {len(ids)} transactions.")], [evidence], rows[0]["event_time"].isoformat())


class DormantActivationRule:
    code = "DORMANT_ACTIVATION"
    def __init__(self, warehouse_path: Path, dormant_days: int = 7, window_hours: int = 24, min_transactions: int = 5, max_alerts: int = 30) -> None:
        self.window, self.dormant, self.minimum, self.max_alerts = timedelta(hours=window_hours), timedelta(days=dormant_days), min_transactions, max_alerts
    def detect(self) -> list[Alert]:
        grouped = defaultdict(list)
        for row in _rows(): grouped[row["source_account_id"]].append(row)
        result = []
        for account, rows in grouped.items():
            rows.sort(key=lambda x: x["event_time"])
            for index, row in enumerate(rows):
                if index and row["event_time"] - rows[index - 1]["event_time"] >= self.dormant:
                    window = [x for x in rows[index:] if x["event_time"] - row["event_time"] <= self.window]
                    if len(window) >= self.minimum:
                        result.append(_alert(self.code, account, window, "dormant_account_activation", {"dormant_days": self.dormant.total_seconds() / 86400, "window_hours": self.window.total_seconds() / 3600}, 65)); break
            if len(result) >= self.max_alerts: break
        return result


class AccountHopRule:
    code = "ACCOUNT_HOPPING"
    def __init__(self, warehouse_path: Path, window_hours: int = 6, min_hops: int = 3, flow_ratio: float = 0.7, max_alerts: int = 30) -> None:
        self.window, self.minimum, self.ratio, self.max_alerts = timedelta(hours=window_hours), min_hops, flow_ratio, max_alerts
    def detect(self) -> list[Alert]:
        incoming, outgoing = defaultdict(list), defaultdict(list)
        for row in _rows(): incoming[row["target_account_id"]].append(row); outgoing[row["source_account_id"]].append(row)
        result = []
        for account, ins in incoming.items():
            outs = outgoing.get(account, []); pairs = []
            for incoming_row in ins:
                candidates = [x for x in outs if timedelta(0) <= x["event_time"] - incoming_row["event_time"] <= self.window and x["amount"] >= incoming_row["amount"] * self.ratio]
                if candidates: pairs.extend([incoming_row, min(candidates, key=lambda x: x["event_time"])])
            if len(pairs) >= self.minimum * 2:
                result.append(_alert(self.code, account, pairs, "account_hopping", {"window_hours": self.window.total_seconds() / 3600, "hop_count": len(pairs) // 2}, 68))
            if len(result) >= self.max_alerts: break
        return result


class CounterpartyBurstRule:
    code = "COUNTERPARTY_BURST"
    def __init__(self, warehouse_path: Path, window_hours: int = 24, min_counterparties: int = 8, max_alerts: int = 30) -> None:
        self.window, self.minimum, self.max_alerts = timedelta(hours=window_hours), min_counterparties, max_alerts
    def detect(self) -> list[Alert]:
        grouped = defaultdict(list)
        for row in _rows(): grouped[row["source_account_id"]].append(row)
        result = []
        for account, rows in grouped.items():
            rows.sort(key=lambda x: x["event_time"])
            for index, first in enumerate(rows):
                window = [x for x in rows[index:] if x["event_time"] - first["event_time"] <= self.window]
                if len({x["target_account_id"] for x in window}) >= self.minimum:
                    result.append(_alert(self.code, account, window, "counterparty_burst", {"window_hours": self.window.total_seconds() / 3600, "counterparty_count": len({x["target_account_id"] for x in window})}, 58)); break
            if len(result) >= self.max_alerts: break
        return result


class AmountPatternRule:
    code = "AMOUNT_PATTERN"
    def __init__(self, warehouse_path: Path, window_hours: int = 24, min_transactions: int = 5, min_similar: int = 4, tolerance: float = 0.02, max_alerts: int = 30) -> None:
        self.window, self.minimum, self.similar, self.tolerance, self.max_alerts = timedelta(hours=window_hours), min_transactions, min_similar, tolerance, max_alerts
    def detect(self) -> list[Alert]:
        grouped = defaultdict(list)
        for row in _rows(): grouped[row["source_account_id"]].append(row)
        result = []
        for account, rows in grouped.items():
            rows.sort(key=lambda x: x["event_time"])
            for index, first in enumerate(rows):
                window = [x for x in rows[index:] if x["event_time"] - first["event_time"] <= self.window]
                if len(window) < self.minimum: continue
                for anchor in window:
                    similar = [x for x in window if abs(x["amount"] - anchor["amount"]) / max(anchor["amount"], 1) <= self.tolerance]
                    if len(similar) >= self.similar:
                        result.append(_alert(self.code, account, similar, "repeated_amount_pattern", {"window_hours": self.window.total_seconds() / 3600, "similar_count": len(similar), "tolerance": self.tolerance}, 62)); break
                if result and result[-1].account_id == account: break
            if len(result) >= self.max_alerts: break
        return result


class InOutBalanceRule:
    code = "IN_OUT_BALANCE"
    def __init__(self, warehouse_path: Path, window_hours: int = 24, min_in: int = 3, ratio_low: float = 0.8, ratio_high: float = 1.2, max_alerts: int = 30) -> None:
        self.window, self.min_in, self.low, self.high, self.max_alerts = timedelta(hours=window_hours), min_in, ratio_low, ratio_high, max_alerts
    def detect(self) -> list[Alert]:
        incoming, outgoing = defaultdict(list), defaultdict(list)
        for row in _rows(): incoming[row["target_account_id"]].append(row); outgoing[row["source_account_id"]].append(row)
        result = []
        for account, ins in incoming.items():
            for first in ins:
                rows_in = [x for x in ins if timedelta(0) <= x["event_time"] - first["event_time"] <= self.window]; rows_out = [x for x in outgoing.get(account, []) if timedelta(0) <= x["event_time"] - first["event_time"] <= self.window]
                in_total, out_total = sum(x["amount"] for x in rows_in), sum(x["amount"] for x in rows_out)
                ratio = out_total / max(in_total, 1)
                if len(rows_in) >= self.min_in and len(rows_out) >= self.min_in and self.low <= ratio <= self.high:
                    result.append(_alert(self.code, account, rows_in + rows_out, "balanced_in_out_flow", {"window_hours": self.window.total_seconds() / 3600, "in_total": round(in_total, 2), "out_total": round(out_total, 2), "out_in_ratio": round(ratio, 4)}, 66)); break
            if len(result) >= self.max_alerts: break
        return result


class CrossBankBurstRule:
    code = "CROSS_BANK_BURST"
    def __init__(self, warehouse_path: Path, window_hours: int = 24, min_banks: int = 4, max_alerts: int = 30) -> None:
        self.window, self.minimum, self.max_alerts = timedelta(hours=window_hours), min_banks, max_alerts
    def detect(self) -> list[Alert]:
        grouped = defaultdict(list)
        for row in _rows(): grouped[row["source_account_id"]].append(row)
        result = []
        for account, rows in grouped.items():
            for first in rows:
                window = [x for x in rows if timedelta(0) <= x["event_time"] - first["event_time"] <= self.window]
                banks = {str(x["target_account_id"]).split("::", 1)[0] for x in window}
                if len(banks) >= self.minimum:
                    result.append(_alert(self.code, account, window, "cross_bank_burst", {"window_hours": self.window.total_seconds() / 3600, "bank_count": len(banks)}, 57)); break
            if len(result) >= self.max_alerts: break
        return result


class NonClosedReturnRule:
    code = "NON_CLOSED_RETURN"
    def __init__(self, warehouse_path: Path, window_hours: int = 168, min_hops: int = 3, max_hops: int = 5, max_alerts: int = 20) -> None:
        self.window, self.min_hops, self.max_hops, self.max_alerts = timedelta(hours=window_hours), min_hops, max_hops, max_alerts
    def detect(self) -> list[Alert]:
        rows = _rows(); adjacency = defaultdict(list)
        for row in rows: adjacency[row["source_account_id"]].append(row)
        result = []; seen = set()
        def walk(start, current, path, visited):
            if len(path) >= self.max_hops: return
            for edge in adjacency.get(current, []):
                if path and (edge["event_time"] < path[-1]["event_time"] or edge["event_time"] - path[0]["event_time"] > self.window): continue
                candidate = path + [edge]; target = edge["target_account_id"]
                if target == start and len(candidate) >= self.min_hops:
                    ids = tuple(sorted(x["transaction_id"] for x in candidate))
                    if ids not in seen: result.append(_alert(self.code, start, candidate, "non_closed_return", {"hop_count": len(candidate), "window_hours": self.window.total_seconds() / 3600}, 70)); seen.add(ids)
                elif target not in visited: walk(start, target, candidate, visited | {target})
                if len(result) >= self.max_alerts: return
        for start in sorted(adjacency):
            walk(start, start, [], {start})
            if len(result) >= self.max_alerts: break
        return result
