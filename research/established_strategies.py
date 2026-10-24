"""Established Strategies Lab — live, investable ETF records, never hindsight stock lists.

Approach: Use actual fund history (price + adjusted distributions) to compare VOO
with momentum ETF implementations and concentrated sector/index alternatives on
exactly matched US market dates and equal monthly contributions.

This does NOT reconstruct historical S&P index constituents or prove future alpha.
Changing holdings of SPMO/XMMO are already represented in their historical ETF prices.
XMMO changed its underlying index on 2019-06-21; only 2019-06-24 onward is
labelled *present index*.

No trading recommendations, paper execution, or scheduled alert changes.
"""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import json,math
import numpy as np
import pandas as pd
import yfinance as yf

TICKERS=("VOO","SPMO","XMMO","QQQ","SMH","MTUM","MDY")
BENCHMARK="VOO"
COST_BPS=10
START_USD=2000.
MONTHLY_USD=100.
WINDOWS=(
 ("common_2016","2016-10-03","Common 2016–latest (XMMO mixes earlier index history)"),
 ("current_xmmo","2019-06-24","Since current XMMO index adoption (2019–latest)"),
 ("recent_2022","2022-01-03","Recent 2022–latest"),
 ("recent_2024","2024-01-02","Recent 2024–latest"),
)
METADATA={
 "VOO":{"category":"S&P 500 baseline","rules":"Hold the US large-cap S&P 500 index; periodic fund-level index updates.","mechanism":"Broad benchmark","inception":"2010-09-07","source":"https://investor.vanguard.com/investment-products/etfs/profile/voo"},
 "SPMO":{"category":"Systematic large-cap momentum","rules":"S&P 500 Momentum Index: selects high-momentum names from S&P 500; selection and weights by index methodology; official fund reconstitutes/rebalances on third Friday March and September.","mechanism":"Rules-based cross-sectional stock selection","inception":"2015-10-09","source":"https://www.invesco.com/us/en/financial-products/etfs/invesco-sp-500-momentum-etf.html"},
 "XMMO":{"category":"Systematic mid-cap momentum","rules":"S&P MidCap 400 Momentum Index: roughly 80 high-momentum mid-caps; semiannual reconstitution/rebalance. Current index started 2019-06-21; earlier XMMO fund returns used different indexes.","mechanism":"Rules-based cross-sectional stock selection","inception":"2005-03-03","current_index_from":"2019-06-21","source":"https://www.invesco.com/content/dam/invesco/us/en/product-documents/etf/fact-sheet/xmmo-invesco-s-p-midcap-momentum-etf-fact-sheet.pdf"},
 "QQQ":{"category":"Concentrated Nasdaq-100 index","rules":"Own Nasdaq-100 index constituents. Not a momentum timing strategy.","mechanism":"Market-cap index exposure, tech-heavy","inception":"1999-03-10","source":"https://www.invesco.com/qqq-etf/en/home.html"},
 "SMH":{"category":"Concentrated semiconductor industry","rules":"Own a concentrated index of US-listed semiconductor industry stocks. Not a momentum timing strategy.","mechanism":"Sector concentration","inception":"2011-12-20","source":"https://www.vaneck.com/us/en/investments/semiconductor-etf-smh/"},
 "MTUM":{"category":"Alternate rules-based momentum","rules":"Tracks broad MSCI USA Momentum index fund; methodology differs from SPMO.","mechanism":"Rules-based US equity factor selection","inception":"2013-04-16","source":"https://www.ishares.com/us/products/239726/ishares-msci-usa-momentum-factor-etf"},
 "MDY":{"category":"S&P MidCap 400 benchmark","rules":"Hold the S&P MidCap 400 constituents. A relevant mid-cap comparator for XMMO.","mechanism":"Mid-cap broad index baseline","inception":"1995-05-04","source":"https://www.ssga.com/us/en/intermediary/etfs/spdr-sp-midcap-400-etf-trust-mdy"},
}
def get_prices():
    out={}
    for symbol in TICKERS:
        frame=yf.download(symbol,start="2016-01-01",auto_adjust=True,
                          progress=False,threads=False,multi_level_index=False)
        if frame.empty or not {"Open","Close"}.issubset(frame):
            raise ValueError(f"Missing adjusted Open/Close for {symbol}: do not publish stale signals")
        for field in ("Open","Close"):
            series=frame[field]
            if isinstance(series,pd.DataFrame):series=series.iloc[:,0]
            out[symbol,field]=series.astype(float)
    prices=pd.concat(out,axis=1).sort_index().dropna()
    prices.index=pd.DatetimeIndex(prices.index).tz_localize(None)
    local=datetime.now(ZoneInfo("America/New_York"))
    if prices.index[-1].date()==local.date() and (local.hour,local.minute)<(16,30):
        prices=prices.iloc[:-1]
    if len(prices)<2400 or prices.index[-1]<pd.Timestamp.now(tz="UTC").tz_localize(None)-pd.Timedelta(days=8):
        raise ValueError("Fund history insufficient or older than eight days; no misleading report")
    if (prices<=0).any().any() or prices.index.has_duplicates:
        raise ValueError("ETF prices invalid")
    return prices

