"""Daily SignalDesk EDITORIAL report.

Presentation layer ONLY. All metrics and live-trading gates are read directly
from already produced independent research JSON files. Do not compute investment
signals, modify strategy definitions, manufacture forward returns or call quotes.

Write for a first-time investor: conclusion, connected cause/effect explanation,
evidence, exactly what is missing, and one next action. Keep jargon WITH a
short plain-English definition. The full quantitative sources stay linked.
"""
from __future__ import annotations

from datetime import datetime,timezone
from html import escape as H
from pathlib import Path
import json
import math

REQUIRED=("decision_hub.json","market_discovery.json","established_strategies.json")
OPTIONAL=("kotegawa_reversion.json",)

def get(name,base=Path("research")):
    f=base/name
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else None

def pct(value,sign=False):
    try:
        v=float(value)
        if not math.isfinite(v):raise ValueError()
        return ("+" if sign and v>0 else "")+f"{v:.2f}%"
    except (ValueError,TypeError):
        return "not available"

def pp(value,sign=False):
    try:
        v=float(value)
        if not math.isfinite(v):raise ValueError()
        return ("+" if sign and v>0 else "")+f"{v:.2f} percentage points"
    except (ValueError,TypeError):
        return "not available"

def fact_line(text):
    return f'<p class="fact">{H(text)}</p>'

