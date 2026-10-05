"""Validates the Python model against Excel and produces the figures for the analysis questions.

Run from the project root:  python scripts/run_validation.py
Outputs: tables printed in the terminal + CSV and PNG files in results/.
"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # render images without opening a window
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from mc_valuation.assumptions import BASE_CASE, DEFAULT_SEED, JUSTIFIED_INPUTS
from mc_valuation.correlation import validate_correlation_matrix
from mc_valuation.model import break_even_price, break_even_volume, npv
from mc_valuation.simulation import simulate_correlated, simulate_independent_normals, simulate_justified
from mc_valuation.validation import (
    EXCEL_CORRELATION_COMPARISON,
    EXCEL_REFERENCE,
    correlation_comparison,
    correlation_effect_on_mean,
    validation_table,
)

RESULTS_DIR = Path(__file__).resolve().parent.parent / "results"
ITERATIONS = (5_000, 1_000_000)
FILE_SLUGS = {"Independent normals": "independent", "Justified distributions": "justified",
              "Correlated (ρ = −0.5)": "correlated"}

# Chart colours: blue = NPV >= 0, red = NPV < 0 (diverging pair).
POSITIVE_COLOR, NEGATIVE_COLOR, INK, MUTED, GRID = "#2a78d6", "#e34948", "#0b0b0b", "#898781", "#e1e0d9"

pd.set_option("display.width", 160)
pd.set_option("display.float_format", lambda value: f"{value:,.4f}" if abs(value) < 10 else f"{value:,.0f}")


def section(title: str) -> None:
    print(f"\n{'=' * 80}\n{title}\n{'=' * 80}")


def deterministic_check() -> None:
    section("Deterministic model")
    base_npv = float(npv(BASE_CASE.price, BASE_CASE.volume, BASE_CASE.variable_cost))
    price, volume = break_even_price(), break_even_volume()
    print(f"Base-case NPV: €{base_npv:,.2f}  (expected €33,973.09)")
    print(f"Break-even price: €{price:.2f} ({price / BASE_CASE.price - 1:+.1%})")
    print(f"Break-even volume: {volume:,.0f} units ({volume / BASE_CASE.volume - 1:+.1%})")


def validation_tables() -> None:
    for model in EXCEL_REFERENCE:
        section(f"{model} — Excel vs Python")
        table = validation_table(model, ITERATIONS, DEFAULT_SEED)
        print(table.to_string())
        print("\nz-scores (gap / combined SE):")
        print(table.attrs["z_scores"].to_string())
        slug = FILE_SLUGS[model]
        table.to_csv(RESULTS_DIR / f"validation_{slug}.csv")
        table.attrs["z_scores"].to_csv(RESULTS_DIR / f"validation_{slug}_zscores.csv")


def correlation_tables() -> None:
    section("Effect of ρ: Excel (5,000)")
    print(pd.DataFrame(EXCEL_CORRELATION_COMPARISON).rename(columns=lambda rho: f"ρ = {rho:+.1f}").to_string())
    for iterations in ITERATIONS:
        section(f"Effect of ρ: Python ({iterations:,})")
        comparison = correlation_comparison(iterations, DEFAULT_SEED)
        print(comparison.to_string())
        effect = correlation_effect_on_mean(comparison)
        print(
            f"\nMean NPV(ρ = −0.5) − Mean NPV(ρ = 0) = €{effect['Difference']:,.0f} "
            f"(SE €{effect['SE of difference']:,.0f}, z = {effect['z']:.1f}) → "
            f"{'significant' if abs(effect['z']) >= 2 else 'not significant'} at the |z| ≥ 2 threshold"
        )
        comparison.to_csv(RESULTS_DIR / f"correlation_comparison_{iterations}.csv")


def impossible_matrix_check() -> None:
    section("Impossible correlation matrix")
    matrix = np.array([[1.0, -0.9, 0.9], [-0.9, 1.0, 0.9], [0.9, 0.9, 1.0]])
    print(f"Eigenvalues: {np.round(np.linalg.eigvalsh(matrix), 4)}")
    print(f"Determinant: {np.linalg.det(matrix):.4f}")
    try:
        np.linalg.cholesky(matrix)
    except np.linalg.LinAlgError as error:
        print(f"np.linalg.cholesky raises LinAlgError: \"{error}\"")
    try:
        validate_correlation_matrix(matrix)
    except ValueError as error:
        print(f"Our validation: {error}")


def plot_histograms() -> None:
    """NPV histogram for each model (1,000,000 iterations), NPV < 0 in red."""
    simulations = {
        "Three independent normals": simulate_independent_normals(1_000_000, DEFAULT_SEED),
        "Justified distributions: PERT, capacity cap, fitted data": simulate_justified(1_000_000, DEFAULT_SEED),
        "Gaussian copula, ρ = −0.5": simulate_correlated(1_000_000, DEFAULT_SEED, -0.5),
    }
    bins = np.linspace(-700_000, 800_000, 121)
    fig, axes = plt.subplots(3, 1, figsize=(9, 9), sharex=True)
    for ax, (title, results) in zip(axes, simulations.items()):
        values = results["npv"].to_numpy()
        counts, edges = np.histogram(values, bins=bins)
        colors = np.where(edges[:-1] < 0, NEGATIVE_COLOR, POSITIVE_COLOR)
        ax.bar(edges[:-1], counts / counts.sum(), width=np.diff(edges) * 0.85, align="edge", color=colors)
        p5, p50, p95 = np.percentile(values, [5, 50, 95])
        for value, label in ((p5, "P5"), (p50, "P50"), (p95, "P95")):
            ax.axvline(value, color=MUTED, linewidth=1)
            ax.text(value, ax.get_ylim()[1] * 0.92, f" {label}", color=MUTED, fontsize=8)
        ax.set_title(f"{title}   ·   P(NPV < 0) = {(values < 0).mean():.1%}", loc="left", fontsize=10, color=INK)
        ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1, decimals=1))
        ax.grid(axis="y", color=GRID, linewidth=0.6)
        ax.set_axisbelow(True)
        for spine in ("top", "right", "left"):
            ax.spines[spine].set_visible(False)
        ax.spines["bottom"].set_color(MUTED)
        ax.tick_params(colors=MUTED, labelsize=8)
    axes[-1].xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda x, _: f"€{x / 1000:,.0f}k"))
    axes[-1].set_xlabel("NPV", color=MUTED)
    fig.tight_layout()
    fig.savefig(RESULTS_DIR / "npv_histograms.png", dpi=150)
    plt.close(fig)
    print(f"\nHistograms saved to {RESULTS_DIR / 'npv_histograms.png'}")


def main() -> None:
    RESULTS_DIR.mkdir(exist_ok=True)
    deterministic_check()
    print(f"\nVariable cost fitted on data: mean {JUSTIFIED_INPUTS.variable_cost.mean:.4f}, "
          f"sample SD {JUSTIFIED_INPUTS.variable_cost.sd:.4f}")
    validation_tables()
    correlation_tables()
    impossible_matrix_check()
    plot_histograms()


if __name__ == "__main__":
    main()
