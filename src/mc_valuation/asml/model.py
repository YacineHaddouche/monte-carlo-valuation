"""Vectorised ASML DCF: each driver is an array of n scenarios, each flow an (n, years) matrix.

Convention: Year 0 = 31 December 2025 (latest annual balance sheet), Year 1 = 2026 … Year 10 = 2035,
flows discounted at year end. The value per share is then rolled forward to the share-price date.
"""

import numpy as np
from numpy.typing import ArrayLike

from mc_valuation.asml.assumptions import ASML_MARKET, ASML_OPERATIONS, MarketData, OperatingAssumptions


def _column(values: ArrayLike) -> np.ndarray:
    """(n,) → (n, 1) so that one scenario per row broadcasts against one year per column."""
    return np.asarray(values, dtype=float)[..., np.newaxis]


def revenue_path(revenue_2030: ArrayLike, growth_2031_2035: ArrayLike,
                 operations: OperatingAssumptions = ASML_OPERATIONS) -> np.ndarray:
    """Revenue 2026–2035.

    2026 = guidance; 2026 → 2030 = constant growth up to the 2030 driver; 2031 → 2035 = growth starting at the
    2031 driver and fading linearly towards terminal growth.
    """
    target = _column(revenue_2030)
    step = np.arange(operations.years_to_target) / (operations.years_to_target - 1)  # 0, ¼, ½, ¾, 1
    early = operations.revenue_first_year * (target / operations.revenue_first_year) ** step

    late_years = operations.horizon_years - operations.years_to_target
    fade = (late_years - np.arange(late_years)) / late_years  # 1, 0.8, 0.6, 0.4, 0.2
    growth = operations.terminal_growth + (_column(growth_2031_2035) - operations.terminal_growth) * fade
    late = target * np.cumprod(1 + growth, axis=-1)
    return np.concatenate([early, late], axis=-1)


def ramp(start: float, end: ArrayLike, operations: OperatingAssumptions = ASML_OPERATIONS) -> np.ndarray:
    """Moves linearly from the 2026 value to the 2030 value, then stays flat until 2035."""
    years = np.arange(operations.horizon_years)
    progress = np.minimum(years / (operations.years_to_target - 1), 1.0)
    return start + (_column(end) - start) * progress


def free_cash_flows(
    revenue_2030: ArrayLike,
    gross_margin_2030: ArrayLike,
    opex_ratio: ArrayLike,
    growth_2031_2035: ArrayLike,
    operations: OperatingAssumptions = ASML_OPERATIONS,
) -> dict[str, np.ndarray]:
    """Projects flows from 2026 to 2035: shape (n, 10) for n scenarios, (10,) for a single one."""
    revenue = revenue_path(revenue_2030, growth_2031_2035, operations)
    gross_margin = ramp(operations.gross_margin_first_year, gross_margin_2030, operations)
    opex = ramp(operations.opex_ratio_first_year, opex_ratio, operations)

    ebit = revenue * (gross_margin - opex)  # income from operations (R&D and SG&A already include D&A)
    taxes = operations.tax_rate * np.maximum(ebit, 0)
    depreciation = operations.depreciation_rate * revenue
    capex = operations.capex_rate * revenue
    previous_revenue = np.concatenate(
        [np.broadcast_to(operations.revenue_last_year, revenue[..., :1].shape), revenue[..., :-1]], axis=-1)
    working_capital = operations.working_capital_rate * (revenue - previous_revenue)
    fcf = ebit - taxes + depreciation - capex - working_capital
    return {"revenue": revenue, "gross_margin": gross_margin, "ebit": ebit, "taxes": taxes,
            "capex": capex, "working_capital": working_capital, "fcf": fcf}


def enterprise_value(fcf: np.ndarray, wacc: ArrayLike, terminal_growth: float) -> np.ndarray:
    """Present value of the explicit FCFs + terminal value (Gordon growth) on the last FCF."""
    wacc = _column(wacc)
    if np.any(wacc <= terminal_growth):
        raise ValueError("The WACC must be greater than the perpetual growth rate.")
    years = np.arange(1, fcf.shape[-1] + 1)
    discount_factors = 1 / (1 + wacc) ** years
    terminal_value = fcf[..., -1:] * (1 + terminal_growth) / (wacc - terminal_growth)
    return (fcf * discount_factors).sum(axis=-1) + (terminal_value * discount_factors[..., -1:]).sum(axis=-1)


def value_per_share(
    revenue_2030: ArrayLike,
    gross_margin_2030: ArrayLike,
    opex_ratio: ArrayLike,
    growth_2031_2035: ArrayLike,
    wacc: ArrayLike,
    operations: OperatingAssumptions = ASML_OPERATIONS,
    market: MarketData = ASML_MARKET,
) -> np.ndarray:
    """Intrinsic value per share at the share-price date.

    Equity value at 31 December 2025 = Enterprise Value + net cash + non-operating assets. Per share, it is
    rolled forward to the share-price date at the cost of capital, minus the dividends paid in between.
    """
    flows = free_cash_flows(revenue_2030, gross_margin_2030, opex_ratio, growth_2031_2035, operations)
    equity_value = (enterprise_value(flows["fcf"], wacc, operations.terminal_growth)
                    + market.net_cash + market.non_operating_assets)
    per_share_at_year_end = equity_value / market.shares_outstanding
    rolled_forward = (per_share_at_year_end * (1 + np.asarray(wacc, dtype=float)) ** market.years_since_balance_sheet
                      - market.dividends_paid_since)
    return np.maximum(rolled_forward, 0)
