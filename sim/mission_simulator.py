"""Mission progression with shared, hidden OLTARIS BFO exposure accounting."""
from copy import deepcopy
from dataclasses import asdict, replace
from .mission_recovery import MissionRecovery
from .repair_tasks import REPAIRS
from .background_radiation import interval as gcr_interval
from .anatomical_reference import dose_vector
import math
from sim.assumptions import DEFAULT_ASSUMPTIONS
from radiation.anatomical_environment import load_environment, interval_exposure
from .models import (Astronaut, EVA, Scenario, MissionState, State, Decision,
                     ActiveEVAObservation)
from .informed_config import InformedConfig, ForecastSpec
from .radiation_information import RadiationInformation
from .strategies import INFORMED_STRATEGIES


class RadiationEnvironment:
    """One anatomical environment for all strategies; never supplied as an observation."""
    def __init__(self, scenario: Scenario):
        if not math.isfinite(scenario.spe_scale) or scenario.spe_scale <= 0:
            raise ValueError("SPE scale must be finite and positive")
        self.scenario = scenario
        gcr_interval(0, 0, scenario.shielding, scenario.gcr_scale)
        severity = int(scenario.severity.rsplit('-', 1)[1])
        self.anatomy_ratios = {depth: tuple(selected / baseline for selected, baseline in
            zip(dose_vector(scenario.anatomy, severity, depth), dose_vector('MAX', severity, depth)))
            for depth in (scenario.shielding, scenario.cabin_shielding)}
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
        spe = interval_exposure(self.data[self.data.shielding_g_cm2.eq(shielding)],
            mission_start + self.scenario.storm_start_hour,
            mission_end + self.scenario.storm_start_hour, quantity)
        index = {'absorbed_dose_mGy': 0, 'gray_equivalent_mGy_eq': 1}[quantity]
        return spe * self.scenario.spe_scale * self.anatomy_ratios[shielding][index] + gcr_interval(mission_start, mission_end, shielding, self.scenario.gcr_scale)[index]


def get_hourly_exposure(hour: float, scenario: Scenario, environment=None) -> float:
    """One mission-relative hour of external modeled BFO absorbed dose, in mGy."""
    return (environment or RadiationEnvironment(scenario)).dose(hour, hour+1, scenario.shielding)


def start_eva(start_time, astronaut, repair_type, engine_type, config=DEFAULT_ASSUMPTIONS, work_hours=None) -> EVA:
    if start_time < astronaut.available_from:
        raise ValueError('Astronaut is not available')
    work = config.eva_duration_hours if work_hours is None else work_hours
    return EVA(start_time, start_time+work, None, False, astronaut,
               repair_type, engine_type, last_update_time=start_time, work_hours=work)


def abort_eva(eva: EVA, current_time: float, reason: str, return_hours: float = 0.5) -> None:
    """Stop work and begin return; outside exposure continues until airlock arrival."""
    if eva.reported_end_time is not None or eva.return_started_h is not None:
        return
    if current_time != eva.last_update_time:
        raise ValueError('Account exposure to the abort time before ending the EVA')
    eva.aborted = True
    eva.return_started_h = current_time
    eva.return_end_h = current_time + return_hours
    eva.end_reason = reason


