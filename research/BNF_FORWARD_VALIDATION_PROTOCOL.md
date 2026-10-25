# BNF-inspired mean-reversion v1 — prospective validation registration

**Registered 2026-10-25 (Asia/Singapore).** This document is an advance specification, **not** evidence of profitability and **not** a live-trading authorization. It cannot retroactively turn previously inspected 2019–2026 prices into an independent test. Preserve this document and its Git history. If a rule changes, create v2 with a new start date; do not overwrite v1 results.

## Decision as of registration

**Keep ordinary VOO dollar-cost averaging (DCA); do not execute any BNF-inspired real-money trades.** The October 23, 2026 close yielded 2 retrospective passes (PLTR and FROG) among 88 tested surviving US stocks, but zero new BNF paper-entry setups and zero independently observed forward fills. The existing `research/forward_shadow.json` follows **ETF** models; it is NOT a BNF forward-trading journal. Neither 88 priced names nor 10,931 directory listings mean the whole investable market was validated.

## Frozen strategy (no optimization using inspected history)

- Version: `bnf_inspired_mean_reversion_v1_20261024` as implemented in `research/kotegawa_reversion.py`.
- Market filter: after a **completed** US session, VOO closes below its trailing 50-session simple moving average (SMA50).
- Candidate signal: that stock's completed close is at least 10% below its trailing SMA25; only the first signal of an oversold episode qualifies.
- Paper BUY at the **next actual regular-session open** only when the signal was durably recorded before that open.
- Paper SELL at the **next actual regular-session open** after the prior completed close recovered to SMA25, fell to or below 92% of actual paper entry price, or the position reached five sessions. Overnight gaps may exceed the stop.
- Paper account: US$2,000 initial, US$100 deposited monthly; fractional units and no borrowing. Estimated all-in 20 basis points (0.20%) **per side** for fees and slippage. Keep idle money in cash.
- Benchmark: invest the same initial US$2,000 and monthly US$100 into VOO on the same executable dates, with the same per-side cost convention. Compare end wealth, deposit-adjusted/time-weighted returns, maximum drawdown, and matched-entry/exit VOO trade returns. Include dividend-adjusted prices where reliably available; disclose missing spreads, FX, taxes and adjusted-open limitations.
- Do not claim these exact rules reproduce Takashi Kotegawa's discretionary Japanese strategy.

## Independent validation: two distinct paths

**Path A — genuine forward paper trading (preferred without a paid point-in-time archive):**
1. On the **first eligible future completed US close after registration**, freeze and commit the exact 2026-era screening universe **before** reading any future session's opening price. Preserve ticker, exchange, first inclusion date, eligibility reason, and identifier. Future scanner ranking changes must NOT silently add or remove names. Track subsequent delistings, mergers, and ticker changes as outcomes, not delete the losers. Any later expanded universe is a separately registered cohort.
2. Append immutable close-date snapshots: universe version/hash, model version, close date, source and adjusted-price convention, each eligible signal, timestamp in UTC, estimated next open, paper positions, and explicit no-signal days. Preserve all snapshots, including those without candidates. On reruns, never rewrite an already recorded close.
3. When the next actual US session arrives, check the prior snapshot's UTC timestamp was **strictly before** that session's NYSE opening time. Only then record simulated next-open fills, costs, shares, deposits, stops and conditional exits. If the prior snapshot was late, data are missing, or a session was skipped, mark that interval INVALID and never reconstruct a profitable hypothetical trade later.
4. Journal every completed round trip and the matching VOO account; publish missing/invalid observations, coverage denominator, exact transaction-cost assumptions, realized paper P&L and drawdown. Never conflate a signal with an executed paper fill. Do not backfill prior to this registration.

**Path B — truly different historical universe (optional and strictly separate):** obtain a documented **point-in-time** US equity membership and corporate-actions/delisting dataset with historical constituents (including failures), then define a fresh untouched period or venue **before** examining its outcomes. Freeze membership rules and prices available on each date. Merely running the same present-day 88 stocks across 2019–2026, or changing thresholds until PLTR/FROG win, does NOT qualify. Because 2019–2026 was already inspected, reusing that history is descriptive only.

## Minimum evidence gates before even proposing a live pilot

- At least **six calendar months** of genuinely prospective, valid paper observations and **30 completed independent trades** across the frozen cohort. If fewer trades occur, continue tracking; do not waive the minimum.
- Positive net advantage against same-date, same-deposit VOO DCA after the 20-bps-per-side assumption; disclose both dollar wealth and time-weighted return, including idle cash. Positive mean trade-level matched-VOO excess and a descriptive confidence interval that excludes zero **after** allowing for dependence and multiple comparisons. Do not imply an interval alone proves a stable edge.
- Repeat at 30-bps and 50-bps per-side cost sensitivity; no hidden look-ahead, dropped losers, revised signals, missing bars or omitted overnight gaps; report losing periods and worst drawdown.
- Independently audit data source, universe point-in-time integrity, next-open timing, fills and corporate actions. Paper success is necessary but **not sufficient** for live approval; explicit human risk review is still required.
- Until every gate is satisfied, output `real_money_approved=false`, `no_live_approval=true`, and plain-English **NO TRADE**. Never publish entry/exit wording that implies a guaranteed profit.

## Implementation gap identified 2026-10-25

The BNF report currently computes retrospective `paper_candidates` from the most recent historical bar but **does not persist timestamped BNF decisions, BNF-specific next-session fills, conditional exits or a BNF-versus-VOO forward ledger**. Existing ETF `forward_shadow.py` cannot be presented as BNF evidence. Build this ledger and regression tests before counting the first valid BNF paper session. Preserve the above protocol unchanged; register any necessary implementation corrections explicitly.
