"""Streamlit dashboard: Monte Carlo simulation of an investment project's NPV.

Run from the project root:  streamlit run Investment_project_NPV.py
"""

from dataclasses import replace

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from mc_valuation.assumptions import (
    BASE_CASE,
    DEFAULT_SEED,
    INDEPENDENT_NORMAL_INPUTS,
    JUSTIFIED_INPUTS,
    PRICE_DEMAND_CORRELATION,
    IndependentNormalInputs,
    JustifiedInputs,
    ProjectAssumptions,
)
from mc_valuation.distributions import NormalParams, PertParams, normal_ppf, pert_ppf
from mc_valuation.model import npv
from mc_valuation.simulation import achieved_correlation, simulate_correlated, simulate_independent_normals
from mc_valuation.summary import summarize

MODEL_NORMAL = "Three independent normals"
MODEL_JUSTIFIED = "Justified distributions: PERT, capacity cap, correlation"
ITERATION_CHOICES = [1_000, 5_000, 10_000, 50_000, 100_000, 500_000, 1_000_000]
MAX_EXPORT_ROWS = 100_000

# Blue = NPV >= 0 / NPV increase, red = NPV < 0 / NPV decrease.
POSITIVE_COLOR, NEGATIVE_COLOR, MUTED = "#2a78d6", "#e34948", "#898781"


def euros(value: float) -> str:
    sign = "−" if value < 0 else ""
    return f"{sign}€{abs(value):,.0f}"


# ---------------------------------------------------------------- Simulation (cached)


@st.cache_data(show_spinner="Running simulation…", max_entries=5)
def run_simulation(
    model: str,
    iterations: int,
    seed: int,
    project: ProjectAssumptions,
    normal_inputs: IndependentNormalInputs,
    justified_inputs: JustifiedInputs,
    rho: float,
) -> pd.DataFrame:
    if model == MODEL_NORMAL:
        return simulate_independent_normals(iterations, seed, normal_inputs, project)
    return simulate_correlated(iterations, seed, rho, justified_inputs, project)


def central_values(model: str, project: ProjectAssumptions, normal_inputs, justified_inputs) -> dict[str, float]:
    """Central value of each input: the starting point of the tornado chart."""
    if model == MODEL_NORMAL:
        return {"price": normal_inputs.price.mean, "volume": normal_inputs.volume.mean,
                "variable_cost": normal_inputs.variable_cost.mean}
    return {"price": justified_inputs.price.mode,
            "volume": min(justified_inputs.demand.mean, project.capacity),
            "variable_cost": justified_inputs.variable_cost.mean}


def tornado_data(model: str, project: ProjectAssumptions, normal_inputs, justified_inputs) -> pd.DataFrame:
    """NPV when one input moves from its P5 to its P95, the others staying at their central value."""
    center = central_values(model, project, normal_inputs, justified_inputs)
    low_high = np.array([0.05, 0.95])
    if model == MODEL_NORMAL:
        ranges = {
            "price": normal_ppf(low_high, normal_inputs.price),
            "volume": normal_ppf(low_high, normal_inputs.volume),
            "variable_cost": normal_ppf(low_high, normal_inputs.variable_cost),
        }
    else:
        ranges = {
            "price": pert_ppf(low_high, justified_inputs.price),
            "volume": np.minimum(normal_ppf(low_high, justified_inputs.demand), project.capacity),
            "variable_cost": normal_ppf(low_high, justified_inputs.variable_cost),
        }
    labels = {"price": "Price", "volume": "Units sold", "variable_cost": "Variable cost"}
    rows = []
    for name, (low, high) in ranges.items():
        npv_low = float(npv(**{**center, name: low}, project=project))
        npv_high = float(npv(**{**center, name: high}, project=project))
        rows.append({"Input": labels[name], "Input P5": low, "Input P95": high,
                     "NPV at P5": npv_low, "NPV at P95": npv_high, "Swing": abs(npv_high - npv_low)})
    return pd.DataFrame(rows).sort_values("Swing")


# ---------------------------------------------------------------- Charts


