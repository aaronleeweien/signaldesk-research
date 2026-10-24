"""Prevent broken notification scripts and unsupported promises in decision engine."""
import pathlib,unittest
from research import decision_hub as hub

class DecisionIntegrationTests(unittest.TestCase):
    def test_notification_and_hub_python_compile(self):
        for f in ("research/notify_daily.py","research/decision_hub.py",
                  "research/daily_scanner.py","research/validation_protocol.py"):
            source=pathlib.Path(f).read_text(encoding="utf-8")
            compile(source,f,"exec")

    def test_hub_rejects_guaranteed_profit_and_automated_live_orders(self):
        source=pathlib.Path("research/decision_hub.py").read_text(encoding="utf-8")
        self.assertIn('"current_live_trade_approval":False',source)
        self.assertIn('"live_trade_approved":False',source)
        self.assertIn('proposed buy',source.lower())

    def test_public_page_keeps_research_disclaimer(self):
        html=pathlib.Path("research/decision_template.html").read_text(encoding="utf-8")
        self.assertIn("not an approved trading service",html)
        self.assertIn("conditional",html.lower())
        self.assertIn("/*DECISION_DATA*/",html)
        self.assertIn('id="trade-tab"',html)

if __name__=="__main__":unittest.main()
