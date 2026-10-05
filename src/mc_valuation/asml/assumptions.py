"""ASML valuation assumptions, with their sources.

Main sources:
- ASML Annual Report 2025 (US GAAP): consolidated statements of operations, balance sheet and cash flows
  (pages 276–281), net system sales per technology (note 2), Eurobonds and leases (notes 14 and 16),
  2026 outlook and 2030 revenue opportunity (CFO letter, page 52);
- ASML Q2 2026 results (15 July 2026): updated 2026 guidance, 2026 dividends;
- Euronext Amsterdam share price (ASML) at the close of 2 October 2026.
"""

from dataclasses import dataclass

from mc_valuation.distributions import NormalParams, PertParams


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
    """Operating assumptions treated as certain (not simulated)."""

    horizon_years: int = 10  # explicit forecast 2026–2035
    years_to_target: int = 5  # 2030 is the 5th forecast year
    revenue_last_year: float = 32_667.3e6  # total net sales 2025
    revenue_first_year: float = 44.0e9  # 2026 guidance €43–45bn (Q2 2026 results), midpoint
    gross_margin_first_year: float = 0.55  # 2026 guidance 54–56% (Q2 2026 results), midpoint
    opex_ratio_first_year: float = 0.17  # R&D + SG&A in H1 2026: €3.07bn on €18.07bn of sales
    tax_rate: float = 0.17  # 2026 annualised effective tax rate guidance (Annual Report 2025, page 52)
    depreciation_rate: float = 0.035  # D&A / sales: 3.1% in 2025 (€1,025.9m), rising with the capacity build-out
    capex_rate: float = 0.05  # PP&E + intangibles / sales: 5.0% in 2025, 7.4% in 2024, 8.0% in 2023
    working_capital_rate: float = 0.10  # net working capital invested per € of additional sales (assumption)
    terminal_growth: float = 0.025  # perpetual nominal growth after 2035


@dataclass(frozen=True)
class UncertainInputs:
    """The five simulated drivers."""

    revenue_2030: PertParams
    gross_margin_2030: PertParams
    opex_ratio: NormalParams
    growth_2031_2035: PertParams
    wacc: NormalParams


ASML_MARKET = MarketData()
ASML_OPERATIONS = OperatingAssumptions()

ASML_INPUTS = UncertainInputs(
    # 2030 target set at the 2024 Investor Day: €44–60bn. The 2026 guidance was then raised to €43–45bn,
    # so the target is outdated. Mode = 14% CAGR from 2026 (AI-driven capacity build-out); min = 6% CAGR
    # (cycle downturn, export restrictions on China, which is 29% of 2025 sales); max = 23% CAGR.
    revenue_2030=PertParams(minimum=55e9, mode=75e9, maximum=100e9),
    # Company target for 2030: 56–60% (52.8% in 2025, 54–56% guided for 2026). EUV and High-NA mix and the
    # growing installed base push the margin up; dilutive early High-NA systems cap the upside.
    gross_margin_2030=PertParams(minimum=0.54, mode=0.59, maximum=0.62),
    # R&D + SG&A / sales at scale: 18.2% in 2025, 17.0% in H1 2026. Costs grow slower than sales.
    opex_ratio=NormalParams(mean=0.15, sd=0.015),
    # Revenue growth in 2031, fading linearly towards terminal growth by 2035. Semiconductor equipment is
    # cyclical: a flat or declining period after the AI build-out is possible.
    growth_2031_2035=PertParams(minimum=0.0, mode=0.08, maximum=0.14),
    # Rf 3.6% (10-year Bund, late September 2026) + β 1.2 × equity risk premium 4.5% ⇒ Ke ≈ 9.0%.
    # β ranges from 1.15 (1-year raw) to 1.43 (5-year, Blume-adjusted). Debt is under 1% of value: WACC ≈ Ke.
    wacc=NormalParams(mean=0.09, sd=0.0075),
)

# Revenue–gross margin correlation: ASML's own targets pair low revenue with low margin (€44bn ↔ 56%) and high
# revenue with high margin (€60bn ↔ 60%), through operating leverage and EUV mix. Also tested at 0 and +0.8.
REVENUE_MARGIN_CORRELATION = 0.5
CORRELATIONS_TO_COMPARE = (0.0, 0.5, 0.8)

ASML_DEFAULT_ITERATIONS = 100_000
