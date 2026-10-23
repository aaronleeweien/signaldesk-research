"""SignalDesk: research-only. Never sends brokerage orders."""
from pathlib import Path
import json, datetime, html
import numpy as np
import pandas as pd
import yfinance as yf

START="2013-01-02"; TEST="2022-01-03"; COST=.001
INITIAL=2000.; MONTHLY=100.

def prices():
    x=yf.download("VOO",start="2010-09-01",auto_adjust=True,progress=False,threads=False,multi_level_index=False)
    if x.empty or len(x)<2500 or not {"Open","Close"}.issubset(x.columns):
        raise ValueError("Market data unavailable or incomplete; refusing to publish")
    d=x[["Open","Close"]].dropna().copy()
    d.index=pd.to_datetime(d.index).tz_localize(None)
    # Daily bars may include today's incomplete US session during manual reruns.
    # Never use a partially formed bar as if the regular session had closed.
    new_york_time = pd.Timestamp.now(tz="America/New_York")
    if d.index[-1].date() == new_york_time.date() and (
        new_york_time.hour, new_york_time.minute
    ) < (16, 30):
        d = d.iloc[:-1]
    if (d<=0).any().any() or d.index[-1] < pd.Timestamp.utcnow().tz_localize(None)-pd.Timedelta(days=8):
        raise ValueError("Invalid/stale data; refusing to publish")
    return d

def rules(d):
    p=d.Close
    sma=p.rolling(200,min_periods=200).mean()
    m=p.groupby(p.index.to_period("M")).last()
    ten=(m>m.rolling(10,min_periods=10).mean()).shift(1).astype(float)
    monthly=pd.Series(p.index.to_period("M").map(ten).to_numpy(dtype=float),index=p.index)
    weekly=((p>p.shift(126))&(p>sma)).astype(float).where(sma.notna())
    weekly=weekly.where(p.index.weekday==4).ffill()
    high=p.shift(1).rolling(20).max();low=p.shift(1).rolling(10).min()
    states=[];held=0
    for i in range(len(p)):
        if np.isnan(sma.iloc[i]) or np.isnan(high.iloc[i]) or np.isnan(low.iloc[i]):states.append(np.nan);continue
        if held==0 and p.iloc[i]>high.iloc[i] and p.iloc[i]>sma.iloc[i]:held=1
        if held==1 and (p.iloc[i]<low.iloc[i] or p.iloc[i]<sma.iloc[i]):held=0
        states.append(float(held))
    return {"DCA":pd.Series(1.,index=p.index),
      "200-day trend":(p>sma).astype(float).where(sma.notna()),
      "10-month trend":monthly,
      "6-month momentum":weekly,
      "20-day breakout":pd.Series(states,index=p.index)}

def backtest(d,signal,begin,end):
    # Close signal at t; execution at t+1 open, using adjusted OHLC.
    s=signal.shift(1).reindex(d.index).loc[begin:end]
    sub=d.loc[begin:end]
    if s.isna().any() or len(sub)<200:raise ValueError("Insufficient warm-up or test prices")
    cash=INITIAL;units=0.;total=INITIAL;lastmonth=sub.index[0].month;cost=0.;orders=0
    returns=[];equity=[];dates=[]
    for dt,row in sub.iterrows():
        deposit=MONTHLY if dt.month!=lastmonth else 0.;lastmonth=dt.month;cash+=deposit;total+=deposit
        op=float(row.Open);close=float(row.Close);t=int(s.loc[dt])
        old=(equity[-1] if equity else INITIAL)
        if t and cash>1e-8:
            spent=cash/(1+COST);fee=spent*COST;units+=spent/op;cash=0.;cost+=fee;orders+=1
        elif not t and units>1e-10:
            proceeds=units*op;fee=proceeds*COST;cash+=proceeds-fee;units=0.;cost+=fee;orders+=1
        val=cash+units*close
        returns.append((val-deposit)/old-1);equity.append(val);dates.append(dt)
    growth=np.cumprod(1+np.array(returns));drawdown=growth/np.maximum.accumulate(growth)-1
    years=(dates[-1]-dates[0]).days/365.25
    ann=(growth[-1]**(1/years)-1)*100
    vol=np.std(returns,ddof=1)
    sharpe=(np.mean(returns)/vol*252**.5) if vol>0 else -100
    return {"end":round(equity[-1],2),"deposited":round(total,2),"annual":round(float(ann),2),
       "drawdown":round(float(drawdown.min()*100),2),"sharpe":round(float(sharpe),3),
       "orders":orders,"cost":round(cost,2),"curve":growth.tolist(),"dates":[str(t.date()) for t in dates]}

