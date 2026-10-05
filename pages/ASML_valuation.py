"""ASML page: Monte Carlo valuation with pre-filled, editable assumptions."""

from dataclasses import replace

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from mc_valuation.asml.assumptions import (
    ASML_DEFAULT_ITERATIONS,
    ASML_INPUTS,
    ASML_MARKET,
    ASML_OPERATIONS,
    REVENUE_MARGIN_CORRELATION,
    MarketData,
    OperatingAssumptions,
    UncertainInputs,
)
from mc_valuation.asml.model import free_cash_flows, value_per_share
from mc_valuation.asml.simulation import (
    DRIVER_LABELS,
    central_values,
    implied_value,
    simulate_asml,
    summarize_valuation,
    tornado_table,
)
from mc_valuation.assumptions import DEFAULT_SEED
from mc_valuation.distributions import NormalParams, PertParams

# Capped at 200,000 to stay within the hosted app's memory (run scripts/run_asml.py for one million).
ITERATION_CHOICES = [1_000, 10_000, 50_000, 100_000, 200_000]
BLUE, RED, MUTED, INK = "#2a78d6", "#e34948", "#898781", "#52514e"


@st.cache_data(show_spinner="Running simulation…", max_entries=3)
def run(iterations: int, seed: int, rho: float, inputs: UncertainInputs, operations: OperatingAssumptions,
        market: MarketData) -> pd.DataFrame:
    return simulate_asml(iterations, seed, rho, inputs, operations, market)


def pert_inputs(label: str, params: PertParams, scale: float, step: float, fmt: str, key: str) -> PertParams:
    """Three fields (min / mode / max); `scale` converts the displayed unit (e.g. % or €bn) to the model's unit."""
    st.markdown(f"**{label}** — PERT")
    cols = st.columns(3)
    values = [cols[i].number_input(name, value=getattr(params, attr) * scale, step=step, format=fmt, key=f"{key}_{attr}")
              / scale for i, (name, attr) in enumerate((("Min", "minimum"), ("Mode", "mode"), ("Max", "maximum")))]
    return PertParams(*values)


st.set_page_config(page_title="ASML — Monte Carlo", page_icon="🔬", layout="wide")
st.title("ASML: value per share by Monte Carlo")
st.caption(
    "10-year DCF + terminal value, with five uncertain drivers drawn simultaneously (Gaussian copula). "
    "Data: ASML Annual Report 2025 (US GAAP), Q2 2026 guidance, Euronext close on 2 October 2026."
)

with st.sidebar:
    st.header("Settings")
    iterations = st.select_slider("Iterations", ITERATION_CHOICES, value=ASML_DEFAULT_ITERATIONS,
                                  format_func=lambda n: f"{n:,}")
    seed = int(st.number_input("Seed", min_value=0, value=DEFAULT_SEED, step=1))
    rho = st.slider("Revenue–Gross margin correlation (ρ)", -0.9, 0.9, REVENUE_MARGIN_CORRELATION, 0.1)
    try:
        with st.expander("Uncertain drivers", expanded=True):
            inputs = UncertainInputs(
                revenue_2030=pert_inputs("Revenue 2030 (€bn)", ASML_INPUTS.revenue_2030, 1e-9, 1.0, "%.0f", "r"),
                gross_margin_2030=pert_inputs("Gross margin 2030 (%)", ASML_INPUTS.gross_margin_2030,
                                              100, 0.5, "%.1f", "m"),
                opex_ratio=NormalParams(
                    st.number_input("R&D + SG&A / sales, mean (%)", value=ASML_INPUTS.opex_ratio.mean * 100,
                                    step=0.5) / 100,
                    st.number_input("R&D + SG&A / sales, SD (%)", value=ASML_INPUTS.opex_ratio.sd * 100,
                                    step=0.25) / 100),
                growth_2031_2035=pert_inputs("Revenue growth 2031, fading to 2035 (%)",
                                             ASML_INPUTS.growth_2031_2035, 100, 0.5, "%.1f", "g"),
                wacc=NormalParams(
                    st.number_input("WACC, mean (%)", value=ASML_INPUTS.wacc.mean * 100, step=0.25) / 100,
                    st.number_input("WACC, SD (%)", value=ASML_INPUTS.wacc.sd * 100, step=0.25) / 100),
            )
        with st.expander("Operating assumptions"):
            operations = replace(
                ASML_OPERATIONS,
                revenue_first_year=st.number_input("Revenue 2026 (€bn)", value=ASML_OPERATIONS.revenue_first_year / 1e9,
                                                   step=0.5) * 1e9,
                tax_rate=st.number_input("Tax rate (%)", value=ASML_OPERATIONS.tax_rate * 100, step=0.5) / 100,
                capex_rate=st.number_input("Capex / sales (%)", value=ASML_OPERATIONS.capex_rate * 100,
                                           step=0.5) / 100,
                terminal_growth=st.number_input("Perpetual growth (%)",
                                                value=ASML_OPERATIONS.terminal_growth * 100, step=0.25) / 100,
            )
        with st.expander("Market and balance sheet"):
            market = replace(
                ASML_MARKET,
                share_price=st.number_input("Share price (€)", value=ASML_MARKET.share_price, step=10.0),
            )
            st.caption(f"Net cash at 31 Dec 2025 (cash − debt − leases): €{market.net_cash / 1e9:,.2f}bn · "
                       f"{market.shares_outstanding / 1e6:,.1f}m shares")
    except ValueError as error:
        st.error(str(error))
        st.stop()

