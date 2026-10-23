"""SignalDesk Institutional Evidence V4: audit-ready retrospective quant research.

No live trading. No implied edge when survivorship / selection bias remain.
Only data known through completed close can inform a next-session paper trade.
"""
from pathlib import Path
import json,math
import numpy as np
import pandas as pd

def safe_float(x):
    return round(float(x),4) if np.isfinite(x) else None

def monthly_series(detail):
    days=pd.to_datetime(detail["daily_dates"])
    ret=pd.Series(detail["daily_returns"],index=days,dtype=float)
    m=(1+ret).groupby(ret.index.to_period("M")).prod()-1
    m.index=m.index.to_timestamp(how="end").normalize()
    return m

def cashflow_regression(model,bench):
    """Monthly beta and annualized alpha, OLS with 3-lag Newey-West HAC."""
    aligned=pd.concat([model,bench],axis=1,join="inner").dropna()
    if len(aligned)<24:return {"months":int(len(aligned)),"alpha_annual_pct":None}
    y=aligned.iloc[:,0].to_numpy(float)
    x=aligned.iloc[:,1].to_numpy(float)
    X=np.column_stack([np.ones(len(x)),x])
    inv=np.linalg.pinv(X.T@X)
    coefficients=inv@X.T@y
    residual=y-X@coefficients
    L=min(3,len(y)-2)
    meat=np.zeros((2,2))
    for t in range(len(y)):
        xt=X[t:t+1].T
        meat+=residual[t]**2*(xt@xt.T)
    for lag in range(1,L+1):
        weighted=(1-lag/(L+1))
        for t in range(lag,len(y)):
            cross=weighted*residual[t]*residual[t-lag]
            meat+=cross*(np.outer(X[t],X[t-lag])+np.outer(X[t-lag],X[t]))
    covariance=inv@meat@inv
    se=math.sqrt(max(0,covariance[0,0]))
    tstat=float(coefficients[0]/se) if se>0 else 0.
    p_approx=float(math.erfc(abs(tstat)/math.sqrt(2.)))
    diff=y-x
    active_vol=float(np.std(diff,ddof=1)*math.sqrt(12))
    return {
        "months":len(y),"alpha_annual_pct":safe_float(coefficients[0]*12*100),
        "monthly_beta":safe_float(coefficients[1]),
        "alpha_normal_approx_p":safe_float(p_approx),
        "alpha_hac_tstat":safe_float(tstat),
        "annual_tracking_error_pct":safe_float(active_vol*100),
        "information_ratio":safe_float(np.mean(diff)*12/active_vol) if active_vol>1e-12 else None,
        "monthly_win_rate_pct":safe_float(100*np.mean(diff>0)),
        "mean_monthly_active_return_pct":safe_float(100*np.mean(diff)),
        "median_monthly_active_return_pct":safe_float(100*np.median(diff)),
        "worst_active_month_pct":safe_float(100*np.min(diff)),
        "best_active_month_pct":safe_float(100*np.max(diff))
    }

def bootstrap_excess(model,bench,seed=4071):
    """3-month circular block bootstrap of monthly arithmetic mean active return.
    Sampling distribution is conditional on observed period; no future guarantee.
    """
    table=pd.concat([model,bench],axis=1,join="inner").dropna()
    diff=(table.iloc[:,0]-table.iloc[:,1]).to_numpy(float)
    n=len(diff)
    if n<12:return {}
    rng=np.random.default_rng(seed)
    samples=2500;block=3
    draw=np.zeros(samples)
    for k in range(samples):
        starts=rng.integers(0,n,size=math.ceil(n/block))
        ind=np.concatenate([(np.arange(start,start+block)%n) for start in starts])[:n]
        draw[k]=float(np.mean(diff[ind])*12*100)
    lo,hi=np.percentile(draw,[5,95])
    return {"bootstrap_method":"circular 3-month blocks, 2500 replicates",
        "annual_active_return_estimate_pct":safe_float(diff.mean()*12*100),
        "90pct_ci_low_pct":safe_float(lo),"90pct_ci_high_pct":safe_float(hi),
        "bootstrap_probability_active_gt_zero":safe_float(np.mean(draw>0)),
        "statistical_edge_90pct":bool(lo>0)}

