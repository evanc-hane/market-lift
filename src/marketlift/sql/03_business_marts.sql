CREATE OR REPLACE TABLE mart_customer_funnel_daily AS
SELECT
    CAST(session_timestamp AS DATE) AS event_date,
    city_id,
    COUNT(*) AS sessions,
    SUM(checkout_started) AS checkouts,
    COUNT(order_id) AS orders,
    SUM(checkout_started) / COUNT(*)::DOUBLE AS checkout_start_rate,
    COUNT(order_id) / COUNT(*)::DOUBLE AS order_conversion_rate
FROM fct_sessions
GROUP BY 1, 2;

CREATE OR REPLACE TABLE mart_city_unit_economics AS
SELECT
    CAST(o.created_at AS DATE) AS event_date,
    o.city_id,
    c.city_name,
    COUNT(*) AS orders,
    SUM(CASE WHEN o.order_status = 'completed' THEN 1 ELSE 0 END) AS completed_orders,
    SUM(CASE WHEN o.order_status = 'completed'
        THEN o.platform_commission + o.delivery_fee ELSE 0 END) AS platform_revenue,
    SUM(o.courier_base_pay + o.courier_bonus) AS courier_cost,
    SUM(o.refund_amount + o.estimated_support_cost) AS refund_and_support_cost,
    SUM(CASE WHEN o.order_status = 'completed'
        THEN o.platform_commission + o.delivery_fee ELSE 0 END)
        - SUM(o.courier_base_pay + o.courier_bonus)
        - SUM(o.refund_amount + o.estimated_support_cost) AS contribution_margin
FROM fct_orders o
JOIN dim_city c USING (city_id)
GROUP BY 1, 2, 3;

CREATE OR REPLACE TABLE mart_experiment_guardrails AS
SELECT
    city_id,
    city_name,
    treatment_assignment,
    SUM(cancelled_orders) / NULLIF(SUM(orders), 0)::DOUBLE AS cancellation_rate,
    SUM(late_deliveries) / NULLIF(SUM(completed_orders), 0)::DOUBLE AS late_delivery_rate,
    SUM(courier_earnings) / NULLIF(SUM(active_courier_hours), 0)::DOUBLE
        AS courier_earnings_per_hour,
    AVG(p90_delivery_minutes) AS mean_block_p90_delivery_minutes
FROM mart_experiment_cluster_hour
GROUP BY 1, 2, 3;

