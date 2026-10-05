# Code walkthrough

This guide follows a simulation from the assumptions to the chart. For each module, it covers what the
module does and which lines matter.

## Overview

```
assumptions.py ──► distributions.py ──► simulation.py ──► model.py (NPV) ──► summary.py ──► validation.py
                   correlation.py ────┘                                         │
                                                                                 └──► Investment_project_NPV.py
asml/     reuses distributions.py, correlation.py and the same vectorised approach for a DCF.
```

**Core idea: vectorisation.** There is never a `for` loop over scenarios. Each variable is a NumPy array
of n values (one per scenario), and a single line of arithmetic processes all n scenarios at once. For
example, `volume * (price - variable_cost)` multiplies two arrays of one million values element by
element. This is the equivalent of an Excel column filled down, and it runs orders of magnitude faster
than a Python loop.

---

## 1. `assumptions.py`: the inputs

- `@dataclass(frozen=True)` groups named values (`BASE_CASE.price`, `BASE_CASE.discount_rate`…).
  `frozen=True` makes them read-only, so no calculation can change an assumption by accident.
- `800_000.0`: the underscore is only a thousands separator for readability.
- `JUSTIFIED_INPUTS.variable_cost = normal_params_from_data(HISTORICAL_VARIABLE_COSTS)`: the Variable
  cost parameters are not typed in by hand. They are **computed** from the 8 historical data points.
- `DEFAULT_SEED = 42`: the seed sets the starting point of the random generator. Same seed ⇒ same draws ⇒
  reproducible results.

Keeping the inputs separate from the code works like an "Inputs" sheet in Excel. A scenario can be
changed without touching the formulas.

## 2. `distributions.py`: probability distributions

- `NormalParams` and `PertParams` hold the parameters of each distribution. `__post_init__` checks that
  they are consistent (SD > 0; min ≤ mode ≤ max) as soon as they are created.
- **PERT**: `alpha = 1 + 4 × (mode − min) / (max − min)` and `beta = 1 + 4 × (max − mode) / (max − min)`.
  With (44, 50, 52), α = 4 and β = 2. Since α > β, the mass sits towards the top of the range and the
  tail stretches downwards: this is a downside-skewed risk.
- `sample_pert`: `rng.beta(α, β)` draws a Beta between 0 and 1, then `min + (max − min) × draw` rescales
  it to the range 44 to 52.
- `normal_params_from_data`: `values.std(ddof=1)`. By default `np.std` divides by n (= `STDEV.P`).
  `ddof=1` divides by n − 1 (= `STDEV.S`), which is the right choice when estimating from a sample.
  Without it, the SD would be 1.164 instead of 1.244.
- `normal_ppf` and `pert_ppf`: the *ppf* (percent point function) is the inverse CDF. Given a probability
  u ∈ (0, 1), it returns the value x such that P(X ≤ x) = u. These are the equivalents of Excel's
  `NORM.INV` and `BETA.INV`, and they implement step 4 of the copula.

## 3. `model.py`: NPV

- `discount_factors`: `t = np.arange(1, years + 1)` creates [1, 2, 3, 4, 5], then `1 / (1 + r) ** t`
  computes the five discount factors at once.
- `annuity_factor`: the sum of the discount factors (≈ 3.7908 at 10% over 5 years), i.e. the present
  value of €1 received every year for 5 years.
- `npv = fcf × annuity_factor − initial_investment`. This shortcut holds **because one draw applies to all
  5 years**: the FCF is the same every year. 220,000 × 3.7908 − 800,000 = €33,973.09.
- `npv_from_cash_flows`: the same calculation year by year, with t = 0 for the investment. A test checks
  that both methods agree. Excel's `NPV()` discounts from the first flow (first flow at t = 1), while
  `numpy_financial.npv` puts the first flow at t = 0. Here t = 0 is explicit, so there is no ambiguity.
- `break_even_price`: find the FCF that sets NPV to zero, FCF* = I / annuity factor = €211,038, then solve
  V × (P − VC) − FC = FCF* for P. Result: €49.40.

