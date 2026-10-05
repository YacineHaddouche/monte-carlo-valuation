# ASML: how likely is the share to be worth less than its price?

*DCF valuation with Monte Carlo simulation · financials from the 2025 Annual Report (US GAAP), 2026
guidance from the Q2 2026 results, share price at 2 October 2026*

## 1. Question and short answer

ASML is the sole supplier of EUV lithography systems, the machines needed to print the most advanced
chips. In 2025 it reported €32.7bn of sales (+15.6%), a 52.8% gross margin and €9.6bn of net income. In
July 2026 it raised its 2026 sales guidance to €43–45bn on the back of AI-driven demand. The share
closed at €1,653 on 2 October 2026, a market capitalisation of about €637bn, or roughly 46 times our
estimate of 2026 operating profit after tax.

A single-scenario DCF hides how much this price depends on a few assumptions. We therefore simulate
1,000,000 scenarios in which the five value drivers move at the same time, each following a justified
probability distribution. The question is: **what is the probability that the intrinsic value per share
is below the share price?**

**Answer: 99.1%** (standard error 0.01 point). Our central scenario gives €1,068 per share, and even the
P95 (€1,440) is below the share price. The reverse DCF shows why: with the other drivers at their central
value, the price requires either **€122bn of revenue in 2030**, about twice the top of ASML's own 2030
range (€44–60bn), or a **WACC of 6.8%**. The market is pricing a much longer and stronger AI cycle, or a
much lower risk premium, than our assumptions.

## 2. Model

**Scope.** Nominal-euro DCF. Year 0 is 31 December 2025, the date of the latest annual balance sheet.
Cash flows are projected from 2026 to 2035, followed by a Gordon growth terminal value at 2.5%.

**Calculation chain, for each year:**

- **Revenue.** 2026 = €44bn (midpoint of the updated guidance). From 2026 to 2030, revenue grows at a
  constant rate up to the simulated 2030 level. In 2031 it grows at the simulated rate, which then fades
  linearly towards terminal growth by 2035.
- **Gross margin.** 55% in 2026 (guidance midpoint), moving linearly to the simulated 2030 level, then
  flat.
- **Operating costs.** R&D + SG&A at 17.0% of sales in 2026 (H1 2026 actual), moving linearly to the
  simulated mature level by 2030.
- **EBIT** = sales × (gross margin − operating-cost ratio). R&D and SG&A already include depreciation.
- **Tax** at 17%, the 2026 effective-rate guidance.
- **FCF** = EBIT − tax + D&A − capex − investment in working capital, with:
  - D&A at 3.5% of sales (3.1% in 2025);
  - capex (property, plant, equipment and intangibles) at 5.0% of sales (5.0% in 2025, 7.4% in 2024);
  - working capital at 10% of each additional euro of sales. Inventories (€11.4bn) are largely funded by
    customer prepayments (€19.4bn of contract liabilities), which unwound in H1 2026.
- FCFs are discounted at the WACC.

**From Enterprise Value to value per share.**

- Add net cash at 31 December 2025: €13.32bn of cash and short-term investments − €4.39bn of debt
  (Eurobonds and borrowings) − €0.25bn of leases = **€8.68bn**.
- Add non-operating assets at book value: the 24.9% stake in Carl Zeiss SMT (€0.82bn) and equity
  investments, mainly Mistral AI (€1.32bn).
- Divide by the 385.4m shares outstanding at 31 December 2025.
- Roll the result forward to the share-price date: grow it at the cost of capital for 9 months, then
  subtract the €6.18 of dividends per share paid in between (€1.60 + €2.70 + €1.88).

**Consistency with reported figures.** The central scenario gives a 2026 FCF of €12.1bn, against
€11.0bn of free cash flow reported for 2025 and an expected 35% jump in sales. Its 2026 operating margin
(38%) compares with 34.6% in 2025.

## 3. Uncertain drivers and distributions

| Driver | Distribution | Parameters | Rationale |
| --- | --- | --- | --- |
| Revenue 2030 | PERT | €55bn / €75bn / €100bn | The 2024 Investor Day range (€44–60bn) is outdated now that 2026 is guided at €43–45bn. Mode = 14% a year from 2026 (AI capacity build-out); minimum = 6% a year (cycle downturn, tighter export controls on China, which was 29% of 2025 sales); maximum = 23% a year. |
| Gross margin 2030 | PERT | 54% / 59% / 62% | Company target for 2030: 56–60%. 52.8% in 2025, 54–56% guided for 2026. EUV mix and installed-base services push it up; early High-NA systems dilute it. |
| R&D + SG&A / sales (mature) | Normal | mean 15%, SD 1.5% | 18.2% in 2025, 17.0% in H1 2026: costs grow more slowly than sales. |
| Revenue growth in 2031 (fading to 2035) | PERT | 0% / 8% / 14% | Semiconductor equipment is cyclical: a flat period after the AI build-out is possible, while EUV adoption in memory supports growth. |
| WACC | Normal | mean 9.0%, SD 0.75% | Rf 3.6% (10-year Bund, late September 2026) + β 1.2 × equity risk premium 4.5% ⇒ Ke ≈ 9.0%. β ranges from 1.15 (1-year raw) to 1.43 (5-year, Blume-adjusted). Debt is under 1% of value, so WACC ≈ Ke. |

