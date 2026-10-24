"""Forward-only paper equity ledger with strictly timestamped PRE-OPEN decisions.

Unlike the historical simulator, this NEVER reconstructs past trades from today's
entire price series. A decision recorded on date T can only be executed when the
next real bar T+1 appears on a later scheduled run. Gaps are marked, not backfilled.
Data and account values are PUBLIC and contain only a hypothetical 2000 USD portfolio.
"""
from pathlib import Path
from datetime import datetime,date,time,timezone
from zoneinfo import ZoneInfo
import json
import numpy as np
import pandas as pd

FILE=Path("research/forward_shadow.json")
NAMES=("Daily Breakout Top2","SPMO SMA200","VOO SMA200",
       "SPMO SMA200 Buffer","VOO DCA","SPMO DCA")
FEE=.001
START_CASH=2000.
MONTHLY=100.

def new_state():
    return {
      "version":"forward_paper_ledger_v1",
      "live_trades_authorized":False,
      "started_utc":datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
      "first_trading_session":None,
      "last_completed_us_close":None,
      "valid_forward_sessions":0,
      "missed_or_invalid_sessions":0,
      "signal_history":[],
      "session_history":[],
      "order_history":[],
      "accounts":{name:{
           "cash_usd":START_CASH,
           "shares":{},
           "nav_usd":START_CASH,
           "deposits_usd":START_CASH,
           "fees_paid_usd":0.,
           "orders":0,
           "last_trade_month":None
           } for name in NAMES}
    }

def pure_execute(account,weights,opens,closes,trade_day,monthly_topup=False):
    """Execute hypothetical next-open allocation, then mark that day's close.
    Fractional units; no shorts; estimated 10-bp turnover fee.
    Does not touch time fields or parent state (easy independent accounting tests).
    """
    out=json.loads(json.dumps(account))
    if monthly_topup:
        out["cash_usd"]+=MONTHLY;out["deposits_usd"]+=MONTHLY
    holdings=out["shares"]
    symbols=set(holdings)|set(weights)
    open_nav=out["cash_usd"]+sum(float(holdings.get(k,0))*opens[k] for k in symbols)
    target={k:open_nav*float(weights.get(k,0)) for k in symbols}
    fills=[]
    for k in sorted(symbols):
        have=float(holdings.get(k,0))*opens[k]
        difference=have-target[k]
        if difference>0.01:
            gross=min(difference,have)
            qty=gross/opens[k]
            holdings[k]=float(holdings.get(k,0))-qty
            charge=gross*FEE
            out["cash_usd"]+=gross-charge
            out["fees_paid_usd"]+=charge
            out["orders"]+=1
            fills.append({"ticker":k,"side":"SELL","quantity":round(qty,8),
                          "price_usd":round(opens[k],6),"notional_usd":round(gross,4),
                          "cost_usd":round(charge,4)})
    for k in sorted(symbols):
        have=float(holdings.get(k,0))*opens[k]
        need=target[k]-have
        if need>0.01:
            gross=min(need,out["cash_usd"]/(1+FEE))
            if gross>0.01:
                qty=gross/opens[k];charge=gross*FEE
                holdings[k]=float(holdings.get(k,0))+qty
                out["cash_usd"]-=gross+charge
                out["fees_paid_usd"]+=charge
                out["orders"]+=1
                fills.append({"ticker":k,"side":"BUY","quantity":round(qty,8),
                              "price_usd":round(opens[k],6),"notional_usd":round(gross,4),
                              "cost_usd":round(charge,4)})
    holdings={k:float(qty) for k,qty in holdings.items() if float(qty)>1e-9}
    out["shares"]=holdings
    out["nav_usd"]=float(out["cash_usd"]+sum(qty*closes[k] for k,qty in holdings.items()))
    out["last_trade_month"]=str(trade_day)[:7]
    if out["cash_usd"] < -.01 or out["nav_usd"]<=0:
        raise AssertionError("Paper order used leverage or negative capital")
    return out,fills

def next_us_business_day(day):
    return str((pd.Timestamp(day)+pd.offsets.BDay(1)).date())

def eligible_for_future(close_date,now):
    estimated=next_us_business_day(close_date)
    expected_open=datetime.combine(date.fromisoformat(estimated),time(9,30),
          tzinfo=ZoneInfo("America/New_York"))
    return now<expected_open,estimated

def build_prices(df,tickers,row):
    return {name:float(df[name,kind].iloc[row]) for name in tickers for kind in ()}

