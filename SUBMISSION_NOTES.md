# Assignment Submission Notes

## Project summary

This submission is a local analytics demonstration for a Ghanaian retail business that wants to understand SMS campaign performance and explore which opted-in customers may respond. The implemented journey starts with a business workspace, creates reproducible synthetic data, runs SQL analysis, evaluates a response model, requests a Snwolley summary, and builds a dashboard.

The retail SMS use case is the selected demonstration scenario. The workspace lets a user choose response or conversion as the outcome, and the same model pipeline uses the selected target. Data ingestion, SQL analysis, and features are still specific to retail SMS; this is not yet a multi-business analytics platform.

## How the work maps to the assignment

| Area | Evidence in this project | Scope note |
| --- | --- | --- |
| Business context and workflow | `app.py`, `outputs/workspace.json` | Local workspace and ordered workflow for one implemented use case. |
| Data model and synthetic data | `schema.sql`, `data.py`, `campaigns.sqlite` | Deterministic generator with 1,200 synthetic customers, 24 campaigns, and message records. Running `data.py` recreates the database. |
| SQL analysis | `sqlanalysisqueries.sql`, `run_sql.py` | Quality checks, duplicate-key review, campaign/segment aggregates, a CTE, and a window ranking. |
| Machine learning | `model.py`, `notebooks/model_walkthrough.ipynb`, `outputs/model_report.json`, `outputs/scored_messages.csv` | Selectable response/conversion target, logistic regression, training-only threshold selection, chronological holdout, baseline comparison, metrics, feature associations, and scored held-out messages. |
| Snwolley integration | `snwolley_agent.py`, `outputs/ai_insights.md` | Sends aggregate synthetic analytics and model metrics; reads the key from local environment configuration. |
| Business dashboard | `dashboard.py`, `outputs/dashboard.html` | Campaign, segment, offer, model, and Snwolley results in one report. |
| Setup and limitations | `README.md`, this document | Local run steps, scope boundaries, security notes, and production considerations. |

## Model explanation

The workspace prediction goal is either a response or conversion among delivered SMS messages. The model uses customer and campaign attributes available before sending, including segment, region, tenure, preferred contact hour, offer type, send hour, and derived timing features. It does not use either outcome or delivery status as an input. The model is a regularized logistic regression implemented in Python.

Campaign dates define the chronological split: the model trains through 2025-09-10 and is evaluated on later campaigns beginning 2025-09-24. The decision threshold (0.15 for the recorded run) is selected from training data, not from the held-out test outcomes. The report compares the model to a prior-probability baseline.

For the current response run, the held-out set contains 1,362 messages and has a 14.83% response rate. Test ROC AUC is 0.539, precision is 0.178, recall is 0.569, and F1 is 0.271. Accuracy is 0.546 versus 0.852 for the majority-class baseline, reflecting the imbalanced target and selected threshold. The strongest positive feature associations are the Loyal segment (+0.2228), High Value segment (+0.1549), and sending within the preferred contact window (+0.0922). Free Delivery (-0.0525) and later send hour (-0.0444) are negative associations in this fitted model. These values are standardized model coefficients against reference categories, not causal effects; because held-out AUC is weak, they are hypotheses for controlled experiments rather than targeting advice. The model demonstrates a reproducible pipeline and should not be used for automated targeting or customer-level decisions.

## Model monitoring and responsible use

Before any real use, evaluate on consented, representative historical data and establish a randomized campaign holdout. Monitor data freshness, missing values, category changes, response prevalence, and feature distributions. At each campaign cycle, compare ROC AUC and precision/recall at the business-selected threshold with a simple baseline and the randomized control. Review results by customer segment and region for material performance gaps. Set review thresholds with the business before launch; pause scoring and investigate when data checks fail or performance degrades. Keep a dated record of model version, feature definitions, threshold, and evaluation results. A human owner must approve any campaign action.

The current project produces a single offline evaluation report. It does not implement scheduled production monitoring, model deployment, alerting, or automated retraining.

## Snwolley role and safeguards

Snwolley receives aggregate campaign, segment, offer, and held-out model metrics and is prompted to make only evidence-grounded observations, avoid causal claims, identify weak model performance, and state a limitation. The response is saved locally and displayed in the workspace/dashboard as AI-generated guidance for human review.

The API key is read from `.env` or the process environment and is excluded from Git by `.gitignore`. It must never be placed in source code or this submission document. The integration has request timeout and readable handling for authentication, rate-limit, network, and unexpected-response errors. Only aggregate synthetic information is included in the request; do not send real customer-level personal data through this demo.

## Architecture and scaling plan

See `ARCHITECTURE.md` for the component diagram, entity relationships, and a concise production scaling plan.

## Run-through for reviewers

1. Install/open the project in PyCharm and follow the setup in `README.md`.
2. Start `app.py` and open `http://127.0.0.1:8000`.
3. Create a workspace and follow the numbered workflow one step at a time: generate data, run SQL analysis, train/evaluate the model, generate the Snwolley brief, then build the dashboard.
4. In the dashboard, review Part 4 model results and Part 5 Snwolley insights. Point out the low held-out ROC AUC and explain why this is not ready for targeting.
5. Review the generated artifacts in `outputs/`, the notebook, and the scope/monitoring notes in this file.

## Before uploading

- Confirm `.env` and its secret value are not staged or uploaded. `.gitignore` excludes `.env` and `.venv/`.
- Keep `.env.example` as the safe setup template; never replace its placeholder with a real key.
- Include source files, schema, SQL, README, assignment notes, and relevant synthetic output artifacts.
- Add the actual public or reviewer-accessible GitHub repository URL to `GITHUB_REPOSITORY_LINK.md` after the repository has been created and pushed.
- Do not claim the repository is published until the uploaded files are visible at that URL.

