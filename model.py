"""Train and evaluate a campaign outcome model using Python's standard library.

The model uses customer and campaign details known before a message is sent.
It excludes delivery_status, responded, and converted from the inputs. The
latest campaigns are held out to evaluate performance on future-like data.
"""

from __future__ import annotations

import csv
import argparse
import json
import math
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "campaigns.sqlite"
OUTPUT_DIR = ROOT / "outputs"
TARGETS = {
    "responded": "response among delivered messages",
    "converted": "conversion among delivered messages",
}
CATEGORICAL_FIELDS = ("segment", "region", "offer_type")
NUMERIC_FIELDS = ("tenure_months", "preferred_contact_hour", "send_hour",
                  "hour_difference", "within_preferred_window")


def load_rows(target: str = "responded") -> list[dict]:
    if target not in TARGETS:
        raise ValueError(f"Unsupported target '{target}'. Choose one of: {', '.join(TARGETS)}")
    if not DB_PATH.exists() or DB_PATH.stat().st_size == 0:
        raise FileNotFoundError("campaigns.sqlite is missing or empty. Run data.py first.")
    with sqlite3.connect(DB_PATH) as connection:
        connection.row_factory = sqlite3.Row
        query = f"""SELECT m.message_id, m.{target} AS target_outcome, cu.segment, cu.region,
                          cu.tenure_months, cu.preferred_contact_hour,
                          ca.offer_type, ca.send_hour, ca.send_date
                   FROM messages AS m
                   JOIN customers AS cu ON cu.customer_id = m.customer_id
                   JOIN campaigns AS ca ON ca.campaign_id = m.campaign_id
                   WHERE m.delivery_status = 'delivered'
                   ORDER BY ca.send_date, m.message_id"""
        return [dict(row) for row in connection.execute(query)]


def add_derived_features(row: dict) -> dict:
    return {**row,
            "hour_difference": abs(row["send_hour"] - row["preferred_contact_hour"]),
            "within_preferred_window": int(
                abs(row["send_hour"] - row["preferred_contact_hour"]) <= 3
            )}


def make_feature_names(rows: list[dict]) -> list[str]:
    names = list(NUMERIC_FIELDS)
    for field in CATEGORICAL_FIELDS:
        names.extend(f"{field}={value}" for value in sorted(
            {str(row[field] or "Unknown") for row in rows})[1:])
    return names


def encode(row: dict, names: list[str], training_rows: list[dict]) -> list[float]:
    values = {field: float(row[field]) for field in NUMERIC_FIELDS}
    for field in CATEGORICAL_FIELDS:
        categories = sorted({str(item[field] or "Unknown") for item in training_rows})
        for category in categories[1:]:
            values[f"{field}={category}"] = float(str(row[field] or "Unknown") == category)
    return [values.get(name, 0.0) for name in names]


def fit_scaler(matrix: list[list[float]]) -> tuple[list[float], list[float]]:
    means = [sum(row[i] for row in matrix) / len(matrix) for i in range(len(matrix[0]))]
    scales = []
    for i, mean in enumerate(means):
        variance = sum((row[i] - mean) ** 2 for row in matrix) / len(matrix)
        scales.append(math.sqrt(variance) or 1.0)
    return means, scales


def scale(matrix: list[list[float]], means: list[float], scales: list[float]) -> list[list[float]]:
    return [[(value - means[i]) / scales[i] for i, value in enumerate(row)] for row in matrix]


def sigmoid(value: float) -> float:
    return 1.0 / (1.0 + math.exp(-max(-35.0, min(35.0, value))))


def train_logistic_regression(matrix: list[list[float]], labels: list[int]) -> list[float]:
    """Fit L2-regularized logistic regression with batch gradient descent."""
    weights = [0.0] * (len(matrix[0]) + 1)  # intercept plus feature weights
    learning_rate, regularization = 0.12, 0.03
    for _ in range(1600):
        gradients = [0.0] * len(weights)
        for row, label in zip(matrix, labels):
            probability = sigmoid(weights[0] + sum(w * x for w, x in zip(weights[1:], row)))
            error = probability - label
            gradients[0] += error
            for i, value in enumerate(row, start=1):
                gradients[i] += error * value
        count = len(matrix)
        weights[0] -= learning_rate * gradients[0] / count
        for i in range(1, len(weights)):
            weights[i] -= learning_rate * (gradients[i] / count + regularization * weights[i])
    return weights


def probabilities(matrix: list[list[float]], weights: list[float]) -> list[float]:
    return [sigmoid(weights[0] + sum(w * x for w, x in zip(weights[1:], row))) for row in matrix]


def roc_auc(labels: list[int], scores: list[float]) -> float | None:
    positives, negatives = sum(labels), len(labels) - sum(labels)
    if not positives or not negatives:
        return None
    ranked = sorted(zip(scores, labels))
    rank_sum, index = 0.0, 0
    while index < len(ranked):
        end = index + 1
        while end < len(ranked) and ranked[end][0] == ranked[index][0]:
            end += 1
        average_rank = (index + 1 + end) / 2
        rank_sum += average_rank * sum(label for _, label in ranked[index:end])
        index = end
    return (rank_sum - positives * (positives + 1) / 2) / (positives * negatives)


