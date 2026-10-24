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
        if found:
            return found
    return {}

def instant_tag(facts, candidates):
    gaap = facts.get("facts", {}).get("us-gaap", {})
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
        if records:
            d, f, val, tag = max(records)
            return {"value_usd": val, "period_end": d.isoformat(),
                    "filed": f.isoformat(), "tag": tag}
    return None

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
    market_cap = finite(stock.get("market_cap_usd"))
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
        "free_cash_flow_margin_pct": pct_ratio(fcf, revenue),
        "market_cap_at_screen_usd": market_cap,
        "free_cash_flow_yield_pct": pct_ratio(fcf, market_cap),
        "cash_balance": instant_tag(facts, BALANCE_TAGS["cash"]),
        "long_term_debt_tag": instant_tag(facts, BALANCE_TAGS["long_term_debt"]),
        "primary_source": API.format(cik),
        "company_filings": f"https://www.sec.gov/edgar/browse/?CIK={cik}",
        "data_limitations": [
            "Annual 10-K figures may be several quarters old; balances can be from a newer 10-Q.",
            "Free cash flow = operating cash flow minus reported property/equipment purchases; it is not a forecast.",
            "Free-cash-flow yield compares last annual cash flow with a later stock-market value, not matched point-in-time data.",
            "SEC facts can reflect later amendments. Do not use these figures in historical backtests as if known then.",
            "Missing XBRL tags mean unknown, not zero. Long-term-debt tags may omit other liabilities.",
            "A company's cash flow, momentum and P/E alone do not establish fair value or future VOO outperformance."
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