## 4. `correlation.py`: the Gaussian copula

The four steps, in order:

1. `rng.standard_normal(size=(n, 3))`: three columns of **independent** standard normals.
2. `independent @ lower.T`: correlation through Cholesky. `np.linalg.cholesky(C)` returns the triangular
   matrix L such that L × Lᵀ = C. For each scenario, x = L × z. `@` is the matrix product, and
   `Z @ Lᵀ` handles every row at once. With two variables, this reproduces the familiar formula
   X₂ = ρ·Z₁ + √(1 − ρ²)·Z₂.
3. `stats.norm.cdf(...)`: U = Φ(X) turns each normal into a probability between 0 and 1. The dependence
   is preserved because Φ is increasing.
4. In `simulation.py`, `pert_ppf(U₁)` and `normal_ppf(U₂)` give each variable its own distribution.

The order matters: the standard normals are correlated *before* the distributions are applied.
Correlating PERT and Normal draws after the fact would not make sense.

The matrix is 3×3 (Price, Demand, VC), with zeros for VC. The Variable cost goes through the same
mechanism but stays independent, and testing a different correlation structure only requires a new
matrix.

Before Cholesky, `validate_correlation_matrix` checks that the matrix is square, symmetric, has a
diagonal of 1, contains values between −1 and 1, and is **positive semi-definite** (all eigenvalues ≥ 0,
via `np.linalg.eigvalsh`).

## 5. `simulation.py`: the three simulations

- `rng = np.random.default_rng(seed)`: NumPy's modern generator, created once and passed to every
  sampling function.
- `volume = np.minimum(demand, project.capacity)`: an element-wise comparison, like `=MIN()` filled down
  in Excel. The cap applies to units *sold*, not to drawn demand. Both columns are kept, because the
  correlation is checked on drawn demand.
- Each function returns a `pd.DataFrame` with one row per scenario and one column per variable, plus the
  NPV. This is the equivalent of an Excel Data Table.
- `achieved_correlation`: `np.corrcoef(price, demand)[0, 1]`. `corrcoef` returns a 2×2 matrix whose
  element [0, 1] is the correlation between the two variables. It comes out around −0.49 for a −0.5
  target: the non-linear PERT transformation slightly attenuates the Pearson correlation.

## 6. `summary.py`: statistics

| Statistic | Code | Excel equivalent |
| --- | --- | --- |
| Mean NPV | `values.mean()` | `AVERAGE` |
| Standard deviation | `values.std(ddof=1)` | `STDEV.S` |
| P5 / P50 / P95 | `np.percentile(values, [5, 50, 95])` | `PERCENTILE.INC` |
| P(NPV < 0) | `(values < 0).mean()` | `COUNTIF(<0) / n` |
| SE of probability | `√(p(1 − p) / n)` | same |
| SE of mean | `sd / √n` | same |

`(values < 0)` creates an array of True/False values. Python counts True as 1 and False as 0, so its
mean is the share of scenarios with a negative NPV.

## 7. `validation.py` and `scripts/run_validation.py`

- `EXCEL_REFERENCE`: the Excel results, stored for automatic comparison.
- `z_score`: the gap divided by the combined SE √(SE₁² + SE₂²). |z| < 2 ⇒ consistent.
- `run_validation.py` prints everything in the terminal and saves the CSV files and the histogram to
  `results/`. The findings are written up in [VALIDATION.md](VALIDATION.md).

## 8. `Investment_project_NPV.py`: the dashboard

- Streamlit reruns the whole script on every interaction. `@st.cache_data` stores the result of
  `run_simulation` for a given set of inputs, so the simulation only reruns when a parameter changes.
- `st.sidebar` holds the inputs, `st.metric` shows the key figures, and `st.tabs` creates the tabs.
- **Tornado chart**: for each input, the NPV at its P5 and then at its P95, with the others at their
  central value. This is deliberately a one-input-at-a-time analysis: it ranks the sources of risk but
  ignores correlations, unlike the simulation.
