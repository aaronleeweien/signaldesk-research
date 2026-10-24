"""SignalDesk Decision Hub — daily invest and trading discovery, research only.

SINGLE decision surface:
 (1) candidate multi-year and 4–12-week investments from live-traded ETFs and a
     fixed-survivor 30-stock exploratory watchlist
 (2) exact executable NEXT-OPEN paper breakout opportunities with a conditional
     exit protocol, evaluated separately for every ticker on nonoverlapping,
     full-history matched-date VOO holding periods.

Backtest = actual adjusted Open/Close, next US open fills, fees both sides;
no same-close executions, hindsight index constituent reconstruction or option leverage.
Validation data retrospective and selected. The history cannot approve real trades.
"""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import json,math,statistics
import numpy as np
import pandas as pd
try:
    from . import daily_scanner as scanner
except ImportError:
    import daily_scanner as scanner

VERSION="decision_hub_v1_fixed_2026-10-24"
ETFS=tuple(dict.fromkeys(scanner.ETF+("SMH","XMMO","MDY")))
STOCKS=scanner.STOCK
DEF="SHY"
FEE=.001
MAX_HOLD=15
STOP_PCT=.07
STOP_LOW=10
PAST_START="2018-01-02"
MAX_INVEST=14
MAX_TRADE_CARDS=64

def px_dict(df,t):
    return {"close":df[t,"Close"].to_numpy(float),"open":df[t,"Open"].to_numpy(float)}

def features(close):
    v=pd.Series(close,dtype=float)
    return {
       "sma200":v.rolling(200,min_periods=200).mean().to_numpy(),
       "previous_high20":v.shift(1).rolling(20,min_periods=20).max().to_numpy(),
       "previous_low10":v.shift(1).rolling(STOP_LOW,min_periods=STOP_LOW).min().to_numpy(),
       "r63":(v/v.shift(63)-1).to_numpy(),
       "r126":(v/v.shift(126)-1).to_numpy(),
       "r252":(v/v.shift(252)-1).to_numpy(),
       "vol63":(v.pct_change().rolling(63).std()*np.sqrt(252)).to_numpy()
    }

def qualifies(c,f,i):
    if i<254:return False
    x=(c[i],f["sma200"][i],f["previous_high20"][i],f["r63"][i],f["r126"][i])
    return all(np.isfinite(x)) and c[i]>f["sma200"][i] and c[i]>f["previous_high20"][i] and f["r63"][i]>0 and f["r126"][i]>0

def exit_reasons(c,f,i,entry_px,entry_i):
    why=[]
    if c[i]<=entry_px*(1-STOP_PCT):why.append("7% closing-price stop")
    if c[i]<f["previous_low10"][i]:why.append("below the prior 10-session low")
    if c[i]<f["sma200"][i]:why.append("below its 200-day average")
    if i-entry_i>=MAX_HOLD-1:why.append("15-session time limit")
    return why

def paired_ci(active,baseline,seed=7034):
    a=np.asarray(active,float)-np.asarray(baseline,float)
    if not len(a):return {"n":0,"low_pct":None,"high_pct":None,"mean_excess_pct":None}
    avg=100*a.mean()
    if len(a)<10:return {"n":len(a),"low_pct":None,"high_pct":None,"mean_excess_pct":round(float(avg),2)}
    rng=np.random.default_rng(seed)
    x=np.mean(rng.choice(a,size=(1500,len(a)),replace=True),axis=1)*100
    lo,hi=np.quantile(x,[.05,.95])
    return {"n":len(a),"low_pct":round(float(lo),2),"high_pct":round(float(hi),2),
         "mean_excess_pct":round(float(avg),2),
         "method":"descriptive paired trade bootstrap; not corrected for ticker search, overlap, or serial dependence"}

