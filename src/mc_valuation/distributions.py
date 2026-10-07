"""Probability distributions used for the inputs: Normal, PERT and scenario-weighted PERT mixtures."""

from dataclasses import dataclass
from typing import Sequence

import numpy as np
from scipy import stats


@dataclass(frozen=True)
class NormalParams:
    """Parameters of a Normal distribution: mean and standard deviation."""

    mean: float
    sd: float

    def __post_init__(self) -> None:
        if self.sd <= 0:
            raise ValueError(f"The standard deviation must be > 0 (got {self.sd}).")


@dataclass(frozen=True)
class PertParams:
    """Parameters of a PERT distribution: a three-point expert estimate (min, mode, max)."""

    minimum: float
    mode: float
    maximum: float

    def __post_init__(self) -> None:
        if not (self.minimum <= self.mode <= self.maximum and self.minimum < self.maximum):
            raise ValueError("PERT parameters need minimum <= mode <= maximum, with minimum < maximum.")

    @property
    def width(self) -> float:
        """Width of the range: max − min."""
        return self.maximum - self.minimum

    @property
    def alpha(self) -> float:
        """First shape parameter of the underlying Beta distribution."""
        return 1 + 4 * (self.mode - self.minimum) / self.width

    @property
    def beta(self) -> float:
        """Second shape parameter of the underlying Beta distribution."""
        return 1 + 4 * (self.maximum - self.mode) / self.width

    @property
    def mean(self) -> float:
        """Theoretical mean of the PERT: (min + 4 × mode + max) / 6."""
        return (self.minimum + 4 * self.mode + self.maximum) / 6


@dataclass(frozen=True)
class PertMixture:
    """Scenario-weighted mixture of PERT distributions: one PERT per regime, drawn with probability `weight`."""

    components: tuple[PertParams, ...]
    weights: tuple[float, ...]
    names: tuple[str, ...]

    def __post_init__(self) -> None:
        if not (len(self.components) == len(self.weights) == len(self.names) > 0):
            raise ValueError("A mixture needs one weight and one name per component.")
        if min(self.weights) < 0 or not np.isclose(sum(self.weights), 1.0):
            raise ValueError("Mixture weights must be non-negative and sum to 100%.")

    @property
    def mean(self) -> float:
        """Probability-weighted average of the component means."""
        return sum(weight * pert.mean for weight, pert in zip(self.weights, self.components))

    @property
    def mode(self) -> float:
        """Central value used for the base case: the mode of the most likely regime."""
        return self.components[int(np.argmax(self.weights))].mode


def normal_params_from_data(data: Sequence[float]) -> NormalParams:
    """Fits a Normal distribution to historical data.

    ddof=1 gives the sample standard deviation (Excel's STDEV.S): we divide by n − 1
    because we estimate the spread of a population from a small sample.
    """
    values = np.asarray(data, dtype=float)
    return NormalParams(mean=float(values.mean()), sd=float(values.std(ddof=1)))


def sample_normal(params: NormalParams, size: int, rng: np.random.Generator) -> np.ndarray:
    """Draws `size` independent values from a Normal distribution."""
    return rng.normal(loc=params.mean, scale=params.sd, size=size)


def sample_pert(params: PertParams, size: int, rng: np.random.Generator) -> np.ndarray:
    """Draws `size` PERT values: a Beta(α, β) on [0, 1], rescaled to [min, max]."""
    beta_draws = rng.beta(params.alpha, params.beta, size=size)
    return params.minimum + params.width * beta_draws


def normal_ppf(probabilities: np.ndarray, params: NormalParams) -> np.ndarray:
    """Inverse CDF of the Normal distribution (Excel's NORM.INV)."""
    return stats.norm.ppf(probabilities, loc=params.mean, scale=params.sd)


def pert_ppf(probabilities: np.ndarray, params: PertParams) -> np.ndarray:
    """Inverse CDF of the PERT distribution (Excel's BETA.INV, rescaled)."""
    return params.minimum + params.width * stats.beta.ppf(probabilities, params.alpha, params.beta)


def mixture_cdf(values: np.ndarray, params: PertMixture) -> np.ndarray:
    """CDF of a PERT mixture: the weighted sum of each regime's CDF."""
    values = np.asarray(values, dtype=float)
    return sum(weight * stats.beta.cdf((values - pert.minimum) / pert.width, pert.alpha, pert.beta)
               for weight, pert in zip(params.weights, params.components))


def mixture_ppf(probabilities: np.ndarray, params: PertMixture, grid_points: int = 20_001) -> np.ndarray:
    """Inverse CDF of a PERT mixture.

    A mixture has no closed-form inverse, so we tabulate its CDF on a fine grid and interpolate backwards
    (np.interp with the roles of x and y swapped).
    """
    grid = np.linspace(min(p.minimum for p in params.components), max(p.maximum for p in params.components),
                       grid_points)
    return np.interp(probabilities, mixture_cdf(grid, params), grid)
