from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from scipy import stats
from statsmodels.stats.multitest import multipletests


@dataclass(frozen=True)
class Estimate:
    estimate: float
    standard_error: float
    ci_lower: float
    ci_upper: float
    p_value: float

    def to_dict(self) -> dict[str, float]:
        return {key: round(float(value), 6) for key, value in asdict(self).items()}


def sample_ratio_mismatch(assignments: pd.Series, expected_share: float = 0.5) -> dict[str, float]:
    observed_treatment = int(assignments.sum())
    total = len(assignments)
    expected = np.asarray([total * (1 - expected_share), total * expected_share])
    observed = np.asarray([total - observed_treatment, observed_treatment])
    statistic, p_value = stats.chisquare(observed, expected)
    return {
        "control_units": int(observed[0]),
        "treatment_units": int(observed[1]),
        "chi_square": round(float(statistic), 6),
        "p_value": round(float(p_value), 6),
    }


def naive_difference(
    frame: pd.DataFrame, outcome: str, treatment: str = "treatment_assignment"
) -> Estimate:
    treated = frame.loc[frame[treatment] == 1, outcome].astype(float).dropna()
    control = frame.loc[frame[treatment] == 0, outcome].astype(float).dropna()
    estimate = float(treated.mean() - control.mean())
    variance = treated.var(ddof=1) / len(treated) + control.var(ddof=1) / len(control)
    standard_error = float(np.sqrt(max(variance, 0)))
    z_score = estimate / standard_error if standard_error else 0.0
    p_value = float(2 * stats.norm.sf(abs(z_score))) if standard_error else 1.0
    return Estimate(
        estimate=estimate,
        standard_error=standard_error,
        ci_lower=estimate - 1.96 * standard_error,
        ci_upper=estimate + 1.96 * standard_error,
        p_value=p_value,
    )


def cuped_adjust(
    frame: pd.DataFrame, outcome: str, covariate: str
) -> tuple[pd.Series, float, float]:
    clean = frame[[outcome, covariate]].astype(float).dropna()
    covariate_variance = float(clean[covariate].var(ddof=1))
    theta = (
        float(clean[[outcome, covariate]].cov().iloc[0, 1]) / covariate_variance
        if covariate_variance > 0
        else 0.0
    )
    adjusted = frame[outcome] - theta * (frame[covariate] - frame[covariate].mean())
    variance_reduction = 1 - float(adjusted.var(ddof=1) / frame[outcome].var(ddof=1))
    return adjusted, theta, variance_reduction


def cluster_robust_estimate(
    frame: pd.DataFrame,
    outcome: str,
    treatment: str = "treatment_assignment",
) -> Estimate:
    formula = (
        f"{outcome} ~ {treatment} + C(city_id) + C(block_hour) + C(day_of_week) + rain_intensity"
    )
    fitted = smf.ols(formula, data=frame).fit(
        cov_type="cluster",
        cov_kwds={"groups": frame["zone_cluster_id"], "use_correction": True},
    )
    estimate = float(fitted.params[treatment])
    standard_error = float(fitted.bse[treatment])
    p_value = float(fitted.pvalues[treatment])
    return Estimate(
        estimate=estimate,
        standard_error=standard_error,
        ci_lower=estimate - 1.96 * standard_error,
        ci_upper=estimate + 1.96 * standard_error,
        p_value=p_value,
    )


def minimum_detectable_effect(
    outcome: pd.Series,
    treatment_share: float = 0.5,
    alpha: float = 0.05,
    power: float = 0.80,
) -> float:
    sample_size = len(outcome)
    effective_n = sample_size * treatment_share * (1 - treatment_share)
    critical = stats.norm.ppf(1 - alpha / 2) + stats.norm.ppf(power)
    return float(critical * outcome.std(ddof=1) / np.sqrt(max(effective_n, 1)))


