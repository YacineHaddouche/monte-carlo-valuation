# Excel reference model

`monte_carlo_model.xlsx` is the Excel implementation of the three Monte Carlo models. The Python code is
validated against it.

| Sheet | Content |
| --- | --- |
| Cover | Project description, live key results, sheet guide and colour code |
| Independent | Three independent Normal inputs |
| Justified | PERT price, Normal demand capped by capacity, variable cost fitted on historical data |
| Correlated | Price–Demand correlation through a Gaussian copula, plus a ρ sensitivity table |
| Validation | Excel (5,000 iterations, live) vs Python (1,000,000 iterations) with z-scores |

Each model sheet follows the same layout: base-case inputs, distributions (one random draw), cash flows
and NPV, then simulation results. An Excel Data Table (columns L–O) re-evaluates the model 5,000 times,
and columns Q–V hold the histogram bins.

Blue cells are inputs, black cells are formulas and green cells link to another sheet. The workbook uses
"Automatic except for data tables" calculation: press F9 (Mac: Cmd + =) to rerun the simulation.
