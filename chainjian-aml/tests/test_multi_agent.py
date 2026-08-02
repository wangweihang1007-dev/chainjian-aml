import tempfile
import unittest
from pathlib import Path

from agents.supervisor_agent import SupervisorAgent
from agents.task_store import InvestigationTaskStore


class MultiAgentTest(unittest.TestCase):
    def test_supervisor_selects_specialists_by_rules(self):
        supervisor = SupervisorAgent(Path("does-not-need-to-exist.db"))
        plan = supervisor._task_plan(
            {"alert_id": "AL1", "account_id": "A", "risk_level": "MEDIUM", "rule_hits": ["RAPID_MOVEMENT"]},
            {"risk_features": []},
        )
        self.assertEqual([item["agent_name"] for item in plan], ["Rule Agent", "Transaction Agent", "Report Agent"])

    def test_task_store_records_lifecycle(self):
        with tempfile.TemporaryDirectory() as directory:
            store = InvestigationTaskStore(Path(directory) / "tasks.db")
            ids = store.initialize("AL1", [{"task_id": "rule", "agent_name": "Rule Agent", "task_type": "rule_analysis", "input": {"alert_id": "AL1"}}])
            self.assertEqual(store.list("AL1")[0]["status"], "WAITING")
            store.start(ids["rule"])
            store.finish(ids["rule"], "COMPLETED", {"rule_hits": ["RAPID_MOVEMENT"]})
            record = store.list("AL1")[0]
            self.assertEqual(record["status"], "COMPLETED")
            self.assertIn("RAPID_MOVEMENT", record["output_summary"])


if __name__ == "__main__":
    unittest.main()