def histogram_figure(values: np.ndarray, stats: pd.Series) -> go.Figure:
    # Equal-width bins aligned so that 0 is a bin edge: each bar is entirely < 0 or >= 0.
    bin_width = (values.max() - values.min()) / 80
    start = np.floor(values.min() / bin_width) * bin_width
    edges = np.arange(start, values.max() + bin_width, bin_width)
    counts, edges = np.histogram(values, bins=edges)
    fig = go.Figure(go.Bar(
        x=(edges[:-1] + edges[1:]) / 2, y=counts / counts.sum(), width=bin_width * 0.9,
        marker_color=np.where(edges[:-1] < 0, NEGATIVE_COLOR, POSITIVE_COLOR),
        customdata=np.column_stack([edges[:-1], edges[1:]]),
        hovertemplate="NPV between €%{customdata[0]:,.0f} and €%{customdata[1]:,.0f}"
                      "<br>%{y:.2%} of scenarios<extra></extra>",
    ))
    for key in ("P5", "P50", "P95"):
        fig.add_vline(x=stats[key], line_width=1, line_color=MUTED,
                      annotation_text=key, annotation_position="top", annotation_font_color=MUTED)
    fig.update_layout(height=380, margin=dict(t=30, b=10, l=10, r=10), showlegend=False,
                      xaxis_title="NPV (€) — red: NPV < 0, blue: NPV ≥ 0", yaxis_title="Share of scenarios")
    fig.update_xaxes(tickformat=",.0f")
    fig.update_yaxes(tickformat=".1%")
    return fig


def cdf_figure(values: np.ndarray) -> go.Figure:
    probabilities = np.linspace(0.001, 0.999, 999)
    quantiles = np.quantile(values, probabilities)
    prob_negative = (values < 0).mean()
    fig = go.Figure(go.Scatter(x=quantiles, y=probabilities, mode="lines", line=dict(color=POSITIVE_COLOR, width=2),
                               name="P(NPV ≤ x)", hovertemplate="P(NPV ≤ €%{x:,.0f}) = %{y:.1%}<extra></extra>"))
    fig.add_trace(go.Scatter(x=[0], y=[prob_negative], mode="markers+text", marker=dict(color=NEGATIVE_COLOR, size=9),
                             text=[f"  P(NPV < 0) = {prob_negative:.1%}"], textposition="middle right",
                             hoverinfo="skip", showlegend=False))
    fig.update_layout(height=380, margin=dict(t=30, b=10, l=10, r=10), showlegend=False,
                      xaxis_title="NPV (€)", yaxis_title="Cumulative probability")
    fig.update_xaxes(tickformat=",.0f")
    fig.update_yaxes(tickformat=".0%", range=[0, 1])
    return fig


def tornado_figure(table: pd.DataFrame, center_npv: float) -> go.Figure:
    fig = go.Figure()
    for column, label in (("NPV at P5", "Input at its P5"), ("NPV at P95", "Input at its P95")):
        deltas = table[column] - center_npv
        fig.add_trace(go.Bar(
            y=table["Input"], x=deltas, base=center_npv, orientation="h", name=label,
            marker_color=np.where(deltas < 0, NEGATIVE_COLOR, POSITIVE_COLOR),
            customdata=table[column], hovertemplate="%{y} — " + label + "<br>NPV = €%{customdata:,.0f}<extra></extra>",
        ))
    fig.add_vline(x=center_npv, line_width=1, line_color=MUTED)
    fig.update_layout(barmode="overlay", height=300, margin=dict(t=10, b=10, l=10, r=10), showlegend=False,
                      xaxis_title="NPV (€)")
    fig.update_xaxes(tickformat=",.0f")
    return fig


def scatter_figure(results: pd.DataFrame) -> go.Figure:
    sample = results.sample(n=min(len(results), 3_000), random_state=0)
    fig = go.Figure(go.Scattergl(
        x=sample["price"], y=sample["demand"], mode="markers",
        marker=dict(size=4, color=POSITIVE_COLOR, opacity=0.5),
        hovertemplate="Price €%{x:.2f}<br>Demand %{y:,.0f}<extra></extra>",
    ))
    fig.update_layout(height=380, margin=dict(t=10, b=10, l=10, r=10), xaxis_title="Price (€)",
                      yaxis_title="Drawn demand (units)")
    return fig


