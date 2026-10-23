"""SignalDesk Stock Opportunities (research, NEVER live trading approval).
Two *predeclared* monthly cross-sectional stock strategies, no ML hype or broker orders.
WARNING: Fixed survivor tickers introduce severe survivorship/selection bias.
"""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import json
import numpy as np
import pandas as pd
import yfinance as yf

# Static modern-known stocks chosen for exploratory coverage. NOT a historical point-in-time universe.
# Excludes delisted companies and is biased toward survivors; no excess return is validated alpha.
STOCKS=(
"AAPL","MSFT","NVDA","AMZN","GOOGL","IBM","INTC","CSCO","ORCL","QCOM",
"TXN","ADBE","JPM","BAC","WFC","XOM","CVX","JNJ","PFE","MRK",
"KO","PEP","WMT","HD","MCD","CAT","BA","DIS","GE","UNH",
)
TICKERS=("VOO","QQQ","SHY")+STOCKS
NAMES=("VOO DCA","QQQ DCA","Static Equal Weight","Top-5 Momentum","Top-5 Trend Filter","Top-5 Defensive")
INITIAL=2000.;CONTRIBUTION=100.;COST=.001
PERIODS={"development":("2013-01-02","2018-12-31"),
"validation":("2019-01-02","2022-12-30"),
"diagnostic":("2023-01-03",None)}

def fetch_prices():
    pieces={}
    # Per-ticker downloads tolerate one missing data source by STOPPING, not ignoring missing failed names.
    for ticker in TICKERS:
        data=yf.download(ticker,start="2010-09-01",auto_adjust=True,
                         multi_level_index=False,progress=False,threads=False)
        if data.empty or not {"Open","Close"}.issubset(data.columns):
            raise ValueError("Missing historical price data for "+ticker)
        for field in ("Open","Close"):
            pieces[(ticker,field)]=data[field]
    df=pd.concat(pieces,axis=1).sort_index().dropna()
    df.index=pd.DatetimeIndex(df.index).tz_localize(None)
    ny=datetime.now(ZoneInfo("America/New_York"))
    if df.index[-1].date()==ny.date() and (ny.hour,ny.minute)<(16,30):
        df=df.iloc[:-1]
    if len(df)<3000 or df.index[-1]<pd.Timestamp.now(tz="UTC").tz_localize(None)-pd.Timedelta(days=8):
        raise ValueError("Price data missing or stale, refusing to publish")
    if df.index.has_duplicates or (df<=0).any().any():
        raise ValueError("Bad historical prices")
    return df

def rank(closes,decision_day):
    """Stock rankings use closes only up to end of the completed prior session."""
    p=closes.iloc[:decision_day+1]
    eligible=[]
    if len(p)<260:return []
    for ticker in STOCKS:
        x=p[ticker]
        r12to1=x.iloc[-22]/x.iloc[-253]-1.
        r6=x.iloc[-1]/x.iloc[-127]-1.
        trend=x.iloc[-1]>x.iloc[-200:].mean()
        # Fixed predeclared blend of 12-1 and six-month trend indicators.
        score=.65*r12to1+.35*r6
        eligible.append((ticker,float(score),bool(trend),float(r6),float(r12to1)))
    return sorted(eligible,key=lambda q:q[1],reverse=True)

def plans(df):
    close=df.xs("Close",level=1,axis=1)
    result={m:[] for m in NAMES}
    last_month=None
    active={}
    for i,date in enumerate(df.index):
        new_month=last_month!=date.to_period("M")
        if new_month:
            if i<260:
                static={t:1/len(STOCKS) for t in STOCKS}
                mom={"SHY":1.};trend={"SHY":1.};defensive={"SHY":1.}
            else:
                # Month first session uses prior completed close only.
                ranked=rank(close,i-1)
                best=ranked[:5]
                static={t:1/len(STOCKS) for t in STOCKS}
                mom={t:.2 for t,score,passes,r6,r12 in best}
                good=[t for t,score,passes,r6,r12 in ranked if passes and score>0 and r6>0][:5]
                trend={t:.2 for t in good}
                leftover=1.-sum(trend.values())
                if leftover>1e-9:trend["SHY"]=leftover
                # Regime check for entire market; no leverage.
                market=close.VOO.iloc[:i]
                good_market=market.iloc[-1]>market.iloc[-200:].mean()
                risky_weight=.7 if good_market else .35
                defensive={t:risky_weight*v for t,v in trend.items() if t!="SHY"}
                defensive["SHY"]=1.-sum(defensive.values())
            active={"VOO DCA":{"VOO":1.},
                    "QQQ DCA":{"QQQ":1.},
                    "Static Equal Weight":static,
                    "Top-5 Momentum":mom,
                    "Top-5 Trend Filter":trend,
                    "Top-5 Defensive":defensive}
            last_month=date.to_period("M")
        for model in NAMES:result[model].append(active[model].copy())
    return result

