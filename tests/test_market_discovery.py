"""Safeguards for broadened market screen (offline synthetic data)."""
import unittest
import pandas as pd
import numpy as np
from research import market_discovery as m

class BroadMarketTests(unittest.TestCase):
    def test_catalog_separates_etfs_from_stocks_and_drops_bad_instruments(self):
        raw=("Symbol|Security Name|Market Category|Test Issue|Financial Status|Round Lot Size|ETF|NextShares\n"
             "AAPL|Apple Inc|Q|N|N|100|N|N\n"
             "VOO|Vanguard S&P 500 ETF|Q|N|N|100|Y|N\n"
             "BOGUS|Test Issue|Q|Y|N|100|N|N\n"
             "BROKE|Failed Listed|Q|N|Q|100|N|N\n"
             "File Creation Time: 1023202620:00|||||||\n")
        a=m.parse_directory("NASDAQ",raw)
        self.assertEqual([x["ticker"] for x in a],["AAPL","VOO"])
        self.assertEqual([x["type"] for x in a],["Stock","ETF"])

    def test_no_false_claim_of_valuation_when_missing(self):
        q=m.quote_from_screen({"symbol":"SIMPLE","shortName":"Simple",
            "marketCap":9e9,"averageDailyVolume3Month":1e6},"Largest listed")
        self.assertIsNone(q["forward_pe"])
        self.assertIsNone(q["earnings_growth_pct"])

    def test_growth_percent_normalization(self):
        q=m.quote_from_screen({"symbol":"GROW","marketCap":9e9,
            "forwardPE":20,"earningsGrowth":0.2,"revenueGrowth":25},"Growth")
        self.assertEqual(q["earnings_growth_pct"],20.)
        self.assertEqual(q["revenue_growth_pct"],25.)

    def test_missing_growth_can_be_derived_from_existing_earnings_estimates(self):
        quote=m.quote_from_screen({"symbol":"VALU",
            "marketCap":12e9,"averageDailyVolume3Month":2e6,
            "forwardPE":10.0,"trailingPE":15.0},"Valuation")
        self.assertEqual(quote["earnings_growth_pct"],50.0)
        self.assertIn("implied",quote["earnings_growth_source"])
        self.assertIsNone(quote["revenue_growth_pct"])

    def test_tiny_illiquid_companies_are_filtered(self):
        small=m.quote_from_screen({"symbol":"TINY","marketCap":20e6,"averageDailyVolume3Month":10000},"Momentum")
        self.assertIsNone(small)

    def test_historical_outperformance_does_not_imply_future_buy(self):
        idx=pd.bdate_range("2023-01-02",periods=390)
        columns={}
        for t,rate in (("VOO",1.0003),("GROW",1.0008)):
            curve=100*np.power(rate,np.arange(len(idx)))
            columns[t,"Open"]=pd.Series(curve,index=idx)
            columns[t,"Close"]=pd.Series(curve,index=idx)
        df=pd.concat(columns,axis=1)
        q={"ticker":"GROW","name":"Growing","market_cap_usd":9e9,
          "average_volume_shares":1e6,"forward_pe":None,
          "trailing_pe":25,"peg":None,"earnings_growth_pct":None,
          "revenue_growth_pct":None,"sector":"Technology","industry":None,
          "sources":["Largest listed"]}
        result=m.analyse_stock("GROW",q,df,df["VOO","Close"],str(idx[-1].date()))
        self.assertGreater(result["relative_to_voo_year_pp"],0)
        self.assertEqual(result["status"],"WATCH / MISSING PROOF")
        self.assertFalse(result["valuation_metrics_complete"])

    def test_no_proven_trading_claim_even_with_winners(self):
        self.assertEqual(m.VERSION,"market_discovery_v1")
        self.assertGreater(m.SELECTION_COUNT,30)

if __name__=="__main__":unittest.main()
