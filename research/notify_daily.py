"""Notify owner through an assigned GitHub Issue only for fresh PRE-OPEN paper events.

Works with GITHUB_TOKEN limited to issues:write; never sends broker orders.
Workflow runs this on schedule only, not on code pushes or manual debug runs.
"""
import os,json,urllib.request
from pathlib import Path

def main():
    p=Path("research/daily_alert_payload.json")
    if not p.exists():
        print("No daily alert file. No notification.");return
    report=json.loads(p.read_text(encoding="utf-8"))
    events=report.get("events",[])
    # Merge decision-centre newly observed ETF breakouts with the old scanner.
    # Eligibility still comes from the scanner's before-next-open journal timing.
    if report.get("notify"):
        hub_path=Path("research/decision_hub.json")
        if hub_path.exists():
            hub=json.loads(hub_path.read_text(encoding="utf-8"))
            if hub.get("market_last_completed_close")==report.get("latest_close"):
                existing={(e.get("type"),e.get("ticker")) for e in events}
                for row in hub.get("trading_opportunities",[]):
                    if row.get("new_entry_setup") and ("HUB_PAPER_ENTRY_WATCH",row.get("ticker")) not in existing:
                        events.append({"type":"HUB_PAPER_ENTRY_WATCH","ticker":row["ticker"],"latest_planned_exit":row["latest_planned_exit"]})
    if not report.get("notify") or not events:
        print("No eligible new momentum event. No GitHub Issue created.");return
    repo=os.environ.get("GITHUB_REPOSITORY","")
    token=os.environ.get("GH_TOKEN","")
    if not repo or not token:raise RuntimeError("Missing GitHub environment for alert delivery")
    owner=repo.split("/")[0]
    source_day=report["latest_close"]
    title=f"[SignalDesk PAPER momentum alert] {source_day}"
    items=[]
    for x in events:
        t=x["type"]
        symbol=x["ticker"]
        if t=="ETF_PAPER_BUY_REVIEW":
            message=f"**PAPER BUY REVIEW:** {symbol} new target allocation {x['new_weight']:.0%}"
        elif t=="ETF_PAPER_EXIT_REVIEW":
            message=f"**PAPER EXIT REVIEW:** {symbol} old allocation {x['old_weight']:.0%} → 0%"
        elif t=="HUB_PAPER_ENTRY_WATCH":
            message=f"**DAILY HUB PAPER ENTRY:** {symbol} new ETF breakout watch, exit is CONDITIONAL; max planned time exit {x['latest_planned_exit']}. NOT live-approved."
        elif t=="ETF_MOMENTUM_WATCH":
            message=f"**ETF MOMENTUM WATCH:** {symbol} newly met breakout conditions (not a portfolio trade)"
        else:
            message=f"**STOCK WATCH ONLY:** {symbol} newly met momentum breakout conditions (survivor bias; not a trade)"
        items.append("- "+message)
    body=(
      "**This is research only. Do not use as live buy/sell instructions.**\n\n"
      f"Signals calculated using completed US trading date: **{source_day}**.\n\n"
      +"\n".join(items)
      +"\n\nThe daily rule is experimental and may underperform VOO/SPMO after costs. "
       "Options trades and brokerage orders are never created.\n\n"
       "DECISION CENTRE: https://"+owner+".github.io/"+repo.split("/")[1]+"/decisions.html\n"\n       "Scanner: https://"+owner+".github.io/"+repo.split("/")[1]+"/scanner.html\n"
       "Past events: https://github.com/"+repo+"/blob/main/research/daily_events.csv\n"
      )
    url=f"https://api.github.com/repos/{repo}/issues"
    hdr={"Authorization":"Bearer "+token,"Accept":"application/vnd.github+json",
         "X-GitHub-Api-Version":"2022-11-28","User-Agent":"SignalDesk-research-bot"}
    check=urllib.request.Request(url+"?state=all&per_page=30",headers=hdr)
    with urllib.request.urlopen(check,timeout=25) as resp:
        existing=json.load(resp)
    if any(i.get("title","").startswith(title) for i in existing):
        print("Existing notification issue found; duplicate suppressed.");return
    payload=json.dumps({"title":title,"body":body,"assignees":[owner]}).encode()
    request=urllib.request.Request(url,data=payload,headers={**hdr,"Content-Type":"application/json"},method="POST")
    with urllib.request.urlopen(request,timeout=25) as resp:
        result=json.load(resp)
    print("Assigned one paper-research alert issue:",result.get("html_url"))
if __name__=="__main__":main()
