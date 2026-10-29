-- Data quality: missing or suspicious customer attributes.
SELECT
    COUNT(*) AS customer_count,
    SUM(CASE WHEN region IS NULL OR TRIM(region) = '' THEN 1 ELSE 0 END) AS missing_region_count,
    SUM(CASE WHEN tenure_months < 0 THEN 1 ELSE 0 END) AS invalid_tenure_count,
    SUM(CASE WHEN preferred_contact_hour NOT BETWEEN 0 AND 23 THEN 1 ELSE 0 END) AS invalid_hour_count
FROM customers;

-- Duplicate source identifiers across separate customer rows.
SELECT external_customer_key, COUNT(*) AS duplicate_rows
FROM customers
GROUP BY external_customer_key
HAVING COUNT(*) > 1
ORDER BY duplicate_rows DESC;

-- Campaign performance: joins, filtering, conditional aggregation.
SELECT c.campaign_id, c.campaign_name, c.offer_type,
       COUNT(m.message_id) AS messages_sent,
       SUM(CASE WHEN m.delivery_status = 'delivered' THEN 1 ELSE 0 END) AS delivered,
       SUM(CASE WHEN m.responded = 1 THEN 1 ELSE 0 END) AS responses,
       ROUND(100.0 * SUM(CASE WHEN m.responded = 1 THEN 1 ELSE 0 END) /
             NULLIF(SUM(CASE WHEN m.delivery_status = 'delivered' THEN 1 ELSE 0 END), 0), 2) AS response_rate_pct,
       SUM(CASE WHEN m.converted = 1 THEN 1 ELSE 0 END) AS conversions
FROM campaigns c
JOIN messages m ON m.campaign_id = c.campaign_id
WHERE c.send_date >= '2025-01-01'
GROUP BY c.campaign_id, c.campaign_name, c.offer_type
ORDER BY response_rate_pct DESC;

-- CTE plus aggregation: compare response by customer segment.
WITH segment_stats AS (
    SELECT cu.segment,
           COUNT(*) AS sends,
           SUM(CASE WHEN m.delivery_status = 'delivered' THEN 1 ELSE 0 END) AS delivered,
           SUM(m.responded) AS responses,
           SUM(m.converted) AS conversions
    FROM customers cu
    JOIN messages m ON m.customer_id = cu.customer_id
    GROUP BY cu.segment
)
SELECT segment, sends, delivered, responses, conversions,
       ROUND(100.0 * responses / NULLIF(delivered, 0), 2) AS response_rate_pct,
       ROUND(100.0 * conversions / NULLIF(delivered, 0), 2) AS conversion_rate_pct
FROM segment_stats
ORDER BY response_rate_pct DESC;

-- Window function: rank campaigns within each offer type.
WITH campaign_rates AS (
    SELECT c.offer_type, c.campaign_id, c.campaign_name,
           AVG(CASE WHEN m.delivery_status = 'delivered' THEN m.responded * 1.0 END) AS response_rate
    FROM campaigns c
    JOIN messages m ON m.campaign_id = c.campaign_id
    GROUP BY c.offer_type, c.campaign_id, c.campaign_name
)
SELECT offer_type, campaign_name,
       ROUND(response_rate * 100, 2) AS response_rate_pct,
       RANK() OVER (PARTITION BY offer_type ORDER BY response_rate DESC) AS rank_within_offer
FROM campaign_rates
ORDER BY offer_type, rank_within_offer;