def standardized_mean_difference(
    frame: pd.DataFrame, column: str, treatment: str = "treatment_assignment"
) -> float:
    treated = frame.loc[frame[treatment] == 1, column].astype(float)
    control = frame.loc[frame[treatment] == 0, column].astype(float)
    pooled_sd = np.sqrt((treated.var(ddof=1) + control.var(ddof=1)) / 2)
    return float((treated.mean() - control.mean()) / pooled_sd) if pooled_sd else 0.0


def stratified_randomization_test(
    frame: pd.DataFrame,
    outcome: str,
    strata: tuple[str, ...] = ("city_id", "experiment_date", "block_hour"),
    treatment: str = "treatment_assignment",
    repetitions: int = 1_000,
    seed: int = 42,
) -> dict[str, object]:
    """Test a sharp null by reshuffling assignment within randomization strata."""
    if repetitions < 1:
        raise ValueError("repetitions must be positive")
    required = {outcome, treatment, *strata}
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"Missing randomization-test columns: {sorted(missing)}")

    clean = frame.dropna(subset=[outcome, treatment, *strata]).reset_index(drop=True)
    values = clean[outcome].astype(float).to_numpy()
    assignments = clean[treatment].astype(int).to_numpy()
    if len(np.unique(assignments)) != 2:
        raise ValueError("randomization test requires treatment and control observations")

    observed = float(values[assignments == 1].mean() - values[assignments == 0].mean())
    group_indices = [
        np.asarray(indices, dtype=int)
        for indices in clean.groupby(list(strata), sort=False, observed=True).indices.values()
    ]
    rng = np.random.default_rng(seed)
    extreme = 0
    permuted = assignments.copy()
    for _ in range(repetitions):
        for indices in group_indices:
            permuted[indices] = rng.permutation(assignments[indices])
        difference = float(values[permuted == 1].mean() - values[permuted == 0].mean())
        extreme += int(abs(difference) >= abs(observed))

    return {
        "observed_difference": round(observed, 6),
        "p_value": round((extreme + 1) / (repetitions + 1), 6),
        "repetitions": repetitions,
        "strata": list(strata),
    }


def city_heterogeneous_effects(frame: pd.DataFrame, outcome: str) -> list[dict[str, object]]:
    rows = []
    for (city_id, city_name, maturity), city_frame in frame.groupby(
        ["city_id", "city_name", "market_maturity"]
    ):
        estimate = naive_difference(city_frame, outcome)
        rows.append(
            {
                "city_id": city_id,
                "city_name": city_name,
                "market_maturity": maturity,
                **estimate.to_dict(),
            }
        )
    adjusted = multipletests([float(row["p_value"]) for row in rows], method="fdr_bh")[1]
    for row, adjusted_p in zip(rows, adjusted, strict=True):
        row["adjusted_p_value"] = round(float(adjusted_p), 6)
    return rows


def difference_in_differences(
    frame: pd.DataFrame,
    outcome: str,
    treated_group: str = "treated_group",
    post_period: str = "post_period",
) -> Estimate:
    formula = (
        f"{outcome} ~ {treated_group} + {post_period} "
        f"+ {treated_group}:{post_period} + C(unit_id) + C(period)"
    )
    fitted = smf.ols(formula, data=frame).fit(cov_type="HC1")
    coefficient = f"{treated_group}:{post_period}"
    estimate = float(fitted.params[coefficient])
    standard_error = float(fitted.bse[coefficient])
    return Estimate(
        estimate=estimate,
        standard_error=standard_error,
        ci_lower=estimate - 1.96 * standard_error,
        ci_upper=estimate + 1.96 * standard_error,
        p_value=float(fitted.pvalues[coefficient]),
    )


def aa_false_positive_rate(outcome: pd.Series, repetitions: int = 200, seed: int = 42) -> float:
    rng = np.random.default_rng(seed)
    values = outcome.astype(float).to_numpy()
    half = len(values) // 2
    false_positives = 0
    for _ in range(repetitions):
        shuffled = rng.permutation(values)
        p_value = stats.ttest_ind(shuffled[:half], shuffled[half:], equal_var=False).pvalue
        false_positives += int(p_value < 0.05)
    return false_positives / repetitions
