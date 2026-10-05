# Python vs Excel validation

Every Python figure below can be reproduced with `python scripts/run_validation.py` (seed 42). The full
tables are saved as CSV files in `results/`.

## 1. Validation table

z = (Python − Excel) / √(SE_Python² + SE_Excel²). If |z| < 2, the gap is consistent with sampling noise
alone at roughly 95% confidence.

| | Excel (5,000) | Python (5,000) | Python (1,000,000) | z (5,000) | z (1,000,000) |
| --- | --- | --- | --- | --- | --- |
| **Independent normals**, mean NPV | €35,631 | €31,209 | €34,037 | −1.10 | −0.55 |
| **Independent normals**, P(NPV < 0) | 44.2% | 44.8% | 44.8% | 0.58 | 0.83 |
| **Justified distributions**, mean NPV | −€8,871 | −€9,238 | −€11,940 | −0.12 | −1.45 |
| **Justified distributions**, P(NPV < 0) | 52.6% | 52.6% | 53.2% | 0.02 | 0.83 |
| **Correlated (ρ = −0.5)**, mean NPV | −€14,171 | −€13,465 | −€15,688 | 0.30 | −0.89 |
| **Correlated (ρ = −0.5)**, P(NPV < 0) | 54.7% | 55.0% | 55.8% | 0.32 | 1.50 |

Standard deviations and percentiles also agree within a few percent. For example, the correlated model
has an SD of €119,830 in Excel versus €119,283 in Python.

## 2. Findings

### Why Python and Excel do not give exactly the same numbers at 5,000 iterations

The two tools do not draw the same random numbers. Excel uses its own generator (`RAND()`), while NumPy
uses PCG64 through `np.random.default_rng(42)`. With only 5,000 draws, every statistic is an
**estimate** with sampling error, so two different samples give two different estimates even when the
model is identical.

**Objective criterion: the standard error.** Equality is not required; the gap only has to be
explainable by chance. For a mean, SE = SD / √n; for a probability, SE = √(p(1 − p) / n). Because the two
estimates are independent, their gap has an SE of √(SE₁² + SE₂²). The z-score measures the gap in units
of that SE, and **|z| < 2 ⇒ consistent**. All 12 z-scores above are below 1.5 in absolute value.

Caveat: these are 12 tests. Even with two perfectly identical models, an occasional |z| > 2 would be
expected (about 1 time in 20). A single isolated breach would not prove an error, but systematic
breaches in the same direction would.

### Precision at 1,000,000 iterations and the effect of ρ

SE of probability = √(0.5575 × 0.4425 / 1,000,000) ≈ **0.0005, i.e. 0.05 percentage point**, versus
0.70 pt at 5,000 iterations. Multiplying n by 200 divides the SE by √200 ≈ 14.

Effect of the correlation on the mean NPV (Python, same seed for every ρ):

| | ρ = −0.5 | ρ = 0 | Difference | SE of difference | z |
| --- | --- | --- | --- | --- | --- |
| 5,000 iterations | −€13,465 | −€9,923 | −€3,542 | €2,663 | −1.3 → **not significant** |
| 1,000,000 iterations | −€15,688 | −€12,070 | −€3,618 | €190 | −19.1 → **significant** |

At 5,000 iterations the effect (about −€3,600) is lost in the noise: it is only 1.3 SE. At 1,000,000 it is
19 SE and can no longer be explained by chance.

The SE of the difference is computed as if the two simulations were independent. Because they share the
same seed (*common random numbers*), the two estimates are positively correlated. The true SE is
therefore smaller, which makes this test conservative.

**Why a negative correlation lowers the mean.** Revenue is Price × Volume, and
E[P × V] = E[P] × E[V] + Cov(P, V). With ρ < 0 the covariance is negative: when the price is high,
volume tends to be low. Expected revenue falls, and so does the mean NPV. In exchange, the spread
narrows (SD of €119,283 versus €147,618): price increases and volume decreases partly offset each other,
like a natural hedge.

### An impossible correlation matrix

Consider ρ(Price, Demand) = −0.9, ρ(Price, VC) = +0.9 and ρ(Demand, VC) = +0.9. Here
`np.linalg.cholesky` raises `LinAlgError: Matrix is not positive definite`, because the decomposition
does not exist.

**Intuition.** The matrix asks the Variable cost to move strongly *with* Price and strongly *with*
Demand, while Price and Demand move strongly *against* each other. These three requirements contradict
each other: if VC closely tracks both Price and Demand, then Price and Demand must track each other.

**Formally.** A correlation matrix must be **positive semi-definite**: wᵀ C w ≥ 0 for every weight
vector w. For standardised variables, wᵀ C w is the variance of w₁X₁ + w₂X₂ + w₃X₃, and a variance cannot
be negative. Equivalently, all its eigenvalues must be ≥ 0. Here they are **−0.8**, 1.9 and 1.9
(determinant −2.888). The negative eigenvalue means some combination of the three variables would have a
negative "variance", which is absurd.

The code checks this condition before Cholesky (`validate_correlation_matrix`) and returns an explicit
message. Note that Cholesky requires a *positive definite* matrix (strictly positive eigenvalues), so a
correlation of exactly ±1, which is valid but degenerate, also makes it fail.
