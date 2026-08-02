import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from risk_profile.profile_service import AccountProfileService
from rules.rapid_movement_rule import RapidMovementRule


class RiskProfileRapidTest(unittest.TestCase):
    def test_profile_uses_dwd_and_dws_values(self):
        import sqlite3
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "profile.db"
            connection = sqlite3.connect(path)
            try:
                connection.executescript("""
                CREATE TABLE dwd_transaction_detail (transaction_id TEXT, transaction_time TEXT, from_account_id TEXT, to_account_id TEXT, amount_paid REAL, amount_received REAL);
                CREATE TABLE dws_account_risk_features (account_id TEXT, total_transaction_count INTEGER, outbound_amount REAL, inbound_amount REAL, counterparty_count INTEGER);
                CREATE TABLE dim_account (account_id TEXT, effective_batch_id INTEGER);
                INSERT INTO dwd_transaction_detail VALUES ('IN1','2026-01-01T00:00:00','B','A',10000,10000),('OUT1','2026-01-01T00:30:00','A','C',9000,9000);
                INSERT INTO dws_account_risk_features VALUES ('A',2,9000,10000,2);
                INSERT INTO dim_account VALUES ('A',1);
                """)
            finally:
                connection.close()
            profile = AccountProfileService(path).get("A")
            self.assertEqual(profile["txn_count"], 2)
            self.assertEqual(profile["counterparty_count"], 2)
            self.assertEqual(profile["average_holding_time_minutes"], 30.0)
            self.assertIn("资金快进快出", profile["risk_features"])

    @patch("rules.rapid_movement_rule.run_read")
    def test_rapid_movement_pairs_in_and_out(self, run_read):
        run_read.return_value = [
            {"source_account_id": "B", "target_account_id": "A", "transaction_id": "IN1", "timestamp": "2026-01-01T00:00:00", "amount_paid": 10000, "payment_currency": "USD"},
            {"source_account_id": "A", "target_account_id": "C", "transaction_id": "OUT1", "timestamp": "2026-01-01T00:15:00", "amount_paid": 9000, "payment_currency": "USD"},
        ]
        alerts = RapidMovementRule(Path("unused")).detect()
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0].rule_hits[0].rule_code, "RAPID_MOVEMENT")
        self.assertEqual(alerts[0].evidence[0].details["holding_time_minutes"], 15.0)


if __name__ == "__main__":
    unittest.main()
