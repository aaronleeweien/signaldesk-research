"""Broad US market discovery (not a fixed watchlist): research, never live orders.

Stage 1: Nasdaq Trader's Nasdaq + other US exchange directories describe ALL
currently listed tickers, including ETFs. That is a catalog, NOT a full price scan.
Stage 2: Yahoo EQUITY screener collects multiple liquid-stock slices across market
cap, price momentum, growth and valuation. Successful result count is recorded.
Stage 3: batch historical price scans for top ~90 stocks. Show only independently
available earnings/valuation fields. Unknown growth estimates remain UNKNOWN.
Stage 4: for breakout candidates only, use the existing predeclared trade-rule
backtest, not a new fitted or retrospectively optimized rule.

Limits: US-listed market only; subset is screened with prices daily; data source
is unofficial; survival bias for today's tickers; valuation is NOT a price target.
"""
from __future__ import annotations
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
from io import StringIO
from urllib.request import Request,urlopen
import json,math,time
import numpy as np
import pandas as pd
import yfinance as yf

try:
    from . import decision_hub as hub
except ImportError:
    import decision_hub as hub

VERSION="market_discovery_v1"
DIRECTORIES=(
 ("NASDAQ","https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt"),
 ("OTHER_US","https://www.nasdaqtrader.com/dynamic/SymDir/otherlisted.txt")
)
SELECTION_COUNT=90
TECHNICAL_COUNT=35
MOMENTUM_MIN_DAYS=253
MIN_MARKET_CAP=1_000_000_000
MIN_VOLUME=300_000
MAX_PRICE=200_000
SOURCES=("Largest listed","Strong price momentum","Positive earnings growth","Low price versus earnings")
SORTS=("intradaymarketcap","fiftytwowkpercentchange","epsgrowth.lasttwelvemonths","peratio.lasttwelvemonths")
SCREENS=(False,False,False,True)
BLOCKLIST=(" warrant"," warrants"," rights"," right "," unit "," units",
           " preferred"," preference"," depositary"," note "," notes",
           " acquisition corp"," acquisition company"," trust preferred")

def as_float(value):
    if value is None or isinstance(value,bool):return None
    try:
        result=float(value)
        return result if math.isfinite(result) else None
    except (ValueError,TypeError):return None

def first_number(d,fields):
    for field in fields:
        value=as_float(d.get(field))
        if value is not None:return value
    return None

def parse_directory(source,raw):
    df=pd.read_csv(StringIO(raw),sep="|",dtype=str,keep_default_na=False)
    df.columns=[x.strip() for x in df.columns]
    listings=[]
    for row in df.to_dict(orient="records"):
        ticker=(row.get("Symbol") if source=="NASDAQ" else row.get("ACT Symbol","")).strip()
        name=(row.get("Security Name","") or "").strip()
        if not ticker or "File Creation Time" in ticker or row.get("Test Issue")!="N":continue
        if row.get("ETF") not in ("Y","N"):continue
        if source=="NASDAQ" and row.get("Financial Status","N") not in ("N",""):continue
        if any(z in name.lower() for z in BLOCKLIST):continue
        if len(ticker)>9 or not all(k.isalnum() or k in (".","-") for k in ticker):continue
        listings.append({"ticker":ticker,"name":name,"type":"ETF" if row.get("ETF")=="Y" else "Stock",
                         "exchange":"NASDAQ" if source=="NASDAQ" else row.get("Exchange","OTHER")})
    return listings

def directory_catalog():
    entries=[];errors=[]
    for source,url in DIRECTORIES:
        try:
            req=Request(url,headers={"User-Agent":"Mozilla/5.0 SignalDeskResearch/1.0"})
            with urlopen(req,timeout=12) as r:
                data=r.read(2_500_000).decode("utf-8-sig",errors="replace")
            found=parse_directory(source,data)
            if len(found)<500:raise ValueError("Directory returned too few listings")
            entries+=found
        except Exception as ex:
            errors.append(f"{source}: {type(ex).__name__}")
    unique={r["ticker"]:r for r in entries}
    counts={"US_listings_catalogued":len(unique),
            "listed_stocks_catalogued":sum(v["type"]=="Stock" for v in unique.values()),
            "listed_ETFs_catalogued":sum(v["type"]=="ETF" for v in unique.values()),
            "scope":"NASDAQ and other US exchanges (directory only; not all companies priced daily)",
            "catalog_complete":len(errors)==0,
            "catalog_issues":errors,
            "source":"https://www.nasdaqtrader.com/trader.aspx?id=symboldirdefs"}
    return unique,counts

