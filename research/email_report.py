"""Send the actual daily SignalDesk report through Gmail SMTP.

Recipient/sender/app password come ONLY from GitHub Actions secrets.
Never hard-code addresses in public files. Sends only for a complete, fresh,
scheduled research run. Maintains a public session-only receipt (no PII).
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from email.message import EmailMessage
from email.utils import parseaddr
from pathlib import Path
from zoneinfo import ZoneInfo
import json
import os
import smtplib

REPORT_URL = "https://aaronleeweien.github.io/signaldesk-research/report.html"

def verified_address(value):
    display, address = parseaddr(value or "")
    if display or address != value or "@" not in address or "\r" in value or "\n" in value:
        raise ValueError("Use a plain email address, without header formatting.")
    return address

def build_message(sender, recipient, report, markdown, html):
    sender = verified_address(sender)
    recipient = verified_address(recipient)
    if not report.get("fresh"):
        raise ValueError("Research sources differ in market date; no email will be sent.")
    day = date.fromisoformat(report["date"])
    if day > datetime.now(ZoneInfo("America/New_York")).date():
        raise ValueError("Report market date is in the future.")
    if (datetime.now(ZoneInfo("America/New_York")).date() - day).days > 4:
        raise ValueError("Report is stale; refusing to email an old investment report.")
    if not markdown.strip() or not html.lstrip().lower().startswith("<!doctype html>"):
        raise ValueError("Missing report article.")
    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = recipient
    msg["Subject"] = f"SignalDesk Daily | US market close {day.isoformat()} | Research only"
    msg.set_content(markdown + f"\nFull report and sources: {REPORT_URL}\n")
    # The HTML is a readable article; full evidence links remain clickable.
    msg.add_alternative(html, subtype="html")
    return msg

def main(base=Path("research"), site=Path("site")):
    sender = os.environ.get("SIGNALDESK_GMAIL_FROM", "").strip()
    recipient = os.environ.get("SIGNALDESK_MAIL_TO", "").strip()
    password = os.environ.get("SIGNALDESK_GMAIL_APP_PASSWORD", "").strip()
    if not all((sender, recipient, password)):
        print("::warning::SignalDesk daily email NOT active: set SIGNALDESK_GMAIL_FROM, SIGNALDESK_MAIL_TO, SIGNALDESK_GMAIL_APP_PASSWORD as repository secrets.")
        return False
    report = json.loads((site / "daily_brief.json").read_text(encoding="utf-8"))
    receipt_file = base / "email_sent_sessions.json"
    receipts = json.loads(receipt_file.read_text(encoding="utf-8")) if receipt_file.exists() else []
    if any(r["market_date"] == report["date"] for r in receipts):
        print("Email already recorded for market session:", report["date"])
        return False
    msg = build_message(
        sender, recipient, report,
        (base / "daily_brief.md").read_text(encoding="utf-8"),
        (site / "report.html").read_text(encoding="utf-8"))
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=35) as smtp:
        smtp.login(sender, password)
        smtp.send_message(msg)
    receipts.append({"market_date": report["date"],
                     "sent_utc": datetime.now(timezone.utc).isoformat()})
    receipt_file.write_text(json.dumps(receipts, indent=2) + "\n", encoding="utf-8")
    print("Daily report email SENT for completed US market session:", report["date"])
    return True

if __name__ == "__main__":
    main()