def narrative_bundle(hub,market,est,rev=None,fundamentals=None):
    date=hub["market_last_completed_close"]
    complete_dates=(market.get("last_completed_us_price_date")==date and
                    est.get("latest_completed_us_market_day")==date)
    if not complete_dates:
        # Fail closed: never mix historical strategy data from different sessions
        # while claiming to report today's comparative return numbers.
        return {"date":date,"fresh":False,
            "headline":"No new investment recommendation: the sources are on different dates.",
            "long_intro":"The fund and stock files do not describe the same market day. Comparing their figures could mislead us.",
            "long_stories":[],"stock_story":None,"trade_intro":"No fresh trading instruction. Do not rely on mismatched data.",
            "trade_story":None,"reversion_story":None,
            "limits":["Research files contain different market dates.",
                "No real-time price, fair-value target or approved brokerage trade is supplied."],
            "coverage":{},"fundamental_stories":[]}

    etfs={x["ticker"]:x for x in hub.get("investment_ideas",[])}
    voo=est["windows"]["recent_2022"]["returns"]["VOO"]["annual_twr_pct"]
    long_stories=[]
    for ticker in ("QQQ","SPMO","SMH"):
        x=etfs.get(ticker)
        if not x:continue
        perf=pct(x.get("annual_return_recent_pct"))
        dd=pct(x.get("max_drawdown_recent_pct"))
        excess=pp(x.get("relative_2022_pp"),sign=True)
        if ticker=="QQQ":
            action="KEEP ON THE LONG-TERM WATCHLIST. Do not replace VOO yet."
            why="QQQ owns many large Nasdaq-listed companies. Some grew much faster than the wider S&P 500 → QQQ earned more over the period we tested. But heavy exposure to growth companies also means it can fall hard if their prices drop."
            missing="We have actual past fund returns, but not a reliable forecast of the return at today's price."
        elif ticker=="SPMO":
            action="RESEARCH AS A POSSIBLE LONG-TERM ADDITION; no immediate switch."
            why="SPMO holds S&P 500 stocks whose prices had stronger momentum (recent price strength). Those stocks kept performing well in some past periods → the fund beat VOO. The current trend check is weak, so the record alone does not settle whether to buy now."
            missing="We have no defensible future expected return or fair-value estimate for this fund."
        else:
            action="ONLY IF YOU ACCEPT A MUCH BIGGER LOSS RISK. Not my first choice."
            why="SMH concentrates in semiconductor companies. That industry grew unusually fast → SMH beat VOO by a lot. Concentration works both ways → one bad period for chip stocks can hurt more than a broad fund."
            missing="The return came with higher sector concentration; it does not prove that this extra risk is worth taking from here."
        long_stories.append({
            "ticker":ticker,"action":action,"why":why,
            "evidence":f"Since January 2022, annualised total return (average compounded yearly growth) was {perf}, against VOO at {pct(voo)}. That is {excess} per year; the fund's largest peak-to-trough drop (drawdown) was {dd}.",
            "missing":missing,
            "trend":x.get("status",""),
            "source":"established.html"})

    stocks=market.get("stock_investing_watchlist",[])
    stock=next((x for x in stocks if x.get("status")=="RESEARCH CANDIDATE" and
                    x.get("forward_pe") is not None and x.get("earnings_growth_pct") is not None),None)
    stock_story=None
    if stock:
        symbol=stock["ticker"]
        growth_origin=stock.get("earnings_growth_source","unknown")
        stock_story={
            "ticker":symbol,"name":stock.get("name",symbol),
            "recommendation":"RESEARCH FURTHER; do not buy based on this screen alone.",
            "why":f"{symbol}'s price rose faster than VOO over the last year → our screen noticed it. We then looked at its forward P/E (price divided by forecast earnings) to ask whether the price might be expensive. But P/E alone cannot tell us what the company is worth.",
            "evidence":f"Past one-year advantage over VOO: {pp(stock.get('relative_to_voo_year_pp'),True)}. Forward P/E: {stock['forward_pe']:.1f}. Displayed EPS growth: {pct(stock.get('earnings_growth_pct'))}.",
            "missing":"Important: the growth number was calculated from trailing and forward P/E ratios, NOT obtained from an independent company profit forecast." if "implied" in growth_origin else "Profit forecasts may be wrong; future return was not estimated.",
            "status":stock.get("status")}

    new=[x for x in hub.get("trading_opportunities",[]) if x.get("new_entry_setup")]
    gates=[x for x in new if x.get("historical_evidence",{}).get("passes_historical_gate")]
    trade_story=None
    if new:
        x=new[0]
        ticker=x["ticker"]
        e=x["historical_evidence"]
        trade_story={
            "ticker":ticker,
            "recommendation":"PAPER-TEST ONLY. I would not place a real trade.",
            "why":f"{ticker} moved above its recent high → our breakout rule noticed it → the model would buy at the next US open and sell when a stop or trend rule triggers. But spotting a big price move is not proof we can earn more than holding VOO.",
            "evidence":f"The old trades made {pp(e.get('avg_vs_voo_pct'),True)} more per trade, on average, than VOO bought and sold on the same dates; the required historical evidence check {'passed' if e.get('passes_historical_gate') else 'failed'}.",
            "exit":"The paper entry is the next US regular open, not a known purchase price. Exit at the next open after the 7% closing stop, 10-day low, 200-day average, or after 15 sessions. The sell date can change.",
            "source":"decisions.html#trade"}

    reversion_story=None
    if rev and rev.get("market_date")==date:
        names=[x["ticker"] for x in rev.get("historical_screen_summary",[]) if x.get("historical_only_pass")]
        reversion_story={
            "recommendation":"NOT A REAL TRADE. Keep it as a separate research idea.",
            "why":"A falling stock can sometimes bounce back. The strategy buys after an unusually large fall → sells when the price recovers or a preset exit triggers → compares the entire account with regular VOO investing. Some companies passed the past test, but that test chose from today's surviving stocks.",
            "evidence":f"It checked {rev['screened_prices_for_assets']} stocks; {rev['passing_retrospective_tests']} passed the early historical filter ({', '.join(names) if names else 'none'}). It found {rev['new_paper_entry_setups']} new paper entries.",
            "missing":"Because we know which stocks survived until today, the old results may be biased. This is not Kotegawa's exact trading method."}

    # Filed numbers are independent of the market screener. These are audited
    # annual FINANCIAL FACTS, not analyst forecasts or proof of undervaluation.
    fundamental_stories=[]
    if fundamentals and fundamentals.get("source_market_date")==date:
        for item in fundamentals.get("companies",[]):
            sym=item["ticker"]
            year=item.get("fiscal_year_ended") or "unknown period"
            def dollars(v):
                return "not available" if v is None else f"USD {v/1e9:,.2f} billion"
            evidence=(f"SEC 10-K year ended {year}: revenue {dollars(item.get('revenue_usd'))}; "
                f"year-on-year revenue growth {pct(item.get('revenue_growth_yoy_pct'))}; "
                f"net income {dollars(item.get('net_income_usd'))}; "
                f"operating cash flow {dollars(item.get('operating_cash_usd'))}; "
                f"capital spending {dollars(item.get('capital_spending_usd'))}; "
                f"free cash flow {dollars(item.get('free_cash_flow_usd'))}; "
                f"free-cash-flow yield {pct(item.get('free_cash_flow_yield_pct'))}.")
            history=item.get("annual_history_latest_three",[])
            if history:
                history_sentence="; ".join(
                    f"{h['fiscal_year_ended']}: {dollars(h.get('free_cash_flow_usd'))}"
                    for h in history)
                evidence+=f" Annual free cash flow in the latest available filing years: {history_sentence}."
            if item.get("fcf_years_available"):
                evidence+=(f" Positive free cash flow in {item['positive_fcf_years']} of "
                    f"{item['fcf_years_available']} available years; a single positive year is not proof of stability.")
            cash=item.get("cash_balance")
            debt=item.get("long_term_debt_tag")
            if cash:
                evidence+=(f" Reported cash balance {dollars(cash.get('value_usd'))} "
                           f"(balance-sheet date {cash['period_end']}).")
            if debt:
                evidence+=(f" Reported long-term-debt tag {dollars(debt.get('value_usd'))} "
                           f"(balance-sheet date {debt['period_end']}); this may NOT include every liability.")
            model=item.get("reverse_cash_flow_valuation",{})
            implied=model.get("implied_growth_needed_by_stock_price_pct")
            if implied is not None:
                evidence+=(
                    f" Reverse-valuation arithmetic: today's stock-market value would require about "
                    f"{pct(implied)} annual free-cash-flow growth for five years under the FIXED "
                    f"11% investor-required return and 2% perpetual terminal growth assumptions.")
                scenarios=model.get("fixed_assumption_scenarios",{})
                if scenarios:
                    scenario_summary="; ".join(
                        f"{label.replace('_',' ')}: {pct(z.get('value_as_pct_of_current_market_cap'))} of market cap"
                        for label,z in scenarios.items())
                    evidence+=f" Sensitivity if FCF growth instead stays at 0%, 5%, or 10%: {scenario_summary}."
            note=("FCF (free cash flow) means cash generated from operations minus money spent on property and equipment. "
                "Positive FCF can help a company invest, repay debt or return cash to shareholders. "
                "FCF yield compares that historical cash with today's market value: a higher number can be attractive "
                "but could also mean that cash flow is expected to decline. "
                "Revenue growth tells us whether sales expanded, not whether investors will earn a profit.")
            missing=("We still need current-quarter context, business quality, competitors, detailed debt analysis, "
                "forward earnings and a properly justified valuation scenario before claiming this may beat VOO. "
                "Annual reports lag today's market price; the SEC facts may include amendments. "
                "The reverse-valuation calculation is a sensitivity exercise, NOT a verified fair value or "
                "a company forecast: real growth, discount rates, cash use and borrowing could differ substantially.")
            fundamental_stories.append({
                "ticker":sym,"recommendation":"PRIMARY-SOURCE FINANCIAL CHECK ONLY; not a buy recommendation.",
                "why":note,"evidence":evidence,"missing":missing,
                "source":item.get("primary_source",""),
                "filing_dates":item.get("filing_dates",{}),
                "complete":item.get("status")=="independent_annual_fundamentals_verified"})

    coverage={
        "listing_count":market["universe_catalog"]["US_listings_catalogued"],
        "screen_count":market["discovery_feeds"]["unique_stock_quotes"],
        "priced":market["stocks_with_price_and_momentum_results"],
        "valued":market["stocks_with_price_growth_and_valuation_data"]}

    # A rank of 'candidate' is a research-status label only, never a
    # buy decision. The report always keeps investment and trade gates apart.
    return {"date":date,"fresh":True,
        "headline":"My recommendation: keep investing in VOO. Do not open a new real-money trade.",
        "long_intro":"VOO is already a simple way to own many large US companies. A different asset must give us a good reason to expect better future returns, not just show that it made more money before.",
        "long_stories":long_stories,"stock_story":stock_story,
        "trade_intro":f"{len(new)} new technical breakouts appeared in our limited ETF/stock scanner. {len(gates)} of those passed our historical evidence check. No real-money trades are approved.",
        "trade_story":trade_story,"reversion_story":reversion_story,
        "limits":[
            f"The US exchange catalog had {coverage['listing_count']:,} listings, but only {coverage['screen_count']:,} stocks were in the screener output, {coverage['priced']} had historical prices checked, and {coverage['valued']} had basic valuation and growth fields. This is NOT every asset in the market.",
            "Our stock-level valuation is a basic filter, not a Wall Street-quality fair-value model. No independent forecasts, earnings calls, detailed balance-sheet work, management evaluation or scenario-based price targets are in the report.",
            "Backtests use historical prices and a modern selected stock universe. Results may look good because we know which stocks survived or because we tested multiple ideas.",
            "The report uses completed US market prices, not live quotes. It cannot know tomorrow's profitable sell date."],
        "coverage":coverage,"fundamental_stories":fundamental_stories}

