import json
from pathlib import Path

import duckdb
import pandas as pd

from marketlift.experimentation import (
    aa_false_positive_rate,
    city_heterogeneous_effects,
    cluster_robust_estimate,
    cuped_adjust,
    minimum_detectable_effect,
    naive_difference,
    sample_ratio_mismatch,
    standardized_mean_difference,
    stratified_randomization_test,
)


def _estimate_metric(frame: pd.DataFrame, metric: str) -> dict[str, float]:
    clean = frame.dropna(subset=[metric]).copy()
    return cluster_robust_estimate(clean, metric).to_dict()


def analyze_experiment(database: str | Path) -> dict[str, object]:
    with duckdb.connect(str(database), read_only=True) as connection:
        frame = connection.execute(
            """
            SELECT m.*, p.pre_contribution_margin
            FROM mart_experiment_cluster_hour m
            LEFT JOIN mart_pre_experiment_covariates p
                USING (zone_cluster_id, block_hour)
            ORDER BY block_start, zone_cluster_id
            """
        ).fetch_df()
        truth = connection.execute(
            """
            SELECT g.*, c.city_name
            FROM validation_ground_truth g JOIN dim_city c USING (city_id)
            ORDER BY city_id
            """
        ).fetch_df()

    frame["pre_contribution_margin"] = frame["pre_contribution_margin"].fillna(
        frame["pre_contribution_margin"].mean()
    )
    raw_naive = naive_difference(frame, "contribution_margin")
    raw_adjusted, theta, variance_reduction = cuped_adjust(
        frame, "contribution_margin", "pre_contribution_margin"
    )
    frame["cuped_contribution_margin"] = raw_adjusted
    frame["experiment_date"] = frame["block_start"].dt.date
    cluster_raw = cluster_robust_estimate(frame, "contribution_margin")
    cluster_cuped = cluster_robust_estimate(frame, "cuped_contribution_margin")
    randomization_inference = stratified_randomization_test(frame, "cuped_contribution_margin")
    overall_truth = float(truth["true_cm_lift_per_zone_hour"].mean() * 2)

    secondary_metrics = {
        metric: _estimate_metric(frame, metric)
        for metric in (
            "completion_rate",
            "cancellation_rate",
            "p90_delivery_minutes",
            "avg_online_couriers",
            "courier_earnings_per_hour",
        )
    }
    city_effects = city_heterogeneous_effects(frame, "contribution_margin")
    city_cancellation = {
        str(row["city_id"]): row for row in city_heterogeneous_effects(frame, "cancellation_rate")
    }
    true_by_city = {
        row.city_id: float(row.true_cm_lift_per_zone_hour * 2)
        for row in truth.itertuples(index=False)
    }
    for city in city_effects:
        city["true_effect"] = round(true_by_city[str(city["city_id"])], 6)
        city["estimation_bias"] = round(float(city["estimate"]) - float(city["true_effect"]), 6)
        city["absolute_error"] = round(abs(float(city["estimation_bias"])), 6)
        cancellation_ci_upper = float(city_cancellation[str(city["city_id"])]["ci_upper"])
        city["cancellation_ci_upper"] = round(cancellation_ci_upper, 6)
        city["passes_cancellation_guardrail"] = cancellation_ci_upper <= 0.005

    srm = sample_ratio_mismatch(frame["treatment_assignment"])
    pre_balance = standardized_mean_difference(frame, "pre_contribution_margin")
    rain_balance = standardized_mean_difference(frame, "rain_intensity")
    health_violations = []
    if float(srm["p_value"]) < 0.01:
        health_violations.append("sample_ratio_mismatch")
    if abs(pre_balance) > 0.10:
        health_violations.append("pre_period_imbalance")
    if abs(rain_balance) > 0.10:
        health_violations.append("rain_imbalance")
    experiment_valid = not health_violations

    significant_positive = [
        city
        for city in city_effects
        if float(city["estimate"]) > 0
        and float(city["adjusted_p_value"]) < 0.10
        and bool(city["passes_cancellation_guardrail"])
    ]
    cancellation_guardrail = secondary_metrics["cancellation_rate"]["ci_upper"] <= 0.005
    if not experiment_valid:
        recommendation = "INVALID_EXPERIMENT"
    elif cluster_cuped.ci_lower > 0 and cancellation_guardrail:
        recommendation = "LAUNCH"
    elif significant_positive:
        recommendation = "TARGETED_LAUNCH"
    elif cluster_cuped.ci_upper <= 0:
        recommendation = "STOP"
    else:
        recommendation = "ITERATE"

    return {
        "experiment": {
            "experiment_id": "courier_bonus_peak_v1",
            "business_question": (
                "Should a $2 peak-hour courier bonus be launched without harming "
                "marketplace unit economics?"
            ),
            "randomization_unit": "zone_cluster x 2-hour block",
            "analysis_units": len(frame),
        },
        "health": {
            "experiment_valid": experiment_valid,
            "violations": health_violations,
            "sample_ratio_mismatch": srm,
            "pre_period_balance_smd": round(pre_balance, 6),
            "rain_balance_smd": round(rain_balance, 6),
            "aa_false_positive_rate": round(
                aa_false_positive_rate(frame["pre_contribution_margin"]), 4
            ),
        },
        "power": {
            "minimum_detectable_effect": round(
                minimum_detectable_effect(frame["contribution_margin"]), 6
            ),
            "alpha": 0.05,
            "power": 0.80,
        },
        "primary_metric": {
            "name": "contribution_margin_per_zone_cluster_block",
            "naive": raw_naive.to_dict(),
            "cluster_robust": cluster_raw.to_dict(),
            "cuped_cluster_robust": cluster_cuped.to_dict(),
            "randomization_inference": randomization_inference,
            "cuped_theta": round(theta, 6),
            "cuped_variance_reduction": round(variance_reduction, 6),
            "known_ground_truth": round(overall_truth, 6),
            "cuped_estimation_bias": round(cluster_cuped.estimate - overall_truth, 6),
            "cuped_absolute_error": round(abs(cluster_cuped.estimate - overall_truth), 6),
        },
        "secondary_metrics": secondary_metrics,
        "city_effects": city_effects,
        "decision": {
            "recommendation": recommendation,
            "launch_cities": [city["city_name"] for city in significant_positive],
            "rules": {
                "primary_ci_lower_above_zero": cluster_cuped.ci_lower > 0,
                "cancellation_increase_ci_upper_below_0_5pp": cancellation_guardrail,
                "city_fdr_threshold": 0.10,
                "experiment_health_required": True,
                "city_guardrail_required": True,
            },
        },
    }


def write_analysis_json(results: dict[str, object], output: str | Path) -> None:
    destination = Path(output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
