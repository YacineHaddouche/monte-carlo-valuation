"""Deterministic model: FCF, NPV and break-even.

Every function accepts either a number or a NumPy array: the same code computes
the base case and 1,000,000 scenarios in one go.
"""

import numpy as np
from numpy.typing import ArrayLike

from mc_valuation.assumptions import BASE_CASE, ProjectAssumptions


def discount_factors(discount_rate: float, years: int) -> np.ndarray:
    """Discount factors from Year 1 to Year n: 1 / (1 + r)^t."""
    t = np.arange(1, years + 1)
    return 1 / (1 + discount_rate) ** t


def annuity_factor(discount_rate: float, years: int) -> float:
    """Sum of the discount factors: present value of €1 received every year."""
    return float(discount_factors(discount_rate, years).sum())


def annual_fcf(
    price: ArrayLike, volume: ArrayLike, variable_cost: ArrayLike, fixed_costs: float
) -> np.ndarray:
    """Annual FCF (Free Cash Flow) = Volume × (Price − Variable cost) − Fixed costs."""
    return np.asarray(volume) * (np.asarray(price) - np.asarray(variable_cost)) - fixed_costs


def npv(
    price: ArrayLike,
    volume: ArrayLike,
    variable_cost: ArrayLike,
    project: ProjectAssumptions = BASE_CASE,
) -> np.ndarray:
    """NPV (Net Present Value) of the project.

    One draw applies to all 5 years: the FCF is the same every year, so
    NPV = FCF × annuity factor − initial investment.
    """
    fcf = annual_fcf(price, volume, variable_cost, project.fixed_costs)
    return fcf * annuity_factor(project.discount_rate, project.years) - project.initial_investment


def cash_flows(project: ProjectAssumptions = BASE_CASE) -> np.ndarray:
    """Base-case cash flows from Year 0 to Year n (Year 0 = investment, negative)."""
    fcf = annual_fcf(project.price, project.volume, project.variable_cost, project.fixed_costs)
    return np.concatenate(([-project.initial_investment], np.full(project.years, fcf)))


def npv_from_cash_flows(flows: ArrayLike, discount_rate: float) -> float:
    """NPV computed year by year, including the (undiscounted) Year 0 flow.

    Careful: Excel's `NPV()` discounts from the first flow onwards, whereas
    `numpy_financial.npv` treats the first flow as t = 0. Here, t = 0 is explicit.
    """
    flows = np.asarray(flows, dtype=float)
    t = np.arange(len(flows))
    return float((flows / (1 + discount_rate) ** t).sum())


def break_even_price(project: ProjectAssumptions = BASE_CASE) -> float:
    """Price that gives NPV = 0, all other inputs at their base-case value."""
    required_fcf = project.initial_investment / annuity_factor(project.discount_rate, project.years)
    return (required_fcf + project.fixed_costs) / project.volume + project.variable_cost


def break_even_volume(project: ProjectAssumptions = BASE_CASE) -> float:
    """Volume that gives NPV = 0, all other inputs at their base-case value."""
    required_fcf = project.initial_investment / annuity_factor(project.discount_rate, project.years)
    return (required_fcf + project.fixed_costs) / (project.price - project.variable_cost)
