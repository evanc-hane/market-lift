CREATE OR REPLACE TABLE mart_experiment_cluster_hour AS
WITH session_metrics AS (
    SELECT
        a.assignment_id,
        COUNT(s.session_id) AS sessions,
        COALESCE(SUM(s.checkout_started), 0) AS checkouts,
        COUNT(s.order_id) AS orders
    FROM fct_experiment_assignments a
    LEFT JOIN fct_sessions s
        ON a.zone_id = s.zone_id
        AND s.session_timestamp >= a.block_start
        AND s.session_timestamp < a.block_end
    GROUP BY a.assignment_id
),
order_metrics AS (
    SELECT
        a.assignment_id,
        SUM(CASE WHEN o.order_status = 'completed' THEN 1 ELSE 0 END) AS completed_orders,
        SUM(CASE WHEN o.order_status = 'cancelled' THEN 1 ELSE 0 END) AS cancelled_orders,
        SUM(CASE WHEN o.order_status = 'completed'
            THEN o.platform_commission + o.delivery_fee ELSE 0 END) AS platform_revenue,
        SUM(o.courier_base_pay) AS courier_base_pay,
        SUM(o.courier_bonus) AS courier_bonus,
        SUM(o.refund_amount) AS refunds,
        SUM(o.estimated_support_cost) AS support_cost,
        QUANTILE_CONT(o.delivery_minutes, 0.9)
            FILTER (WHERE o.order_status = 'completed') AS p90_delivery_minutes,
        SUM(o.late_delivery) AS late_deliveries
    FROM fct_experiment_assignments a
    LEFT JOIN fct_orders o
        ON a.zone_id = o.zone_id
        AND o.created_at >= a.block_start
        AND o.created_at < a.block_end
    GROUP BY a.assignment_id
),
supply_metrics AS (
    SELECT
        a.assignment_id,
        AVG(cs.online_couriers) AS avg_online_couriers,
        SUM(cs.active_courier_minutes) / 60.0 AS active_courier_hours,
        SUM(cs.courier_earnings) AS courier_earnings,
        AVG(cs.rain_intensity) AS rain_intensity,
        AVG(cs.pickup_eta_minutes) AS pickup_eta_minutes
    FROM fct_experiment_assignments a
    LEFT JOIN fct_courier_supply cs
        ON a.zone_id = cs.zone_id
        AND cs.event_hour >= a.block_start
        AND cs.event_hour < a.block_end
    GROUP BY a.assignment_id
)
SELECT
    a.assignment_id,
    a.experiment_id,
    a.city_id,
    c.city_name,
    c.market_maturity,
    a.zone_id,
    a.zone_cluster_id,
    a.block_start,
    a.block_end,
    EXTRACT('hour' FROM a.block_start)::INTEGER AS block_hour,
    EXTRACT('dow' FROM a.block_start)::INTEGER AS day_of_week,
    a.treatment_assignment,
    a.bonus_amount,
    sm.sessions,
    sm.checkouts,
    sm.orders,
    COALESCE(om.completed_orders, 0) AS completed_orders,
    COALESCE(om.cancelled_orders, 0) AS cancelled_orders,
    COALESCE(om.platform_revenue, 0) AS platform_revenue,
    COALESCE(om.courier_base_pay, 0) AS courier_base_pay,
    COALESCE(om.courier_bonus, 0) AS courier_bonus,
    COALESCE(om.refunds, 0) AS refunds,
    COALESCE(om.support_cost, 0) AS support_cost,
    COALESCE(om.platform_revenue, 0)
        - COALESCE(om.courier_base_pay, 0)
        - COALESCE(om.courier_bonus, 0)
        - COALESCE(om.refunds, 0)
        - COALESCE(om.support_cost, 0) AS contribution_margin,
    om.p90_delivery_minutes AS p90_delivery_minutes,
    COALESCE(om.late_deliveries, 0) AS late_deliveries,
    COALESCE(sp.avg_online_couriers, 0) AS avg_online_couriers,
    COALESCE(sp.active_courier_hours, 0) AS active_courier_hours,
    COALESCE(sp.courier_earnings, 0) AS courier_earnings,
    COALESCE(sp.rain_intensity, 0) AS rain_intensity,
    COALESCE(sp.pickup_eta_minutes, 0) AS pickup_eta_minutes,
    sm.orders / NULLIF(sm.sessions, 0)::DOUBLE AS checkout_conversion_rate,
    COALESCE(om.completed_orders, 0) / NULLIF(sm.orders, 0)::DOUBLE AS completion_rate,
    COALESCE(om.cancelled_orders, 0) / NULLIF(sm.orders, 0)::DOUBLE AS cancellation_rate,
    COALESCE(om.late_deliveries, 0)
        / NULLIF(COALESCE(om.completed_orders, 0), 0)::DOUBLE AS late_delivery_rate,
    COALESCE(sp.courier_earnings, 0)
        / NULLIF(COALESCE(sp.active_courier_hours, 0), 0)::DOUBLE AS courier_earnings_per_hour
FROM fct_experiment_assignments a
JOIN dim_city c USING (city_id)
JOIN session_metrics sm USING (assignment_id)
LEFT JOIN order_metrics om USING (assignment_id)
LEFT JOIN supply_metrics sp USING (assignment_id);