**One draw applies to the whole horizon**: the model captures uncertainty about the level of each
driver, not year-to-year cycles.

**Correlation.** Revenue and gross margin are linked through a Gaussian copula (Cholesky, then
U = Φ(X), then each inverse distribution), with **ρ = +0.5**. ASML's own targets pair them: €44bn of
revenue goes with a 56% margin, €60bn with 60%, through operating leverage and the EUV mix. We also test
ρ = 0 and ρ = +0.8. The other drivers are independent.

## 4. Results (1,000,000 iterations, seed 42)

![Value-per-share distribution and tornado chart](../results/asml_valuation.png)

| Statistic | Value |
| --- | --- |
| Value, central scenario (modes and means) | €1,068 |
| Mean value per share (SE) | €1,083 (€0.20) |
| Standard deviation | €200 |
| P5 / P50 / P95 | €795 / €1,062 / €1,440 |
| **P(value < share price of €1,653)** | **99.1%** (SE 0.01 pt) |

**Reading the results.**

1. **The share price sits in the far right tail.** Only 0.9% of scenarios exceed it. They combine a
   low WACC, revenue near €100bn in 2030 and sustained growth afterwards.
2. **Terminal value dominates.** In the central scenario, 61% of the Enterprise Value (€377bn) comes from
   the terminal value. The valuation is above all a view on ASML's earning power after 2035.
3. **The correlation barely changes the answer.** A positive revenue–margin correlation widens the
   spread (SD €190 → €205 from ρ = 0 to ρ = +0.8), but P(value < price) only moves from 99.3% to 99.0%.

## 5. Sensitivities: what does the market assume?

**Tornado chart.** Each driver moves from its P5 to its P95, the others staying at their central value:

| Driver | Driver P5 → P95 | Value per share | Swing |
| --- | --- | --- | --- |
| WACC | 7.8% → 10.2% | €1,328 → €892 | €435 |
| Revenue 2030 | €62bn → €90bn | €907 → €1,259 | €352 |
| Revenue growth 2031 (fading) | 3.2% → 11.9% | €969 → €1,155 | €186 |
| R&D + SG&A / sales | 12.5% → 17.5% | €1,125 → €1,011 | €114 |
| Gross margin 2030 | 56.1% → 61.0% | €1,001 → €1,114 | €113 |

The **discount rate** and the **size of the 2030 market** dominate. Margins matter much less: ASML's
profitability is already high, and the uncertainty lies in volumes and in the risk premium.

**Reverse DCF.** We solve for the value of each driver that exactly justifies the €1,653 share price,
with the others at their central value (`scipy.optimize.brentq`):

- **2030 revenue of €122bn** (central: €75bn; company range: €44–60bn), i.e. 29% growth a year from 2026;
- or **30% revenue growth in 2031**, fading to 2035;
- or a **WACC of 6.8%** (central: 9.0%), i.e. a β of about 0.7 with our risk-free rate and premium.

## 6. Limitations

- **Distributions are judgement calls.** In particular, the 2030 revenue range was set above the company's
  own (outdated) target. Analysts with a more optimistic view on AI demand would reach higher values: the
  average analyst price target is about €2,045. The dashboard lets every parameter be changed.
- **WACC is the decisive input and the hardest to pin down.** A 1.2 β and a 4.5% premium are standard
  but not unique choices; at a 7.5% WACC the central value rises by about 30%, to €1,401.
- **No explicit cycle.** One level per driver over the whole horizon smooths the semiconductor cycle.
  Real cash flows are lumpier.
- **Capital returns.** Buybacks at a price above intrinsic value would transfer value from remaining to
  selling shareholders; the model ignores this, as well as future share-based dilution.
- **Mixed dates.** The balance sheet is at 31 December 2025, the guidance at July 2026 and the share
  price at October 2026. The roll-forward adjusts for time and dividends, not for news since then.

## 7. Conclusion

With assumptions that already go well beyond ASML's own 2030 targets, **99.1% of simulated scenarios give
an intrinsic value below the €1,653 share price**, and the central value is €1,068. The market price can
be justified, but only by roughly doubling the 2030 revenue opportunity or by applying a cost of capital
of about 6.8%. ASML is an exceptional business; the question this analysis raises is not its quality, but
how much of a long AI super-cycle the current price already assumes.

---

**Sources.** ASML, *Annual Report 2025* (US GAAP): consolidated statements of operations, balance sheet and
cash flows (pages 276–281), notes 2, 14 and 16, CFO letter (page 52); ASML Q2 2026 results press release
(15 July 2026); Euronext Amsterdam share price (via stockanalysis.com); 10-year Bund yield (Trading
Economics, September 2026); β (Intrinio).

**Reproducibility.** `python scripts/run_asml.py` and `streamlit run Investment_project_NPV.py`
("ASML valuation" page).
