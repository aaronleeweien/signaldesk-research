"""SignalDesk V4B — Live-history factor ETF strategy due diligence.

A point-in-time implemented momentum ETF avoids the *researcher's* hindsight-selected
surviving-stock list; live ETF performance still carries timing, concentration and factor risks.
No brokerage orders; paper research only.
"""
from pathlib import Path
import json, math
import numpy as np
import pandas as pd
import yfinance as yf
import institutional_v4 as stats

SYMS=("VOO","SPMO","QQQ","MTUM","SHY")
MODEL_NAMES=("VOO DCA","SPMO DCA","QQQ DCA","MTUM DCA","SPMO/VOO 50-50",
             "SPMO-VOO 6M Rotation","SPMO Trend + SHY")
FEE=.001;START=2000.;MONTHLY=100.

def get_data():
    frames={}
    for name in SYMS:
        t=yf.download(name,start="2015-10-09",auto_adjust=True,
                      progress=False,threads=False,multi_level_index=False)
        if t.empty or not {"Open","Close"}.issubset(t):
            raise ValueError("Missing ETF history for "+name)
        for col in ("Open","Close"):
            frames[name,col]=t[col]
    d=pd.concat(frames,axis=1).dropna().sort_index()
    d.index=pd.DatetimeIndex(d.index).tz_localize(None)
    ny=pd.Timestamp.now(tz="America/New_York")
    if d.index[-1].date()==ny.date() and (ny.hour,ny.minute)<(16,30):d=d.iloc[:-1]
    if len(d)<2500 or d.index[-1]<pd.Timestamp.utcnow().tz_localize(None)-pd.Timedelta(days=8):
        raise ValueError("SPMO index-fund price feed is stale/incomplete")
    if d.index.has_duplicates or (d<=0).any().any():raise ValueError("Invalid ETF prices")
    return d

def decisions(data):
    c=data.xs("Close",level=1,axis=1)
    plans={m:[] for m in MODEL_NAMES}
    state={"SPMO-VOO 6M Rotation":{"VOO":1.},"SPMO Trend + SHY":{"SHY":1.}}
    last_month=None
    for j,day in enumerate(data.index):
        month=day.to_period("M")
        if month!=last_month:
            if j>=201:
                # Today's session is not completed: only prices through j-1.
                hist=c.iloc[:j]
                spmo=hist.SPMO
                voo=hist.VOO
                # A predeclared six-month return contest; ties default to VOO.
                spmo_ret=spmo.iloc[-1]/spmo.iloc[-127]-1
                voo_ret=voo.iloc[-1]/voo.iloc[-127]-1
                state["SPMO-VOO 6M Rotation"]={"SPMO":1.} if spmo_ret>voo_ret else {"VOO":1.}
                trend=float(spmo.iloc[-1])>float(spmo.iloc[-200:].mean())
                state["SPMO Trend + SHY"]={"SPMO":1.} if trend else {"SHY":1.}
            last_month=month
        out={
         "VOO DCA":{"VOO":1.},
         "SPMO DCA":{"SPMO":1.},
         "QQQ DCA":{"QQQ":1.},
         "MTUM DCA":{"MTUM":1.},
         "SPMO/VOO 50-50":{"SPMO":.5,"VOO":.5},
         **state
        }
        for name in MODEL_NAMES:plans[name].append(out[name].copy())
    return plans

