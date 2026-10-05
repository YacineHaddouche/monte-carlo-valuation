"""Statistics of the NPV distribution, with their standard errors."""

import numpy as np
import pandas as pd
from numpy.typing import ArrayLike


def summarize(npv_values: ArrayLike) -> pd.Series:
    """Summarises the distribution of simulated NPVs.

    - SD with ddof=1: equivalent to Excel's STDEV.S.
    - Percentiles: NumPy's default linear method = Excel's PERCENTILE.INC.
    - SE of probability = √(p × (1 − p) / n); SE of mean = SD / √n.
    """
    values = np.asarray(npv_values, dtype=float)
    n = values.size
    sd = values.std(ddof=1)
    p5, p50, p95 = np.percentile(values, [5, 50, 95])
    prob_negative = float((values < 0).mean())  # share of scenarios with NPV < 0
    return pd.Series(
        {
            "Iterations": n,
            "Mean NPV": values.mean(),
            "Standard deviation": sd,
            "P5": p5,
            "P50": p50,
            "P95": p95,
            "P(NPV < 0)": prob_negative,
            "SE of probability": np.sqrt(prob_negative * (1 - prob_negative) / n),
            "SE of mean": sd / np.sqrt(n),
        }
    )
