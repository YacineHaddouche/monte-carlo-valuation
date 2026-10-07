"""Monte Carlo simulation of ASML's value per share (Gaussian copula on the drivers)."""

from dataclasses import replace
from typing import Mapping

import numpy as np
import pandas as pd
from numpy.typing import ArrayLike
from scipy import optimize

from mc_valuation.asml.assumptions import (
    ASML_INPUTS,
    ASML_MARKET,
    ASML_OPERATIONS,
    FIRST_VERSION,
    MarketData,
    OperatingAssumptions,
    UncertainInputs,
)
from mc_valuation.asml.model import cost_of_capital, terminal_multiple, value_per_share
from mc_valuation.correlation import correlated_uniforms
from mc_valuation.distributions import PertMixture, PertParams, mixture_ppf, normal_ppf, pert_ppf

# Variable order in the correlation matrix.
DRIVERS = ("revenue_2030", "gross_margin_2030", "opex_ratio", "growth_2031", "terminal_growth",
           "risk_free", "beta", "equity_premium")
DRIVER_LABELS = {
    "revenue_2030": "Revenue 2030",
    "gross_margin_2030": "Gross margin 2030",
    "opex_ratio": "R&D + SG&A / sales",
    "growth_2031": "Revenue growth 2031 (fading to 2040)",
    "terminal_growth": "Perpetual growth",
    "risk_free": "Risk-free rate",
    "beta": "Beta",
    "equity_premium": "Equity risk premium",
    "wacc": "WACC",
}


def correlation_matrix(revenue_margin_correlation: float) -> np.ndarray:
    """Only the Revenue–Gross margin pair is correlated; the other drivers are independent."""
    matrix = np.eye(len(DRIVERS))
    i, j = DRIVERS.index("revenue_2030"), DRIVERS.index("gross_margin_2030")
    matrix[i, j] = matrix[j, i] = revenue_margin_correlation
    return matrix


def inverse_distribution(name: str, probabilities: np.ndarray, inputs: UncertainInputs) -> np.ndarray:
    """Applies a driver's inverse distribution (PERT mixture⁻¹, PERT⁻¹ or Normal⁻¹)."""
    params = getattr(inputs, name)
    if isinstance(params, PertMixture):
        return mixture_ppf(probabilities, params)
    if isinstance(params, PertParams):
        return pert_ppf(probabilities, params)
    return normal_ppf(probabilities, params)


def central_values(inputs: UncertainInputs = ASML_INPUTS) -> dict[str, float]:
    """Central value of each driver: the mode for a PERT (most likely regime for a mixture), the mean for a Normal."""
    return {name: getattr(getattr(inputs, name), "mode", getattr(inputs, name).mean) for name in DRIVERS}


def value_scenarios(
    drivers: Mapping[str, ArrayLike],
    operations: OperatingAssumptions = ASML_OPERATIONS,
    market: MarketData = ASML_MARKET,
) -> np.ndarray:
    """Value per share from a set of drivers. A "wacc" entry overrides Rf + β × ERP (used by the reverse DCF)."""
    wacc = drivers["wacc"] if "wacc" in drivers else cost_of_capital(
        drivers["risk_free"], drivers["beta"], drivers["equity_premium"])
    return value_per_share(drivers["revenue_2030"], drivers["gross_margin_2030"], drivers["opex_ratio"],
                           drivers["growth_2031"], drivers["terminal_growth"], wacc, operations, market)


def central_value(
    inputs: UncertainInputs = ASML_INPUTS,
    operations: OperatingAssumptions = ASML_OPERATIONS,
    market: MarketData = ASML_MARKET,
) -> float:
    """Value per share with every driver at its central value."""
    return float(value_scenarios(central_values(inputs), operations, market))