def simulate(data,plan,from_date,to_date,fee=FEE,detail=False):
    dates=data.index
    ixs=np.flatnonzero((dates>=pd.Timestamp(from_date))&(dates<=pd.Timestamp(to_date)))
    if len(ixs)<100:raise ValueError("Insufficient common-date ETF data")
    op=data.xs("Open",level=1,axis=1).reindex(columns=SYMS).to_numpy(dtype=float)
    cl=data.xs("Close",level=1,axis=1).reindex(columns=SYMS).to_numpy(dtype=float)
    code={s:i for i,s in enumerate(SYMS)}
    shares=np.zeros(len(SYMS))
    cash=START;contributed=START;old_value=START;old_month=None;target_old=None
    traded=0;fees=0.;rets=[];targets=[]
    for j in ixs:
        mon=dates[j].to_period("M")
        topup=0.
        if old_month is not None and mon!=old_month:
            cash+=MONTHLY;contributed+=MONTHLY;topup=MONTHLY
        target=plan[j]
        if old_month is None or mon!=old_month or target_old!=target:
            open_value=cash+np.dot(shares,op[j])
            desired=np.zeros(len(SYMS))
            for k,v in target.items():desired[code[k]]=open_value*v
            owned=shares*op[j]
            sells=np.maximum(0.,owned-desired)
            for k in np.flatnonzero(sells>.01):
                gross=float(min(sells[k],owned[k]));tx_fee=gross*fee
                shares[k]-=gross/op[j,k];cash+=gross-tx_fee;traded+=1;fees+=tx_fee
            owned=shares*op[j]
            buys=np.maximum(0.,desired-owned)
            for k in np.flatnonzero(buys>.01):
                gross=float(min(buys[k],cash/(1+fee)))
                if gross>.01:
                    tx_fee=gross*fee
                    shares[k]+=gross/op[j,k];cash-=gross+tx_fee;traded+=1;fees+=tx_fee
        value=float(cash+np.dot(shares,cl[j]))
        if cash<-.02 or value<=0:raise AssertionError("Invalid simulated holdings")
        rets.append(value/(old_value+topup)-1.)
        old_value=value;old_month=mon;target_old=target.copy();targets.append(target.copy())
    r=np.asarray(rets);growth=np.cumprod(1+r)
    years=(dates[ixs[-1]]-dates[ixs[0]]).days/365.25
    vol=float(np.std(r,ddof=1))*math.sqrt(252)
    market=cl[ixs,code["VOO"]]
    prior=cl[ixs[0]-1,code["VOO"]] if ixs[0]>0 else market[0]
    market_ret=np.diff(np.r_[prior,market])/np.r_[prior,market[:-1]]
    denom=np.var(market_ret,ddof=1)
    beta=np.cov(r,market_ret,ddof=1)[0,1]/denom if denom>0 else 0.
    m={}
    for year in sorted(set(dates[ixs].year)):
        y=r[dates[ixs].year==year]
        m[str(year)]=round(float((np.prod(1+y)-1)*100),2)
    report={
        "start":str(dates[ixs[0]].date()),"end":str(dates[ixs[-1]].date()),
        "annual_twr_pct":round(float((growth[-1]**(1/years)-1)*100),2),
        "max_drawdown_pct":round(float((growth/np.maximum.accumulate(np.r_[1,growth])[1:]-1).min()*100),2),
        "volatility_pct":round(vol*100,2),
        "beta_to_voo":round(float(beta),2),
        "sharpe_zero_rf":round(float((np.mean(r)/np.std(r,ddof=1))*math.sqrt(252)),2) if vol>0 else 0,
        "account_value_usd":round(value,2),"total_deposits_usd":round(contributed,2),
        "orders":traded,"trading_fees_usd":round(fees,2),
        "year_returns_pct":m,"end_target":targets[-1]
    }
    if detail:
        report["daily_dates"]=[str(dates[j].date()) for j in ixs]
        report["daily_returns"]=[float(v) for v in r]
    return report

def prospective(data,plans):
    next_day=data.index[-1]+pd.offsets.BDay(1)
    fake=data.iloc[[-1]].copy()
    fake.index=pd.DatetimeIndex([next_day])
    both=decisions(pd.concat([data,fake]))
    next_target={name:both[name][-1] for name in MODEL_NAMES}
    last_target={name:plans[name][-1] for name in MODEL_NAMES}
    actions={}
    for name in MODEL_NAMES:
        previous=last_target[name];after=next_target[name]
        changes=[]
        for ticker in sorted(set(previous)|set(after)):
            delta=after.get(ticker,0.)-previous.get(ticker,0.)
            changes.append({"symbol":ticker,"target_pct":round(after.get(ticker,0.)*100,2),
                 "change_pct_points":round(delta*100,2),
                 "paper_action":"BUY/INCREASE" if delta>.00001 else
                                "SELL/REDUCE" if delta<-.00001 else "HOLD"})
        actions[name]=changes
    return str(next_day.date()),next_target,actions

