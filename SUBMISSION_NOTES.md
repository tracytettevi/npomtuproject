# Assignment Submission Notes

## Project summary

This submission is a local business analytics prototype with two selectable synthetic scenarios: retail SMS campaign performance (response or conversion) and subscription customer retention (churn). The selected scenario controls data analysis, SQL, model training, the Snwolley prompt, and dashboard content.

The workspace selector offers both scenarios. Each scenario has its own dataset adapter and business measures while sharing the ordered workflow, SQLite store, model evaluation approach, and report location. The platform does not yet accept arbitrary external datasets; the two implemented adapters are the supported scope of this prototype.

## How the work maps to the assignment

| Area | Evidence in this project | Scope note |
| --- | --- | --- |
| Business context and workflow | `app.py`, `outputs/workspace.json` | Selectable campaign or retention scenario with ordered workflow steps. |
| Data model and synthetic data | `schema.sql`, `data.py`, `campaigns.sqlite` | Reproducible campaign records plus 3,600 synthetic monthly subscription snapshots. Running `data.py` regenerates both. |
| SQL analysis | `sqlanalysisqueries.sql`, `retention_analysis.sql`, `run_sql.py` | Scenario-specific quality checks, joins, aggregates, CTE analysis, and window ranking. |
| Machine learning | `model.py`, `retention_model.py`, `notebooks/model_walkthrough.ipynb`, `outputs/model_report.json` | Campaign response/conversion or subscription churn; logistic regression, chronological holdout, training-only threshold selection, baseline, metrics, feature associations, and scored holdout records. |
| Snwolley integration | `snwolley_agent.py`, `outputs/ai_insights.md` | Scenario-specific aggregate synthetic analytics and model metrics; key comes from local environment configuration. |
| Business dashboard | `dashboard.py`, `outputs/dashboard.html` | Scenario-specific campaign or retention measures, model results, and Snwolley brief. |
| Setup and limitations | `README.md`, this document | Local run steps, scope boundaries, security notes, and production considerations. |

## Model explanation

The campaign scenario predicts response or conversion among delivered SMS messages using customer and campaign attributes available before sending. The retention scenario predicts account churn using segment, region, plan type, tenure, monthly charge, support ticket count, and inactivity days. Both use regularized logistic regression implemented in Python and chronological holdout evaluation.

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
3. Create a workspace, select a business scenario and prediction goal, then follow the numbered workflow in order.
4. Review the scenario-specific dashboard, Parts 4 and 5, model metrics, and source aggregates. Explain why held-out performance on synthetic data is not ready for operational customer decisions.
5. Review the generated artifacts in `outputs/`, the notebook, and the scope/monitoring notes in this file.

## Before uploading

- Confirm `.env` and its secret value are not staged or uploaded. `.gitignore` excludes `.env` and `.venv/`.
- Keep `.env.example` as the safe setup template; never replace its placeholder with a real key.
- Include source files, schema, SQL, README, assignment notes, and relevant synthetic output artifacts.
- The public GitHub repository is `https://github.com/tracytettevi/npomtuproject`; verify the link opens before portal submission.
- The repository was published with the local `.env` file excluded; `.env.example` contains only a placeholder.

