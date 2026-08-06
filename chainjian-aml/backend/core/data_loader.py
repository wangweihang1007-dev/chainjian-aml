"""Data loading utilities for the AML warehouse and cleaned CSV fallback."""

from functools import lru_cache
from core.database import sqlite3

import pandas as pd

from .config import active_data_dir
from .warehouse import DEFAULT_DATABASE


@lru_cache(maxsize=1)
def load_demo_data() -> dict[str, pd.DataFrame]:
    """Load warehouse tables, with cleaned CSVs as a development fallback.

    Labels are evaluation-only and must not drive alerts, graph queries, or
    Agent responses.
    """
    try:
        with sqlite3.connect(DEFAULT_DATABASE) as connection:
            return {
                "accounts": pd.read_sql_query("SELECT * FROM dim_account", connection),
                "transactions": pd.read_sql_query("SELECT * FROM dwd_transaction_detail", connection),
                "labels": pd.read_sql_query("SELECT * FROM ods_evaluation_labels_raw", connection),
                "cases": pd.read_sql_query("SELECT * FROM dwd_case_detail", connection),
            }
    except Exception:
        # CSV fallback is retained only for a first-run developer environment;
        # production data is expected to be in PostgreSQL.
        pass
    data_dir = active_data_dir()
    return {
        "accounts": pd.read_csv(data_dir / "accounts.csv"),
        "transactions": pd.read_csv(data_dir / "transactions.csv"),
        "labels": pd.read_csv(data_dir / "labels.csv"),
        "cases": pd.read_csv(data_dir / "cases.csv"),
    }
