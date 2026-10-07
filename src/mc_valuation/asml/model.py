"""Vectorised three-stage ASML DCF: each driver is an array of n scenarios, each flow an (n, years) matrix.

Convention: Year 0 = 31 December 2025 (latest annual balance sheet), Year 1 = 2026 … Year 15 = 2040,
flows discounted at year end. Stage 1 (2026–2030): explicit forecast up to the 2030 drivers. Stage 2
(2031–2040): growth fades to the perpetual rate. Stage 3: terminal value at the end of 2040. The value per
share is then rolled forward to the share-price date.
"""

import numpy as np
from numpy.typing import ArrayLike

from mc_valuation.asml.assumptions import ASML_MARKET, ASML_OPERATIONS, MarketData, OperatingAssumptions


def _column(values: ArrayLike) -> np.ndarray:
    """(n,) → (n, 1) so that one scenario per row broadcasts against one year per column."""
    return np.asarray(values, dtype=float)[..., np.newaxis]


def cost_of_capital(risk_free: ArrayLike, beta: ArrayLike, equity_premium: ArrayLike) -> np.ndarray:
    """CAPM: Rf + β × ERP. ASML's debt is under 1% of its value, so the WACC equals the cost of equity."""
    return np.asarray(risk_free, dtype=float) + np.asarray(beta, dtype=float) * np.asarray(equity_premium, dtype=float)


def revenue_path(revenue_2030: ArrayLike, growth_2031: ArrayLike, terminal_growth: ArrayLike,
                 operations: OperatingAssumptions = ASML_OPERATIONS) -> np.ndarray:
    """Revenue over the explicit horizon.

    2026 = guidance; 2026 → 2030 = constant growth up to the 2030 driver; from 2031 = growth starting at the
    2031 driver and fading linearly towards the perpetual rate by the last explicit year.
    """
    target = _column(revenue_2030)
    step = np.arange(operations.years_to_target) / (operations.years_to_target - 1)  # 0, ¼, ½, ¾, 1
    early = operations.revenue_first_year * (target / operations.revenue_first_year) ** step

    late_years = operations.horizon_years - operations.years_to_target
    fade = (late_years - np.arange(late_years)) / late_years  # 1, 0.9, …, 0.1 over 2031–2040
    terminal = _column(terminal_growth)
    growth = terminal + (_column(growth_2031) - terminal) * fade
    late = target * np.cumprod(1 + growth, axis=-1)
    return np.concatenate([early, late], axis=-1)


def ramp(start: float, end: ArrayLike, operations: OperatingAssumptions = ASML_OPERATIONS) -> np.ndarray:
    """Moves linearly from the 2026 value to the 2030 value, then stays flat."""
    years = np.arange(operations.horizon_years)
    progress = np.minimum(years / (operations.years_to_target - 1), 1.0)
    return start + (_column(end) - start) * progress


def free_cash_flows(
    revenue_2030: ArrayLike,
    gross_margin_2030: ArrayLike,
    opex_ratio: ArrayLike,
    growth_2031: ArrayLike,
    terminal_growth: ArrayLike,
    operations: OperatingAssumptions = ASML_OPERATIONS,
) -> dict[str, np.ndarray]:
    """Projects flows over the explicit horizon: shape (n, years) for n scenarios, (years,) for a single one."""
    revenue = revenue_path(revenue_2030, growth_2031, terminal_growth, operations)
    gross_margin = ramp(operations.gross_margin_first_year, gross_margin_2030, operations)
    opex = ramp(operations.opex_ratio_first_year, opex_ratio, operations)

    ebit = revenue * (gross_margin - opex)  # income from operations (R&D and SG&A already include D&A)
    taxes = operations.tax_rate * np.maximum(ebit, 0)
    depreciation = operations.depreciation_rate * revenue
    capex = operations.capex_rate * revenue
    previous_revenue = np.concatenate(
        [np.broadcast_to(operations.revenue_last_year, revenue[..., :1].shape), revenue[..., :-1]], axis=-1)
    working_capital = operations.working_capital_rate * (revenue - previous_revenue)
    nopat = ebit - taxes
    fcf = nopat + depreciation - capex - working_capital
    return {"revenue": revenue, "gross_margin": gross_margin, "ebit": ebit, "taxes": taxes, "nopat": nopat,
            "capex": capex, "working_capital": working_capital, "fcf": fcf}