def simulate_asml(
    iterations: int,
    seed: int,
    revenue_margin_correlation: float,
    inputs: UncertainInputs = ASML_INPUTS,
    operations: OperatingAssumptions = ASML_OPERATIONS,
    market: MarketData = ASML_MARKET,
) -> pd.DataFrame:
    """Draws the 8 drivers through a Gaussian copula and values each scenario per share."""
    rng = np.random.default_rng(seed)
    uniforms = correlated_uniforms(correlation_matrix(revenue_margin_correlation), iterations, rng)
    results = pd.DataFrame({name: inverse_distribution(name, uniforms[:, k], inputs) for k, name in enumerate(DRIVERS)})
    results["wacc"] = cost_of_capital(results["risk_free"], results["beta"], results["equity_premium"])
    results["terminal_multiple"] = terminal_multiple(results["wacc"], results["terminal_growth"], operations)
    results["value_per_share"] = value_scenarios(results, operations, market)
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


def regime_table(
    iterations: int,
    seed: int,
    revenue_margin_correlation: float,
    inputs: UncertainInputs = ASML_INPUTS,
    operations: OperatingAssumptions = ASML_OPERATIONS,
    market: MarketData = ASML_MARKET,
) -> pd.DataFrame:
    """Simulation run separately within each 2030 revenue regime (all other drivers unchanged)."""
    mixture = inputs.revenue_2030
    rows = []
    for name, weight, component in zip(mixture.names, mixture.weights, mixture.components):
        single = replace(inputs, revenue_2030=PertMixture((component,), (1.0,), (name,)))
        values = simulate_asml(iterations, seed, revenue_margin_correlation, single, operations, market)["value_per_share"]
        rows.append({"Regime": name, "Probability": weight,
                     "Revenue 2030 (€bn)": f"{component.minimum / 1e9:.0f} / {component.mode / 1e9:.0f} / "
                                           f"{component.maximum / 1e9:.0f}",
                     "Mean value per share": values.mean(), "P(value < price)": (values < market.share_price).mean()})
    return pd.DataFrame(rows)


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
        value_low = float(value_scenarios({**center, name: low}, operations, market))
        value_high = float(value_scenarios({**center, name: high}, operations, market))
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
    """Value of one driver (or of the WACC as a whole) that exactly justifies the share price, others central.

    `optimize.brentq` finds the root of the function between `lower` and `upper` (a bisection-like method).
    """
    center = central_values(inputs)

    def gap(x: float) -> float:
        return float(value_scenarios({**center, driver: x}, operations, market)) - market.share_price

    return optimize.brentq(gap, lower, upper)


def model_bridge(
    inputs: UncertainInputs = ASML_INPUTS,
    operations: OperatingAssumptions = ASML_OPERATIONS,
    market: MarketData = ASML_MARKET,
) -> pd.DataFrame:
    """Central value per share, from the first version of the model to the current one, one change at a time."""
    first = FIRST_VERSION["operations"]
    old = FIRST_VERSION["central_drivers"]
    center = central_values(inputs)
    current_wacc = float(cost_of_capital(center["risk_free"], center["beta"], center["equity_premium"]))
    steps = [
        ("First version: 10-year DCF, Gordon growth on the 2035 FCF, WACC 9.0%", old, first),
        ("Fade period extended to 2040 (three-stage DCF)", old, replace(first, horizon_years=operations.horizon_years)),
        (f"Terminal value by the value-driver formula (RONIC {operations.terminal_ronic:.0%})", old,
         replace(operations, terminal_method="value_driver")),
        (f"WACC built from Rf + β × ERP: {current_wacc:.2%}", {**old, "wacc": current_wacc},
         replace(operations, terminal_method="value_driver")),
        ("Current central drivers", {**center, "wacc": current_wacc}, operations),
    ]
    rows, previous = [], None
    for label, drivers, step_operations in steps:
        value = float(value_scenarios(drivers, step_operations, market))
        rows.append({"Step": label, "Value per share": value,
                     "Change": np.nan if previous is None else value - previous})
        previous = value
    return pd.DataFrame(rows)
