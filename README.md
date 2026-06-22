# SmartSpend AI — Personal Finance Analyst

Turns natural-language finance questions into safe, transparent SQL queries
against a demo SQLite database, then returns results as a chart plus a
plain-English analyst summary — with suggested follow-up questions.

## Problem
Beginner-to-intermediate analysts can understand analytics questions but
writing correct SQL (joins/aggregations) slows them down. Stakeholders need
plain-English insights, not raw tables. SmartSpend AI bridges that gap.

## How it works
1. User types a question (e.g. *"Which categories are over budget this month
   and by how much?"*).
2. The app generates a **SELECT-only** SQL query using an LLM, schema-aware
   and validated against an allowlist of tables.
3. The query runs against a demo SQLite finance database.
4. Results are shown as a chart + a short bullet-point analyst summary.
5. The app suggests relevant follow-up questions.

## Tech stack
- **Backend:** Python
- **LLM:** OpenAI (gpt-4o-mini for NL→SQL)
- **Database:** SQLite (`transactions`, `accounts`, `budget_rules`)
- **UI:** Streamlit
- **Charts:** Plotly

## Safety
- SQL must be `SELECT`-only — INSERT/UPDATE/DELETE/DROP/etc. are blocked.
- Only allowlisted tables (`transactions`, `accounts`, `budget_rules`) may be
  referenced.
- Single-statement only (no stacked queries).
- One retry if generated SQL fails validation.

## Setup

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env            # then add your OPENAI_API_KEY
python src/db.py                # builds & seeds the demo database
python src/nl_to_sql.py         # smoke test: one NL->SQL call
```

## Project structure
```
smartspend-ai/
├── src/
│   ├── db.py           # SQLite schema + seed data
│   ├── sql_guard.py    # SELECT-only validator + table allowlist
│   ├── nl_to_sql.py     # LLM-based NL -> SQL generation
│   └── app.py           # Streamlit UI (coming Day 3+)
├── data/
│   └── finance.db
├── requirements.txt
├── .env.example
└── README.md
```

## Status
Day 2 — environment set up, database seeded, SQL safety guard in place,
first LLM API call wired and tested.
