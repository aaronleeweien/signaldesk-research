"""Synthetic tests for frozen research protocols and prospective paper-account state."""
import tempfile
import unittest
from datetime import datetime,timezone
from pathlib import Path
from unittest.mock import patch
import numpy as np
import pandas as pd
from research import daily_scanner as scanner
from research import validation_protocol as protocol
from research import forward_shadow as fwd

def bars(n=650):
    idx=pd.bdate_range("2018-01-01",periods=n)
    cols={}
    for i,name in enumerate(scanner.ASSETS):
        px=np.full(n,100.+i)
        cols[name,"Open"]=pd.Series(px,index=idx)
        cols[name,"Close"]=pd.Series(px,index=idx)
    return pd.concat(cols,axis=1)

class ProtocolControlsTests(unittest.TestCase):
    def test_multiple_independent_fixed_rules_registered(self):
        frame=bars()
        old,_=scanner.daily_plan(frame.xs("Close",level=1,axis=1))
        plans=protocol.plans(frame.xs("Close",level=1,axis=1),old)
        self.assertGreaterEqual(len(plans),7)
        self.assertEqual(plans["SPMO SMA200"][-1],{"SHY":1.})
        for k,v in plans.items():
            self.assertEqual(len(v),len(frame))
            self.assertAlmostEqual(sum(v[-1].values()),1.)

    def test_preserve_prior_signals_when_new_close_changes(self):
        frame=bars()
        old,_=scanner.daily_plan(frame.xs("Close",level=1,axis=1))
        a=protocol.plans(frame.xs("Close",level=1,axis=1),old)
        changed=frame.copy()
        changed.loc[frame.index[-1],("SPMO","Close")]=999.
        new,_=scanner.daily_plan(changed.xs("Close",level=1,axis=1))
        b=protocol.plans(changed.xs("Close",level=1,axis=1),new)
        for k in a:self.assertEqual(a[k][-2],b[k][-2])

    def test_bootstrap_has_no_edge_for_equal_series(self):
        data=np.array([.01,-.02,.01,.03]*15)
        stats=protocol.paired_bootstrap(data,data)
        self.assertFalse(stats["interval_excludes_zero"])
        self.assertAlmostEqual(stats["annual_mean_active_pct"],0.,places=9)

class ForwardLedgerTests(unittest.TestCase):
    def test_no_leverage_after_fee_and_cashflow(self):
        start=fwd.new_state()["accounts"]["SPMO DCA"]
        result,fills=fwd.pure_execute(start,{"SPMO":1.},
             {"SPMO":100.},{"SPMO":110.},"2026-10-26")
        self.assertGreater(result["nav_usd"],start["nav_usd"])
        self.assertGreater(result["cash_usd"],-.01)
        self.assertEqual(fills[0]["side"],"BUY")
        self.assertLess(result["shares"]["SPMO"],20.)
        self.assertGreater(result["fees_paid_usd"],0.)

    def test_friday_to_monday_schedule(self):
        self.assertEqual(fwd.next_us_business_day("2026-10-23"),"2026-10-26")
        early=datetime(2026,10,24,2,0,tzinfo=timezone.utc)
        late=datetime(2026,10,26,16,0,tzinfo=timezone.utc)
        self.assertTrue(fwd.eligible_for_future("2026-10-23",early)[0])
        self.assertFalse(fwd.eligible_for_future("2026-10-23",late)[0])

    def test_forward_history_is_only_recorded_after_next_real_session(self):
        days=pd.to_datetime(["2026-10-23","2026-10-26"])
        out={}
        for name in scanner.ASSETS:
            out[name,"Open"]=pd.Series([100.,100.],index=days)
            out[name,"Close"]=pd.Series([100.,104.],index=days)
        data=pd.concat(out,axis=1)
        one={key:[{"SPMO":1.}] for key in fwd.NAMES}
        two={key:[{"SPMO":1.},{"SPMO":1.}] for key in fwd.NAMES}
        with tempfile.TemporaryDirectory() as folder:
            with patch.object(fwd,"FILE",Path(folder)/"ledger.json"), patch.object(fwd,"render",lambda x:None):
                first=fwd.update(data.iloc[:1],one,
                       now=datetime(2026,10,24,1,0,tzinfo=timezone.utc))
                self.assertEqual(first["valid_forward_sessions"],0)
                self.assertEqual(first["accounts"]["SPMO DCA"]["orders"],0)
                second=fwd.update(data,two,
                       now=datetime(2026,10,26,22,0,tzinfo=timezone.utc))
                self.assertEqual(second["valid_forward_sessions"],1)
                self.assertGreater(second["accounts"]["SPMO DCA"]["orders"],0)
                replay=fwd.update(data,{key:[{"VOO":1.}]*2 for key in fwd.NAMES},
                       now=datetime(2026,10,27,1,0,tzinfo=timezone.utc))
                self.assertEqual(replay["signal_history"],second["signal_history"])
                self.assertEqual(replay["valid_forward_sessions"],1)

if __name__=="__main__":unittest.main()
