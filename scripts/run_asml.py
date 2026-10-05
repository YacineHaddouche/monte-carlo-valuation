"""Monte Carlo valuation of ASML.

Run from the project root:  python scripts/run_asml.py
Outputs: tables printed in the terminal + CSV and PNG files in results/.
"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from mc_valuation.asml.assumptions import ASML_MARKET, CORRELATIONS_TO_COMPARE, REVENUE_MARGIN_CORRELATION
from mc_valuation.asml.model import free_cash_flows, value_per_share
from mc_valuation.asml.simulation import (
    central_values,
    implied_value,
    simulate_asml,
    summarize_valuation,
    tornado_table,
)
from mc_valuation.assumptions import DEFAULT_SEED

RESULTS_DIR = Path(__file__).resolve().parent.parent / "results"
ITERATIONS = 1_000_000
BLUE, RED, INK, MUTED, GRID = "#2a78d6", "#e34948", "#0b0b0b", "#898781", "#e1e0d9"

pd.set_option("display.width", 160)
pd.set_option("display.float_format", lambda value: f"{value:,.4f}" if abs(value) < 1 else f"{value:,.1f}")


def section(title: str) -> None:
    print(f"\n{'=' * 80}\n{title}\n{'=' * 80}")


def central_scenario() -> None:
    section("Central scenario (each driver at its mode or mean)")
    center = central_values()
    flows = free_cash_flows(center["revenue_2030"], center["gross_margin_2030"], center["opex_ratio"],
                            center["growth_2031_2035"])
    table = pd.DataFrame({key: values / 1e9 for key, values in flows.items() if key != "gross_margin"})
    table.insert(1, "gross margin", flows["gross_margin"])
    table.index = [str(year) for year in range(2026, 2026 + len(table))]
    print("Flows in €bn:")
    print(table.to_string())
    table.to_csv(RESULTS_DIR / "asml_central_cash_flows.csv")
    print(f"\nNet cash at 31 December 2025 (leases included): €{ASML_MARKET.net_cash / 1e9:,.2f}bn")
    print(f"Value per share, central scenario: €{float(value_per_share(**center)):,.0f} "
          f"(share price: €{ASML_MARKET.share_price:,.2f})")


def simulation() -> pd.DataFrame:
    section(f"Monte Carlo ({ITERATIONS:,} iterations, Revenue–Margin ρ = {REVENUE_MARGIN_CORRELATION:+.1f})")
    results = simulate_asml(ITERATIONS, DEFAULT_SEED, REVENUE_MARGIN_CORRELATION)
    stats = summarize_valuation(results["value_per_share"], ASML_MARKET.share_price)
    print(stats.to_string())
    stats.to_csv(RESULTS_DIR / "asml_summary.csv")
    return results


def correlation_effect() -> None:
    section("Effect of the Revenue–Gross margin correlation")
    rows = {}
    for rho in CORRELATIONS_TO_COMPARE:
        stats = summarize_valuation(simulate_asml(ITERATIONS, DEFAULT_SEED, rho)["value_per_share"],
                                    ASML_MARKET.share_price)
        rows[f"ρ = {rho:+.1f}"] = stats[["Mean value per share", "Standard deviation", "P5", "P95",
                                         "P(value < price)", "SE of probability"]]
    table = pd.DataFrame(rows)
    print(table.to_string())
    table.to_csv(RESULTS_DIR / "asml_correlation_comparison.csv")


def sensitivities() -> pd.DataFrame:
    section("Tornado: value per share when one driver moves from its P5 to its P95")
    table = tornado_table()
    print(table.to_string())
    table.to_csv(RESULTS_DIR / "asml_tornado.csv", index=False)

    section("What the share price implies (other drivers at their central value)")
    print(f"Implied revenue 2030: €{implied_value('revenue_2030', 40e9, 300e9) / 1e9:,.0f}bn")
    print(f"Implied revenue growth in 2031: {implied_value('growth_2031_2035', -0.05, 0.60):.1%}")
    print(f"Implied WACC: {implied_value('wacc', 0.03, 0.15):.2%}")
    return table


def style_axis(ax: plt.Axes) -> None:
    for spine in ("top", "right", "left"):
        ax.spines[spine].set_visible(False)
    ax.spines["bottom"].set_color(MUTED)
    ax.tick_params(colors=MUTED, labelsize=8)
    ax.set_axisbelow(True)


def plot(results: pd.DataFrame, tornado: pd.DataFrame) -> None:
    values = results["value_per_share"].to_numpy()
    price = ASML_MARKET.share_price
    fig, (ax_hist, ax_tornado) = plt.subplots(2, 1, figsize=(9, 8), gridspec_kw={"height_ratios": [3, 2]})

    # Histogram: in red, scenarios where intrinsic value is below the share price. The axis spans
    # P0.1–P99.9 and always includes the share price.
    lower = min(np.percentile(values, 0.1), price)
    upper = max(np.percentile(values, 99.9), price * 1.05)
    edges = np.linspace(lower, upper, 101)
    counts, edges = np.histogram(values, bins=edges)
    colors = np.where(edges[:-1] < price, RED, BLUE)
    ax_hist.bar(edges[:-1], counts / values.size, width=np.diff(edges) * 0.85, align="edge", color=colors)
    ax_hist.axvline(price, color=INK, linewidth=1.2)
    ax_hist.text(price, ax_hist.get_ylim()[1] * 0.95, f" Share price €{price:,.0f}", color=INK, fontsize=9,
                 ha="right")
    for key, value in zip(("P5", "P50", "P95"), np.percentile(values, [5, 50, 95])):
        ax_hist.axvline(value, color=MUTED, linewidth=1)
        ax_hist.text(value, ax_hist.get_ylim()[1] * 0.85, f" {key}", color=MUTED, fontsize=8)
    ax_hist.set_title(f"ASML intrinsic value per share   ·   P(value < share price) = {(values < price).mean():.1%}",
                      loc="left", fontsize=10, color=INK)
    ax_hist.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1, decimals=1))
    ax_hist.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda x, _: f"€{x:,.0f}"))
    ax_hist.grid(axis="y", color=GRID, linewidth=0.6)
    style_axis(ax_hist)

    # Tornado: bars from the central value to the value at each driver's P5 and P95.
    center_value = float(value_per_share(**central_values()))
    ordered = tornado.iloc[::-1]
    for column in ("Value at P5", "Value at P95"):
        deltas = ordered[column] - center_value
        ax_tornado.barh(ordered["Driver"], deltas, left=center_value, height=0.6,
                        color=np.where(deltas < 0, RED, BLUE))
    ax_tornado.axvline(center_value, color=MUTED, linewidth=1)
    ax_tornado.axvline(price, color=INK, linewidth=1.2)
    ax_tornado.text(center_value, len(ordered) - 0.5, f"central €{center_value:,.0f} ", color=MUTED, fontsize=8,
                    ha="right")
    ax_tornado.text(price, len(ordered) - 0.5, f" price €{price:,.0f}", color=INK, fontsize=8, ha="left")
    ax_tornado.set_title("Sensitivity: each driver from its P5 to its P95, others at the central scenario",
                         loc="left", fontsize=10, color=INK)
    ax_tornado.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda x, _: f"€{x:,.0f}"))
    ax_tornado.grid(axis="x", color=GRID, linewidth=0.6)
    style_axis(ax_tornado)
    ax_tornado.tick_params(axis="y", colors=INK)

    fig.tight_layout()
    fig.savefig(RESULTS_DIR / "asml_valuation.png", dpi=150)
    plt.close(fig)
    print(f"\nChart saved to {RESULTS_DIR / 'asml_valuation.png'}")


def main() -> None:
    RESULTS_DIR.mkdir(exist_ok=True)
    central_scenario()
    results = simulation()
    correlation_effect()
    tornado = sensitivities()
    plot(results, tornado)


if __name__ == "__main__":
    main()
