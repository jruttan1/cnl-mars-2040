"""Synthetic engineering scenarios, not validated reactor limits or clinical rules."""
from dataclasses import asdict, replace
from unittest.mock import patch
import unittest

from sim.mission_recovery import RecoveryConfig, MissionRecovery, CrewPermission, NTP_PROFILE, NEP_PROFILE
from sim.mission_simulator import simulate_mission
from sim.models import Decision, Astronaut, Scenario
from sim.assumptions import DEFAULT_ASSUMPTIONS
from sim.strategies import strategy_a
from tests.test_strategy_a import ConstantEnvironment


class RecoveryTests(unittest.TestCase):
    def run_case(self, recovery=None, cfg=None, strategy=strategy_a, crew=None, repairs=None):
        with patch('sim.mission_simulator.RadiationEnvironment', ConstantEnvironment):
            return simulate_mission(strategy, astronauts=crew, repairs=repairs,
                                    config=cfg or DEFAULT_ASSUMPTIONS,
                                    recovery_config=recovery or RecoveryConfig())

    def test_engine_specific_order_and_checkout_change_outcomes(self):
        ntp=self.run_case()
        nep=self.run_case(cfg=replace(DEFAULT_ASSUMPTIONS,engine_type='NEP'))
        self.assertEqual(ntp.completed_repairs,['monitoring','communications','propulsion'])
        self.assertEqual(nep.completed_repairs,['monitoring','propulsion','communications'])
        self.assertEqual((ntp.current_mission_time,nep.current_mission_time),(25,27))
        for run in (ntp,nep):
            self.assertEqual(run.status,'mission_continuation_authorized')
            self.assertGreater(run.current_mission_time,run.progress[-1].reported_end_time)
            self.assertIsNone(run.active_eva)
            for a in run.astronauts:
                self.assertAlmostEqual(a.inside_hours+a.outside_hours,run.current_mission_time)
                self.assertAlmostEqual(a.bfo_absorbed_dose_mGy,a.inside_hours+10*a.outside_hours)
                self.assertAlmostEqual(a.bfo_gray_equivalent_mGy_eq,1.5*a.bfo_absorbed_dose_mGy)

    def test_hard_interlocks_cannot_be_bypassed_by_policy(self):
        def unsafe(obs):return Decision('start','ignore prerequisites',obs.available_astronauts[0],'propulsion')
        with self.assertRaisesRegex(ValueError,'monitoring'):
            self.run_case(strategy=unsafe)
        def restart(obs):return Decision('resume_mission','skip checkout')
        with self.assertRaisesRegex(ValueError,'not permitted'):
            self.run_case(strategy=restart)

    def test_initial_reactor_hazards_stop_without_inventing_dose(self):
        for field in ('shutdown_confirmed','decay_heat_removal_available','reactor_shield_integrity_confirmed'):
            result=self.run_case(recovery=replace(RecoveryConfig(),**{field:False}))
            self.assertEqual(result.status,'reactor_safety_unresolved')
            self.assertEqual(result.current_mission_time,0)
            self.assertEqual(result.exposure_history,[])
            self.assertEqual(result.progress,[])

    def test_forced_abort_at_fractional_exclusion_even_if_strategy_ignores_it(self):
        def stubborn(obs):
            if obs.active_eva:return Decision('continue','ignore external hazard')
            return strategy_a(obs)
        recovery=replace(RecoveryConfig(),exclusion_intervals=((2.25,4.5),))
        result=self.run_case(recovery=recovery,strategy=stubborn,cfg=replace(DEFAULT_ASSUMPTIONS,time_step_hours=5))
        first=result.progress[0]
        self.assertEqual(first.reported_end_time,2.25)
        self.assertTrue(first.aborted)
        self.assertEqual(first.bfo_absorbed_dose_mGy,22.5)
        self.assertEqual(result.recovery_state.completed_attempts['monitoring'],1)
        self.assertEqual(result.recovery_state.eva_kits_remaining,2)

    def test_failed_repair_consumes_time_exposure_and_kit_without_progress(self):
        recovery=replace(RecoveryConfig(),repair_success_attempt=(('monitoring',2),))
        result=self.run_case(recovery=recovery)
        self.assertFalse(result.progress[0].completed)
        self.assertFalse(result.progress[0].aborted)
        self.assertEqual(result.progress[0].bfo_absorbed_dose_mGy,70)
        self.assertEqual([e.repair_type for e in result.progress][:2],['monitoring','monitoring'])
        self.assertEqual(result.recovery_state.completed_attempts['monitoring'],2)
        self.assertEqual(result.recovery_state.eva_kits_remaining,2)
        self.assertEqual(result.status,'mission_continuation_authorized')

    def test_checkout_failure_and_authority_are_distinct_from_repairs(self):
        result=self.run_case(recovery=replace(RecoveryConfig(),checkout_succeeds=False))
        self.assertEqual(len(result.completed_repairs),3)
        self.assertEqual(result.status,'checkout_failed')
        result=self.run_case(recovery=replace(RecoveryConfig(),continuation_authorized=False))
        self.assertEqual(result.status,'safe_hold_requested')
        self.assertEqual(len(result.completed_repairs),3)

    def test_ground_review_changes_nep_sequence_without_oracle(self):
        recovery=replace(RecoveryConfig(),local_recovery_authority=False,ground_round_trip_hours=1.25,ground_review_hours=2)
        result=self.run_case(recovery=recovery,cfg=replace(DEFAULT_ASSUMPTIONS,engine_type='NEP'))
        self.assertEqual(result.completed_repairs,['monitoring','communications','propulsion'])
        prop=next(e for e in result.progress if e.repair_type=='propulsion')
        self.assertEqual(prop.start_time,18.25)
        self.assertEqual(result.recovery_state.ground_review_ready_at,18.25)

    def test_cooldown_gates_only_propulsion_area_and_changes_schedule(self):
        recovery=replace(RecoveryConfig(),ntp=replace(NTP_PROFILE,propulsion_access_after_hours=30.25))
        result=self.run_case(recovery=recovery,cfg=replace(DEFAULT_ASSUMPTIONS,time_step_hours=5))
        self.assertEqual(result.progress[-1].start_time,30.25)
        self.assertEqual(result.current_mission_time,39.25)

    def test_resource_conservation_is_a_real_decision(self):
        recovery=replace(RecoveryConfig(),ntp=replace(NTP_PROFILE,emergency_support_hours=15))
        def no_conservation(obs):
            if obs.recovery and 'conserve_support' in obs.recovery.allowed_actions:
                obs=replace(obs,recovery=replace(obs.recovery,allowed_actions=tuple(a for a in obs.recovery.allowed_actions if a!='conserve_support')))
            return strategy_a(obs)
        conserved=self.run_case(recovery=recovery)
        depleted=self.run_case(recovery=recovery,strategy=no_conservation)
        self.assertEqual(conserved.status,'mission_continuation_authorized')
        self.assertEqual(depleted.status,'emergency_support_exhausted')
        self.assertEqual(depleted.current_mission_time,15)
        self.assertTrue(depleted.progress[-1].aborted)
        self.assertNotIn('communications',depleted.completed_repairs)  # depletion wins exact completion tie

    def test_crew_consent_qualification_rest_and_workload_constraints(self):
        cfg=replace(DEFAULT_ASSUMPTIONS,allow_consecutive_evas=True,crew_rotation=False)
        recovery=replace(RecoveryConfig(),crew_permissions=(CrewPermission('A',False),CrewPermission('B',True,('monitoring',)),CrewPermission('C')))
        result=self.run_case(recovery=recovery,cfg=cfg,crew=[Astronaut('A'),Astronaut('B'),Astronaut('C')])
        self.assertEqual([e.astronaut.name for e in result.progress],['B','C','C'])
        self.assertEqual(result.progress[2].start_time,23)  # C rests eight hours after hour 15
        self.assertEqual(result.recovery_state.crew_eva_hours,{'A':0,'B':7,'C':14})
        self.assertEqual(result.status,'mission_continuation_authorized')
        strict=replace(recovery,crew_eva_budget_hours=7)
        result=self.run_case(recovery=strict,cfg=replace(cfg,max_hours=40),crew=[Astronaut('A'),Astronaut('B'),Astronaut('C')])
        self.assertEqual(len(result.progress),2)
        self.assertNotEqual(result.status,'mission_continuation_authorized')

    def test_kits_are_consumed_by_abort_and_prevent_extra_launches(self):
        recovery=replace(RecoveryConfig(),eva_kits=1,exclusion_intervals=((2,3),))
        result=self.run_case(recovery=recovery,cfg=replace(DEFAULT_ASSUMPTIONS,max_hours=15))
        self.assertEqual(len(result.progress),1)
        self.assertTrue(result.progress[0].aborted)
        self.assertEqual(result.recovery_state.eva_kits_remaining,0)

    def test_hold_and_abandon_stop_active_eva_without_claiming_return_or_survival(self):
        for action,outcome in [('safe_hold','safe_hold_requested'),('abort_mission','mission_objective_abandoned')]:
            def policy(obs):
                if obs.active_eva:return Decision(action,'crew requests stop')
                return strategy_a(obs)
            result=self.run_case(strategy=policy)
            self.assertEqual(result.status,outcome)
            self.assertTrue(result.progress[0].aborted)
            self.assertEqual(result.current_mission_time,1)
            self.assertIsNone(result.active_eva)

    def test_no_hidden_outcomes_or_radiation_in_observation(self):
        observations=[]
        def spy(obs):
            observations.append(obs.recovery)
            self.assertFalse(hasattr(obs.recovery,'config'))
            self.assertFalse(hasattr(obs.recovery,'repair_success_attempt'))
            self.assertFalse(hasattr(obs.recovery,'checkout_succeeds'))
            self.assertFalse(hasattr(obs.recovery,'dose'))
            return strategy_a(obs)
        a=self.run_case(strategy=spy)
        with patch.object(ConstantEnvironment,'outside_rate',1e9):b=self.run_case()
        self.assertEqual(a.event_log,b.event_log)
        self.assertEqual(a.recovery_state,b.recovery_state)
        controller=MissionRecovery('NTP',RecoveryConfig(),['A'],('monitoring',),7)
        view=controller.observe(0,[])
        with self.assertRaises(AttributeError):view.phase='ready'

    def test_reproducibility_no_cross_run_state_or_step_size_bias(self):
        recovery=replace(RecoveryConfig(),exclusion_intervals=((2.25,3.5),),local_recovery_authority=False)
        a=self.run_case(recovery=recovery,cfg=replace(DEFAULT_ASSUMPTIONS,time_step_hours=.25))
        b=self.run_case(recovery=recovery,cfg=replace(DEFAULT_ASSUMPTIONS,time_step_hours=5))
        c=self.run_case(recovery=recovery,cfg=replace(DEFAULT_ASSUMPTIONS,time_step_hours=.25))
        self.assertEqual(asdict(a),asdict(c))
        self.assertEqual(a.recovery_state,b.recovery_state)
        self.assertEqual(a.current_mission_time,b.current_mission_time)
        self.assertEqual([asdict(e) for e in a.progress],[asdict(e) for e in b.progress])

    def test_data_and_mission_horizons_do_not_imply_recovery_success(self):
        result=self.run_case(cfg=replace(DEFAULT_ASSUMPTIONS,max_hours=23))
        self.assertEqual(len(result.completed_repairs),3)
        self.assertEqual(result.status,'emergency_duration_reached')
        result=self.run_case(recovery=replace(RecoveryConfig(),continuation_deadline_hours=12.5))
        self.assertEqual(result.current_mission_time,12.5)
        self.assertEqual(result.status,'recovery_window_closed')
        self.assertTrue(result.progress[-1].aborted)
        result=self.run_case(cfg=replace(DEFAULT_ASSUMPTIONS,storm_start_hour=263))
        self.assertEqual(result.status,'radiation_data_exhausted')
        self.assertEqual(result.current_mission_time,1)

    def test_invalid_recovery_inputs_and_commands_rejected(self):
        bad=[replace(RecoveryConfig(),eva_kits=-1),replace(RecoveryConfig(),conserved_support_consumption=0),
             replace(RecoveryConfig(),ntp=replace(NTP_PROFILE,checkout_hours=float('nan'))),
             replace(RecoveryConfig(),crew_permissions=(CrewPermission('unknown'),)),
             replace(RecoveryConfig(),repair_success_attempt=(('monitoring',0),)),
             replace(RecoveryConfig(),exclusion_intervals=((2,1),))]
        for cfg in bad:
            with self.assertRaises(ValueError):self.run_case(recovery=cfg)
        ctrl=MissionRecovery('NTP',RecoveryConfig(),['A'],('monitoring',),7)
        with self.assertRaises(ValueError):ctrl.command('begin_checkout',0,[],True)
        with self.assertRaises(ValueError):ctrl.advance(-1)
        with self.assertRaises(ValueError):ctrl.start_eva('monitoring','missing',0,[])

    def test_failed_attempt_world_is_keyed_by_task_not_policy_draw_order(self):
        cfg=replace(RecoveryConfig(),repair_success_attempt=(('propulsion',2),))
        a=MissionRecovery('NTP',cfg,['A'],REPAIRS,7)
        b=MissionRecovery('NTP',cfg,['A'],REPAIRS,7)
        b.finish_eva('communications','A',0,True)
        self.assertEqual([a.finish_eva('propulsion','A',0,True) for _ in range(2)],[False,True])
        self.assertEqual([b.finish_eva('propulsion','A',0,True) for _ in range(2)],[False,True])

from sim.mission_recovery import REPAIRS
if __name__=='__main__':unittest.main()
