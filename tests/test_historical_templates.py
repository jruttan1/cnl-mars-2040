"""Independent event normalization, selection and mission boundary regressions."""
import unittest
from unittest.mock import patch
import numpy as np
import pandas as pd
import radiation_model as model
from sim.models import Scenario, Astronaut
from sim.assumptions import MissionAssumptions
from sim.mission_simulator import RadiationEnvironment, simulate_mission
from sim.strategies import strategy_a

GOES = 'october_2003_goes10'


class HistoricalTemplates(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.all_data = model.load_baseline(historical_template=None)
        cls.goes = model.load_baseline(historical_template=GOES)
        cls.cfg = model.load_config(historical_template=GOES)
        cls.profiles = model.build_temporal_profiles(cls.cfg)

    def test_goes_complete_and_values_preserved(self):
        data = model.load_hourly(GOES)
        raw = pd.read_csv(model.ROOT/model.HISTORICAL_TEMPLATES[GOES]['path'])
        self.assertEqual(len(data), 336)
        self.assertEqual(str(data.timestamp_utc.iloc[-1]), '2003-11-08 23:00:00+00:00')
        self.assertFalse(self.profiles.is_gap_filled.any())
        for (channel, method), g in self.profiles.groupby(['proxy_threshold_MeV','gap_method']):
            np.testing.assert_array_equal(g.observed_proton_flux, raw[f'proton_flux_gt{channel}_MeV'])
            np.testing.assert_array_equal(g.modeled_proton_flux, g.observed_proton_flux)
            self.assertAlmostEqual(g.normalized_bin_weight.sum(), 1, places=12)
        for _, g in self.profiles.groupby('proxy_threshold_MeV'):
            self.assertTrue(g.groupby('hour_since_event_start').normalized_bin_weight.nunique().eq(1).all())
        self.assertEqual(self.profiles[self.profiles.estimate_type.eq('central')].in_emergency_window.sum(), 72)

    def test_1989_audit_and_disabled_selection(self):
        raw = pd.read_csv(model.ROOT/model.HISTORICAL_TEMPLATES['october_1989']['path'])
        missing = raw.proton_flux_gt10_MeV.isna()
        self.assertEqual(len(raw), 360)
        self.assertEqual(missing.sum(), 96)
        self.assertEqual(missing.groupby(missing.ne(missing.shift()).cumsum()).sum().max(), 29)
        for loader in (model.load_hourly, lambda t: model.load_config(historical_template=t),
                       lambda t: model.load_baseline(historical_template=t)):
            with self.assertRaisesRegex(ValueError, 'disabled'):
                loader('october_1989')

    def test_reject_invalid_goes_data(self):
        raw = pd.read_csv(model.ROOT/model.HISTORICAL_TEMPLATES[GOES]['path'])
        for column, value in [('proton_flux_gt10_MeV', np.nan), ('missing_measurement', 1),
                              ('timestamp_utc', raw.timestamp_utc.iloc[0])]:
            bad = raw.copy(); bad.loc[1, column] = value
            with patch.object(model.pd, 'read_csv', return_value=bad):
                with self.assertRaises(ValueError): model.load_hourly(GOES)

    def test_totals_and_seven_hour_windows_all_depths_and_members(self):
        old = model.load_baseline()
        for (scenario, depth, variant), g in self.goes.groupby(['scenario','shielding_g_cm2','timing_variant']):
            np.testing.assert_array_equal(g.hour, np.arange(336))
            reference = old[old.scenario.eq(scenario)&old.shielding_g_cm2.eq(depth)&old.timing_variant.eq(variant)]
            total = reference.event_absorbed_dose_mGy.iloc[0]
            self.assertAlmostEqual(g.dose_rate_mGy_h.sum(), total, places=8)
            self.assertAlmostEqual(g.normalized_bin_weight.sum(), 1, places=12)
            self.assertTrue(g.cumulative_end_dose_mGy.is_monotonic_increasing)
            c = np.r_[g.cumulative_dose_mGy, g.cumulative_end_dose_mGy.iloc[-1]]
            np.testing.assert_allclose(c[7:]-c[:-7], np.convolve(g.dose_rate_mGy_h, np.ones(7), mode='valid'), rtol=1e-10, atol=1e-8)
            for start in (0, 16, 257, 329, 328.5):
                dose = model.baseline_interval_dose(scenario, depth, start, start+7, variant,
                    baseline=g, historical_template=GOES)
                self.assertAlmostEqual(dose, np.interp(start+7,np.arange(337),c)-np.interp(start,np.arange(337),c), places=8)
            self.assertNotIn('OLTARIS', g.source_path.iloc[0])
            for metric in ('dose_rate_mGy_h','cumulative_end_dose_mGy'):
                self.assertTrue(g[metric].between(g[metric+'_sensitivity_lower'],g[metric+'_sensitivity_upper']).all())

    def test_no_cross_template_mixing_and_default_unchanged(self):
        self.assertEqual(len(self.all_data), 64800)
        self.assertEqual(len(model.load_baseline()), 28512)
        self.assertEqual(set(model.load_baseline().historical_template), {model.DEFAULT_TEMPLATE})
        scenario='SAPPHIRE-1-in-100'
        for template in (model.DEFAULT_TEMPLATE, GOES):
            a=model.baseline_interval_dose(scenario,.4,16,23,baseline=self.all_data,historical_template=template)
            b=model.baseline_interval_dose(scenario,.4,16,23,historical_template=template)
            self.assertEqual(a,b)
        with self.assertRaises(ValueError):
            model.baseline_interval_dose(scenario,.4,330,337,historical_template=GOES)
        # For a complete template there are no invented gap values.
        self.assertTrue(self.goes.data_quality.eq('observed_template_hour').all())

    def test_longer_mission_and_strategy_observation_boundary(self):
        scenario=Scenario(historical_template=GOES,storm_start_hour=329)
        env=RadiationEnvironment(scenario)
        self.assertEqual(env.end_hour,336)
        observations=[]
        def strategy(obs):
            observations.append(obs)
            self.assertFalse(hasattr(obs,'historical_template'))
            self.assertFalse(hasattr(obs,'dose_rate_mGy_h'))
            self.assertFalse(hasattr(obs,'accumulated_radiation'))
            return strategy_a(obs)
        result=simulate_mission(strategy,scenario,[Astronaut('A')],['communications'],MissionAssumptions(max_hours=10))
        self.assertEqual(result.status,'all_repairs_completed')
        self.assertEqual(result.current_mission_time,7)
        self.assertAlmostEqual(result.astronauts[0].accumulated_radiation,env.dose(0,7,.4),places=9)
        result=simulate_mission(strategy_a,Scenario(historical_template=GOES,storm_start_hour=332),
            [Astronaut('A')],['communications'],MissionAssumptions(max_hours=10))
        self.assertEqual(result.status,'radiation_data_exhausted')
        self.assertEqual(result.current_mission_time,4)
        self.assertTrue(result.progress[0].aborted)


if __name__=='__main__': unittest.main()
