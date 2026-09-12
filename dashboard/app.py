import json
import os
from pathlib import Path

import duckdb
import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(
    page_title="MarketLift Experiment Decision Center",
    page_icon="📈",
    layout="wide",
)

REPORT_PATH = Path(os.getenv("MARKETLIFT_RESULTS", "reports/results.json"))
DATABASE_PATH = Path(os.getenv("MARKETLIFT_DATABASE", "data/marketlift.duckdb"))

st.title("MarketLift — Marketplace Incentive Experimentation & Causal Inference Platform")
st.caption("Decision center for a geo-switchback test of a $2 peak-hour courier incentive.")

if not REPORT_PATH.exists() or not DATABASE_PATH.exists():
    st.error("Run `marketlift-run --scale demo` before opening the dashboard.")
    st.stop()

results = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
with duckdb.connect(str(DATABASE_PATH), read_only=True) as connection:
    experiment_units = connection.execute("SELECT * FROM mart_experiment_cluster_hour").fetch_df()
    daily_economics = connection.execute(
        "SELECT * FROM mart_city_unit_economics ORDER BY event_date, city_name"
    ).fetch_df()

executive, health, marketplace, segments, methods = st.tabs(
    ["Executive", "Experiment Health", "Marketplace", "City Effects", "Methods"]
)

primary = results["primary_metric"]["cuped_cluster_robust"]
with executive:
    recommendation = results["decision"]["recommendation"].replace("_", " ")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Recommendation", recommendation)
    col2.metric("CM effect / block", f"${primary['estimate']:.2f}")
    col3.metric("95% CI", f"[{primary['ci_lower']:.2f}, {primary['ci_upper']:.2f}]")
    col4.metric(
        "CUPED variance reduction",
        f"{results['primary_metric']['cuped_variance_reduction']:.1%}",
    )
    launch_cities = results["decision"]["launch_cities"]
    st.write("**Recommended launch cities:**", ", ".join(launch_cities) or "None")
    st.info(
        "This benchmark uses intent-to-treat assignment and a known simulator ground "
        "truth. It is not evidence about a real marketplace."
    )

with health:
    srm = results["health"]["sample_ratio_mismatch"]
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("SRM p-value", f"{srm['p_value']:.4f}")
    col2.metric("Pre-period SMD", f"{results['health']['pre_period_balance_smd']:.3f}")
    col3.metric("A/A false-positive rate", f"{results['health']['aa_false_positive_rate']:.1%}")
    col4.metric("Experiment valid", "Yes" if results["health"]["experiment_valid"] else "No")
    if results["health"]["violations"]:
        st.error("Blocking health violations: " + ", ".join(results["health"]["violations"]))
    assignment_counts = (
        experiment_units.groupby("treatment_assignment", as_index=False)
        .size()
        .replace({"treatment_assignment": {0: "Control", 1: "Treatment"}})
    )
    st.plotly_chart(
        px.bar(assignment_counts, x="treatment_assignment", y="size", title="Assignment balance"),
        width="stretch",
    )

with marketplace:
    selected_metric = st.selectbox(
        "Metric",
        ["contribution_margin", "completed_orders", "platform_revenue", "courier_cost"],
    )
    daily = daily_economics.groupby("event_date", as_index=False)[selected_metric].sum()
    st.plotly_chart(
        px.line(daily, x="event_date", y=selected_metric, title="Marketplace metric over time"),
        width="stretch",
    )
    st.dataframe(daily_economics.tail(50), width="stretch")

with segments:
    city_frame = pd.DataFrame(results["city_effects"])
    figure = px.scatter(
        city_frame,
        x="estimate",
        y="city_name",
        color="market_maturity",
        error_x=city_frame["ci_upper"] - city_frame["estimate"],
        error_x_minus=city_frame["estimate"] - city_frame["ci_lower"],
        title="Contribution-margin effect by city",
    )
    figure.add_vline(x=0, line_dash="dash")
    st.plotly_chart(figure, width="stretch")
    st.dataframe(city_frame, width="stretch")

with methods:
    method_frame = pd.DataFrame(
        [
            {"method": "Naive", **results["primary_metric"]["naive"]},
            {"method": "Cluster-robust", **results["primary_metric"]["cluster_robust"]},
            {
                "method": "CUPED + cluster-robust",
                **results["primary_metric"]["cuped_cluster_robust"],
            },
        ]
    )
    st.dataframe(method_frame, width="stretch")
    st.metric("Known ground truth", f"${results['primary_metric']['known_ground_truth']:.3f}")
    st.metric(
        "Randomization p-value",
        f"{results['primary_metric']['randomization_inference']['p_value']:.4f}",
    )
    st.metric("CUPED bias", f"${results['primary_metric']['cuped_estimation_bias']:.3f}")
    st.metric("CUPED absolute error", f"${results['primary_metric']['cuped_absolute_error']:.3f}")
