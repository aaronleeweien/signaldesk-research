"""Isolated fixtures: no external data calls, no fabricated fundamentals."""
import unittest
from research.sec_fundamentals import inspect_company, annual_tag, select_candidates

def annual(value, end="2025-12-31", filed="2026-02-15"):
    return {"val":value,"start":"2025-01-01","end":end,"filed":filed,
            "form":"10-K","accn":"0000000000-26-000001"}
def usd(values):
    return {"units":{"USD":values}}

class SecFundamentalsTests(unittest.TestCase):
    def test_fcf_and_growth_are_independent_filing_numbers(self):
        facts={"entityName":"Example, Inc.","facts":{"us-gaap":{
            "Revenues":usd([annual(100),{"val":80,"start":"2024-01-01","end":"2024-12-31","filed":"2025-02-15","form":"10-K"}]),
            "NetCashProvidedByUsedInOperatingActivities":usd([annual(20)]),
            "PaymentsToAcquirePropertyPlantAndEquipment":usd([annual(5)]),
            "NetIncomeLoss":usd([annual(12)])
        }}}
        stock={"ticker":"EXM","name":"Example","market_cap_usd":300}
        actual=inspect_company(stock, 123, facts)
        self.assertEqual(actual["free_cash_flow_usd"],15)
        self.assertEqual(actual["free_cash_flow_yield_pct"],5)
        self.assertEqual(actual["revenue_growth_yoy_pct"],25)
        self.assertEqual(actual["status"],"independent_annual_fundamentals_verified")

    def test_missing_capex_is_not_zero(self):
        facts={"facts":{"us-gaap":{
            "Revenues":usd([annual(100)]),
            "NetCashProvidedByUsedInOperatingActivities":usd([annual(20)]),
        }}}
        actual=inspect_company({"ticker":"EXM","market_cap_usd":100},123,facts)
        self.assertIsNone(actual["free_cash_flow_usd"])
        self.assertIsNone(actual["free_cash_flow_yield_pct"])
        self.assertEqual(actual["status"],"partial_filing_data")

    def test_no_forecast_or_buy_from_SEC_ratios(self):
        self.assertFalse(any("buy" in key or "target" in key
            for key in inspect_company({"ticker":"E","market_cap_usd":1},1,{})))

    def test_shortlist_uses_multiple_predeclared_sorts(self):
        rows=[{"ticker":s,"status":"RESEARCH CANDIDATE","forward_pe":p}
              for s,p in [("A",70),("B",45),("C",8),("D",12),("E",7)]]
        self.assertEqual([x["ticker"] for x in select_candidates(rows,4)], ["A","B","E","C"])
if __name__=="__main__":unittest.main()
