"""Tests of the deterministic model."""

import numpy as np
import pytest

from mc_valuation.assumptions import BASE_CASE
from mc_valuation.model import (
    annual_fcf,
    break_even_price,
    break_even_volume,
    cash_flows,
    npv,
    npv_from_cash_flows,
)


def test_base_case_fcf() -> None:
    fcf = annual_fcf(BASE_CASE.price, BASE_CASE.volume, BASE_CASE.variable_cost, BASE_CASE.fixed_costs)
    assert fcf == pytest.approx(220_000)


def test_base_case_npv_non_regression() -> None:
    result = npv(BASE_CASE.price, BASE_CASE.volume, BASE_CASE.variable_cost)
    assert result == pytest.approx(33_973.09, abs=0.01)


def test_npv_matches_year_by_year_discounting() -> None:
    year_by_year = npv_from_cash_flows(cash_flows(), BASE_CASE.discount_rate)
    assert year_by_year == pytest.approx(33_973.09, abs=0.01)


def test_npv_is_vectorized() -> None:
    prices = np.array([50.0, 49.4025, 60.0])
    results = npv(prices, BASE_CASE.volume, BASE_CASE.variable_cost)
    assert results.shape == (3,)
    assert results[0] == pytest.approx(33_973.09, abs=0.01)


def test_break_even_price() -> None:
    price = break_even_price()
    assert price == pytest.approx(49.40, abs=0.005)
    assert npv(price, BASE_CASE.volume, BASE_CASE.variable_cost) == pytest.approx(0, abs=1e-6)


def test_break_even_volume() -> None:
    volume = break_even_volume()
    assert round(volume) == 14_552
    assert npv(BASE_CASE.price, volume, BASE_CASE.variable_cost) == pytest.approx(0, abs=1e-6)
