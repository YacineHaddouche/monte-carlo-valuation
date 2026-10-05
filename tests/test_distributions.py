"""Tests of the probability distributions."""

import numpy as np
import pytest

from mc_valuation.assumptions import HISTORICAL_VARIABLE_COSTS, JUSTIFIED_INPUTS
from mc_valuation.distributions import (
    NormalParams,
    PertParams,
    normal_params_from_data,
    pert_ppf,
    sample_pert,
)

PRICE = JUSTIFIED_INPUTS.price


def test_pert_shape_parameters() -> None:
    assert PRICE.alpha == pytest.approx(4)
    assert PRICE.beta == pytest.approx(2)


def test_pert_theoretical_mean() -> None:
    assert PRICE.mean == pytest.approx(49.33, abs=0.005)


def test_pert_sample_mean_and_bounds() -> None:
    draws = sample_pert(PRICE, 1_000_000, np.random.default_rng(0))
    assert draws.mean() == pytest.approx(49.33, abs=0.01)
    assert draws.min() >= PRICE.minimum
    assert draws.max() <= PRICE.maximum


def test_pert_ppf_matches_sampling() -> None:
    draws = sample_pert(PRICE, 1_000_000, np.random.default_rng(1))
    assert pert_ppf(np.array(0.5), PRICE) == pytest.approx(np.median(draws), abs=0.01)


def test_variable_cost_estimated_with_sample_sd() -> None:
    params = normal_params_from_data(HISTORICAL_VARIABLE_COSTS)
    assert params.mean == pytest.approx(30.0625)
    assert params.sd == pytest.approx(1.2443, abs=1e-4)  # STDEV.S, not STDEV.P (≈ 1.164)


def test_invalid_parameters_are_rejected() -> None:
    with pytest.raises(ValueError):
        PertParams(minimum=52, mode=50, maximum=44)
    with pytest.raises(ValueError):
        NormalParams(mean=0, sd=-1)
