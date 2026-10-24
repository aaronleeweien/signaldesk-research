"""SignalDesk Daily Strategy Research Protocol V2.

PREDECLARED comparisons, not performance-optimized by scanning arbitrary parameters:
 A. Existing daily two-ETF breakout (legacy)
 B. SPMO 200-day daily regime, SHY fallback
 C. VOO 200-day daily regime, SHY fallback
 D. SPMO 200-day regime with ±2% hysteresis, SHY fallback
 E. Passive VOO, SPMO, QQQ

Data ending 2026 is retrospective and has been examined. NOT true untouched holdout.
2017–2021 is descriptive screening; 2022–latest is historical stress; beyond
creation timestamp is the ONLY prospective evidence. Past validation cannot grant
live approval regardless of simulation returns.
"""
from pathlib import Path
import json,math
import numpy as np
import pandas as pd

VERSION="daily_protocol_v2_2026-10-24_fixed_rules"
FAMILIES={
 "Daily Breakout Top2":"existing 20d breakout, exits at 20d low/200d SMA/63d return; up to two ETFs",
 "SPMO SMA200":"SPMO when last completed close > 200d average, otherwise SHY",
 "VOO SMA200":"VOO when last completed close > 200d average, otherwise SHY",
 "SPMO SMA200 Buffer":"SPMO entry above 102% of SMA200; exit below 98% of SMA200; else maintain previous regime",
 "VOO DCA":"VOO monthly DCA",
 "SPMO DCA":"SPMO monthly DCA",
 "QQQ DCA":"QQQ monthly DCA"
}
WINDOWS={
 "development":{"start":"2017-01-03","end":"2021-12-31","label":"Retrospective development 2017–2021"},
 "stress":{"start":"2022-01-03","end":None,"label":"Retrospective stress 2022–latest (ALREADY EXAMINED)"},
 "combined":{"start":"2017-01-03","end":None,"label":"Retrospective total 2017–latest"}
}
ACTIVE=("Daily Breakout Top2","SPMO SMA200","VOO SMA200","SPMO SMA200 Buffer")

def plans(closes,daily_targets):
    result={"Daily Breakout Top2":daily_targets}
    for ticker in ("SPMO","VOO"):
        values=closes[ticker].to_numpy(dtype=float)
        av=closes[ticker].rolling(200,min_periods=200).mean().to_numpy(dtype=float)
        base=[];hysteresis=[]
        state=False
        for i in range(len(values)):
            is_above=bool(np.isfinite(av[i]) and values[i]>av[i])
            base.append({ticker:1.} if is_above else {"SHY":1.})
            if np.isfinite(av[i]):
                if state and values[i]<.98*av[i]:state=False
                elif not state and values[i]>1.02*av[i]:state=True
            hysteresis.append({ticker:1.} if state else {"SHY":1.})
        result[ticker+" SMA200"]=base
        if ticker=="SPMO":result["SPMO SMA200 Buffer"]=hysteresis
    for ticker in ("VOO","SPMO","QQQ"):
        result[ticker+" DCA"]=[{ticker:1.}]*len(closes)
    return result

def metrics_from_backtest(prices,plan,start,end,fee=.001):
    from daily_scanner import backtest
    result=backtest(prices,plan,start,end,fee=fee,detail=True)
    returns=np.asarray(result.pop("daily_returns"),dtype=float)
    days=pd.to_datetime(result.pop("daily_dates"))
    s=pd.Series(returns,index=days)
    monthly=(1+s).groupby(s.index.to_period("M")).prod()-1
    result["months"]=len(monthly)
    result["monthly_growth_pct"]=[round(100*float(x),4) for x in monthly]
    result["monthly_labels"]=[str(x) for x in monthly.index]
    result["annual_orders"]=round(result["orders"]/max(1,(days[-1]-days[0]).days/365.25),1)
    return result

def paired_bootstrap(a,b,seed=7343):
    """Paired circular 3-month moving block resampling of arithmetic active returns.
    Retrospective uncertainty, not a prediction nor post-selection-valid p-value.
    """
    x=np.asarray(a,dtype=float)-np.asarray(b,dtype=float)
    n=len(x)
    if n<24:return {"valid":False}
    rng=np.random.default_rng(seed)
    sims=np.empty(1500);block=3
    for i in range(len(sims)):
        starts=rng.integers(0,n,size=math.ceil(n/block))
        ids=np.concatenate([(np.arange(j,j+block)%n) for j in starts])[:n]
        sims[i]=100*12*np.mean(x[ids])
    lo,hi=np.quantile(sims,[.05,.95])
    return {"valid":True,"months":n,
      "annual_mean_active_pct":round(float(np.mean(x)*1200),2),
      "interval90_low_pct":round(float(lo),2),
      "interval90_high_pct":round(float(hi),2),
      "monthly_outperformed_pct":round(float(np.mean(x>0)*100),1),
      "interval_excludes_zero":bool(lo>0)
    }