def simulate(prices,symbol,begin,end,fee_bps=10,detail=False):
    """Matched monthly DCA; initial buy and additions at each month's first opening.
    Expense ratio embedded in actual ETF adjusted prices; add per-side brokerage proxy.
    """
    idx=prices.index
    choose=np.flatnonzero((idx>=pd.Timestamp(begin))&(idx<=pd.Timestamp(end)))
    if len(choose)<100:raise ValueError("Too few matched dates in comparison")
    op=prices[symbol,"Open"].to_numpy(float)
    cl=prices[symbol,"Close"].to_numpy(float)
    units=0.;cash=START_USD;contributions=START_USD
    prev_nav=START_USD;last_month=None;orders=0;fees=0.;returns=[];equity=[]
    rate=fee_bps/10000.
    for i in choose:
        month=idx[i].to_period("M")
        deposit=MONTHLY_USD if last_month is not None and last_month!=month else 0.
        if deposit:
            cash+=deposit;contributions+=deposit
        if last_month is None or month!=last_month:
            notional=cash/(1+rate)
            if notional>.001:
                units+=notional/op[i]
                charge=notional*rate
                cash-=notional+charge
                fees+=charge;orders+=1
        nav=cash+units*cl[i]
        if nav<=0 or cash<-.001:raise AssertionError("Cash accounting error")
        returns.append(nav/(prev_nav+deposit)-1)
        equity.append(nav);prev_nav=nav;last_month=month
    ret=np.asarray(returns,float)
    wealth=np.cumprod(1+ret)
    peak=np.maximum.accumulate(np.r_[1.,wealth])[1:]
    elapsed=(idx[choose[-1]]-idx[choose[0]]).days/365.25
    vol=float(np.std(ret,ddof=1))*math.sqrt(252)
    metrics={"start":str(idx[choose[0]].date()),"end":str(idx[choose[-1]].date()),
        "annual_twr_pct":round(float((wealth[-1]**(1/elapsed)-1)*100),2),
        "max_drawdown_pct":round(float((wealth/peak-1).min()*100),2),
        "volatility_pct":round(vol*100,2),"sharpe_zero_rf":round(float(np.mean(ret)*math.sqrt(252)/np.std(ret,ddof=1)),2) if vol>0 else None,
        "ending_usd":round(float(equity[-1]),2),"total_deposits_usd":round(contributions,2),
        "orders":orders,"trading_fees_usd":round(fees,2),
        "annual_by_calendar_year_pct":{str(yr):round(float((np.prod(1+ret[idx[choose].year==yr])-1)*100),2)
            for yr in sorted(set(idx[choose].year))}
        }
    if detail:
        months=pd.PeriodIndex(idx[choose],freq="M")
        by_month=pd.Series(ret).groupby(months).apply(lambda r:float(np.prod(1+r)-1))
        metrics["_monthly"]=by_month
        metrics["_daily"]=pd.Series(ret,index=idx[choose])
    return metrics

def block_bootstrap(left,right):
    """Paired, circular 3-month block resampling; not selection-adjusted.
    Returns arithmetic monthly active mean annualised; 90% interval.
    """
    aligned=pd.concat([left,right],axis=1,join="inner").dropna()
    x=(aligned.iloc[:,0]-aligned.iloc[:,1]).to_numpy(float)
    n=len(x)
    if n<24:return {"enough_months":False,"months":n}
    rng=np.random.default_rng(6013);samples=np.empty(1800)
    k=3
    for i in range(len(samples)):
        starts=rng.integers(0,n,size=math.ceil(n/k))
        points=np.concatenate([(st+np.arange(k))%n for st in starts])[:n]
        samples[i]=12*100*np.mean(x[points])
    a,b=np.quantile(samples,[.05,.95])
    return {"enough_months":True,"months":n,
      "observed_average_active_pp_ann":round(float(np.mean(x)*1200),2),
      "ci90_lower":round(float(a),2),"ci90_upper":round(float(b),2),
      "fraction_months_ahead_pct":round(float((x>0).mean()*100),1),
      "zero_in_ci90":bool(a<=0<=b),
      "limitations":"Retrospective, selected fund universe; no adjustment for searching multiple alternatives"}

