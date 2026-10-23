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
    updated=datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    rows="".join("<tr><td>"+html.escape(n)+("</td><td>"+str(development[n]["annual"])+"%</td><td>"+str(holdout[n]["annual"])+"%</td><td>"+str(holdout[n]["drawdown"])+"%</td><td>"+str(holdout[n]["orders"])+"</td></tr>") for n in signals)
    page="""<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>SignalDesk</title>
<style>body{background:#0c1320;color:#edf3fe;font:16px system-ui;margin:0}main{max-width:1100px;margin:auto;padding:30px}h1{font-size:32px}p{line-height:1.6}.muted{color:#a9bbd1}.alert{background:#493823;border:1px solid #a27f4a;color:#ffe3ae;padding:16px;border-radius:12px}.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:12px;margin:22px 0}.card{border:1px solid #344861;background:#142237;border-radius:15px;padding:20px}.value{font-size:28px;font-weight:750;margin-top:9px}.body{background:#142237;border:1px solid #344861;padding:22px;border-radius:15px;margin:18px 0}table{width:100%;border-collapse:collapse;text-align:left;display:block;overflow-x:auto}th,td{border-bottom:1px solid #33445b;padding:13px 16px;white-space:nowrap}a{color:#9dcaff}small{color:#a9bbd1}</style>
<main><h1>SignalDesk <small>VOO research monitor</small></h1>
<div class="alert"><strong>RESEARCH ONLY — NO LIVE TRADING APPROVAL</strong><br>Automatic end-of-day historical analysis, not real-time quotes or personal investment advice.</div>
<p class="muted">Updated: UPDATED · Last market session: LASTDATE · Selected using 2013–2021 data only; independently reviewed on 2022 onward.</p>
<div class="cards"><div class="card"><div class="muted">Latest research target</div><div class="value">TARGET</div><small>Not an order instruction</small></div>
<div class="card"><div class="muted">Model tested</div><div class="value">WINNER</div></div>
<div class="card"><div class="muted">Holdout annual return</div><div class="value">MODELRETURN</div></div>
<div class="card"><div class="muted">DCA annual return</div><div class="value">DCARETURN</div></div></div>
<div class="body"><h2>What does this mean?</h2><p>EXPLANATION</p></div>
<div class="body"><h2>All strategies: results after assumed 0.1% cost per trade</h2>
<table><thead><tr><th>Strategy</th><th>Earlier annual growth</th><th>Later annual growth</th><th>Worst later fall</th><th>Later orders</th></tr></thead><tbody>ROWS</tbody></table>
<p class="muted">All portfolios receive the same USD 2,000 initial amount and USD 100/month deposits. No leverage, shorting, automatic orders or personal holdings.</p></div>
<div class="body"><h2>Limitations</h2><p>This snapshot uses historical dividend-adjusted prices and estimated costs. It omits certain FX/tax/slippage effects. Past performance does not establish a profitable future strategy. Market data relies on an unofficial source and may fail; the scheduled job stops rather than publish invented results.</p></div></main></html>"""
    for a,c in {"UPDATED":updated,"LASTDATE":str(d.index[-1].date()),"TARGET":signal,"WINNER":html.escape(winner),
       "MODELRETURN":f"{w['annual']:.2f}%","DCARETURN":f"{b['annual']:.2f}%","EXPLANATION":html.escape(interpretation),"ROWS":rows}.items():
        page=page.replace(a,c)
    Path("site").mkdir(exist_ok=True);Path("site/index.html").write_text(page,encoding="utf-8")
    print("Generated historical dashboard",str(d.index[-1].date()),"selected",winner,"passed",passed)

if __name__=="__main__":main()