def update(prices,targets,now=None):
    if now is None:now=datetime.now(timezone.utc)
    if FILE.exists():state=json.loads(FILE.read_text(encoding="utf-8"))
    else:state=new_state()
    index=prices.index
    latest=str(index[-1].date())
    old=state.get("last_completed_us_close")
    if old and latest<old:
        raise ValueError("Forward ledger refuses out-of-order market history")
    if old==latest:
        # Immutable-by-session record. Updating the current pending allocation
        # from a later rerun would silently revise the historic prediction.
        return state
    if state.get("signal_history"):
        preceding=state["signal_history"][-1]
        base=preceding["decision_close"]
        later=index[index>pd.Timestamp(base)]
        if len(later)==1 and str(later[0].date())==latest and preceding["before_estimated_next_open"]:
            j=len(index)-1
            closings={t:float(prices[t,"Close"].iloc[j]) for t in prices.columns.get_level_values(0).unique()}
            opening={t:float(prices[t,"Open"].iloc[j]) for t in closings}
            day_record={"session":latest,"orders":[],"accounts":{}}
            for name in NAMES:
                account=state["accounts"][name]
                prev_month=account.get("last_trade_month")
                contribution=bool(prev_month and prev_month!=latest[:7])
                new_account,fills=pure_execute(account,preceding["targets"][name],
                            opening,closings,latest,monthly_topup=contribution)
                state["accounts"][name]=new_account
                day_record["accounts"][name]={
                  "nav_usd":round(new_account["nav_usd"],4),
                  "cash_usd":round(new_account["cash_usd"],4),
                  "deposits_usd":round(new_account["deposits_usd"],4),
                  "total_return_on_deposits_pct":round(
                     (new_account["nav_usd"]/new_account["deposits_usd"]-1)*100,3),
                  "fees_usd":round(new_account["fees_paid_usd"],4),
                  "orders":new_account["orders"]}
                for fill in fills:
                    state["order_history"].append({
                      "executed_market_date":latest,
                      "decision_recorded_utc":preceding["recorded_utc"],
                      "model":name,**fill})
                    day_record["orders"].append({"model":name,**fill})
            state["session_history"].append(day_record)
            state["valid_forward_sessions"]+=1
            if not state["first_trading_session"]:
                state["first_trading_session"]=latest
        else:
            state["missed_or_invalid_sessions"]+=1
            state["session_history"].append({
              "session":latest,"status":"SKIPPED: no valid preceding pre-open signal or market data gap",
              "pending_signal_date":base,"missing_sessions":max(0,len(later)-1)})
    eligible,next_day=eligible_for_future(latest,now)
    snap={
      "decision_close":latest,
      "estimated_next_us_business_day":next_day,
      "recorded_utc":now.strftime("%Y-%m-%d %H:%M:%S UTC"),
      "before_estimated_next_open":bool(eligible),
      "targets":{name:targets[name][-1].copy() for name in NAMES},
      "trading_authorized":False,
      "status":"PROSPECTIVE_PAPER_SIGNAL" if eligible else "LATE_NOT_PROSPECTIVE"
    }
    state["signal_history"].append(snap)
    state["last_completed_us_close"]=latest
    state["signal_history"]=state["signal_history"][-2000:]
    state["session_history"]=state["session_history"][-2000:]
    state["order_history"]=state["order_history"][-5000:]
    FILE.parent.mkdir(exist_ok=True,parents=True)
    FILE.write_text(json.dumps(state,indent=2)+"\n",encoding="utf-8")
    render(state)
    return state

def summary_data(state):
    histories=[h for h in state["session_history"] if "accounts" in h]
    started=state["first_trading_session"]
    accounts={}
    for name,account in state["accounts"].items():
        records=[{"date":e["session"],**e["accounts"][name]} for e in histories]
        if len(records)>=2:
            rets=[]
            for prev,cur in zip(records,records[1:]):
                deposit=cur["deposits_usd"]-prev["deposits_usd"]
                rets.append(cur["nav_usd"]/(prev["nav_usd"]+deposit)-1)
            if rets:
                compounded=np.cumprod(1+np.asarray(rets))
                dd=float((compounded/np.maximum.accumulate(np.r_[1.,compounded])[1:]-1).min()*100)
            else:dd=0.
        else:dd=None
        accounts[name]={
            "nav_usd":round(account["nav_usd"],2),
            "deposits_usd":round(account["deposits_usd"],2),
            "paper_pnl_usd":round(account["nav_usd"]-account["deposits_usd"],2),
            "fees_paid_usd":round(account["fees_paid_usd"],2),
            "orders":account["orders"],
            "max_forward_drawdown_pct":round(dd,2) if dd is not None else None,
            "sessions":[{"date":z["date"],"nav_usd":z["nav_usd"],
                         "deposits_usd":z["deposits_usd"]} for z in records]
        }
    return {
      "simulation_only":True,"no_real_orders":True,
      "last_completed_close":state["last_completed_us_close"],
      "start_market_session":started,
      "prospective_market_sessions":state["valid_forward_sessions"],
      "target_minimum_sessions":63,
      "missing_or_invalid_intervals":state["missed_or_invalid_sessions"],
      "eligible_session_progress_pct":round(min(100,100*state["valid_forward_sessions"]/63),1),
      "pending_snapshot":state["signal_history"][-1] if state["signal_history"] else None,
      "accounts":accounts,
      "last_fills":state["order_history"][-50:],
      "invalid_records":[h for h in state["session_history"][-20:] if "status" in h],
      "assumptions":{
        "initial_account_usd":START_CASH,"monthly_contribution_usd":MONTHLY,
        "side_cost_bps":10,"fractional_shares":True,"execution":"NEXT session's actual reported Open, using targets timestamped BEFORE estimated open",
        "marking":"Close from that completed day (adjusted historical quotes)",
        "market_gap_policy":"Refuse to backfill missing sessions or late predictions",
        "limitations":"Not broker paper fills; Yahoo adjusted Open can be revised for splits/dividends; no real spread, FX, taxes or slippage."
      }
    }

def render(state):
    data=summary_data(state)
    Path("site").mkdir(exist_ok=True)
    Path("site/paper_forward.json").write_text(json.dumps(data,indent=2)+"\n",encoding="utf-8")
    template=Path("research/forward_template.html").read_text(encoding="utf-8")
    injection=json.dumps(data,separators=(",",":"),ensure_ascii=True).replace("<","\\u003c")
    Path("site/paper_forward.html").write_text(template.replace("/*FORWARD_PAPER*/",injection),encoding="utf-8")

if __name__=="__main__":
    raise SystemExit("Paper ledger must be run by scanner after data download")
