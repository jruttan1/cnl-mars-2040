"""Scientific invariants and boundary cases; run with unittest discovery."""
import json
import tempfile
import unittest
from pathlib import Path
import numpy as np
import pandas as pd
import radiation_model as model


class RadiationModelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cfg, cls.mission, cls.profiles, cls.grids, cls.report = model.build_historical_environment()

    def test_exact_raw_targets_and_units(self):
        references = self.report['references']
        for location, dose, job, depth in [
            ('external_eva_reference', 59997.39, 'job_1', 0.4),
            ('spacecraft_cabin_reference', 185.2349, 'job_3', 20.0),
        ]:
            ref = references[location]
            self.assertEqual(ref['event_absorbed_dose_mGy'], dose)
            self.assertEqual(ref['job_name'], job)
            self.assertEqual(ref['shielding_g_cm2'], depth)
            self.assertEqual(ref['tissue_depth_g_cm2'], 0)
            self.assertIn('Dose (mGy)', (model.ROOT/ref['source_path']).read_text())
        # These exports are depth databases, not selected-sphere organ totals.
        np.testing.assert_array_equal(self.grids['external_eva_reference'].dose_value,
                                      self.grids['spacecraft_cabin_reference'].dose_value)

    def test_observations_preserved_and_gaps_flagged(self):
        hourly = model.load_hourly()
        self.assertEqual(len(hourly), 264)
        for energy in (10, 30, 60):
            y = hourly[f'proton_flux_gt{energy}_MeV'].to_numpy()
            self.assertEqual(np.isnan(y).sum(), 8)
            for method in self.cfg['gap_methods']:
                filled = model.fill_gaps(y, method)
                np.testing.assert_array_equal(filled[~np.isnan(y)], y[~np.isnan(y)])
                self.assertTrue(np.isfinite(filled).all())
                self.assertTrue((filled >= 0).all())
        for method in self.cfg['gap_methods']:
            with self.assertRaises(ValueError):
                model.fill_gaps([np.nan, 1, 2], method)
        np.testing.assert_allclose(model.fill_gaps([1,np.nan,9], 'linear'), [1,5,9])
        np.testing.assert_allclose(model.fill_gaps([1,np.nan,9], 'log_linear'), [1,3,9])

    def test_full_record_conservation(self):
        self.assertEqual(self.mission.member_id.nunique(), 9)
        for _, rows in self.profiles.groupby('member_id'):
            self.assertEqual(len(rows), 264)
            self.assertAlmostEqual(rows.normalized_bin_weight.sum(), 1, places=12)
            for ref in self.report['references'].values():
                total = ref['event_absorbed_dose_mGy']
                self.assertAlmostEqual(np.sum(rows.normalized_bin_weight.to_numpy()*total), total, places=8)

    def test_cumulative_and_seven_hour_integration(self):
        for _, rows in self.mission.groupby(['location','member_id']):
            rows = rows.sort_values('hour_since_emergency')
            self.assertEqual(len(rows), 72)
            self.assertEqual(rows.hour_since_emergency.iloc[0], 0)
            self.assertEqual(rows.hour_end_since_emergency.iloc[-1], 72)
            c = np.r_[rows.cumulative_absorbed_dose_mGy, rows.cumulative_end_absorbed_dose_mGy.iloc[-1]]
            self.assertEqual(c[0], 0)
            self.assertTrue((np.diff(c) >= 0).all())
            np.testing.assert_allclose(np.diff(c), rows.absorbed_dose_rate_mGy_h, rtol=1e-11, atol=1e-10)
            for start in (0, 17.25, 65):
                expected = np.interp(start+7, np.arange(73), c)-np.interp(start, np.arange(73), c)
                self.assertAlmostEqual(model.seven_hour_exposure(rows, start), expected, places=8)
            self.assertAlmostEqual(model.accumulated_dose(rows, 0, 72), c[-1], places=8)
            with self.assertRaises(ValueError):
                model.seven_hour_exposure(rows, 66)
        with self.assertRaises(ValueError):
            model.seven_hour_exposure(self.mission, 0)

    def test_locations_share_timeline_and_bands(self):
        pivot = self.mission.pivot(index=['member_id','hour_since_emergency'], columns='location', values='absorbed_dose_rate_mGy_h')
        np.testing.assert_allclose(pivot.external_eva_reference/pivot.spacecraft_cabin_reference, 59997.39/185.2349)
        for col in ['absorbed_dose_rate_mGy_h','cumulative_absorbed_dose_mGy','cumulative_end_absorbed_dose_mGy']:
            self.assertTrue(self.mission[col].between(self.mission[col+'_sensitivity_lower'], self.mission[col+'_sensitivity_upper']).all())

    def test_window_change_preserves_normalization(self):
        cfg = json.loads(json.dumps(self.cfg))
        cfg['emergency_start_utc'] = '1972-08-04T01:00:00Z'
        cfg['emergency_duration_hours'] = 48
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'config.json'; path.write_text(json.dumps(cfg))
            _, mission, profiles, _, _ = model.build_historical_environment(path)
        self.assertEqual(len(mission), 48*2*9)
        np.testing.assert_array_equal(profiles.normalized_bin_weight, self.profiles.normalized_bin_weight)
        cfg['emergency_start_utc'] = '1972-08-20T00:00:00Z'
        with self.assertRaises(ValueError):
            model.select_window(model.load_hourly(), cfg)
        cfg['environments']['spacecraft_cabin_reference']['shielding_g_cm2'] = 19.9
        with self.assertRaises(ValueError):
            model.load_historical_shielding(cfg)

    def test_export_matches_calculated_data(self):
        actual = pd.read_csv(model.ROOT/'outputs/model/historical/mission_radiation_environment.csv')
        self.assertEqual(len(actual), len(self.mission))
        for col in ['absorbed_dose_rate_mGy_h','cumulative_absorbed_dose_mGy','normalized_bin_weight']:
            np.testing.assert_allclose(actual[col], self.mission[col], rtol=1e-12, atol=1e-12)
        self.assertFalse(actual.duplicated(['location','member_id','hour_since_emergency']).any())


if __name__ == '__main__':
    unittest.main()
