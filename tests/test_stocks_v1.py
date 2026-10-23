"""Stock opportunity backtest controls (synthetic, no market data calls)."""
import unittest
import numpy as np
import pandas as pd
from research import stocks_v1 as q

def fake(rows=700):
    ix=pd.bdate_range("2020-01-01",periods=rows)
    dic={}
    for n,sym in enumerate(q.TICKERS):
        vals=np.full(rows,100+n,dtype=float)
        dic[(sym,"Open")]=pd.Series(vals,index=ix)
        dic[(sym,"Close")]=pd.Series(vals,index=ix)
    return pd.concat(dic,axis=1)

class StockEngineTests(unittest.TestCase):
    def test_contributions_flat_prices_zero_profit(self):
        d=fake()
        plans=q.plans(d)
        report=q.backtest(d,plans["VOO DCA"],"2021-01-05",str(d.index[-1].date()),fee=0.)
        self.assertAlmostEqual(report["ending_usd"],report["total_contributed_usd"],places=2)
        self.assertAlmostEqual(report["annual_twr_pct"],0.,places=3)
    def test_only_previous_completed_session_used(self):
        d=fake()
        a=q.plans(d)
        changed=d.copy()
        for stock in ["NVDA","VOO"]:
            changed.loc[d.index[-1],(stock,"Close")]=9999.
        b=q.plans(changed)
        for key in q.NAMES:self.assertEqual(a[key][-1],b[key][-1])
    def test_weights_sum_to_one(self):
        d=fake()
        plans=q.plans(d)
        for name in q.NAMES:
            for v in plans[name][260::25]:
                self.assertAlmostEqual(sum(v.values()),1.,places=6)
                self.assertTrue(all(x>=0 for x in v.values()))
    def test_cost_reduces_returns_on_flat_prices(self):
        d=fake()
        p=q.plans(d)
        start="2021-01-05";end=str(d.index[-1].date())
        free=q.backtest(d,p["VOO DCA"],start,end,fee=0.)
        charged=q.backtest(d,p["VOO DCA"],start,end,fee=.001)
        self.assertLess(charged["ending_usd"],free["ending_usd"])

if __name__=="__main__":unittest.main()