def completed_trades(df,ticker,benchmark="VOO"):
    """Buy next open after completed-session breakout.
    Exit at next open after triggering a closing-price stop or fixed time limit.
    No forward-looking fills; no simultaneous positions in same ticker.
    Compare an equal-dollar VOO position held over identical trade timestamps.
    """
    index=df.index
    dates=np.asarray(index)
    c=df[ticker,"Close"].to_numpy(float)
    o=df[ticker,"Open"].to_numpy(float)
    b=df[benchmark,"Open"].to_numpy(float)
    f=features(c)
    history=[]
    earliest=max(255,int(np.searchsorted(dates,np.datetime64(PAST_START))))
    j=earliest
    while j<len(index)-MAX_HOLD-2:
        signal=j
        if not qualifies(c,f,signal):
            j+=1;continue
        buy=signal+1
        if not (np.isfinite(o[buy]) and o[buy]>0):
            j+=1;continue
        entry=float(o[buy]);exit_at=None;reason=""
        for d in range(buy,len(index)-1):
            reasons=exit_reasons(c,f,d,entry,buy)
            if reasons:
                exit_at=d+1;reason="; ".join(reasons);break
        if exit_at is None:break
        if exit_at<=buy or not np.isfinite(o[exit_at]) or not np.isfinite(b[exit_at]):
            j=buy+1;continue
        gross=o[exit_at]/entry-1
        net=float((1-FEE)*(o[exit_at]/entry)*(1-FEE)-1)
        voo=float((1-FEE)*(b[exit_at]/b[buy])*(1-FEE)-1)
        history.append({
            "entry_signal_date":str(index[signal].date()),
            "buy_date":str(index[buy].date()),
            "sell_date":str(index[exit_at].date()),
            "hold_sessions":int(exit_at-buy),
            "return_net_pct":round(net*100,3),
            "voo_same_dates_pct":round(voo*100,3),
            "matched_excess_pct":round((net-voo)*100,3),
            "exit_reason":reason})
        j=exit_at+1 # conservative no overlapping positions
    return history,f

def validate_trades(trades):
    if not trades:
        return {"n":0,"avg_trade_pct":None,"win_rate_pct":None,"avg_vs_voo_pct":None,
          "ci90_excess_pct":None,"recent_vs_voo_pct":None,"passes_historical_gate":False,
          "reason":"No completed historical sample"}
    r=np.array([x["return_net_pct"] for x in trades])/100
    v=np.array([x["voo_same_dates_pct"] for x in trades])/100
    recent=[x for x in trades if x["buy_date"]>="2022-01-03"]
    delta=(r-v)*100
    interval=paired_ci(r,v)
    late=np.mean([x["matched_excess_pct"] for x in recent]) if recent else None
    passed=(len(trades)>=30 and len(recent)>=10 and float(delta.mean())>0 and
            late is not None and late>0 and interval["low_pct"] is not None and interval["low_pct"]>0)
    return {"n":len(trades),"n_recent":len(recent),
      "avg_trade_pct":round(float(r.mean()*100),2),
      "median_trade_pct":round(float(np.median(r)*100),2),
      "win_rate_pct":round(float(np.mean(r>0)*100),1),
      "avg_vs_voo_pct":round(float(delta.mean()),2),
      "median_vs_voo_pct":round(float(np.median(delta)),2),
      "ci90_excess_pct":[interval["low_pct"],interval["high_pct"]],
      "recent_vs_voo_pct":round(float(late),2) if late is not None else None,
      "passes_historical_gate":bool(passed),
      "limitations":"Historical trades use 2018–2026 prices; same 10bps per side for asset and VOO. Paired trade CI ignores search across assets, common market exposure and tax/FX."}

def snapshot_signal(df,ticker,f):
    i=len(df)-1;c=df[ticker,"Close"].to_numpy(float)
    current=float(c[i])
    metrics={"last_close_usd":round(current,2),
      "r63_pct":round(float(f["r63"][i]*100),2) if np.isfinite(f["r63"][i]) else None,
      "r126_pct":round(float(f["r126"][i]*100),2) if np.isfinite(f["r126"][i]) else None,
      "sma200_usd":round(float(f["sma200"][i]),2) if np.isfinite(f["sma200"][i]) else None,
      "prior_high20_usd":round(float(f["previous_high20"][i]),2) if np.isfinite(f["previous_high20"][i]) else None,
      "historical_volatility_ann_pct":round(float(f["vol63"][i]*100),1) if np.isfinite(f["vol63"][i]) else None}
    today=qualifies(c,f,i)
    yesterday=qualifies(c,f,i-1)
    metrics["bullish_breakout_now"]=today
    metrics["brand_new_breakout"]=bool(today and not yesterday)
    metrics["above_long_average"]=bool(current>f["sma200"][i]) if np.isfinite(f["sma200"][i]) else False
    return metrics

