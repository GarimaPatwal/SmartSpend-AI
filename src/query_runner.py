"""
query_runner.py — Executes a pre-validated SQL query against the demo
SQLite database and returns results as a pandas DataFrame.

IMPORTANT: Only call this AFTER sql_guard.validate_sql() has passed.
This module never validates SQL itself — that's sql_guard's job.
"""

import sqlite3
import pandas as pd
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "finance.db"


class QueryExecutionError(Exception):
    """Raised when a valid SQL query fails at runtime (e.g. type mismatch)."""


def run_query(sql: str) -> pd.DataFrame:
    """
    Executes a SELECT query and returns a DataFrame.
    Raises QueryExecutionError with a user-friendly message on failure.
    """
    if not DB_PATH.exists():
        raise QueryExecutionError(
            "Database not found. Please run `python src/db.py` first to seed it."
        )

    try:
        conn = sqlite3.connect(DB_PATH)
        df = pd.read_sql_query(sql, conn)
        conn.close()
    except Exception as e:
        raise QueryExecutionError(f"Query failed at runtime: {e}") from e

    if df.empty:
        # Not an error — just signal clearly so the UI can show a friendly message
        return df

    # Round any float columns to 2 decimal places for cleaner display
    float_cols = df.select_dtypes(include="float").columns
    df[float_cols] = df[float_cols].round(2)

    return df
