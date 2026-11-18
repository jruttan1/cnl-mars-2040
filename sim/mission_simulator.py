"""Mission progression with shared, hidden OLTARIS BFO exposure accounting."""
from copy import deepcopy
from .mission_recovery import MissionRecovery
import math
from sim.assumptions import DEFAULT_ASSUMPTIONS
from anatomical_environment import load_environment, interval_exposure
from .models import (Astronaut, EVA, Scenario, MissionState, State,
                     ActiveEVAObservation)


class RadiationEnvironment:
    """One anatomical environment for all strategies; never supplied as an observation."""
    def __init__(self, scenario: Scenario):
        self.scenario = scenario
        data = load_environment(scenario.historical_template)
        self.data = data[data.scenario.eq(scenario.severity) &
                         data.timing_variant.eq(scenario.timing_variant)].copy()
        if self.data.empty:
            raise ValueError('Unknown scenario or timing variant')
        for depth in (scenario.shielding, scenario.cabin_shielding):
            if self.data[self.data.shielding_g_cm2.eq(depth)].empty:
                raise ValueError('Anatomical data support only exact 0.4 and 20 g/cm² shielding')
        self.start_hour = float(self.data.hour.min())
        self.end_hour = float(self.data.hour_end.max())

    def dose(self, mission_start, mission_end, shielding):
        return self.exposure(mission_start, mission_end, shielding, 'absorbed_dose_mGy')

    def gray_equivalent(self, mission_start, mission_end, shielding):
        return self.exposure(mission_start, mission_end, shielding, 'gray_equivalent_mGy_eq')

    def exposure(self, mission_start, mission_end, shielding, quantity):
        return interval_exposure(self.data[self.data.shielding_g_cm2.eq(shielding)],
            mission_start + self.scenario.storm_start_hour,
            mission_end + self.scenario.storm_start_hour, quantity)


def get_hourly_exposure(hour: float, scenario: Scenario, environment=None) -> float:
    """One mission-relative hour of external modeled BFO absorbed dose, in mGy."""
    return (environment or RadiationEnvironment(scenario)).dose(hour, hour+1, scenario.shielding)


def start_eva(start_time, astronaut, repair_type, engine_type, config=DEFAULT_ASSUMPTIONS) -> EVA:
    if start_time < astronaut.available_from:
        raise ValueError('Astronaut is not available')
    return EVA(start_time, start_time+config.eva_duration_hours, None, False, astronaut,
               repair_type, engine_type, last_update_time=start_time)


def abort_eva(eva: EVA, current_time: float, reason: str) -> None:
    """End an active EVA after exposure has been accounted to current_time."""
    if eva.reported_end_time is not None:
        return
    if current_time != eva.last_update_time:
        raise ValueError('Account exposure to the abort time before ending the EVA')
    eva.aborted = True
    eva.reported_end_time = current_time
    eva.end_reason = reason


def update_eva(eva: EVA, current_time: float, scenario: Scenario, environment=None) -> None:
    """Account only the unprocessed interval. Terminal EVAs are immutable here."""
    if eva.reported_end_time is not None:
        return
    start = eva.last_update_time if eva.last_update_time is not None else eva.start_time
    end = min(current_time, eva.scheduled_end_time)
    if end < start:
        raise ValueError('Cannot run an EVA backwards')
    if end == start:
        return
    environment = environment or RadiationEnvironment(scenario)
    dose = environment.dose(start, end, scenario.shielding)
    gray_equivalent = environment.gray_equivalent(start, end, scenario.shielding)
    eva.astronaut.accumulated_radiation += dose
    eva.astronaut.outside_hours += end-start
    eva.modeled_dose_mGy += dose
    eva.astronaut.bfo_gray_equivalent_mGy_eq += gray_equivalent
    eva.bfo_gray_equivalent_mGy_eq += gray_equivalent
    eva.last_update_time = end
    # Mission loop resolves operational aborts before marking success at the boundary.