def get_stocks():
    """Optional batch feed. No output is traded if the stock source is incomplete."""
    try:
        data=scanner.fetch(STOCKS,required=False)
        if len(data.index)<300:return None
        return data
    except Exception as exc:
        print("STOCK INVESTMENT WATCH FEED FAILED:",str(exc))
        return None

def stock_ideas(stocks,baseline):
    if stocks is None:return [],"Stock price source unavailable; scanner refuses to pretend coverage."
    closes=stocks.xs("Close",level=1,axis=1)
    base=baseline["VOO","Close"]
    ideas=[]
    asof=str(baseline.index[-1].date())
    for ticker in STOCKS:
        if ticker not in closes:continue
        s=closes[ticker].dropna()
        s=s.reindex(baseline.index)
        if len(s.dropna())<600 or pd.isna(s.iloc[-1]):continue
        f=features(s.to_numpy(dtype=float))
        cur=float(s.iloc[-1]);longavg=float(f["sma200"][-1])
        if not (np.isfinite(longavg) and np.isfinite(f["r63"][-1]) and np.isfinite(f["r126"][-1])):continue
        startdates=("2019-06-24","2022-01-03")
        rel=[]
        for first in startdates:
            loc=int(baseline.index.searchsorted(pd.Timestamp(first)))
            if loc>=len(base)-100 or pd.isna(s.iloc[loc]) or s.iloc[loc]<=0:break
            ret=cur/float(s.iloc[loc])-1
            vret=float(base.iloc[-1])/float(base.iloc[loc])-1
            rel.append(round((ret-vret)*100,2))
        if len(rel)<2:continue
        if cur<=longavg or f["r63"][-1]<=0 or f["r126"][-1]<=0:continue
        strength=float(.6*f["r63"][-1]+.4*f["r126"][-1])
        ideas.append({
          "ticker":ticker,"name":ticker,"asset_type":"Stock","category":"Exploratory individual company",
          "horizon":"SHORT","hold_guide":"4–12 weeks, research watch only",
          "status":"WATCH — NOT VALIDATED",
          "r63_pct":round(float(f["r63"][-1]*100),2),
          "r126_pct":round(float(f["r126"][-1]*100),2),
          "strength_score_pct":round(strength*100,2),
          "above_long_average":True,
          "relative_2019_pp":rel[0],"relative_2022_pp":rel[1],
          "evidence_qualifier":"Fixed list of 30 present-day surviving stocks creates survivorship/selection bias; no tested buy/hold rule proved.",
          "simple_why":"Recent 3- and 6-month gains are positive and the price is above its long-term average. Past stock outperformance is not a reliable forecast.",
          "jargon":{"momentum":"Weighted combination of 63- and 126-trading-session returns.","trend":"Close > 200-session SMA.",
                    "relative_performance":"Since-date adjusted-price buy/hold gains versus VOO, not a timing backtest."}})
    ideas.sort(key=lambda x:x["strength_score_pct"],reverse=True)
    return ideas[:10],None

