"""Gaussian copula: drawing correlated probabilities through a Cholesky decomposition."""

import numpy as np
from scipy import stats


def price_demand_correlation_matrix(rho: float) -> np.ndarray:
    """3×3 correlation matrix in the order (Price, Demand, Variable cost).

    Only the Price–Demand pair is correlated; the Variable cost stays independent.
    """
    return np.array(
        [
            [1.0, rho, 0.0],
            [rho, 1.0, 0.0],
            [0.0, 0.0, 1.0],
        ]
    )


def is_positive_semidefinite(matrix: np.ndarray, tolerance: float = 1e-10) -> bool:
    """True if every eigenvalue is >= 0: the condition for a valid correlation matrix."""
    eigenvalues = np.linalg.eigvalsh(matrix)
    return bool(eigenvalues.min() >= -tolerance)


def validate_correlation_matrix(matrix: np.ndarray) -> None:
    """Checks that a matrix can be a correlation matrix; raises a clear error otherwise."""
    if matrix.ndim != 2 or matrix.shape[0] != matrix.shape[1]:
        raise ValueError("The correlation matrix must be square.")
    if not np.allclose(matrix, matrix.T):
        raise ValueError("The correlation matrix must be symmetric.")
    if not np.allclose(np.diag(matrix), 1.0):
        raise ValueError("The diagonal of a correlation matrix must be 1.")
    if np.abs(matrix).max() > 1:
        raise ValueError("A correlation always lies between −1 and +1.")
    if not is_positive_semidefinite(matrix):
        eigenvalues = np.round(np.linalg.eigvalsh(matrix), 4)
        raise ValueError(
            "Impossible matrix: it is not positive semi-definite "
            f"(eigenvalues {eigenvalues.tolist()}). These correlations are mutually inconsistent."
        )


def correlated_standard_normals(
    correlation_matrix: np.ndarray, size: int, rng: np.random.Generator
) -> np.ndarray:
    """Copula steps 1 and 2: independent standard normals, then correlated through Cholesky.

    Returns an array of shape (size, k): one row per scenario, one column per variable.
    """
    validate_correlation_matrix(correlation_matrix)
    lower = np.linalg.cholesky(correlation_matrix)  # L such that L × Lᵀ = correlation matrix
    independent = rng.standard_normal(size=(size, correlation_matrix.shape[0]))
    # For each scenario z: x = L × z. Written for all rows at once: Z × Lᵀ.
    return independent @ lower.T


def correlated_uniforms(
    correlation_matrix: np.ndarray, size: int, rng: np.random.Generator
) -> np.ndarray:
    """Copula step 3: U = Φ(X), probabilities between 0 and 1 that keep the correlation."""
    return stats.norm.cdf(correlated_standard_normals(correlation_matrix, size, rng))