def observe(state: MissionState, recovery=None) -> State:
    t, cfg = state.current_mission_time, state.config
    restricted = any(a <= t < b for a, b in cfg.operational_restrictions)
    reason = 'Preset operational restriction is active' if restricted else ''
    launch = not restricted and t >= state.next_eva_time
    if not restricted and not launch:
        reason = 'Minimum turnaround period has not elapsed'
    if t+cfg.eva_duration_hours > cfg.max_hours:
        launch = False
        reason = 'Insufficient emergency time for a complete planned EVA'
    # Fewest previous attempts first; input order breaks ties. No true dose ranking.
    crew_order = state.astronauts
    if cfg.crew_rotation:
        crew_order = sorted(crew_order, key=lambda a: sum(e.astronaut.name == a.name for e in state.progress))
    previous = state.progress[-1].astronaut.name if state.progress else None
    available = tuple(a.name for a in crew_order if a.available_from <= t and
        (cfg.allow_consecutive_evas or a.name != previous) and
        (a.estimated_dose_mGy is None or a.estimated_dose_mGy < cfg.radiation_abort_threshold_mGy))
    eva = state.active_eva
    active = None if eva is None else ActiveEVAObservation(
        eva.astronaut.name, eva.repair_type, t-eva.start_time, eva.astronaut.estimated_dose_mGy)
    recovery_obs = None if recovery is None else recovery.observe(state.completed_repairs, state.engineering_stabilized)
    if recovery_obs is not None and not recovery_obs.ready_repairs:
        launch = False
        if not reason:
            reason = '; '.join(reason for _, reason in recovery_obs.blocked_repairs) or 'Mission decision pending'
    return State(t, available, tuple(r for r in state.required_repairs if r not in state.completed_repairs),
                 tuple(state.completed_repairs), active, launch, reason, restricted,
                 cfg.eva_time_limit_hours, cfg.radiation_abort_threshold_mGy, recovery_obs)


def _validate(scenario, crew, repairs, cfg):
    values = [cfg.max_hours, cfg.time_step_hours, cfg.eva_duration_hours, cfg.eva_time_limit_hours]
    if cfg.radiation_abort_threshold_mGy is not None:
        values.append(cfg.radiation_abort_threshold_mGy)
    if cfg.estimated_external_rate_mGy_h is not None and cfg.radiation_abort_threshold_mGy is None:
        raise ValueError('An optional BFO dose estimate requires an explicit experimental BFO threshold')
    if any(not math.isfinite(v) or v <= 0 for v in values):
        raise ValueError('Duration, time step, time cap and threshold must be finite and positive')
    if not math.isfinite(cfg.turnaround_hours) or cfg.turnaround_hours < 0:
        raise ValueError('Turnaround must be finite and nonnegative')
    if cfg.astronauts_per_eva != 1 or cfg.max_simultaneous_evas != 1:
        raise ValueError('This simulator supports exactly one astronaut per EVA and one active EVA')
    if scenario.engine_type not in ('NTP', 'NEP'):
        raise ValueError('Engine type must be NTP or NEP')
    if not crew or len({a.name for a in crew}) != len(crew):
        raise ValueError('Provide a nonempty crew with unique names')
    if len(set(repairs)) != len(repairs) or not set(repairs) <= {'communications','monitoring','propulsion'}:
        raise ValueError('Repairs must be unique supported categories')
    for a in crew:
        if not a.name or any(not math.isfinite(v) or v < 0 for v in
                           (a.radiation_baseline, a.accumulated_radiation, a.available_from,
                            a.bfo_initial_gray_equivalent_mGy_eq, a.bfo_gray_equivalent_mGy_eq)):
            raise ValueError('Invalid crew initialization')
    for rate in (cfg.estimated_external_rate_mGy_h, cfg.estimated_cabin_rate_mGy_h):
        if rate is not None and (not math.isfinite(rate) or rate < 0):
            raise ValueError('Assumed estimate rates must be finite and nonnegative')
    if any(not math.isfinite(a+b) or a < 0 or b <= a for a,b in cfg.operational_restrictions):
        raise ValueError('Restrictions must be finite ordered nonnegative intervals')