- **Cumulative probability**: for each NPV value x, the probability that NPV ≤ x. P(NPV < 0) can be read
  directly at x = 0.

## 9. `asml/`: the DCF

The same logic, applied to a listed company. The NPV is replaced by a DCF and a value per share, and
P(NPV < 0) is replaced by P(value < share price).

**`assumptions.py`.** Every number carries its source as a comment (2025 annual report page or note, Q2
2026 guidance, Euronext price). The module has three blocks:

- `MarketData`: share price, number of shares, cash, debt, leases, non-operating assets, dividends paid
  since the balance-sheet date;
- `OperatingAssumptions`: what is treated as certain (2026 guidance, tax rate, capex and D&A ratios);
- `UncertainInputs`: the five simulated drivers.

`net_cash = cash − debt − lease_liabilities`. ASML holds more cash than debt, so net cash is *added* to the
Enterprise Value. Leases count as debt because their payments are a fixed financial commitment.

**`model.py`.**

- `_column` turns an array of n scenarios (shape `(n,)`) into a column (shape `(n, 1)`). Multiplied by an
  array of 10 years (shape `(10,)`), NumPy automatically produces an `(n, 10)` matrix: one row per
  scenario, one column per year. This is **broadcasting**, and it needs no loop over scenarios or years.
- `revenue_path`: from 2026 to 2030, `first × (target / first) ** step` with `step` = 0, ¼, ½, ¾, 1 gives
  constant growth that lands exactly on the 2030 driver. From 2031, `fade` = 1, 0.8 … 0.2 shrinks the
  extra growth towards terminal growth, and `np.cumprod` compounds it year after year.
- `ramp`: moves the gross margin and the cost ratio linearly from their 2026 value to their 2030 value,
  then keeps them flat.
- `free_cash_flows`: EBIT = sales × (gross margin − cost ratio); FCF = EBIT − tax + D&A − capex − working
  capital. Working capital is invested on each *additional* euro of sales, so the previous year's revenue
  is needed (2025 actual for 2026).
- `enterprise_value`: the sum of discounted FCFs plus the terminal value `FCF_N × (1 + g) / (WACC − g)`,
  discounted over N years. A test checks that a growing perpetuity gives back `FCF / (WACC − g)`.
- `value_per_share`: equity value at 31 December 2025 per share, then **rolled forward** to the share-price
  date: `× (1 + WACC) ** (275 / 365)` for the time value, minus the dividends paid in between. Without it,
  a December 2025 value would be compared with an October 2026 price.

**`simulation.py`.**

- The same copula, with a 5×5 matrix where only the Revenue–Gross margin pair is set to ρ.
  `inverse_distribution` picks `pert_ppf` or `normal_ppf` depending on the distribution type.
- `tornado_table`: one driver at a time moves from its P5 to its P95.
- `implied_value` (**reverse DCF**): `optimize.brentq(gap, lower, upper)` finds the value x such that
  `value_per_share(x) − share_price = 0`, as long as the function changes sign between `lower` and
  `upper`. This answers the question "what does the market assume?".

## 10. Tests (`tests/`)

`pytest` automatically runs every function whose name starts with `test_`. `pytest.approx` compares
decimal numbers with a tolerance, because floating-point arithmetic is never exact to the last digit. The
key tests are:

- base-case NPV = €33,973.09 (non-regression: if someone breaks the formula, the test fails);
- PERT mean ≈ €49.33; α = 4, β = 2; sample SD of the Variable cost = 1.2443;
- achieved correlation ≈ target for ρ ∈ {−0.5, 0, +0.5}; an impossible matrix is rejected;
- units sold ≤ capacity, while drawn demand can exceed it;
- same seed ⇒ same results. For independent normals, the simulated mean matches the base-case NPV
  within 4 SE, because the model is linear in each input and the inputs are independent and centred on
  the base case;
- ASML: net cash from the balance sheet, revenue path hitting the guidance and the 2030 driver, fading
  growth, growing-perpetuity check, achieved correlation, and a reverse DCF that reproduces the share price;
- both dashboard pages run without error.
