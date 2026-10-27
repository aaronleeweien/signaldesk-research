# SignalDesk Objective Strategy Validation — Protocol V2

**Status: REJECT LIVE TRADING; RESEARCH/PAPER ONLY**
Market close: 2026-10-26

**Important:** These historical windows have already been inspected. They are NOT clean unseen out-of-sample data.

## Predeclared daily strategies vs passive investing

| Strategy | 2017–21 annual % | 2022+ annual % | 2022+ drawdown % | 2022+ orders/year | 2022+ annual after 30bps % |
|---|---:|---:|---:|---:|---:|
| Daily Breakout Top2 | 8.25 | 5.16 | -20.13 | 81.9 | 0.37 |
| SPMO SMA200 | 12.62 | 10.38 | -26.9 | 25.8 | 7.2 |
| VOO SMA200 | 12.7 | 7.41 | -23.33 | 24.3 | 4.66 |
| SPMO SMA200 Buffer | 15.79 | 11.25 | -27.69 | 16.8 | 10.04 |
| VOO DCA | 18.19 | 11.83 | -24.56 | 12.1 | — |
| SPMO DCA | 20.16 | 18.81 | -22.77 | 12.1 | — |
| QQQ DCA | 28.12 | 13.41 | -34.88 | 12.1 | — |

## Objective strategy gates
At least VOO and SPMO net returns, drawdown controls, low turnover, 30bps cost stress and bootstrap confidence must pass before further consideration.

- **Daily Breakout Top2**: historical score **FAIL**; failed checks: stress_return_above_VOO, stress_return_above_SPMO, trades_under_52_a_year, positive_relative_to_VOO_at_30bps, bootstrap_lower_excess_above_zero, clean_independent_holdout_available, live_forward_paper_record_long_enough
- **SPMO SMA200**: historical score **FAIL**; failed checks: stress_return_above_VOO, stress_return_above_SPMO, risk_drawdown_within_three_points_of_SPMO, positive_relative_to_VOO_at_30bps, bootstrap_lower_excess_above_zero, clean_independent_holdout_available, live_forward_paper_record_long_enough
- **VOO SMA200**: historical score **FAIL**; failed checks: stress_return_above_VOO, stress_return_above_SPMO, positive_relative_to_VOO_at_30bps, bootstrap_lower_excess_above_zero, clean_independent_holdout_available, live_forward_paper_record_long_enough
- **SPMO SMA200 Buffer**: historical score **FAIL**; failed checks: stress_return_above_VOO, stress_return_above_SPMO, risk_drawdown_within_three_points_of_SPMO, positive_relative_to_VOO_at_30bps, bootstrap_lower_excess_above_zero, clean_independent_holdout_available, live_forward_paper_record_long_enough

**Paper-only even if all historical checks pass.** No reliable future trading edge has been verified.

## Paper-trading protocol

63 future market sessions minimum, three calendar months, daily timestamped targets, next-open fills, no hidden restatements, VOO/SPMO parallel paper portfolios.

## What we are NOT going to do

Tune dozens of parameters until the already-seen 2022–2026 period suddenly looks profitable; that would be overfitting.