def evaluate(labels: list[int], scores: list[float], threshold: float) -> dict:
    predictions = [int(score >= threshold) for score in scores]
    tp = sum(y == 1 and p == 1 for y, p in zip(labels, predictions))
    tn = sum(y == 0 and p == 0 for y, p in zip(labels, predictions))
    fp = sum(y == 0 and p == 1 for y, p in zip(labels, predictions))
    fn = sum(y == 1 and p == 0 for y, p in zip(labels, predictions))
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    return {
        "records": len(labels), "positive_rate": sum(labels) / len(labels),
        "decision_threshold": threshold,
        "accuracy": (tp + tn) / len(labels), "precision": precision, "recall": recall,
        "f1_score": 2 * precision * recall / (precision + recall) if precision + recall else 0.0,
        "roc_auc": roc_auc(labels, scores),
        "confusion_matrix": {"true_negative": tn, "false_positive": fp,
                             "false_negative": fn, "true_positive": tp},
    }


def run_model(target: str = "responded") -> dict:
    if target not in TARGETS:
        raise ValueError(f"Unsupported target '{target}'. Choose one of: {', '.join(TARGETS)}")
    rows = [add_derived_features(row) for row in load_rows(target)]
    dates = sorted({row["send_date"] for row in rows})
    split_date = dates[max(1, int(len(dates) * 0.8))]
    training_rows = [row for row in rows if row["send_date"] < split_date]
    test_rows = [row for row in rows if row["send_date"] >= split_date]
    if not training_rows or not test_rows:
        raise ValueError("Not enough campaign dates for a time-based train/test split.")

    feature_names = make_feature_names(training_rows)
    train_x = [encode(row, feature_names, training_rows) for row in training_rows]
    test_x = [encode(row, feature_names, training_rows) for row in test_rows]
    means, scales = fit_scaler(train_x)
    train_x, test_x = scale(train_x, means, scales), scale(test_x, means, scales)
    train_y = [int(row["target_outcome"]) for row in training_rows]
    test_y = [int(row["target_outcome"]) for row in test_rows]
    weights = train_logistic_regression(train_x, train_y)
    train_scores = probabilities(train_x, weights)
    scores = probabilities(test_x, weights)
    # Tune the action threshold on training data only; a 0.5 cutoff is poorly
    # suited to this imbalanced outcome and can predict no responders at all.
    thresholds = [i / 100 for i in range(5, 41)]
    threshold = max(
        thresholds,
        key=lambda candidate: evaluate(train_y, train_scores, candidate)["f1_score"],
    )
    report = {
        "model": "L2-regularized logistic regression",
        "prediction_target": TARGETS[target],
        "target_column": target,
        "feature_names": feature_names,
        "split_method": "chronological by campaign send date",
        "train_through_date": max(row["send_date"] for row in training_rows),
        "test_from_date": min(row["send_date"] for row in test_rows),
        "decision_threshold_selection": "threshold with highest training-set F1, selected without using test outcomes",
        "training_metrics": evaluate(train_y, train_scores, threshold),
        "test_metrics": evaluate(test_y, scores, threshold),
        "baseline_test_accuracy": max(sum(test_y), len(test_y) - sum(test_y)) / len(test_y),
        "top_model_drivers": [
            {"feature": name, "coefficient": round(coefficient, 4),
             "direction": "positive association" if coefficient > 0 else "negative association"}
            for name, coefficient in sorted(
                zip(feature_names, weights[1:]), key=lambda item: abs(item[1]), reverse=True
            )[:8]
        ],
        "feature_driver_note": (
            "Coefficients are standardized associations in this fitted model, relative to "
            "the encoded reference categories; they are not causal effects."
        ),
        "limitations": [
            "The data is synthetic and does not establish real-world performance.",
            "This predicts response among delivered messages, not delivery or conversion.",
            "Deployment needs real historical data, monitoring, and business review.",
        ],
    }
    OUTPUT_DIR.mkdir(exist_ok=True)
    (OUTPUT_DIR / "model_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    with (OUTPUT_DIR / "scored_messages.csv").open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(("message_id", f"actual_{target}", f"predicted_{target}_probability",
                         f"predicted_{target}_at_selected_threshold"))
        for row, score in zip(test_rows, scores):
            writer.writerow((row["message_id"], row["target_outcome"], round(score, 6), int(score >= threshold)))
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train a campaign response or conversion model.")
    parser.add_argument("--target", choices=tuple(TARGETS), default="responded")
    args = parser.parse_args()
    report = run_model(args.target)
    print("Model evaluation on later held-out campaigns")
    for name, value in report["test_metrics"].items():
        print(f"{name}: {value:.3f}" if isinstance(value, float) else f"{name}: {value}")
    print(f"Baseline accuracy: {report['baseline_test_accuracy']:.3f}")
    print(f"Saved report: {OUTPUT_DIR / 'model_report.json'}")
    print(f"Saved predictions: {OUTPUT_DIR / 'scored_messages.csv'}")
