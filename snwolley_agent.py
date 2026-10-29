"""Request a grounded campaign summary from the Npontu Snwolley Agent API.

Only aggregate synthetic campaign/model results are sent. The API key is read
from SNWOLLEY_API_KEY (or a local .env file ignored by Git), never source code.
"""

from __future__ import annotations

import json
import os
import ssl
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from dashboard import load_dashboard_data, load_retention_dashboard_data

ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = ROOT / "outputs"
OUTPUT_PATH = OUTPUT_DIR / "ai_insights.md"
DISPLAY_PATH = OUTPUT_DIR / "ai_insights.txt"
API_URL = "https://v1.snwolley.ai/v1/chat/completions/assignment"


def load_local_env() -> None:
    """Load simple KEY=value entries from .env without replacing OS values."""
    env_path = ROOT / ".env"
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        name, value = name.strip(), value.strip().strip("\"'")
        if name and value:
            os.environ.setdefault(name, value)


def build_prompt(data: dict) -> str:
    totals = data["totals"]
    delivered = int(totals.get("delivered") or 0)
    responses = int(totals.get("responses") or 0)
    conversions = int(totals.get("conversions") or 0)
    overall = responses / delivered if delivered else 0.0
    converted_rate = conversions / delivered if delivered else 0.0
    segments = [
        {"segment": row["segment"], "delivered": row["delivered"],
         "responses": row["responses"], "response_rate": round(row["response_rate"] or 0, 4),
         "conversion_rate": round(row["conversion_rate"] or 0, 4)}
        for row in data["segments"]
    ]
    offers = [
        {"offer_type": row["offer_type"], "delivered": row["delivered"],
         "responses": row["responses"], "response_rate": round(row["response_rate"] or 0, 4),
         "conversion_rate": round(row["conversion_rate"] or 0, 4)}
        for row in data["offers"]
    ]
    model = data.get("model") or {}
    metrics = model.get("test_metrics", {})
    model_context = {
        "model": model.get("model", "not run"),
        "target": model.get("prediction_target", "response among delivered messages"),
        "test_records": metrics.get("records"),
        "test_roc_auc": metrics.get("roc_auc"),
        "test_precision": metrics.get("precision"),
        "test_recall": metrics.get("recall"),
        "test_f1": metrics.get("f1_score"),
        "threshold": metrics.get("decision_threshold"),
    }
    context = {
        "business_context": "Synthetic Ghanaian retail SMS campaign analytics demo.",
        "data_scope": {"customers": totals["customers"], "campaigns": totals["campaigns"],
                       "messages": totals["messages"], "delivered": delivered},
        "overall_kpis": {"responses": responses, "response_rate": round(overall, 4),
                         "conversions": conversions, "conversion_rate": round(converted_rate, 4)},
        "segment_results": segments,
        "offer_results": offers,
        "held_out_model_results": model_context,
    }
    return (
        "You are the business intelligence assistant inside a campaign analytics application. "
        "Use only the supplied figures. Write a concise executive brief with: (1) three "
        "specific observations, (2) up to three practical next-step recommendations, and "
        "(3) one limitation. Tie each observation to supplied numbers. Do not claim that "
        "an offer or segment caused an outcome; these are descriptive synthetic data. "
        "Clearly state that model performance is weak if ROC AUC is near 0.5, and do not "
        "recommend automated targeting based on this model. If the figures do not support "
        "a conclusion, say so.\n\nANALYTICS CONTEXT:\n"
        + json.dumps(context, indent=2, ensure_ascii=False)
    )


def build_retention_prompt(data: dict) -> str:
    """Construct an aggregate-only brief for the subscription retention scenario."""
    totals = data["totals"]
    model = data.get("model") or {}
    metrics = model.get("test_metrics", {})
    context = {
        "business_context": "Synthetic subscription customer-retention analytics.",
        "data_scope": {"subscription_records": totals["accounts"],
                       "churned_accounts": totals["churned"],
                       "overall_churn_rate": round(totals["churn_rate"] or 0, 4)},
        "segment_results": [{"segment": row["segment"], "accounts": row["accounts"],
                             "churned": row["churned"],
                             "churn_rate": round(row["churn_rate"] or 0, 4)}
                            for row in data["segments"]],
        "plan_results": [{"plan_type": row["plan_type"], "accounts": row["accounts"],
                          "churned": row["churned"],
                          "churn_rate": round(row["churn_rate"] or 0, 4)}
                         for row in data["plans"]],
        "monthly_results": [{"month": row["month"], "accounts": row["accounts"],
                             "churn_rate": round(row["churn_rate"] or 0, 4)}
                            for row in data["monthly"]],
        "held_out_model_results": {"model": model.get("model", "not run"),
                                   "target": model.get("prediction_target", "churn"),
                                   "records": metrics.get("records"),
                                   "roc_auc": metrics.get("roc_auc"),
                                   "precision": metrics.get("precision"),
                                   "recall": metrics.get("recall"),
                                   "f1": metrics.get("f1_score")},
    }
    return (
        "You are a business intelligence assistant. Use only the supplied aggregate figures. "
        "Write three specific observations, up to three practical next steps, and one limitation. "
        "Tie observations to numbers. Do not claim correlation proves cause, do not recommend "
        "automated customer decisions, and clearly call out weak model performance if ROC AUC "
        "is near 0.5. The data is synthetic.\n\nANALYTICS CONTEXT:\n"
        + json.dumps(context, indent=2, ensure_ascii=False)
    )


