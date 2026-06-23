"""
nl_to_sql.py — Converts a natural-language finance question into a safe,
schema-aware SQL query using Groq's API (free tier, no card required,
works identically in local dev and after deployment).

Day 4 additions:
  - Response caching (identical questions skip the API entirely)
  - Exponential backoff retry for rate limit / transient API errors
  - Explicit dotenv path so it works when called from any directory
"""

import os
import time
import random
from pathlib import Path
from groq import Groq, RateLimitError
from dotenv import load_dotenv

from db import get_schema_description
from sql_guard import validate_sql, SQLValidationError
import cache as sql_cache

# Explicit path so .env is found regardless of working directory
load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent / ".env")

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

MODEL = "llama-3.1-8b-instant"

SYSTEM_PROMPT = """You are a SQL generator for a personal finance app.
You write ONLY valid SQLite SELECT statements.
Rules:
- Only use the tables and columns provided in the schema.
- Only SELECT statements. Never write INSERT, UPDATE, DELETE, DROP, or any DDL.
- Do not include explanations, markdown, or comments — output raw SQL only.
- Use SQLite-compatible syntax (e.g., date functions like strftime).
- When using JOINs, ALWAYS qualify ambiguous column names with their table name
  (e.g., use budget_rules.category instead of just category in GROUP BY and SELECT).
- Always use table aliases for clarity in JOINs (e.g., t for transactions, b for budget_rules).
"""


def generate_sql(question: str) -> str:
    """
    Sends the user's natural-language question + schema to Groq.
    Returns raw SQL text. Does NOT validate — that's generate_validated_sql's job.
    Implements exponential backoff for rate limit errors (up to 3 attempts).
    """
    schema = get_schema_description()
    user_prompt = f"""Schema:
{schema}

Question: "{question}"

Write a single SQLite SELECT query that answers this question."""

    max_attempts = 3
    for attempt in range(max_attempts):
        try:
            response = client.chat.completions.create(
                model=MODEL,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0,
            )
            raw_sql = response.choices[0].message.content.strip()
            raw_sql = raw_sql.replace("```sql", "").replace("```", "").strip()
            return raw_sql

        except RateLimitError:
            if attempt < max_attempts - 1:
                # Exponential backoff: 2s, 4s, 8s + small random jitter
                wait = (2 ** (attempt + 1)) + random.uniform(0, 1)
                print(f"Rate limit hit — retrying in {wait:.1f}s (attempt {attempt + 1}/{max_attempts})")
                time.sleep(wait)
            else:
                raise

        except Exception:
            raise

    raise RuntimeError("Failed to generate SQL after all retries.")


def generate_validated_sql(question: str, max_retries: int = 1) -> str:
    """
    1. Check cache first — if this exact question was answered before, return immediately.
    2. Generate SQL via Groq (with backoff retry on rate limits).
    3. Validate via sql_guard — retry once on failure, appending the error to context.
    4. Cache the valid SQL for future calls.
    """
    # Cache hit — skip the API entirely
    cached = sql_cache.get(question)
    if cached:
        return cached

    last_error = None
    current_question = question

    for attempt in range(max_retries + 1):
        sql = generate_sql(current_question)
        try:
            validated = validate_sql(sql)
            # Store in cache before returning
            sql_cache.set(question, validated)
            return validated
        except SQLValidationError as e:
            last_error = e
            current_question = (
                f"{question}\n\n(Note: previous attempt failed validation: {e}. "
                f"Only use allowed tables and SELECT-only syntax.)"
            )

    raise SQLValidationError(f"Failed after {max_retries + 1} attempts: {last_error}")


if __name__ == "__main__":
    test_question = "Which categories are over budget this month and by how much?"
    print(f"Question: {test_question}\n")
    try:
        sql = generate_validated_sql(test_question)
        print("Generated SQL:\n", sql)
        print("\nRunning again (should be instant from cache):")
        sql2 = generate_validated_sql(test_question)
        print("Cached SQL:\n", sql2)
    except Exception as e:
        print("Error:", e)
