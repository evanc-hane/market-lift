import json

import duckdb

from marketlift.analysis import analyze_experiment
from marketlift.config import SimulationConfig
from marketlift.reporting import write_reports
from marketlift.simulation import simulate_marketplace
from marketlift.warehouse import build_warehouse


def test_end_to_end_pipeline_builds_decision_artifacts(tmp_path):
    database = tmp_path / "marketlift.duckdb"
    reports = tmp_path / "reports"
    summary = simulate_marketplace(database, SimulationConfig.for_scale("test", seed=12))
    assert summary["sessions"] > 1_000
    assert summary["orders"] > 100

    marts = build_warehouse(database)
    assert marts["mart_experiment_cluster_hour"] > 0
    assert marts["mart_pre_experiment_covariates"] > 0

    results = analyze_experiment(database)
    write_reports(results, reports)
    assert results["decision"]["recommendation"] in {
        "LAUNCH",
        "TARGETED_LAUNCH",
        "ITERATE",
        "STOP",
    }
    assert results["health"]["sample_ratio_mismatch"]["p_value"] > 0.01
    assert (reports / "decision_memo.md").exists()
    assert (
        json.loads((reports / "results.json").read_text())["experiment"]["experiment_id"]
        == "courier_bonus_peak_v1"
    )


def test_simulation_is_reproducible_at_table_level(tmp_path):
    first = tmp_path / "first.duckdb"
    second = tmp_path / "second.duckdb"
    config = SimulationConfig.for_scale("test", seed=99)
    assert simulate_marketplace(first, config) == simulate_marketplace(second, config)
    with (
        duckdb.connect(str(first), read_only=True) as left,
        duckdb.connect(str(second), read_only=True) as right,
    ):
        left_truth = left.execute(
            "SELECT * FROM validation_ground_truth ORDER BY city_id"
        ).fetchall()
        right_truth = right.execute(
            "SELECT * FROM validation_ground_truth ORDER BY city_id"
        ).fetchall()
    assert left_truth == right_truth