def other_risk(detail):
    r=np.asarray(detail["daily_returns"],dtype=float)
    q=np.quantile(r,.05)
    yr=252
    equity=np.cumprod(1+r)
    high=np.maximum.accumulate(np.r_[1.,equity])[1:]
    drawdown=equity/high-1
    dates=detail["daily_dates"]
    bottom=int(np.argmin(drawdown))
    peak=int(np.argmax(equity[:bottom+1])) if bottom>0 else 0
    neg=r[r<0]
    downside=np.sqrt(np.mean(np.minimum(r,0)**2))*math.sqrt(yr)
    sortino=(np.mean(r)*yr/downside) if downside>0 else 0.
    months=monthly_series(detail)
    return {"daily_var_95_pct":safe_float(q*100),
        "daily_expected_shortfall_95_pct":safe_float(r[r<=q].mean()*100),
        "sortino_zero_rf":safe_float(sortino),
        "worst_month_pct":safe_float(months.min()*100),
        "best_month_pct":safe_float(months.max()*100),
        "max_drawdown_peak_date":dates[peak],
        "max_drawdown_trough_date":dates[bottom],
        "positive_months_pct":safe_float((months>0).mean()*100),
        "calendar_months":len(months),
        "monthly_series":[{"month":str(k.date())[:7],"ret_pct":safe_float(v*100)} for k,v in months.items()]}

