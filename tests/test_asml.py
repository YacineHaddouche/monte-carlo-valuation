"""Tests of the ASML valuation."""

from dataclasses import replace

import numpy as np
import pytest

from mc_valuation.asml.assumptions import ASML_INPUTS, ASML_MARKET, ASML_OPERATIONS, FIRST_VERSION
from mc_valuation.asml.model import (
    cost_of_capital,
    enterprise_value,
    free_cash_flows,
    ramp,
    revenue_path,
    terminal_multiple,
    terminal_value,
)
from mc_valuation.asml.simulation import (
    central_value,
    central_values,
    correlation_matrix,
    implied_value,
    model_bridge,
    simulate_asml,
    summarize_valuation,
    value_scenarios,
)
from mc_valuation.distributions import PertMixture, PertParams, mixture_cdf, mixture_ppf


def test_net_cash_from_balance_sheet() -> None:
    # €13,321.9m cash and short-term investments − €4,390.9m debt − €251.4m leases (31 December 2025).
    assert ASML_MARKET.net_cash == pytest.approx(8_679.6e6)


def test_revenue_path_hits_guidance_and_target() -> None:
    path = revenue_path(np.array([75e9]), np.array([0.08]), np.array([0.025]))
    assert path.shape == (1, ASML_OPERATIONS.horizon_years)
    assert path[0, 0] == pytest.approx(ASML_OPERATIONS.revenue_first_year)  # 2026 = guidance midpoint
    assert path[0, ASML_OPERATIONS.years_to_target - 1] == pytest.approx(75e9)  # 2030 = driver
    assert path[0, 5] == pytest.approx(75e9 * 1.08)  # 2031 grows at the full driver rate


def test_growth_fades_towards_terminal_growth() -> None:
    path = revenue_path(np.array([75e9]), np.array([0.10]), np.array([0.025]))[0]
    growth = path[5:] / path[4:-1] - 1
    assert np.all(np.diff(growth) < 0)
    assert growth[-1] == pytest.approx(0.025 + (0.10 - 0.025) / 10)  # last fade step before the perpetual rate


def test_margin_ramp_reaches_target_and_stays_flat() -> None:
    path = ramp(0.55, np.array([0.59]))[0]
    assert path[0] == pytest.approx(0.55)
    assert np.allclose(path[ASML_OPERATIONS.years_to_target - 1:], 0.59)


def test_first_year_consistent_with_guidance() -> None:
    center = central_values()
    flows = free_cash_flows(center["revenue_2030"], center["gross_margin_2030"], center["opex_ratio"],
                            center["growth_2031"], center["terminal_growth"])
    # 2026: €44bn of sales at 55% gross margin and 17% opex ⇒ operating margin of 38%.
    assert flows["ebit"][0] / flows["revenue"][0] == pytest.approx(0.38)


def test_cost_of_capital_is_capm() -> None:
    assert cost_of_capital(0.036, 1.2, 0.0425) == pytest.approx(0.087)


def test_value_driver_formula() -> None:
    # Without growth there is no reinvestment: the terminal value is a plain perpetuity of NOPAT.
    assert terminal_multiple(0.08, 0.0) == pytest.approx(1 / 0.08)
    # With RONIC = WACC, growth creates no value: the multiple equals the no-growth multiple.
    at_cost = replace(ASML_OPERATIONS, terminal_ronic=0.08)
    assert terminal_multiple(0.08, 0.03, at_cost) == pytest.approx(1 / 0.08)


def test_terminal_value_methods() -> None:
    flows = {"nopat": np.array([[100.0]]), "fcf": np.array([[90.0]])}
    exit_ops = replace(ASML_OPERATIONS, terminal_method="exit_multiple", exit_multiple=20.0)
    assert terminal_value(flows, 0.08, 0.02, exit_ops)[0] == pytest.approx(100 * 1.02 * 20)
    gordon = replace(ASML_OPERATIONS, terminal_method="gordon_fcf")
    assert terminal_value(flows, 0.08, 0.02, gordon)[0] == pytest.approx(90 * 1.02 / 0.06)


def test_enterprise_value_of_a_growing_perpetuity() -> None:
    wacc, growth = 0.08, 0.02
    fcf = 100 * (1 + growth) ** np.arange(10)
    terminal = fcf[-1] * (1 + growth) / (wacc - growth)
    assert enterprise_value(fcf[np.newaxis, :], terminal, np.array([wacc]))[0] == pytest.approx(100 / (wacc - growth))


def test_wacc_below_growth_is_rejected() -> None:
    with pytest.raises(ValueError):
        terminal_multiple(0.02, 0.025)


def test_first_version_is_reproduced() -> None:
    # The first version of the model (10 years, Gordon growth on the 2035 FCF, WACC 9%) gave €1,068.
    value = value_scenarios(FIRST_VERSION["central_drivers"], FIRST_VERSION["operations"])
    assert float(value) == pytest.approx(FIRST_VERSION["results"]["Value, central scenario"], abs=0.5)
    bridge = model_bridge()
    assert bridge["Value per share"].iloc[-1] == pytest.approx(central_value())


def test_mixture_weights_and_inverse() -> None:
    mixture = PertMixture((PertParams(0, 1, 2), PertParams(10, 11, 12)), (0.3, 0.7), ("low", "high"))
    assert mixture.mean == pytest.approx(0.3 * 1 + 0.7 * 11)
    assert mixture.mode == 11  # mode of the most likely regime
    assert mixture_cdf(np.array([5.0]), mixture)[0] == pytest.approx(0.3)  # all of the low regime lies below 5
    probabilities = np.array([0.1, 0.5, 0.9])
    assert mixture_cdf(mixture_ppf(probabilities, mixture), mixture) == pytest.approx(probabilities, abs=1e-4)
    with pytest.raises(ValueError):
        PertMixture((PertParams(0, 1, 2),), (0.5,), ("only",))


def test_value_per_share_is_vectorized_and_increasing_in_revenue() -> None:
    center = central_values()
    values = value_scenarios({**center, "revenue_2030": np.array([60e9, 90e9])})
    assert values.shape == (2,)
    assert values[1] > values[0] > 0


def test_simulation_correlation_and_reproducibility() -> None:
    first = simulate_asml(200_000, seed=3, revenue_margin_correlation=0.5)
    second = simulate_asml(200_000, seed=3, revenue_margin_correlation=0.5)
    assert first.equals(second)
    achieved = np.corrcoef(first["revenue_2030"], first["gross_margin_2030"])[0, 1]
    assert achieved == pytest.approx(0.5, abs=0.04)  # PERT and mixture transformations slightly attenuate ρ
    assert np.corrcoef(first["beta"], first["revenue_2030"])[0, 1] == pytest.approx(0, abs=0.01)
    assert first["revenue_2030"].mean() == pytest.approx(ASML_INPUTS.revenue_2030.mean, rel=0.005)


def test_correlation_matrix_is_valid() -> None:
    matrix = correlation_matrix(0.8)
    assert np.allclose(matrix, matrix.T)
    assert np.linalg.eigvalsh(matrix).min() > 0


def test_summary_probability() -> None:
    stats = summarize_valuation(np.array([1_000.0, 2_000.0, 1_500.0, 1_700.0]), share_price=1_653.0)
    assert stats["P(value < price)"] == pytest.approx(0.5)


def test_implied_value_reproduces_share_price() -> None:
    implied_wacc = implied_value("wacc", 0.04, 0.15)
    value = value_scenarios({**central_values(), "wacc": implied_wacc})
    assert float(value) == pytest.approx(ASML_MARKET.share_price, abs=1e-6)
