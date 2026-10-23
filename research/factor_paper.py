"""Append-only, dated paper signals for SPMO factor ETF models.

Backtests and theoretical targets are NOT instructions to trade real capital.
"""
from pathlib import Path
from datetime import date,datetime,time,timezone
from zoneinfo import ZoneInfo
import csv,json,html
PATH=Path("research/factor_paper.csv")
COLUMNS=("observed_us_close","estimated_next_business_day","model","paper_target_json","signal_actions_json",
         "recorded_utc","timing_quality","live_approved")

def run():
    d=json.loads(Path("research/factor_etf.json").read_text(encoding="utf-8"))
    day=d["last_market_session"];next_day=d["next_estimated_business_day"]
    et=ZoneInfo("America/New_York")
    cut=datetime.combine(date.fromisoformat(next_day),time(9,30),tzinfo=et)
    now=datetime.now(timezone.utc)
    timing="BEFORE_ESTIMATED_US_OPEN" if now<cut else "AFTER_OPEN_NOT_PROSPECTIVE"
    rows=[]
    if PATH.exists():
        with PATH.open(newline="",encoding="utf-8") as inp:rows=list(csv.DictReader(inp))
    seen={(x["observed_us_close"],x["model"]) for x in rows}
    added=0
    for model in d["models"]:
        if (day,model) in seen:continue
        rows.append({
         "observed_us_close":day,"estimated_next_business_day":next_day,"model":model,
         "paper_target_json":json.dumps(d["next_session_paper_weights"][model],sort_keys=True,separators=(",",":")),
         "signal_actions_json":json.dumps(d["next_session_paper_actions"][model],sort_keys=True,separators=(",",":")),
         "recorded_utc":now.strftime("%Y-%m-%d %H:%M UTC"),
         "timing_quality":timing,"live_approved":"NO"})
        added+=1
    PATH.parent.mkdir(exist_ok=True,parents=True)
    with PATH.open("w",newline="",encoding="utf-8") as f:
        writer=csv.DictWriter(f,fieldnames=COLUMNS)
        writer.writeheader();writer.writerows(rows)
    Path("site").mkdir(exist_ok=True)
    Path("site/factor_paper.json").write_text(json.dumps({
      "paper_only":True,"trading_approved":False,"sessions_recorded":len(set(x["observed_us_close"] for x in rows)),
      "records":rows[-210:]
      },indent=2)+"\n",encoding="utf-8")
    table=""
    for x in rows[-100:][::-1]:
        allocation=", ".join(f"{k} {v:.0%}" for k,v in json.loads(x["paper_target_json"]).items())
        table+=("<tr><td>"+html.escape(x["observed_us_close"])+"</td><td>"+html.escape(x["model"])
              +"</td><td>"+html.escape(allocation)+"</td><td>"+html.escape(x["timing_quality"])+"</td></tr>")
    site='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>SignalDesk Factor ETF Paper Journal</title><style>body{font:14px system-ui;background:#0b1525;color:#e9f2ff;margin:30px auto;padding:0 16px;max-width:1000px}a{color:#93d3ff}p{line-height:1.6}table{border-collapse:collapse;width:100%;display:block;overflow:auto}th,td{padding:12px 14px;border-bottom:1px solid #34465d;text-align:left;white-space:nowrap}aside{background:#42331f;border:1px solid #ac834b;padding:16px;border-radius:12px}</style><a href="factor.html">← SPMO evidence dashboard</a><h1>ETF paper-signal history</h1><aside>Only BEFORE_OPEN entries count as genuinely prospective. There are no live trading approvals or broker connections, and this is a hypothetical, timestamped research archive.</aside><p>Distinct completed-session dates: COUNT · Last observed session: DAY. The exchange holiday calendar is approximate and timing must be confirmed before execution.</p><table><tr><th>Completed US date</th><th>Strategy</th><th>Hypothetical next target</th><th>Timing status</th></tr>ROWS</table><p><a href="factor_paper.json">Read structured history</a></p></html>'''
    site=site.replace("COUNT",str(len(set(x["observed_us_close"] for x in rows)))).replace("DAY",day).replace("ROWS",table)
    Path("site/factor_paper.html").write_text(site,encoding="utf-8")
    print("Factor ETF research journal",day,"added",added,"total",len(rows))

if __name__=="__main__":run()