def extract_answer(response: dict) -> str:
    """Handle common chat-completion and direct-text response envelopes."""
    choices = response.get("choices")
    if isinstance(choices, list) and choices:
        first = choices[0]
        message = first.get("message", {}) if isinstance(first, dict) else {}
        content = message.get("content") if isinstance(message, dict) else None
        if content is None and isinstance(first, dict):
            content = first.get("text")
        if isinstance(content, list):
            content = "\n".join(
                part.get("text", "") if isinstance(part, dict) else str(part)
                for part in content
            )
        if isinstance(content, str) and content.strip():
            return content.strip()
    for key in ("response", "answer", "content", "output", "message"):
        value = response.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
        if isinstance(value, dict):
            nested = value.get("content") or value.get("text")
            if isinstance(nested, str) and nested.strip():
                return nested.strip()
    raise ValueError("Snwolley returned JSON, but no text answer field was recognized.")


def trusted_ssl_context() -> ssl.SSLContext:
    """Use Python's configured roots, with the macOS system bundle as fallback."""
    paths = ssl.get_default_verify_paths()
    configured = os.environ.get("SSL_CERT_FILE") or paths.cafile
    candidates = [configured, "/etc/ssl/cert.pem", "/opt/homebrew/etc/openssl@3/cert.pem"]
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return ssl.create_default_context(cafile=candidate)
    # Keep normal certificate verification if no explicit CA bundle exists.
    return ssl.create_default_context()


def request_insights(message: str, api_key: str) -> str:
    body = json.dumps({"message": message, "stream": False}).encode("utf-8")
    request = urllib.request.Request(
        API_URL,
        data=body,
        method="POST",
        headers={"Content-Type": "application/json", "X-API-Key": api_key},
    )
    try:
        with urllib.request.urlopen(request, timeout=60, context=trusted_ssl_context()) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        if error.code == 401:
            raise RuntimeError("Snwolley rejected the key (HTTP 401). Recheck .env and the testing key.") from None
        if error.code == 429:
            retry_after = error.headers.get("Retry-After", "a short time")
            raise RuntimeError(f"Snwolley rate limit reached (HTTP 429). Wait {retry_after} seconds before retrying.") from None
        raise RuntimeError(f"Snwolley request failed with HTTP {error.code}.") from None
    except urllib.error.URLError as error:
        raise RuntimeError(f"Could not reach Snwolley: {error.reason}") from None
    if not isinstance(payload, dict):
        raise RuntimeError("Snwolley returned an unexpected response format.")
    return extract_answer(payload)


def main() -> int:
    load_local_env()
    api_key = os.environ.get("SNWOLLEY_API_KEY", "").strip()
    if not api_key or api_key == "PASTE_TEST_KEY_HERE":
        print("API key missing. Copy .env.example to .env and add the testing key from the assignment PDF.")
        return 2
    try:
        workspace_path = OUTPUT_DIR / "workspace.json"
        workspace = json.loads(workspace_path.read_text(encoding="utf-8")) if workspace_path.exists() else {}
        if workspace.get("use_case") == "retention":
            source = load_retention_dashboard_data()
            prompt = build_retention_prompt(source)
            use_case = "retention"
        else:
            source = load_dashboard_data()
            prompt = build_prompt(source)
            use_case = "campaigns"
        answer = request_insights(prompt, api_key)
    except (FileNotFoundError, RuntimeError, ValueError, json.JSONDecodeError) as error:
        print(f"Snwolley insight generation failed: {error}")
        return 1
    OUTPUT_DIR.mkdir(exist_ok=True)
    (OUTPUT_DIR / "ai_insights_use_case.txt").write_text(use_case, encoding="utf-8")
    (OUTPUT_DIR / f"ai_insights_{use_case}.txt").write_text(answer.strip() + "\n", encoding="utf-8")
    DISPLAY_PATH.write_text(answer.strip() + "\n", encoding="utf-8")
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    OUTPUT_PATH.write_text(
        f"# Snwolley Agent: {use_case.replace('_', ' ')} insight brief\n\n"
        f"Generated: {generated}\n\n"
        "> AI-generated narrative based on synthetic aggregate results. "
        "Review recommendations against the source metrics before acting.\n\n"
        + answer.strip() + "\n",
        encoding="utf-8",
    )
    (OUTPUT_DIR / f"ai_insights_{use_case}.md").write_text(
        f"# Snwolley Agent: {use_case.replace('_', ' ')} insight brief\n\n"
        f"Generated: {generated}\n\n"
        "> AI-generated narrative based on synthetic aggregate results. "
        "Review recommendations against the source metrics before acting.\n\n"
        + answer.strip() + "\n",
        encoding="utf-8",
    )
    print(f"Snwolley insights saved to {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