# ---------------------------------------------------------------- Interface


st.set_page_config(page_title="Monte Carlo NPV", page_icon="🎲", layout="wide")
st.title("Monte Carlo simulation of NPV")
st.caption(
    "A sensitivity analysis changes one or two variables at a time. Monte Carlo changes **all** variables at "
    "once, each drawn from a probability distribution, and produces a distribution of NPV with the "
    "probabilities attached."
)

with st.sidebar:
    st.header("Settings")
    model = st.radio("Model", (MODEL_JUSTIFIED, MODEL_NORMAL))
    iterations = st.select_slider("Iterations", ITERATION_CHOICES, value=50_000, format_func=lambda n: f"{n:,}")
    seed = int(st.number_input("Seed", min_value=0, value=DEFAULT_SEED, step=1))

    with st.expander("Project", expanded=False):
        project = replace(
            BASE_CASE,
            initial_investment=st.number_input("Initial investment (€)", value=BASE_CASE.initial_investment, step=10_000.0),
            fixed_costs=st.number_input("Fixed costs (€ / year)", value=BASE_CASE.fixed_costs, step=5_000.0),
            discount_rate=st.number_input("Discount rate (%)", value=BASE_CASE.discount_rate * 100, step=0.5) / 100,
            years=int(st.number_input("Life (years)", min_value=1, value=BASE_CASE.years, step=1)),
            capacity=st.number_input("Capacity (units / year)", value=BASE_CASE.capacity, step=500.0),
        )

    normal_inputs, justified_inputs, rho = INDEPENDENT_NORMAL_INPUTS, JUSTIFIED_INPUTS, PRICE_DEMAND_CORRELATION
    try:
        with st.expander("Distributions", expanded=True):
            if model == MODEL_NORMAL:
                st.markdown("**Price** — Normal")
                price = NormalParams(st.number_input("Mean (€)", value=INDEPENDENT_NORMAL_INPUTS.price.mean, key="p_m"),
                                     st.number_input("SD (€)", value=INDEPENDENT_NORMAL_INPUTS.price.sd, key="p_s"))
                st.markdown("**Volume** — Normal")
                volume = NormalParams(st.number_input("Mean (units)", value=INDEPENDENT_NORMAL_INPUTS.volume.mean, key="v_m"),
                                      st.number_input("SD (units)", value=INDEPENDENT_NORMAL_INPUTS.volume.sd, key="v_s"))
                st.markdown("**Variable cost** — Normal")
                cost = NormalParams(
                    st.number_input("Mean (€)", value=INDEPENDENT_NORMAL_INPUTS.variable_cost.mean, key="c_m"),
                    st.number_input("SD (€)", value=INDEPENDENT_NORMAL_INPUTS.variable_cost.sd, key="c_s"))
                normal_inputs = IndependentNormalInputs(price, volume, cost)
            else:
                st.markdown("**Price** — PERT")
                price = PertParams(st.number_input("Min (€)", value=JUSTIFIED_INPUTS.price.minimum),
                                   st.number_input("Mode (€)", value=JUSTIFIED_INPUTS.price.mode),
                                   st.number_input("Max (€)", value=JUSTIFIED_INPUTS.price.maximum))
                st.markdown("**Demand** — Normal, capped by capacity")
                demand = NormalParams(st.number_input("Mean (units)", value=JUSTIFIED_INPUTS.demand.mean),
                                      st.number_input("SD (units)", value=JUSTIFIED_INPUTS.demand.sd))
                st.markdown("**Variable cost** — Normal fitted on 8 historical data points")
                cost = NormalParams(st.number_input("Mean (€)", value=JUSTIFIED_INPUTS.variable_cost.mean, format="%.4f"),
                                    st.number_input("SD (€)", value=JUSTIFIED_INPUTS.variable_cost.sd, format="%.4f"))
                justified_inputs = JustifiedInputs(price, demand, cost)
                rho = st.slider("Price–Demand correlation (ρ)", -0.95, 0.95, PRICE_DEMAND_CORRELATION, 0.05)
    except ValueError as error:
        st.error(str(error))
        st.stop()