def backtest(df,schedule,start,end,fee=COST):
    all_idx=df.index
    selected=np.flatnonzero((all_idx>=pd.Timestamp(start))&(all_idx<=pd.Timestamp(end)))
    if len(selected)<150:raise ValueError("Insufficient observations")
    shares={t:0. for t in TICKERS}
    cash=INITIAL;deposited=INITIAL;previous_equity=INITIAL
    prev_month=None;prev_weights=None
    n_orders=0;paid=0.;net_returns=[];navs=[];last_target={}
    for j in selected:
        today=all_idx[j]
        deposit=0.
        if prev_month is not None and today.to_period("M")!=prev_month:
            cash+=CONTRIBUTION;deposited+=CONTRIBUTION;deposit=CONTRIBUTION
        target=schedule[j]
        if prev_month is None or today.to_period("M")!=prev_month or target!=prev_weights:
            opens={t:float(df.iloc[j][t,"Open"]) for t in TICKERS}
            portfolio_open=cash+sum(shares[t]*opens[t] for t in TICKERS)
            intended={t:portfolio_open*target.get(t,0.) for t in TICKERS}
            for t in TICKERS:
                sale=max(0.,shares[t]*opens[t]-intended[t])
                if sale>.01:
                    qty=min(shares[t],sale/opens[t]);gross=qty*opens[t];commission=gross*fee
                    cash+=gross-commission;shares[t]-=qty
                    n_orders+=1;paid+=commission
            for t in TICKERS:
                buying=max(0.,intended[t]-shares[t]*opens[t])
                buying=min(buying,cash/(1+fee))
                if buying>.01:
                    commission=buying*fee;shares[t]+=buying/opens[t];cash-=buying+commission
                    n_orders+=1;paid+=commission
        ending=cash+sum(shares[t]*float(df.iloc[j][t,"Close"]) for t in TICKERS)
        if cash<-.02 or ending<=0:raise AssertionError("Invalid cash or leverage")
        net_returns.append(ending/(previous_equity+deposit)-1.)
        navs.append(ending)
        previous_equity=ending;prev_month=today.to_period("M");prev_weights=target.copy();last_target=target.copy()
    rets=np.asarray(net_returns)
    wealth=np.cumprod(1+rets)
    maxdd=float((wealth/np.maximum.accumulate(np.r_[1.,wealth])[1:]-1.).min()*100)
    yrs=(all_idx[selected[-1]]-all_idx[selected[0]]).days/365.25
    annual=float((wealth[-1]**(1/yrs)-1)*100)
    std=float(np.std(rets,ddof=1))
    volatility=std*252**.5*100
    sharpe=float(np.mean(rets)/std*252**.5) if std>0 else 0.
    market=df["VOO","Close"].pct_change().reindex(all_idx[selected]).fillna(0.).values
    beta=float(np.cov(rets,market,ddof=1)[0,1]/np.var(market,ddof=1)) if np.var(market,ddof=1)>0 else 0.
    annual_by_year={}
    for year in sorted(set(all_idx[selected].year)):
        mask=all_idx[selected].year==year
        annual_by_year[str(year)]=round(float((np.prod(1+rets[mask])-1)*100),2)
    ind=np.unique(np.linspace(0,len(wealth)-1,min(240,len(wealth))).astype(int))
    return {"annual_twr_pct":round(annual,2),"worst_drawdown_pct":round(maxdd,2),
         "volatility_pct":round(volatility,2),"sharpe":round(sharpe,2),"beta_to_voo":round(beta,2),
         "ending_usd":round(ending,2),"total_contributed_usd":round(deposited,2),
         "fees_usd":round(paid,2),"orders":n_orders,
         "annual_by_year":annual_by_year,
         "last_weights":last_target,
         "curve":{"dates":[str(all_idx[selected[k]].date()) for k in ind],
                  "growth":[round(float(wealth[k]),4) for k in ind]}}

def get_next_session_target(df):
    # Replicate the calculation as if one additional future market session had just opened.
    fake=df.iloc[[-1]].copy()
    future=df.index[-1]+pd.offsets.BDay(1)
    fake.index=pd.DatetimeIndex([future])
    # The fake prices are not consumed when generating the next session's target.
    out=plans(pd.concat([df,fake]))
    return {m:out[m][-1] for m in NAMES},str(future.date())

def explain_targets(current,previous,latest_closes):
    output={}
    for model,target in current.items():
        old=previous.get(model,{})
        actions=[]
        for ticker in sorted(set(target)|set(old)):
            after=float(target.get(ticker,0.))
            before=float(old.get(ticker,0.))
            delta=after-before
            if delta>.00001:verb="PAPER BUY / INCREASE"
            elif delta<-.00001:verb="PAPER SELL / DECREASE"
            else:verb="PAPER HOLD"
            actions.append({"ticker":ticker,"action":verb,
             "previous_target_pct":round(before*100,2),
             "new_target_pct":round(after*100,2),
             "change_percentage_points":round(delta*100,2),
             "last_close_usd":round(float(latest_closes[ticker]),2)})
        output[model]=actions
    return output