def fund_ideas(established,etfs):
    result=[]
    windows=established["windows"]
    current=windows["current_xmmo"]
    recent=windows["recent_2022"]
    latest=str(etfs.index[-1].date())
    for ticker in established["tickers"]:
        if ticker=="VOO":continue
        d=established["ticker_metadata"][ticker]
        a=current["diagnostics"][ticker]
        b=recent["diagnostics"][ticker]
        r=recent["returns"][ticker]
        fav=a["historically_exceeds_voo_after_10bps"] and b["historically_exceeds_voo_after_10bps"]
        ahead30=(b["returns_30bps"]["annual_twr_pct"]>recent["diagnostics"]["VOO"]["returns_30bps"]["annual_twr_pct"])
        if ticker not in etfs.columns.get_level_values(0):continue
        s=etfs[ticker,"Close"].to_numpy(float)
        f=features(s)
        trend=bool(s[-1]>f["sma200"][-1])
        momentum=bool(f["r63"][-1]>0 and f["r126"][-1]>0)
        is_sector=ticker=="SMH"
        if not fav:status="NOT QUALIFIED — BELOW VOO IN SOME PERIODS"
        elif not ahead30:status="WATCH — COST SENSITIVITY"
        elif is_sector:status="HIGH-RISK WATCH — INDUSTRY CONCENTRATION"
        elif not (trend and momentum):status="WATCH — PRICE TREND WEAK"
        else:status="HISTORICAL OUTPERFORMER — INVESTMENT RESEARCH"
        score=round(float(.6*f["r63"][-1]+.4*f["r126"][-1])*100,2)
        simple=("This actual ETF historically grew faster than VOO in both inspected periods after the same estimated purchase fee."
            if fav else "This fund did not consistently beat VOO in the two historical windows we checked.")
        if is_sector:simple+=" Semiconductor concentration caused substantially larger historical losses."
        result.append({"ticker":ticker,"name":ticker,"asset_type":"ETF","category":d["category"],
          "horizon":"LONG","hold_guide":"1–5+ years (investment, not a promised exit date)",
          "status":status,"strength_score_pct":score,
          "r63_pct":round(float(f["r63"][-1]*100),2),
          "r126_pct":round(float(f["r126"][-1]*100),2),
          "above_long_average":trend,
          "relative_2019_pp":a["annual_advantage_over_voo_pp"],
          "relative_2022_pp":b["annual_advantage_over_voo_pp"],
          "annual_return_recent_pct":r["annual_twr_pct"],
          "max_drawdown_recent_pct":r["max_drawdown_pct"],
          "beta_to_voo":b["beta_to_voo"],
          "statistical_ci90_pct":b["paired_active_uncertainty"],
          "after_30bps_beats_voo":ahead30,
          "methodology_url":d["source"],
          "evidence_qualifier":"Actual fund history and fund-level stock selection. Selection done after observing older winners; taxes, Singapore currency conversion and trading differences are not modelled.",
          "simple_why":simple,
          "jargon":{"momentum":"63- and 126-session trailing returns; positive does not mean guaranteed future gains.",
                    "beta":"Historical sensitivity to VOO, not a prediction.",
                    "drawdown":"Largest peak-to-trough decline within the matched sample.",
                    "bootstrap":"How uncertain historical fund-minus-VOO returns are; fund selection after observing the past weakens statistical certainty."}})
    result.sort(key=lambda x:(x["status"].startswith("HISTORICAL"),x["relative_2022_pp"]),reverse=True)
    return result

def estimated_exit_date(decision_day):
    next_session=pd.Timestamp(decision_day)+pd.offsets.BDay(1)
    latest=next_session+pd.offsets.BDay(MAX_HOLD)
    return str(next_session.date()),str(latest.date())