def build():
    d=get_data()
    plans=decisions(d)
    latest=str(d.index[-1].date())
    full_start="2016-10-03"  # one-year feature warmup; all comparisons share identical dates
    windows={"full":{"start":full_start,"end":latest},
             "2016_2020":{"start":full_start,"end":"2020-12-31"},
             "2021_2023":{"start":"2021-01-04","end":"2023-12-29"},
             "2024_latest":{"start":"2024-01-02","end":latest}}
    metrics={w:{m:simulate(d,plans[m],period["start"],period["end"]) for m in MODEL_NAMES}
             for w,period in windows.items()}
    details={m:simulate(d,plans[m],full_start,latest,detail=True) for m in MODEL_NAMES}
    mrets={name:stats.monthly_series(value) for name,value in details.items()}
    factor={}
    for model in ["SPMO DCA","SPMO/VOO 50-50","SPMO-VOO 6M Rotation","SPMO Trend + SHY"]:
        factor[model]={
            "vs_VOO":stats.cashflow_regression(mrets[model],mrets["VOO DCA"]),
            "vs_QQQ":stats.cashflow_regression(mrets[model],mrets["QQQ DCA"]),
            "bootstrap_vs_VOO":stats.bootstrap_excess(mrets[model],mrets["VOO DCA"]),
            "bootstrap_vs_QQQ":stats.bootstrap_excess(mrets[model],mrets["QQQ DCA"])}
    tails={name:stats.other_risk(detail) for name,detail in details.items()}
    fees={}
    for cost in [0.,.001,.003]:
        fees[str(int(round(cost*10000)))]={
            model:{p:z for p,z in
                   simulate(d,plans[model],full_start,latest,fee=cost).items() if p in
                   ("annual_twr_pct","account_value_usd","orders","trading_fees_usd")}
            for model in ["VOO DCA","SPMO DCA","QQQ DCA","SPMO-VOO 6M Rotation"]}
    next_date,targets,actions=prospective(d,plans)
    # SPMO fund rebalances constituents internally; investor chooses allocation at monthly review.
    approval={
       "real_ETF_live_history":True,
       "fund_construction_not_hindsight_selected_by_us":True,
       "independent_future_predictive_trading_test":False,
       "guaranteed_to_outperform":False,
       "live_order_approved":False}
    report={
      "generated_utc":pd.Timestamp.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
      "last_market_session":latest,
      "next_estimated_business_day":next_date,
      "investment_hypothesis":"Invest in SPMO, a public index ETF that selects S&P 500 stocks with positive relative momentum and rebalances twice annually; compare against VOO/QQQ and optional tactical overlays.",
      "study_design":"Predeclared common-sample, adjusted-price, next-open monthly deposits; 2016–2020, 2021–2023, 2024 onward segments; no selection of best historical window.",
      "primary_candidate":"SPMO DCA",
      "research_only":True,"buy_sell_signals_not_live_recommendations":True,
      "gross_data_expenses":"ETF ongoing fees are reflected in adjusted market prices; estimated broker execution expenses added separately.",
      "fee_assumptions_bps":10,
      "sponsor_spmo_expense_ratio_pct":0.13,
      "sponsor_reconstitution":"Third Friday March and September, per Invesco product profile",
      "assets":SYMS,"models":MODEL_NAMES,"windows":windows,"metrics":metrics,
      "monthly_factor_analysis":factor,"risk":tails,"fee_sensitivity":fees,
      "next_session_paper_weights":targets,"next_session_paper_actions":actions,
      "evidence_gates":approval,
      "broker_note":"Check whether Syfe actually offers this ETF and estimate SGD/USD conversion and broker fees; never assume it is accessible.",
      "limitations":[
        "Even live ETF history is retrospective to a decision made in 2026. SPMO has not proven future outperformance.",
        "SPMO holds momentum stocks and may become concentrated in industries or firms, and can suffer sudden reversals.",
        "The index methodology, management and holdings can evolve over time; live historical fund returns are used, not a reconstructed 2026 constituent list.",
        "Higher returns versus VOO may reflect equity factor and risk exposures; regression is descriptive, not causal.",
        "Trend and relative rotation overlays are experiments and must beat uncomplicated SPMO DCA after costs.",
        "Dividends are approximated by price adjustment and fractional unit assumptions; broker FX, taxes, spreads and order minimums omitted.",
        "No intraday prices; exit thresholds and month-start trade targets are speculative until the completed market signal is recorded before execution."],
      "sources":[
        {"title":"Invesco SPMO sponsor product page","url":"https://www.invesco.com/us/en/financial-products/etfs/invesco-sp-500-momentum-etf.html"},
        {"title":"Jegadeesh and Titman (1993) momentum","url":"https://doi.org/10.1111/j.1540-6261.1993.tb04702.x"},
        {"title":"Daniel & Moskowitz (2016) momentum crashes","url":"https://doi.org/10.1016/j.jfineco.2015.12.002"},
        {"title":"Bailey et al. (2017) backtest overfitting","url":"https://scholarworks.wmich.edu/math_pubs/42/"}]
    }
    Path("research").mkdir(exist_ok=True)
    Path("site").mkdir(exist_ok=True)
    Path("research/factor_etf.json").write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    Path("research/factor_etf.md").write_text(markdown(report),encoding="utf-8")
    Path("site/factor_etf.json").write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    template=Path("research/factor_template.html").read_text(encoding="utf-8")
    data_js=json.dumps(report,separators=(",",":"),ensure_ascii=True).replace("<","\\u003c")
    Path("site/factor.html").write_text(template.replace("/*FACTOR_DATA*/",data_js),encoding="utf-8")
    home=Path("site/index.html")
    if home.exists():
        h=home.read_text(encoding="utf-8")
        if 'href="factor.html"' not in h:
            h=h.replace("</main></html>",'<p style="margin-top:26px"><a href="factor.html" style="color:#84d3ff">SPMO: Live-history Momentum ETF Evidence and Signals →</a></p></main></html>')
            home.write_text(h,encoding="utf-8")
    print("FACTOR ETF report",latest,"SPMO",metrics["full"]["SPMO DCA"]["annual_twr_pct"],"VOO",metrics["full"]["VOO DCA"]["annual_twr_pct"])

