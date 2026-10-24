"""BNF / Takashi Kotegawa-inspired SHORT-TERM MEAN REVERSION study.

Research registration 2026-10-24, NOT a replication of his discretionary
trading and NOT a strategy certified to outperform the S&P 500.

Primary contemporary descriptions transcribed from 2006 Net Money and 2008
ZAKZAK/Weekly Asahi interviews:
 https://kabushiki-blog.com/article/18401857.html
 https://kabushiki-blog.com/article/80415989.html
 https://fxhikakublog.com/bnf-syuhou20081114

One precommitted, simplified US-market ADAPTATION:
* Universe: contemporary liquid US stock screener; not a point-in-time historic
  membership list; cannot unbiasedly backtest historical Japanese BNF trading.
* Context: completed VOO close below its 50-session moving average.
* Entry signal: completed stock close <= 90% of its 25-session SMA (10% below).
  BUY at following market OPEN, once per oversold episode.
* Exit: SELL at next OPEN if prior close >= its SMA25, OR <= 92% of entry
  price, OR after 5 held sessions. No perfect lows or known sell prices.
* Cost: 10bp per side plus 10bp each-way slippage proxy = 20bp each side.
* Compare an unleveraged, mostly-cash DCA-style account with VOO monthly DCA
  on exact same historical dates. Also compare every trade to VOO on equal dates.
* Historical testing already seen, selection on surviving companies,
  no manual intervention, no claim this reproduces BNF or proves an edge.

The person reportedly adapted thresholds by sector, market conditions, order
book and judgment. This experiment does NOT attribute these exact thresholds
or exit conditions to him.
"""
from __future__ import annotations
import math
import numpy as np
import pandas as pd

VERSION="bnf_inspired_mean_reversion_v1_20261024"
SMA=25
MARKET_SMA=50
DISCOUNT=.10
STOP=.08
MAX_DAYS=5
COST=.002
START="2019-06-24"
RECENT="2022-01-03"
INITIAL=2000.
MONTHLY=100.

def signals(stock_close,voo_close):
    s=pd.Series(stock_close,dtype=float)
    b=pd.Series(voo_close,dtype=float)
    avg=s.rolling(SMA,min_periods=SMA).mean()
    market=b.rolling(MARKET_SMA,min_periods=MARKET_SMA).mean()
    discount=s/avg-1
    eligible=(discount<=-DISCOUNT)&(b<market)&s.notna()&b.notna()
    # Record only the first signal of an oversold episode.
    fresh=eligible & ~eligible.shift(1,fill_value=False)
    return fresh.fillna(False).to_numpy(bool),avg.to_numpy(float),discount.to_numpy(float)

def roundtrip_trades(frame,ticker,cost=COST):
    """All executed fills require a previous completed close.
    Last unfinished trade is OMITTED from completed-trade average.
    """
    d=frame.loc[:,[("VOO","Close"),("VOO","Open"),(ticker,"Close"),(ticker,"Open")]].dropna()
    if len(d)<300:return [],None
    dates=d.index
    c=d[ticker,"Close"].to_numpy(float)
    o=d[ticker,"Open"].to_numpy(float)
    bc=d["VOO","Close"].to_numpy(float)
    bo=d["VOO","Open"].to_numpy(float)
    entry,avg,dev=signals(c,bc)
    trades=[];held=False;buy_i=None;buy_px=None
    for i in range(1,len(d)):
        if not held and entry[i-1]:
            held=True;buy_i=i;buy_px=o[i]
        elif held:
            triggers=[]
            if c[i-1]>=avg[i-1]:triggers.append("price recovered to 25-day average")
            if c[i-1]<=buy_px*(1-STOP):triggers.append("8% stop on prior close")
            if (i-1)-buy_i>=MAX_DAYS-1:triggers.append("5-session maximum holding period")
            if triggers:
                net=(o[i]/buy_px)*(1-cost)**2-1
                voo=(bo[i]/bo[buy_i])*(1-cost)**2-1
                trades.append({"buy_date":str(dates[buy_i].date()),
                   "sell_date":str(dates[i].date()),
                   "sessions_held":i-buy_i,
                   "entry_price":round(float(buy_px),4),
                   "exit_price":round(float(o[i]),4),
                   "net_return_pct":round(float(net)*100,3),
                   "same_dates_voo_pct":round(float(voo)*100,3),
                   "relative_to_voo_pp":round(float(net-voo)*100,3),
                   "exit_reason":"; ".join(triggers)})
                held=False
    return trades,{"last_complete_date":str(dates[-1].date()),
       "eligible_now":bool(entry[-1]),
       "price_deviation_pct":round(float(dev[-1])*100,2) if np.isfinite(dev[-1]) else None,
       "last_close_usd":round(float(c[-1]),3),
       "sma25_usd":round(float(avg[-1]),3) if np.isfinite(avg[-1]) else None,
       "last_open_usd":round(float(o[-1]),3),
       "data_rows":len(d),"has_unfinished_position":bool(held)}

