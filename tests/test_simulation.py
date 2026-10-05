"""Tests of the simulations and statistics."""

import numpy as np
import pytest

from mc_valuation.assumptions import BASE_CASE
from mc_valuation.model import npv
from mc_valuation.simulation import simulate_independent_normals, simulate_justified
from mc_valuation.summary import summarize


def test_same_seed_gives_same_results() -> None:
    first = simulate_justified(1_000, seed=7)
    second = simulate_justified(1_000, seed=7)
    assert first.equals(second)


def test_independent_normals_mean_close_to_base_case() -> None:
    # The model is linear in each input and the inputs are independent and centred on the
    # base case: the expected NPV is exactly the base-case NPV.
    results = simulate_independent_normals(1_000_000, seed=0)
    stats = summarize(results["npv"])
    expected = npv(BASE_CASE.price, BASE_CASE.volume, BASE_CASE.variable_cost)
    assert abs(stats["Mean NPV"] - expected) < 4 * stats["SE of mean"]


def test_summarize_on_known_values() -> None:
    values = np.array([-2.0, -1.0, 1.0, 2.0])
    stats = summarize(values)
    assert stats["Mean NPV"] == pytest.approx(0)
    assert stats["Standard deviation"] == pytest.approx(np.sqrt(10 / 3))  # ddof=1
    assert stats["P50"] == pytest.approx(0)
    assert stats["P(NPV < 0)"] == pytest.approx(0.5)
    assert stats["SE of probability"] == pytest.approx(np.sqrt(0.5 * 0.5 / 4))
    assert stats["SE of mean"] == pytest.approx(np.sqrt(10 / 3) / 2)
