import os
from dataclasses import asdict
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

from marketlift.config import SimulationConfig

CITY_SPECS = [
    ("Toronto", "mature", 1.35, 1.05, 0.03),
    ("Vancouver", "mature", 1.15, 1.08, 0.04),
    ("Montreal", "growth", 1.10, 0.92, 0.13),
    ("Calgary", "growth", 0.90, 0.88, 0.15),
    ("Ottawa", "growth", 0.72, 0.90, 0.14),
    ("Edmonton", "new", 0.75, 0.76, 0.24),
    ("Winnipeg", "new", 0.58, 0.72, 0.27),
    ("Halifax", "new", 0.52, 0.70, 0.30),
]


def _sigmoid(value: np.ndarray) -> np.ndarray:
    return 1 / (1 + np.exp(-value))


def _city_and_zone_dimensions(config: SimulationConfig, rng: np.random.Generator):
    city_rows = []
    zone_rows = []
    for city_index, (name, maturity, demand, supply, lift) in enumerate(
        CITY_SPECS[: config.city_count]
    ):
        city_id = f"city_{city_index:02d}"
        city_rows.append(
            {
                "city_id": city_id,
                "city_name": name,
                "market_maturity": maturity,
                "demand_index": demand,
                "supply_index": supply,
                "true_supply_lift": lift,
                "base_commission_rate": 0.22,
                "timezone": "America/Toronto",
            }
        )
        # Marketplace zones have persistent demand differences; this stable signal
        # gives the pre-period covariate realistic predictive value for CUPED.
        zone_weights = rng.lognormal(0, 0.45, config.zones_per_city)
        zone_weights /= zone_weights.mean()
        for zone_index, weight in enumerate(zone_weights):
            zone_rows.append(
                {
                    "zone_id": f"{city_id}_zone_{zone_index:02d}",
                    "zone_cluster_id": f"{city_id}_cluster_{zone_index:02d}",
                    "city_id": city_id,
                    "zone_name": f"{name} Zone {zone_index + 1}",
                    "demand_weight": float(weight),
                }
            )
    return pd.DataFrame(city_rows), pd.DataFrame(zone_rows)