def terminal_multiple(wacc: ArrayLike, terminal_growth: ArrayLike,
                      operations: OperatingAssumptions = ASML_OPERATIONS) -> np.ndarray:
    """Terminal value / next-year NOPAT implied by the value-driver formula: (1 − g / RONIC) / (WACC − g).

    Growing at g requires reinvesting g / RONIC of NOPAT each year; the rest is free cash flow.
    """
    wacc = np.asarray(wacc, dtype=float)
    growth = np.asarray(terminal_growth, dtype=float)
    if np.any(wacc <= growth):
        raise ValueError("The WACC must be greater than the perpetual growth rate.")
    return (1 - growth / operations.terminal_ronic) / (wacc - growth)


def terminal_value(flows: dict[str, np.ndarray], wacc: ArrayLike, terminal_growth: ArrayLike,
                   operations: OperatingAssumptions = ASML_OPERATIONS) -> np.ndarray:
    """Value at the end of the explicit horizon of all later cash flows, by the selected method."""
    wacc = np.asarray(wacc, dtype=float)
    growth = np.asarray(terminal_growth, dtype=float)
    next_nopat = flows["nopat"][..., -1] * (1 + growth)
    if operations.terminal_method == "value_driver":
        return next_nopat * terminal_multiple(wacc, growth, operations)
    if operations.terminal_method == "exit_multiple":
        return next_nopat * operations.exit_multiple
    if operations.terminal_method == "gordon_fcf":
        if np.any(wacc <= growth):
            raise ValueError("The WACC must be greater than the perpetual growth rate.")
        return flows["fcf"][..., -1] * (1 + growth) / (wacc - growth)
    raise ValueError(f"Unknown terminal-value method: {operations.terminal_method}")


def enterprise_value(fcf: np.ndarray, terminal: ArrayLike, wacc: ArrayLike) -> np.ndarray:
    """Present value of the explicit FCFs + present value of the terminal value."""
    wacc = _column(wacc)
    years = np.arange(1, fcf.shape[-1] + 1)
    discount_factors = 1 / (1 + wacc) ** years
    return (fcf * discount_factors).sum(axis=-1) + np.asarray(terminal, dtype=float) * discount_factors[..., -1]


def value_per_share(
    revenue_2030: ArrayLike,
    gross_margin_2030: ArrayLike,
    opex_ratio: ArrayLike,
    growth_2031: ArrayLike,
    terminal_growth: ArrayLike,
    wacc: ArrayLike,
    operations: OperatingAssumptions = ASML_OPERATIONS,
    market: MarketData = ASML_MARKET,
) -> np.ndarray:
    """Intrinsic value per share at the share-price date.

    Equity value at 31 December 2025 = Enterprise Value + net cash + non-operating assets. Per share, it is
    rolled forward to the share-price date at the cost of capital, minus the dividends paid in between.
    """
    flows = free_cash_flows(revenue_2030, gross_margin_2030, opex_ratio, growth_2031, terminal_growth, operations)
    terminal = terminal_value(flows, wacc, terminal_growth, operations)
    equity_value = enterprise_value(flows["fcf"], terminal, wacc) + market.net_cash + market.non_operating_assets
    per_share_at_year_end = equity_value / market.shares_outstanding
    rolled_forward = (per_share_at_year_end * (1 + np.asarray(wacc, dtype=float)) ** market.years_since_balance_sheet
                      - market.dividends_paid_since)
    return np.maximum(rolled_forward, 0)