def quote_from_screen(q,source):
    symbol=q.get("symbol")
    if not isinstance(symbol,str) or len(symbol)>9 or not all(c.isalnum() or c in ".-" for c in symbol):
        return None
    if q.get("quoteType","EQUITY") not in ("EQUITY",None):
        return None
    cap=first_number(q,("marketCap","intradaymarketcap","lastclosemarketcap.lasttwelvemonths"))
    volume=first_number(q,("averageDailyVolume3Month","avgdailyvol3m","dayvolume"))
    if cap is not None and cap<MIN_MARKET_CAP:return None
    if volume is not None and volume<MIN_VOLUME:return None
    pe=first_number(q,("forwardPE","forwardPe"))
    trailing=first_number(q,("trailingPE","trailingPe","peratio.lasttwelvemonths"))
    peg=first_number(q,("pegRatio","pegratio_5y"))
    growth=first_number(q,("earningsGrowth","epsgrowth.lasttwelvemonths","epsGrowth"))
    growth_source="direct earnings-growth field" if growth is not None else "not available"
    # Both ratios use the same price: trailing P/E divided by forward P/E
    # minus one approximately measures the market's change in estimated EPS.
    if growth is None and pe is not None and trailing is not None and pe>0 and trailing>0:
        estimate=trailing/pe-1
        if -0.95<estimate<5.0:
            growth=estimate
            growth_source="implied EPS change using forward/trailing P/E"
    sales=first_number(q,("revenueGrowth","quarterlyrevenuegrowth.quarterly"))
    # Yahoo growth can be a fraction in some fields or percent points in screener.
    # A directly provided screener field may be percentage points. A
    # forward/trailing P/E derived estimate is ALREADY a fraction, even if >2.
    if growth is not None and abs(growth)>2 and growth_source=="direct earnings-growth field":
        growth/=100
    if sales is not None and abs(sales)>2:sales/=100
    return {"ticker":symbol,"name":q.get("shortName") or q.get("longName") or symbol,
            "sector":q.get("sector") or None,"industry":q.get("industry") or None,
            "market_cap_usd":cap,"average_volume_shares":volume,
            "forward_pe":pe,"trailing_pe":trailing,"peg":peg,
            "earnings_growth_pct":round(growth*100,2) if growth is not None else None,
            "revenue_growth_pct":round(sales*100,2) if sales is not None else None,
            "analyst_growth_forecast_available":pe is not None,
            "earnings_growth_source":growth_source,
            "sources":[source]}

def screen_market(catalog):
    """Multiple independently oriented lenses, no manually selected individual stocks.
    Yahoo permits 250 per paginated screener call. Record actual coverage; no
    claim that screener samples == entire US market.
    """
    available={};failures=[];calls=0
    from yfinance import EquityQuery
    common=EquityQuery("and",[
      EquityQuery("eq",["region","us"]),
      EquityQuery("gte",["intradaymarketcap",MIN_MARKET_CAP]),
      EquityQuery("gte",["avgdailyvol3m",MIN_VOLUME]),
      EquityQuery("gte",["intradayprice",5])
    ])
    for label,sort,ascending in zip(SOURCES,SORTS,SCREENS):
        try:
            # First page per category; do not imply exhaustive even if successful.
            result=yf.screen(common,size=250,offset=0,sortField=sort,sortAsc=ascending)
            calls+=1
            data=result.get("quotes",[]) or []
            if not isinstance(data,list):raise ValueError("Unexpected screen response")
            for item in data:
                q=quote_from_screen(item,label)
                if q is None:continue
                if catalog and q["ticker"] not in catalog:continue
                if q["ticker"] not in available:
                    available[q["ticker"]]=q
                else:
                    prev=available[q["ticker"]]
                    prev["sources"]=list(dict.fromkeys(prev["sources"]+q["sources"]))
                    for k,v in q.items():
                        if k not in ("sources",) and prev.get(k) is None and v is not None:prev[k]=v
        except Exception as ex:
            failures.append(f"{label}: {type(ex).__name__}: {str(ex)[:100]}")
    # Fresh outside-research watchlists explicitly enter discovery, not fixed screen universe.
    for t in ("VOO","SPMO","QQQ"):
        available.pop(t,None) # these are funds, not stocks
    return available,{"screen_calls_ok":calls,"unique_stock_quotes":len(available),
       "screen_failures":failures,"screen_style":"4 independent liquid-stock screens, max 250 quotes each; overlap deduplicated",
       "screen_fully_marketwide":False,
       "screener_source":"https://ranaroussi.github.io/yfinance/reference/api/yfinance.screen.html"}

