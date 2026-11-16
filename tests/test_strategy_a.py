"""Operational fixtures below are synthetic test inputs, not physical thresholds."""
import unittest
from dataclasses import asdict, replace
from unittest.mock import patch
import math
from sim.models import Astronaut, Scenario, MissionConfig, State
from sim import mission_simulator as sim
from sim.strategies import strategy_a, strategy_b, strategy_c, strategy_d
from radiation_model import baseline_interval_dose, load_baseline


class ConstantEnvironment:
    start_hour=0.0
    end_hour=264.0
    outside_rate=10.0
    inside_rate=1.0
    def __init__(self, scenario):self.scenario=scenario
    def dose(self, start, end, shielding):
        assert 0 <= start <= end <= 264-self.scenario.storm_start_hour
        return (end-start)*(self.outside_rate if shielding==self.scenario.shielding else self.inside_rate)


class StrategyATests(unittest.TestCase):
    def run_case(self, cfg=None, repairs=None, crew=None, scenario=None, strategy=strategy_a):
        with patch.object(sim,'RadiationEnvironment',ConstantEnvironment):
            return sim.simulate_mission(strategy,scenario or Scenario(),crew or [Astronaut('A'),Astronaut('B'),Astronaut('C')],repairs,cfg)

    def test_creation_and_no_double_accounting(self):
        a=Astronaut('A');s=Scenario();env=ConstantEnvironment(s)
        e=sim.start_eva(2,a,'communications','NTP')
        self.assertEqual(e.scheduled_end_time,9)
        self.assertIs(e.astronaut,a)
        sim.update_eva(e,3,s,env);sim.update_eva(e,3,s,env);sim.update_eva(e,4.5,s,env)
        self.assertEqual(a.accumulated_radiation,25)
        self.assertEqual(a.outside_hours,2.5)
        sim.abort_eva(e,4.5,'test operational condition')
        sim.update_eva(e,9,s,env)
        self.assertEqual(a.accumulated_radiation,25)
        self.assertFalse(e.completed);self.assertTrue(e.aborted)
        self.assertEqual(e.reported_end_time,4.5)

    def test_complete_reference_mission(self):
        r=self.run_case()
        self.assertEqual(r.status,'all_repairs_completed')
        self.assertEqual(r.current_mission_time,23)
        self.assertEqual(r.completed_repairs,['communications','monitoring','propulsion'])
        self.assertEqual([e.start_time for e in r.progress],[0,8,16])
        self.assertEqual([e.astronaut.name for e in r.progress],['A','B','C'])
        for a in r.astronauts:
            self.assertEqual(a.outside_hours,7);self.assertEqual(a.inside_hours,16)
            self.assertEqual(a.accumulated_radiation,86)
        for e in r.progress:
            self.assertTrue(e.completed);self.assertFalse(e.aborted)
            self.assertEqual(e.reported_end_time-e.start_time,7)
        self.assertTrue(all(a.reported_end_time<=b.start_time for a,b in zip(r.progress,r.progress[1:])))

    def test_terminal_eva_does_not_change(self):
        r=self.run_case(repairs=['communications']);e=r.progress[0]
        before=asdict(e)
        sim.update_eva(e,20,r.scenario,ConstantEnvironment(r.scenario))
        sim.abort_eva(e,20,'too late')
        self.assertEqual(asdict(e),before)

    def test_abort_and_retry_without_partial_progress(self):
        cfg=MissionConfig(operational_restrictions=((3,5),))
        r=self.run_case(cfg,repairs=['communications'])
        self.assertEqual([(e.start_time,e.reported_end_time,e.aborted) for e in r.progress],[(0,3,True),(5,12,False)])
        self.assertEqual([e.repair_type for e in r.progress],['communications']*2)
        self.assertEqual(r.completed_repairs,['communications'])
        for a in r.astronauts:
            self.assertEqual(a.inside_hours+a.outside_hours,12)
            self.assertEqual(a.accumulated_radiation,a.outside_hours*10+a.inside_hours)

    def test_cap_without_dosimetry_ends_unfinished(self):
        r=self.run_case(MissionConfig(max_hours=15,max_continuous_eva_hours=3),repairs=['propulsion'])
        self.assertEqual(r.status,'emergency_duration_reached')
        self.assertEqual(r.completed_repairs,[])
        self.assertTrue(all(e.aborted and not e.completed for e in r.progress))
        self.assertEqual([e.start_time for e in r.progress],[0,4,8])
        self.assertTrue(all(a.estimated_dose_mGy is None for a in r.astronauts))

    def test_estimate_abort_uses_estimate_not_true_dose(self):
        cfg=MissionConfig(max_hours=15,estimated_external_rate_mGy_h=10,radiation_abort_threshold_mGy=15)
        r=self.run_case(cfg,repairs=['monitoring'],crew=[Astronaut('A')])
        self.assertEqual(len(r.progress),1)
        self.assertEqual(r.progress[0].reported_end_time,2)
        self.assertIn('estimate',r.progress[0].end_reason)
        self.assertEqual(r.completed_repairs,[])
        with patch.object(ConstantEnvironment,'outside_rate',100000):
            other=self.run_case(cfg,repairs=['monitoring'],crew=[Astronaut('A')])
        self.assertEqual(r.event_log,other.event_log)
        self.assertNotEqual(r.astronauts[0].accumulated_radiation,other.astronauts[0].accumulated_radiation)

    def test_no_future_or_ground_truth_in_observations(self):
        observations=[]
        def spy(obs):
            observations.append(obs)
            self.assertIsInstance(obs,State)
            self.assertFalse(hasattr(obs,'scenario'))
            self.assertFalse(hasattr(obs,'astronauts'))
            self.assertFalse(hasattr(obs,'radiation_data'))
            if obs.active_eva:self.assertIsNone(obs.active_eva.estimated_dose_mGy)
            return strategy_a(obs)
        r=self.run_case(strategy=spy)
        with patch.object(ConstantEnvironment,'outside_rate',1e9),patch.object(ConstantEnvironment,'inside_rate',1e8):
            changed=self.run_case()
        self.assertEqual(r.event_log,changed.event_log)
        self.assertTrue(observations)

    def test_crew_availability_and_fractional_turnaround(self):
        r=self.run_case(MissionConfig(time_step_hours=2,turnaround_hours=.5,allow_consecutive_evas=True),
                        repairs=['communications','monitoring'],crew=[Astronaut('A',available_from=1.5)])
        self.assertEqual([e.start_time for e in r.progress],[1.5,9])
        self.assertEqual(r.current_mission_time,16)
        self.assertEqual(r.astronauts[0].accumulated_radiation,142)

    def test_step_size_consistency_and_reproducibility(self):
        a=self.run_case();b=self.run_case(MissionConfig(time_step_hours=.25))
        self.assertEqual([asdict(e) for e in a.progress],[asdict(e) for e in b.progress])
        self.assertEqual(asdict(a),asdict(self.run_case()))

    def test_engine_specific_priorities_and_explicit_override(self):
        cfg=MissionConfig(repair_order_nep=('propulsion','monitoring','communications'))
        r=self.run_case(cfg,scenario=Scenario(engine_type='NEP'))
        self.assertEqual(r.completed_repairs,['propulsion','monitoring','communications'])
        r=self.run_case(cfg,repairs=['communications'],scenario=Scenario(engine_type='NEP'))
        self.assertEqual(r.completed_repairs,['communications'])

    def test_exact_horizon_and_data_exhaustion(self):
        r=self.run_case(MissionConfig(max_hours=7),repairs=['communications'])
        self.assertEqual(r.status,'all_repairs_completed')
        r=self.run_case(MissionConfig(max_hours=10),scenario=Scenario(storm_start_hour=263))
        self.assertEqual(r.status,'radiation_data_exhausted')
        self.assertEqual(r.current_mission_time,1)
        self.assertTrue(r.progress[0].aborted)
        with self.assertRaises(ValueError):self.run_case(scenario=Scenario(storm_start_hour=264))
        r=self.run_case(repairs=[])
        self.assertEqual(r.current_mission_time,0)

    def test_abort_wins_at_completion_boundary(self):
        r=self.run_case(MissionConfig(max_hours=7,operational_restrictions=((7,8),)),repairs=['communications'])
        self.assertTrue(r.progress[0].aborted);self.assertFalse(r.progress[0].completed)
        self.assertEqual(r.completed_repairs,[])

    def test_invalid_configuration_and_stubs(self):
        for cfg in [MissionConfig(time_step_hours=0),MissionConfig(max_hours=math.nan),MissionConfig(turnaround_hours=-1)]:
            with self.assertRaises(ValueError):self.run_case(cfg)
        for f in (strategy_b,strategy_c,strategy_d):
            with self.assertRaises(NotImplementedError):f(None)

    def test_centralized_defaults_and_five_person_crew(self):
        from sim.assumptions import MissionAssumptions
        cfg=MissionAssumptions()
        self.assertEqual(cfg.crew_size,5)
        self.assertEqual(cfg.astronauts_per_eva,1)
        self.assertEqual(cfg.eva_duration_hours,7)
        self.assertEqual(cfg.turnaround_hours,1)
        self.assertEqual(cfg.max_simultaneous_evas,1)
        self.assertEqual(cfg.max_hours,264)
        with patch.object(sim,'RadiationEnvironment',ConstantEnvironment):
            result=sim.simulate_mission(strategy_a,config=cfg)
        self.assertIs(result.config,cfg)
        self.assertEqual(len(result.astronauts),5)
        self.assertEqual([e.astronaut.name for e in result.progress],['Crew 1','Crew 2','Crew 3'])
        self.assertEqual([e.start_time for e in result.progress],[0,8,16])
        self.assertEqual([a.outside_hours for a in result.astronauts],[7,7,7,0,0])

    def test_assumptions_drive_duration_scenario_and_repair_order(self):
        from sim.assumptions import MissionAssumptions
        cfg=MissionAssumptions(crew_size=2,eva_duration_hours=4,turnaround_hours=2,
            default_spe_severity='SAPPHIRE-1-in-1000',external_shielding_g_cm2=1,
            cabin_shielding_g_cm2=10,storm_start_hour=0,
            required_repair_types=('propulsion','communications'))
        with patch.object(sim,'RadiationEnvironment',ConstantEnvironment):
            r=sim.simulate_mission(strategy_a,config=cfg)
        self.assertEqual(len(r.astronauts),2)
        self.assertEqual(r.scenario.severity,cfg.default_spe_severity)
        self.assertEqual(r.scenario.shielding,1)
        self.assertEqual(r.scenario.cabin_shielding,10)
        self.assertEqual(r.completed_repairs,['propulsion','communications'])
        self.assertEqual([(e.start_time,e.reported_end_time) for e in r.progress],[(0,4),(6,10)])
        self.assertEqual(cfg.eva_time_limit_hours,4)

    def test_no_consecutive_eva_without_explicit_permission(self):
        r=self.run_case(MissionConfig(max_hours=20),repairs=['communications','monitoring'],crew=[Astronaut('A')])
        self.assertEqual(len(r.progress),1)
        self.assertEqual(r.completed_repairs,['communications'])
        self.assertEqual(r.astronauts[0].available_from,0)  # Global turnaround does not rewrite availability.
        self.assertEqual(r.status,'emergency_duration_reached')

    def test_rotation_switch_and_sequential_model_validation(self):
        cfg=MissionConfig(crew_rotation=False,allow_consecutive_evas=True)
        r=self.run_case(cfg)
        self.assertEqual([e.astronaut.name for e in r.progress],['A','A','A'])
        for cfg in (MissionConfig(astronauts_per_eva=2),MissionConfig(max_simultaneous_evas=2)):
            with self.assertRaisesRegex(ValueError,'exactly one'):
                self.run_case(cfg)

    def test_actual_csv_selection_and_exposure(self):
        baseline=load_baseline()
        for severity in ('SAPPHIRE-1-in-100','SAPPHIRE-1-in-1000'):
            s=Scenario(severity=severity)
            r=sim.simulate_mission(strategy_a,s,[Astronaut('A',available_from=2)],['communications'])
            expected=baseline_interval_dose(severity,20,48,50,s.timing_variant,baseline=baseline)
            expected+=baseline_interval_dose(severity,.4,50,57,s.timing_variant,baseline=baseline)
            self.assertAlmostEqual(r.astronauts[0].accumulated_radiation,expected,places=8)
        for scenario in [Scenario(severity='sapphire_100yr'),Scenario(timing_variant='bad'),Scenario(shielding=3)]:
            with self.assertRaises(ValueError):sim.RadiationEnvironment(scenario)


if __name__=='__main__':unittest.main()
