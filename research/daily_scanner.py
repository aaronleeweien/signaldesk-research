"""SignalDesk daily momentum scanner and paper portfolio — research only.

- Recalculates after complete US sessions.
- Entry: close > prior 20-session high, above 200-day SMA, positive 63/126-day returns.
- Exit: close < prior 20-session low OR below 200-day SMA OR 63-day return <= 0.
- Max two eligible ETFs, selected by 0.6*63d + 0.4*126d momentum; remainder SHY.
- Signals are computed from completed close and execute hypothetically at the NEXT open.
- Stock breakouts are WATCH ONLY: the fixed modern survivor list is biased in backtests.
No intraday data, broker execution, financial guarantees, or non-public investor data.
"""
from pathlib import Path
from datetime import datetime,date,time,timezone
from zoneinfo import ZoneInfo
import json,csv,html,math,sys
import numpy as np
import pandas as pd
import yfinance as yf

ETF=("VOO","SPMO","QQQ","MTUM","XLK","XLF","XLE","XLI","XLV","XLP","XLU","XLY","XLB")
DEFENSIVE="SHY"
STOCK=("AAPL","MSFT","NVDA","AMZN","GOOGL","IBM","INTC","CSCO","ORCL","QCOM",
"TXN","ADBE","JPM","BAC","WFC","XOM","CVX","JNJ","PFE","MRK",
"KO","PEP","WMT","HD","MCD","CAT","BA","DIS","GE","UNH")
ASSETS=ETF+(DEFENSIVE,)
COST=.001
INITIAL=2000.
MONTHLY=100.
EVENT_CSV=Path("research/daily_events.csv")

def fetch(tickers,required=True):
    """Yahoo adjusted US ETF prices; no signal if required prices stale or missing."""
    raw=yf.download(tickers=list(tickers),start="2015-10-09",progress=False,
       threads=True,group_by="ticker",auto_adjust=True,multi_level_index=True)
    if raw.empty:raise ValueError("No market prices downloaded")
    outputs={}
    for symbol in tickers:
        try:
            f=raw[symbol]
            if "Close" not in f or "Open" not in f or f["Close"].dropna().empty:raise KeyError(symbol)
            outputs[(symbol,"Close")]=f["Close"].astype(float)
            outputs[(symbol,"Open")]=f["Open"].astype(float)
        except (KeyError,TypeError):
            if required:raise ValueError(f"Missing required market feed: {symbol}")
    frame=pd.concat(outputs,axis=1).sort_index()
    frame.index=pd.DatetimeIndex(frame.index).tz_localize(None)
    local=datetime.now(ZoneInfo("America/New_York"))
    if frame.index[-1].date()==local.date() and (local.hour,local.minute)<(16,30):
        frame=frame.iloc[:-1]
    if required:
        frame=frame.dropna()
        if len(frame)<2300 or frame.index[-1] < pd.Timestamp.now(tz="UTC").tz_localize(None)-pd.Timedelta(days=8):
            raise ValueError("Incomplete ETF history or outdated last session: cannot generate alerts")
        if (frame<=0).any().any() or frame.index.has_duplicates:raise ValueError("Invalid market history")
    return frame

def indicators(closes):
    return {
      "sma200":closes.rolling(200,min_periods=200).mean(),
      "high20":closes.shift(1).rolling(20,min_periods=20).max(),
      "low20":closes.shift(1).rolling(20,min_periods=20).min(),
      "r63":closes/closes.shift(63)-1,
      "r126":closes/closes.shift(126)-1
    }

def daily_plan(closes,inds=None):
    if inds is None:inds=indicators(closes)
    targets=[]
    held=[]
    info=[]
    for i,day in enumerate(closes.index):
        if i<200:
            targets.append({DEFENSIVE:1.})
            info.append({"entered":[],"exited":[],"eligible":[]})
            continue
        exited=[]
        for symbol in list(held):
            c=float(closes.iloc[i][symbol])
            if (c<float(inds["low20"].iloc[i][symbol]) or
                c<float(inds["sma200"].iloc[i][symbol]) or
                float(inds["r63"].iloc[i][symbol])<=0):
                held.remove(symbol);exited.append(symbol)
        eligible=[]
        for symbol in ETF:
            px=float(closes.iloc[i][symbol])
            trend=float(inds["sma200"].iloc[i][symbol])
            high=float(inds["high20"].iloc[i][symbol])
            r63=float(inds["r63"].iloc[i][symbol])
            r126=float(inds["r126"].iloc[i][symbol])
            if np.isfinite(trend) and np.isfinite(high) and np.isfinite(r63) and np.isfinite(r126) and (
               px>trend and r63>0 and r126>0 and px>high):
                eligible.append((symbol,.6*r63+.4*r126))
        eligible.sort(key=lambda z:z[1],reverse=True)
        entered=[]
        for symbol,score in eligible:
            if len(held)>=2:break
            if symbol not in held:
                held.append(symbol);entered.append(symbol)
        allocation={s:.5 for s in held}
        if len(held)<2:allocation[DEFENSIVE]=.5*(2-len(held))
        targets.append(allocation)
        info.append({"entered":entered,"exited":exited,
                     "eligible":[{"ticker":sym,"score_pct":round(score*100,2)} for sym,score in eligible[:8]]})
    return targets,info

