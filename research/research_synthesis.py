"""Source-bounded, self-contained 3–6-month asset assessment.

This is deterministic research from dated SEC facts and recorded quotes. It does
not treat headlines as verified events, invent forecast returns, or instruct
the reader to perform unfinished research. Unknown evidence stays unknown.
"""
from __future__ import annotations
import math


def number(value):
    try:
        x = float(value)
        return x if math.isfinite(x) else None
    except (TypeError, ValueError):
        return None


def pct(value):
    x = number(value)
    return f"{x:+.1f}%" if x is not None else "unavailable"


def change(now, before):
    a, b = number(now), number(before)
    return 100 * (a / b - 1) if a is not None and b is not None and b > 0 else None


def amount(value):
    x = number(value)
    if x is None:
        return "unavailable"
    if abs(x) >= 1e9:
        return f"{x/1e9:.2f} billion USD"
    if abs(x) >= 1e6:
        return f"{x/1e6:.1f} million USD"
    return f"{x:,.0f} USD"


def coverage(asset):
    m = asset.get("metrics") or {}
    filing = asset.get("filings") or {}
    if asset.get("kind") == "equity":
        rows = m.get("annual_history") or []
        recent = filing.get("priority_filings") or []
        passages = filing.get("read_passages") or []
        output = [
            f"Annual SEC financial periods available: {len(rows)}",
            "Recent official filings identified: " + (
                ", ".join(str(f.get("form")) + " (" + str(f.get("filed")) + ")" for f in recent)
                if recent else "none"
            ),
            f"Short filing excerpts retrieved: {len(passages)}; these are not comprehensive readings of all risk factors, guidance or management discussion",
            "Verified forward earnings consensus and dated catalyst: unavailable",
        ]
    else:
        output = [
            "Issuer description and dated adjusted ETF prices available",
            "Future macroeconomic expectations and current issuer tracking costs not fully verified",
        ]
    news = (asset.get("qualitative_context") or {}).get("headline_sample") or []
    output.append(f"Recent news-index headlines: {len(news)}; article text and investor-sentiment distribution NOT independently verified")
    return output


def filing_date(asset, form):
    for item in ((asset.get("filings") or {}).get("priority_filings") or []):
        if item.get("form") == form:
            return item.get("filed")
    return None