def generate():
    df=fetch_prices()
    targets=plans(df)
    figures={}
    for name,(lo,hi) in PERIODS.items():
        end=hi or str(df.index[-1].date())
        figures[name]={m:backtest(df,targets[m],lo,end) for m in NAMES}
    next_targets,next_day=get_next_session_target(df)
    latest={t:float(df[t,"Close"].iloc[-1]) for t in TICKERS}
    before={m:targets[m][-1] for m in NAMES}
    decisions=explain_targets(next_targets,before,latest)
    candidates=["Top-5 Momentum","Top-5 Trend Filter","Top-5 Defensive"]
    qualified=[m for m in candidates if
      figures["validation"][m]["annual_twr_pct"]>figures["validation"]["VOO DCA"]["annual_twr_pct"]
      and figures["validation"][m]["worst_drawdown_pct"]>=figures["validation"]["VOO DCA"]["worst_drawdown_pct"]-7.]
    winner=max(qualified,key=lambda m: figures["validation"][m]["annual_twr_pct"]) if qualified else None
    diagnostic_beats=bool(winner and figures["diagnostic"][winner]["annual_twr_pct"]>figures["diagnostic"]["VOO DCA"]["annual_twr_pct"])
    doc={
      "generated_utc":pd.Timestamp.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
      "last_complete_market_day":str(df.index[-1].date()),
      "estimated_next_business_day":next_day,
      "research_only":True,"approved_for_live_trading":False,
      "strategy_family":"Cross-sectional large-cap equity momentum and trend/risk controls",
      "selection_bias":"SEVERE: fixed hindsight-selected surviving stocks. Includes winners and excludes delisted firms; backtest alpha NOT trustworthy.",
      "time_periods":{"development":"2013–2018","validation":"2019–2022 (retrospective)","diagnostic":"2023–latest (already observed)"},
      "universe":STOCKS,"model_names":NAMES,
      "selection_from_validation":winner,"diagnostic_outperformed_voo":diagnostic_beats,
      "metrics":figures,"next_session_research_targets":next_targets,
      "paper_action_changes":decisions,
      "assumptions":{"initial_usd":INITIAL,"monthly_contribution_usd":CONTRIBUTION,
        "cost_per_side_bps":10,"currency":"USD","cash_proxy":"SHY",
        "fills":"first regular-session open of each month; signals use previous close only",
        "limits":"No shorting, leverage or margin; FX/taxes/spread additional; adjusted historical prices"},
      "papers":[
        {"title":"Jegadeesh and Titman (1993) cross-sectional momentum","url":"https://doi.org/10.1111/j.1540-6261.1993.tb04702.x"},
        {"title":"Daniel and Moskowitz (2016) Momentum crashes","url":"https://www.nber.org/papers/w20439"},
      ]}
    Path("research").mkdir(exist_ok=True,parents=True)
    Path("site").mkdir(exist_ok=True)
    Path("research/stocks_v1.json").write_text(json.dumps(doc,indent=2)+"\n",encoding="utf-8")
    doc_html=json.dumps(doc,separators=(",",":"),ensure_ascii=True).replace("<","\\u003c")
    template=Path("research/stock_template.html").read_text(encoding="utf-8")
    Path("site/stocks.html").write_text(template.replace("/*RESEARCH_DATA*/",doc_html),encoding="utf-8")
    lines=["# SignalDesk Individual-Stock Opportunity Research",
           f"Last completed market session: {doc['last_complete_market_day']}",
           "**RESEARCH ONLY — NEVER A LIVE BUY/SELL INSTRUCTION.**","",
           "**IMPORTANT**: Fixed surviving stock universe creates material survivorship bias; apparent outperformance is not validated.","",
           "Chosen validation candidate: "+str(winner),
           "Diagnostic annual return exceeds VOO: "+str(diagnostic_beats),"",
           "| Model | 2019–22 return % | 2023+ return % | 2023+ drawdown % | 2023+ beta | 2023+ orders |",
           "|---|---:|---:|---:|---:|---:|"]
    for m in NAMES:
        a=figures["validation"][m];b=figures["diagnostic"][m]
        lines.append(f"| {m} | {a['annual_twr_pct']:.2f} | {b['annual_twr_pct']:.2f} | {b['worst_drawdown_pct']:.2f} | {b['beta_to_voo']:.2f} | {b['orders']} |")
    lines+=["","## Indicative paper positions for the next session",""]
    for m in NAMES:
        lines.append("- "+m+": "+", ".join(f"{t} {100*v:.0f}%" for t,v in next_targets[m].items()))
    lines+=["","A currently successful backtest cannot certify a strategy; observe predictions with future data before considering real-money use."]
    Path("research/stocks_v1.md").write_text("\n".join(lines)+"\n",encoding="utf-8")
    home=Path("site/index.html")
    if home.exists():
        h=home.read_text(encoding="utf-8")
        if 'href="stocks.html"' not in h:
            h=h.replace("</main></html>",'<p><a href="stocks.html" style="color:#93c9ff">Open Stock Opportunity Research →</a></p></main></html>')
            home.write_text(h,encoding="utf-8")
    print("Stock research generated",doc["last_complete_market_day"],"candidate",winner,"diagnostic pass",diagnostic_beats)

if __name__=="__main__":
    generate()