def update_eva(eva: EVA, current_time: float, scenario: Scenario, environment=None) -> None:
    """Account only the unprocessed interval. Terminal EVAs are immutable here."""
    if eva.reported_end_time is not None:
        return
    start = eva.last_update_time if eva.last_update_time is not None else eva.start_time
    end = min(current_time, eva.return_end_h if eva.return_end_h is not None else eva.scheduled_end_time)
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
    horizon = min(cfg.max_hours, cfg.observation_end_h or cfg.max_hours)
    outstanding = [r for r in state.required_repairs if r not in state.completed_repairs]
    work = [state.work_remaining.get(r, cfg.eva_duration_hours) for r in outstanding] or [cfg.eva_duration_hours]
    # Launch needs only the shortest outstanding job to fit; planned duration reports the longest.
    if t+min(work)+cfg.return_to_airlock_h > horizon:
        launch = False
        reason = 'Insufficient emergency time for a complete planned EVA'
    # Fewest previous attempts first; input order breaks ties. No true dose ranking.
    crew_order = state.astronauts
    if cfg.crew_rotation:
        crew_order = sorted(crew_order, key=lambda a: sum(e.astronaut.name == a.name for e in state.progress))
    previous = state.progress[-1].astronaut.name if state.progress else None
    available = tuple(a.name for a in crew_order if a.available_from <= t and a.rest_until_h <= t and
        a.medically_fit_for_eva is True and a.rested_for_eva is True and
        (cfg.allow_consecutive_evas or a.name != previous) and
        (a.estimated_dose_mGy is None or a.estimated_dose_mGy < cfg.radiation_abort_threshold_mGy))
    eva = state.active_eva
    active = None if eva is None else ActiveEVAObservation(
        eva.astronaut.name, eva.repair_type, t-eva.start_time, eva.astronaut.estimated_dose_mGy,
        eva.return_started_h is not None,
        max(0, (eva.return_end_h if eva.return_end_h is not None else
                eva.scheduled_end_time + cfg.return_to_airlock_h) - t))
    recovery_obs = None if recovery is None else recovery.observe(state.completed_repairs, state.engineering_stabilized)
    if recovery_obs is not None and not recovery_obs.ready_repairs:
        launch = False
        if not reason:
            reason = '; '.join(reason for _, reason in recovery_obs.blocked_repairs) or 'Mission decision pending'
    return State(t, available, tuple(r for r in state.required_repairs if r not in state.completed_repairs),
                 tuple(state.completed_repairs), active, launch, reason, restricted,
                 cfg.eva_time_limit_hours, cfg.radiation_abort_threshold_mGy, recovery_obs,
                 max(work) + cfg.return_to_airlock_h, cfg.turnaround_hours, state.next_eva_time,
                 operational_restrictions=cfg.operational_restrictions, return_to_airlock_h=cfg.return_to_airlock_h,
                 dose_wait_targets=tuple(state.dose_wait_targets.items()),
                 repair_work_remaining_h=tuple((r, state.work_remaining.get(r, cfg.eva_duration_hours)) for r in outstanding))


def _validate(scenario, crew, repairs, cfg):
    values = [cfg.max_hours, cfg.time_step_hours, cfg.eva_duration_hours, cfg.return_to_airlock_h]
    if cfg.max_continuous_eva_hours is not None:
        values.append(cfg.max_continuous_eva_hours)
        if cfg.max_continuous_eva_hours <= cfg.return_to_airlock_h:
            raise ValueError('EVA time cap must leave time to return')
    if cfg.observation_end_h is not None:
        values.append(cfg.observation_end_h)
    if not math.isfinite(cfg.abort_progress_credit) or not 0 <= cfg.abort_progress_credit <= 1:
        raise ValueError('Abort progress credit must be between 0 and 1')
    if not math.isfinite(cfg.minimum_rest_h) or cfg.minimum_rest_h < 0:
        raise ValueError('Minimum rest must be finite and nonnegative')
    if type(cfg.continued_shelter_feasible) is not bool:
        raise ValueError('Continued shelter feasibility must be explicitly boolean')
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
    if len(set(repairs)) != len(repairs) or not set(repairs) <= set(REPAIRS):
        raise ValueError('Repairs must be unique supported categories')
    for a in crew:
        if any(value is not None and type(value) is not bool for value in (a.medically_fit_for_eva, a.rested_for_eva)):
            raise ValueError('Medical and rest assessments must be true, false or unknown')
        if not a.name or any(not math.isfinite(v) or v < 0 for v in
                           (a.radiation_baseline, a.accumulated_radiation, a.available_from,
                            a.bfo_initial_gray_equivalent_mGy_eq, a.bfo_gray_equivalent_mGy_eq, a.rest_until_h)):
            raise ValueError('Invalid crew initialization')
    for rate in (cfg.estimated_external_rate_mGy_h, cfg.estimated_cabin_rate_mGy_h):
        if rate is not None and (not math.isfinite(rate) or rate < 0):
            raise ValueError('Assumed estimate rates must be finite and nonnegative')
    if any(not math.isfinite(a+b) or a < 0 or b <= a for a,b in cfg.operational_restrictions):
        raise ValueError('Restrictions must be finite ordered nonnegative intervals')