def shortlist(quotes):
    def priority(q):
        # Avoid mechanically only following the best 2026 stock winners.
        # Balanced representation from large / momentum / growth / value.
        pos=min((SOURCES.index(s) for s in q["sources"]),default=9)
        cap=q["market_cap_usd"] or 0
        return (len(q["sources"]),math.log1p(cap),-pos)
    keys=[]
    for cat in SOURCES:
        arr=[q for q in quotes.values() if cat in q["sources"]]
        arr.sort(key=priority,reverse=True)
        keys.extend(q["ticker"] for q in arr[:40])
    # Ensure broad exposure with stocks collected from different lenses.
    # Spread the sample across size, momentum, growth and valuation,
    # so the first query cannot swallow the entire selection.
    sources={label:[q["ticker"] for q in quotes.values() if label in q["sources"]]
             for label in SOURCES}
    for label in SOURCES:
        sources[label].sort(key=lambda t:priority(quotes[t]),reverse=True)
    picked=[]
    for rank in range(40):
        for label in SOURCES:
            names=sources[label]
            if rank<len(names) and names[rank] not in picked:
                picked.append(names[rank])
            if len(picked)>=SELECTION_COUNT:return picked
    return picked

def get_prices(tickers):
    """Batch once for screen-selected names; avoid thousands of small HTTP calls."""
    symbols=list(dict.fromkeys(("VOO",)+tuple(tickers)))
    raw=yf.download(symbols,start="2017-01-01",auto_adjust=True,threads=True,
                    progress=False,group_by="ticker",multi_level_index=True)
    if raw.empty:raise ValueError("Price provider returned no bars")
    frame={}
    for ticker in symbols:
        try:
            data=raw[ticker]
            if not {"Open","Close"}.issubset(data.columns):continue
            frame[(ticker,"Open")]=data["Open"].astype(float)
            frame[(ticker,"Close")]=data["Close"].astype(float)
        except (TypeError,KeyError):continue
    if ("VOO","Close") not in frame:raise ValueError("VOO benchmark missing; abort")
    d=pd.concat(frame,axis=1).sort_index()
    d.index=pd.DatetimeIndex(d.index).tz_localize(None)
    now=datetime.now(ZoneInfo("America/New_York"))
    if d.index[-1].date()==now.date() and (now.hour,now.minute)<(16,30):d=d.iloc[:-1]
    if pd.Timestamp.now(tz="UTC").tz_localize(None)-d.index[-1]>pd.Timedelta(days=7):
        raise ValueError("Price feed stale; no recommendations")
    return d