def compare(prices):
    newest=str(prices.index[-1].date())
    report={"generated_utc":pd.Timestamp.now(tz="UTC").strftime("%Y-%m-%d %H:%M UTC"),
        "latest_completed_us_market_day":newest,
        "objective":"Search among actual operated investment funds for implemented selection strategies beating S&P 500 after common-sample execution costs.",
        "hard_gate":"No fund or copied trading rule is approved as an automatic real-money BUY/SELL signal.",
        "ticker_metadata":METADATA,"tickers":TICKERS,
        "simulated_account":{"starting_usd":START_USD,"monthly_usd":MONTHLY_USD,
            "extra_broker_cost_bps_one_way":COST_BPS,
            "expenses_and_distributions":"ETF expense ratios embedded in adjusted market data; adjusted Open/Close approximate reinvested dividends",
            "taxes":"No Singapore or US withholding, estate, or Syfe order/FX cost simulation; comparison should NOT be read as equivalent to CSPX after tax",
            "fractional_units":True},
        "windows":{}, "historical_bias_flags":[
            "We chose and examined these ETFs in 2026; their older success is retrospective and may reflect hindsight selection.",
            "The historical data are the real ETF tickers, not a fake reconstruction of today's winning stock constituents.",
            "XMMO changed index 2019-06-21: historical return before 2019-06-24 is a DIFFERENT methodology.",
            "QQQ and SMH are concentrated growth/sector bets, not systematic entry/exit trading rules.",
            "No individual stock trading strategy is replicated here; acquiring point-in-time constituent/sector universe data is a separate research requirement.",
            "Profitable over a particular past sample does not mean it will keep beating VOO.",
            "Transaction fees use a simple 10bps/side proxy; costs, tax and FX differ by broker and domicile."]}
    for key,start,label in WINDOWS:
        full={symbol:simulate(prices,symbol,start,newest,fee_bps=COST_BPS,detail=True) for symbol in TICKERS}
        benchmark=full[BENCHMARK]
        risk={}
        for symbol in TICKERS:
            item=full[symbol]
            x=item["_daily"];base=benchmark["_daily"]
            beta=float(np.cov(x,base,ddof=1)[0,1]/np.var(base,ddof=1))
            risk[symbol]={
                "annual_advantage_over_voo_pp":round(item["annual_twr_pct"]-benchmark["annual_twr_pct"],2),
                "historically_exceeds_voo_after_10bps":item["annual_twr_pct"]>benchmark["annual_twr_pct"],
                "beta_to_voo":round(beta,2),
                "paired_active_uncertainty":block_bootstrap(item["_monthly"],benchmark["_monthly"]) if symbol!=BENCHMARK else None,
                "returns_30bps":{fld:val for fld,val in simulate(prices,symbol,start,newest,fee_bps=30).items() if fld in
                   ("annual_twr_pct","trading_fees_usd","ending_usd")},
                "returns_0bps":{fld:val for fld,val in simulate(prices,symbol,start,newest,fee_bps=0).items() if fld in
                   ("annual_twr_pct","trading_fees_usd","ending_usd")}
            }
        # This is descriptive, not claim of valid out-of-sample significance.
        item_metrics={symbol:{field:val for field,val in data.items() if not field.startswith("_")}
                      for symbol,data in full.items()}
        report["windows"][key]={"label":label,"start":item_metrics["VOO"]["start"],
           "end":newest,"returns":item_metrics,"diagnostics":risk}
    report["analysis"]={
       "candidate_screen":[
           {"ticker":symbol,
           "beats_voo_2019_onwards":report["windows"]["current_xmmo"]["diagnostics"][symbol]["historically_exceeds_voo_after_10bps"],
           "beats_voo_2022_onwards":report["windows"]["recent_2022"]["diagnostics"][symbol]["historically_exceeds_voo_after_10bps"],
           "extra_vs_voo_2019_pp":report["windows"]["current_xmmo"]["diagnostics"][symbol]["annual_advantage_over_voo_pp"],
           "extra_vs_voo_2022_pp":report["windows"]["recent_2022"]["diagnostics"][symbol]["annual_advantage_over_voo_pp"],
           "annual_2022_pct":report["windows"]["recent_2022"]["returns"][symbol]["annual_twr_pct"],
           "max_dd_2022_pct":report["windows"]["recent_2022"]["returns"][symbol]["max_drawdown_pct"],
           "status":"HISTORICAL FACTOR CANDIDATE / NOT PREDICTIVE TRADING APPROVAL"
                      if symbol in ("SPMO","XMMO","MTUM") else "CONCENTRATED EXPOSURE / NOT ENTRY SIGNAL" }
           for symbol in TICKERS if symbol!="VOO"
       ],
       "strategy_to_copy":"Do not clone the funds as if they were active daily buy/sell strategies. For individual stock replication we need exact historical eligible lists, corporate action treatment, and index weight/rebalance methodology.",
       "next_action":"Paper-track any momentum fund exposure versus VOO/CSPX; independently audit fund index methodology changes and US vs Ireland withholding/FX before real purchases.",
       "automatic_live_trading_approved":False}
    report["analysis"]["candidate_screen"].sort(
        key=lambda item:item["extra_vs_voo_2019_pp"],reverse=True)
    return report

