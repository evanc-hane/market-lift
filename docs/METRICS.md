# Metric Definitions

## Primary metric

`contribution_margin_per_zone_cluster_block` aggregates platform revenue minus courier pay,
bonus, refunds, and estimated support cost over the randomized two-hour block.

For cancelled orders, `refund_amount` represents a platform-funded customer credit equal to
10% of basket value, not the merchant-funded reversal of the basket. This keeps the metric on
a platform contribution-margin basis and avoids counting pass-through funds as platform loss.

This assignment-level metric captures both order-volume changes and per-order subsidy cost.
Analyzing only margin per completed order would condition on a treatment-affected outcome.

## Secondary metrics

- `completion_rate`: completed orders divided by submitted orders.
- `avg_online_couriers`: mean available supply during the block.
- `p90_delivery_minutes`: block-level 90th percentile among completed orders.
- `checkout_conversion_rate`: submitted orders divided by eligible sessions.

## Guardrails

- `cancellation_rate`: cancelled orders divided by submitted orders.
- `late_delivery_rate`: completed orders above 45 minutes divided by completed orders.
- `courier_earnings_per_hour`: courier pay and bonus divided by active courier hours.

All rate denominators are explicitly defined in SQL. Zero-denominator units remain null
rather than silently becoming zero.