def backtest(prices,plans,start,end,fee=COST):
    index=prices.index
    selected=np.flatnonzero((index>=pd.Timestamp(start))&(index<=pd.Timestamp(end)))
    if len(selected)<100:raise ValueError("No sample")
    op=prices.xs("Open",level=1,axis=1).reindex(columns=ASSETS).to_numpy(dtype=float)
    cl=prices.xs("Close",level=1,axis=1).reindex(columns=ASSETS).to_numpy(dtype=float)
    pos=np.zeros(len(ASSETS));cash=INITIAL;total=INITIAL;last=INITIAL
    symbols={k:i for i,k in enumerate(ASSETS)}
    lastmonth=None;prior_target=None
    fees=0.;orders=0;returns=[];value_series=[]
    for j in selected:
        if j<1:raise ValueError("Missing prior completed session")
        month=index[j].to_period("M")
        contribution=0.
        if lastmonth is not None and month!=lastmonth:
            contribution=MONTHLY;cash+=MONTHLY;total+=MONTHLY
        target=plans[j-1] # yesterday's completed close, execute at today's open
        if target!=prior_target or contribution:
            startvalue=cash+float(np.dot(pos,op[j]))
            desired=np.zeros(len(ASSETS))
            for ticker,fraction in target.items():desired[symbols[ticker]]=startvalue*fraction
            current=pos*op[j]
            for k in np.flatnonzero(current-desired>.01):
                gross=min(float(current[k]-desired[k]),float(current[k]))
                charge=gross*fee;pos[k]-=gross/op[j,k]
                cash+=gross-charge;fees+=charge;orders+=1
            current=pos*op[j]
            for k in np.flatnonzero(desired-current>.01):
                buy=min(float(desired[k]-current[k]),cash/(1+fee))
                if buy>.01:
                    charge=buy*fee
                    pos[k]+=buy/op[j,k];cash-=buy+charge
                    fees+=charge;orders+=1
        netvalue=cash+float(np.dot(pos,cl[j]))
        if cash<-.02 or netvalue<=0:raise AssertionError("Invalid position or borrowing")
        returns.append(netvalue/(last+contribution)-1.)
        value_series.append(netvalue)
        last=netvalue;lastmonth=month;prior_target=target.copy()
    r=np.asarray(returns,dtype=float);wealth=np.cumprod(1+r)
    years=(index[selected[-1]]-index[selected[0]]).days/365.25
    vol=float(np.std(r,ddof=1))*np.sqrt(252)
    worst=float((wealth/np.maximum.accumulate(np.r_[1.,wealth])[1:]-1).min()*100)
    return {"start":str(index[selected[0]].date()),"end":str(index[selected[-1]].date()),
       "annual_pct":round(float((wealth[-1]**(1/years)-1)*100),2),
       "max_drawdown_pct":round(worst,2),"vol_pct":round(vol*100,2),
       "end_usd":round(netvalue,2),"contributed_usd":round(total,2),
       "orders":orders,"fees_usd":round(fees,2),
       "monthly_year_returns":{str(y):round(float((np.prod(1+r[index[selected].year==y])-1)*100),2) for y in set(index[selected].year)},
       "growth":[round(float(wealth[k]),4) for k in np.unique(np.linspace(0,len(wealth)-1,min(200,len(wealth))).astype(int))]}

