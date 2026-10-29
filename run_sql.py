"""Run the queries in sqlanalysisqueries.sql against campaigns.sqlite."""

from __future__ import annotations

import sqlite3
import argparse
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


def run_queries(use_case: str = "campaigns") -> None:
    if not DB_PATH.exists() or DB_PATH.stat().st_size == 0:
        raise FileNotFoundError(
            f"{DB_PATH.name} is missing or empty. Run data.py first to generate the database."
        )

    query_path = QUERIES_PATH if use_case == "campaigns" else ROOT / "retention_analysis.sql"
    with sqlite3.connect(DB_PATH) as connection:
        for number, statement in enumerate(
            sql_statements(query_path.read_text(encoding="utf-8")), start=1
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
    parser = argparse.ArgumentParser()
    parser.add_argument("--use-case", choices=("campaigns", "retention"), default="campaigns")
    run_queries(parser.parse_args().use_case)
