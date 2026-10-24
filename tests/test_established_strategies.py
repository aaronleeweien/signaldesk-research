"""Independent synthetic accounting checks: Established Strategies research."""
import unittest
import pandas as pd
import numpy as np
from research import established_strategies as m

def frame(n=710):
    dates=pd.bdate_range("2017-01-02",periods=n)
    fields={}
    for t in m.TICKERS:
        v=np.full(n,100.,dtype=float)
        fields[t,"Open"]=pd.Series(v,index=dates)
        fields[t,"Close"]=pd.Series(v,index=dates)
    return pd.concat(fields,axis=1)

class EstablishedStrategiesTests(unittest.TestCase):
    def test_flat_price_dca_no_fake_growth(self):
        d=frame()
        r=m.simulate(d,"VOO","2018-01-02",str(d.index[-1].date()),fee_bps=0)
        self.assertAlmostEqual(r["ending_usd"],r["total_deposits_usd"],places=2)
        self.assertAlmostEqual(r["annual_twr_pct"],0.,places=2)
        self.assertEqual(r["orders"],len(set(d.loc["2018-01-02":].index.to_period("M"))))

    def test_fees_reduce_portfolio_value(self):
        d=frame()
        begin="2018-01-02";end=str(d.index[-1].date())
        zero=m.simulate(d,"SPMO",begin,end,0)
        ten=m.simulate(d,"SPMO",begin,end,10)
        thirty=m.simulate(d,"SPMO",begin,end,30)
        self.assertGreater(zero["ending_usd"],ten["ending_usd"])
        self.assertGreater(ten["ending_usd"],thirty["ending_usd"])
        self.assertEqual(ten["orders"],thirty["orders"])

    def test_no_lookahead_and_nonleverage(self):
        d=frame()
        begin="2018-01-02";end=str(d.index[-2].date())
        first=m.simulate(d,"VOO",begin,end,10)
        changed=d.copy()
        changed.loc[d.index[-1],("VOO","Close")]=9000.
        second=m.simulate(changed,"VOO",begin,end,10)
        self.assertEqual(first,second)

    def test_positive_price_appreciation_generates_gain(self):
        d=frame()
        n=len(d)
        tr=100*np.power(1.001,np.arange(n))
        d.loc[:,("XMMO","Open")]=tr
        d.loc[:,("XMMO","Close")]=tr
        a=m.simulate(d,"XMMO","2018-01-02",str(d.index[-1].date()),10)
        b=m.simulate(d,"VOO","2018-01-02",str(d.index[-1].date()),10)
        self.assertGreater(a["annual_twr_pct"],b["annual_twr_pct"])

    def test_bootstrap_is_not_edge_when_funds_identical(self):
        ix=pd.period_range("2017-01","2021-12",freq="M")
        z=pd.Series(np.tile([.01,.02,-.02,.005],15),index=ix)
        a=m.block_bootstrap(z,z)
        self.assertTrue(a["enough_months"])
        self.assertTrue(a["zero_in_ci90"])
        self.assertAlmostEqual(a["observed_average_active_pp_ann"],0.,places=4)

    def test_original_xmmo_methodology_warning(self):
        self.assertEqual(m.METADATA["XMMO"]["current_index_from"],"2019-06-21")
        self.assertEqual(dict((a,b) for a,b,_ in m.WINDOWS)["current_xmmo"],"2019-06-24")

if __name__=="__main__":unittest.main()