def markdown(r):
    lines=[
     "# SignalDesk — Institutional-Style Implemented Momentum ETF Report",
     "",
     "**Live-history systematic strategy:** SPMO buy-and-hold / monthly accumulation.",
     f"Latest complete US market session: {r['last_market_session']}",
     "**RESEARCH ONLY; NOT A GUARANTEED OR APPROVED LIVE TRADE.**",
     "",
     "## Actual-ETF price backtest on matched market days, 2016–2026",
     "",
     "| Method | Annual return | Worst drawdown | Beta to VOO | Simulated orders | Fees USD |",
     "|---|---:|---:|---:|---:|---:|"]
    for name in MODEL_NAMES:
        a=r["metrics"]["full"][name]
        lines.append(f"| {name} | {a['annual_twr_pct']:.2f}% | {a['max_drawdown_pct']:.2f}% | {a['beta_to_voo']:.2f} | {a['orders']} | {a['trading_fees_usd']:.2f} |")
    lines+=["","## Distinct retrospective windows","",
      "| Model | 2016–2020 annual % | 2021–2023 annual % | 2024–latest annual % |",
      "|---|---:|---:|---:|"]
    for name in MODEL_NAMES:
        x=r["metrics"]
        lines.append(f"| {name} | {x['2016_2020'][name]['annual_twr_pct']} | {x['2021_2023'][name]['annual_twr_pct']} | {x['2024_latest'][name]['annual_twr_pct']} |")
    lines+=["","## Monthly factor-aware risk diagnostics",""]
    for name in ("SPMO DCA","SPMO-VOO 6M Rotation","SPMO Trend + SHY"):
        x=r["monthly_factor_analysis"][name]
        lines.append(f"- {name}, vs VOO: estimated beta {x['vs_VOO'].get('monthly_beta')}, alpha {x['vs_VOO'].get('alpha_annual_pct')}%/year, HAC statistic {x['vs_VOO'].get('alpha_hac_tstat')}, bootstrap 90% annual active-return interval [{x['bootstrap_vs_VOO'].get('90pct_ci_low_pct')}, {x['bootstrap_vs_VOO'].get('90pct_ci_high_pct')}]%.")
    lines+=["","## Model target exposures for estimated next session (PAPER ONLY)",""]
    for name,weights in r["next_session_paper_weights"].items():
        lines.append("- "+name+": "+", ".join(f"{s} {v:.0%}" for s,v in weights.items()))
    lines+=["","## Published sources / caveats",""]
    lines+=["- "+x["title"]+": "+x["url"] for x in r["sources"]]
    lines+=["","**Method and bias:** This uses actual historical ETF prices (not an invented 2016 portfolio of today's winners), with contemporaneously implemented fund history. That limits historical constituent survivorship bias but does not eliminate data-snooping, concentration, changing risk exposures or future uncertainty.",""]
    lines+=["- "+x for x in r["limitations"]]
    return "\n".join(lines)+"\n"

if __name__=="__main__":
    build()