if inputs.wacc.mean - 4 * inputs.wacc.sd <= operations.terminal_growth:
    st.error("Drawn WACC values could fall below perpetual growth: raise the mean or lower the standard deviation.")
    st.stop()

results = run(iterations, seed, rho, inputs, operations, market)
values = results["value_per_share"].to_numpy()
stats = summarize_valuation(values, market.share_price)
center = central_values(inputs)
center_value = float(value_per_share(**center, operations=operations, market=market))

cols = st.columns(6)
cols[0].metric("Share price", f"€{market.share_price:,.0f}")
cols[1].metric("Value, central scenario", f"€{center_value:,.0f}", help="Each driver at its mode (PERT) or mean (Normal).")
cols[2].metric("Mean value per share", f"€{stats['Mean value per share']:,.0f}",
               help=f"SE of mean: €{stats['SE of mean']:.2f}")
cols[3].metric("P50", f"€{stats['P50']:,.0f}")
cols[4].metric("P5 / P95", f"€{stats['P5']:,.0f} / €{stats['P95']:,.0f}")
cols[5].metric("P(value < price)", f"{stats['P(value < price)']:.1%}",
               help=f"SE of probability: {stats['SE of probability'] * 100:.2f} pt")
st.caption(f"{iterations:,} iterations · value per share at 31 December 2025, rolled forward to the share-price "
           "date at the cost of capital, minus the dividends paid since.")

tab_distribution, tab_tornado, tab_implied, tab_flows = st.tabs(
    ["Distribution", "Tornado chart", "What the price implies", "Central-scenario cash flows"])

with tab_distribution:
    lower = min(np.percentile(values, 0.1), market.share_price)
    upper = max(np.percentile(values, 99.9), market.share_price * 1.05)
    edges = np.linspace(lower, upper, 101)
    counts, edges = np.histogram(values, bins=edges)
    fig = go.Figure(go.Bar(
        x=(edges[:-1] + edges[1:]) / 2, y=counts / values.size, width=np.diff(edges) * 0.9,
        marker_color=np.where(edges[:-1] < market.share_price, RED, BLUE),
        customdata=np.column_stack([edges[:-1], edges[1:]]),
        hovertemplate="Value between €%{customdata[0]:,.0f} and €%{customdata[1]:,.0f}<br>"
                      "%{y:.2%} of scenarios<extra></extra>",
    ))
    fig.add_vline(x=market.share_price, line_width=2, line_color=INK,
                  annotation_text=f"Price €{market.share_price:,.0f}", annotation_position="top left")
    for key in ("P5", "P50", "P95"):
        fig.add_vline(x=stats[key], line_width=1, line_color=MUTED, annotation_text=key,
                      annotation_position="top right", annotation_font_color=MUTED)
    fig.update_layout(height=420, margin=dict(t=30, b=10, l=10, r=10), showlegend=False,
                      xaxis_title="Value per share (€) — red: below the share price, blue: above",
                      yaxis_title="Share of scenarios")
    fig.update_xaxes(tickformat=",.0f")
    fig.update_yaxes(tickformat=".1%")
    st.plotly_chart(fig, width="stretch")

