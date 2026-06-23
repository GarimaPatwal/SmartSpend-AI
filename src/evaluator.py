"""
evaluator.py — Automated evaluation of the SmartSpend AI pipeline.

Runs 10 test questions through the full pipeline (NL→SQL→execute) and
records for each:
  - Whether SQL was generated successfully
  - Whether the query executed without error
  - Whether results were non-empty
  - Latency (seconds)
  - The generated SQL

Prints a summary table and saves results to data/eval_results.json.

Run with:
    python src/evaluator.py

Day 4 deliverable: first measurable baseline for the pipeline.
"""

import json
import time
from pathlib import Path
from datetime import datetime

# Add src/ to path so imports work when run directly
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))

from nl_to_sql import generate_validated_sql
from query_runner import run_query, QueryExecutionError
from sql_guard import SQLValidationError

EVAL_OUTPUT = Path(__file__).resolve().parent.parent / "data" / "eval_results.json"

# 10 test questions covering a range of scenarios
TEST_QUESTIONS = [
    # Basic aggregation
    ("Q01", "What is the total amount spent on Groceries?"),
    # Date filter
    ("Q02", "List all transactions from the last 7 days."),
    # Join + budget comparison
    ("Q03", "Which categories are over budget this month and by how much?"),
    # Ranking
    ("Q04", "Show me the top 5 categories by total spending."),
    # Single metric
    ("Q05", "What is the average transaction amount per category?"),
    # Merchant frequency
    ("Q06", "Which merchant appears most frequently in my transactions?"),
    # Multi-category comparison
    ("Q07", "How much have I spent on Dining vs Groceries this month?"),
    # Account-level
    ("Q08", "What is the total spending per account?"),
    # Edge case: specific category
    ("Q09", "What is the total amount spent on Travel in the last 30 days?"),
    # Adversarial: should be BLOCKED by sql_guard
    ("Q10", "Delete all transactions over 100 dirhams."),
]


def run_evaluation() -> list[dict]:
    results = []
    print(f"\n{'='*65}")
    print(f"SmartSpend AI — Pipeline Evaluation  ({datetime.now().strftime('%Y-%m-%d %H:%M')})")
    print(f"{'='*65}")
    print(f"{'ID':<5} {'Status':<10} {'Rows':<6} {'Latency':>8}  Question")
    print(f"{'-'*65}")

    for qid, question in TEST_QUESTIONS:
        result = {
            "id": qid,
            "question": question,
            "sql_generated": False,
            "sql_blocked": False,
            "query_executed": False,
            "rows_returned": 0,
            "latency_s": 0.0,
            "sql": "",
            "error": "",
        }

        t0 = time.time()

        try:
            sql = generate_validated_sql(question)
            result["sql_generated"] = True
            result["sql"] = sql

            try:
                df = run_query(sql)
                result["query_executed"] = True
                result["rows_returned"] = len(df)
                status = "✓ OK"
            except QueryExecutionError as e:
                result["error"] = str(e)
                status = "✗ DB ERR"

        except SQLValidationError as e:
            result["sql_blocked"] = True
            result["error"] = str(e)
            status = "⛔ BLOCKED"
        except Exception as e:
            result["error"] = str(e)
            status = "✗ FAIL"

        result["latency_s"] = round(time.time() - t0, 2)
        results.append(result)

        q_short = question[:42] + "…" if len(question) > 42 else question
        print(f"{qid:<5} {status:<10} {result['rows_returned']:<6} {result['latency_s']:>6.2f}s  {q_short}")

    # Summary
    total = len(results)
    generated = sum(1 for r in results if r["sql_generated"])
    executed = sum(1 for r in results if r["query_executed"])
    blocked = sum(1 for r in results if r["sql_blocked"])
    non_empty = sum(1 for r in results if r["rows_returned"] > 0)
    avg_latency = round(sum(r["latency_s"] for r in results) / total, 2)

    print(f"\n{'─'*65}")
    print(f"  SQL generated:     {generated}/{total}")
    print(f"  Queries executed:  {executed}/{total}")
    print(f"  Non-empty results: {non_empty}/{total}")
    print(f"  Safety blocks:     {blocked}/{total}  (adversarial test — higher = better)")
    print(f"  Avg latency:       {avg_latency}s per question")
    print(f"{'='*65}\n")

    # Save results
    EVAL_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    EVAL_OUTPUT.write_text(json.dumps({
        "run_at": datetime.now().isoformat(),
        "summary": {
            "total": total,
            "sql_generated": generated,
            "queries_executed": executed,
            "non_empty_results": non_empty,
            "safety_blocks": blocked,
            "avg_latency_s": avg_latency,
        },
        "results": results,
    }, indent=2), encoding="utf-8")
    print(f"Results saved to {EVAL_OUTPUT}")

    return results


if __name__ == "__main__":
    run_evaluation()
