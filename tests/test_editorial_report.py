"""Beginner report: factual links, short causal explanations, no invented BUY."""
import unittest
from pathlib import Path
from research import editorial_report as r

ROOT=Path(__file__).resolve().parents[1]
class EditorialReportTests(unittest.TestCase):
    def sources(self):
        src=ROOT/"research"
        return (r.get("decision_hub.json",src),
                r.get("market_discovery.json",src),
                r.get("established_strategies.json",src),
                r.get("kotegawa_reversion.json",src))

    def test_no_automatic_buy_from_historical_outperformance(self):
        a,b,c,d=self.sources()
        if any(x is None for x in (a,b,c)):self.skipTest("Repository data not yet generated")
        obj=r.narrative_bundle(a,b,c,rev=d)
        html=r.render_article(obj)
        self.assertIn("My recommendation",html)
        self.assertIn("real-money trade",html)
        self.assertIn("What I would do",html)
        self.assertIn("forward p/e",html.lower())
        self.assertIn("does not",html.lower())
        self.assertIn("Wall Street-grade research",html)
        self.assertIn("market.html",html)
        self.assertIn("established.html",html)
        self.assertIn("plain-English",html)

    def test_historical_approvals_do_not_grant_live_trading(self):
        a,b,c,d=self.sources()
        if any(x is None for x in (a,b,c)):self.skipTest("Data unavailable")
        obj=r.narrative_bundle(a,b,c,rev=d)
        self.assertNotIn("BUY NOW",r.render_article(obj))
        self.assertIn("Do not open a new real-money trade",obj["headline"])

    def test_source_date_mismatch_prevents_claiming_fresh(self):
        a,b,c,d=self.sources()
        if any(x is None for x in (a,b,c)):self.skipTest("Data unavailable")
        b=dict(b)
        b["last_completed_us_price_date"]="2020-01-01"
        result=r.narrative_bundle(a,b,c,rev=d)
        self.assertFalse(result["fresh"])
        self.assertEqual(result["long_stories"],[])
        self.assertIsNone(result["trade_story"])
        self.assertIn("different dates",result["headline"])

    def test_pct_and_pp_dont_invent_missing_values(self):
        self.assertEqual(r.pct(None),"not available")
        self.assertEqual(r.pp(None),"not available")
        self.assertEqual(r.pp(3.335,sign=True),"+3.33 percentage points")
        self.assertEqual(r.pct(-22.7),"-22.70%")

if __name__=="__main__":unittest.main()
