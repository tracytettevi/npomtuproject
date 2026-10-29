# Campaign Analytics Demo

A small end-to-end demonstration for synthetic SMS campaign response analytics. It uses SQLite and Python's standard library, so no package installation is required.

For the assignment mapping, model explanation, monitoring approach, Snwolley safeguards, and reviewer walk-through, see [SUBMISSION_NOTES.md](SUBMISSION_NOTES.md). The relational schema and system design are explained in [ARCHITECTURE.md](ARCHITECTURE.md). The public repository URL is recorded in [GITHUB_REPOSITORY_LINK.md](GITHUB_REPOSITORY_LINK.md) for the application portal.

## Run it from PyCharm

Use the project's `.venv` interpreter. To open the workspace screen, right-click `app.py` in the Project panel and choose **Run**. Open `http://127.0.0.1:8000` in a browser, create a workspace, and run the workflow cards in order. Stop the app with Ctrl+C in PyCharm.

You can also run each Python file directly from the Project panel in this order:

1. `data.py` creates or regenerates `campaigns.sqlite` from `schema.sql`.
2. `run_sql.py` runs the SQL quality checks and campaign analyses in `sqlanalysisqueries.sql`.
3. `model.py` trains and evaluates the response model by default, writing `outputs/model_report.json` and `outputs/scored_messages.csv`. Use `--target converted` to predict conversion instead.
4. Configure the local API key as described below, then run `snwolley_agent.py` to request an insight brief from Snwolley.
5. Run `dashboard.py` to build `outputs/dashboard.html`. Open that HTML file in a browser or use the workspace's dashboard link.

Run `data.py` first whenever you want a fresh synthetic database. It replaces the existing database contents.

The workspace lets you choose whether the campaign model predicts a delivered message response or conversion. The same model pipeline supports both outcomes. The notebook in `notebooks/model_walkthrough.ipynb` shows how to run and interpret the selected target.

## Snwolley key setup

Copy `.env.example` to a new file named `.env` in the project root. Replace `PASTE_TEST_KEY_HERE` with the testing key shown in the assignment PDF. The `.env` file is ignored by Git; do not commit it or paste the key into Python source. Keep the key private. The integration sends aggregate synthetic KPIs and model metrics, not customer-level records. It sends one non-streaming request per run and reports HTTP 401 or 429 errors without printing the key.

The Snwolley Agent endpoint and request format are specified in the assignment PDF. The API allows five requests per minute. If rate limited, wait for the indicated retry period before running the script again.

## What the model predicts

The target is whether a **delivered** message receives a response. Features are customer and campaign attributes known before sending. The most recent campaign dates are held out as a future-like test set. Delivery status, response, and conversion are excluded from model inputs to avoid outcome leakage.

The current synthetic-data run has weak test ranking performance (ROC AUC around 0.54). This is reported honestly: the model demonstrates a reproducible pipeline, but should not drive automated campaign targeting. The model and dashboard are demonstrations on synthetic data, not evidence of real-world performance.

## Current scope and next production steps

The demo has basic business workspace onboarding and one implemented retail SMS use case. The business question is saved as workspace context; selecting another question does not yet reconfigure the current data/model pipeline. A fuller generic platform would add authentication, user-provided data ingestion, configurable use-case adapters and targets, access controls, production model monitoring, and a reviewed deployment process. The AI summary is prompted to use supplied figures, avoid causal claims, and call out weak model results; generated recommendations still require human review.