def simulate_mission(strategy, scenario=None, astronauts=None, repairs=None, config=None, recovery_config=None):
    """Fresh, deterministic run. Strategy receives observations, never this state."""
    cfg = config if config is not None else DEFAULT_ASSUMPTIONS
    scenario = scenario if scenario is not None else Scenario.from_assumptions(cfg)
    if type(cfg.crew_size) is not int or cfg.crew_size < 1:
        raise ValueError("Crew size must be a positive integer")
    astronauts = astronauts if astronauts is not None else [Astronaut(f"Crew {i+1}") for i in range(cfg.crew_size)]
    engine_order = cfg.repair_order_ntp if scenario.engine_type == 'NTP' else cfg.repair_order_nep
    default_repairs = cfg.required_repair_types if engine_order is None else engine_order
    repairs = tuple(default_repairs if repairs is None else repairs)
    _validate(scenario, astronauts, repairs, cfg)
    environment = RadiationEnvironment(scenario)
    if not math.isfinite(scenario.storm_start_hour) or not environment.start_hour <= scenario.storm_start_hour < environment.end_hour:
        raise ValueError('Mission origin is outside the anatomical radiation record')
    end = min(cfg.max_hours, environment.end_hour-scenario.storm_start_hour)
    state = MissionState(scenario, cfg, deepcopy(astronauts), repairs)
    recovery = None if recovery_config is None else MissionRecovery(
        scenario.engine_type, recovery_config, [a.name for a in state.astronauts], repairs)
    if recovery is not None:
        state.recovery_config = recovery_config
    for a in state.astronauts:
        a.accumulated_radiation += a.radiation_baseline
        a.bfo_gray_equivalent_mGy_eq += a.bfo_initial_gray_equivalent_mGy_eq
        a.inside_hours = a.outside_hours = 0.0
        a.estimated_dose_mGy = 0.0 if cfg.estimated_external_rate_mGy_h is not None else None
    def log(action, reason, eva=None):
        state.event_log.append(dict(hour=state.current_mission_time, action=action, reason=reason,
            astronaut=eva.astronaut.name if eva else None, repair=eva.repair_type if eva else None))
    def credit_completed_eva(eva):
        eva.completed = True
        eva.reported_end_time = state.current_mission_time
        eva.end_reason = 'Planned EVA repair completed'
        state.completed_repairs.append(eva.repair_type)
        log('completed', eva.end_reason, eva)

    def finish(eva):
        state.next_eva_time = state.current_mission_time+cfg.turnaround_hours
        state.progress.append(eva)
        state.active_eva = None

    def deadline_failed():
        if recovery is None or not recovery.missed_deadline(state.current_mission_time, state.completed_repairs):
            return False
        state.status = ('ntp_propellant_recovery_window_lost' if scenario.engine_type == 'NTP'
                        else 'nep_thermal_recovery_window_lost')
        if state.active_eva:
            abort_eva(state.active_eva, state.current_mission_time, state.status)
            log('aborted', state.status, state.active_eva)
            finish(state.active_eva)
        return True
    # A finite horizon and a strictly increasing clock bound every run.
    while state.current_mission_time < end:
        t = state.current_mission_time
        obs = observe(state, recovery)
        eva = state.active_eva
        # Resolve a seven-hour completion before a new launch, with abort precedence
        # for restrictions or the optional estimate; reaching the normal duration is success.
        if eva and t >= eva.scheduled_end_time:
            if obs.operational_abort or (eva.astronaut.estimated_dose_mGy is not None and
                    eva.astronaut.estimated_dose_mGy >= cfg.radiation_abort_threshold_mGy):
                reason = obs.restriction_reason or 'Imperfect operational dose estimate reached configured threshold'
                abort_eva(eva, t, reason);log('aborted', reason, eva)
            else:
                credit_completed_eva(eva)
            finish(eva);obs = observe(state, recovery)
        if deadline_failed():
            break
        if recovery is None and len(state.completed_repairs) == len(repairs):
            state.status = 'all_repairs_completed';break
        decision = strategy(obs)
        log(decision.action, decision.reason, state.active_eva)
        if decision.action == 'stabilize':
            if recovery is None or state.active_eva or state.engineering_stabilized or obs.recovery.safety_blockers:
                raise ValueError('Spacecraft stabilization is not permitted')
            state.engineering_stabilized = True
            continue
        if decision.action == 'start':
            if state.active_eva or not obs.launch_allowed or decision.astronaut not in obs.available_astronauts or decision.repair_type not in obs.outstanding_repairs:
                raise ValueError('Strategy requested an invalid EVA launch')
            if recovery is not None:
                recovery.require_launch(decision.repair_type, decision.astronaut, state.completed_repairs,
                                        state.engineering_stabilized)
            a = next(a for a in state.astronauts if a.name == decision.astronaut)
            state.active_eva = start_eva(t, a, decision.repair_type, scenario.engine_type, cfg)
            state.event_log[-1].update(astronaut=a.name, repair=decision.repair_type)
        elif decision.action == 'abort':
            if not state.active_eva:raise ValueError('No EVA to abort')
            abort_eva(state.active_eva,t,decision.reason);finish(state.active_eva)
            continue
        elif decision.action in ('resume_mission', 'safe_hold', 'abort_mission'):
            if recovery is None:
                raise ValueError('Recovery model must be enabled for mission-recovery commands')
            if decision.action == 'resume_mission' and (state.active_eva or obs.recovery.continuation_blockers):
                raise ValueError('Mission continuation is not permitted before repairs, crew return and approval')
            if state.active_eva:
                eva = state.active_eva
                abort_eva(eva, t, decision.reason)
                log('aborted', eva.end_reason, eva)
                finish(eva)
            state.status = {'resume_mission': 'mission_continuation_authorized',
                            'safe_hold': 'safe_hold_requested',
                            'abort_mission': 'mission_objective_abandoned'}[decision.action]
            break
        elif decision.action not in ('wait','continue'):
            raise ValueError('Unknown decision')
        # Split at known operational boundaries, never at predicted radiation peaks.
        boundaries = [end, t+cfg.time_step_hours, state.next_eva_time]
        if recovery is not None and recovery.deadline is not None:
            boundaries.append(recovery.deadline)
        boundaries += [a.available_from for a in state.astronauts]
        boundaries += [x for interval in cfg.operational_restrictions for x in interval]
        if state.active_eva:
            boundaries += [state.active_eva.scheduled_end_time,
                           state.active_eva.start_time+cfg.eva_time_limit_hours]
        until = min(x for x in boundaries if x > t)
        active = state.active_eva
        if active:update_eva(active,until,scenario,environment)
        for a in state.astronauts:
            outside = active is not None and active.astronaut is a
            shielding = scenario.shielding if outside else scenario.cabin_shielding
            absorbed = environment.dose(t, until, shielding)
            gray_equivalent = environment.gray_equivalent(t, until, shielding)
            if not outside:
                a.accumulated_radiation += absorbed
                a.bfo_gray_equivalent_mGy_eq += gray_equivalent
                a.inside_hours += until-t
            state.exposure_history.append(dict(astronaut=a.name, start_hour=t, end_hour=until,
                location='eva' if outside else 'cabin', shielding_g_cm2=shielding,
                bfo_absorbed_dose_mGy=absorbed, bfo_gray_equivalent_mGy_eq=gray_equivalent))
            if a.estimated_dose_mGy is not None:
                rate = cfg.estimated_external_rate_mGy_h if outside else cfg.estimated_cabin_rate_mGy_h
                a.estimated_dose_mGy += rate*(until-t)
        state.current_mission_time = until
    if state.status == 'running':
        # Resolve an EVA ending exactly at the terminal boundary.
        eva = state.active_eva
        if eva:
            obs = observe(state, recovery)
            exceeded = (eva.astronaut.estimated_dose_mGy is not None and
                        eva.astronaut.estimated_dose_mGy >= cfg.radiation_abort_threshold_mGy)
            if eva.scheduled_end_time == end and not obs.operational_abort and not exceeded:
                credit_completed_eva(eva)
            else:
                abort_eva(eva,end,'Emergency/data boundary or operational abort condition');log('aborted',eva.end_reason,eva)
            finish(eva)
        state.status = ('all_repairs_completed' if recovery is None and len(state.completed_repairs)==len(repairs) else
                        'radiation_data_exhausted' if end < cfg.max_hours else 'emergency_duration_reached')
        deadline_failed()
    log('mission_ended',state.status)
    return state
