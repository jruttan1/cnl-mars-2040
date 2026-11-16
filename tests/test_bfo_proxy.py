"""Arithmetic checks for an explicitly unverified organ-dose proxy, not physics validation."""
import unittest
import numpy as np
import pandas as pd
from bfo_proxy import (build_bfo_proxy, bfo_interval_dose, KING_POINT_MGY,
                       KING_BFO_MGY, KING_BFO_MGY_EQ)
from radiation_model import ROOT, sha256


class BFOProxyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.frame = build_bfo_proxy()

    def test_2003_scope_units_and_event_conservation(self):
        f = self.frame
        self.assertEqual(len(f), 2*9*336)
        self.assertEqual(set(f.historical_template), {'october_2003_goes10'})
        self.assertTrue(f.shielding_g_cm2.eq(20).all())
        self.assertFalse(f.for_operational_decisions.any())
        self.assertTrue(f.reference_status.eq('user_supplied_not_verified_in_repository').all())
        self.assertTrue(f.data_quality.eq('observed_template_hour').all())
        for _, g in f.groupby(['scenario', 'timing_variant']):
            np.testing.assert_array_equal(g.hour, np.arange(336))
            self.assertAlmostEqual(g.normalized_bin_weight.sum(), 1, places=12)
            for unit, reference in [('mGy', KING_BFO_MGY), ('mGy_Eq', KING_BFO_MGY_EQ)]:
                expected = g.event_absorbed_dose_mGy.iloc[0] * reference / KING_POINT_MGY
                self.assertAlmostEqual(g[f'bfo_proxy_rate_{unit}_h'].sum(), expected, places=10)
                self.assertTrue(g[f'bfo_proxy_cumulative_end_{unit}'].is_monotonic_increasing)
                self.assertAlmostEqual(g[f'bfo_proxy_cumulative_end_{unit}'].iloc[-1], expected, places=10)

    def test_seven_hour_and_fractional_queries(self):
        for (scenario, variant), g in self.frame.groupby(['scenario','timing_variant']):
            for start in (0, 16, 329, 328.5):
                result = bfo_interval_dose(g, scenario, start, start+7, variant)
                for unit in ('mGy', 'mGy_Eq'):
                    c = np.r_[g[f'bfo_proxy_cumulative_start_{unit}'],g[f'bfo_proxy_cumulative_end_{unit}'].iloc[-1]]
                    expected = np.interp(start+7, np.arange(337), c)-np.interp(start, np.arange(337), c)
                    self.assertAlmostEqual(result[f'bfo_proxy_{unit}'], expected, places=10)

    def test_no_other_shielding_or_extrapolation(self):
        scenario = 'SAPPHIRE-1-in-100'
        for a,b in [(-1,6),(330,337),(23,16)]:
            with self.assertRaises(ValueError): bfo_interval_dose(self.frame,scenario,a,b)
        wrong=self.frame.copy();wrong['shielding_g_cm2']=.4
        with self.assertRaises(ValueError): bfo_interval_dose(wrong,scenario,0,7)
        wrong=self.frame.copy();wrong['reference_bfo_gray_equivalent_mGy_Eq']=48.20886
        with self.assertRaises(ValueError): bfo_interval_dose(wrong,scenario,0,7)

    def test_template_changes_timing_only_and_preserves_core(self):
        paths = ['data/processed/mission_radiation_environment.csv', 'outputs/mission_radiation_environment.csv',
                 'sim/mission_simulator.py','sim/strategies.py']
        before = {p:sha256(ROOT/p) for p in paths}
        other = build_bfo_proxy('august_1972')
        keys=['scenario','timing_variant']
        columns=['bfo_proxy_event_total_mGy','bfo_proxy_event_total_mGy_Eq']
        pd.testing.assert_frame_equal(self.frame.groupby(keys)[columns].first(), other.groupby(keys)[columns].first())
        a=bfo_interval_dose(self.frame,'SAPPHIRE-1-in-100',16,23)
        b=bfo_interval_dose(other,'SAPPHIRE-1-in-100',16,23)
        self.assertNotEqual(a,b)
        self.assertEqual(before, {p:sha256(ROOT/p) for p in paths})


if __name__=='__main__': unittest.main()
