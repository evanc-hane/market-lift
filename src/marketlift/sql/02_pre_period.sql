CREATE OR REPLACE TABLE mart_pre_experiment_covariates AS
WITH experiment_start AS (
    SELECT MIN(block_start) AS start_at FROM fct_experiment_assignments
),
session_metrics AS (
    SELECT
        s.zone_cluster_id,
        CASE
            WHEN EXTRACT('hour' FROM s.session_timestamp) IN (17, 18) THEN 17
            WHEN EXTRACT('hour' FROM s.session_timestamp) IN (19, 20) THEN 19
        END AS block_hour,
        COUNT(*) AS sessions,
        COUNT(s.order_id) AS orders
    FROM fct_sessions s, experiment_start e
    WHERE s.session_timestamp < e.start_at
        AND EXTRACT('hour' FROM s.session_timestamp) BETWEEN 17 AND 20
    GROUP BY 1, 2
),
order_metrics AS (
    SELECT
        o.zone_cluster_id,
        CASE
            WHEN EXTRACT('hour' FROM o.created_at) IN (17, 18) THEN 17
            WHEN EXTRACT('hour' FROM o.created_at) IN (19, 20) THEN 19
        END AS block_hour,
        SUM(CASE WHEN o.order_status = 'completed'
            THEN o.platform_commission + o.delivery_fee ELSE 0 END)
            - SUM(o.courier_base_pay)
            - SUM(o.courier_bonus)
            - SUM(o.refund_amount)
            - SUM(o.estimated_support_cost) AS contribution_margin,
        COUNT(DISTINCT CAST(o.created_at AS DATE)) AS observed_days
    FROM fct_orders o, experiment_start e
    WHERE o.created_at < e.start_at
        AND EXTRACT('hour' FROM o.created_at) BETWEEN 17 AND 20
    GROUP BY 1, 2
)
SELECT
    sm.zone_cluster_id,
    sm.block_hour,
    sm.sessions / NULLIF(om.observed_days, 0) AS pre_sessions_per_day,
    sm.orders / NULLIF(om.observed_days, 0) AS pre_orders_per_day,
    om.contribution_margin / NULLIF(om.observed_days, 0) AS pre_contribution_margin
FROM session_metrics sm
JOIN order_metrics om USING (zone_cluster_id, block_hour);