def render_article(info):
    date=H(info["date"])
    def sec(story,title):
        why=H(story["why"])
        evidence=H(story["evidence"])
        missing=H(story.get("missing",""))
        action=H(story.get("action",story.get("recommendation","")))
        return f'''<section class="idea">
<h3>{H(title)}</h3><p class="answer"><strong>What I would do:</strong> {action}</p>
<p>{why}</p><p class="fact"><strong>Evidence:</strong> {evidence}</p>
{f'<p class="gap"><strong>What is missing:</strong> {missing}</p>' if missing else ''}
</section>'''

    stories=info["long_stories"]
    long_html="".join(sec(x,f"{x['ticker']}: worth buying instead of VOO?") for x in stories)
    if info["stock_story"]:
        long_html+=sec(info["stock_story"],f"Stock example: {info['stock_story']['ticker']}")
    else:
        long_html+='<p>No stock has a complete enough basic valuation screen to include in the article today.</p>'
    filings=info.get("fundamental_stories",[])
    filings_html="".join(
        sec(s,f"SEC filing check: {s['ticker']}")+
        (f'<p class="meta"><a href="{H(s["source"])}" rel="noopener noreferrer">Read SEC primary-source figures</a>'
         f' · Filing dates: {H(", ".join(sorted(set(s["filing_dates"].values()))))}</p>' if s.get("source") else "")
        for s in filings)
    if not filings_html:
        filings_html="<p>Independent SEC filing checks are not available for this market session. "
        filings_html+="We cannot treat screener P/E or price momentum as independently verified company analysis.</p>"
    trade=info["trade_story"]
    trading_html=sec(trade,f"Example: {trade['ticker']} breakout") if trade else "<p>There is no new breakout signal to investigate today.</p>"
    if trade:
        trading_html+=f'<p class="gap"><strong>When to sell?</strong> {H(trade["exit"])}</p>'
    reversion=info["reversion_story"]
    reversion_html=(sec(reversion,"Buying after a sharp fall: a Kotegawa-inspired study") if reversion else "")
    caveats="".join(f"<li>{H(x)}</li>" for x in info["limits"])
    status="All sources matched the same market date." if info["fresh"] else "Different source dates: no fresh decision."
    body=f'''<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="description" content="SignalDesk Daily Investment Report — plain-English findings from transparent quantitative stock and ETF research">
<title>SignalDesk — Daily Investment Report</title>
<style>
:root{{color-scheme:light;font-family:Georgia,"Times New Roman",serif;color:#17283a;background:#f7f9fb}}
*{{box-sizing:border-box}}
body{{margin:0;font-size:17px;line-height:1.65}}
main{{max-width:790px;padding:32px 24px 75px;margin:auto}}
h1,h2,h3,.meta,.answer,.gap,.fact,.nav,.foot,.overline,.button-link{{font-family:system-ui,-apple-system,Segoe UI,Arial,sans-serif}}
h1{{font-size:clamp(31px,5vw,48px);line-height:1.16;letter-spacing:-.035em;margin:10px 0 15px}}
h2{{font-size:25px;letter-spacing:-.02em;line-height:1.25;margin-top:24px}}
h3{{font-size:20px;line-height:1.35;margin:24px 0 12px}}
p{{margin:10px 0 16px}}.overline{{color:#326078;letter-spacing:.16em;font-weight:800;font-size:11px}}
.meta{{font-size:13px;color:#647487}}
.lead{{font-size:20px;line-height:1.55;color:#2d4154}}
.answer{{font-size:17px;border-left:3px solid #1f716a;padding:12px 16px;background:#eaf4f1;line-height:1.5}}
.fact{{font-size:14px;line-height:1.7;padding:11px 14px;background:#edf2f7;border-radius:8px}}
.gap{{font-size:14px;line-height:1.65;color:#5e4242}}
.chapter{{border-top:1px solid #cfdae2;margin-top:30px;padding-top:9px}}
.idea{{padding:0 0 10px;border-bottom:1px solid #e0e7ee}}
.idea:last-child{{border-bottom:0}}
.nav{{font-size:13px;display:flex;gap:13px;flex-wrap:wrap;margin:22px 0}}
a{{color:#145c79;text-underline-offset:3px}}
details{{border:1px solid #cbd9e1;background:#fff;padding:14px 18px;border-radius:10px;margin-top:15px;font:14px/1.6 system-ui,-apple-system,Arial,sans-serif}}
summary{{cursor:pointer;font-weight:700}}li{{margin:9px 0}}
.foot{{margin-top:30px;font-size:13px;color:#607080;border-top:1px solid #cbd9e1;padding-top:15px}}
@media(max-width:600px){{main{{padding:20px 16px 44px}}body{{font-size:16px}}.lead{{font-size:18px}}}}
@media print{{body{{background:#fff}}main{{max-width:unset}}details{{display:block}}}}
</style></head><body><main>
<div class="overline">SIGNALDESK · INVESTMENT RESEARCH NOTE</div>
<h1>What is worth buying? Is there a trade today?</h1>
<p class="meta">Based on the completed US market session: <strong>{date}</strong> · {H(status)}</p>
<p class="answer"><strong>{H(info["headline"])}</strong></p>
<p class="lead">{H(info["long_intro"])}</p>
<div class="nav"><a href="#long">Longer-term investing</a><a href="#filings">SEC filing checks</a><a href="#short">Short-term opportunities</a><a href="#proof">Check the full evidence</a><a href="decisions.html">Original dashboard</a></div>
<section class="chapter" id="long"><h2>1. Could something beat VOO over the next few years?</h2>
{long_html}</section>
<section class="chapter" id="filings"><h2>2. What do the companies actually earn and produce in cash?</h2>
<p>These numbers come from SEC annual filings, not a share-price chart. Every missing field stays explicitly unknown. Financial strength is not the same as a bargain stock.</p>
{filings_html}</section>
<section class="chapter" id="short"><h2>3. Is there a short-term trade worth taking?</h2>
<p>{H(info["trade_intro"])}</p>{trading_html}{reversion_html}
<p class="answer"><strong>My recommendation:</strong> No new real-money trade. Continue VOO DCA (dollar-cost averaging: investing a set amount regularly) while these strategies are tested.</p>
</section>
<section class="chapter" id="proof"><h2>4. What we still cannot prove</h2>
<p>Wall Street-grade research would check more than past prices. It would estimate a company's future cash, debts, profits, risks and a realistic range of future prices. We have not completed that work.</p>
<details><summary>Open the data checks and limits</summary><ul>{caveats}</ul>
<p><a href="market.html">Market discovery data</a> · <a href="established.html">ETF comparison</a> · <a href="validation.html">Backtest audit</a> · <a href="kotegawa.html">Rebound strategy test</a> · <a href="decision_hub.json">Daily calculation data</a></p>
</details></section>
<div class="foot">Research, not a live trading instruction. No promise of beating VOO. Figures use available historical data and can change. The report is written automatically from SignalDesk research results.</div>
</main></body></html>'''
    return body