def build(established,etfs,stocks=None,now=None):
    if now is None:now=datetime.now(ZoneInfo("America/New_York"))
    last=str(etfs.index[-1].date())
    if established["latest_completed_us_market_day"]!=last:
        raise ValueError("Established fund report and trading signals are on different market sessions; refuse misleading report")
    benchmark="VOO"
    ideas=fund_ideas(established,etfs)
    stockideas,stockerror=stock_ideas(stocks,etfs)
    next_day,latest_exit=estimated_exit_date(last)
    trade=[]
    for t in ETFS:
        fills,f=completed_trades(etfs,t,benchmark=benchmark)
        score=validate_trades(fills)
        latest=snapshot_signal(etfs,t,f)
        # The condition is computed from the latest COMPLETED US close.
        signal=latest["brand_new_breakout"]
        older=(latest["bullish_breakout_now"] and not signal)
        pass_history=score["passes_historical_gate"]
        # A retrospective pass is insufficient to call this a vetted executable edge.
        label=("NEW PAPER ENTRY — UNVALIDATED" if signal else
               "TREND CONTINUES — NO NEW ENTRY" if older else "NO ENTRY")
        # data-snooping and prospectiveness is tracked separately; all live orders blocked
        trade.append({
          "ticker":t,"asset_type":"ETF","horizon":"UP TO 15 US TRADING SESSIONS",
          "signal_date":last,"proposed_next_open":next_day,
          "latest_planned_exit":latest_exit,
          "setup_state":label,"new_entry_setup":signal,
          "candidate_historical_gate":pass_history,
          "live_trade_approved":False,
          "trade_type":"BUY next regular US open IF a paper entry is confirmed; not a recommendation to place a live order",
          "exit_plan":"After a completed close <= 93% of entry price, OR below prior 10-session low, OR below 200-session SMA, OR after 15 sessions: SELL next US open. Earlier exits can occur. No fixed profitable sell date can be predicted.",
          "stop_closing_threshold_pct":-7,"max_hold_sessions":MAX_HOLD,
          "risk_budget_note":"Notional trade size and gap risk require separate account constraints; a 7% closing stop can lose more after an overnight gap.",
          "indicators":latest,"historical_evidence":score,
          "why_simple":("A brand-new 20-day price high occurred with positive 3-/6-month momentum and above the 200-day trend." if signal
                       else "No brand-new breakout today. The rules do not call for opening a fresh trade."),
          "not_trading_why":"We do not yet have independent future validation or a demonstrated repeatable advantage over simply holding VOO."
        })
    # Optional stock-level trade watches. The 30-stock universe consists of modern
    # survivors, so even an excellent historical stock simulation is NOT validated
    # and must never gain a live or historical trade approval by this screen.
    if stocks is not None:
        stock_rows=stocks.reindex(etfs.index)
        for ticker in STOCKS:
            fields=[(ticker,"Open"),(ticker,"Close")]
            if not all(field in stock_rows.columns for field in fields):continue
            data=pd.concat([stock_rows[fields],
                etfs[[("VOO","Open"),("VOO","Close")]]],axis=1).dropna()
            if len(data)<900 or data.index[-1]!=etfs.index[-1]:continue
            stock_fills,stock_feat=completed_trades(data,ticker)
            stock_score=validate_trades(stock_fills)
            stock_score["survivor_biased_historical_screen"] = stock_score["passes_historical_gate"]
            stock_score["passes_historical_gate"]=False
            latest_stock=snapshot_signal(data,ticker,stock_feat)
            fresh=latest_stock["brand_new_breakout"]
            ongoing=latest_stock["bullish_breakout_now"] and not fresh
            trade.append({
                "ticker":ticker,"asset_type":"Stock","horizon":"UP TO 15 US TRADING SESSIONS",
                "signal_date":last,"proposed_next_open":next_day,
                "latest_planned_exit":latest_exit,
                "setup_state":"NEW STOCK BREAKOUT — EXPLORATORY PAPER ONLY" if fresh else
                    ("STOCK TREND CONTINUES — NO NEW ENTRY" if ongoing else "NO ENTRY"),
                "new_entry_setup":fresh,
                "candidate_historical_gate":False,
                "live_trade_approved":False,
                "trade_type":"EXPLORATORY WATCH ONLY; a survivor-biased stock history is not a trade recommendation",
                "exit_plan":"After a completed close <= 93% of hypothetical next-open entry price, OR below prior 10-session low, OR below 200-session SMA, OR after 15 sessions: paper SELL next regular US open. Earlier exits possible.",
                "stop_closing_threshold_pct":-7,
                "max_hold_sessions":MAX_HOLD,
                "risk_budget_note":"Individual stocks can gap through stops; 30 present-day surviving companies create serious historical selection bias.",
                "indicators":latest_stock,
                "historical_evidence":stock_score,
                "why_simple":"New 20-day stock price high with positive 3-/6-month momentum. This is NOT proven to outperform VOO because the stock history comes from today's surviving names." if fresh else
                    "No new breakout today; the rules do not open a fresh stock trade.",
                "not_trading_why":"Stock selection uses today's survivors, not a point-in-time eligible universe. Paper watch only; no trading edge has been independently verified."
            })
    trade.sort(key=lambda x:(x["new_entry_setup"],x["candidate_historical_gate"],x["historical_evidence"]["avg_vs_voo_pct"] or -999),reverse=True)
    # Stocks are intentionally NOT allowed in trade backtesting because the 2026
    # survivor-list would make an unfair historical trading universe.
    research_watch=[i for i in trade if i["new_entry_setup"]]
    n_pass=sum(x["candidate_historical_gate"] for x in trade)
    count=sum(x["new_entry_setup"] for x in trade)
    days_old=(pd.Timestamp(now.date())-pd.Timestamp(last)).days
    if days_old>5:raise ValueError("Daily trade data too old to present actionable ideas")
    if now.weekday()>=5:market="WEEKEND: US exchanges are closed. Next session is estimated."
    elif (now.hour,now.minute)<(9,30):market="PRE-MARKET: Regular US trading has not opened."
    elif (now.hour,now.minute)>=(16,0):market="AFTER HOURS: Last completed prices, not live quotes."
    else:market="US SESSION: prices are from the prior completed close; no intraday entry signal."
    return {"protocol":VERSION,
      "generated_utc":pd.Timestamp.now(tz="UTC").strftime("%Y-%m-%d %H:%M UTC"),
      "market_last_completed_close":last,
      "us_market_context":market,
      "data_type":"Previous completed-session adjusted prices; NOT real-time trading quotes",
      "next_estimated_us_business_session":next_day,
      "current_live_trade_approval":False,
      "universe":{"etfs_tested":len(ETFS),"stocks_screened":len(STOCKS),
          "not_marketwide":"The initial universe is selected ETFs plus a fixed list of surviving large-cap stocks; it is not all listed securities."},
      "topline":{
        "long_historical_investment_candidates":[x["ticker"] for x in ideas if x["status"].startswith("HISTORICAL")],
        "new_technical_breakouts":count,
        "historical_trade_gates_passed":n_pass,
        "approved_real_trades":0,
        "quick_answer_today":"No approved active trade. Review the historical fund investment candidates separately."},
      "investment_ideas":ideas,
      "short_term_stock_watch":stockideas,
      "stock_feed_warning":stockerror,
      "trading_opportunities":trade[:MAX_TRADE_CARDS],
      "research_new_technical_breakouts":[x["ticker"] for x in research_watch],
      "methodology":{
        "long_investment":"Match live ETF histories vs VOO 2019+ and 2022+, including dividends embedded in adjusted prices and estimated 10bps monthly buy costs. Filter by recent momentum/trend.",
        "short_stock_watch":"Show 30 surviving companies with positive 63/126-day momentum above SMA200, no claim of predictive stock alpha.",
        "trade_entry":"After a completed US close breaks above the PRIOR 20-session high, 200-day SMA, positive 63 and 126-session returns; next US regular opening is paper fill.",
        "trade_exit":"Next session open after a close crosses 7% downside from entry, previous 10-session low, 200-day SMA or after 15 holding sessions.",
        "trading_backtest":"Nonoverlapping trades since 2018, same-date VOO entry/exit, estimated 10bps costs on both sides; bootstrap historical matched excess.",
        "trade_gate":"At least 30 total completed trades, 10 in 2022+, positive average matched excess in entire and recent periods, positive lower bound of descriptive 90% bootstrap; STILL not approved to trade live until prospective data independent of selection.",
        "execution_time":"Signal after US market close, proposed buy the NEXT open; never pretend an entry is available in the already-closed session.",
        "long_horizon":"Long term 1–5+ years, no fixed successful sell date. Use periodic review, not short-term trading stops.",
        "live_prices":"Not provided: GitHub Pages is a daily research snapshot, not a live brokerage terminal."},
      "data_limits":[
        "The trade backtest covers a finite handpicked ETF list and 30 present-day stock survivors; stock backtests have survivorship bias and multiple ticker searches inflate chance of apparent winners.",
        "All trade strategies remain research-only even if historical screening passes.",
        "Simulated next-open trading may not match accessible broker quotes, fills, order sizes or FX costs.",
        "Trading stop checks closes only; overnight gaps can exceed the planned loss limit.",
        "U.S. exchange holidays are not represented by simple business-day estimates.",
        "XMMO index methodology was changed in June 2019; older XMMO history under prior index is not evidence for the present method.",
        "US ETF after-tax results may differ materially from Ireland-domiciled CSPX for Singapore-based investors.",
        "This site is refreshed by scheduled GitHub Actions; it has no real-time data subscription and cannot guarantee notification delivery."
      ]}

