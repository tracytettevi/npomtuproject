# Business Analytics Prototype

A configurable end-to-end prototype with two synthetic business scenarios: SMS campaign analytics (response or conversion) and subscription customer retention (churn). Both use SQLite and Python's standard library, so no package installation is required.

For the assignment mapping, model explanation, monitoring approach, Snwolley safeguards, and reviewer walk-through, see [SUBMISSION_NOTES.md](SUBMISSION_NOTES.md). The relational schema and system design are explained in [ARCHITECTURE.md](ARCHITECTURE.md). The public repository URL is recorded in [GITHUB_REPOSITORY_LINK.md](GITHUB_REPOSITORY_LINK.md) for the application portal.

## Run it from PyCharm

Use the project's `.venv` interpreter. To open the workspace screen, right-click `app.py` in the Project panel and choose **Run**. Open `http://127.0.0.1:8000` in a browser, create a workspace, and run the workflow cards in order. Stop the app with Ctrl+C in PyCharm. If an older local server is still occupying port 8000, stop it or set the `PORT` environment variable to `8001` in the PyCharm run configuration.

You can also run each Python file directly from the Project panel in this order:

1. `data.py` creates or regenerates `campaigns.sqlite` from `schema.sql`, including both scenario datasets.
2. In the workspace, choose SMS campaign analytics or subscription retention.
3. `run_sql.py --use-case campaigns` runs campaign checks; `--use-case retention` runs subscription churn checks.
4. `model.py --target responded` or `--target converted` trains a campaign model. `retention_model.py` trains the churn model. Both write `outputs/model_report.json` and a held-out predictions CSV.
5. Configure the local API key as described below, then run `snwolley_agent.py` for an aggregate brief tailored to the active workspace scenario.
5. Run `dashboard.py` to build `outputs/dashboard.html`. Open that HTML file in a browser or use the workspace's dashboard link.

Run `data.py` first whenever you want a fresh synthetic database. It replaces the existing database contents.

The workspace scenario selector changes the data analysis, SQL, model, Snwolley prompt, and dashboard. The campaign scenario lets you select response or conversion. The retention scenario predicts churn from subscription snapshots. The notebook in `notebooks/model_walkthrough.ipynb` documents the campaign model.

## Snwolley key setup

Copy `.env.example` to a new file named `.env` in the project root. Replace `PASTE_TEST_KEY_HERE` with the testing key shown in the assignment PDF. The `.env` file is ignored by Git; do not commit it or paste the key into Python source. Keep the key private. The integration sends aggregate synthetic KPIs and model metrics, not customer-level records. It sends one non-streaming request per run and reports HTTP 401 or 429 errors without printing the key.

The Snwolley Agent endpoint and request format are specified in the assignment PDF. The API allows five requests per minute. If rate limited, wait for the indicated retry period before running the script again.

## What the model predicts

For campaigns, the target is whether a **delivered** message responds or converts, using only pre-send attributes and later campaign dates for evaluation. For retention, the target is account churn using subscription attributes and later monthly snapshots for evaluation. In both scenarios, the target and post-outcome fields are excluded from model inputs.

The generated example results may have weak test ranking performance. The dashboard reports the held-out metrics and baseline for the active scenario. These models demonstrate a reproducible pipeline and should not drive automated customer decisions. Synthetic results are not evidence of real-world performance.

## Current scope and next production steps

The prototype currently implements two scenario adapters: retail SMS campaign analytics and subscription customer retention. It does not yet ingest arbitrary customer datasets. A fuller platform would add validated data import and schema mapping, authenticated users, tenant-level access controls, scheduled production monitoring, and a reviewed deployment process. The AI summary is prompted to use supplied figures, avoid causal claims, and call out weak model results; generated recommendations still require human review.
