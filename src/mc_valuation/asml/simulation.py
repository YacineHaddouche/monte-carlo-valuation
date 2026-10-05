"""Monte Carlo simulation of ASML's value per share (Gaussian copula on the drivers)."""

import numpy as np
import pandas as pd
from scipy import optimize

from mc_valuation.asml.assumptions import (
    ASML_INPUTS,
    ASML_MARKET,
    ASML_OPERATIONS,
    MarketData,
    OperatingAssumptions,
    UncertainInputs,
)
from mc_valuation.asml.model import value_per_share
from mc_valuation.correlation import correlated_uniforms
from mc_valuation.distributions import normal_ppf, pert_ppf

# Variable order in the correlation matrix.
DRIVERS = ("revenue_2030", "gross_margin_2030", "opex_ratio", "growth_2031_2035", "wacc")
DRIVER_LABELS = {
    "revenue_2030": "Revenue 2030",
    "gross_margin_2030": "Gross margin 2030",
    "opex_ratio": "R&D + SG&A / sales",
    "growth_2031_2035": "Revenue growth 2031 (fading)",
    "wacc": "WACC",
}


def correlation_matrix(revenue_margin_correlation: float) -> np.ndarray:
    """5×5 matrix: only the Revenue–Gross margin pair is correlated, the other drivers are independent."""
    matrix = np.eye(len(DRIVERS))
    i, j = DRIVERS.index("revenue_2030"), DRIVERS.index("gross_margin_2030")
    matrix[i, j] = matrix[j, i] = revenue_margin_correlation
    return matrix


def inverse_distribution(name: str, probabilities: np.ndarray, inputs: UncertainInputs) -> np.ndarray:
    """Applies a driver's inverse distribution (PERT⁻¹ or Normal⁻¹)."""
    params = getattr(inputs, name)
    if hasattr(params, "mode"):
        return pert_ppf(probabilities, params)
    return normal_ppf(probabilities, params)


def central_values(inputs: UncertainInputs = ASML_INPUTS) -> dict[str, float]:
    """Central value of each driver: the mode for a PERT, the mean for a Normal."""
    return {name: getattr(getattr(inputs, name), "mode", getattr(inputs, name).mean) for name in DRIVERS}


def simulate_asml(
    iterations: int,
    seed: int,
    revenue_margin_correlation: float,
    inputs: UncertainInputs = ASML_INPUTS,
    operations: OperatingAssumptions = ASML_OPERATIONS,
    market: MarketData = ASML_MARKET,
) -> pd.DataFrame:
    """Draws the 5 drivers through a Gaussian copula and values each scenario per share."""
    rng = np.random.default_rng(seed)
    uniforms = correlated_uniforms(correlation_matrix(revenue_margin_correlation), iterations, rng)
    draws = {name: inverse_distribution(name, uniforms[:, k], inputs) for k, name in enumerate(DRIVERS)}
    results = pd.DataFrame(draws)
    results["value_per_share"] = value_per_share(**draws, operations=operations, market=market)
    return results


def summarize_valuation(values: np.ndarray, share_price: float) -> pd.Series:
    """Statistics of the value per share and probability that it is below the share price."""
    values = np.asarray(values, dtype=float)
    n = values.size
    sd = values.std(ddof=1)
    p5, p50, p95 = np.percentile(values, [5, 50, 95])
    prob_below = float((values < share_price).mean())
    return pd.Series({
        "Iterations": n,
        "Mean value per share": values.mean(),
        "Standard deviation": sd,
        "P5": p5,
        "P50": p50,
        "P95": p95,
        "Share price": share_price,
        "P(value < price)": prob_below,
        "SE of probability": np.sqrt(prob_below * (1 - prob_below) / n),
        "SE of mean": sd / np.sqrt(n),
    })


def tornado_table(
    inputs: UncertainInputs = ASML_INPUTS,
    operations: OperatingAssumptions = ASML_OPERATIONS,
    market: MarketData = ASML_MARKET,
) -> pd.DataFrame:
    """Value per share when one driver moves from its P5 to its P95, the others staying central."""
    center = central_values(inputs)
    rows = []
    for name in DRIVERS:
        low, high = inverse_distribution(name, np.array([0.05, 0.95]), inputs)
        value_low = float(value_per_share(**{**center, name: low}, operations=operations, market=market))
        value_high = float(value_per_share(**{**center, name: high}, operations=operations, market=market))
        rows.append({"Driver": DRIVER_LABELS[name], "Driver P5": low, "Driver P95": high,
                     "Value at P5": value_low, "Value at P95": value_high,
                     "Swing": abs(value_high - value_low)})
    return pd.DataFrame(rows).sort_values("Swing", ascending=False, ignore_index=True)


def implied_value(
    driver: str,
    lower: float,
    upper: float,
    inputs: UncertainInputs = ASML_INPUTS,
    operations: OperatingAssumptions = ASML_OPERATIONS,
    market: MarketData = ASML_MARKET,
) -> float:
    """Value of one driver that exactly justifies the share price, the others staying central.

    `optimize.brentq` finds the root of the function between `lower` and `upper` (a bisection-like method).
    """
    center = central_values(inputs)

    def gap(x: float) -> float:
        return float(value_per_share(**{**center, driver: x}, operations=operations, market=market)) - market.share_price

    return optimize.brentq(gap, lower, upper)
