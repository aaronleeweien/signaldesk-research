"""Append-only daily prospective research signals; never executes orders."""
from pathlib import Path
from datetime import datetime,timezone,time,date
from zoneinfo import ZoneInfo
import csv,json,html

ARCHIVE=Path("research/paper_signals.csv")
FIELDS=["observed_close_date","indicative_next_business_day","model",
        "weights_json","first_recorded_utc","signal_timing","mode"]

def main():
    report=json.loads(Path("research/lab_v3.json").read_text(encoding="utf-8"))
    day=report["last_complete_market_day"]
    estimated=report["indicative_next_business_day"]
    current=report["current_research_allocations"]
    eastern=ZoneInfo("America/New_York")
    predicted_open=datetime.combine(date.fromisoformat(estimated),time(9,30),tzinfo=eastern)
    on_time=datetime.now(eastern)<predicted_open
    timing="BEFORE_ESTIMATED_OPEN" if on_time else "LATE_RECORD_AFTER_ESTIMATED_OPEN"
    previous=[]
    if ARCHIVE.exists():
        with ARCHIVE.open(newline="",encoding="utf-8") as stream:
            previous=list(csv.DictReader(stream))
    seen={(x["observed_close_date"],x["model"]) for x in previous}
    new=[]
    for model,weights in current.items():
        if (day,model) in seen:
            continue
        new.append({
          "observed_close_date":day,
          "indicative_next_business_day":estimated,
          "model":model,
          "weights_json":json.dumps(weights,sort_keys=True,separators=(",",":")),
          "first_recorded_utc":datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
          "signal_timing":timing,
          "mode":"PAPER ONLY / NOT APPROVED FOR EXECUTION",
        })
    # Rows for older dates are preserved unchanged if models are modified later.
    all_rows=previous+new
    ARCHIVE.parent.mkdir(exist_ok=True,parents=True)
    with ARCHIVE.open("w",newline="",encoding="utf-8") as stream:
        writer=csv.DictWriter(stream,fieldnames=FIELDS)
        writer.writeheader();writer.writerows(all_rows)
    dates=sorted(set(x["observed_close_date"] for x in all_rows))
    Path("site").mkdir(exist_ok=True)
    Path("site/paper_journal.json").write_text(json.dumps({
       "research_only":True,"sessions_recorded":len(dates),
       "models":list(current),"latest_date":day,"records":all_rows[-280:]},
       indent=2)+"\n",encoding="utf-8")
    visible=all_rows[-105:][::-1]
    trs=[]
    for row in visible:
        weights=json.loads(row["weights_json"])
        allocation=", ".join(f"{k} {float(v)*100:.0f}%" for k,v in weights.items())
        trs.append("<tr><td>"+html.escape(row["observed_close_date"])+"</td><td>"+html.escape(row["model"])+"</td><td>"+html.escape(allocation)+"</td><td>"+html.escape(row.get("signal_timing","UNKNOWN"))+"</td></tr>")
    page='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>SignalDesk Paper Signals</title>
<style>body{background:#0b1424;color:#eaf1fb;font:14px system-ui;max-width:1100px;padding:22px;margin:auto}a{color:#97cfff}p{line-height:1.6}.warn{background:#3e3020;border:1px solid #927046;padding:14px;border-radius:12px;color:#ffe1b3}table{border-collapse:collapse;width:100%;display:block;overflow:auto}td,th{white-space:nowrap;text-align:left;border-bottom:1px solid #354860;padding:11px 14px}</style>
<a href="lab.html">← Return to research dashboard</a><h1>Prospective paper-signal history</h1><p class="warn">PAPER RESEARCH ONLY. Nothing here is an approved trade. ETF prices can move sharply after a signal; old predictions are not altered when the rules change.</p>
<p>Signal dates recorded: <b>COUNT</b>. Latest observed close: <b>DAY</b>. All allocations are from models, not from your real brokerage holdings.</p>
<p>The system stores a dated snapshot after every successful fresh market-data run. Only signals timestamped BEFORE their estimated next-session opening can become eligible for future evaluation. The day estimate excludes weekends but not all exchange holidays. Late records are not predictive evidence.</p><table><thead><tr><th>Signal close date</th><th>Model</th><th>Hypothetical target allocation</th><th>Timestamp status</th></tr></thead><tbody>ROWS</tbody></table><p><a href="paper_journal.json">Machine-readable paper archive</a></p></html>'''
    page=page.replace("COUNT",str(len(dates))).replace("DAY",html.escape(day)).replace("ROWS","".join(trs))
    Path("site/forward.html").write_text(page,encoding="utf-8")
    print("Prospective paper archive updated: new snapshots",len(new),"session dates",len(dates))
if __name__=="__main__":main()
