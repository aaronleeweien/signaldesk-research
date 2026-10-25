"""Gmail sender preflight is tested with no network traffic."""
import unittest
from unittest.mock import patch
from research.email_report import build_message, verified_address, email_ready_html

HTML="<!doctype html><html><body><h1>Research only</h1></body></html>"
class EmailReportTests(unittest.TestCase):
    def test_header_injection_rejected(self):
        for value in ("x@gmail.com\nBcc: bad@evil.net", "Display <x@gmail.com>"):
            with self.assertRaises(ValueError):
                verified_address(value)
    def test_stale_and_mismatched_reports_not_emailed(self):
        with self.assertRaises(ValueError):
            build_message("sender@gmail.com","to@gmail.com",
                          {"date":"2020-01-01","fresh":True},"text",HTML)
        with self.assertRaises(ValueError):
            build_message("sender@gmail.com","to@gmail.com",
                          {"date":"2020-01-01","fresh":False},"text",HTML)
    def test_web_links_are_absolute_inside_email(self):
        snippet='<!doctype html><a href="market.html">Market</a><a href="#proof">Evidence</a>'
        fixed=email_ready_html(snippet)
        self.assertIn('href="https://aaronleeweien.github.io/signaldesk-research/market.html"',fixed)
        self.assertIn('href="https://aaronleeweien.github.io/signaldesk-research/report.html#proof"',fixed)

    def test_message_contains_entire_article_not_just_link(self):
        from datetime import datetime
        from zoneinfo import ZoneInfo
        today=datetime.now(ZoneInfo("America/New_York")).date().isoformat()
        msg=build_message("sender@gmail.com","to@gmail.com",
                          {"date":today,"fresh":True},"Explanation and evidence",HTML)
        self.assertIn("Explanation and evidence",msg.get_body(preferencelist=("plain",)).get_content())
        self.assertIn("Research only",msg.get_body(preferencelist=("html",)).get_content())
if __name__=="__main__":unittest.main()
