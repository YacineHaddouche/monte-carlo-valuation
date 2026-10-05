"""Tests of the ASML valuation."""

import numpy as np
import pytest

from mc_valuation.asml.assumptions import ASML_MARKET, ASML_OPERATIONS
from mc_valuation.asml.model import enterprise_value, free_cash_flows, ramp, revenue_path, value_per_share
from mc_valuation.asml.simulation import (
    central_values,
    correlation_matrix,
    implied_value,
    simulate_asml,
    summarize_valuation,
)


def test_net_cash_from_balance_sheet() -> None:
    # €13,321.9m cash and short-term investments − €4,390.9m debt − €251.4m leases (31 December 2025).
    assert ASML_MARKET.net_cash == pytest.approx(8_679.6e6)


def test_revenue_path_hits_guidance_and_target() -> None:
    path = revenue_path(np.array([75e9]), np.array([0.08]))
    assert path.shape == (1, ASML_OPERATIONS.horizon_years)
    assert path[0, 0] == pytest.approx(ASML_OPERATIONS.revenue_first_year)  # 2026 = guidance midpoint
    assert path[0, ASML_OPERATIONS.years_to_target - 1] == pytest.approx(75e9)  # 2030 = driver
    assert path[0, 5] == pytest.approx(75e9 * 1.08)  # 2031 grows at the full driver rate


def test_growth_fades_towards_terminal_growth() -> None:
    path = revenue_path(np.array([75e9]), np.array([0.10]))[0]
    growth = path[5:] / path[4:-1] - 1
    assert np.all(np.diff(growth) < 0)
    assert growth[-1] > ASML_OPERATIONS.terminal_growth


def test_margin_ramp_reaches_target_and_stays_flat() -> None:
    path = ramp(0.55, np.array([0.59]))[0]
    assert path[0] == pytest.approx(0.55)
    assert np.allclose(path[ASML_OPERATIONS.years_to_target - 1:], 0.59)


def test_first_year_consistent_with_guidance() -> None:
    center = central_values()
    flows = free_cash_flows(center["revenue_2030"], center["gross_margin_2030"], center["opex_ratio"],
                            center["growth_2031_2035"])
    # 2026: €44bn of sales at 55% gross margin and 17% opex ⇒ operating margin of 38%.
    assert flows["ebit"][0] / flows["revenue"][0] == pytest.approx(0.38)


def test_enterprise_value_of_a_growing_perpetuity() -> None:
    wacc, growth = 0.08, 0.02
    fcf = 100 * (1 + growth) ** np.arange(10)
    assert enterprise_value(fcf[np.newaxis, :], np.array([wacc]), growth)[0] == pytest.approx(100 / (wacc - growth))


def test_wacc_below_growth_is_rejected() -> None:
    with pytest.raises(ValueError):
        enterprise_value(np.ones((1, 5)), np.array([0.02]), 0.025)


def test_value_per_share_is_vectorized_and_increasing_in_revenue() -> None:
    center = central_values()
    values = value_per_share(np.array([60e9, 90e9]), center["gross_margin_2030"], center["opex_ratio"],
                             center["growth_2031_2035"], center["wacc"])
    assert values.shape == (2,)
    assert values[1] > values[0] > 0


def test_simulation_correlation_and_reproducibility() -> None:
    first = simulate_asml(200_000, seed=3, revenue_margin_correlation=0.5)
    second = simulate_asml(200_000, seed=3, revenue_margin_correlation=0.5)
    assert first.equals(second)
    achieved = np.corrcoef(first["revenue_2030"], first["gross_margin_2030"])[0, 1]
    assert achieved == pytest.approx(0.5, abs=0.03)  # PERT transformation slightly attenuates ρ
    assert np.corrcoef(first["wacc"], first["revenue_2030"])[0, 1] == pytest.approx(0, abs=0.01)


def test_correlation_matrix_is_valid() -> None:
    matrix = correlation_matrix(0.8)
    assert np.allclose(matrix, matrix.T)
    assert np.linalg.eigvalsh(matrix).min() > 0


def test_summary_probability() -> None:
    stats = summarize_valuation(np.array([1_000.0, 2_000.0, 1_500.0, 1_700.0]), share_price=1_653.0)
    assert stats["P(value < price)"] == pytest.approx(0.5)


def test_implied_value_reproduces_share_price() -> None:
    implied_wacc = implied_value("wacc", 0.03, 0.15)
    center = central_values()
    value = value_per_share(center["revenue_2030"], center["gross_margin_2030"], center["opex_ratio"],
                            center["growth_2031_2035"], implied_wacc)
    assert float(value) == pytest.approx(ASML_MARKET.share_price, abs=1e-6)