def build(df,plans,stock_report):
    # Models and comparators use identical simulation dates, capital and transaction assumptions.
    import stocks_v1 as s
    start="2019-01-02";last=str(df.index[-1].date())
    comparison=("VOO DCA","QQQ DCA","Static Equal Weight",
                "Top-5 Momentum","Top-5 Trend Filter","Top-5 Defensive")
    detail={name:s.backtest(df,plans[name],start,last,detail=True) for name in comparison}
    monthly={name:monthly_series(d) for name,d in detail.items()}
    risk={name:other_risk(d) for name,d in detail.items()}
    active={}
    for name in comparison[2:]:
        active[name]={
          "versus_voo":cashflow_regression(monthly[name],monthly["VOO DCA"]),
          "versus_qqq":cashflow_regression(monthly[name],monthly["QQQ DCA"]),
          "block_bootstrap_vs_voo":bootstrap_excess(monthly[name],monthly["VOO DCA"]),
          "block_bootstrap_vs_qqq":bootstrap_excess(monthly[name],monthly["QQQ DCA"])}
    # Show objective performance under meaningful trading-cost variations.
    fee_runs={}
    for cost in [0.,.001,.003]:
        fee_runs[str(int(round(cost*10000)))]={
          name:{"2019_latest":{field:result[field] for field in
             ("annual_twr_pct","ending_usd","fees_usd","orders","worst_drawdown_pct")}}
          for name in ["VOO DCA","QQQ DCA","Top-5 Momentum"]
          for result in [s.backtest(df,plans[name],start,last,fee=cost)]}
    # Produce a frozen paper decision sheet based on available completed bar.
    candidate="Top-5 Momentum"
    position=stock_report["next_session_research_targets"][candidate]
    old=stock_report["paper_action_changes"][candidate]
    ranked=s.rank(df.xs("Close",level=1,axis=1),len(df)-1)
    ranking=[
      {"ticker":ticker,"relative_momentum_score_pct":safe_float(score*100),
       "above_200day":is_trending,"six_month_return_pct":safe_float(m6*100),
       "twelve_minus_one_month_return_pct":safe_float(m12*100),
       "in_selected_five":ticker in position}
      for ticker,score,is_trending,m6,m12 in ranked]
    # Evidence gates: no retrospective PBO-clean holdout, fixed survivor universe.
    gates={
      "predeclared_ex_ante_universe":False,
      "includes_historical_delistings":False,
      "risk_adjusted_vs_qqq_robust":bool(active[candidate]["block_bootstrap_vs_qqq"]["statistical_edge_90pct"]),
      "robust_vs_voo_at_30bps":bool(fee_runs["30"][candidate]["2019_latest"]["annual_twr_pct"]>
                                fee_runs["30"]["VOO DCA"]["2019_latest"]["annual_twr_pct"]),
      "independent_future_paper_evidence":False,
      "all_gates_pass":False
    }
    summary={
     "asof_completed_us_session":stock_report["last_complete_market_day"],
     "generated_utc":stock_report["generated_utc"],
     "model":"Top-5 Momentum",
     "research_state":"EXPLORATORY / NOT APPROVED",
     "future_trade_authorized":False,
     "next_month_review":"First US trading day of the next calendar month; verify exchange calendar",
     "candidate_evidence":{
       "validation_2019_2022":{k:stock_report["metrics"]["validation"][k]["annual_twr_pct"] for k in
            ("VOO DCA","QQQ DCA","Top-5 Momentum")},
       "diagnostic_2023_latest":{k:stock_report["metrics"]["diagnostic"][k]["annual_twr_pct"] for k in
            ("VOO DCA","QQQ DCA","Top-5 Momentum")},
       "model_has_survivorship_bias":True,
       "winner_was_selected_from_retrospective_data":True,
       "compared_models":len(comparison),
       "market_regime_risk":"A concentrated long-only model can lose heavily and may underperform in reversals."
     },
     "period_results":{k:{period:{metric:value for metric,value in stock_report["metrics"][period][k].items()
                           if metric not in ("curve","annual_by_year","last_weights")} for period in
                           ("development","validation","diagnostic")}
                           for k in comparison},
     "full_period_2019_latest":{k:{fld:val for fld,val in report.items()
                                  if fld not in ("daily_dates","daily_returns","curve","annual_by_year","last_weights")}
                               for k,report in detail.items()},
     "risk":risk,"factor_and_bootstrap":active,
     "fees_sensitivity":fee_runs,
     "rankings":ranking,
     "next_session_research_targets":stock_report["next_session_research_targets"],
     "next_session_paper_actions":stock_report["paper_action_changes"],
     "selection_gates":gates,
     "limitations":[
       "Severe survivorship/selection bias: thirty companies were picked knowing they survived to 2026.",
       "No delisted stock return history or point-in-time constituent database is included.",
       "Historical 2023–2026 is retrospective and has already informed our research; not unseen confirmation.",
       "Momentum portfolio is concentrated in five individual stocks; market beta can be much larger than one.",
       "Bootstrap uncertainty and Newey-West regression are descriptive and do NOT correct survivor bias or multiple model testing.",
       "Trading fee sensitivity excludes FX conversion, commissions minimums, tax, bid-ask spreads and price gaps.",
       "Market signals use prior completed close, next-session execution estimated at adjusted open, no broker connection.",
       "A future order must be checked against real quotes, exchange calendar, spread, broker lot size, and personal risk limits."
     ],
     "papers":[
      {"name":"Jegadeesh & Titman (1993): equity momentum","url":"https://doi.org/10.1111/j.1540-6261.1993.tb04702.x"},
      {"name":"Daniel & Moskowitz: Momentum crashes","url":"https://www.nber.org/papers/w20439"},
      {"name":"Bailey et al.: Probability of backtest overfitting","url":"https://scholarworks.wmich.edu/math_pubs/42/"}]
    }
    Path("research").mkdir(exist_ok=True)
    Path("site").mkdir(exist_ok=True)
    Path("research/institutional_v4.json").write_text(json.dumps(summary,indent=2)+"\n",encoding="utf-8")
    concise=summary.copy()
    # File includes research-only signals, not personal balances.
    Path("site/institutional_v4.json").write_text(json.dumps(concise,indent=2)+"\n",encoding="utf-8")
    Path("research/institutional_v4.md").write_text(markdown_report(summary),encoding="utf-8")
    tpl=Path("research/institutional_template.html").read_text(encoding="utf-8")
    injected=json.dumps(summary,separators=(",",":"),ensure_ascii=True).replace("<","\\u003c")
    Path("site/institutional.html").write_text(tpl.replace("/*V4_DATA*/",injected),encoding="utf-8")
    home=Path("site/index.html")
    if home.exists():
        content=home.read_text(encoding="utf-8")
        if 'href="institutional.html"' not in content:
            content=content.replace("</main></html>",'<p style="margin-top:22px"><a href="institutional.html" style="color:#96d0ff">Institutional Quant Evidence & Trade Report V4 →</a></p></main></html>')
            home.write_text(content,encoding="utf-8")
    print("Institutional evidence dashboard",summary["asof_completed_us_session"],
          "candidate 2019 to date",detail[candidate]["annual_twr_pct"],
          "VOO",detail["VOO DCA"]["annual_twr_pct"],
          "alpha vs VOO",active[candidate]["versus_voo"]["alpha_annual_pct"])

