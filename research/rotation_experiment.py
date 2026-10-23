"""Additional historical research only. No order placement or live-trade approval."""
from pathlib import Path
import json
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime
from zoneinfo import ZoneInfo

SYMS=("VOO","QQQ","IWM","IAU","IEF","SHY")
RISK=SYMS[:-1]
EQUITY={"VOO","QQQ","IWM"}
COST=.001

def fetch():
    cols={}
    for ticker in SYMS:
        frame=yf.download(ticker,start="2010-09-01",auto_adjust=True,progress=False,
                          multi_level_index=False,threads=False)
        if frame.empty or not {"Open","Close"}.issubset(frame):
            raise RuntimeError("Market data missing: "+ticker)
        for key in ("Open","Close"):
            cols[ticker,key]=frame[key]
    data=pd.concat(cols,axis=1).dropna()
    data.index=pd.to_datetime(data.index).tz_localize(None)
    ny=datetime.now(ZoneInfo("America/New_York"))
    if data.index[-1].date()==ny.date() and (ny.hour,ny.minute)<(16,30):
        data=data.iloc[:-1]
    if len(data)<3000 or data.index[-1]<pd.Timestamp.utcnow().tz_localize(None)-pd.Timedelta(days=8):
        raise RuntimeError("Incomplete or stale prices")
    return data

def targets(data,cutoff,method):
    if method=="VOO DCA":return {"VOO":1.}
    close=data.loc[:cutoff].xs("Close",axis=1,level=1)
    candidates=[]
    if len(close)<260:return {"SHY":1.}
    for sym in RISK:
        s=close[sym]
        p=s.iloc[-1]
        m3=p/s.iloc[-64]-1
        m6=p/s.iloc[-127]-1
        m12=p/s.iloc[-253]-1
        score=.5*m3+.3*m6+.2*m12
        if m6>0 and score>0 and p>s.iloc[-200:].mean():
            candidates.append((sym,score))
    candidates.sort(key=lambda x:x[1],reverse=True)
    if method=="Top 1":
        return {candidates[0][0]:1.} if candidates else {"SHY":1.}
    if method=="Top 2":
        d={k:.5 for k,v in candidates[:2]}
        if len(d)<2:d["SHY"]=d.get("SHY",0)+.5*(2-len(d))
        return d
    if method=="Diversified":
        eq=next((k for k,v in candidates if k in EQUITY),"SHY")
        other=next((k for k,v in candidates if k in {"IAU","IEF"}),"SHY")
        out={}
        for k in (eq,other):out[k]=out.get(k,0)+.5
        return out
    raise ValueError(method)

def simulate(data,method,begin,finish):
    sub=data.loc[begin:finish]
    holdings={k:0. for k in SYMS}
    cash=2000.;deposited=2000.;prev_value=2000.
    last_month=None;trades=0;costs=0.;growth=1.;curve=[]
    latest={}
    for day,row in sub.iterrows():
        month=day.to_period("M")
        contribution=0.
        if last_month is not None and month!=last_month:
            contribution=100.;cash+=contribution;deposited+=contribution
        if month!=last_month:
            prior=data.index[data.index<day]
            latest=targets(data,prior[-1],method)
            opening={k:float(row[k,"Open"]) for k in SYMS}
            open_value=cash+sum(holdings[k]*opening[k] for k in SYMS)
            desired={k:open_value*latest.get(k,0)/(1+COST) for k in SYMS}
            for k in SYMS:
                sell=max(0.,holdings[k]*opening[k]-desired[k])
                if sell>.01:
                    units=sell/opening[k];fee=sell*COST
                    holdings[k]-=units;cash+=sell-fee;trades+=1;costs+=fee
            for k in SYMS:
                buy=max(0.,desired[k]-holdings[k]*opening[k])
                buy=min(buy,cash/(1+COST))
                if buy>.01:
                    fee=buy*COST
                    holdings[k]+=buy/opening[k];cash-=buy+fee
                    trades+=1;costs+=fee
        value=cash+sum(holdings[k]*float(row[k,"Close"]) for k in SYMS)
        growth*=value/(prev_value+contribution)
        curve.append(growth)
        prev_value=value;last_month=month
    arr=np.array(curve)
    years=(sub.index[-1]-sub.index[0]).days/365.25
    return {"annual_twr_pct":round((growth**(1/years)-1)*100,2),
      "end_usd":round(prev_value,2),
      "worst_decline_pct":round(float((arr/np.maximum.accumulate(arr)-1).min())*100,2),
      "orders":trades,"fees_usd":round(costs,2),
      "contributed_usd":round(deposited,2),
      "research_weights":latest}

