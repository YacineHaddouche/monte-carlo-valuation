"""Tests of the Gaussian copula."""

import numpy as np
import pytest

from mc_valuation.correlation import (
    correlated_standard_normals,
    is_positive_semidefinite,
    price_demand_correlation_matrix,
)
from mc_valuation.simulation import achieved_correlation, simulate_correlated

IMPOSSIBLE_MATRIX = np.array(
    [
        [1.0, -0.9, 0.9],
        [-0.9, 1.0, 0.9],
        [0.9, 0.9, 1.0],
    ]
)


@pytest.mark.parametrize("rho", [-0.5, 0.0, 0.5])
def test_correlated_normals_hit_target(rho: float) -> None:
    normals = correlated_standard_normals(price_demand_correlation_matrix(rho), 500_000, np.random.default_rng(0))
    achieved = np.corrcoef(normals, rowvar=False)
    assert achieved[0, 1] == pytest.approx(rho, abs=0.01)
    assert achieved[0, 2] == pytest.approx(0, abs=0.01)  # Variable cost stays independent


@pytest.mark.parametrize("rho", [-0.5, 0.0, 0.5])
def test_price_demand_correlation_after_transformation(rho: float) -> None:
    results = simulate_correlated(500_000, seed=0, price_demand_correlation=rho)
    # The PERT transformation slightly attenuates the correlation: tolerance of 0.03.
    assert achieved_correlation(results) == pytest.approx(rho, abs=0.03)


def test_capacity_caps_volume_not_demand() -> None:
    results = simulate_correlated(100_000, seed=0, price_demand_correlation=-0.5)
    assert results["volume"].max() <= 17_000
    assert results["demand"].max() > 17_000


def test_impossible_matrix_is_rejected() -> None:
    assert not is_positive_semidefinite(IMPOSSIBLE_MATRIX)
    with pytest.raises(np.linalg.LinAlgError):
        np.linalg.cholesky(IMPOSSIBLE_MATRIX)
    with pytest.raises(ValueError, match="positive semi-definite"):
        simulate_correlated(1_000, seed=0, price_demand_correlation=0, correlation_matrix=IMPOSSIBLE_MATRIX)
