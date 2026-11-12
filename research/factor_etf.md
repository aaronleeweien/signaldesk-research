# SignalDesk — Institutional-Style Implemented Momentum ETF Report

**Live-history systematic strategy:** SPMO buy-and-hold / monthly accumulation.
Latest complete US market session: 2026-11-10
**RESEARCH ONLY; NOT A GUARANTEED OR APPROVED LIVE TRADE.**

## Actual-ETF price backtest on matched market days, 2016–2026

| Method | Annual return | Worst drawdown | Beta to VOO | Simulated orders | Fees USD |
|---|---:|---:|---:|---:|---:|
| VOO DCA | 14.92% | -34.00% | 1.00 | 122 | 14.09 |
| SPMO DCA | 17.99% | -30.96% | 1.03 | 122 | 14.09 |
| QQQ DCA | 19.53% | -35.13% | 1.17 | 122 | 14.09 |
| MTUM DCA | 14.30% | -34.08% | 1.07 | 122 | 14.09 |
| SPMO/VOO 50-50 | 16.57% | -32.48% | 1.01 | 244 | 28.40 |
| SPMO-VOO 6M Rotation | 16.52% | -34.00% | 1.03 | 140 | 495.08 |
| SPMO Trend + SHY | 13.97% | -20.97% | 0.47 | 137 | 517.33 |

## Distinct retrospective windows

| Model | 2016–2020 annual % | 2021–2023 annual % | 2024–latest annual % |
|---|---:|---:|---:|
| VOO DCA | 16.0 | 9.75 | 18.94 |
| SPMO DCA | 18.38 | 8.65 | 28.07 |
| QQQ DCA | 26.68 | 9.7 | 20.02 |
| MTUM DCA | 20.39 | 0.03 | 21.7 |
| SPMO/VOO 50-50 | 17.25 | 9.3 | 23.68 |
| SPMO-VOO 6M Rotation | 15.77 | 8.15 | 27.35 |
| SPMO Trend + SHY | 15.34 | 5.52 | 21.45 |

## Monthly factor-aware risk diagnostics

- SPMO DCA, vs VOO: estimated beta 1.0045, alpha 3.0652%/year, HAC statistic 1.0186, bootstrap 90% annual active-return interval [-2.2616, 8.7338]%.
- SPMO-VOO 6M Rotation, vs VOO: estimated beta 1.0265, alpha 1.406%/year, HAC statistic 0.5908, bootstrap 90% annual active-return interval [-2.2274, 6.0224]%.
- SPMO Trend + SHY, vs VOO: estimated beta 0.5448, alpha 5.9016%/year, HAC statistic 1.836, bootstrap 90% annual active-return interval [-6.4491, 4.7884]%.

## Model target exposures for estimated next session (PAPER ONLY)

- VOO DCA: VOO 100%
- SPMO DCA: SPMO 100%
- QQQ DCA: QQQ 100%
- MTUM DCA: MTUM 100%
- SPMO/VOO 50-50: SPMO 50%, VOO 50%
- SPMO-VOO 6M Rotation: VOO 100%
- SPMO Trend + SHY: SHY 100%

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
