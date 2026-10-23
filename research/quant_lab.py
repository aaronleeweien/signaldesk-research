"""SignalDesk Quant Lab v3 — transparent research only. No orders or live trading authorization."""
from pathlib import Path
import json, math, html
import numpy as np
import pandas as pd
import yfinance as yf

SECTORS=("XLK","XLF","XLE","XLI","XLV","XLP","XLU","XLY","XLB")
ASSETS=("VOO","QQQ","SHY","IAU")+SECTORS
MODEL_NAMES=("VOO DCA","QQQ DCA","Sector Top 2","Core + Sector","Sector Risk Weighted","VOO Volatility Target","VOO Pullback")
COST=.001
START_USD=2000.
MONTHLY_USD=100.
PERIODS={"development":("2013-01-02","2018-12-31"),
         "validation":("2019-01-02","2022-12-30"),
         "diagnostic":("2023-01-03",None)}

def history():
    tables={}
    for ticker in ASSETS:
        df=yf.download(ticker,start="2010-09-01",auto_adjust=True,
                       multi_level_index=False,progress=False,threads=False)
        if df.empty or not {"Open","Close"}.issubset(df.columns):
            raise ValueError(f"Missing historical data: {ticker}")
        for field in ("Open","Close"):
            tables[(ticker,field)]=df[field]
    data=pd.concat(tables,axis=1).dropna().sort_index()
    data.index=pd.DatetimeIndex(data.index).tz_localize(None)
    eastern=pd.Timestamp.now(tz="America/New_York")
    if data.index[-1].date()==eastern.date() and (eastern.hour,eastern.minute)<(16,30):
        data=data.iloc[:-1]
    if len(data)<3000 or data.index[-1]<pd.Timestamp.now(tz="UTC").tz_localize(None)-pd.Timedelta(days=8):
        raise ValueError("Missing or stale market history")
    if data.index.has_duplicates or (data<=0).any().any():
        raise ValueError("Invalid or duplicate market prices")
    return data

def rank_sectors(close,i):
    if i<260:return [],{}
    scores={}
    for ticker in SECTORS:
        p=close[ticker].iloc[:i+1]
        six=p.iloc[-1]/p.iloc[-127]-1
        twelve_minus_one=p.iloc[-22]/p.iloc[-253]-1
        sma200=p.iloc[-200:].mean()
        score=.6*six+.4*twelve_minus_one
        if p.iloc[-1]>sma200 and six>0 and score>0:
            scores[ticker]=float(score)
    chosen=sorted(scores,key=scores.get,reverse=True)
    return chosen,scores

