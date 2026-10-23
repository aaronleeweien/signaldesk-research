"""Institutional quant-statistics regression tests using synthetic returns."""
import unittest
import numpy as np
import pandas as pd
from research import institutional_v4 as q

def details(month_values):
    days=pd.bdate_range("2022-01-03",periods=len(month_values))
    return {"daily_dates":[str(d.date()) for d in days],
       "daily_returns":[float(x) for x in month_values]}

class InstitutionalMethodsTests(unittest.TestCase):
    def test_monthly_compounding_excludes_contributions(self):
        days=pd.bdate_range("2022-01-03","2022-03-31")
        x={"daily_dates":[str(t.date()) for t in days],"daily_returns":[0. for t in days]}
        v=q.monthly_series(x)
        self.assertEqual(len(v),3)
        self.assertAlmostEqual(float(v.sum()),0.,places=9)
    def test_bootstrap_no_alpha_for_identical_returns(self):
        dates=pd.date_range("2019-01-31",periods=80,freq="ME")
        a=pd.Series(np.linspace(-.04,.05,len(dates)),index=dates)
        ci=q.bootstrap_excess(a,a)
        self.assertAlmostEqual(ci["annual_active_return_estimate_pct"],0.)
        self.assertFalse(ci["statistical_edge_90pct"])
    def test_regression_beta_for_linear_exposure(self):
        dates=pd.date_range("2019-01-31",periods=96,freq="ME")
        x=pd.Series(np.sin(np.arange(96)/3.)*.05,index=dates)
        y=0.002+1.5*x
        r=q.cashflow_regression(y,x)
        self.assertAlmostEqual(r["monthly_beta"],1.5,places=3)
        self.assertAlmostEqual(r["alpha_annual_pct"],2.4,places=3)
    def test_bootstrap_detects_strong_consistent_difference(self):
        dates=pd.date_range("2019-01-31",periods=72,freq="ME")
        x=pd.Series(np.zeros(72),index=dates)
        y=pd.Series(np.full(72,.01),index=dates)
        ci=q.bootstrap_excess(y,x)
        self.assertGreater(ci["90pct_ci_low_pct"],10.)
        self.assertTrue(ci["statistical_edge_90pct"])
    def test_tail_risk_has_valid_range(self):
        r=np.array([.01]*160+[-.03]*60+[.0]*40)
        v=q.other_risk(details(r))
        self.assertLess(v["daily_expected_shortfall_95_pct"],0.)
        self.assertLessEqual(v["positive_months_pct"],100.)
if __name__=="__main__":unittest.main()