def render_markdown(info):
    lines=["# SignalDesk — Daily Investment Report",
        f"Market close: {info['date']}",
        "","**"+info["headline"]+"**","",info["long_intro"],"",
        "## Could something beat VOO over the next few years?"]
    for x in info["long_stories"]:
        lines+=["",f"### {x['ticker']}",f"**What I would do:** {x['action']}",x["why"],
                "**Evidence:** "+x["evidence"],"**Still missing:** "+x["missing"]]
    x=info["stock_story"]
    if x:lines+=["",f"### Stock example: {x['ticker']}",
         f"**What I would do:** {x['recommendation']}",x["why"],
         "**Evidence:** "+x["evidence"],"**Still missing:** "+x["missing"]]
    lines+=["","## What the actual SEC financial filings say"]
    if not info.get("fundamental_stories"):
        lines+=["No independently verified SEC company filings were available for this market session."]
    for x in info.get("fundamental_stories",[]):
        lines+=["",f"### Filing: {x['ticker']}",x["recommendation"],
                x["why"],"**Reported facts:** "+x["evidence"],
                "**Limitations:** "+x["missing"],
                "**SEC source:** "+x["source"],
                "**Filed:** "+", ".join(sorted(set(x["filing_dates"].values())))]
    lines+=["","## Is there a short-term trade?","",info["trade_intro"]]
    if info["trade_story"]:
        x=info["trade_story"]
        lines+=["",f"### {x['ticker']} breakout",x["recommendation"],x["why"],x["evidence"],x["exit"]]
    if info["reversion_story"]:
        x=info["reversion_story"];lines+=["","### Rebound research",x["recommendation"],x["why"],x["evidence"],x["missing"]]
    lines+=["","**Final recommendation:** Keep DCA into VOO; no real trade is approved.",
        "","## Missing evidence / limitations"]+["- "+x for x in info["limits"]]
    return "\n\n".join(lines)+"\n"

def publish(base=Path("research"),site=Path("site")):
    data=[get(name,base) for name in REQUIRED]
    if any(x is None for x in data):raise FileNotFoundError("Daily report requires fresh research source JSON")
    bnf=get(OPTIONAL[0],base)
    fundamental=get("sec_fundamentals.json",base)
    info=narrative_bundle(*data,rev=bnf,fundamentals=fundamental)
    if not info["fresh"]:
        # Publish an honest no-data report; no recommendation from mismatched dates.
        info["long_intro"]="The data are not on the same date. We cannot fairly compare investments today."
    site.mkdir(exist_ok=True,parents=True)
    (site/"report.html").write_text(render_article(info),encoding="utf-8")
    (base/"daily_brief.md").write_text(render_markdown(info),encoding="utf-8")
    (site/"daily_brief.json").write_text(json.dumps(info,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print("PLAIN ENGLISH REPORT",info["date"],"synchronized:",info["fresh"],
          "fund stories:",len(info["long_stories"]),
          "trade section:",bool(info["trade_story"]))
    return info

if __name__=="__main__":publish()