def backtest_with_cost(d, signal, begin, end, cost):
    """Runs the same model at an alternative per-side cost, without reselecting it."""
    global COST
    old=COST
    try:
        COST=cost
        return backtest(d,signal,begin,end)
    finally:
        COST=old

def main():
    d=prices();signals=rules(d)
    development={n:backtest(d,s,START,"2021-12-31") for n,s in signals.items()}
    holdout={n:backtest(d,s,TEST,str(d.index[-1].date())) for n,s in signals.items()}
    names=[n for n in signals if n!="DCA"]
    # Selection is based on development data alone. Holdout must not change model choice.
    def score(n):
        q=development[n];return q["sharpe"] + .015*q["drawdown"]-.003*q["orders"]
    winner=max(names,key=score)
    w=holdout[winner];b=holdout["DCA"]
    passed=w["annual"]>b["annual"] and w["drawdown"]>=b["drawdown"]-5
    target=signals[winner].dropna().iloc[-1]
    signal="HOLD VOO" if target==1 else "HOLD CASH"
    delta=w["end"]-b["end"]
    interpretation=(f"The chosen model ended USD {abs(delta):,.2f} {'above' if delta>=0 else 'below'} regular VOO investing on the later test period. "
                    f"Its worst percentage fall was {abs(w['drawdown']):.1f}%, versus {abs(b['drawdown']):.1f}% for DCA. "
                    + ("The limited historical hurdle passed; this is STILL NOT a validated live trade." if passed else "The historical hurdle failed; do NOT use this model to replace DCA."))
    # Display the evidence, not just the strategy's current position.
    report_status = "NO STRATEGY QUALIFIED — NO MODEL TRADE" if not passed else "PRELIMINARY HISTORICAL PASS — STILL PAPER ONLY"
    model_target = "100% VOO (research)" if target else "100% CASH (research)"
    cost_rows=[]
    for cost_fraction in [0.0,0.001,0.003]:
        model_result=backtest_with_cost(d,signals[winner],TEST,str(d.index[-1].date()),cost_fraction)
        passive_result=backtest_with_cost(d,signals["DCA"],TEST,str(d.index[-1].date()),cost_fraction)
        gap=model_result["end"]-passive_result["end"]
        cost_rows.append(f"<tr><td>{int(cost_fraction*10000)} bps</td><td>{model_result['annual']:.2f}%</td><td>{passive_result['annual']:.2f}%</td><td>{gap:+,.0f} USD</td></tr>")
    fees_html="".join(cost_rows)
    # SVG of hypothetical time-weighted dollar growth, independent of monthly deposits.
    a=np.array(w["curve"]);base=np.array(b["curve"])
    scale_min=float(min(a.min(),base.min()));scale_max=float(max(a.max(),base.max()))
    scale_span=max(scale_max-scale_min,0.01)
    def line_svg(arr):
        positions=np.unique(np.linspace(0,len(arr)-1,min(220,len(arr))).astype(int))
        return " ".join(f"{10+860*i/max(1,len(arr)-1):.1f},{195-175*(arr[i]-scale_min)/scale_span:.1f}" for i in positions)
    graph=f'<svg role="img" aria-label="Time-weighted growth comparison; blue DCA, amber model" viewBox="0 0 880 210" style="width:100%;height:auto;background:#0b1424;border-radius:10px"><polyline fill="none" stroke="#69c6ff" stroke-width="3" points="{line_svg(base)}"/><polyline fill="none" stroke="#ffc16b" stroke-width="3" points="{line_svg(a)}"/></svg>'
    updated=datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    rows="".join("<tr><td>"+html.escape(n)+("</td><td>"+str(development[n]["annual"])+"%</td><td>"+str(holdout[n]["annual"])+"%</td><td>"+str(holdout[n]["drawdown"])+"%</td><td>"+str(holdout[n]["orders"])+"</td><td>USD "+str(holdout[n]["cost"])+"</td></tr>") for n in signals)
    page="""<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>SignalDesk | VOO Research</title>
<style>*{box-sizing:border-box}body{background:#0c1320;color:#edf3fe;font:15px system-ui,sans-serif;margin:0}main{max-width:1100px;margin:auto;padding:24px 18px 50px}.muted,small{color:#aec1d7}h1{font-size:30px}h2{font-size:19px;margin-top:0}.warning{padding:18px;border:1px solid #c99d60;background:#433421;border-radius:12px;color:#ffdfaa;margin:16px 0}.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px;margin:20px 0}.card,.panel{border:1px solid #344961;background:#152235;border-radius:13px;padding:19px}.value{font-size:26px;font-weight:750;margin:7px 0}.panel{margin:18px 0}p{line-height:1.6}table{border-collapse:collapse;width:100%;display:block;overflow-x:auto}td,th{padding:12px 14px;text-align:left;border-bottom:1px solid #35475e;white-space:nowrap}th{color:#b8cae1}</style>
<main><h1>SignalDesk <small>VOO research monitor</small></h1><div class="warning"><strong>REPORTSTATUS</strong><p>Signals are model positions, not approved trades. Your existing brokerage account is not connected.</p></div>
<p class="muted">Report updated UPDATED · Latest market data LASTDATE · Models selected using 2013–2021 and judged on 2022 onward.</p>
<div class="cards"><div class="card"><small>Latest model position</small><div class="value">TARGET</div><small>Not an order to place</small></div><div class="card"><small>Model selected before holdout</small><div class="value">WINNER</div></div><div class="card"><small>Model annual return, 2022+</small><div class="value">MODELRETURN</div></div><div class="card"><small>VOO DCA annual return, 2022+</small><div class="value">DCARETURN</div></div></div>
<div class="panel"><h2>What do the results mean?</h2><p>EXPLANATION</p><p>Since the model did not outperform the passive benchmark, its current position is not a reason to change your VOO investments.</p></div>
<div class="panel"><h2>Wealth growth over time (independent of deposits)</h2><p class="muted"><span style="color:#69c6ff">● VOO DCA</span> &nbsp; <span style="color:#ffc16b">● Chosen model</span></p>CHART<p class="muted">This shows compounded daily investment returns in the 2022-onward period. It does not include changes to the account balance caused by deposits.</p></div>
<div class="panel"><h2>All strategies compared</h2><table><thead><tr><th>Strategy</th><th>Annual 2013–2021</th><th>Annual 2022+</th><th>Worst 2022+ fall</th><th>2022+ orders</th><th>Estimated trading costs</th></tr></thead><tbody>ROWS</tbody></table><p class="muted">Each strategy starts with 2,000 USD and gets 100 USD monthly. Costs assumed at 10 basis points per buy/sell. No leverage.</p></div>
<div class="panel"><h2>Cost sensitivity</h2><table><thead><tr><th>Trading cost per side</th><th>Model annual</th><th>DCA annual</th><th>Model less DCA (ending USD)</th></tr></thead><tbody>COSTROWS</tbody></table><p class="muted">0 bps = 0%, 10 bps = 0.1%, 30 bps = 0.3% each transaction. Actual brokerage and FX costs may differ.</p></div>
<div class="panel"><h2>Next research milestone</h2><p>Keep normal VOO investing separate from this research. The next step is to save and track future paper-trading signals BEFORE the market moves. We should not repeatedly adjust these four strategies to fit the already-seen 2022-onward results.</p></div>
<div class="panel"><h2>Limitations</h2><p>This is end-of-day research, not streaming prices. Adjusted market prices approximate dividends; idle cash earns 0%; FX costs, taxes, financing and execution differences are not fully modelled. Historical backtesting does not prove future profitability. The market-data feed is unofficial; if it fails, updates should stop rather than show invented figures.</p></div></main></html>"""
    for a,c in {"UPDATED":updated,"LASTDATE":str(d.index[-1].date()),"TARGET":html.escape(model_target),
       "REPORTSTATUS":html.escape(report_status),"WINNER":html.escape(winner),
       "MODELRETURN":f"{w['annual']:.2f}%","DCARETURN":f"{b['annual']:.2f}%",
       "EXPLANATION":html.escape(interpretation),"ROWS":rows,"CHART":graph,"COSTROWS":fees_html}.items():
        page=page.replace(a,c)
    Path("site").mkdir(exist_ok=True);Path("site/index.html").write_text(page,encoding="utf-8")
    # Machine-readable and human-readable snapshots for ChatGPT via connected GitHub.
    # This is public market research only. Never include personal holdings or account data.
    report = {
        "generated_at_utc": updated,
        "last_market_session": str(d.index[-1].date()),
        "research_only": True,
        "approved_for_live_trading": False,
        "selected_strategy": winner,
        "historical_hurdle_passed": bool(passed),
        "current_model_position": "VOO" if target == 1 else "CASH",
        "interpretation": interpretation,
        "assumptions": {
            "initial_usd": INITIAL, "monthly_contribution_usd": MONTHLY,
            "standard_cost_fraction_per_trade": COST, "cash_interest": 0,
            "development_period": "2013-01-02 to 2021-12-31",
            "holdout_period_start": TEST,
        },
        "development": {
            k: {a: v for a,v in q.items() if a not in ("curve","dates")}
            for k,q in development.items()
        },
        "holdout": {
            k: {a: v for a,v in q.items() if a not in ("curve","dates")}
            for k,q in holdout.items()
        },
        "cost_sensitivity": [
            {"cost_bps": int(round(bps*10000)), "model_annual_return_pct": float(m), "dca_annual_return_pct": float(dca), "model_minus_dca_final_usd": float(diff)}
            for bps,m,dca,diff in [
                (
                    float(cost),
                    backtest_with_cost(d, signals[winner], TEST, str(d.index[-1].date()), cost)["annual"],
                    backtest_with_cost(d, signals["DCA"], TEST, str(d.index[-1].date()), cost)["annual"],
                    backtest_with_cost(d, signals[winner], TEST, str(d.index[-1].date()), cost)["end"] -
                    backtest_with_cost(d, signals["DCA"], TEST, str(d.index[-1].date()), cost)["end"]
                ) for cost in (0.0, 0.001, 0.003)
            ]
        ],
    }
    snapshot = json.dumps(report, indent=2, ensure_ascii=False)
    Path("latest_report.json").write_text(snapshot + "\n", encoding="utf-8")
    Path("site/latest_report.json").write_text(snapshot + "\n", encoding="utf-8")
    summary_lines = [
        "# SignalDesk — Latest VOO Research",
        "",
        f"Last market session: **{report['last_market_session']}**",
        f"Updated UTC: **{updated}**",
        "",
        "**RESEARCH ONLY: No strategy has been approved for real-money trading.**",
        "",
        f"Selected strategy: **{winner}**",
        f"Current model exposure: **{report['current_model_position']}** (not an order)",
        f"Passed historical hurdle: **{'Yes (still only research)' if passed else 'No'}**",
        "",
        "## What the numbers mean",
        "",
        interpretation,
        "",
        "## Strategy comparison",
        "",
        "| Strategy | Development annual % | Holdout annual % | Holdout worst fall % | Holdout orders | Trading cost USD |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for name in signals:
        pre,post=development[name],holdout[name]
        summary_lines.append(
            f"| {name} | {pre['annual']:.2f} | {post['annual']:.2f} | {post['drawdown']:.2f} | {post['orders']} | {post['cost']:.2f} |"
        )
    summary_lines.extend([
        "",
        "## Limits",
        "",
        "All strategies assume USD 2,000 initially, USD 100 added monthly, and 0.1% execution costs per trade. "
        "Cash earns no interest. Backtests omit some taxes, foreign exchange expenses and slippage. "
        "Past performance cannot guarantee future gains.",
        "",
        "This file is automatically updated by GitHub Actions after a successful market-data refresh.",
    ])
    Path("latest_report.md").write_text("\n".join(summary_lines) + "\n", encoding="utf-8")
    print("Generated historical dashboard",str(d.index[-1].date()),"selected",winner,"passed",passed)

if __name__=="__main__":main()