def simulate_account(frame,ticker,begin=START,cost=COST):
    """Single stock when the first signal appears; cash between trades.
    Dividends embedded in auto_adjust True bars. Monthly cash deposits continue.
    """
    d=frame.loc[:,[("VOO","Close"),("VOO","Open"),(ticker,"Close"),(ticker,"Open")]].dropna()
    if len(d)<300:return None
    c=d[ticker,"Close"].to_numpy(float);o=d[ticker,"Open"].to_numpy(float)
    v=d["VOO","Close"].to_numpy(float);vo=d["VOO","Open"].to_numpy(float)
    fresh,avg,_=signals(c,v)
    start=max(60,int(np.searchsorted(d.index,np.datetime64(begin))))
    if len(d)-start<120:return None
    cash=INITIAL;shares=0.;entry_px=None;buy_i=None;count=0;fees=0.;deposits=INITIAL
    bv=INITIAL;bs=0.;bfees=0.
    last_month=None;prev=INITIAL;prev_voo=INITIAL;returns=[];bench_returns=[]
    equities=[];values=[]
    for i in range(start,len(d)):
        month=d.index[i].to_period("M")
        topup=MONTHLY if last_month is not None and last_month!=month else 0.
        cash+=topup;bv+=topup;deposits+=topup
        # Passive benchmark invests initial and every monthly top-up at the
        # same opening. Both accounts face the same 20bp one-way fee.
        if i==start or topup:
            notional=bv/(1+cost)
            bs+=notional/vo[i];bv-=notional*(1+cost);bfees+=notional*cost
        if shares>0:
            reasons=(c[i-1]>=avg[i-1] or
                c[i-1]<=entry_px*(1-STOP) or
                (i-1)-buy_i>=MAX_DAYS-1)
            if reasons:
                gross=shares*o[i];charge=gross*cost
                cash+=gross-charge;fees+=charge;shares=0.;entry_px=None;buy_i=None;count+=1
        if shares==0 and fresh[i-1]:
            notional=cash/(1+cost)
            if notional>1:
                shares=notional/o[i];charge=notional*cost
                fees+=charge;cash-=notional+charge;entry_px=o[i];buy_i=i
        nav=cash+shares*c[i];bench=bv+bs*v[i]
        if cash<-.01 or nav<=0 or bench<=0:raise ValueError("Invalid strategy portfolio cash accounting")
        returns.append(nav/(prev+topup)-1)
        bench_returns.append(bench/(prev_voo+topup)-1)
        equities.append(nav);values.append(bench)
        last_month=month;prev=nav;prev_voo=bench
    rr=np.asarray(returns,float);bb=np.asarray(bench_returns,float)
    def annual(x):
        years=(d.index[-1]-d.index[start]).days/365.25
        return round(float((np.prod(1+x)**(1/years)-1)*100),2)
    def drawdown(x):
        wealth=np.cumprod(1+x)
        peaks=np.maximum.accumulate(np.r_[1.,wealth])[1:]
        return round(float(np.min(wealth/peaks-1)*100),2)
    return {"start":str(d.index[start].date()),"end":str(d.index[-1].date()),
        "strategy_annual_twr_pct":annual(rr),
        "voo_annual_twr_pct":annual(bb),
        "annual_advantage_vs_voo_pp":round(annual(rr)-annual(bb),2),
        "strategy_max_dd_pct":drawdown(rr),
        "voo_max_dd_pct":drawdown(bb),
        "strategy_final_account_usd":round(float(equities[-1]),2),
        "voo_final_account_usd":round(float(values[-1]),2),
        "total_deposits_usd":round(deposits,2),
        "completed_sell_orders":count,
        "strategy_fees_usd":round(fees,2),
        "voo_fees_usd":round(bfees,2)}