def json_safe(value):
    """Convert numpy scalar output into ordinary JSON scalars without hiding other bugs."""
    if isinstance(value,np.generic):return value.item()
    if isinstance(value,pd.Timestamp):return str(value)
    raise TypeError(f"Unsupported report value: {type(value).__name__}")

def save(report):
    Path("research").mkdir(exist_ok=True)
    Path("site").mkdir(exist_ok=True)
    Path("research/decision_hub.json").write_text(json.dumps(report,indent=2,default=json_safe)+"\n",encoding="utf-8")
    Path("site/decision_hub.json").write_text(json.dumps(report,indent=2,default=json_safe)+"\n",encoding="utf-8")
    html=Path("research/decision_template.html").read_text(encoding="utf-8")
    js=json.dumps(report,separators=(",",":"),ensure_ascii=True,default=json_safe).replace("<","\\u003c")
    Path("site/decisions.html").write_text(html.replace("/*DECISION_DATA*/",js),encoding="utf-8")
    homepage=Path("site/index.html")
    if homepage.exists():
        old=homepage.read_text(encoding="utf-8")
        if 'href="decisions.html"' not in old and "<main>" in old:
            top=('<div style="margin:14px 0 22px;padding:17px;border:1px solid #69a8c0;'
                 'background:#102e40;border-radius:13px"><a href="decisions.html" '
                 'style="color:#94ebca;font-size:19px;font-weight:800">'
                 'DAILY DECISIONS: What to consider buying and whether to trade today →'
                 '</a><p style="margin:8px 0 0;color:#caddeb">'
                 'Unified research, historical evidence, precise conditional paper exit rules.</p></div>')
            homepage.write_text(old.replace("<main>","<main>"+top,1),encoding="utf-8")
    lines=["# SignalDesk Daily Investor / Trader Decisions",f"Latest completed market close: {report['market_last_completed_close']}",
           "**NO APPROVED LIVE TRADES**","", "## Historic ETF investment candidates", ""]
    for row in report["investment_ideas"]:
        lines.append(f"- {row['ticker']}: {row['status']}. Annualised advantage vs VOO 2019+ {row['relative_2019_pp']:+.2f}pp, 2022+ {row['relative_2022_pp']:+.2f}pp. {row['simple_why']}")
    lines+=["","## Current ETF setups (PAPER ONLY)",""]
    for row in report["trading_opportunities"]:
        if row["new_entry_setup"]:
            lines.append(f"- {row['ticker']} breakout observed on {row['signal_date']}, next estimated US open {row['proposed_next_open']}, max planned exit {row['latest_planned_exit']}; stop/exit rules are CONDITIONAL. 2018+ historical trade count {row['historical_evidence']['n']}, observed average matched excess {row['historical_evidence']['avg_vs_voo_pct']}pp.")
    if not any(x["new_entry_setup"] for x in report["trading_opportunities"]):
        lines.append("- No fresh ETF breakouts on the last completed close.")
    lines+=["","The system provides research watches, NOT a real-money trading instruction.",
        "All figures historical; fixed ETF universe; not a guaranteed profitable strategy.",
        "","Next research milestone: record post-decision future fills and benchmark returns for the proposed trade rules, and test a sufficiently broad point-in-time stock universe."]
    Path("research/decision_hub.md").write_text("\n".join(lines)+"\n",encoding="utf-8")

