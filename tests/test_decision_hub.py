"""Decision Hub invariants on synthetic market prices; no internet required."""
import unittest
import numpy as np
import pandas as pd
from research import decision_hub as hub

def fixture(days=1150):
    ix=pd.bdate_range("2018-01-01",periods=days)
    prices={}
    for t in tuple(dict.fromkeys(hub.ETFS+("SHY",))):
        data=np.full(days,100.)
        prices[t,"Open"]=pd.Series(data,index=ix)
        prices[t,"Close"]=pd.Series(data,index=ix)
    return pd.concat(prices,axis=1)

class InvestmentDecisionTests(unittest.TestCase):
    def test_no_signal_on_flat_market(self):
        data=fixture()
        f=hub.features(data["VOO","Close"].to_numpy())
        self.assertFalse(hub.qualifies(data["VOO","Close"].to_numpy(),f,len(data)-1))
        self.assertFalse(hub.snapshot_signal(data,"VOO",f)["brand_new_breakout"])

    def test_paper_trade_does_not_look_at_future_close_for_entry(self):
        d=fixture()
        d.loc[:,("SPMO","Close")]=100*np.power(1.001,np.arange(len(d)))
        d.loc[:,("SPMO","Open")]=d["SPMO","Close"].to_numpy()
        f=hub.features(d["SPMO","Close"].to_numpy())
        x=hub.qualifies(d["SPMO","Close"].to_numpy(),f,len(d)-2)
        after=d.copy()
        after.loc[d.index[-1],("SPMO","Close")]=99999.
        f2=hub.features(after["SPMO","Close"].to_numpy())
        self.assertEqual(x,hub.qualifies(after["SPMO","Close"].to_numpy(),f2,len(d)-2))

    def test_fixed_expiration_and_early_close_stop(self):
        d=fixture()
        px=100*np.power(1.001,np.arange(len(d)))
        d.loc[:,("SPMO","Close")]=px
        d.loc[:,("SPMO","Open")]=px
        history,_=hub.completed_trades(d,"SPMO")
        self.assertGreater(len(history),0)
        self.assertTrue(all(1<=t["hold_sessions"]<=hub.MAX_HOLD for t in history))
        self.assertTrue(all(t["buy_date"]>t["entry_signal_date"] for t in history))
        self.assertTrue(all(t["sell_date"]>t["buy_date"] for t in history))
        self.assertTrue(all(t["return_net_pct"]!=float("inf") for t in history))

    def test_costs_make_flat_roundtrip_unprofitable(self):
        d=fixture()
        o=d["VOO","Open"].to_numpy()
        fee=hub.FEE
        cost=(1-fee)*(o[-1]/o[-2])*(1-fee)-1
        self.assertLess(cost,0.)

    def test_trade_gate_rejects_tiny_history(self):
        small=[{"return_net_pct":10.,"voo_same_dates_pct":0.,
                "matched_excess_pct":10.,"buy_date":"2026-01-05"} for i in range(4)]
        output=hub.validate_trades(small)
        self.assertFalse(output["passes_historical_gate"])
        self.assertEqual(output["n"],4)

    def test_trade_research_requires_at_least_30_historical_samples(self):
        trades=[{"return_net_pct":2.,"voo_same_dates_pct":1.,
                "matched_excess_pct":1.,"buy_date":"2026-05-05"} for i in range(30)]
        output=hub.validate_trades(trades)
        self.assertEqual(output["n"],30)
        # A retrospective statistical screen still does not authorise live trades.
        self.assertTrue(output["passes_historical_gate"])

    def test_fund_scores_use_actual_live_etf_windows(self):
        d=fixture()
        def rec(n):
            return {"annual_twr_pct":n,"max_drawdown_pct":-20}
        meta={x:{"category":"Test ETF","source":"https://example.com"} for x in ("VOO","SPMO")}
        est={"latest_completed_us_market_day":str(d.index[-1].date()),"tickers":["VOO","SPMO"],
             "ticker_metadata":meta,
             "windows":{
              k:{"returns":{"VOO":rec(8),"SPMO":rec(15)},
              "diagnostics":{"VOO":{"returns_30bps":rec(8)},
               "SPMO":{"historically_exceeds_voo_after_10bps":True,
                       "returns_30bps":rec(14),"annual_advantage_over_voo_pp":5,
                       "beta_to_voo":1,"paired_active_uncertainty":{}}}}
              for k in ("current_xmmo","recent_2022")}}
        # synthetic flat prices are not in positive trend, so should not fabricate a BUY
        fund=hub.fund_ideas(est,d)
        self.assertEqual(fund[0]["status"],"WATCH — PRICE TREND WEAK")

    def test_calendar_last_sell_date_after_next_open(self):
        nextday,sell=hub.estimated_exit_date("2026-10-23")
        self.assertEqual(nextday,"2026-10-26")
        self.assertGreater(sell,nextday)

if __name__=="__main__":unittest.main()
