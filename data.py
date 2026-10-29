"""Deterministic synthetic campaign-data generator and SQLite loader."""

from __future__ import annotations

import random
import math
import sqlite3
from datetime import date, timedelta
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "campaigns.sqlite"
SCHEMA_PATH = ROOT / "schema.sql"

SEGMENTS = ("New", "Loyal", "At Risk", "High Value")
REGIONS = ("Greater Accra", "Ashanti", "Central", "Northern", "Western")
OFFERS = ("Discount", "Free Delivery", "Loyalty Points")


def create_database(db_path: Path = DB_PATH, seed: int = 42) -> Path:
    """Create the demo database and regenerate all records using a fixed seed."""
    rng = random.Random(seed)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()

    connection = sqlite3.connect(db_path)
    connection.execute("PRAGMA foreign_keys = ON")
    connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))

    connection.execute(
        "INSERT INTO businesses VALUES (?, ?, ?)",
        (1, "Demo Retail Ghana", "Retail"),
    )

    customer_count = 1200
    customers = []
    for customer_id in range(1, customer_count + 1):
        # A small number of repeated source keys simulates duplicate imported profiles.
        external_key = f"CUST-{customer_id:05d}"
        if customer_id % 101 == 0:
            external_key = f"CUST-{customer_id - 1:05d}"
        segment = rng.choices(SEGMENTS, weights=(30, 35, 20, 15))[0]
        region = None if customer_id % 47 == 0 else rng.choice(REGIONS)
        tenure = rng.randint(1, 72)
        preferred_hour = rng.randint(8, 20)
        consent = "opted_in" if rng.random() > 0.04 else "unknown"
        customers.append((customer_id, 1, external_key, segment, region, tenure, preferred_hour, consent))
    connection.executemany(
        "INSERT INTO customers VALUES (?, ?, ?, ?, ?, ?, ?, ?)", customers
    )

    start_date = date(2025, 1, 1)
    campaigns = []
    for campaign_id in range(1, 25):
        campaign_date = start_date + timedelta(days=14 * (campaign_id - 1))
        campaigns.append(
            (campaign_id, 1, f"Campaign {campaign_id:02d}",
             rng.choice(OFFERS), campaign_date.isoformat(), rng.randint(8, 20))
        )
    connection.executemany(
        "INSERT INTO campaigns VALUES (?, ?, ?, ?, ?, ?)", campaigns
    )

    messages = []
    message_id = 1
    for campaign_id, _, _, offer_type, send_date, send_hour in campaigns:
        for customer_id, _, _, segment, region, tenure, preferred_hour, consent in customers:
            # A small random audience per campaign keeps the generated database compact.
            if rng.random() > 0.24:
                continue
            if consent != "opted_in":
                continue

            delivered = rng.random() < 0.94
            hour_match = abs(send_hour - preferred_hour) <= 3
            segment_lift = {"New": 0.01, "Loyal": 0.08, "At Risk": -0.01, "High Value": 0.06}[segment]
            offer_lift = {"Discount": 0.04, "Free Delivery": 0.02, "Loyalty Points": 0.03}[offer_type]
            probability = max(0.02, min(0.55, 0.06 + segment_lift + offer_lift + (0.04 if hour_match else 0)))
            responded = int(delivered and rng.random() < probability)
            converted = int(responded and rng.random() < (0.35 if segment == "High Value" else 0.22))
            status = "delivered" if delivered else "failed"
            sent_at = f"{send_date}T{send_hour:02d}:00:00"
            messages.append((message_id, campaign_id, customer_id, status, responded, converted, sent_at))
            message_id += 1

    connection.executemany(
        "INSERT INTO messages VALUES (?, ?, ?, ?, ?, ?, ?)", messages
    )

    # A second, distinct business scenario demonstrates the same workflow for
    # subscription retention rather than campaign engagement.
    retention_rows = []
    account_id = 1
    for month_index in range(18):
        snapshot = date(2025 + month_index // 12, month_index % 12 + 1, 1)
        for _ in range(200):
            segment = rng.choices(SEGMENTS, weights=(30, 35, 20, 15))[0]
            region = None if account_id % 83 == 0 else rng.choice(REGIONS)
            plan_type = rng.choice(("Basic", "Standard", "Premium"))
            tenure = rng.randint(1, 72)
            monthly_charge = round(rng.uniform(25, 240), 2)
            support_tickets = rng.randint(0, 8)
            inactive_days = rng.randint(0, 60)
            # Generate a plausible synthetic signal, with overlap/noise so the
            # prediction remains a demonstration rather than a perfect rule.
            logit = (-2.25 + 0.045 * inactive_days + 0.18 * support_tickets
                     - 0.018 * tenure + (0.35 if plan_type == "Basic" else 0)
                     + rng.uniform(-1.35, 1.35))
            churn_probability = 1 / (1 + math.exp(-logit))
            churned = int(rng.random() < churn_probability)
            retention_rows.append((account_id, 1, snapshot.isoformat(), segment, region,
                                   plan_type, tenure, monthly_charge, support_tickets,
                                   inactive_days, churned))
            account_id += 1
    connection.executemany(
        """INSERT INTO retention_accounts
           (account_id, business_id, snapshot_date, segment, region, plan_type,
            tenure_months, monthly_charge, support_tickets, inactive_days, churned)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        retention_rows,
    )
    connection.commit()
    connection.close()
    return db_path


if __name__ == "__main__":
    print(f"Created synthetic campaign database at {create_database()}")
