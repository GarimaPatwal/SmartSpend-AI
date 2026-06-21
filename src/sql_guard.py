"""
sql_guard.py — Safety layer for LLM-generated SQL.

Ensures any SQL the app executes is:
  1. SELECT-only (no INSERT/UPDATE/DELETE/DROP/ALTER/etc.)
  2. Restricted to the allowlisted tables (transactions, accounts, budget_rules)
  3. A single statement (no chained/stacked queries via semicolons)

This module does NOT execute SQL — it only validates. Execution happens
in app.py / a thin db-execution helper, only after validate_sql() passes.
"""

import re

ALLOWED_TABLES = {"transactions", "accounts", "budget_rules"}

BLOCKED_KEYWORDS = {
    "insert", "update", "delete", "drop", "alter", "create",
    "truncate", "replace", "attach", "detach", "pragma",
    "exec", "execute", "vacuum", "grant", "revoke",
}


class SQLValidationError(Exception):
    """Raised when generated SQL fails a safety check."""


def validate_sql(sql: str) -> str:
    """
    Validates a SQL string against safety rules.
    Returns the cleaned SQL (stripped, single statement) if valid.
    Raises SQLValidationError with a clear reason if invalid.
    """
    if not sql or not sql.strip():
        raise SQLValidationError("Empty SQL string.")

    cleaned = sql.strip().rstrip(";").strip()

    # Block multiple statements (basic stacked-query protection)
    if ";" in cleaned:
        raise SQLValidationError("Multiple SQL statements are not allowed.")

    # Must start with SELECT
    if not re.match(r"^\s*select\b", cleaned, re.IGNORECASE):
        raise SQLValidationError("Only SELECT statements are allowed.")

    # Block dangerous keywords anywhere in the query
    lowered = cleaned.lower()
    for kw in BLOCKED_KEYWORDS:
        if re.search(rf"\b{kw}\b", lowered):
            raise SQLValidationError(f"Disallowed keyword detected: '{kw}'.")

    # Extract table names referenced after FROM / JOIN and check allowlist
    referenced_tables = set(
        re.findall(r"\b(?:from|join)\s+([a-zA-Z_][a-zA-Z0-9_]*)", cleaned, re.IGNORECASE)
    )
    if not referenced_tables:
        raise SQLValidationError("Could not detect any table in FROM/JOIN clause.")

    disallowed = referenced_tables - ALLOWED_TABLES
    if disallowed:
        raise SQLValidationError(
            f"Query references non-allowlisted table(s): {', '.join(disallowed)}"
        )

    return cleaned


if __name__ == "__main__":
    # Quick manual tests
    tests = [
        "SELECT category, SUM(amount) FROM transactions GROUP BY category",
        "SELECT * FROM transactions; DROP TABLE transactions;",
        "DELETE FROM transactions WHERE amount > 100",
        "SELECT * FROM users",
        "select t.category, b.monthly_budget from transactions t join budget_rules b on t.category = b.category",
    ]
    for t in tests:
        try:
            print("OK  :", validate_sql(t))
        except SQLValidationError as e:
            print("FAIL:", e, "|", t)