def stocks_watch():
    try:
        frame=fetch(STOCK,required=False)
        end=frame.index[-1]
        close=frame.xs("Close",level=1,axis=1)
        pieces=[]
        ix=indicators(close)
        for symbol in STOCK:
            if symbol not in close:continue
            p=close[symbol].dropna()
            if len(p)<230 or end not in p.index:continue
            s=indicators(p)
            if len(p)<202:continue
            recent=p.iloc[-1];prior=p.iloc[-2]
            good=bool(recent>s["sma200"].iloc[-1] and s["r63"].iloc[-1]>0 and s["r126"].iloc[-1]>0 and recent>s["high20"].iloc[-1])
            was_good=bool(prior>s["sma200"].iloc[-2] and s["r63"].iloc[-2]>0 and s["r126"].iloc[-2]>0 and prior>s["high20"].iloc[-2])
            if good and not was_good:
                score=.6*s["r63"].iloc[-1]+.4*s["r126"].iloc[-1]
                pieces.append({"ticker":symbol,"score_pct":round(float(score*100),2),
                  "status":"STOCK MOMENTUM WATCH ONLY — biased historical universe"})
        pieces.sort(key=lambda z:z["score_pct"],reverse=True)
        return pieces,len(close.columns),str(end.date())
    except Exception as e:
        return [],0,"unavailable (stock scan failed)"

