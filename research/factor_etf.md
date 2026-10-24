# SignalDesk — Institutional-Style Implemented Momentum ETF Report

**Live-history systematic strategy:** SPMO buy-and-hold / monthly accumulation.
Latest complete US market session: 2026-10-23
**RESEARCH ONLY; NOT A GUARANTEED OR APPROVED LIVE TRADE.**

## Actual-ETF price backtest on matched market days, 2016–2026

| Method | Annual return | Worst drawdown | Beta to VOO | Simulated orders | Fees USD |
|---|---:|---:|---:|---:|---:|
| VOO DCA | 15.15% | -34.00% | 1.00 | 121 | 13.99 |
| SPMO DCA | 18.88% | -30.96% | 1.02 | 121 | 13.99 |
| QQQ DCA | 20.15% | -35.13% | 1.17 | 121 | 13.99 |
| MTUM DCA | 15.30% | -34.08% | 1.06 | 121 | 13.99 |
| SPMO/VOO 50-50 | 17.12% | -32.48% | 1.01 | 242 | 26.47 |
| SPMO-VOO 6M Rotation | 16.95% | -34.00% | 1.03 | 138 | 414.47 |
| SPMO Trend + SHY | 14.25% | -20.97% | 0.48 | 135 | 452.56 |

## Distinct retrospective windows

| Model | 2016–2020 annual % | 2021–2023 annual % | 2024–latest annual % |
|---|---:|---:|---:|
| VOO DCA | 16.0 | 9.75 | 19.86 |
| SPMO DCA | 18.38 | 8.65 | 31.75 |
| QQQ DCA | 26.68 | 9.7 | 22.27 |
| MTUM DCA | 20.39 | 0.03 | 25.7 |
| SPMO/VOO 50-50 | 17.25 | 9.3 | 25.91 |
| SPMO-VOO 6M Rotation | 15.77 | 8.15 | 29.23 |
| SPMO Trend + SHY | 15.34 | 5.52 | 22.67 |

## Monthly factor-aware risk diagnostics

- SPMO DCA, vs VOO: estimated beta 0.9978, alpha 3.7021%/year, HAC statistic 1.3109, bootstrap 90% annual active-return interval [-1.4793, 9.1317]%.
- SPMO-VOO 6M Rotation, vs VOO: estimated beta 1.0232, alpha 1.6092%/year, HAC statistic 0.693, bootstrap 90% annual active-return interval [-2.1341, 6.2583]%.
- SPMO Trend + SHY, vs VOO: estimated beta 0.5415, alpha 6.099%/year, HAC statistic 1.9177, bootstrap 90% annual active-return interval [-6.5206, 4.6235]%.

## Model target exposures for estimated next session (PAPER ONLY)

- VOO DCA: VOO 100%
- SPMO DCA: SPMO 100%
- QQQ DCA: QQQ 100%
- MTUM DCA: MTUM 100%
- SPMO/VOO 50-50: SPMO 50%, VOO 50%
- SPMO-VOO 6M Rotation: SPMO 100%
- SPMO Trend + SHY: SPMO 100%

## Published sources / caveats

- Invesco SPMO sponsor product page: https://www.invesco.com/us/en/financial-products/etfs/invesco-sp-500-momentum-etf.html
- Jegadeesh and Titman (1993) momentum: https://doi.org/10.1111/j.1540-6261.1993.tb04702.x
- Daniel & Moskowitz (2016) momentum crashes: https://doi.org/10.1016/j.jfineco.2015.12.002
- Bailey et al. (2017) backtest overfitting: https://scholarworks.wmich.edu/math_pubs/42/

**Method and bias:** This uses actual historical ETF prices (not an invented 2016 portfolio of today's winners), with contemporaneously implemented fund history. That limits historical constituent survivorship bias but does not eliminate data-snooping, concentration, changing risk exposures or future uncertainty.

- Even live ETF history is retrospective to a decision made in 2026. SPMO has not proven future outperformance.
- SPMO holds momentum stocks and may become concentrated in industries or firms, and can suffer sudden reversals.
- The index methodology, management and holdings can evolve over time; live historical fund returns are used, not a reconstructed 2026 constituent list.
- Higher returns versus VOO may reflect equity factor and risk exposures; regression is descriptive, not causal.
- Trend and relative rotation overlays are experiments and must beat uncomplicated SPMO DCA after costs.
- Dividends are approximated by price adjustment and fractional unit assumptions; broker FX, taxes, spreads and order minimums omitted.
- No intraday prices; exit thresholds and month-start trade targets are speculative until the completed market signal is recorded before execution.