def weights(data):
    """Decisions for session i use prices only through close of session i-1."""
    ix=data.index
    close=data.xs("Close",level=1,axis=1)
    out={m:[] for m in MODEL_NAMES}
    months=None
    sector_1={"SHY":1.};sector_2={"SHY":1.};sector_risk={"SHY":1.}
    defensive={"VOO":.5,"SHY":.5}
    vol_weights={"VOO":1.}
    pullback=False;pullback_days=0
    last_info={}
    for i,day in enumerate(ix):
        month=day.to_period("M")
        is_new=months is None or month!=months
        if is_new:
            if i<260:
                sector_1={"SHY":1.};sector_2={"SHY":1.};sector_risk={"SHY":1.}
                defensive={"VOO":.5,"SHY":.5}
            else:
                eligible,scores=rank_sectors(close,i-1)
                leader=eligible[0] if eligible else None
                sector_1={leader:1.} if leader else {"SHY":1.}
                if len(eligible)>=2:sector_2={eligible[0]:.5,eligible[1]:.5}
                elif len(eligible)==1:sector_2={eligible[0]:.5,"SHY":.5}
                else:sector_2={"SHY":1.}
                defensive={"VOO":.5,leader:.5} if leader else {"VOO":.5,"SHY":.5}
                pick=eligible[:2]
                if len(pick)==2:
                    vol={}
                    for asset in pick:
                        daily=close[asset].pct_change().iloc[i-22:i-1].dropna()
                        vol[asset]=max(float(daily.std()*math.sqrt(252)),.02)
                    inverse={a:1/vol[a] for a in pick}
                    scale=sum(inverse.values())
                    a_weight=min(.65,inverse[pick[0]]/scale)
                    sector_risk={pick[0]:a_weight,pick[1]:1-a_weight}
                else:
                    sector_risk=sector_2.copy()
            if i>=40:
                returns=close.VOO.pct_change().iloc[i-22:i-1].dropna()
                vol=float(returns.std()*math.sqrt(252))
                invest=max(0.,min(1.,.12/max(vol,.025)))
                vol_weights={"VOO":invest,"SHY":1-invest} if invest<.999 else {"VOO":1.}
            else:
                vol_weights={"VOO":1.}
            months=month
        if i>=205:
            p=close.VOO.iloc[:i]
            # RSI2 computed from the two most recent completed sessions.
            diffs=p.diff().iloc[-2:]
            gains=float(diffs.clip(lower=0).mean())
            losses=float((-diffs.clip(upper=0)).mean())
            rsi=100*gains/(gains+losses) if gains+losses>0 else 50.
            trend=float(p.iloc[-1])>float(p.iloc[-200:].mean())
            if pullback:
                if rsi>70 or pullback_days>=5:
                    pullback=False;pullback_days=0
                else:pullback_days+=1
            elif trend and rsi<15:
                pullback=True;pullback_days=1
        else:rsi=None
        pull_weights={"VOO":1.} if pullback else {"VOO":.6,"SHY":.4}
        selected={
          "VOO DCA":{"VOO":1.},
          "QQQ DCA":{"QQQ":1.},
          "Sector Top 2":sector_2.copy(),
          "Core + Sector":defensive.copy(),
          "Sector Risk Weighted":sector_risk.copy(),
          "VOO Volatility Target":vol_weights.copy(),
          "VOO Pullback":pull_weights}
        for key in MODEL_NAMES:out[key].append(selected[key])
        if i==len(ix)-1:
            candidates,scores=rank_sectors(close,i)
            recent=close.VOO
            last_info={
             "voo_close":round(float(recent.iloc[-1]),2),
             "voo_200day_sma":round(float(recent.iloc[-200:].mean()),2),
             "top_sectors":[{"symbol":v,"score_pct":round(scores[v]*100,2)} for v in candidates[:6]],
             "rsi2":round(rsi,1) if rsi is not None else None,
             "voo_21day_vol_pct":round(float(recent.pct_change().iloc[-21:].std()*math.sqrt(252)*100),2),
             "model_target_at_last_session":selected}
    return out,last_info

def simulate(data,plans,begin,finish,fee=COST):
    ix=data.index
    mask=(ix>=pd.Timestamp(begin)) & (ix<=pd.Timestamp(finish))
    selected=np.flatnonzero(mask)
    if len(selected)<150:raise ValueError("Evaluation period too short")
    shares={asset:0. for asset in ASSETS}
    cash=START_USD;invested=START_USD;prev_nav=START_USD
    old_month=None;prior_weights=None
    cost_total=0.;norders=0
    daily_returns=[];values=[];position_log=[]
    for j in selected:
        today=ix[j];period=today.to_period("M")
        contribution=0.
        if old_month is not None and old_month!=period:
            cash+=MONTHLY_USD;invested+=MONTHLY_USD;contribution=MONTHLY_USD
        target=plans[j]
        if old_month is None or old_month!=period or target!=prior_weights:
            open_prices={x:float(data.iloc[j][x,"Open"]) for x in ASSETS}
            at_open=cash+sum(shares[x]*open_prices[x] for x in ASSETS)
            dollar_targets={x:at_open*target.get(x,0.) for x in ASSETS}
            # Sell first, then buy; cannot leverage.
            for x in ASSETS:
                excess=max(0.,shares[x]*open_prices[x]-dollar_targets[x])
                if excess>.01:
                    units=min(shares[x],excess/open_prices[x])
                    gross=units*open_prices[x];paid=gross*fee
                    shares[x]-=units;cash+=gross-paid;norders+=1;cost_total+=paid
            for x in ASSETS:
                shortage=max(0.,dollar_targets[x]-shares[x]*open_prices[x])
                amount=min(shortage,cash/(1+fee))
                if amount>.01:
                    paid=amount*fee
                    shares[x]+=amount/open_prices[x];cash-=amount+paid
                    norders+=1;cost_total+=paid
        nav=cash+sum(shares[x]*float(data.iloc[j][x,"Close"]) for x in ASSETS)
        if cash<-.02 or nav<=0:raise AssertionError("Invalid position accounting")
        daily_returns.append(nav/(prev_nav+contribution)-1.)
        values.append(nav)
        prev_nav=nav;old_month=period;prior_weights=target.copy()
        position_log.append(target)
    rets=np.asarray(daily_returns)
    path=np.cumprod(1+rets)
    peak=np.maximum.accumulate(np.r_[1.,path])[1:]
    max_drawdown=float((path/peak-1).min())*100.
    yrs=(ix[selected[-1]]-ix[selected[0]]).days/365.25
    ann=(path[-1]**(1/yrs)-1)*100
    annualvol=float(np.std(rets,ddof=1)*math.sqrt(252)*100)
    sharpe=float((np.mean(rets)/np.std(rets,ddof=1))*math.sqrt(252)) if np.std(rets,ddof=1)>0 else 0.
    by_year={}
    for year in sorted(set(ix[selected].year)):
        yr=rets[ix[selected].year==year]
        by_year[str(year)]=round((np.prod(1+yr)-1)*100,2)
    curve_ix=np.unique(np.linspace(0,len(path)-1,min(280,len(path))).astype(int))
    return {"start":str(ix[selected[0]].date()),"end":str(ix[selected[-1]].date()),
      "annual_return_pct":round(float(ann),2),"max_drawdown_pct":round(max_drawdown,2),
      "volatility_pct":round(annualvol,2),"sharpe_zero_cash":round(sharpe,2),
      "final_usd":round(nav,2),"contributed_usd":round(invested,2),
      "orders":norders,"fees_usd":round(cost_total,2),
      "year_returns_pct":by_year,
      "curve":{"dates":[str(ix[selected[i]].date()) for i in curve_ix],
               "values":[round(float(path[i]),4) for i in curve_ix]}}

