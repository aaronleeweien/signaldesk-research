"""Factor ETF backtest regression checks. No external data download needed."""
import unittest
import numpy as np
import pandas as pd
from research import factor_etf as q

def fixture(n=700):
    ix=pd.bdate_range("2018-01-01",periods=n)
    cols={}
    for j,ticker in enumerate(q.SYMS):
        flat=np.full(n,100.+j,dtype=float)
        cols[ticker,"Open"]=pd.Series(flat,index=ix)
        cols[ticker,"Close"]=pd.Series(flat,index=ix)
    return pd.concat(cols,axis=1)

class ETFStrategyTests(unittest.TestCase):
    def test_flat_dca_only_contributions(self):
        d=fixture()
        p=q.decisions(d)
        r=q.simulate(d,p["SPMO DCA"],"2018-10-01",str(d.index[-1].date()),fee=0)
        self.assertAlmostEqual(r["account_value_usd"],r["total_deposits_usd"],places=2)
        self.assertAlmostEqual(r["annual_twr_pct"],0.,places=2)
    def test_unseen_final_close_cannot_change_todays_decision(self):
        d=fixture()
        a=q.decisions(d)
        altered=d.copy()
        altered.loc[d.index[-1],("SPMO","Close")]=10000.
        altered.loc[d.index[-1],("VOO","Close")]=50000.
        b=q.decisions(altered)
        for name in q.MODEL_NAMES:
            self.assertEqual(a[name][-1],b[name][-1])
    def test_weights_and_leverage(self):
        d=fixture()
        a=q.decisions(d)
        for m in q.MODEL_NAMES:
            for w in a[m][270::25]:
                self.assertAlmostEqual(sum(w.values()),1.,places=7)
                self.assertTrue(all(z>=0 for z in w.values()))
    def test_fees_hurt_flat_buy_and_hold(self):
        d=fixture()
        p=q.decisions(d)
        st="2018-10-01";end=str(d.index[-1].date())
        free=q.simulate(d,p["SPMO DCA"],st,end,fee=0)
        charged=q.simulate(d,p["SPMO DCA"],st,end,fee=.003)
        self.assertLess(charged["account_value_usd"],free["account_value_usd"])
if __name__=="__main__":unittest.main()
