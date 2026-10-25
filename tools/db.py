import sqlite3
from contextlib import closing
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "paymind.db"

VALID_CATEGORIES = [
    "food",
    "fuel",
    "shopping",
    "dining",
    "groceries",
    "travel",
    "entertainment",
    "bills",
    "health",
    "other",
]

SCHEMA = """
CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    merchant TEXT NOT NULL,
    amount REAL NOT NULL,
    category TEXT NOT NULL,
    payment_method TEXT NOT NULL,
    payment_id TEXT NOT NULL,
    cashback_earned REAL DEFAULT 0.0,
    notes TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS user_cards (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    card_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    active BOOLEAN DEFAULT TRUE
);
"""


def _connect() -> sqlite3.Connection:
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with closing(_connect()) as connection, connection:
        connection.executescript(SCHEMA)


def insert_transaction(
    date: str,
    merchant: str,
    amount: float,
    category: str,
    payment_method: str,
    payment_id: str,
    cashback_earned: float = 0.0,
    notes: str = "",
) -> int:
    with closing(_connect()) as connection, connection:
        cursor = connection.execute(
            """INSERT INTO transactions
               (date, merchant, amount, category, payment_method, payment_id, cashback_earned, notes)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (date, merchant, amount, category, payment_method, payment_id, cashback_earned, notes),
        )
        return cursor.lastrowid


def get_transactions(
    start_date: str | None = None,
    end_date: str | None = None,
    category: str | None = None,
) -> list[dict]:
    """Return transactions between two ISO dates (inclusive), newest first."""
    query = "SELECT * FROM transactions WHERE 1 = 1"
    params: list = []
    if start_date:
        query += " AND date >= ?"
        params.append(start_date)
    if end_date:
        query += " AND date <= ?"
        params.append(end_date)
    if category:
        query += " AND category = ?"
        params.append(category)
    query += " ORDER BY date DESC, id DESC"
    with closing(_connect()) as connection:
        return [dict(row) for row in connection.execute(query, params).fetchall()]


def save_user_card(card_id: str, user_id: str) -> None:
    with closing(_connect()) as connection, connection:
        connection.execute(
            "INSERT INTO user_cards (card_id, user_id) VALUES (?, ?)", (card_id, user_id)
        )


def clear_user_cards(user_id: str) -> None:
    with closing(_connect()) as connection, connection:
        connection.execute("DELETE FROM user_cards WHERE user_id = ?", (user_id,))


def get_user_cards(user_id: str) -> list[str]:
    with closing(_connect()) as connection:
        rows = connection.execute(
            "SELECT card_id FROM user_cards WHERE user_id = ? AND active ORDER BY id", (user_id,)
        ).fetchall()
    return [row["card_id"] for row in rows]
