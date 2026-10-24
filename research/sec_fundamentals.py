"""Independent, primary-source US-company fundamentals for SignalDesk.

This research layer verifies a small number of existing screener candidates using
SEC EDGAR XBRL company facts. It neither forecasts share prices nor approves trades.

No secrets or email addresses are written into public report data. The SEC asks
automated clients to identify themselves with a contact address. Supply
SIGNALDESK_SEC_USER_AGENT (secret) or SIGNALDESK_MAIL_TO (secret) at runtime.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen
import json
import math
import os
import time

SOURCE = "https://www.sec.gov/files/company_tickers.json"
API = "https://data.sec.gov/api/xbrl/companyfacts/CIK{:010d}.json"
REVENUE_TAGS = ("RevenueFromContractWithCustomerExcludingAssessedTax",
                "Revenues", "SalesRevenueNet", "RevenueFromContractWithCustomerIncludingAssessedTax")
TAGS = {
    "net_income": ("NetIncomeLoss", "ProfitLoss"),
    "operating_cash": ("NetCashProvidedByUsedInOperatingActivities",),
    "capital_spending": ("PaymentsToAcquirePropertyPlantAndEquipment",),
}
BALANCE_TAGS = {
    "cash": ("CashAndCashEquivalentsAtCarryingValue",),
    "long_term_debt": ("LongTermDebt", "LongTermDebtNoncurrent"),
}

def finite(value):
    try:
        x = float(value)
        return x if math.isfinite(x) else None
    except (ValueError, TypeError):
        return None

def pct_ratio(numerator, denominator):
    a, b = finite(numerator), finite(denominator)
    return round(a / b * 100, 2) if a is not None and b is not None and b > 0 else None

def select_candidates(rows, limit=4):
    """Mix top momentum ideas with the lowest positive forward P/E; NOT picks to buy."""
    valid = [row for row in rows if row.get("ticker") and
             row.get("status") == "RESEARCH CANDIDATE"]
    selected = []
    for row in valid[:2] + sorted(valid, key=lambda x: (
            x.get("forward_pe") is None or finite(x.get("forward_pe")) is None or
            finite(x.get("forward_pe")) <= 0,
            finite(x.get("forward_pe")) if finite(x.get("forward_pe")) is not None else float("inf"))):
        ticker = row["ticker"].upper().strip()
        if ticker not in {x["ticker"] for x in selected}:
            selected.append(row)
        if len(selected) >= limit:
            break
    return selected

def annual_tag(facts, candidates):
    gaap = facts.get("facts", {}).get("us-gaap", {})
    best = {}
    for tag in candidates:
        values = gaap.get(tag, {}).get("units", {}).get("USD", [])
        found = {}
        for item in values:
            if item.get("form") not in ("10-K", "10-K/A") or not item.get("start"):
                continue
            try:
                start = date.fromisoformat(item["start"])
                end = date.fromisoformat(item["end"])
                filed = date.fromisoformat(item["filed"])
            except (KeyError, ValueError, TypeError):
                continue
            if not 330 <= (end - start).days <= 390 or filed > date.today():
                continue
            val = finite(item.get("val"))
            if val is None:
                continue
            existing = found.get(end.isoformat())
            if existing is None or filed.isoformat() > existing["filed"]:
                found[end.isoformat()] = {
                    "value_usd": val, "filed": filed.isoformat(),
                    "fiscal_end": end.isoformat(), "tag": tag,
                    "form": item["form"], "accession": item.get("accn")}
        # Prefer the revenue/XBRL tag whose latest annual period is newest.
        # A legacy tag can be valid but end years before a newer taxonomy tag.
        if found and (not best or max(found) > max(best)):
            best = found
    return best

def instant_tag(facts, candidates):
    gaap = facts.get("facts", {}).get("us-gaap", {})
    all_records = []
    for tag in candidates:
        records = []
        for item in gaap.get(tag, {}).get("units", {}).get("USD", []):
            if item.get("form") not in ("10-K", "10-K/A", "10-Q", "10-Q/A") or item.get("start"):
                continue
            try:
                d = date.fromisoformat(item["end"])
                f = date.fromisoformat(item["filed"])
            except (ValueError, KeyError, TypeError):
                continue
            val = finite(item.get("val"))
            if val is not None and f <= date.today():
                records.append((d, f, val, tag))
        all_records.extend(records)
    if all_records:
        d, f, val, tag = max(all_records)
        return {"value_usd": val, "period_end": d.isoformat(),
                "filed": f.isoformat(), "tag": tag}
    return None

def fcf_present_value(starting_fcf, annual_growth, required_return=.11,
                      terminal_growth=.02, years=5):
    """Illustrative equity FCF perpetuity model, not an independent fair value.

    Assumes all CFO minus capex is distributable to shareholders, constant
    growth for five years and no net borrowing. These assumptions commonly
    fail for cyclical, leveraged and rapidly growing businesses.
    """
    value = finite(starting_fcf)
    if value is None or value <= 0 or required_return <= terminal_growth:
        return None
    annual = value
    pv = 0.0
    for year in range(1, years + 1):
        annual *= (1 + annual_growth)
        pv += annual / ((1 + required_return) ** year)
    terminal = annual * (1 + terminal_growth) / (required_return - terminal_growth)
    return pv + terminal / ((1 + required_return) ** years)

def reverse_fcf_growth(starting_fcf, market_cap):
    """What five-year annual growth would mathematically reconcile price/FCF?"""
    cap = finite(market_cap)
    if cap is None or cap <= 0 or finite(starting_fcf) is None or starting_fcf <= 0:
        return None
    lo, hi = -.75, 1.5
    lower = fcf_present_value(starting_fcf, lo)
    upper = fcf_present_value(starting_fcf, hi)
    if lower is None or upper is None or not lower <= cap <= upper:
        return None
    for _ in range(65):
        mid = (lo + hi) / 2
        if fcf_present_value(starting_fcf, mid) < cap:
            lo = mid
        else:
            hi = mid
    return round((lo + hi) * 50, 2)

def inspect_company(stock, cik, facts):
    """Return tagged facts, ratios and provenance, never a fair-value claim."""
    rev = annual_tag(facts, REVENUE_TAGS)
    inc = annual_tag(facts, TAGS["net_income"])
    cashflow = annual_tag(facts, TAGS["operating_cash"])
    capex = annual_tag(facts, TAGS["capital_spending"])
    ends = sorted(rev, reverse=True)
    latest = ends[0] if ends else None
    previous = rev.get(ends[1]) if len(ends) > 1 else None
    cur = rev.get(latest) if latest else None
    op = cashflow.get(latest)
    spending = capex.get(latest)
    net = inc.get(latest)
    revenue = cur["value_usd"] if cur else None
    fcf = (op["value_usd"] - spending["value_usd"]) if op and spending else None
    cash_history = []
    for end in ends[:3]:
        flow, investment = cashflow.get(end), capex.get(end)
        year_fcf = (flow["value_usd"] - investment["value_usd"]) if flow and investment else None
        cash_history.append({"fiscal_year_ended": end,
                             "revenue_usd": rev[end]["value_usd"],
                             "free_cash_flow_usd": year_fcf})
    available_fcf = [x["free_cash_flow_usd"] for x in cash_history if x["free_cash_flow_usd"] is not None]
    market_cap = finite(stock.get("market_cap_usd"))
    implied = reverse_fcf_growth(fcf, market_cap)
    scenario_values = {}
    if fcf is not None and fcf > 0 and market_cap is not None and market_cap > 0:
        for label, growth in (("no_growth", 0.), ("moderate_growth", .05), ("fast_growth", .10)):
            v = fcf_present_value(fcf, growth)
            scenario_values[label] = {
                "annual_fcf_growth_assumed_pct": round(growth * 100, 2),
                "illustrative_equity_value_usd": round(v, 2),
                "value_as_pct_of_current_market_cap": pct_ratio(v, market_cap)}
    return {
        "ticker": stock["ticker"],
        "company_sec_name": facts.get("entityName"),
        "company_screen_name": stock.get("name"),
        "cik": cik,
        "status": "independent_annual_fundamentals_verified" if cur and op and spending else "partial_filing_data",
        "fiscal_year_ended": latest,
        "filing_dates": {k: v["filed"] for k, v in
                         (("revenue", cur), ("operating_cash", op),
                          ("capital_spending", spending), ("net_income", net)) if v},
        "revenue_usd": revenue,
        "revenue_growth_yoy_pct": pct_ratio(revenue - previous["value_usd"], previous["value_usd"]) if cur and previous else None,
        "net_income_usd": net["value_usd"] if net else None,
        "operating_cash_usd": op["value_usd"] if op else None,
        "capital_spending_usd": spending["value_usd"] if spending else None,
        "free_cash_flow_usd": fcf,
        "annual_history_latest_three": cash_history,
        "positive_fcf_years": sum(x > 0 for x in available_fcf),
        "fcf_years_available": len(available_fcf),
        "cash_conversion_operating_to_net_income": round(op["value_usd"]/net["value_usd"],2) if op and net and net["value_usd"] > 0 else None,
        "free_cash_flow_margin_pct": pct_ratio(fcf, revenue),
        "market_cap_at_screen_usd": market_cap,
        "free_cash_flow_yield_pct": pct_ratio(fcf, market_cap),
        "reverse_cash_flow_valuation": {
            "illustrative_only": True,
            "required_return_assumed_pct": 11,
            "terminal_perpetual_growth_assumed_pct": 2,
            "years_of_projected_cash_flow": 5,
            "implied_growth_needed_by_stock_price_pct": implied,
            "fixed_assumption_scenarios": scenario_values,
            "methodology": "Discount annual equity-like operating cash flow minus capital spending with no net new borrowing. Simplified fixed assumptions are NOT forecasts, calibrated costs of capital or defensible price targets."
        },
        "cash_balance": instant_tag(facts, BALANCE_TAGS["cash"]),
        "long_term_debt_tag": instant_tag(facts, BALANCE_TAGS["long_term_debt"]),
        "primary_source": API.format(cik),
        "company_filings": f"https://www.sec.gov/edgar/browse/?CIK={cik}",
        "data_limitations": [
            "Annual 10-K figures may be several quarters old; balances can be from a newer 10-Q.",
            "Free cash flow = operating cash flow minus reported property/equipment purchases; it is not a forecast.",
            "Three-year history is provided only when revenue and matching fiscal-year cash-flow tags exist.",
            "Operating-cash/net-income conversion can be distorted by one-off working-capital and noncash items.",
            "Free-cash-flow yield compares last annual cash flow with a later stock-market value, not matched point-in-time data.",
            "SEC facts can reflect later amendments. Do not use these figures in historical backtests as if known then.",
            "Missing XBRL tags mean unknown, not zero. Long-term-debt tags may omit other liabilities.",
            "A company's cash flow, momentum and P/E alone do not establish fair value or future VOO outperformance.",
            "Reverse cash-flow valuation assumes all CFO less capex is distributable to shareholders, fixed 11% required return, 2% terminal growth, and no net borrowing; the implied growth is NOT a company forecast."
        ]
    }

def download(url, agent):
    req = Request(url, headers={"User-Agent": agent, "Accept": "application/json"})
    with urlopen(req, timeout=25) as response:
        return json.loads(response.read())

def run(base=Path("research"), site=Path("site"), downloader=download):
    base.mkdir(parents=True, exist_ok=True)
    site.mkdir(parents=True, exist_ok=True)
    market = json.loads((base / "market_discovery.json").read_text(encoding="utf-8"))
    candidates = select_candidates(market.get("stock_investing_watchlist", []))
    user_agent = (os.environ.get("SIGNALDESK_SEC_USER_AGENT") or
                  ("SignalDesk Research " + os.environ.get("SIGNALDESK_MAIL_TO", ""))).strip()
    has_contact = bool(os.environ.get("SIGNALDESK_SEC_USER_AGENT") or
                       os.environ.get("SIGNALDESK_MAIL_TO"))
    report = {
        "version": "sec_primary_source_v1",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "source_market_date": market.get("last_completed_us_price_date"),
        "research_only": True,
        "source_catalogue": SOURCE,
        "selected_screened_tickers": [r["ticker"] for r in candidates],
        "companies": [],
        "errors": [],
        "status": "not_configured" if not has_contact else "research_incomplete",
        "selection_limitations": "A handful of PRESENT-DAY shortlisted US tickers, not all publicly traded companies. Survivorship and selection bias remain."
    }
    if has_contact and candidates:
        try:
            entries = downloader(SOURCE, user_agent)
            mapping = {r["ticker"].upper(): int(r["cik_str"]) for r in entries.values()}
            for stock in candidates:
                symbol = stock["ticker"].upper()
                if symbol not in mapping:
                    report["errors"].append(f"{symbol}: SEC ticker/CIK mapping unavailable")
                    continue
                try:
                    data = downloader(API.format(mapping[symbol]), user_agent)
                    report["companies"].append(inspect_company(stock, mapping[symbol], data))
                except Exception as exc:
                    report["errors"].append(f"{symbol}: SEC facts unavailable ({type(exc).__name__})")
                time.sleep(.24)
            report["status"] = ("filings_retrieved" if report["companies"]
                                else "sec_data_unavailable")
        except Exception as exc:
            report["errors"].append(f"SEC catalogue unavailable ({type(exc).__name__})")
            report["status"] = "sec_data_unavailable"
    (base / "sec_fundamentals.json").write_text(
        json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    (site / "sec_fundamentals.json").write_text(
        json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print("SEC filing check:", report["status"], "companies:", len(report["companies"]))
    return report

if __name__ == "__main__":
    run()