def _experiment_assignments(
    config: SimulationConfig,
    cities: pd.DataFrame,
    zones: pd.DataFrame,
    experiment_start: pd.Timestamp,
    rng: np.random.Generator,
) -> pd.DataFrame:
    rows = []
    assignment_index = 0
    for day_offset in range(config.experiment_days):
        day = experiment_start + pd.Timedelta(days=day_offset)
        for city_id in cities["city_id"]:
            city_zones = zones.loc[zones["city_id"] == city_id].copy()
            for block_hour in (17, 19):
                assignments = np.zeros(len(city_zones), dtype=int)
                assignments[: len(city_zones) // 2] = 1
                rng.shuffle(assignments)
                for zone, treatment in zip(
                    city_zones.itertuples(index=False), assignments, strict=True
                ):
                    block_start = day + pd.Timedelta(hours=block_hour)
                    rows.append(
                        {
                            "assignment_id": f"assignment_{assignment_index:07d}",
                            "experiment_id": "courier_bonus_peak_v1",
                            "city_id": city_id,
                            "zone_id": zone.zone_id,
                            "zone_cluster_id": zone.zone_cluster_id,
                            "block_start": block_start,
                            "block_end": block_start + pd.Timedelta(hours=2),
                            "treatment_assignment": int(treatment),
                            "bonus_amount": 2.0 if treatment else 0.0,
                            "randomization_seed": config.seed,
                        }
                    )
                    assignment_index += 1
    return pd.DataFrame(rows)


def _hourly_panel(
    config: SimulationConfig,
    cities: pd.DataFrame,
    zones: pd.DataFrame,
    assignments: pd.DataFrame,
    start: pd.Timestamp,
    rng: np.random.Generator,
) -> pd.DataFrame:
    hours = pd.date_range(
        start,
        periods=(config.pre_period_days + config.experiment_days) * 24,
        freq="h",
    )
    panel = zones.merge(cities, on="city_id", how="left").merge(
        pd.DataFrame({"event_hour": hours}), how="cross"
    )
    hour = panel["event_hour"].dt.hour.to_numpy()
    day_of_week = panel["event_hour"].dt.dayofweek.to_numpy()
    weekend = day_of_week >= 5
    rain = np.where(rng.random(len(panel)) < 0.28, rng.beta(2, 5, len(panel)), 0.0)
    lunch_peak = np.exp(-(((hour - 12) / 3.2) ** 2))
    dinner_peak = np.exp(-(((hour - 19) / 3.0) ** 2))
    hour_factor = 0.22 + 0.48 * lunch_peak + 1.05 * dinner_peak
    expected_sessions = (
        config.mean_sessions_per_zone_hour
        * panel["demand_index"].to_numpy()
        * panel["demand_weight"].to_numpy()
        * hour_factor
        * np.where(weekend, 1.12, 1.0)
        * (1 - 0.08 * rain)
    )

    expanded_assignments = pd.concat(
        [
            assignments.assign(event_hour=assignments["block_start"]),
            assignments.assign(event_hour=assignments["block_start"] + pd.Timedelta(hours=1)),
        ],
        ignore_index=True,
    )[
        [
            "assignment_id",
            "zone_id",
            "event_hour",
            "treatment_assignment",
            "bonus_amount",
        ]
    ]
    panel = panel.merge(expanded_assignments, on=["zone_id", "event_hour"], how="left")
    panel["treatment_assignment"] = panel["treatment_assignment"].fillna(0).astype(int)
    panel["bonus_amount"] = panel["bonus_amount"].fillna(0.0)
    panel["is_experiment_eligible"] = panel["assignment_id"].notna().astype(int)

    base_online = np.maximum(
        1.5,
        expected_sessions * 0.095 * panel["supply_index"].to_numpy() * (0.90 + 0.12 * dinner_peak),
    )
    treated_online = base_online * (
        1 + panel["treatment_assignment"].to_numpy() * panel["true_supply_lift"].to_numpy()
    )
    online_couriers = np.maximum(1, rng.poisson(treated_online)).astype(int)
    marketplace_load = expected_sessions / np.maximum(online_couriers * 5.0, 1)
    pickup_eta = 17 + np.maximum(marketplace_load - 0.65, 0) * 24 + rain * 7
    order_probability = _sigmoid(-1.22 - 0.058 * (pickup_eta - 22) + 0.10 * weekend - 0.10 * rain)

    panel["day_of_week"] = day_of_week
    panel["is_weekend"] = weekend.astype(int)
    panel["rain_intensity"] = rain
    panel["expected_sessions"] = expected_sessions
    panel["base_online_couriers"] = base_online
    panel["online_couriers"] = online_couriers
    panel["pickup_eta_minutes"] = pickup_eta
    panel["order_probability"] = order_probability
    return panel


def _event_facts(panel: pd.DataFrame, rng: np.random.Generator):
    session_counts = rng.poisson(panel["expected_sessions"].to_numpy())
    panel_indices = np.repeat(np.arange(len(panel)), session_counts)
    session_panel = panel.iloc[panel_indices].reset_index(drop=True)
    session_count = len(session_panel)
    second_offsets = rng.integers(0, 3600, session_count)
    session_timestamps = session_panel["event_hour"] + pd.to_timedelta(second_offsets, unit="s")
    checkout = rng.random(session_count) < 0.48
    conditional_order_probability = np.minimum(
        session_panel["order_probability"].to_numpy() / 0.48, 0.95
    )
    ordered = checkout & (rng.random(session_count) < conditional_order_probability)
    user_count = max(2_000, session_count // 4)
    session_ids = np.asarray([f"session_{index:09d}" for index in range(session_count)])
    order_sequence = np.cumsum(ordered) - 1
    order_ids = np.full(session_count, None, dtype=object)
    order_ids[ordered] = [f"order_{index:09d}" for index in order_sequence[ordered]]

    sessions = pd.DataFrame(
        {
            "session_id": session_ids,
            "user_id": [
                f"user_{value:08d}" for value in rng.integers(0, user_count, session_count)
            ],
            "city_id": session_panel["city_id"].to_numpy(),
            "zone_id": session_panel["zone_id"].to_numpy(),
            "zone_cluster_id": session_panel["zone_cluster_id"].to_numpy(),
            "session_timestamp": session_timestamps,
            "restaurant_impressions": rng.poisson(11, session_count) + 1,
            "checkout_started": checkout.astype(int),
            "order_id": order_ids,
        }
    )

    ordered_panel = session_panel.loc[ordered].reset_index(drop=True)
    ordered_sessions = sessions.loc[ordered].reset_index(drop=True)
    order_count = len(ordered_panel)
    basket_value = rng.lognormal(np.log(32), 0.42, order_count).clip(8, 180)
    distance_km = rng.lognormal(np.log(2.8), 0.55, order_count).clip(0.4, 18)
    pickup_eta = ordered_panel["pickup_eta_minutes"].to_numpy()
    rain = ordered_panel["rain_intensity"].to_numpy()
    completion_probability = np.clip(
        0.965 - 0.005 * np.maximum(pickup_eta - 22, 0) - 0.07 * rain,
        0.62,
        0.98,
    )
    completed = rng.random(order_count) < completion_probability
    delivery_minutes = (pickup_eta + 9 + distance_km * 2.8 + rng.normal(0, 3.5, order_count)).clip(
        15, 120
    )
    base_pay = 5.5 + distance_km * 1.1
    bonus = ordered_panel["bonus_amount"].to_numpy() * completed
    # A cancelled order records the platform-funded customer credit, not the full
    # merchant refund, which is not platform revenue or loss in this simulation.
    refund = np.where(completed, 0.0, basket_value * 0.10)
    support_cost = np.where(completed, 0.20, 1.25)
    created_at = ordered_sessions["session_timestamp"]
    delivered_at = created_at + pd.to_timedelta(delivery_minutes, unit="m")
    delivered_at = delivered_at.where(completed, pd.NaT)

    orders = pd.DataFrame(
        {
            "order_id": ordered_sessions["order_id"],
            "session_id": ordered_sessions["session_id"],
            "city_id": ordered_panel["city_id"],
            "zone_id": ordered_panel["zone_id"],
            "zone_cluster_id": ordered_panel["zone_cluster_id"],
            "created_at": created_at,
            "delivered_at": delivered_at,
            "order_status": np.where(completed, "completed", "cancelled"),
            "basket_value": basket_value.round(2),
            "delivery_fee": np.full(order_count, 4.99),
            "platform_commission": (basket_value * 0.22).round(2),
            "courier_base_pay": base_pay.round(2),
            "courier_bonus": bonus.round(2),
            "refund_amount": refund.round(2),
            "estimated_support_cost": support_cost,
            "delivery_minutes": np.where(completed, delivery_minutes, np.nan),
            "late_delivery": (completed & (delivery_minutes > 45)).astype(int),
        }
    )

    order_aggregate = (
        orders.assign(event_hour=orders["created_at"].dt.floor("h"))
        .groupby(["zone_id", "event_hour"], as_index=False)
        .agg(
            accepted_orders=("order_id", "count"),
            completed_orders=("order_status", lambda values: int((values == "completed").sum())),
            courier_earnings=("courier_base_pay", "sum"),
            bonus_paid=("courier_bonus", "sum"),
        )
    )
    supply = panel[
        [
            "city_id",
            "zone_id",
            "zone_cluster_id",
            "event_hour",
            "online_couriers",
            "rain_intensity",
            "pickup_eta_minutes",
        ]
    ].merge(order_aggregate, on=["zone_id", "event_hour"], how="left")
    for column in ("accepted_orders", "completed_orders", "courier_earnings", "bonus_paid"):
        supply[column] = supply[column].fillna(0)
    supply["active_courier_minutes"] = supply["online_couriers"] * 60
    supply["courier_earnings"] += supply["bonus_paid"]
    return sessions, orders, supply


def _ground_truth(panel: pd.DataFrame) -> pd.DataFrame:
    eligible = panel.loc[panel["is_experiment_eligible"] == 1].copy()
    truth_rows = []
    for city_id, city_panel in eligible.groupby("city_id"):
        scenario_values = {}
        for treatment in (0, 1):
            online = city_panel["base_online_couriers"].to_numpy() * (
                1 + treatment * city_panel["true_supply_lift"].to_numpy()
            )
            load = city_panel["expected_sessions"].to_numpy() / np.maximum(online * 5, 1)
            eta = 17 + np.maximum(load - 0.65, 0) * 24 + city_panel["rain_intensity"].to_numpy() * 7
            p_order = _sigmoid(
                -1.22
                - 0.058 * (eta - 22)
                + 0.10 * city_panel["is_weekend"].to_numpy()
                - 0.10 * city_panel["rain_intensity"].to_numpy()
            )
            p_complete = np.clip(
                0.965
                - 0.005 * np.maximum(eta - 22, 0)
                - 0.07 * city_panel["rain_intensity"].to_numpy(),
                0.62,
                0.98,
            )
            completed_margin = 32 * 0.22 + 4.99 - 8.58 - 2 * treatment - 0.20
            cancelled_margin = -(32 * 0.10) - 1.25
            expected_margin = (
                city_panel["expected_sessions"].to_numpy()
                * p_order
                * (p_complete * completed_margin + (1 - p_complete) * cancelled_margin)
            )
            scenario_values[treatment] = expected_margin
        truth_rows.append(
            {
                "city_id": city_id,
                "true_cm_lift_per_zone_hour": float(
                    np.mean(scenario_values[1] - scenario_values[0])
                ),
                "true_supply_lift_pct": float(city_panel["true_supply_lift"].iloc[0]),
            }
        )
    return pd.DataFrame(truth_rows)


def simulate_marketplace(database: str | Path, config: SimulationConfig) -> dict[str, int]:
    destination = Path(database)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    if temporary.exists():
        temporary.unlink()

    rng = np.random.default_rng(config.seed)
    start = pd.Timestamp(config.start_date)
    experiment_start = start + pd.Timedelta(days=config.pre_period_days)
    cities, zones = _city_and_zone_dimensions(config, rng)
    assignments = _experiment_assignments(config, cities, zones, experiment_start, rng)
    panel = _hourly_panel(config, cities, zones, assignments, start, rng)
    sessions, orders, supply = _event_facts(panel, rng)
    ground_truth = _ground_truth(panel)
    metadata = pd.DataFrame(
        [{"key": key, "value": str(value)} for key, value in asdict(config).items()]
    )

    with duckdb.connect(str(temporary)) as connection:
        tables = {
            "simulation_metadata": metadata,
            "dim_city": cities.drop(columns=["true_supply_lift"]),
            "dim_zone": zones,
            "fct_experiment_assignments": assignments,
            "fct_sessions": sessions,
            "fct_orders": orders,
            "fct_courier_supply": supply,
            "validation_ground_truth": ground_truth,
        }
        for table_name, frame in tables.items():
            connection.register("source_frame", frame)
            connection.execute(f"CREATE TABLE {table_name} AS SELECT * FROM source_frame")
            connection.unregister("source_frame")

    os.replace(temporary, destination)
    return {
        "cities": len(cities),
        "zones": len(zones),
        "assignments": len(assignments),
        "sessions": len(sessions),
        "orders": len(orders),
    }
