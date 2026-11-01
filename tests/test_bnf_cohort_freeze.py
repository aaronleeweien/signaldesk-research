"""Only synthetic data: freezing must be prospective, complete, and immutable."""
import unittest
from datetime import datetime, timezone
from research.bnf_cohort_freeze import freeze, VERSION


def example():
    return {
        "protocol": "bnf_inspired_mean_reversion_v1_20261024",
        "no_live_approval": True,
        "paper_entry_executable": False,
        "market_date": "2026-11-02",
        "screened_tickers": ["PLTR", "FROG", "AMD"],
        "screened_prices_for_assets": 3,
    }


class CohortFreezeTests(unittest.TestCase):
    def test_registration_is_preopen_and_immutable(self):
        now = datetime(2026, 11, 3, 2, 0, tzinfo=timezone.utc)
        registered, created = freeze(example(), now)
        self.assertTrue(created)
        self.assertEqual(registered["frozen_tickers"], ["AMD", "FROG", "PLTR"])
        self.assertFalse(registered["paper_execution_enabled"])
        self.assertFalse(registered["real_money_approved"])
        self.assertEqual(registered["valid_forward_sessions"], 0)
        changed = example()
        changed["screened_tickers"] = ["XYZ", "ABC"]
        changed["screened_prices_for_assets"] = 2
        again, created = freeze(changed, now, registered)
        self.assertFalse(created)
        self.assertEqual(again, registered)

    def test_refuses_late_or_missing_or_mismatched_universe(self):
        now = datetime(2026, 11, 3, 16, 0, tzinfo=timezone.utc)
        with self.assertRaisesRegex(ValueError, "Late"):
            freeze(example(), now)
        bad = example()
        bad["screened_tickers"] = ["AMD", "AMD", "FROG"]
        with self.assertRaises(ValueError):
            freeze(bad, datetime(2026, 11, 3, 2, tzinfo=timezone.utc))
        bad = example()
        bad["screened_prices_for_assets"] = 88
        with self.assertRaisesRegex(ValueError, "count"):
            freeze(bad, datetime(2026, 11, 3, 2, tzinfo=timezone.utc))
        bad = example()
        bad["paper_entry_executable"] = True
        with self.assertRaisesRegex(ValueError, "Unjournaled"):
            freeze(bad, datetime(2026, 11, 3, 2, tzinfo=timezone.utc))

    def test_rejects_unknown_existing_version(self):
        with self.assertRaisesRegex(ValueError, "unexpected version"):
            freeze(example(), datetime(2026, 11, 3, 2, tzinfo=timezone.utc),
                   {"version": VERSION + "_modified"})


if __name__ == "__main__":
    unittest.main()