def main():
    established=json.loads(Path("research/established_strategies.json").read_text(encoding="utf-8"))
    data=scanner.fetch(ETFS+(DEF,))
    stocks=get_stocks()
    report=build(established,data,stocks)
    discovery=Path("research/market_discovery.json")
    if discovery.exists():
        wide=json.loads(discovery.read_text(encoding="utf-8"))
        fresh=(wide.get("last_completed_us_price_date")==report["market_last_completed_close"])
        report["broader_market"]={
           "available":bool(fresh and wide["discovery_feeds"]["unique_stock_quotes"]>0),
           "market_catalog_count":wide["universe_catalog"]["US_listings_catalogued"],
           "market_stocks_screener_count":wide["discovery_feeds"]["unique_stock_quotes"],
           "stocks_with_price_analysis":wide["stocks_with_price_and_momentum_results"],
           "stocks_with_full_valuation":wide["stocks_with_price_growth_and_valuation_data"],
           "research_candidates":wide["stock_investing_watchlist"][:8] if fresh else [],
           "new_research_trade_setups":wide["expanded_trade_watches"][:8] if fresh else [],
           "coverage_note":wide["important"],
           "status":"FRESH PARTIAL MARKET SCREEN" if fresh else "MARKET DISCOVERY DATA UNAVAILABLE OR STALE",
           "research_page":"market.html"
        }
    else:
        report["broader_market"]={"available":False,"status":"NO WIDER MARKET DATA","research_page":"market.html"}
    save(report)
    print("DECISION HUB",report["market_last_completed_close"],
          "ETF fund candidates",report["topline"]["long_historical_investment_candidates"],
          "new ETF breakout watches",report["research_new_technical_breakouts"],
          "live trades approved 0")
if __name__=="__main__":main()
