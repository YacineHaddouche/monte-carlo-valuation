"""Model assumptions, kept separate from the code: no hard-coded numbers inside formulas."""

from dataclasses import dataclass

from mc_valuation.distributions import NormalParams, PertParams, normal_params_from_data


@dataclass(frozen=True)
class ProjectAssumptions:
    """Base case of the investment project (deterministic model)."""

    initial_investment: float = 800_000.0  # € in Year 0
    volume: float = 15_000.0  # units / year
    price: float = 50.0  # € / unit
    variable_cost: float = 30.0  # € / unit
    fixed_costs: float = 80_000.0  # € / year
    discount_rate: float = 0.10  # 10%
    years: int = 5  # operations from Year 1 to Year 5
    capacity: float = 17_000.0  # units / year


@dataclass(frozen=True)
class IndependentNormalInputs:
    """Independent model: three independent Normal distributions."""

    price: NormalParams
    volume: NormalParams
    variable_cost: NormalParams


@dataclass(frozen=True)
class JustifiedInputs:
    """Justified model: distributions chosen and justified input by input."""

    price: PertParams
    demand: NormalParams
    variable_cost: NormalParams


BASE_CASE = ProjectAssumptions()

INDEPENDENT_NORMAL_INPUTS = IndependentNormalInputs(
    price=NormalParams(mean=50.0, sd=2.5),
    volume=NormalParams(mean=15_000.0, sd=1_500.0),
    variable_cost=NormalParams(mean=30.0, sd=1.5),
)

# Variable cost observed over 8 periods, with no clear trend.
HISTORICAL_VARIABLE_COSTS = (28.5, 29.0, 31.2, 30.4, 29.8, 32.1, 30.6, 28.9)

JUSTIFIED_INPUTS = JustifiedInputs(
    price=PertParams(minimum=44.0, mode=50.0, maximum=52.0),
    demand=NormalParams(mean=15_000.0, sd=1_500.0),
    variable_cost=normal_params_from_data(HISTORICAL_VARIABLE_COSTS),
)

# Price–Demand correlation (a higher price dampens demand).
PRICE_DEMAND_CORRELATION = -0.5
CORRELATIONS_TO_COMPARE = (-0.5, 0.0, 0.5)

# Fixed seed: same draws on every run, hence reproducible results.
DEFAULT_SEED = 42
