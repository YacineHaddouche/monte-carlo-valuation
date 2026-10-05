"""Python vs Excel validation: can the gaps be explained by sampling noise alone?"""

import numpy as np
import pandas as pd

from mc_valuation.assumptions import CORRELATIONS_TO_COMPARE, PRICE_DEMAND_CORRELATION
from mc_valuation.simulation import (
    achieved_correlation,
    simulate_correlated,
    simulate_independent_normals,
    simulate_justified,
)
from mc_valuation.summary import summarize

INDEPENDENT = "Independent normals"
JUSTIFIED = "Justified distributions"
CORRELATED = "Correlated (ρ = −0.5)"

# Excel reference results (5,000 iterations, a single recalculation).
EXCEL_ITERATIONS = 5_000
EXCEL_REFERENCE: dict[str, dict[str, float]] = {
    INDEPENDENT: {
        "Mean NPV": 35_631, "Standard deviation": 203_846, "P5": -285_522, "P50": 27_305,
        "P95": 386_160, "P(NPV < 0)": 0.442, "SE of probability": 0.0070, "SE of mean": 2_883,
    },
    JUSTIFIED: {
        "Mean NPV": -8_871, "Standard deviation": 149_663, "P5": -256_754, "P50": -9_112,
        "P95": 234_141, "P(NPV < 0)": 0.526, "SE of probability": 0.0071, "SE of mean": 2_117,
    },
    CORRELATED: {
        "Mean NPV": -14_171, "Standard deviation": 119_830, "P5": -209_469, "P50": -12_837,
        "P95": 185_689, "P(NPV < 0)": 0.547, "SE of probability": 0.0070, "SE of mean": 1_695,
    },
}

# Excel comparison of three values of ρ.
EXCEL_CORRELATION_COMPARISON: dict[float, dict[str, float]] = {
    -0.5: {"Mean NPV": -16_704, "Standard deviation": 117_181, "P(NPV < 0)": 0.562, "Correlation check": -0.51},
    0.0: {"Mean NPV": -14_735, "Standard deviation": 147_353, "P(NPV < 0)": 0.541, "Correlation check": 0.01},
    0.5: {"Mean NPV": -10_357, "Standard deviation": 172_201, "P(NPV < 0)": 0.515, "Correlation check": 0.48},
}

# Test threshold: |z| < 2 ⇔ gap consistent with chance at roughly 95% confidence.
Z_THRESHOLD = 2.0


def run_model(model: str, iterations: int, seed: int) -> pd.DataFrame:
    """Runs the simulation that matches a model name."""
    if model == INDEPENDENT:
        return simulate_independent_normals(iterations, seed)
    if model == JUSTIFIED:
        return simulate_justified(iterations, seed)
    if model == CORRELATED:
        return simulate_correlated(iterations, seed, PRICE_DEMAND_CORRELATION)
    raise ValueError(f"Unknown model: {model}")


def z_score(value_a: float, se_a: float, value_b: float, se_b: float) -> float:
    """Gap between two independent estimates, measured in combined standard errors."""
    return (value_a - value_b) / np.sqrt(se_a**2 + se_b**2)


def validation_table(model: str, iterations_list: tuple[int, ...], seed: int) -> pd.DataFrame:
    """Excel vs Python table for one model, with z-scores for the mean NPV and for P(NPV < 0)."""
    excel = pd.Series(EXCEL_REFERENCE[model], name="Excel (5,000)")
    columns = [excel]
    z_rows = []
    for iterations in iterations_list:
        python = summarize(run_model(model, iterations, seed)["npv"])
        columns.append(python.drop("Iterations").rename(f"Python ({iterations:,})"))
        z_rows.append(
            {
                "Iterations": iterations,
                "z Mean NPV": z_score(python["Mean NPV"], python["SE of mean"],
                                      excel["Mean NPV"], excel["SE of mean"]),
                "z P(NPV < 0)": z_score(python["P(NPV < 0)"], python["SE of probability"],
                                        excel["P(NPV < 0)"], excel["SE of probability"]),
            }
        )
    table = pd.concat(columns, axis=1)
    z_table = pd.DataFrame(z_rows).set_index("Iterations")
    z_table["Consistent (|z| < 2)"] = (z_table.abs() < Z_THRESHOLD).all(axis=1)
    table.attrs["z_scores"] = z_table
    return table


def correlation_comparison(iterations: int, seed: int) -> pd.DataFrame:
    """Effect of ρ on the NPV distribution (same seed for every ρ)."""
    rows = {}
    for rho in CORRELATIONS_TO_COMPARE:
        results = simulate_correlated(iterations, seed, rho)
        stats = summarize(results["npv"])
        rows[f"ρ = {rho:+.1f}"] = {
            "Mean NPV": stats["Mean NPV"],
            "SE of mean": stats["SE of mean"],
            "Standard deviation": stats["Standard deviation"],
            "P(NPV < 0)": stats["P(NPV < 0)"],
            "SE of probability": stats["SE of probability"],
            "Correlation check": achieved_correlation(results),
        }
    return pd.DataFrame(rows)


def correlation_effect_on_mean(comparison: pd.DataFrame) -> pd.Series:
    """Mean NPV gap between ρ = −0.5 and ρ = 0, with its z-score (combined SEs, a conservative test)."""
    negative, zero = comparison["ρ = -0.5"], comparison["ρ = +0.0"]
    difference = negative["Mean NPV"] - zero["Mean NPV"]
    combined_se = np.sqrt(negative["SE of mean"] ** 2 + zero["SE of mean"] ** 2)
    return pd.Series({"Difference": difference, "SE of difference": combined_se,
                      "z": difference / combined_se})