def strip_curves(info):
    return {a:b for a,b in info.items() if a!="curve"}

def create():
    data=history()
    planned,indicators=weights(data)
    tests={}
    for period,(a,b) in PERIODS.items():
        last=b or str(data.index[-1].date())
        tests[period]={m:simulate(data,planned[m],a,last) for m in MODEL_NAMES}
    # Rule selection uses the 2019–2022 validation period only.
    baseline=tests["validation"]["VOO DCA"]
    contenders=list(MODEL_NAMES[2:])
    eligible=[x for x in contenders if tests["validation"][x]["annual_return_pct"]>baseline["annual_return_pct"]]
    pick=max(eligible,key=lambda x:tests["validation"][x]["annual_return_pct"]) if eligible else None
    audit=tests["diagnostic"]
    def better(model,period):
        return (tests[period][model]["annual_return_pct"]>tests[period]["VOO DCA"]["annual_return_pct"])
    audit_pass=bool(pick and better(pick,"diagnostic"))
    risk_candidates=sorted(contenders,key=lambda m:(tests["diagnostic"][m]["max_drawdown_pct"],-tests["diagnostic"][m]["annual_return_pct"]),reverse=True)
    next_targets={m:planned[m][-1] for m in MODEL_NAMES}
    fee_sensitivity={}
    if pick:
        start=PERIODS["diagnostic"][0];end=str(data.index[-1].date())
        for amount in [0.,.001,.003]:
            one=simulate(data,planned[pick],start,end,fee=amount)
            base=simulate(data,planned["VOO DCA"],start,end,fee=amount)
            fee_sensitivity[str(int(amount*10000))]={
                "model_return_pct":one["annual_return_pct"],"dca_return_pct":base["annual_return_pct"],
                "final_difference_usd":round(one["final_usd"]-base["final_usd"],2)}
    result={
        "generated_utc":pd.Timestamp.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
        "last_complete_market_day":str(data.index[-1].date()),
        "mode":"RESEARCH ONLY — NEVER AUTOMATED ORDERS",
        "research_goal":"Seek a repeatable, net-of-cost strategy that beats VOO without intolerable drawdowns.",
        "all_models":MODEL_NAMES,
        "experimental_areas":["Sector relative momentum","Core + sector allocation","Inverse-volatility sector sizing",
          "VOO volatility targeting","VOO short-term mean reversion"],
        "window_warnings":[
          "2013–2018 is retrospective development, 2019–2022 is retrospective validation.",
          "2023–present has already been viewed by the user and is NOT a genuinely untouched future test.",
          "Signal selection uses only the 2019–2022 scores; 2023+ does not select the candidate.",
          "Only future dated prospective paper signals can provide newly unseen evidence."],
        "settings":{"base_cost_bps":10,"initial_usd":START_USD,
          "new_month_contribution_usd":MONTHLY_USD,
          "cash_fallback":"SHY short Treasury ETF, not idle cash",
          "fractional_units":True,"investment_universe":ASSETS,
          "data":"Yahoo Finance yfinance, adjusted daily open/close, incomplete sessions excluded",
          "execution":"Signals from previous day's close, hypothetical fills at next session open; FX/taxes/gap effects not fully included"},
        "metrics":tests,"indicators":indicators,"current_research_allocations":next_targets,
        "validation_candidate":pick,"historical_audit_beats_voo":audit_pass,
        "model_approved_for_trading":False,
        "cost_sensitivity_bps":fee_sensitivity,
        "research_risk_shortlist":risk_candidates}
    Path("research").mkdir(exist_ok=True)
    Path("site").mkdir(exist_ok=True)
    Path("research/lab_v3.json").write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    small={k:v for k,v in result.items() if k!="metrics"}
    small["metrics"]={period:{m:strip_curves(info) for m,info in table.items()} for period,table in tests.items()}
    Path("site/lab_v3.json").write_text(json.dumps(small,indent=2)+"\n",encoding="utf-8")
    Path("research/lab_v3.md").write_text(build_markdown(result),encoding="utf-8")
    template=Path("research/lab_template.html").read_text(encoding="utf-8")
    safe=json.dumps(result,separators=(",",":"),ensure_ascii=True).replace("<","\\u003c")
    page=template.replace("/*DATA_INJECTION*/",safe)
    Path("site/lab.html").write_text(page,encoding="utf-8")
    main=Path("site/index.html")
    if main.exists():
        content=main.read_text(encoding="utf-8")
        if 'href="lab.html"' not in content:
            content=content.replace("</main></html>",'<p style="margin:24px 0"><a href="lab.html" style="color:#93c9ff">Open Quant Lab V3: strategy research dashboard →</a></p></main></html>')
            main.write_text(content,encoding="utf-8")
    print("Quant Lab v3 created",result["last_complete_market_day"],"candidate",pick,"audit",audit_pass)

