"""Conservation and exact interval integration for the standalone EVA chart."""
import importlib.util
from pathlib import Path
import unittest

import numpy as np
import pandas as pd

SPEC = importlib.util.spec_from_file_location('eva_chart', Path(__file__).resolve().parents[1] / 'charts/09_anatomical_eva_exposure.py')
EVA = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(EVA)


class AnatomicalEvaTests(unittest.TestCase):
    def test_fractional_overlap(self):
        frame = pd.DataFrame({'hour': [0, 1, 2], 'hour_end': [1, 2, 3],
                              'bfo_absorbed_dose_rate_mGy_h': [2, 4, 8]})
        self.assertEqual(EVA.interval_dose(frame, .5, 2.25), 7)
        self.assertEqual(EVA.interval_dose(frame, 1, 1), 0)
        with self.assertRaises(ValueError):
            EVA.interval_dose(frame, -1, 1)

    def test_all_member_totals_and_severity_scaling(self):
        frame = EVA.build_profiles()
        for _, member in frame.groupby(['historical_template', 'return_period_years', 'timing_variant']):
            member = member.sort_values('hour')
            self.assertAlmostEqual(EVA.interval_dose(member, member.hour.min(), member.hour_end.max()),
                                   member.event_bfo_absorbed_dose_mGy.iloc[0], places=9)
            self.assertTrue(np.all(np.diff(member.continuous_eva_cumulative_end_mGy) >= 0))
        for _, member in frame.groupby(['historical_template', 'timing_variant']):
            small = member[member.return_period_years.eq(100)].sort_values('hour')
            large = member[member.return_period_years.eq(1000)].sort_values('hour')
            np.testing.assert_allclose(large.bfo_absorbed_dose_rate_mGy_h.to_numpy(),
                                       small.bfo_absorbed_dose_rate_mGy_h.to_numpy() * 723.7 / 415.1)

    def test_rolling_window_edges(self):
        frame = pd.DataFrame({'historical_template': ['test'] * 10, 'return_period_years': [100] * 10,
                              'timing_variant': ['central'] * 10, 'hour': np.arange(10),
                              'hour_end': np.arange(1, 11), 'bfo_absorbed_dose_rate_mGy_h': np.ones(10) * 2})
        windows = EVA.build_eva_windows(frame, 7)
        self.assertEqual(windows.eva_start_hour.tolist(), [0, 1, 2, 3])
        self.assertTrue(windows.bfo_eva_absorbed_dose_mGy.eq(14).all())


if __name__ == '__main__':
    unittest.main()
