"""ASML valuation assumptions, with their sources.

Main sources:
- ASML Annual Report 2025 (US GAAP): consolidated statements of operations, balance sheet and cash flows
  (pages 276–281), net system sales per technology (note 2), Eurobonds and leases (notes 14 and 16),
  2026 outlook and 2030 revenue opportunity (CFO letter, page 52);
- ASML Q2 2026 results (15 July 2026): updated 2026 guidance, 2026 dividends;
- Euronext Amsterdam share price (ASML) at the close of 2 October 2026;
- A. Damodaran, implied equity risk premium (January 2026 update).
"""

from dataclasses import dataclass

from mc_valuation.distributions import NormalParams, PertMixture, PertParams

TERMINAL_METHODS = {
    "value_driver": "Value-driver formula (growth and RONIC)",
    "exit_multiple": "Exit multiple (EV / next-year NOPAT)",
    "gordon_fcf": "Gordon growth on the last FCF (first version of the model)",
}


@dataclass(frozen=True)
class MarketData:
    """Balance sheet at 31 December 2025 and market data, to bridge from Enterprise Value to value per share."""

    share_price: float = 1_653.00  # € per share, close on 2 October 2026
    shares_outstanding: float = 385_417_665  # issued and outstanding at 31 December 2025 (balance sheet)
    cash: float = 13_321.9e6  # cash and cash equivalents €12,916.0m + short-term investments €405.9m
    debt: float = 4_390.9e6  # short-term borrowings and current LT debt €1,681.9m + long-term debt €2,709.0m
    lease_liabilities: float = 251.4e6  # note 14
    non_operating_assets: float = 2_143.3e6  # equity method investments €822.6m (Zeiss) + equity investments €1,320.7m
    years_since_balance_sheet: float = 275 / 365  # 31 December 2025 → 2 October 2026
    dividends_paid_since: float = 6.18  # € per share: €1.60 (Feb) + €2.70 final 2025 (May) + €1.88 interim (Aug 2026)

    @property
    def net_cash(self) -> float:
        """Net cash (positive) at 31 December 2025, leases included as debt."""
        return self.cash - self.debt - self.lease_liabilities


@dataclass(frozen=True)
class OperatingAssumptions:
    """Operating assumptions treated as certain (not simulated).

    Three stages: 2026–2030 explicit forecast, 2031–2040 fade (growth converges to the perpetual rate),
    then a terminal value at the end of 2040.
    """

    horizon_years: int = 15  # explicit cash flows 2026–2040
    years_to_target: int = 5  # 2030 is the 5th forecast year
    revenue_last_year: float = 32_667.3e6  # total net sales 2025
    revenue_first_year: float = 44.0e9  # 2026 guidance €43–45bn (Q2 2026 results), midpoint
    gross_margin_first_year: float = 0.55  # 2026 guidance 54–56% (Q2 2026 results), midpoint
    opex_ratio_first_year: float = 0.17  # R&D + SG&A in H1 2026: €3.07bn on €18.07bn of sales
    tax_rate: float = 0.17  # 2026 annualised effective tax rate guidance (Annual Report 2025, page 52)
    depreciation_rate: float = 0.035  # D&A / sales: 3.1% in 2025 (€1,025.9m), rising with the capacity build-out
    capex_rate: float = 0.05  # PP&E + intangibles / sales: 5.0% in 2025, 7.4% in 2024, 8.0% in 2023
    working_capital_rate: float = 0.10  # net working capital invested per € of additional sales (assumption)
    # ROIC 2025 ≈ 106%: NOPAT €9.3bn (EBIT €11.3bn × (1 − 17.7%)) on €8.8bn of invested capital (equity €19.6bn
    # − net cash €8.7bn − non-operating assets €2.1bn), flattered by customer prepayments. In perpetuity, new
    # capital is assumed to earn 40%: still far above the cost of capital (EUV monopoly), well below today's level.
    terminal_ronic: float = 0.40
    terminal_method: str = "value_driver"
    exit_multiple: float = 20.0  # EV / next-year NOPAT, cross-check only (mature semiconductor-equipment level)


