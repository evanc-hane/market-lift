from pathlib import Path

from streamlit.testing.v1 import AppTest

from marketlift.cli import run_pipeline


def test_dashboard_renders_completed_experiment(tmp_path, monkeypatch):
    database = tmp_path / "marketlift.duckdb"
    reports = tmp_path / "reports"
    summary = run_pipeline(database, reports, scale="test", seed=21)

    monkeypatch.setenv("MARKETLIFT_DATABASE", str(database))
    monkeypatch.setenv("MARKETLIFT_RESULTS", str(reports / "results.json"))
    dashboard = Path(__file__).parents[1] / "dashboard" / "app.py"
    app = AppTest.from_file(str(dashboard), default_timeout=30).run()

    assert not app.exception
    assert summary["decision"]["recommendation"] in {
        "LAUNCH",
        "TARGETED_LAUNCH",
        "ITERATE",
        "STOP",
        "INVALID_EXPERIMENT",
    }
    assert app.title[0].value.startswith("MarketLift")
    assert app.metric[0].label == "Recommendation"