def equity(asset):
    ticker = asset["ticker"]
    m = asset.get("metrics") or {}
    hist = m.get("annual_history") or []
    latest = hist[0] if hist else {}
    prior = hist[1] if len(hist) > 1 else {}
    sales = number(m.get("revenue_growth_yoy_pct"))
    fcf_growth = change(latest.get("free_cash_flow_usd"), prior.get("free_cash_flow_usd"))
    fcf_yield = number(m.get("fcf_yield_pct"))
    implied = number(m.get("price_implied_fcf_growth_pct"))
    pe = number(m.get("forward_pe"))
    quote = asset.get("price_context") or {}
    matched = number(quote.get("relative_to_voo_year_pp"))
    record = [
        f"The last fiscal-year revenue changed {pct(sales)}; annual free cash flow changed "
        f"{pct(fcf_growth)} versus the previous SEC-observed year. These are historical outcomes, not forecasts. [S1]",
        f"Annual free cash flow: {amount(m.get('fcf_usd'))}; market capitalisation from the "
        f"screen: {amount(m.get('market_cap_usd'))}; historical FCF yield: {pct(fcf_yield)}. [S1][S2]",
        f"Screened forward price/earnings multiple: {f'{pe:.1f} times' if pe is not None else 'unavailable'}. "
        "The denominator is an unaudited forecast, not an independently checked earnings consensus. [S2]",
        f"Cash: {amount(m.get('cash_usd'))}; reported long-term-debt tag: {amount(m.get('debt_usd'))}. "
        "The debt tag excludes some obligations and must not be mistaken for full net debt. [S1]",
    ]
    if matched is not None:
        record.append(
            f"The stock's preceding one-year price return exceeded VOO by {matched:+.1f} percentage "
            f"points as of {quote.get('last_price_date', 'the recorded close')}. "
            "This historical period is not a 3–6-month forecast. [S2]"
        )
    if sales is not None and sales > 15 and fcf_growth is not None and fcf_growth < 5:
        mechanism = (
            f"Revenue at {ticker} has grown much faster than cash remaining after capital spending. "
            "New sales only create lasting shareholder value if they eventually generate cash; "
            "strong headlines about demand cannot establish that conversion."
        )
        counter = (
            "Revenue growth might continue without corresponding cash-flow improvement. "
            "In that case an expensive valuation could compress even if sales rise."
        )
    elif sales is not None and sales < 0:
        mechanism = (
            f"{ticker} is a potential earnings-recovery candidate, not an established growth "
            "winner: reported sales declined. A recovery could surprise investors, but "
            "the reported annual cash flow cannot prove when it will occur."
        )
        counter = (
            "A cyclical high in margins or cash flow could reverse before the market's "
            "expected recovery. Historical profitability may therefore overstate value."
        )
    else:
        mechanism = (
            f"{ticker} has reported business fundamentals, but an investable 3–6-month "
            "edge requires an earnings surprise beyond what investors currently expect. "
            "The retrieved evidence does not establish that surprise."
        )
        counter = (
            "Investors can already have priced in the reported business improvement; "
            "market returns depend on changes in expectations, not only growing revenue."
        )
    pricing = (
        f"The fixed-parameter reverse cash-flow exercise implies {implied:.1f}% annual "
        "free-cash-flow growth for five years, under 11% required return, 2% terminal "
        "growth and no net borrowing adjustment. This is a stress-test assumption, "
        "not a company-specific fair value or near-term target. [S1][S2]"
        if implied is not None else
        "Available source data do not establish an independently defensible current fair value."
    )
    last_q = filing_date(asset, "10-Q")
    catalyst = (
        "The next SEC quarterly earnings disclosure could change expectations; "
        + (f"the last identified 10-Q was filed {last_q}. " if last_q else "")
        + "An exact future earnings date and pre-release consensus are not verified."
    )
    return {
        "completed_evidence": record,
        "economic_mechanism": mechanism,
        "pricing_interpretation": pricing,
        "counterargument": counter,
        "catalyst": catalyst,
        "scenarios": [
            "Bull (conditional): the next filed results show better sustainable cash generation than the market anticipated, causing upward earnings revisions and possible outperformance versus VOO.",
            "Base (unverified): results roughly match expectations and the market does not re-rate the shares; the historical numbers alone provide no edge over VOO.",
            "Bear (conditional): cash conversion deteriorates or the earnings multiple falls; a concentrated stock can lose substantially more than VOO.",
        ],
        "voo_test": "To justify a switch, evidence must show a better prospective 3–6-month risk-adjusted payoff than VOO after fees; the present materials do not establish this.",
        "decision": "NO SWITCH FROM VOO: keep on research watchlist until an independently verified, priced catalyst and forward-earnings evidence exist.",
        "research_completeness": "PARTIAL — filed historical numbers quantified; future expectations and precise catalysts unverified",
        "source_audit": coverage(asset),
    }


def commodity(asset):
    m = asset.get("metrics") or {}
    rel = number(m.get("relative_6m_to_voo_pp"))
    measured = (
        f"Six-month adjusted ETF-price return relative to VOO: {rel:+.1f} percentage points. "
        if rel is not None else
        "A same-dates six-month ETF-price return comparison with VOO is unavailable. "
    )
    return {
        "completed_evidence": [
            f"Adjusted ETF-price return through {m.get('asof','unknown')}: three months "
            f"{pct(m.get('return_3m_pct'))}, six months {pct(m.get('return_6m_pct'))}. [S2]",
            measured + "Backward-looking price returns are not a future return forecast. [S2]",
        ],
        "economic_mechanism": "Commodity ETFs may react to real yields, the currency, underlying supply and demand, and ETF structure; these drivers cannot establish future price moves by themselves.",
        "pricing_interpretation": "A commodity has no corporate free cash flow to discount. Fund structure, tracking and costs matter; no forward price target has been established.",
        "counterargument": "The commodity's attractive narrative may be already priced in or reverse, causing losses while VOO performs better.",
        "catalyst": "Future monetary and physical supply/demand developments over three to six months; neither timing nor surprise magnitude is verified.",
        "scenarios": [
            "Bull (conditional): an unexpectedly favourable supply/demand shock moves prices above what was already expected.",
            "Base (unverified): anticipated conditions remain priced in; there is no established excess-return advantage.",
            "Bear (conditional): real yields, currencies or physical supply move adversely; the ETF underperforms VOO.",
        ],
        "voo_test": "A diversification rationale is not proof of positive return versus VOO over the same next six months.",
        "decision": "NO SWITCH FROM VOO for 3–6-month outperformance; diversification is a separate investment decision.",
        "research_completeness": "PARTIAL — fund prices quantified; future drivers and valuation not independently resolved",
        "source_audit": coverage(asset),
    }


def analyse(asset):
    return equity(asset) if asset.get("kind") == "equity" else commodity(asset)
