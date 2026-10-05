"""Probability distributions used for the inputs: Normal and PERT."""

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
