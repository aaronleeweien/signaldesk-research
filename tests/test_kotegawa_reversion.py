"""BNF-inspired mean-reversion rule invariants. Only synthetic historical prices."""
import unittest
import numpy as np
import pandas as pd
from research import kotegawa_reversion as r

def fake_bars(n=650):
    idx=pd.bdate_range("2019-01-02",periods=n)
    b=100*np.power(0.9999,np.arange(n))
    s=np.full(n,100.)
    for k in (210,310,410,510):
        s[k]=78.
        s[k+1]=80.
        s[k+2]=85.
        s[k+3]=96.
        s[k+4]=102.
    data={}
    for t,values in (("VOO",b),("TEST",s)):
        data[t,"Close"]=pd.Series(values,index=idx)
        data[t,"Open"]=pd.Series(values,index=idx)
    return pd.concat(data,axis=1)

class KotegawaResearchTests(unittest.TestCase):
    def test_entry_reacts_to_sudden_oversold_drop_only_when_market_weak(self):
        f=fake_bars()
        signal,mean,disc=r.signals(f["TEST","Close"],f["VOO","Close"])
        self.assertTrue(signal[210])
        self.assertLessEqual(disc[210],-.10)
        self.assertFalse(signal[211])
        self.assertEqual(signal[209],False)

    def test_recovered_stock_sells_only_after_observed_recovery(self):
        f=fake_bars()
        trades,last=r.roundtrip_trades(f,"TEST")
        self.assertGreater(len(trades),0)
        for trade in trades:
            self.assertGreater(trade["sell_date"],trade["buy_date"])
            self.assertGreaterEqual(trade["sessions_held"],1)
            self.assertLessEqual(trade["sessions_held"],r.MAX_DAYS)
        self.assertFalse(any(x["entry_price"]<=0 for x in trades))

    def test_future_price_change_cannot_change_earlier_signal(self):
        f=fake_bars()
        s=f["TEST","Close"].copy()
        b=f["VOO","Close"]
        first=r.signals(s,b)[0]
        s.iloc[-1]=9000
        second=r.signals(s,b)[0]
        self.assertTrue(np.array_equal(first[:-1],second[:-1]))

    def test_costs_reduce_returns_and_account_does_not_borrow(self):
        f=fake_bars()
        low=r.simulate_account(f,"TEST",cost=0)
        expensive=r.simulate_account(f,"TEST",cost=.01)
        self.assertGreater(low["strategy_final_account_usd"],expensive["strategy_final_account_usd"])
        self.assertGreater(low["voo_final_account_usd"],expensive["voo_final_account_usd"])
        self.assertGreater(low["total_deposits_usd"],r.INITIAL)
        self.assertGreater(low["strategy_final_account_usd"],0)

    def test_ticker_comparison_does_not_authorize_real_trading(self):
        f=fake_bars()
        result=r.compare_market(f,["TEST"],str(f.index[-1].date()))
        self.assertEqual(result["screened_prices_for_assets"],1)
        self.assertTrue(result["no_live_approval"])
        self.assertFalse(any(row.get("real_money_approved") for row in result["paper_candidates"]))

if __name__=="__main__":unittest.main()
