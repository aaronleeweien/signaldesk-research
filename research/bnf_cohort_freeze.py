"""Freeze the full current BNF screening cohort before a future market open.

This is registration ONLY. It neither simulates fills nor validates any rule.
Once committed, the cohort must never be overwritten by later daily screeners.
"""
from datetime import date, datetime, time, timezone
from hashlib import sha256
import json
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

REPORT = Path("research/kotegawa_reversion.json")
COHORT = Path("research/bnf_frozen_cohort_v1.json")
PUBLIC = Path("site/bnf_frozen_cohort_v1.json")
VERSION = "bnf_forward_cohort_v1_20261101"


def freeze(report, now, existing=None, minimum_size=80):
    """Return (registered cohort, newly_created); fail closed on invalid input."""
    if existing is not None:
        if existing.get("version") != VERSION:
            raise ValueError("Existing cohort has unexpected version; do not replace")
        return existing, False
    if now.tzinfo is None:
        raise ValueError("UTC-aware registration time required")
    if report.get("protocol") != "bnf_inspired_mean_reversion_v1_20261024":
        raise ValueError("BNF strategy version mismatch")
    if report.get("no_live_approval") is not True:
        raise ValueError("Research must explicitly forbid live trading")
    if report.get("paper_entry_executable") is not False:
        raise ValueError("Unjournaled screen cannot be executable")
    symbols = report.get("screened_tickers")
    if not isinstance(symbols, list) or len(symbols) < minimum_size:
        raise ValueError("Complete priced BNF cohort unavailable or partial")
    if report.get("errors"):
        raise ValueError("BNF price analysis reported errors; refuse partial cohort")
    if (len(set(symbols)) != len(symbols) or
            any(not isinstance(t, str) or not t or t == "VOO" for t in symbols)):
        raise ValueError("Duplicate, invalid or benchmark ticker in cohort")
    if len(symbols) != report.get("screened_prices_for_assets"):
        raise ValueError("Cohort count differs from published priced coverage")
    close = date.fromisoformat(report["market_date"])
    next_estimate = (pd.Timestamp(close) + pd.offsets.BDay(1)).date()
    next_open = datetime.combine(next_estimate, time(9, 30),
                                 tzinfo=ZoneInfo("America/New_York"))
    if now >= next_open:
        raise ValueError("Late cohort registration: next estimated open passed")
    if (next_open - now).total_seconds() > 7 * 86400:
        raise ValueError("Market data are too stale to freeze")
    tickers = sorted(symbols)
    digest = sha256(json.dumps(tickers, separators=(",", ":")).encode()).hexdigest()
    return {
        "version": VERSION,
        "strategy_protocol": report["protocol"],
        "cohort_sha256": digest,
        "frozen_tickers": tickers,
        "ticker_count": len(tickers),
        "source_close": str(close),
        "first_countable_signal_close": "strictly after source_close; requires separate immutable pre-open journal",
        "same_close_signals_counted": False,
        "recorded_utc": now.astimezone(timezone.utc).isoformat(),
        "next_estimated_open": next_open.isoformat(),
        "selection": "2026 contemporary liquid US screener; survivor/selection bias remains",
        "provenance": "research/kotegawa_reversion.json, complete screened_tickers field",
        "delisted_tickers_must_remain": True,
        "cohort_may_not_rotate": True,
        "bnf_forward_fills": 0,
        "valid_forward_sessions": 0,
        "real_money_approved": False,
        "paper_execution_enabled": False,
        "blocker": "No durable pre-open per-close BNF journal or next-open paper fill/exit/VOO ledger; cohort freeze alone proves nothing."
    }, True


def main():
    now = datetime.now(timezone.utc)
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    old = json.loads(COHORT.read_text(encoding="utf-8")) if COHORT.exists() else None
    registered, created = freeze(report, now, old)
    if created:
        COHORT.write_text(json.dumps(registered, indent=2) + "\n", encoding="utf-8")
    PUBLIC.parent.mkdir(exist_ok=True, parents=True)
    PUBLIC.write_text(json.dumps(registered, indent=2) + "\n", encoding="utf-8")
    print("BNF COHORT:", "frozen" if created else "unchanged",
          registered["ticker_count"], "tickers; NO paper fills or live approval")


if __name__ == "__main__":
    main()