def evaluate(prices,legacy_targets,scanner):
    candidates=plans(prices.xs("Close",level=1,axis=1),legacy_targets)
    all_windows={}
    end=str(prices.index[-1].date())
    for period,config in WINDOWS.items():
        begin=config["start"];stop=config["end"] or end
        all_windows[period]={name:metrics_from_backtest(prices,targets,begin,stop)
                            for name,targets in candidates.items()}
    # Test 0bps / 10bps / 30bps and separately 2017–2021 and 2022+
    from daily_scanner import backtest
    stresses={}
    for name in ACTIVE:
        stresses[name]={str(bps):{
            p:{field:r[field] for field in ("annual_pct","max_drawdown_pct","end_usd","orders","fees_usd")}
            for p,(first,last) in {
                "development":("2017-01-03","2021-12-31"),
                "stress":("2022-01-03",end)
            }.items()
            for r in [backtest(prices,candidates[name],first,last,fee=bps/10000.)]
        } for bps in (0,10,30)}
    # "selection" is based ONLY on older retrospective years; 2022+ not used to choose winner.
    benchmark_d=all_windows["development"]["SPMO DCA"]["annual_pct"]
    candidates_older=[name for name in ACTIVE if
                      all_windows["development"][name]["annual_pct"]>benchmark_d and
                      all_windows["development"][name]["max_drawdown_pct"]>=
                      all_windows["development"]["SPMO DCA"]["max_drawdown_pct"]-3 and
                      all_windows["development"][name]["annual_orders"]<=52]
    selection=max(candidates_older,key=lambda z:all_windows["development"][z]["annual_pct"]) if candidates_older else None
    score={}
    for name in ACTIVE:
        cur=all_windows["stress"][name]
        voo=all_windows["stress"]["VOO DCA"]
        spmo=all_windows["stress"]["SPMO DCA"]
        paired_voo=paired_bootstrap(
            np.array(cur["monthly_growth_pct"])/100,
            np.array(voo["monthly_growth_pct"])/100)
        paired_spmo=paired_bootstrap(
            np.array(cur["monthly_growth_pct"])/100,
            np.array(spmo["monthly_growth_pct"])/100)
        conditions={
          "stress_return_above_VOO":cur["annual_pct"]>voo["annual_pct"],
          "stress_return_above_SPMO":cur["annual_pct"]>spmo["annual_pct"],
          "risk_drawdown_within_three_points_of_SPMO":
                cur["max_drawdown_pct"]>=spmo["max_drawdown_pct"]-3,
          "trades_under_52_a_year":cur["annual_orders"]<=52,
          "positive_relative_to_VOO_at_30bps":stresses[name]["30"]["stress"]["annual_pct"]>
                    backtest(prices,candidates["VOO DCA"],"2022-01-03",end,fee=.003)["annual_pct"],
          "bootstrap_lower_excess_above_zero":paired_voo["interval_excludes_zero"],
          "clean_independent_holdout_available":False,
          "live_forward_paper_record_long_enough":False
        }
        score[name]={
          "conditions":conditions,
          "historical_screen_pass":all(conditions[k] for k in
                  ("stress_return_above_VOO","stress_return_above_SPMO",
                   "risk_drawdown_within_three_points_of_SPMO","trades_under_52_a_year",
                   "positive_relative_to_VOO_at_30bps","bootstrap_lower_excess_above_zero")),
          "paper_only":True,"live_approval":False,
          "stress_excess_vs_VOO_pct_points":round(cur["annual_pct"]-voo["annual_pct"],2),
          "stress_excess_vs_SPMO_pct_points":round(cur["annual_pct"]-spmo["annual_pct"],2),
          "vs_VOO_bootstrap":paired_voo,"vs_SPMO_bootstrap":paired_spmo
        }
    # Even if an old-data strategy passes all numerical tests, it is NOT independently verified.
    preferred=selection
    status="REJECT LIVE TRADING; RESEARCH/PAPER ONLY"
    verdict={
      "protocol_id":VERSION,
      "generated_utc":scanner["generated_utc"],
      "last_complete_us_market_day":scanner["latest_completed_us_close"],
      "strategy_appraisal":status,
      "selected_by_2017_2021_only":preferred,
      "candidate_rule":FAMILIES.get(preferred) if preferred else None,
      "important":"2022-2026 has already been examined by this project; do not label it untouched out-of-sample.",
      "registered_models":FAMILIES,
      "review_windows":WINDOWS,
      "results":all_windows,
      "fee_stress":stresses,
      "gates":score,
      "paper_protocol":{"one_account_per_strategy":True,"initial_usd":2000,
         "monthly_usd":100,"fees_bps":10,
         "forward_starts_after_protocol":"2026-10-24",
         "minimum_forward_market_sessions":63,
         "minimum_independent_calendar_months":3,
         "benchmark":"SPMO DCA and VOO DCA",
         "future_evaluation":
           "Use only strictly timestamped target decisions available before the next actual US market session. "
           "Track next-open trades, cash contributions, turnover, equity curves and benchmark-relative returns.",
         "no_auto_live_approval":True},
      "next_decision":"None of these models can be recommended for real trading. Keep collecting prospective paper evidence; revise rules ONLY by publishing a new immutable protocol version.",
      "limits":["Already inspected 2022+ data is descriptive, not untouched holdout",
                "US market venue, FX, taxes, slippage beyond bps approximation and stock ticker survivorship",
                "Adjusted prices can introduce corporate-action inconsistencies in simulated executions",
                "Bootstrap uncertainty is conditional on historical sample and ignores model-selection corrections",
                "No real fills or order book data are available on the static GitHub dashboard"]
    }
    Path("research").mkdir(exist_ok=True)
    Path("site").mkdir(exist_ok=True)
    Path("research/validation_v2.json").write_text(json.dumps(verdict,indent=2)+"\n",encoding="utf-8")
    Path("site/validation.json").write_text(json.dumps(verdict,indent=2)+"\n",encoding="utf-8")
    Path("research/validation_v2.md").write_text(render_markdown(verdict),encoding="utf-8")
    template=Path("research/validation_template.html").read_text(encoding="utf-8")
    safe=json.dumps(verdict,separators=(",",":"),ensure_ascii=True).replace("<","\\u003c")
    Path("site/validation.html").write_text(template.replace("/*VALIDATION*/",safe),encoding="utf-8")
    # Trim appended dashboard meta to a compact status; full stats in validation.json.
    return {
      "verdict":status,
      "leading_older_years_model":preferred,
      "leading_model_trade_approved":False,
      "active_trading_allowed":False,
      "validation_page":"validation.html",
      "paper_protocol_version":VERSION
    }

