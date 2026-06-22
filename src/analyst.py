"""
analyst.py — Takes a question + query results (as a markdown table) and
asks Groq to write a concise analyst-style plain-English summary, plus
3 suggested follow-up questions.

This is the second Groq call in the pipeline:
  1. nl_to_sql.py  → question → SQL
  2. analyst.py    → question + results → narrative + follow-ups
"""

import os
from groq import Groq
from dotenv import load_dotenv
import pandas as pd

load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))
MODEL = "llama-3.1-8b-instant"

SYSTEM_PROMPT = """You are a concise personal finance analyst.
Given a user's question and the data results, write:
1. A short plain-English summary (3-5 bullet points) of what the data shows.
2. Exactly 3 follow-up questions the user might want to ask next.

Format your response exactly like this:
SUMMARY:
- bullet 1
- bullet 2
- bullet 3

FOLLOW_UP:
1. follow-up question 1
2. follow-up question 2
3. follow-up question 3

Be specific — reference actual numbers and category names from the data.
Keep language simple, direct, and actionable.
"""


def generate_narrative(question: str, df: pd.DataFrame) -> dict:
    """
    Generates a plain-English analyst summary and follow-up questions.

    Returns a dict:
    {
        "summary": ["bullet 1", "bullet 2", ...],
        "follow_ups": ["q1", "q2", "q3"]
    }
    Falls back gracefully if the API call fails.
    """
    if df.empty:
        return {
            "summary": ["No data found for this query — try adjusting the date range or category filter."],
            "follow_ups": [
                "What are the total transactions this month?",
                "Which categories have the most transactions overall?",
                "What is the average transaction amount per category?",
            ],
        }

    # Convert results to markdown table for the prompt (cap at 20 rows to stay within token limits)
    table_md = df.head(20).to_markdown(index=False)

    user_prompt = f"""Question: "{question}"

Query results:
{table_md}

Write a plain-English analyst summary and 3 follow-up questions."""

    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.3,
        )
        raw = response.choices[0].message.content.strip()
        return _parse_response(raw)
    except Exception as e:
        # Graceful fallback — don't crash the app if narrative fails
        return {
            "summary": [f"Results returned {len(df)} rows. (Narrative unavailable: {e})"],
            "follow_ups": [],
        }


def _parse_response(raw: str) -> dict:
    """Parses the structured response into summary bullets and follow-up questions."""
    summary = []
    follow_ups = []
    section = None

    for line in raw.splitlines():
        line = line.strip()
        if line.startswith("SUMMARY:"):
            section = "summary"
        elif line.startswith("FOLLOW_UP:"):
            section = "follow_up"
        elif line.startswith("- ") and section == "summary":
            summary.append(line[2:])
        elif line and line[0].isdigit() and ". " in line and section == "follow_up":
            follow_ups.append(line.split(". ", 1)[1])

    # Fallback if parsing fails
    if not summary:
        summary = [raw[:300]]
    if not follow_ups:
        follow_ups = []

    return {"summary": summary, "follow_ups": follow_ups}
