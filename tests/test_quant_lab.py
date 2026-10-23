"""Synthetic checks: no look-ahead and no phantom returns from contributions."""
import unittest
import numpy as np
import pandas as pd
from research import quant_lab as q

def make_data(rows=800):
    ix=pd.bdate_range("2020-01-01",periods=rows)
    c={}
    for j,asset in enumerate(q.ASSETS):
        price=np.full(rows,100.+j)
        c[(asset,"Open")]=pd.Series(price,index=ix)
        c[(asset,"Close")]=pd.Series(price,index=ix)
    return pd.concat(c,axis=1)

class StrategyAccountingTests(unittest.TestCase):
    def test_flat_no_fees_equals_contributions(self):
        data=make_data()
        plans,features=q.weights(data)
        result=q.simulate(data,plans["VOO DCA"],"2021-01-04",str(data.index[-1].date()),fee=0)
        self.assertAlmostEqual(result["final_usd"],result["contributed_usd"],places=2)
        self.assertAlmostEqual(result["annual_return_pct"],0,places=2)
    def test_last_session_prices_cannot_change_opening_model_target(self):
        data=make_data()
        orig,_=q.weights(data)
        changed=data.copy()
        changed.loc[changed.index[-1],("VOO","Close")]=999.
        changed.loc[changed.index[-1],("XLK","Close")]=999.
        revised,_=q.weights(changed)
        for model in q.MODEL_NAMES:
            self.assertEqual(orig[model][-1],revised[model][-1])
    def test_portfolio_never_exceeds_100_percent(self):
        data=make_data()
        planned,_=q.weights(data)
        for name in q.MODEL_NAMES:
            for target in planned[name][300::40]:
                self.assertAlmostEqual(sum(target.values()),1.0,places=6)
                self.assertTrue(all(x>=0 for x in target.values()))
    def test_fees_cannot_improve_flat_market_return(self):
        data=make_data()
        planned,_=q.weights(data)
        base=q.simulate(data,planned["VOO DCA"],"2021-01-04",str(data.index[-1].date()),fee=0)
        with_cost=q.simulate(data,planned["VOO DCA"],"2021-01-04",str(data.index[-1].date()),fee=.003)
        self.assertLess(with_cost["final_usd"],base["final_usd"])

if __name__=="__main__":unittest.main()
