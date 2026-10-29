"""Run the queries in sqlanalysisqueries.sql against campaigns.sqlite."""

from __future__ import annotations

import sqlite3
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "campaigns.sqlite"
QUERIES_PATH = ROOT / "sqlanalysisqueries.sql"


def sql_statements(source: str):
    """Yield complete SQL statements from a multi-statement script."""
    buffer = ""
    for line in source.splitlines():
        buffer += line + "\n"
        if sqlite3.complete_statement(buffer):
            statement = buffer.strip()
            if statement and any(
                line.strip() and not line.lstrip().startswith("--")
                for line in statement.splitlines()
            ):
                yield statement
            buffer = ""
    if buffer.strip():
        raise ValueError(f"Incomplete SQL statement at end of {QUERIES_PATH.name}")


def run_queries() -> None:
    if not DB_PATH.exists() or DB_PATH.stat().st_size == 0:
        raise FileNotFoundError(
            f"{DB_PATH.name} is missing or empty. Run data.py first to generate the database."
        )

    with sqlite3.connect(DB_PATH) as connection:
        for number, statement in enumerate(
            sql_statements(QUERIES_PATH.read_text(encoding="utf-8")), start=1
        ):
            cursor = connection.execute(statement)
            if cursor.description is None:
                continue
            columns = [column[0] for column in cursor.description]
            rows = cursor.fetchall()
            print(f"\nQuery {number} — {len(rows)} rows")
            print(" | ".join(columns))
            print("-" * min(120, max(24, len(" | ".join(columns)))))
            for row in rows[:25]:
                print(" | ".join("" if value is None else str(value) for value in row))
            if len(rows) > 25:
                print(f"... and {len(rows) - 25} more rows")


if __name__ == "__main__":
    run_queries()