with tab_tornado:
    table = tornado_table(inputs, operations, market)
    ordered = table.iloc[::-1]
    fig = go.Figure()
    for column in ("Value at P5", "Value at P95"):
        deltas = ordered[column] - center_value
        fig.add_trace(go.Bar(y=ordered["Driver"], x=deltas, base=center_value, orientation="h",
                             marker_color=np.where(deltas < 0, RED, BLUE), customdata=ordered[column],
                             hovertemplate="%{y}<br>" + column + ": €%{customdata:,.0f}<extra></extra>"))
    fig.add_vline(x=center_value, line_width=1, line_color=MUTED, annotation_text="central",
                  annotation_position="top left")
    fig.add_vline(x=market.share_price, line_width=2, line_color=INK, annotation_text="price",
                  annotation_position="top right")
    fig.update_layout(barmode="overlay", height=360, margin=dict(t=30, b=10, l=10, r=10), showlegend=False,
                      xaxis_title="Value per share (€)")
    fig.update_xaxes(tickformat=",.0f")
    st.plotly_chart(fig, width="stretch")
    st.caption("Each driver moves from its P5 to its P95, the others staying at the central scenario "
               "(red = lower value, blue = higher value). One driver at a time, without correlation.")
    shown = table.copy()
    for column in ("Driver P5", "Driver P95"):
        shown[column] = [f"€{v / 1e9:,.1f}bn" if v > 1e6 else f"{v:.1%}" for v in shown[column]]
    st.dataframe(shown.style.format({"Value at P5": "€{:,.0f}", "Value at P95": "€{:,.0f}", "Swing": "€{:,.0f}"}),
                 hide_index=True, width="stretch")

with tab_implied:
    st.subheader("Which value of each driver exactly justifies the share price?")
    searches = {
        "revenue_2030": (20e9, 400e9, lambda v: f"€{v / 1e9:,.0f}bn"),
        "growth_2031_2035": (-0.10, 0.80, lambda v: f"{v:.1%}"),
        "wacc": (operations.terminal_growth + 0.001, 0.30, lambda v: f"{v:.2%}"),
    }
    rows = []
    for driver, (lower_bound, upper_bound, fmt) in searches.items():
        try:
            implied = fmt(implied_value(driver, lower_bound, upper_bound, inputs, operations, market))
        except ValueError:
            implied = "outside the search range"
        rows.append({"Driver": DRIVER_LABELS[driver], "Central value": fmt(center[driver]), "Implied value": implied})
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
    st.caption("Reverse DCF: `scipy.optimize.brentq` searches for the driver value that equates the value per share "
               "with the share price, the other drivers staying at their central value.")

with tab_flows:
    flows = free_cash_flows(center["revenue_2030"], center["gross_margin_2030"], center["opex_ratio"],
                            center["growth_2031_2035"], operations)
    table = pd.DataFrame({"Revenue (€bn)": flows["revenue"] / 1e9,
                          "Gross margin": flows["gross_margin"],
                          "EBIT (€bn)": flows["ebit"] / 1e9,
                          "Taxes (€bn)": flows["taxes"] / 1e9,
                          "Capex (€bn)": flows["capex"] / 1e9,
                          "Working capital (€bn)": flows["working_capital"] / 1e9,
                          "FCF (€bn)": flows["fcf"] / 1e9},
                         index=[str(year) for year in range(2026, 2026 + operations.horizon_years)])
    st.dataframe(table.style.format("{:,.2f}").format("{:.1%}", subset=["Gross margin"]), width="stretch")
    st.download_button("Download scenarios (CSV, first 100,000 rows)",
                       results.head(100_000).to_csv(index=False).encode("utf-8"),
                       file_name="asml_scenarios.csv", mime="text/csv")
