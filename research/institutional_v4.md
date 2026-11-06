# SignalDesk Institutional Quant Research Report V4

## Decision
**EXPLORATORY / NOT APPROVED FOR REAL TRADING.**
Strategy: Top-5 cross-sectional momentum, equal 20% weights, monthly ranking of a fixed survivor-stock list.
Data through: 2026-11-05

## Return and risk evidence: 2019 to latest

| Model | Annual TWR % | Worst fall % | Daily volatility % | Beta to VOO | Simulated orders | Fees USD |
|---|---:|---:|---:|---:|---:|---:|
| VOO DCA | 16.64 | -34.01 | 19.31 | 1.00 | 95 | 11.39 |
| QQQ DCA | 21.05 | -35.14 | 23.99 | 1.16 | 95 | 11.39 |
| Top-5 Momentum | 20.48 | -30.73 | 27.42 | 1.11 | 577 | 620.77 |
| Top-5 Trend Filter | 18.31 | -33.83 | 26.89 | 1.08 | 585 | 633.44 |
| Top-5 Defensive | 9.19 | -19.77 | 16.11 | 0.56 | 677 | 391.10 |
| Static Equal Weight | 19.22 | -33.17 | 19.25 | 0.96 | 2847 | 70.77 |

## Statistical evidence: monthly factor-aware diagnostics

| Test | Estimated annual alpha % | Monthly beta | HAC t-stat | Approx p | Bootstrap 90% annual active-return CI |
|---|---:|---:|---:|---:|---|
| vs VOO | 3.5959 | 1.0682 | 0.5855 | 0.5582 | [-4.8881, 15.3092]% |
| vs QQQ | 2.7104 | 0.8833 | 0.4808 | 0.6307 | [-9.116, 10.0236]% |

HAC uses Newey-West 3-lag standard errors. Approximate p-values use a normal approximation,
bootstrap is a three-month circular block bootstrap over the same retrospective data.
Neither method corrects survivorship, data-snooping or regime selection bias.

## Cost sensitivity, 2019 to latest

| Fee per side | Momentum annual % | VOO annual % | QQQ annual % |
|---|---:|---:|---:|
| 0 bps | 21.17 | 16.67 | 21.09 |
| 10 bps | 20.48 | 16.64 | 21.05 |
| 30 bps | 19.11 | 16.57 | 20.99 |

## Next paper targets, not brokerage instructions

- INTC: 20%
- MRK: 20%
- TXN: 20%
- CSCO: 20%
- XOM: 20%

## Evidence approval gates

- predeclared ex ante universe: **FAIL**
- includes historical delistings: **FAIL**
- risk adjusted vs qqq robust: **FAIL**
- robust vs voo at 30bps: **PASS**
- independent future paper evidence: **FAIL**
- all gates pass: **FAIL**

## Important limitations

- Severe survivorship/selection bias: thirty companies were picked knowing they survived to 2026.
- No delisted stock return history or point-in-time constituent database is included.
- Historical 2023–2026 is retrospective and has already informed our research; not unseen confirmation.
- Momentum portfolio is concentrated in five individual stocks; market beta can be much larger than one.
- Bootstrap uncertainty and Newey-West regression are descriptive and do NOT correct survivor bias or multiple model testing.
- Trading fee sensitivity excludes FX conversion, commissions minimums, tax, bid-ask spreads and price gaps.
- Market signals use prior completed close, next-session execution estimated at adjusted open, no broker connection.
- A future order must be checked against real quotes, exchange calendar, spread, broker lot size, and personal risk limits.

This is a research artifact, not personalized investment advice or a guarantee of profitable trades.
