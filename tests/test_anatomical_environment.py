"""Organ exposure conservation, unit separation and NASA comparison boundaries."""
import unittest
from unittest.mock import patch
import anatomical_environment as environment
from dataclasses import replace
import numpy as np
import pandas as pd
from anatomical_environment import load_environment, validate_environment, interval_exposure, nasa_bfo_comparisons
from sim.mission_simulator import simulate_mission
from sim.assumptions import DEFAULT_ASSUMPTIONS
from sim.models import Astronaut
from sim.strategies import strategy_a

class AnatomicalEnvironmentTests(unittest.TestCase):
    def test_frozen_export_refuses_rebuild(self):
        with patch.object(environment, 'build_environment') as build:
            with self.assertRaisesRegex(ValueError, 'frozen'):
                environment.export_environment()
            build.assert_not_called()

    def test_frozen_loader_rejects_changed_artifact(self):
        with patch.object(environment, 'sha256', return_value='changed'):
            with self.assertRaisesRegex(ValueError, 'Frozen anatomical environment changed'):
                environment.load_environment('august_1972')

    def test_all_totals_and_fractional_intervals(self):
        for template in ('august_1972', 'october_2003_goes10'):
            data = load_environment(template)
            validate_environment(data)
            for _, member in data.groupby(['scenario','shielding_g_cm2','timing_variant']):
                for quantity in ('absorbed_dose_mGy','gray_equivalent_mGy_eq'):
                    total = interval_exposure(member, 0, member.hour_end.max(), quantity)
                    self.assertAlmostEqual(total, member[f'event_bfo_{quantity}'].iloc[0], places=8)
                    expected = member[f'bfo_{quantity}_per_h'].iloc[:2].sum() / 2
                    self.assertAlmostEqual(interval_exposure(member,.5,1.5,quantity),expected)
        with self.assertRaises(ValueError): interval_exposure(data,0,7)

    def test_real_mission_ledger_separate_units_and_priors(self):
        crew=[Astronaut('A', bfo_initial_absorbed_dose_mGy=12, bfo_initial_gray_equivalent_mGy_eq=27)]
        for template in ('august_1972','october_2003_goes10'):
            result=simulate_mission(strategy_a,astronauts=crew,repairs=['communications'],config=replace(DEFAULT_ASSUMPTIONS,historical_template=template))
            ledger=pd.DataFrame(result.exposure_history)
            a=result.astronauts[0]
            self.assertAlmostEqual(a.bfo_absorbed_dose_mGy,12+ledger.bfo_absorbed_dose_mGy.sum())
            self.assertAlmostEqual(a.bfo_gray_equivalent_mGy_eq,27+ledger.bfo_gray_equivalent_mGy_eq.sum())
            self.assertAlmostEqual(result.progress[0].bfo_absorbed_dose_mGy,ledger.bfo_absorbed_dose_mGy.sum())
            self.assertEqual(crew[0].bfo_absorbed_dose_mGy,0)
            self.assertNotEqual(a.bfo_absorbed_dose_mGy,a.bfo_gray_equivalent_mGy_eq)

    def test_cabin_and_eva_ledger_no_double_count(self):
        result=simulate_mission(strategy_a)
        for a in result.astronauts:
            rows=pd.DataFrame(result.exposure_history).query('astronaut == @a.name')
            self.assertAlmostEqual(a.bfo_absorbed_dose_mGy,rows.bfo_absorbed_dose_mGy.sum())
            self.assertAlmostEqual(a.bfo_gray_equivalent_mGy_eq,rows.bfo_gray_equivalent_mGy_eq.sum())
            self.assertAlmostEqual(a.inside_hours+a.outside_hours,result.current_mission_time)

    def test_rolling_limits_exclude_prior_and_do_not_claim_compliance(self):
        rows=[dict(astronaut='A',start_hour=0,end_hour=1440,bfo_gray_equivalent_mGy_eq=600)]
        result=nasa_bfo_comparisons(rows)
        self.assertEqual(result[0]['max_modeled_mission_contribution_mGy_eq'],300)
        self.assertEqual(result[1]['max_modeled_mission_contribution_mGy_eq'],600)
        self.assertTrue(result[0]['modeled_contribution_exceeds_reference'])
        self.assertEqual(result[0]['compliance_status'],'not_assessed')
        self.assertEqual(nasa_bfo_comparisons([]),[])

    def test_explicit_bfo_threshold_required(self):
        with self.assertRaisesRegex(ValueError,'explicit experimental BFO threshold'):
            simulate_mission(strategy_a,config=replace(DEFAULT_ASSUMPTIONS,estimated_external_rate_mGy_h=1))

if __name__ == '__main__': unittest.main()
