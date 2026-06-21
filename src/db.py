"""
db.py — Creates and seeds the demo SQLite database for SmartSpend AI.

Tables:
  - accounts      : account_id, account_name, account_type
  - transactions  : txn_id, date, amount, category, merchant, account_id
  - budget_rules  : category, monthly_budget

Run directly to (re)build the demo database:
    python src/db.py
"""

import sqlite3
import random
from datetime import date, timedelta
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "finance.db"

CATEGORIES = [
    "Groceries", "Dining", "Transport", "Entertainment",
    "Utilities", "Shopping", "Health", "Travel", "Subscriptions", "Rent",
]

MERCHANTS_BY_CATEGORY = {
    "Groceries": ["Carrefour", "Spinneys", "Lulu Hypermarket"],
    "Dining": ["Zaatar w Zeit", "Starbucks", "Local Cafe"],
    "Transport": ["RTA Metro", "Careem", "Uber"],
    "Entertainment": ["VOX Cinemas", "Spotify", "PlayStation Store"],
    "Utilities": ["DEWA", "Du Telecom", "Etisalat"],
    "Shopping": ["Amazon.ae", "Noon", "IKEA"],
    "Health": ["Aster Pharmacy", "Medcare Clinic"],
    "Travel": ["Emirates", "Booking.com"],
    "Subscriptions": ["Netflix", "Apple iCloud", "Gym Membership"],
    "Rent": ["Property Management Co."],
}

MONTHLY_BUDGETS = {
    "Groceries": 1200,
    "Dining": 600,
    "Transport": 400,
    "Entertainment": 300,
    "Utilities": 700,
    "Shopping": 500,
    "Health": 300,
    "Travel": 800,
    "Subscriptions": 150,
    "Rent": 4000,
}

SCHEMA = """
CREATE TABLE IF NOT EXISTS accounts (
    account_id   INTEGER PRIMARY KEY,
    account_name TEXT NOT NULL,
    account_type TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS transactions (
    txn_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    date        TEXT NOT NULL,
    amount      REAL NOT NULL,
    category    TEXT NOT NULL,
    merchant    TEXT NOT NULL,
    account_id  INTEGER NOT NULL,
    FOREIGN KEY (account_id) REFERENCES accounts(account_id)
);

CREATE TABLE IF NOT EXISTS budget_rules (
    category        TEXT PRIMARY KEY,
    monthly_budget  REAL NOT NULL
);
"""


def build_database(num_transactions: int = 250, seed: int = 42) -> None:
    random.seed(seed)
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # Fresh start each run
    cur.executescript("""
        DROP TABLE IF EXISTS transactions;
        DROP TABLE IF EXISTS budget_rules;
        DROP TABLE IF EXISTS accounts;
    """)
    cur.executescript(SCHEMA)

    # Seed accounts
    accounts = [
        (1, "Main Checking", "checking"),
        (2, "Rewards Credit Card", "credit_card"),
        (3, "Savings", "savings"),
    ]
    cur.executemany(
        "INSERT INTO accounts (account_id, account_name, account_type) VALUES (?, ?, ?)",
        accounts,
    )

    # Seed budget rules
    cur.executemany(
        "INSERT INTO budget_rules (category, monthly_budget) VALUES (?, ?)",
        list(MONTHLY_BUDGETS.items()),
    )

    # Seed transactions across the last 90 days
    today = date.today()
    rows = []
    for _ in range(num_transactions):
        category = random.choice(CATEGORIES)
        merchant = random.choice(MERCHANTS_BY_CATEGORY[category])
        txn_date = today - timedelta(days=random.randint(0, 90))
        amount = round(random.uniform(15, 450), 2)
        account_id = random.choice([1, 2])
        rows.append((txn_date.isoformat(), amount, category, merchant, account_id))

    cur.executemany(
        "INSERT INTO transactions (date, amount, category, merchant, account_id) "
        "VALUES (?, ?, ?, ?, ?)",
        rows,
    )

    conn.commit()
    conn.close()
    print(f"Database built at {DB_PATH} with {num_transactions} transactions.")


def get_schema_description() -> str:
    """Returns a human-readable schema string to feed the LLM as context."""
    return """
TABLES:

transactions(txn_id INTEGER, date TEXT [YYYY-MM-DD], amount REAL, category TEXT,
             merchant TEXT, account_id INTEGER)
accounts(account_id INTEGER, account_name TEXT, account_type TEXT)
budget_rules(category TEXT, monthly_budget REAL)

Allowed categories: Groceries, Dining, Transport, Entertainment, Utilities,
Shopping, Health, Travel, Subscriptions, Rent
""".strip()


if __name__ == "__main__":
    build_database()

    # Quick sanity check
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM transactions")
    print("transactions rows:", cur.fetchone()[0])
    cur.execute("SELECT COUNT(*) FROM budget_rules")
    print("budget_rules rows:", cur.fetchone()[0])
    conn.close()