results = run_simulation(model, iterations, seed, project, normal_inputs, justified_inputs, rho)
values = results["npv"].to_numpy()
stats = summarize(values)
center = central_values(model, project, normal_inputs, justified_inputs)
center_npv = float(npv(**center, project=project))

# Key metrics
columns = st.columns(6)
columns[0].metric("Deterministic NPV", euros(center_npv), help="NPV with every input at its central value.")
columns[1].metric("Mean NPV", euros(stats["Mean NPV"]), help=f"SE of mean: {euros(stats['SE of mean'])}")
columns[2].metric("P5", euros(stats["P5"]), help="5% of scenarios give a lower NPV.")
columns[3].metric("P50", euros(stats["P50"]), help="Median NPV.")
columns[4].metric("P95", euros(stats["P95"]), help="5% of scenarios give a higher NPV.")
columns[5].metric("P(NPV < 0)", f"{stats['P(NPV < 0)']:.1%}",
                  help=f"SE of probability: {stats['SE of probability'] * 100:.2f} pt")
st.caption(
    f"{iterations:,} iterations · SD {euros(stats['Standard deviation'])} · "
    f"SE of mean {euros(stats['SE of mean'])} · SE of probability {stats['SE of probability'] * 100:.2f} pt. "
    "NPV < 0 means the project does not cover its cost of capital — not that it \"loses money\"."
)

tab_distribution, tab_tornado, tab_correlation, tab_export = st.tabs(
    ["Distribution", "Tornado chart", "Correlation", "Data & export"])

with tab_distribution:
    left, right = st.columns(2)
    left.subheader("NPV histogram")
    left.plotly_chart(histogram_figure(values, stats), width="stretch")
    right.subheader("Cumulative probability")
    right.plotly_chart(cdf_figure(values), width="stretch")

with tab_tornado:
    st.subheader("Which input drives the NPV most?")
    table = tornado_data(model, project, normal_inputs, justified_inputs)
    st.plotly_chart(tornado_figure(table, center_npv), width="stretch")
    st.caption(
        "Each bar: NPV when the input moves from its P5 to its P95, the other inputs staying at their central "
        "value (red = lower NPV, blue = higher NPV). This is a one-input-at-a-time analysis: it ranks the risks "
        "but ignores correlations, unlike the simulation."
    )
    st.dataframe(table.sort_values("Swing", ascending=False).style.format(
        {"Input P5": "{:,.2f}", "Input P95": "{:,.2f}", "NPV at P5": "€{:,.0f}",
         "NPV at P95": "€{:,.0f}", "Swing": "€{:,.0f}"}), hide_index=True, width="stretch")

with tab_correlation:
    if model == MODEL_NORMAL:
        st.info("The independent-normals model assumes independent inputs. Pick the justified-distributions "
                "model to correlate Price and Demand.")
    else:
        achieved = achieved_correlation(results)
        left, right = st.columns([1, 2])
        left.metric("Target correlation ρ", f"{rho:+.2f}")
        left.metric("Achieved correlation (Price, drawn Demand)", f"{achieved:+.3f}", delta=f"{achieved - rho:+.3f}",
                    delta_color="off")
        left.caption("Gap = sampling noise + slight attenuation from the PERT transformation. "
                     "The correlation is measured on drawn demand, before the capacity cap.")
        right.plotly_chart(scatter_figure(results), width="stretch")

with tab_export:
    st.subheader("Statistics")
    st.dataframe(stats.rename("Value").to_frame(), width="stretch")
    st.download_button("Download statistics (CSV)", stats.to_csv().encode("utf-8"),
                       file_name="npv_statistics.csv", mime="text/csv")
    exported = results.head(MAX_EXPORT_ROWS)
    st.download_button(f"Download scenarios (CSV, {len(exported):,} rows)",
                       exported.to_csv(index=False).encode("utf-8"), file_name="npv_scenarios.csv", mime="text/csv")
    if len(results) > MAX_EXPORT_ROWS:
        st.caption(f"Export limited to the first {MAX_EXPORT_ROWS:,} scenarios to keep the file size reasonable.")
    st.dataframe(results.head(1_000), width="stretch")
