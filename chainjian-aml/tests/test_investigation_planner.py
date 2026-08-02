import tempfile
import unittest
from pathlib import Path

from agent.investigation_planner import build_plan
from agent.investigation_trace import InvestigationTraceStore


class InvestigationPlannerTest(unittest.TestCase):
    def test_plan_is_rule_driven(self):
        alert = {"alert_id": "AL1", "account_id": "A", "risk_level": "MEDIUM", "rule_hits": ["RAPID_MOVEMENT"]}
        profile = {"risk_features": ["资金快进快出"], "txn_count": 2}
        names = [step.tool_name for step in build_plan(alert, profile)]
        self.assertIn("check_rapid_movement", names)
        self.assertNotIn("check_cycle_evidence", names)

    def test_trace_has_waiting_running_completed_states(self):
        with tempfile.TemporaryDirectory() as directory:
            store = InvestigationTraceStore(Path(directory) / "trace.db")
            ids = store.initialize("AL1", [{"step_id": "S1", "step_name": "One", "tool_name": "tool", "input": {}}])
            self.assertEqual(store.list("AL1")[0]["status"], "WAITING")
            store.start(ids["S1"])
            self.assertEqual(store.list("AL1")[0]["status"], "RUNNING")
            store.finish(ids["S1"], "COMPLETED", {"ok": True})
            self.assertEqual(store.list("AL1")[0]["status"], "COMPLETED")


if __name__ == "__main__":
    unittest.main()