def summary_md(r):
    lines=["# SignalDesk — Implemented Strategies Comparison","",
      "**Status: REAL ETF HISTORIES, NOT AN AUTOMATIC TRADING SIGNAL**",
      f"Data through {r['latest_completed_us_market_day']}.",
      "Same US trading dates, starting US$2,000, monthly US$100, 10 bps per purchase, adjusted prices.",
      "",
      "| ETF | Fund strategy | From 2019 annual % | Since 2022 annual % | Worst 2022+ drawdown % | Beats VOO both periods? |",
      "|---|---|---:|---:|---:|---|"]
    a=r["windows"]["current_xmmo"]["returns"]
    b=r["windows"]["recent_2022"]["returns"]
    for sym in TICKERS:
        score=next((x for x in r["analysis"]["candidate_screen"] if x["ticker"]==sym),None)
        both=("yes" if score and score["beats_voo_2019_onwards"] and score["beats_voo_2022_onwards"] else "no")
        lines.append(f"| {sym} | {METADATA[sym]['category']} | {a[sym]['annual_twr_pct']} | {b[sym]['annual_twr_pct']} | {b[sym]['max_drawdown_pct']} | {both} |")
    lines+=["",
      "**Do not read XMMO 2016–2019 as its present index methodology.** Current index applied from 2019-06-21.",
      "QQQ/SMH are concentrated exposures, not tactical rules. No guarantee that historical winners continue to lead.",
      "Historical fund prices do not prove a public, actively traded entry/exit strategy beats the S&P 500.",
      "Broker commission, FX, taxes, Singapore nonresident withholding, estate risk and CSPX tracking are not included.",
      "",
      "## What to research next","",
      "Fund exposure over time is viable; an independently replicated 100-stock historical point-in-time momentum portfolio requires costly constituent history and must never be backfilled with current winners.",
      "",
      "## Official methodology references",""]
    for sym in TICKERS:
        lines.append(f"- [{sym}: {METADATA[sym]['category']}]({METADATA[sym]['source']})")
    return "\n".join(lines)+"\n"

def main():
    prices=get_prices()
    report=compare(prices)
    Path("research").mkdir(exist_ok=True,parents=True)
    Path("site").mkdir(exist_ok=True,parents=True)
    Path("research/established_strategies.json").write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    Path("research/established_strategies.md").write_text(summary_md(report),encoding="utf-8")
    Path("site/established_strategies.json").write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    page=Path("research/established_template.html").read_text(encoding="utf-8")
    embedded=json.dumps(report,separators=(",",":"),ensure_ascii=True).replace("<","\\u003c")
    Path("site/established.html").write_text(page.replace("/*ESTABLISHED_DATA*/",embedded),encoding="utf-8")
    print("ESTABLISHED LAB",report["latest_completed_us_market_day"])
    for candidate in report["analysis"]["candidate_screen"]:
        print(candidate["ticker"],"2019 excess:",candidate["extra_vs_voo_2019_pp"],
             "2022 excess:",candidate["extra_vs_voo_2022_pp"])
if __name__=="__main__":main()