def build_markdown(r):
    out=["# SignalDesk Quant Lab V3",f"Updated: {r['generated_utc']}",
      f"Latest complete trading session: {r['last_complete_market_day']}",
      "**RESEARCH ONLY — NOT APPROVED FOR REAL MONEY TRADING**","",
      "Strategy selected using 2019–2022 only: "+str(r["validation_candidate"]),
      "Historical 2023+ performance beat VOO: "+("YES (still retrospective)" if r["historical_audit_beats_voo"] else "NO"),
      "","## Backtest figures","",
      "| Strategy | Validation annual % | Diagnostic annual % | Diagnostic drawdown % | Diagnostic net end USD | Diagnostic trades |",
      "|---|---:|---:|---:|---:|---:|"]
    for name in MODEL_NAMES:
        val=r["metrics"]["validation"][name];later=r["metrics"]["diagnostic"][name]
        out.append(f"| {name} | {val['annual_return_pct']:.2f} | {later['annual_return_pct']:.2f} | {later['max_drawdown_pct']:.2f} | {later['final_usd']:,.0f} | {later['orders']} |")
    out+=["","## Model holdings (hypothetical research exposures)",""]
    for name,v in r["current_research_allocations"].items():
        out.append("- "+name+": "+", ".join(f"{k} {x:.0%}" for k,x in v.items()))
    out+=["","## Risk and honesty checks",""]
    out+=["- "+s for s in r["window_warnings"]]
    out+=["","These backtests use historic selected ETFs and exclude FX/tax/gap effects. Trading costs are only assumed. Positive historical alpha is not a predictive guarantee.",
      "Source research: Conlon et al. (2023) sector ETFs; Magner & Sanhueza (2026) ETF ranking and exit rules; Faber tactical asset allocation; Bailey et al. backtest overfitting.",""]
    return "\n".join(out)

if __name__=="__main__":
    create()