def analyse_stock(ticker,quote,df,benchmark,asof):
    column=(ticker,"Close")
    if column not in df or (ticker,"Open") not in df:return None
    s=df[column].reindex(benchmark.index)
    o=df[ticker,"Open"].reindex(benchmark.index)
    good=s.notna()&o.notna()&(s>0)&(o>0)
    if not good.iloc[-1] or good.sum()<MOMENTUM_MIN_DAYS:return None
    last=float(s.iloc[-1]);first_idx=len(s)-253
    if not good.iloc[first_idx]:return None
    trailing=float(s.iloc[-1]/s.iloc[first_idx]-1)
    base=float(benchmark.iloc[-1]/benchmark.iloc[first_idx]-1)
    f=hub.features(s.to_numpy(float))
    if not np.isfinite(f["sma200"][-1]):return None
    r63=float(f["r63"][-1]);r126=float(f["r126"][-1])
    if not all(np.isfinite(v) for v in (r63,r126)):return None
    momentum=last>f["sma200"][-1] and r63>0 and r126>0
    forward=quote["forward_pe"]
    earnings=quote["earnings_growth_pct"]
    sales=quote["revenue_growth_pct"]
    # Missing values are never treated as zero or "undervalued".
    valuation_complete=(forward is not None and 0<forward<=60 and
                        earnings is not None and 0<earnings<=150)
    established_company=(quote.get("market_cap_usd") is not None and
                         quote["market_cap_usd"]>=5_000_000_000)
    very_large_runup=trailing>2.0
    future="FORECAST PARTIAL — NOT A PRICE TARGET"
    if valuation_complete:
        future="FORWARD EARNINGS + VALUATION AVAILABLE — NOT A FAIR VALUE"
    status=("RESEARCH CANDIDATE" if trailing>base and momentum and
            valuation_complete and established_company and not very_large_runup
            else "WATCH / MISSING PROOF")
    score=3*(trailing-base)+r63+r126
    result={k:quote.get(k) for k in (
        "ticker","name","sector","industry","market_cap_usd","average_volume_shares",
        "forward_pe","trailing_pe","peg","earnings_growth_pct","revenue_growth_pct","sources","earnings_growth_source")}
    result.update({"asset_type":"Stock","status":status,"forecast_status":future,
        "last_close_usd":round(last,2),"return_last_year_pct":round(trailing*100,2),
        "voo_same_year_pct":round(base*100,2),
        "relative_to_voo_year_pp":round((trailing-base)*100,2),
        "momentum_3m_pct":round(r63*100,2),
        "momentum_6m_pct":round(r126*100,2),
        "above_200d_average":bool(last>f["sma200"][-1]),
        "trend_is_positive":bool(momentum),
        "valuation_metrics_complete":bool(valuation_complete),
        "larger_established_company":bool(established_company),
        "extreme_one_year_return":bool(very_large_runup),
        "fundamentals_are_forecasts":True,
        "priority_score":round(score*100,2),
        "last_price_date":asof,
        "simple_explanation":(
            "The stock beat VOO over the last year, and its price trend is positive. "
            "We checked earnings forecasts and valuation too. This is worth studying, not an automatic BUY."
            if status=="RESEARCH CANDIDATE" else
            "One or more checks is missing: past outperformance, a strong trend, or enough earnings/valuation data."
        ),
        "valuation_note":"Forward P/E = today's stock price divided by estimated next-year earnings. A low P/E alone does not mean undervalued.",
        "warnings":[
            "Company earnings estimates can be wrong and often change.",
            "When direct earnings growth is missing, any shown growth is estimated using forward and trailing P/E, not independent financial research.",
            "Forward P/E does not measure true fair value; valuation differs by industry.",
            "The current US-listed stock universe excludes previously delisted companies; historical results can be biased.",
            "A large one-year price gain may reverse, so it is not automatically a good purchase.",
            "Comparing trailing one-year stock returns with VOO is NOT proof of future excess returns."]})
    return result

def study_trade(candidate,df):
    """Research only; same rule as original daily hub, extra candidates NOT prevalidated."""
    ticker=candidate["ticker"]
    cols=[("VOO","Open"),("VOO","Close"),(ticker,"Open"),(ticker,"Close")]
    frame=df.loc[:,cols].copy()
    # Keep a *common* exact set of dated bars for fair per-trade comparison.
    frame=frame.dropna()
    if len(frame)<hub.MAX_HOLD+300:return None
    trades,f=hub.completed_trades(frame,ticker)
    status=hub.validate_trades(trades)
    signal=hub.snapshot_signal(frame,ticker,f)
    # Distinguish unvalidated historical screening from real trading permission.
    is_new=signal["brand_new_breakout"]
    if not is_new:return None
    buy,sell=hub.estimated_exit_date(str(frame.index[-1].date()))
    return {"ticker":ticker,"name":candidate["name"],
         "entry_date_estimate":buy,"latest_exit_estimate":sell,
         "entry_rule":"Prior 20-day high breakout + positive 63/126-day momentum + above SMA200",
         "exit_rule":"At the following US open after a 7% closing stop, 10-day low, SMA200 break or 15-session limit",
         "past_completed_trades":status["n"],
         "win_rate_pct":status["win_rate_pct"],
         "avg_excess_vs_same_dates_voo_pp":status["avg_vs_voo_pct"],
         "recent_excess_2022_pp":status["recent_vs_voo_pct"],
         "passes_retrospective_screen":status["passes_historical_gate"],
         "approved_for_real_money":False,
         "status":"PAPER RESEARCH ONLY",
         "warning":"Today's survivors and multiple tested names cause look-back bias; no independently verified trade edge."}

