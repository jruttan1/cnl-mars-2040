"""Mission progression and hidden modeled tissue-target exposure accounting."""
from copy import deepcopy
import math
from sim.assumptions import DEFAULT_ASSUMPTIONS
from radiation_model import load_baseline, baseline_interval_dose
from .models import (Astronaut, EVA, Scenario, MissionState, State,
                     ActiveEVAObservation)


class RadiationEnvironment:
    """Read the frozen CSV once. Never supplied to a strategy."""
    def __init__(self, scenario: Scenario):
        self.scenario = scenario
        data = load_baseline(historical_template=scenario.historical_template)
        self.data = data[data.scenario.eq(scenario.severity) &
                         data.timing_variant.eq(scenario.timing_variant)].copy()
        if self.data.empty:
            raise ValueError('Unknown scenario or timing variant')
        for depth in (scenario.shielding, scenario.cabin_shielding):
            baseline_interval_dose(scenario.severity, depth, float(self.data.hour.min()), float(self.data.hour_end.max()),
                                   scenario.timing_variant, baseline=self.data, historical_template=scenario.historical_template)
        self.start_hour = float(self.data.hour.min())
        self.end_hour = float(self.data.hour_end.max())

    def dose(self, mission_start, mission_end, shielding):
        return baseline_interval_dose(self.scenario.severity, shielding,
            mission_start + self.scenario.storm_start_hour,
            mission_end + self.scenario.storm_start_hour,
            self.scenario.timing_variant, baseline=self.data, historical_template=self.scenario.historical_template)


def get_hourly_exposure(hour: float, scenario: Scenario, environment=None) -> float:
    """One mission-relative hour of external idealized tissue-target dose, in mGy."""
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
    dose = (environment or RadiationEnvironment(scenario)).dose(start, end, scenario.shielding)
    eva.astronaut.accumulated_radiation += dose
    eva.astronaut.outside_hours += end-start
    eva.modeled_dose_mGy += dose
    eva.last_update_time = end
    # Mission loop resolves operational aborts before marking success at the boundary.


def observe(state: MissionState) -> State:
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
    return State(t, available, tuple(r for r in state.required_repairs if r not in state.completed_repairs),
                 tuple(state.completed_repairs), active, launch, reason, restricted,
                 cfg.eva_time_limit_hours, cfg.radiation_abort_threshold_mGy)


def _validate(scenario, crew, repairs, cfg):
    values = [cfg.max_hours, cfg.time_step_hours, cfg.eva_duration_hours, cfg.eva_time_limit_hours,
              cfg.radiation_abort_threshold_mGy]
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
                           (a.radiation_baseline, a.accumulated_radiation, a.available_from)):
            raise ValueError('Invalid crew initialization')
    for rate in (cfg.estimated_external_rate_mGy_h, cfg.estimated_cabin_rate_mGy_h):
        if rate is not None and (not math.isfinite(rate) or rate < 0):
            raise ValueError('Assumed estimate rates must be finite and nonnegative')
    if any(not math.isfinite(a+b) or a < 0 or b <= a for a,b in cfg.operational_restrictions):
        raise ValueError('Restrictions must be finite ordered nonnegative intervals')


def simulate_mission(strategy, scenario=None, astronauts=None, repairs=None, config=None):
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
        raise ValueError('Mission origin is outside the frozen radiation record')
    end = min(cfg.max_hours, environment.end_hour-scenario.storm_start_hour)
    state = MissionState(scenario, cfg, deepcopy(astronauts), repairs)
    for a in state.astronauts:
        a.accumulated_radiation += a.radiation_baseline
        a.inside_hours = a.outside_hours = 0.0
        a.estimated_dose_mGy = 0.0 if cfg.estimated_external_rate_mGy_h is not None else None
    def log(action, reason, eva=None):
        state.event_log.append(dict(hour=state.current_mission_time, action=action, reason=reason,
            astronaut=eva.astronaut.name if eva else None, repair=eva.repair_type if eva else None))
    def finish(eva):
        state.next_eva_time = state.current_mission_time+cfg.turnaround_hours
        state.progress.append(eva)
        state.active_eva = None
    # A finite horizon and a strictly increasing clock bound every run.
    while state.current_mission_time < end:
        t = state.current_mission_time
        obs = observe(state)
        eva = state.active_eva
        # Resolve a seven-hour completion before a new launch, with abort precedence
        # for restrictions or the optional estimate; reaching the normal duration is success.
        if eva and t >= eva.scheduled_end_time:
            if obs.operational_abort or (eva.astronaut.estimated_dose_mGy is not None and
                    eva.astronaut.estimated_dose_mGy >= cfg.radiation_abort_threshold_mGy):
                reason = obs.restriction_reason or 'Imperfect operational dose estimate reached configured threshold'
                abort_eva(eva, t, reason);log('aborted', reason, eva)
            else:
                eva.completed = True;eva.reported_end_time = t;eva.end_reason = 'Planned EVA repair completed'
                state.completed_repairs.append(eva.repair_type);log('completed', eva.end_reason, eva)
            finish(eva);obs = observe(state)
        if len(state.completed_repairs) == len(repairs):
            state.status = 'all_repairs_completed';break
        decision = strategy(obs)
        log(decision.action, decision.reason, state.active_eva)
        if decision.action == 'start':
            if state.active_eva or not obs.launch_allowed or decision.astronaut not in obs.available_astronauts or decision.repair_type not in obs.outstanding_repairs:
                raise ValueError('Strategy requested an invalid EVA launch')
            a = next(a for a in state.astronauts if a.name == decision.astronaut)
            state.active_eva = start_eva(t, a, decision.repair_type, scenario.engine_type, cfg)
            state.event_log[-1].update(astronaut=a.name, repair=decision.repair_type)
        elif decision.action == 'abort':
            if not state.active_eva:raise ValueError('No EVA to abort')
            abort_eva(state.active_eva,t,decision.reason);finish(state.active_eva)
            continue
        elif decision.action not in ('wait','continue'):
            raise ValueError('Unknown decision')
        # Split at known operational boundaries, never at predicted radiation peaks.
        boundaries = [end, t+cfg.time_step_hours, state.next_eva_time]
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
            if not outside:
                a.accumulated_radiation += environment.dose(t,until,scenario.cabin_shielding)
                a.inside_hours += until-t
            if a.estimated_dose_mGy is not None:
                rate = cfg.estimated_external_rate_mGy_h if outside else cfg.estimated_cabin_rate_mGy_h
                a.estimated_dose_mGy += rate*(until-t)
        state.current_mission_time = until
    if state.status == 'running':
        # Resolve an EVA ending exactly at the terminal boundary.
        eva = state.active_eva
        if eva:
            obs = observe(state)
            exceeded = (eva.astronaut.estimated_dose_mGy is not None and
                        eva.astronaut.estimated_dose_mGy >= cfg.radiation_abort_threshold_mGy)
            if eva.scheduled_end_time == end and not obs.operational_abort and not exceeded:
                eva.completed=True;eva.reported_end_time=end;eva.end_reason='Planned EVA repair completed'
                state.completed_repairs.append(eva.repair_type);log('completed',eva.end_reason,eva)
            else:
                abort_eva(eva,end,'Emergency/data boundary or operational abort condition');log('aborted',eva.end_reason,eva)
            finish(eva)
        state.status = ('all_repairs_completed' if len(state.completed_repairs)==len(repairs) else
                        'radiation_data_exhausted' if end < cfg.max_hours else 'emergency_duration_reached')
    log('mission_ended',state.status)
    return state