@dataclass(frozen=True)
class UncertainInputs:
    """The eight simulated drivers."""

    revenue_2030: PertMixture
    gross_margin_2030: PertParams
    opex_ratio: NormalParams
    growth_2031: PertParams
    terminal_growth: PertParams
    risk_free: NormalParams
    beta: PertParams
    equity_premium: PertParams


ASML_MARKET = MarketData()
ASML_OPERATIONS = OperatingAssumptions()

ASML_INPUTS = UncertainInputs(
    # Three regimes instead of a single range. The 2024 Investor Day target (€44–60bn) is outdated now that 2026
    # is guided at €43–45bn. Downturn (6% CAGR from 2026): AI capex digestion, tighter export controls on China
    # (29% of 2025 sales); semiconductor equipment has had a downturn every 3–5 years. Base (14% CAGR): AI-driven
    # capacity build-out. AI super-cycle (23% CAGR): more EUV layers per wafer, fast High-NA adoption.
    revenue_2030=PertMixture(
        components=(PertParams(45e9, 55e9, 65e9), PertParams(60e9, 75e9, 90e9), PertParams(85e9, 100e9, 125e9)),
        weights=(0.20, 0.55, 0.25),
        names=("Downturn", "Base", "AI super-cycle"),
    ),
    # Company target for 2030: 56–60% (52.8% in 2025, 54–56% guided for 2026). EUV and High-NA mix and the
    # growing installed base push the margin up; dilutive early High-NA systems cap the upside.
    gross_margin_2030=PertParams(minimum=0.54, mode=0.59, maximum=0.62),
    # R&D + SG&A / sales at scale: 18.2% in 2025, 17.0% in H1 2026. Costs grow slower than sales.
    opex_ratio=NormalParams(mean=0.15, sd=0.015),
    # Revenue growth in 2031, fading linearly to the perpetual rate by 2040. Semiconductor equipment is
    # cyclical: a flat period after the AI build-out is possible; the EUV monopoly supports a long fade.
    growth_2031=PertParams(minimum=0.0, mode=0.08, maximum=0.14),
    # Perpetual nominal growth after 2040: about inflation (2%) plus a share of real growth in chip demand.
    terminal_growth=PertParams(minimum=0.015, mode=0.025, maximum=0.035),
    # Cost of equity = Rf + β × ERP. Debt is under 1% of value, so WACC ≈ cost of equity.
    # Rf: 10-year Bund yield, late September 2026.
    risk_free=NormalParams(mean=0.036, sd=0.0025),
    # β: 1.15 (1-year raw) to 1.43 (5-year, Blume-adjusted).
    beta=PertParams(minimum=1.0, mode=1.2, maximum=1.45),
    # ERP: 4.23% implied premium (Damodaran, January 2026); 5.5% at the top of the range used by practitioners.
    equity_premium=PertParams(minimum=0.0375, mode=0.0425, maximum=0.055),
)

# Revenue–gross margin correlation: ASML's own targets pair low revenue with low margin (€44bn ↔ 56%) and high
# revenue with high margin (€60bn ↔ 60%), through operating leverage and EUV mix. Also tested at 0 and +0.8.
REVENUE_MARGIN_CORRELATION = 0.5
CORRELATIONS_TO_COMPARE = (0.0, 0.5, 0.8)

ASML_DEFAULT_ITERATIONS = 100_000

# First version of the model (10-year horizon, Gordon growth on the 2035 FCF, perpetual growth fixed at 2.5%,
# WACC ~ Normal(9.0%, 0.75%), single PERT €55/75/100bn for 2030 revenue), kept for comparison.
# Results of scripts/run_asml.py at that version: 1,000,000 iterations, seed 42.
FIRST_VERSION = {
    "operations": OperatingAssumptions(horizon_years=10, terminal_method="gordon_fcf"),
    "central_drivers": {"revenue_2030": 75e9, "gross_margin_2030": 0.59, "opex_ratio": 0.15, "growth_2031": 0.08,
                        "terminal_growth": 0.025, "wacc": 0.09},
    "results": {"Value, central scenario": 1_068.0, "Mean value per share": 1_083.0, "P5": 795.0, "P50": 1_062.0,
                "P95": 1_440.0, "P(value < price)": 0.991},
}
