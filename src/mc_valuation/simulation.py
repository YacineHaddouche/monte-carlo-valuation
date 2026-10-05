"""Vectorised Monte Carlo simulations: one array per variable, no loop over iterations."""

import numpy as np
import pandas as pd

from mc_valuation.assumptions import (
    BASE_CASE,
    INDEPENDENT_NORMAL_INPUTS,
    JUSTIFIED_INPUTS,
    IndependentNormalInputs,
    JustifiedInputs,
    ProjectAssumptions,
)
from mc_valuation.correlation import correlated_uniforms, price_demand_correlation_matrix
from mc_valuation.distributions import normal_ppf, pert_ppf, sample_normal, sample_pert
from mc_valuation.model import npv


def simulate_independent_normals(
    iterations: int,
    seed: int,
    inputs: IndependentNormalInputs = INDEPENDENT_NORMAL_INPUTS,
    project: ProjectAssumptions = BASE_CASE,
) -> pd.DataFrame:
    """Independent model: Price, Volume and Variable cost drawn from three independent Normal distributions."""
    rng = np.random.default_rng(seed)
    price = sample_normal(inputs.price, iterations, rng)
    volume = sample_normal(inputs.volume, iterations, rng)
    variable_cost = sample_normal(inputs.variable_cost, iterations, rng)
    return pd.DataFrame(
        {
            "price": price,
            "volume": volume,
            "variable_cost": variable_cost,
            "npv": npv(price, volume, variable_cost, project),
        }
    )


def simulate_justified(
    iterations: int,
    seed: int,
    inputs: JustifiedInputs = JUSTIFIED_INPUTS,
    project: ProjectAssumptions = BASE_CASE,
) -> pd.DataFrame:
    """Justified model: PERT Price, Normal Demand capped by capacity, Variable cost fitted on data."""
    rng = np.random.default_rng(seed)
    price = sample_pert(inputs.price, iterations, rng)
    demand = sample_normal(inputs.demand, iterations, rng)
    variable_cost = sample_normal(inputs.variable_cost, iterations, rng)
    volume = np.minimum(demand, project.capacity)  # cannot sell more than we can produce
    return pd.DataFrame(
        {
            "price": price,
            "demand": demand,
            "volume": volume,
            "variable_cost": variable_cost,
            "npv": npv(price, volume, variable_cost, project),
        }
    )


def simulate_correlated(
    iterations: int,
    seed: int,
    price_demand_correlation: float,
    inputs: JustifiedInputs = JUSTIFIED_INPUTS,
    project: ProjectAssumptions = BASE_CASE,
    correlation_matrix: np.ndarray | None = None,
) -> pd.DataFrame:
    """Correlated model: justified distributions, with Price and Demand linked by a Gaussian copula.

    Variable order in the matrix: (Price, Demand, Variable cost).
    `correlation_matrix` lets you pass a full 3×3 matrix instead of ρ alone.
    """
    if correlation_matrix is None:
        correlation_matrix = price_demand_correlation_matrix(price_demand_correlation)
    rng = np.random.default_rng(seed)
    # Steps 1 to 3: standard normals → correlated through Cholesky → probabilities U = Φ(X).
    uniforms = correlated_uniforms(correlation_matrix, iterations, rng)
    # Step 4: apply each variable's inverse distribution to its column of probabilities.
    price = pert_ppf(uniforms[:, 0], inputs.price)
    demand = normal_ppf(uniforms[:, 1], inputs.demand)
    variable_cost = normal_ppf(uniforms[:, 2], inputs.variable_cost)
    volume = np.minimum(demand, project.capacity)
    return pd.DataFrame(
        {
            "price": price,
            "demand": demand,
            "volume": volume,
            "variable_cost": variable_cost,
            "npv": npv(price, volume, variable_cost, project),
        }
    )


def achieved_correlation(results: pd.DataFrame) -> float:
    """Price–Demand correlation actually achieved by the draws (on drawn demand, before the cap)."""
    return float(np.corrcoef(results["price"], results["demand"])[0, 1])
