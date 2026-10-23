"""Regression tests for SignalDesk return arithmetic and execution timing.
Run: python -m unittest discover -s tests
"""
import sys
import unittest
from pathlib import Path
import numpy as np
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import engine

class ReturnAccountingTests(unittest.TestCase):
    def test_contributions_do_not_inflate_time_weighted_return(self):
        ix=pd.bdate_range("2021-01-01",periods=265)
        opens=100*1.01**np.arange(len(ix))
        closes=opens*1.01
        prices=pd.DataFrame({"Open":opens,"Close":closes},index=ix)
        signal=pd.Series(1.,index=ix)
        original=engine.COST
        try:
            engine.COST=0.
            result=engine.backtest(prices,signal,str(ix[1].date()),str(ix[-1].date()))
        finally:
            engine.COST=original
        daily=((1.01**(len(result["curve"])) )-1)
        self.assertAlmostEqual(result["curve"][-1],1+daily,places=6)
        self.assertGreater(result["deposited"],engine.INITIAL)

    def test_flat_prices_have_no_false_profit(self):
        ix=pd.bdate_range("2021-01-01",periods=265)
        data=pd.DataFrame({"Open":100.,"Close":100.},index=ix)
        signal=pd.Series(1.,index=ix)
        before=engine.COST
        try:
            engine.COST=0.
            result=engine.backtest(data,signal,str(ix[1].date()),str(ix[-1].date()))
        finally:
            engine.COST=before
        self.assertAlmostEqual(result["end"],result["deposited"],places=2)
        self.assertAlmostEqual(result["annual"],0.,places=4)

if __name__=="__main__":
    unittest.main()