def main():
    prices=fetch(ASSETS)
    close=prices.xs("Close",level=1,axis=1)
    signals,trace=daily_plan(close)
    latest=prices.index[-1]
    previous=signals[-2];current=signals[-1]
    e=[]
    for ticker in ETF:
        before=previous.get(ticker,0);after=current.get(ticker,0)
        if before==0 and after>0:
            e.append({"type":"ETF_PAPER_BUY_REVIEW","ticker":ticker,"old_weight":0,"new_weight":after})
        elif before>0 and after==0:
            e.append({"type":"ETF_PAPER_EXIT_REVIEW","ticker":ticker,"old_weight":before,"new_weight":0})
    # Also notify on *new* ETF breakouts that cannot enter the max-two portfolio yet.
    # This keeps the daily scanner sensitive to momentum in ANY tracked ETF,
    # without forcing portfolio trades or reporting continuous trends every day.
    recent=indicators(close)
    def is_breakout(symbol,row):
        v=float(close.iloc[row][symbol])
        t=float(recent["sma200"].iloc[row][symbol])
        h=float(recent["high20"].iloc[row][symbol])
        r1=float(recent["r63"].iloc[row][symbol])
        r2=float(recent["r126"].iloc[row][symbol])
        return all(np.isfinite(x) for x in (v,t,h,r1,r2)) and v>t and v>h and r1>0 and r2>0
    for ticker in ETF:
        if ticker in trace[-1]["entered"]:
            continue
        if is_breakout(ticker,-1) and not is_breakout(ticker,-2):
            moment=.6*float(recent["r63"].iloc[-1][ticker])+.4*float(recent["r126"].iloc[-1][ticker])
            e.append({"type":"ETF_MOMENTUM_WATCH","ticker":ticker,"score_pct":round(moment*100,2)})
    watch,watched,stock_date=stocks_watch()
    # Only include stock scans aligned to the ETF's same completed day.
    if stock_date!=str(latest.date()):watch=[]
    for x in watch:e.append({"type":"STOCK_WATCH_ONLY","ticker":x["ticker"],"score_pct":x["score_pct"]})
    tests={}
    for label,begin,end in [("full","2017-01-03",str(latest.date())),
                            ("2017_2021","2017-01-03","2021-12-31"),
                            ("2022_present","2022-01-03",str(latest.date()))]:
        for name,plan in (("daily_2_etf_momentum",signals),
                          ("VOO_DCA",[{"VOO":1.}]*len(prices)),
                          ("SPMO_DCA",[{"SPMO":1.}]*len(prices)),
                          ("QQQ_DCA",[{"QQQ":1.}]*len(prices))):
            tests.setdefault(label,{})[name]=backtest(prices,plan,begin,end)
    next_day=latest+pd.offsets.BDay(1)
    open_estimate=datetime.combine(date.fromisoformat(str(next_day.date())),time(9,30),tzinfo=ZoneInfo("America/New_York"))
    stamp=datetime.now(timezone.utc)
    on_time=stamp<open_estimate
    # Public repo: this only holds ticker prices, no personal holdings.
    saved=[]
    if EVENT_CSV.exists():
        with EVENT_CSV.open(newline="",encoding="utf-8") as inp:saved=list(csv.DictReader(inp))
    recorded={(z["completed_close"],z["ticker"],z["event_type"]) for z in saved}
    added=[]
    for event in e:
        key=(str(latest.date()),event["ticker"],event["type"])
        if key in recorded:continue
        row={"completed_close":str(latest.date()),"ticker":event["ticker"],
          "event_type":event["type"],"details":json.dumps(event,sort_keys=True),
          "recorded_utc":stamp.strftime("%Y-%m-%d %H:%M UTC"),
          "timing":"BEFORE_NEXT_ESTIMATED_OPEN" if on_time else "LATE_RESEARCH_SNAPSHOT"}
        saved.append(row);added.append(row);recorded.add(key)
    EVENT_CSV.parent.mkdir(exist_ok=True,parents=True)
    with EVENT_CSV.open("w",newline="",encoding="utf-8") as out:
        writer=csv.DictWriter(out,fieldnames=["completed_close","ticker","event_type","details","recorded_utc","timing"])
        writer.writeheader();writer.writerows(saved)
    scanner={
       "generated_utc":stamp.strftime("%Y-%m-%d %H:%M UTC"),
       "latest_completed_us_close":str(latest.date()),
       "estimated_next_business_day":str(next_day.date()),
       "research_only":True,"real_trading_approved":False,
       "scanner_rules":{"entry":"Above 200-day SMA, positive 63/126-day returns, and closes above PRIOR 20-session high",
          "exit":"Below prior 20-session low OR below 200-day SMA OR negative 63-day momentum",
          "selection":"At most two ETFs; rank NEW breakouts by 0.6*(63d return)+0.4*(126d return); remaining allocation SHY",
          "signals":"Calculated on completed daily close, simulated position changes at NEXT session open",
          "fee_per_buy_sell_bps":10},
       "tracked_etfs":ETF,"defensive_etf":DEFENSIVE,"stocks_tracked":watched,
       "stock_universe_warning":"Fixed 30 currently surviving stocks; breakout alerts only, not validated stock-trading recommendations",
       "latest_strategy_weights":current,"previous_strategy_weights":previous,
       "new_events_on_latest_close":e,"events_newly_recorded":len(added),
       "events_notifications_eligible":len(added) if on_time else 0,
       "new_eligible_events":[json.loads(x["details"]) for x in added] if on_time else [],
       "last_session_new_entries":trace[-1]["entered"],
       "last_session_exits":trace[-1]["exited"],
       "current_breakout_rankings":trace[-1]["eligible"],
       "backtests":tests,
       "limits":["2017–2026 and 2022+ results are retrospective, not untouched prospective validation",
                "ETF universe selected from funds existing today; selection and data snooping remain possible",
                "A price breakout is not a reliable profit prediction",
                "Same-day signal is only known AFTER close, next-open fill may differ",
                "FX costs, taxes, spreads and real-life partial executions are excluded",
                "No notifications on reruns for events already written to the immutable research journal",
                "Daily model has not yet been approved for real-money trading"] }
    Path("research/daily_scan_latest.json").write_text(json.dumps(scanner,indent=2)+"\n",encoding="utf-8")
    Path("site").mkdir(exist_ok=True)
    Path("site/daily_scan.json").write_text(json.dumps(scanner,indent=2)+"\n",encoding="utf-8")
    Path("site/daily_events.json").write_text(json.dumps({"events":saved[-300:]},indent=2)+"\n",encoding="utf-8")
    alert={"notify":bool(added and on_time),
      "latest_close":str(latest.date()),"events":[json.loads(x["details"]) for x in added] if on_time else []}
    Path("research/daily_alert_payload.json").write_text(json.dumps(alert,indent=2)+"\n",encoding="utf-8")
    template=Path("research/scanner_template.html").read_text(encoding="utf-8")
    injection=json.dumps(scanner,separators=(",",":"),ensure_ascii=True).replace("<","\\u003c")
    Path("site/scanner.html").write_text(template.replace("/*SCAN_DATA*/",injection),encoding="utf-8")
    home=Path("site/index.html")
    if home.exists():
        page=home.read_text(encoding="utf-8")
        if 'href="scanner.html"' not in page:
            page=page.replace("</main></html>",'<p style="margin-top:25px"><a href="scanner.html" style="color:#80d4ff">Daily Momentum Scanner — Alerts and Paper Signals →</a></p></main></html>')
            home.write_text(page,encoding="utf-8")
    print("DAILY SCAN: completed",str(latest.date()),"new events",len(added),"eligible push",alert["notify"],
          "daily strategy 2022+ return",tests["2022_present"]["daily_2_etf_momentum"]["annual_pct"],
          "VOO",tests["2022_present"]["VOO_DCA"]["annual_pct"])
if __name__=="__main__":main()
