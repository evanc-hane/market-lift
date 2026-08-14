import json
from pathlib import Path


def _format_estimate(estimate: dict[str, float]) -> str:
    return f"{estimate['estimate']:.3f} [{estimate['ci_lower']:.3f}, {estimate['ci_upper']:.3f}]"


def write_reports(results: dict[str, object], report_directory: str | Path) -> None:
    output = Path(report_directory)
    output.mkdir(parents=True, exist_ok=True)
    health = results["health"]
    primary = results["primary_metric"]
    decision = results["decision"]
    secondary = results["secondary_metrics"]
    cities = results["city_effects"]

    health_markdown = f"""# Experiment Health Report

## Randomization integrity

- Analysis units: {results["experiment"]["analysis_units"]:,}
- Treatment units: {health["sample_ratio_mismatch"]["treatment_units"]}
- Control units: {health["sample_ratio_mismatch"]["control_units"]}
- SRM p-value: {health["sample_ratio_mismatch"]["p_value"]:.4f}
- Pre-period balance SMD: {health["pre_period_balance_smd"]:.4f}
- Rain balance SMD: {health["rain_balance_smd"]:.4f}
- A/A false-positive rate: {health["aa_false_positive_rate"]:.2%}

The analysis must be stopped if SRM p-value is below 0.01 or absolute balance SMD
exceeds 0.10. The A/A calibration is diagnostic and should remain near the nominal 5%.
"""
    (output / "experiment_health.md").write_text(health_markdown, encoding="utf-8")

    city_rows = "\n".join(
        f"| {row['city_name']} | {row['market_maturity']} | {row['estimate']:.3f} | "
        f"{row['ci_lower']:.3f} | {row['ci_upper']:.3f} | "
        f"{row['adjusted_p_value']:.4f} | {row['true_effect']:.3f} |"
        for row in cities
    )
    results_markdown = f"""# Primary Experiment Results

## Contribution margin per zone-cluster block

| Estimator | Effect and 95% CI |
| --- | ---: |
| Naive difference | {_format_estimate(primary["naive"])} |
| Cluster-robust OLS | {_format_estimate(primary["cluster_robust"])} |
| CUPED + cluster-robust OLS | {_format_estimate(primary["cuped_cluster_robust"])} |
| Known simulator ground truth | {primary["known_ground_truth"]:.3f} |

- CUPED variance reduction: {primary["cuped_variance_reduction"]:.2%}
- Minimum detectable effect: {results["power"]["minimum_detectable_effect"]:.3f}
- CUPED absolute estimation error: {primary["cuped_absolute_error"]:.3f}

## City heterogeneity

| City | Maturity | Estimate | CI low | CI high | FDR p-value | Ground truth |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
{city_rows}

Segment results use Benjamini-Hochberg correction. City-level findings are exploratory
unless the segment and decision rule were declared before analysis.
"""
    (output / "primary_results.md").write_text(results_markdown, encoding="utf-8")

    launch_cities = ", ".join(decision["launch_cities"]) or "None"
    decision_markdown = f"""# Executive Decision Memo

## Recommendation: {decision["recommendation"]}

**Business question:** {results["experiment"]["business_question"]}

**Primary effect:** {_format_estimate(primary["cuped_cluster_robust"])}

**Recommended launch cities:** {launch_cities}

## Guardrails

- Cancellation-rate effect: {_format_estimate(secondary["cancellation_rate"])}
- P90 delivery-time effect: {_format_estimate(secondary["p90_delivery_minutes"])}
- Courier earnings/hour effect: {_format_estimate(secondary["courier_earnings_per_hour"])}

## Decision rules

- Primary CI lower bound above zero: {decision["rules"]["primary_ci_lower_above_zero"]}
- Cancellation increase upper bound below 0.5pp:
  {decision["rules"]["cancellation_increase_ci_upper_below_0_5pp"]}
- City findings corrected at FDR q = {decision["rules"]["city_fdr_threshold"]:.2f}

## Interpretation

The recommendation is based on intent-to-treat assignment, not bonus receipt. This avoids
post-treatment bias. Results are generated from a semi-synthetic benchmark and must not
be interpreted as evidence about a real marketplace.
"""
    (output / "decision_memo.md").write_text(decision_markdown, encoding="utf-8")
    (output / "results.json").write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