def run():
    catalog,coverage=directory_catalog()
    quotes,screens=screen_market(catalog)
    asof=None;ideas=[];trades=[];errors=[]
    if quotes:
        try:
            chosen=shortlist(quotes)
            prices=get_prices(chosen)
            # Actual common benchmark market dates only.
            index=prices.index
            benchmark=prices["VOO","Close"].dropna()
            latest=str(benchmark.index[-1].date())
            asof=latest
            for sym in chosen:
                try:
                    idea=analyse_stock(sym,quotes[sym],prices,benchmark,latest)
                    if idea is None:continue
                    ideas.append(idea)
                except Exception as ex:
                    errors.append(f"{sym}: {type(ex).__name__}")
            ideas.sort(key=lambda z:(z["status"]=="RESEARCH CANDIDATE",
                                     z["relative_to_voo_year_pp"],
                                     z["priority_score"]),reverse=True)
            # Research trades for a bounded universe; no asset ever auto-approved.
            for candidate in ideas[:TECHNICAL_COUNT]:
                try:
                    outcome=study_trade(candidate,prices)
                    if outcome is not None:trades.append(outcome)
                except (ValueError,KeyError) as ex:
                    errors.append(f"Trade {candidate['ticker']}: {type(ex).__name__}")
        except Exception as ex:
            errors.append("Historical batch feed: "+type(ex).__name__+": "+str(ex)[:120])
    return {
       "version":VERSION,
       "generated_utc":pd.Timestamp.now(tz="UTC").strftime("%Y-%m-%d %H:%M UTC"),
       "last_completed_us_price_date":asof,
       "scope":"US exchange-listed public stocks and ETFs; NOT the entire global financial market.",
       "universe_catalog":coverage,
       "discovery_feeds":screens,
       "stocks_with_price_and_momentum_results":len(ideas),
       "stocks_with_price_growth_and_valuation_data":sum(x["valuation_metrics_complete"] for x in ideas),
       "stock_investing_watchlist":ideas[:30],
       "expanded_trade_watches":trades[:15],
       "has_verified_profitable_trade_rule":False,
       "next_step":"Seek point-in-time constituent histories and credible fundamental data coverage before any broad-market outperformance claims.",
       "errors":errors,
       "important":"Thousands of symbols in the catalog do not mean that each was priced, valued or trade-backtested today. The second-stage screen is a sample; report exact coverage.",
       "valuation_limits":"Forward P/E and earnings/revenue growth are a first check, NOT discounted cash flow, fair value or a forecast of stock price. No risk-adjusted expected return is estimated.",
       "trading_limits":"A historically profitable setup on today's surviving ticker is not a proven future tradable strategy."
    }

def publish(d):
    for dirname in ("research","site"):Path(dirname).mkdir(exist_ok=True)
    encoded=json.dumps(d,indent=2,ensure_ascii=False)+"\n"
    Path("research/market_discovery.json").write_text(encoded,encoding="utf-8")
    Path("site/market_discovery.json").write_text(encoded,encoding="utf-8")
    tpl=Path("research/market_template.html").read_text(encoding="utf-8")
    safe=json.dumps(d,separators=(",",":"),ensure_ascii=True).replace("<","\\u003c")
    Path("site/market.html").write_text(tpl.replace("/*MARKET_DATA*/",safe),encoding="utf-8")
    print("MARKET DISCOVERY",d["universe_catalog"]["US_listings_catalogued"],"catalogued",
       d["discovery_feeds"]["unique_stock_quotes"],"screener stocks",
       d["stocks_with_price_and_momentum_results"],"priced",
       d["stocks_with_price_growth_and_valuation_data"],"fundamentals complete",
       d["last_completed_us_price_date"],"issues",d["errors"][:3])
if __name__=="__main__":
    publish(run())
