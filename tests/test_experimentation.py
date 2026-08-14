import numpy as np
import pandas as pd

from marketlift.experimentation import (
    cuped_adjust,
    difference_in_differences,
    naive_difference,
    sample_ratio_mismatch,
)


def test_naive_difference_and_srm_on_known_data():
    frame = pd.DataFrame(
        {
            "treatment_assignment": [0] * 50 + [1] * 50,
            "outcome": list(range(50)) + list(range(52, 102)),
        }
    )
    estimate = naive_difference(frame, "outcome")
    assert estimate.estimate == 52
    assert sample_ratio_mismatch(frame["treatment_assignment"])["p_value"] == 1


def test_cuped_reduces_variance_when_pre_period_is_predictive():
    rng = np.random.default_rng(4)
    pre = rng.normal(100, 20, 2_000)
    outcome = 0.9 * pre + rng.normal(0, 5, 2_000)
    frame = pd.DataFrame({"pre": pre, "outcome": outcome})
    adjusted, theta, reduction = cuped_adjust(frame, "outcome", "pre")
    assert theta > 0
    assert reduction > 0.80
    assert adjusted.var() < frame["outcome"].var()


def test_difference_in_differences_recovers_injected_effect():
    rng = np.random.default_rng(9)
    rows = []
    for unit in range(40):
        treated = int(unit >= 20)
        unit_effect = rng.normal()
        for period in range(10):
            post = int(period >= 5)
            rows.append(
                {
                    "unit_id": f"unit_{unit}",
                    "period": period,
                    "treated_group": treated,
                    "post_period": post,
                    "outcome": unit_effect + 0.2 * period + 2.5 * treated * post,
                }
            )
    estimate = difference_in_differences(pd.DataFrame(rows), "outcome")
    assert abs(estimate.estimate - 2.5) < 0.05