def markdown_report(s):
    p=s["full_period_2019_latest"]
    a=s["factor_and_bootstrap"]["Top-5 Momentum"]
    f=s["fees_sensitivity"]
    lines=[
     "# SignalDesk Institutional Quant Research Report V4",
     "",
     "## Decision",
     "**EXPLORATORY / NOT APPROVED FOR REAL TRADING.**",
     "Strategy: Top-5 cross-sectional momentum, equal 20% weights, monthly ranking of a fixed survivor-stock list.",
     "Data through: "+s["asof_completed_us_session"],"",
     "## Return and risk evidence: 2019 to latest","",
     "| Model | Annual TWR % | Worst fall % | Daily volatility % | Beta to VOO | Simulated orders | Fees USD |",
     "|---|---:|---:|---:|---:|---:|---:|"]
    for name in ("VOO DCA","QQQ DCA","Top-5 Momentum","Top-5 Trend Filter","Top-5 Defensive","Static Equal Weight"):
        z=p[name]
        lines.append(f"| {name} | {z['annual_twr_pct']:.2f} | {z['worst_drawdown_pct']:.2f} | {z['volatility_pct']:.2f} | {z['beta_to_voo']:.2f} | {z['orders']} | {z['fees_usd']:.2f} |")
    lines+=["","## Statistical evidence: monthly factor-aware diagnostics","",
      "| Test | Estimated annual alpha % | Monthly beta | HAC t-stat | Approx p | Bootstrap 90% annual active-return CI |",
      "|---|---:|---:|---:|---:|---|"]
    for benchmark,label in (("voo","VOO"),("qqq","QQQ")):
        v=a["versus_"+benchmark];b=a["block_bootstrap_vs_"+benchmark]
        lines.append(f"| vs {label} | {v['alpha_annual_pct']} | {v['monthly_beta']} | {v['alpha_hac_tstat']} | {v['alpha_normal_approx_p']} | [{b['90pct_ci_low_pct']}, {b['90pct_ci_high_pct']}]% |")
    lines+=["","HAC uses Newey-West 3-lag standard errors. Approximate p-values use a normal approximation,",
            "bootstrap is a three-month circular block bootstrap over the same retrospective data.",
            "Neither method corrects survivorship, data-snooping or regime selection bias.","",
            "## Cost sensitivity, 2019 to latest","",
            "| Fee per side | Momentum annual % | VOO annual % | QQQ annual % |",
            "|---|---:|---:|---:|"]
    for bps in ("0","10","30"):
        x=f[bps]
        lines.append(f"| {bps} bps | {x['Top-5 Momentum']['2019_latest']['annual_twr_pct']} | {x['VOO DCA']['2019_latest']['annual_twr_pct']} | {x['QQQ DCA']['2019_latest']['annual_twr_pct']} |")
    lines+=["","## Next paper targets, not brokerage instructions",""]
    for ticker,w in s["next_session_research_targets"]["Top-5 Momentum"].items():
        lines.append(f"- {ticker}: {100*w:.0f}%")
    lines+=["","## Evidence approval gates",""]
    for key,val in s["selection_gates"].items():
        lines.append("- "+key.replace("_"," ")+": **"+("PASS" if val else "FAIL") +"**")
    lines+=["","## Important limitations",""]
    lines+=["- "+v for v in s["limitations"]]
    lines+=["","This is a research artifact, not personalized investment advice or a guarantee of profitable trades.",""]
    return "\n".join(lines)

if __name__=="__main__":
    raise SystemExit("This module is run by research/stocks_v1.py, after market data is downloaded.")