def main():
    data=fetch()
    methods=("VOO DCA","Top 1","Top 2","Diversified")
    early={k:simulate(data,k,"2013-01-02","2021-12-31") for k in methods}
    later={k:simulate(data,k,"2022-01-03",str(data.index[-1].date())) for k in methods}
    report={"last_complete_session":str(data.index[-1].date()),
     "description":"3/6/12-month momentum, 200-day trend filter, monthly next-open rebalancing, one/two/diversified ETFs",
     "warning":"2022 onward has already been seen in VOO research; retrospective only, NOT independently unseen evidence.",
     "research_only":True,"approved_to_trade":False,"2013_2021":early,"2022_onward":later}
    Path("research").mkdir(exist_ok=True)
    Path("research/rotation_results.json").write_text(json.dumps(report,indent=2)+"\n")
    lines=["# SignalDesk ETF Rotation — Research Only","",
      "**This is NOT a validated or live-trading signal.**","",
      "Last completed session: "+report["last_complete_session"],"",
      report["description"],"",report["warning"],"",
      "| Model | 2013–21 annual return | 2022+ annual return | 2022+ worst decline | 2022+ end value | 2022+ trading costs |",
      "|---|---:|---:|---:|---:|---:|"]
    for k in methods:
        a,b=early[k],later[k]
        lines.append(f"| {k} | {a['annual_twr_pct']}% | {b['annual_twr_pct']}% | {b['worst_decline_pct']}% | USD {b['end_usd']:,.0f} | USD {b['fees_usd']:,.0f} |")
    lines+=["","## Model allocations (research only)",""]
    for k in methods[1:]:
        lines.append("- "+k+": "+", ".join(f"{sym} {weight:.0%}" for sym,weight in later[k]["research_weights"].items()))
    lines+=["","## Assumptions","",
            "Initial USD 2,000; USD 100 at each new calendar month; ETFs VOO, QQQ, IWM, IAU, IEF, SHY; fractional units;",
            "0.1% fee per buy or sell; adjusted prices for dividends; next month's first session opening-price fills.",
            "Returns exclude certain FX, tax and spread costs. Historical ETF selection bias possible.",""]
    Path("research/rotation_results.md").write_text("\n".join(lines))
    Path("site").mkdir(exist_ok=True)
    rows="".join(f"<tr><td>{k}</td><td>{early[k]['annual_twr_pct']}%</td><td>{later[k]['annual_twr_pct']}%</td><td>{later[k]['worst_decline_pct']}%</td></tr>" for k in methods)
    website='<html><meta name="viewport" content="width=device-width,initial-scale=1"><meta charset="utf-8"><title>SignalDesk Rotation</title><style>body{font:16px system-ui;background:#0c1422;color:#edf3fe;margin:30px auto;max-width:940px;padding:0 15px}a{color:#9bc8ff}table{border-collapse:collapse;width:100%;display:block;overflow:auto}th,td{border-bottom:1px solid #344861;text-align:left;padding:12px;white-space:nowrap}.warn{color:#ffdbac}</style><a href="index.html">← VOO dashboard</a><h1>ETF rotation experiment</h1><p class="warn">Research only — not validated for live orders</p><p>Every month the model ranks ETFs by 3-, 6-, 12-month momentum, filters for positive trends and holds either one, two, or diversified ETFs. Weak signals use short-Treasury ETF SHY.</p><p>2022 onward is retrospective and was already observed, not untouched test data.</p><table><tr><th>Model</th><th>2013–21 annual</th><th>2022+ annual</th><th>2022+ worst decline</th></tr>'+rows+'</table><p>Assumes same contributions for all, adjusted prices, 0.1% trading costs; this is a historical simulation, not a trading recommendation.</p></html>'
    Path("site/rotation.html").write_text(website)
    index=Path("site/index.html")
    if index.exists():
        index.write_text(index.read_text().replace("</main></html>",'<p><a href="rotation.html" style="color:#9bc8ff">Open separate multi-ETF research →</a></p></main></html>'))
    print("Rotation research completed using",report["last_complete_session"])
if __name__=="__main__":
    main()
