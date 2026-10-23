"""Daily momentum scanner synthetic-data checks; no network needed."""
import unittest
import numpy as np
import pandas as pd
from research import daily_scanner as s

def fixture(n=700):
    dates=pd.bdate_range("2018-01-01",periods=n)
    out={}
    for k,ticker in enumerate(s.ASSETS):
        vals=np.full(n,100.+k,dtype=float)
        out[ticker,"Open"]=pd.Series(vals,index=dates)
        out[ticker,"Close"]=pd.Series(vals,index=dates)
    return pd.concat(out,axis=1)

class ScannerTests(unittest.TestCase):
    def test_flat_market_does_not_invent_entries(self):
        d=fixture()
        plans,trace=s.daily_plan(d.xs("Close",level=1,axis=1))
        self.assertEqual(plans[-1],{"SHY":1.0})
        self.assertEqual(trace[-1]["entered"],[])
        report=s.backtest(d,plans,"2019-01-02",str(d.index[-1].date()),fee=0.)
        self.assertAlmostEqual(report["annual_pct"],0.,places=3)
        self.assertAlmostEqual(report["end_usd"],report["contributed_usd"],places=2)

    def test_future_close_does_not_change_previous_signal(self):
        d=fixture()
        a,_=s.daily_plan(d.xs("Close",level=1,axis=1))
        d2=d.copy()
        d2.loc[d2.index[-1],("SPMO","Close")]=5000.
        b,_=s.daily_plan(d2.xs("Close",level=1,axis=1))
        self.assertEqual(a[-2],b[-2])

    def test_strong_breakout_can_create_paper_entry(self):
        d=fixture()
        values=100*np.power(1.002,np.arange(len(d)))
        d.loc[:,("SPMO","Close")]=values
        d.loc[:,("SPMO","Open")]=values
        plan,trace=s.daily_plan(d.xs("Close",level=1,axis=1))
        self.assertIn("SPMO",plan[-1])
        self.assertLessEqual(len([x for x in plan[-1] if x!="SHY"]),2)
        self.assertAlmostEqual(sum(plan[-1].values()),1.,places=9)

    def test_trading_costs_reduce_flat_dca_value(self):
        d=fixture()
        plan=[{"VOO":1.}]*len(d)
        a=s.backtest(d,plan,"2019-01-02",str(d.index[-1].date()),fee=0.)
        b=s.backtest(d,plan,"2019-01-02",str(d.index[-1].date()),fee=.003)
        self.assertLess(b["end_usd"],a["end_usd"])

    def test_exit_after_loss_of_momentum(self):
        d=fixture()
        values=np.r_[100*np.power(1.003,np.arange(500)),
            100*np.power(1.003,499)*np.power(.98,np.arange(1,201))]
        d.loc[:,("SPMO","Close")]=values
        d.loc[:,("SPMO","Open")]=values
        _,info=s.daily_plan(d.xs("Close",level=1,axis=1))
        self.assertTrue(any("SPMO" in item["exited"] for item in info))
if __name__=="__main__":unittest.main()
