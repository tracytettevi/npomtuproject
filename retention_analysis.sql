-- Retention data quality: missing fields and invalid values.
SELECT COUNT(*) AS account_count,
       SUM(CASE WHEN region IS NULL OR TRIM(region) = '' THEN 1 ELSE 0 END) AS missing_region_count,
       SUM(CASE WHEN tenure_months < 0 OR monthly_charge < 0 THEN 1 ELSE 0 END) AS invalid_value_count,
       SUM(CASE WHEN churned NOT IN (0, 1) THEN 1 ELSE 0 END) AS invalid_target_count
FROM retention_accounts;

-- Churn outcomes by customer segment, using grouping and conditional aggregation.
SELECT segment, COUNT(*) AS accounts, SUM(churned) AS churned_accounts,
       ROUND(100.0 * SUM(churned) / NULLIF(COUNT(*), 0), 2) AS churn_rate_pct,
       ROUND(AVG(tenure_months), 1) AS avg_tenure_months,
       ROUND(AVG(inactive_days), 1) AS avg_inactive_days
FROM retention_accounts
GROUP BY segment ORDER BY churn_rate_pct DESC;

-- CTE plus join: subscription plan performance by snapshot month.
WITH monthly_plan AS (
    SELECT substr(snapshot_date, 1, 7) AS snapshot_month, plan_type,
           COUNT(*) AS accounts, SUM(churned) AS churned_accounts
    FROM retention_accounts GROUP BY substr(snapshot_date, 1, 7), plan_type
)
SELECT snapshot_month, plan_type, accounts, churned_accounts,
       ROUND(100.0 * churned_accounts / NULLIF(accounts, 0), 2) AS churn_rate_pct
FROM monthly_plan ORDER BY snapshot_month, plan_type;

-- Window function: rank plan types by churn rate within each snapshot month.
WITH plan_rates AS (
    SELECT substr(snapshot_date, 1, 7) AS snapshot_month, plan_type,
           AVG(churned * 1.0) AS churn_rate
    FROM retention_accounts GROUP BY substr(snapshot_date, 1, 7), plan_type
)
SELECT snapshot_month, plan_type, ROUND(churn_rate * 100, 2) AS churn_rate_pct,
       RANK() OVER (PARTITION BY snapshot_month ORDER BY churn_rate DESC) AS rank_in_month
FROM plan_rates ORDER BY snapshot_month, rank_in_month;