def render_markdown(report):
    lines=[
      "# SignalDesk Objective Strategy Validation — Protocol V2",
      "",
      f"**Status: {report['strategy_appraisal']}**",
      f"Market close: {report['last_complete_us_market_day']}",
      "",
      "**Important:** These historical windows have already been inspected. They are NOT clean unseen out-of-sample data.",
      "",
      "## Predeclared daily strategies vs passive investing",
      "",
      "| Strategy | 2017–21 annual % | 2022+ annual % | 2022+ drawdown % | 2022+ orders/year | 2022+ annual after 30bps % |",
      "|---|---:|---:|---:|---:|---:|"]
    for name in FAMILIES:
        d=report["results"]["development"][name]
        s=report["results"]["stress"][name]
        fee=report["fee_stress"].get(name,{}).get("30",{}).get("stress",{})
        lines.append(f"| {name} | {d['annual_pct']} | {s['annual_pct']} | {s['max_drawdown_pct']} | {s['annual_orders']} | {fee.get('annual_pct','—')} |")
    lines+=["","## Objective strategy gates",
            "At least VOO and SPMO net returns, drawdown controls, low turnover, 30bps cost stress and bootstrap confidence must pass before further consideration.",
            ""]
    for name,v in report["gates"].items():
        failed=[k for k,x in v["conditions"].items() if not x]
        lines.append(f"- **{name}**: historical score **{'PASS' if v['historical_screen_pass'] else 'FAIL'}**; "
                     +f"failed checks: {', '.join(failed) if failed else 'none'}")
    lines+=["","**Paper-only even if all historical checks pass.** No reliable future trading edge has been verified.","",
      "## Paper-trading protocol","",
      "63 future market sessions minimum, three calendar months, daily timestamped targets, next-open fills, no hidden restatements, VOO/SPMO parallel paper portfolios.",
      "",
      "## What we are NOT going to do","",
      "Tune dozens of parameters until the already-seen 2022–2026 period suddenly looks profitable; that would be overfitting.",
      ""]
    return "\n".join(lines)
