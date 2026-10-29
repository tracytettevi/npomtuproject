"""Train the common logistic-regression workflow for the retention scenario."""

from __future__ import annotations

import csv
import json
import sqlite3
from pathlib import Path

from model import evaluate, fit_scaler, probabilities, scale, train_logistic_regression

ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "campaigns.sqlite"
OUTPUT_DIR = ROOT / "outputs"
CATEGORICAL = ("segment", "region", "plan_type")
NUMERIC = ("tenure_months", "monthly_charge", "support_tickets", "inactive_days")


def run_retention_model() -> dict:
    if not DB_PATH.exists() or DB_PATH.stat().st_size == 0:
        raise FileNotFoundError("campaigns.sqlite is missing. Run data.py first.")
    with sqlite3.connect(DB_PATH) as connection:
        connection.row_factory = sqlite3.Row
        rows = [dict(row) for row in connection.execute(
            "SELECT account_id, snapshot_date, segment, region, plan_type, tenure_months, "
            "monthly_charge, support_tickets, inactive_days, churned "
            "FROM retention_accounts ORDER BY snapshot_date, account_id"
        )]
    if len(rows) < 20:
        raise ValueError("Not enough retention records to train and evaluate the model.")

    dates = sorted({row["snapshot_date"] for row in rows})
    split_date = dates[max(1, int(len(dates) * 0.8))]
    training = [row for row in rows if row["snapshot_date"] < split_date]
    testing = [row for row in rows if row["snapshot_date"] >= split_date]
    if not training or not testing:
        raise ValueError("Not enough snapshot dates for a chronological holdout.")

    categories = {field: sorted({str(row[field] or "Unknown") for row in training})
                  for field in CATEGORICAL}
    feature_names = list(NUMERIC) + [f"{field}={value}" for field in CATEGORICAL
                                    for value in categories[field][1:]]

    def encode(row: dict) -> list[float]:
        values = {field: float(row[field]) for field in NUMERIC}
        for field in CATEGORICAL:
            for value in categories[field][1:]:
                values[f"{field}={value}"] = float(str(row[field] or "Unknown") == value)
        return [values.get(name, 0.0) for name in feature_names]

    train_x = [encode(row) for row in training]
    test_x = [encode(row) for row in testing]
    means, scales = fit_scaler(train_x)
    train_x, test_x = scale(train_x, means, scales), scale(test_x, means, scales)
    train_y = [int(row["churned"]) for row in training]
    test_y = [int(row["churned"]) for row in testing]
    weights = train_logistic_regression(train_x, train_y)
    train_scores = probabilities(train_x, weights)
    test_scores = probabilities(test_x, weights)
    candidates = [i / 100 for i in range(5, 81)]
    threshold = max(candidates, key=lambda candidate: evaluate(train_y, train_scores, candidate)["f1_score"])
    report = {
        "model": "L2-regularized logistic regression",
        "use_case": "customer_retention",
        "prediction_target": "customer churn in the subscription snapshot",
        "target_column": "churned",
        "feature_names": feature_names,
        "split_method": "chronological by monthly snapshot date",
        "train_through_date": max(row["snapshot_date"] for row in training),
        "test_from_date": min(row["snapshot_date"] for row in testing),
        "decision_threshold_selection": "highest training-set F1; held-out outcomes were not used",
        "training_metrics": evaluate(train_y, train_scores, threshold),
        "test_metrics": evaluate(test_y, test_scores, threshold),
        "baseline_test_accuracy": max(sum(test_y), len(test_y) - sum(test_y)) / len(test_y),
        "top_model_drivers": [
            {"feature": name, "coefficient": round(coef, 4),
             "direction": "positive association" if coef > 0 else "negative association"}
            for name, coef in sorted(zip(feature_names, weights[1:]),
                                     key=lambda item: abs(item[1]), reverse=True)[:8]
        ],
        "feature_driver_note": "Standardized associations, not causal effects.",
        "limitations": ["Data is synthetic and does not establish real-world performance.",
                        "No intervention or retention offer effect is estimated.",
                        "Use real consented data and ongoing monitoring before deployment."],
    }
    OUTPUT_DIR.mkdir(exist_ok=True)
    (OUTPUT_DIR / "model_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    with (OUTPUT_DIR / "scored_accounts.csv").open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(("account_id", "actual_churned", "predicted_churn_probability", "predicted_churn_at_threshold"))
        for row, score in zip(testing, test_scores):
            writer.writerow((row["account_id"], row["churned"], round(score, 6), int(score >= threshold)))
    print(f"Retention model evaluated on {len(test_y)} later subscription records.")
    print(f"Test ROC AUC: {report['test_metrics']['roc_auc']:.3f}")
    print(f"Saved report: {OUTPUT_DIR / 'model_report.json'}")
    print(f"Saved predictions: {OUTPUT_DIR / 'scored_accounts.csv'}")
    return report


if __name__ == "__main__":
    run_retention_model()
