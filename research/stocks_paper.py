"""Append-only stock strategy paper signals. NEVER submits trades to a broker."""
from pathlib import Path
from datetime import datetime,date,time,timezone
from zoneinfo import ZoneInfo
import csv,json,html

FILE=Path("research/stocks_paper.csv")
FIELDS=["observed_close","estimated_next_business_day","model",
        "paper_weights_json","first_recorded_utc","timing","approval"]

def main():
    d=json.loads(Path("research/stocks_v1.json").read_text(encoding="utf-8"))
    today=d["last_complete_market_day"]
    next_day=d["estimated_next_business_day"]
    started=datetime.now(timezone.utc)
    et=started.astimezone(ZoneInfo("America/New_York"))
    estimated_open=datetime.combine(date.fromisoformat(next_day),time(9,30),tzinfo=ZoneInfo("America/New_York"))
    timing="BEFORE_OPEN" if et<estimated_open else "AFTER_OPEN_NOT_PROSPECTIVE"
    rows=[]
    if FILE.exists():
        with FILE.open(newline="",encoding="utf-8") as f:
            rows=list(csv.DictReader(f))
    existing={(r["observed_close"],r["model"]) for r in rows}
    added=0
    for model,allocation in d["next_session_research_targets"].items():
        if (today,model) in existing:continue
        rows.append({"observed_close":today,"estimated_next_business_day":next_day,
            "model":model,"paper_weights_json":json.dumps(allocation,sort_keys=True),
            "first_recorded_utc":started.strftime("%Y-%m-%d %H:%M UTC"),
            "timing":timing,"approval":"PAPER ONLY; NOT VERIFIED"})
        added+=1
    FILE.parent.mkdir(exist_ok=True,parents=True)
    with FILE.open("w",newline="",encoding="utf-8") as f:
        writer=csv.DictWriter(f,fieldnames=FIELDS);writer.writeheader();writer.writerows(rows)
    Path("site").mkdir(exist_ok=True)
    Path("site/stocks_paper.json").write_text(json.dumps({"research_only":True,
      "sessions_recorded":len(set(r["observed_close"] for r in rows)),
      "data":[r for r in rows[-360:]]},indent=2)+"\n",encoding="utf-8")
    trs=[]
    for r in rows[-150:][::-1]:
        alloc=json.loads(r["paper_weights_json"])
        text=", ".join(k+" "+str(round(float(v)*100))+"%" for k,v in alloc.items())
        trs.append("<tr><td>"+html.escape(r["observed_close"])+"</td><td>"+html.escape(r["model"])+"</td><td>"+html.escape(text)+"</td><td>"+html.escape(r["timing"])+"</td></tr>")
    page='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>SignalDesk Stock Paper Signals</title>
<style>body{font:14px system-ui;background:#091324;color:#eef4ff;max-width:1100px;margin:25px auto;padding:0 16px}a{color:#8bc8fa}table{border-collapse:collapse;display:block;overflow:auto;width:100%}td,th{white-space:nowrap;padding:12px;border-bottom:1px solid #34465a;text-align:left}.notice{padding:15px;border:1px solid #b2894c;background:#46341f;border-radius:11px;color:#ffe4bd}</style>
<a href="stocks.html">← Stock Opportunity dashboard</a><h1>Stock strategy: dated paper signals</h1><p class="notice">Never real trading instructions. Only targets recorded BEFORE the estimated next market opening can be considered genuinely forward-looking observations. Same-date model records are never silently overwritten.</p>
<p>Dates recorded: TOTAL. Latest report: DAY. Market holidays are not fully accounted for in next-business-day estimates.</p>
<table><thead><tr><th>Observed close</th><th>Model</th><th>Hypothetical holdings</th><th>Timing evidence</th></tr></thead><tbody>ROWS</tbody></table></html>'''
    Path("site/stocks_paper.html").write_text(page.replace("TOTAL",str(len(set(r["observed_close"] for r in rows)))).replace("DAY",today).replace("ROWS","".join(trs)),encoding="utf-8")
    print("Stock paper targets recorded",added,"new rows;",len(rows),"total rows")
if __name__=="__main__":main()