def analyse(frame,ticker):
    trades,current=roundtrip_trades(frame,ticker)
    if current is None:return None
    account=simulate_account(frame,ticker)
    recent=simulate_account(frame,ticker,RECENT)
    if account is None or recent is None:return None
    recent_trades=[t for t in trades if t["buy_date"]>=RECENT]
    avg=float(np.mean([t["relative_to_voo_pp"] for t in trades])) if trades else None
    positive=(avg is not None and avg>0 and account["annual_advantage_vs_voo_pp"]>0 and
              recent["annual_advantage_vs_voo_pp"]>0)
    return {"ticker":ticker,"latest":current,
       "all_trades_count":len(trades),"recent_trades_count":len(recent_trades),
       "win_rate_pct":round(100*np.mean([t["net_return_pct"]>0 for t in trades]),1) if trades else None,
       "mean_matched_trade_excess_pp":round(avg,2) if avg is not None else None,
       "whole_period":account,"recent_period":recent,
       "historical_only_pass":bool(positive and len(trades)>=20 and len(recent_trades)>=8),
       "new_paper_entry_setup":bool(current["eligible_now"]),
       "recent_completed_trades":trades[-3:],
       "real_money_approved":False,
       "limitations":"Current stock universe was selected in 2026. No historical delisted stocks, intraday limit-order fills, accurate spreads, Japanese security data, or independent forward verification."}

def compare_market(frame,universe,market_date):
    """Returns one fixed-specification research experiment on assets downloaded
    by the existing broad-market scanner. Do not optimize thresholds on outputs.
    """
    output=[];errors=[]
    for ticker in universe:
        if ticker=="VOO":continue
        if (ticker,"Open") not in frame or (ticker,"Close") not in frame:continue
        try:
            x=analyse(frame,ticker)
            if x:output.append(x)
        except (ValueError,KeyError,TypeError) as ex:
            errors.append({"ticker":ticker,"error":type(ex).__name__})
    winners=[x for x in output if x["historical_only_pass"]]
    paper=[x for x in output if x["new_paper_entry_setup"]]
    return {"protocol":VERSION,"market_date":market_date,
        "approach":"BNF-inspired short-term contrarian research, NOT his exact discretionary method",
        "source_interviews":[
          "https://kabushiki-blog.com/article/18401857.html",
          "https://kabushiki-blog.com/article/80415989.html",
          "https://fxhikakublog.com/bnf-syuhou20081114"],
        "rules":{"market_context":"VOO close below 50-day SMA",
          "entry":"Stock close at least 10% below 25-day SMA, first signal of oversold episode, buy next open",
          "exit":"After prior close >= 25-day SMA OR <=92% of entry OR 5 sessions, sell next open",
          "transaction_cost_per_side_pct":COST*100,
          "account":"US$2000 initial and US$100 monthly; idle funds in cash",
          "benchmark":"VOO DCA same dates and trading costs",
          "dataset_bias":"2026 survivor-only US market; never blindly extrapolate backtest"},
        "screened_prices_for_assets":len(output),
        "passing_retrospective_tests":len(winners),
        "new_paper_entry_setups":len(paper),
        "historical_screen_summary":sorted(
          [{"ticker":x["ticker"],"trades":x["all_trades_count"],
            "strategy_annual_pct":x["whole_period"]["strategy_annual_twr_pct"],
            "voo_annual_pct":x["whole_period"]["voo_annual_twr_pct"],
            "annual_excess_pp":x["whole_period"]["annual_advantage_vs_voo_pp"],
            "recent_excess_pp":x["recent_period"]["annual_advantage_vs_voo_pp"],
            "historical_only_pass":x["historical_only_pass"]} for x in output],
            key=lambda x:x["annual_excess_pp"],reverse=True)[:30],
        "paper_candidates":[{"ticker":x["ticker"],"data":x["latest"],
             "trade_count":x["all_trades_count"],
             "historical_only_pass":x["historical_only_pass"],
             "description":"Only a paper BUY next US open; sell on rule or within five sessions."}
             for x in paper[:20]],
        "status":"UNVALIDATED RESEARCH, NO REAL MONEY",
        "no_live_approval":True,
        "errors":errors,
        "interpretation":"Historically famous trader methods are not a publicly validated exact rule set. Results on 2026 survivors are biased. A historical screen pass is NOT permission to trade."}