def simulate_mission(strategy, scenario=None, astronauts=None, repairs=None, config=None, recovery_config=None,
                     information_config=None, recovery_schedule=()):
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
    physical_end = environment.end_hour - scenario.storm_start_hour
    end = min(cfg.max_hours, physical_end, cfg.observation_end_h or cfg.max_hours)
    if cfg.continued_shelter_feasible and cfg.observation_end_h is None:
        raise ValueError('Continued shelter comparison requires an explicit observation end')
    if cfg.observation_end_h is not None and cfg.observation_end_h > physical_end:
        raise ValueError('Observation period exceeds available radiation data')
    state = MissionState(scenario, cfg, deepcopy(astronauts), repairs)
    state.work_remaining = {repair: cfg.eva_duration_hours for repair in repairs}
    information = None
    level = INFORMED_STRATEGIES.get(strategy)
    if information_config is not None and level is None:
        raise ValueError('Information configuration requires strategy B, C or D')
    if level:
        if cfg.max_hours > 720:
            raise ValueError('Informed policies currently support a single event of at most 30 days')
        if cfg.estimated_external_rate_mGy_h is not None:
            raise ValueError('Use informed estimates or the legacy fixed-rate estimate, not both')
        if any(astronaut.bfo_initial_absorbed_dose_mGy or astronaut.bfo_absorbed_dose_mGy or
               astronaut.bfo_initial_gray_equivalent_mGy_eq or astronaut.bfo_gray_equivalent_mGy_eq
               for astronaut in astronauts):
            raise ValueError('Informed runs require zero initial exposure; pre-mission exposure histories are not implemented')
        information_config = information_config or InformedConfig(forecast=ForecastSpec(anatomy=scenario.anatomy))
        if information_config.forecast.anatomy != scenario.anatomy:
            raise ValueError('Forecast anatomy must match the known crew reference cohort')
        information = RadiationInformation(level, information_config, [astronaut.name for astronaut in astronauts])
        state.information_config = asdict(information_config)
        state.measurement_log = information.log
        state.estimate_history = information.estimate_log
    recovery = None if recovery_config is None else MissionRecovery(
        scenario.engine_type, recovery_config, [a.name for a in state.astronauts], repairs)
    if recovery is not None:
        state.recovery_config = recovery_config
    for a in state.astronauts:
        a.accumulated_radiation += a.radiation_baseline
        a.bfo_gray_equivalent_mGy_eq += a.bfo_initial_gray_equivalent_mGy_eq
        a.inside_hours = a.outside_hours = 0.0
        a.estimated_dose_mGy = 0.0 if cfg.estimated_external_rate_mGy_h is not None else None
    schedule = list(recovery_schedule)
    if schedule and recovery is None:
        raise ValueError('Recovery reassessments require an initial recovery configuration')
    if any(not math.isfinite(hour) or hour <= 0 for hour, _ in schedule):
        raise ValueError('Reassessment times must be positive and finite')
    if [hour for hour, _ in schedule] != sorted(set(hour for hour, _ in schedule)):
        raise ValueError('Reassessment times must be unique and increasing')
    for _, updated in schedule:
        MissionRecovery(scenario.engine_type, updated, [person.name for person in state.astronauts], repairs)
    pending_status = None

    def log(action, reason, eva=None):
        state.event_log.append(dict(hour=state.current_mission_time, action=action, reason=reason,
            astronaut=eva.astronaut.name if eva else None, repair=eva.repair_type if eva else None))

    def resolve_eva():
        eva = state.active_eva
        now = state.current_mission_time
        if eva is None:
            return
        if eva.return_end_h is not None and now >= eva.return_end_h:
            eva.reported_end_time = now
            eva.astronaut.rest_until_h = max(eva.astronaut.rest_until_h, now + cfg.minimum_rest_h)
            state.next_eva_time = now + cfg.turnaround_hours
            if eva.aborted and not eva.completed and cfg.abort_progress_credit > 0:
                # Credit hours actually worked (not sampling/return time) toward this repair.
                extension = eva.scheduled_end_time - eva.start_time - eva.work_hours
                worked = max(0.0, min(eva.work_hours, eva.return_started_h - eva.start_time - extension))
                eva.credited_work_h = worked * cfg.abort_progress_credit
                state.work_remaining[eva.repair_type] = max(
                    0.0, state.work_remaining[eva.repair_type] - eva.credited_work_h)
            state.progress.append(eva)
            state.active_eva = None
            log('returned', 'Astronaut inside airlock; rest and turnaround begin', eva)
        elif eva.return_started_h is None and now >= eva.scheduled_end_time:
            eva.completed = True
            eva.end_reason = 'Planned repair work completed; returning to airlock'
            state.completed_repairs.append(eva.repair_type)
            eva.return_started_h = now
            eva.return_end_h = now + cfg.return_to_airlock_h
            log('completed', eva.end_reason, eva)

    def terminate(status, reason):
        nonlocal pending_status
        if state.outcome_hour is None:
            state.outcome_hour = state.current_mission_time
        pending_status = status
        if state.active_eva is not None:
            abort_eva(state.active_eva, state.current_mission_time, reason, cfg.return_to_airlock_h)
        else:
            state.status = status

    def observation():
        if information:
            information.update(state)
        observed = observe(state, recovery)
        if information:
            # Panels add time to every job, so project the longest and shortest outstanding job.
            work = [hours for _, hours in observed.repair_work_remaining_h] or [cfg.eva_duration_hours]
            longest = information.projected_duration(max(work), cfg.return_to_airlock_h)
            shortest = information.projected_duration(min(work), cfg.return_to_airlock_h)
            observed = replace(observed, planned_eva_hours=longest)
        else:
            shortest = observed.planned_eva_hours - (max([h for _, h in observed.repair_work_remaining_h] or [cfg.eva_duration_hours])
                                                     - min([h for _, h in observed.repair_work_remaining_h] or [cfg.eva_duration_hours]))
        if state.current_mission_time + shortest > end:
            observed = replace(observed, launch_allowed=False, restriction_reason='Insufficient observation time for EVA and return')
        if information:
            observed = replace(observed, radiation=information.observe(state, observed))
        return observed

    def advance(until):
        start = state.current_mission_time
        active = state.active_eva
        if active:
            update_eva(active, until, scenario, environment)
        for astronaut in state.astronauts:
            outside = active is not None and active.astronaut is astronaut
            shielding = scenario.shielding if outside else scenario.cabin_shielding
            absorbed = environment.dose(start, until, shielding)
            gray_equivalent = environment.gray_equivalent(start, until, shielding)
            if not outside:
                astronaut.accumulated_radiation += absorbed
                astronaut.bfo_gray_equivalent_mGy_eq += gray_equivalent
                astronaut.inside_hours += until - start
            location = 'return' if outside and active.return_started_h is not None else 'eva' if outside else 'cabin'
            gcr = gcr_interval(start, until, shielding, scenario.gcr_scale)
            state.exposure_history.append(dict(astronaut=astronaut.name, start_hour=start, end_hour=until,
                location=location, shielding_g_cm2=shielding, bfo_absorbed_dose_mGy=absorbed,
                bfo_gray_equivalent_mGy_eq=gray_equivalent,
                spe_bfo_absorbed_dose_mGy=absorbed - gcr[0],
                spe_bfo_gray_equivalent_mGy_eq=gray_equivalent - gcr[1],
                gcr_bfo_absorbed_dose_mGy=gcr[0], gcr_bfo_gray_equivalent_mGy_eq=gcr[1],
                gcr_skin_gray_equivalent_mGy_eq=gcr[2], gcr_lens_gray_equivalent_mGy_eq=gcr[3]))
            if astronaut.estimated_dose_mGy is not None:
                rate = cfg.estimated_external_rate_mGy_h if outside else cfg.estimated_cabin_rate_mGy_h
                astronaut.estimated_dose_mGy += rate * (until - start)
        state.current_mission_time = until

    def next_time(limit):
        now = state.current_mission_time
        boundaries = [limit, now + cfg.time_step_hours, state.next_eva_time]
        boundaries.extend(person.available_from for person in state.astronauts)
        boundaries.extend(person.rest_until_h for person in state.astronauts)
        boundaries.extend(edge for interval in cfg.operational_restrictions for edge in interval)
        if information:
            boundaries.extend((information.next_boundary(now), information.forecast.end_h))
        if recovery and recovery.deadline is not None:
            boundaries.append(recovery.deadline)
        if schedule:
            boundaries.append(schedule[0][0])
        if state.active_eva:
            eva = state.active_eva
            boundaries.append(eva.return_end_h if eva.return_end_h is not None else eva.scheduled_end_time)
            boundaries.append(eva.start_time + cfg.eva_time_limit_hours - cfg.return_to_airlock_h)
        return min(boundary for boundary in boundaries if boundary > now)

    while state.current_mission_time < end:
        now = state.current_mission_time
        while schedule and schedule[0][0] <= now:
            _, updated = schedule.pop(0)
            recovery = MissionRecovery(scenario.engine_type, updated, [person.name for person in state.astronauts], repairs)
            state.recovery_config = updated
            log('reassessed', 'Scenario-supplied damage/access/authorization assessment updated')
        resolve_eva()
        if pending_status and state.active_eva is None:
            state.status = pending_status
            break
        if recovery and recovery.missed_deadline(now, state.completed_repairs) and pending_status is None:
            terminate('no_feasible_recovery_plan', 'Scenario urgent-repair deadline missed; no automatic safety override')
            log('no_recovery_plan', 'Scenario urgent-repair deadline missed')
            if state.status != 'running':
                break
        observed = observation()
        if (state.active_eva and state.active_eva.completed and state.active_eva.return_started_h == now and
                (observed.operational_abort or (observed.radiation and
                 any(not estimate.acceptable for estimate in observed.radiation.current)))):
            log('assessment_required', 'Completed work retained; return exposure and crew assessment continue', state.active_eva)
        if pending_status:
            decision = Decision('continue', 'Returning before terminating recovery attempt')
        elif recovery is None and len(state.completed_repairs) == len(repairs) and state.active_eva is None:
            terminate('all_repairs_completed', 'Repairs completed and crew inside')
            break
        else:
            decision = strategy(observed)
        checked_crew = set()
        while level == 'D' and decision.action == 'start' and decision.astronaut not in checked_crew:
            checked_crew.add(decision.astronaut)
            information.before_launch(state, decision.astronaut)
            observed = observation()
            decision = strategy(observed)
        log(decision.action, decision.reason, state.active_eva)
        if decision.dose_wait_until_h is not None:
            target = state.dose_wait_targets.setdefault(decision.repair_type, decision.dose_wait_until_h)
            state.event_log[-1].update(repair=decision.repair_type, dose_wait_until_h=decision.dose_wait_until_h)
        if observed.radiation:
            selected = next((option for option in observed.radiation.options
                             if option.departure_h == now and (not option.repairs or decision.repair_type in option.repairs)
                             and option.astronaut ==
                             (decision.astronaut or (state.active_eva.astronaut.name if state.active_eva else None))), None)
            state.event_log[-1].update(pending_results=observed.radiation.pending_results,
                                      projected_upper_mGy_eq=selected.upper_mGy_eq if selected else None,
                                      projected_reference_exceedance_probability=selected.reference_exceedance_probability if selected else None,
                                      forecast_reference_exceedance_probability=selected.forecast_exceedance_probability if selected else None,
                                      in_eva_markers=observed.radiation.live_markers,
                                      post_eva_review_pending=observed.radiation.post_eva_review_pending,
                                      radiation_held_repairs=observed.radiation.radiation_held_repairs)
        if decision.action == 'stabilize':
            if recovery is None or state.active_eva or state.engineering_stabilized or observed.recovery.safety_blockers:
                raise ValueError('Protective-action confirmation is not permitted')
            state.engineering_stabilized = True
            continue
        if decision.action == 'start':
            if (state.active_eva or not observed.launch_allowed or decision.astronaut not in observed.available_astronauts
                    or decision.repair_type not in observed.outstanding_repairs):
                raise ValueError('Strategy requested an invalid EVA launch')
            if observed.radiation and decision.repair_type in observed.radiation.radiation_held_repairs:
                raise ValueError('Strategy requested an EVA on a task suspended after a radiation abort')
            if recovery:
                recovery.require_launch(decision.repair_type, decision.astronaut, state.completed_repairs, state.engineering_stabilized)
            astronaut = next(person for person in state.astronauts if person.name == decision.astronaut)
            state.active_eva = start_eva(now, astronaut, decision.repair_type, scenario.engine_type, cfg,
                                         state.work_remaining[decision.repair_type])
            state.event_log[-1].update(astronaut=astronaut.name, repair=decision.repair_type)
            if information and decision.repair_type in observed.radiation.restart_ready_repairs:
                review = information.restart_reviews[decision.repair_type]
                state.event_log[-1].update(forecast_restart=True,
                                           restart_quiet_since_h=now - information.config.restart_quiet_hours,
                                           previous_abort_return_h=review.return_h)
        elif decision.action == 'abort':
            if state.active_eva is None:
                raise ValueError('No EVA to abort')
            if information and observed.radiation:
                option = next(iter(observed.radiation.options), None)
                early_return = observed.radiation.immediate_return
                if option is None or not option.acceptable or (early_return and not early_return.acceptable):
                    information.record_radiation_abort(state.active_eva.astronaut.name, now,
                                                       now + cfg.return_to_airlock_h,
                                                       repair=state.active_eva.repair_type,
                                                       planned_hours=information.projected_duration(
                                                           dict(observed.repair_work_remaining_h).get(
                                                               state.active_eva.repair_type, cfg.eva_duration_hours),
                                                           cfg.return_to_airlock_h),
                                                       eva_depth=scenario.shielding)
                    state.event_log[-1]['requires_crew_reassessment'] = True
                    if state.active_eva.repair_type in information.radiation_held_repairs:
                        state.event_log[-1]['suspended_repair'] = state.active_eva.repair_type
            abort_eva(state.active_eva, now, decision.reason, cfg.return_to_airlock_h)
        elif decision.action in ('resume_mission', 'no_recovery_plan', 'abort_mission'):
            if decision.action == 'resume_mission':
                if recovery is None or state.active_eva or observed.recovery.continuation_blockers:
                    raise ValueError('Separate mission-continuation readiness/authorization required')
                status = 'mission_continuation_authorized'
            else:
                status = 'no_feasible_recovery_plan' if decision.action == 'no_recovery_plan' else 'mission_objective_abandoned'
            terminate(status, decision.reason)
            if state.status != 'running':
                break
        elif decision.action not in ('wait', 'continue', 'safe_hold', 'shelter'):
            raise ValueError('Unknown decision')
        elif decision.action in ('safe_hold', 'shelter') and state.active_eva is not None:
            abort_eva(state.active_eva, now, decision.reason, cfg.return_to_airlock_h)
        next_boundary = next_time(end)
        if decision.dose_wait_until_h is not None:
            next_boundary = min(next_boundary, target, decision.dose_wait_until_h)
        advance(next_boundary)

    resolve_eva()
    if state.status == 'running':
        state.status = pending_status or ('all_repairs_completed' if recovery is None and not state.active_eva
                       and len(state.completed_repairs) == len(repairs) else
                       'radiation_data_exhausted' if end == physical_end else 'observation_or_mission_horizon_reached')
    if state.outcome_hour is None:
        state.outcome_hour = state.current_mission_time
    if state.active_eva and state.active_eva.return_started_h is None:
        abort_eva(state.active_eva, state.current_mission_time, 'Recovery observation ended during EVA', cfg.return_to_airlock_h)
    log('recovery_decision_ended', state.status)
    if cfg.continued_shelter_feasible and cfg.observation_end_h is not None:
        while state.current_mission_time < cfg.observation_end_h:
            resolve_eva()
            if information:
                information.update(state)
                information.observe(state, replace(observe(state, recovery), launch_allowed=False))
            advance(next_time(cfg.observation_end_h))
        resolve_eva()
    if information:
        information.update(state)
        information.observe(state, replace(observe(state, recovery), launch_allowed=False))
    state.exposure_observation_end_h = state.current_mission_time
    if cfg.continued_shelter_feasible and cfg.observation_end_h is not None and math.isclose(state.current_mission_time, cfg.observation_end_h):
        state.exposure_comparison_basis = 'common_observation_period'
    log('mission_ended', state.status)
    return state
