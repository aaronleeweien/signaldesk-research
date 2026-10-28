# SignalDesk Institutional Quant Research Report V4

## Decision
**EXPLORATORY / NOT APPROVED FOR REAL TRADING.**
Strategy: Top-5 cross-sectional momentum, equal 20% weights, monthly ranking of a fixed survivor-stock list.
Data through: 2026-10-27

## Return and risk evidence: 2019 to latest

| Model | Annual TWR % | Worst fall % | Daily volatility % | Beta to VOO | Simulated orders | Fees USD |
|---|---:|---:|---:|---:|---:|---:|
| VOO DCA | 17.42 | -34.01 | 19.25 | 1.00 | 94 | 11.29 |
| QQQ DCA | 22.82 | -35.14 | 23.86 | 1.15 | 94 | 11.29 |
| Top-5 Momentum | 23.42 | -30.19 | 27.23 | 1.11 | 571 | 603.70 |
| Top-5 Trend Filter | 20.51 | -33.83 | 26.76 | 1.08 | 578 | 611.59 |
| Top-5 Defensive | 10.57 | -18.13 | 16.01 | 0.56 | 669 | 381.39 |
| Static Equal Weight | 19.80 | -33.17 | 19.21 | 0.96 | 2817 | 68.10 |

## Statistical evidence: monthly factor-aware diagnostics

| Test | Estimated annual alpha % | Monthly beta | HAC t-stat | Approx p | Bootstrap 90% annual active-return CI |
|---|---:|---:|---:|---:|---|
| vs VOO | 5.6126 | 1.0428 | 0.9993 | 0.3176 | [-3.2647, 16.3542]% |
| vs QQQ | 4.3056 | 0.859 | 0.8156 | 0.4147 | [-8.0283, 10.8592]% |

HAC uses Newey-West 3-lag standard errors. Approximate p-values use a normal approximation,
bootstrap is a three-month circular block bootstrap over the same retrospective data.
Neither method corrects survivorship, data-snooping or regime selection bias.

## Cost sensitivity, 2019 to latest

| Fee per side | Momentum annual % | VOO annual % | QQQ annual % |
|---|---:|---:|---:|
| 0 bps | 24.12 | 17.45 | 22.85 |
| 10 bps | 23.42 | 17.42 | 22.82 |
| 30 bps | 22.02 | 17.35 | 22.75 |

## Next paper targets, not brokerage instructions

- INTC: 20%
- MRK: 20%
- CSCO: 20%
- CAT: 20%
- TXN: 20%

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
