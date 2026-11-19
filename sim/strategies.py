"""Strategy rules receive only immutable operational observations."""
from .models import Decision, State


def _job_hours(state: State, repair: str) -> float:
    """Planned EVA time (work still needed plus return) for one repair."""
    work = dict(state.repair_work_remaining_h).get(repair)
    return state.planned_eva_hours if work is None else work + state.return_to_airlock_h


def _operational_candidate(state: State, *, radiation_held_repairs=()) -> Decision:
    if state.active_eva is not None:
        eva = state.active_eva
        if eva.returning:
            return Decision('continue', 'Return to airlock; continue outside exposure accounting')
        if state.operational_abort:
            return Decision('abort', state.restriction_reason)
        if eva.elapsed_hours + state.return_to_airlock_h >= state.max_continuous_eva_hours:
            return Decision('abort', 'Return now to meet the predetermined continuous-EVA time cap')
        if (eva.estimated_dose_mGy is not None and
                eva.estimated_dose_mGy >= state.radiation_abort_threshold_mGy):
            return Decision('abort', 'Imperfect operational dose estimate reached configured threshold')
        return Decision('continue', 'No permitted operational abort condition triggered')
    recovery = state.recovery
    hold_reason = 'Repeat EVA suspended after radiation abort pending independent radiation clearance'
    if recovery is not None:
        if recovery.stabilization_required and not recovery.safety_blockers:
            return Decision('stabilize', recovery.stabilization_action)
        if not state.outstanding_repairs:
            if recovery.continuation_blockers:
                return Decision('safe_hold', '; '.join(recovery.continuation_blockers))
            return Decision('resume_mission', 'Required repairs complete and continuation approved')
        if not recovery.ready_repairs:
            return Decision('safe_hold', '; '.join(reason for _, reason in recovery.blocked_repairs))
        repairs = tuple(repair for repair in recovery.ready_repairs if repair not in radiation_held_repairs)
        if not repairs:
            return Decision('safe_hold', hold_reason)
        if any(repair in radiation_held_repairs for repair in recovery.deadline_repairs):
            return Decision('safe_hold', 'Urgent repair chain blocked. ' + hold_reason)
        deadline_priority = False
        if recovery.repair_deadline_hours is not None and recovery.deadline_repairs:
            count = len(recovery.deadline_repairs)
            earliest_finish = (max(state.current_mission_time, state.next_eva_time)
                               + sum(_job_hours(state, repair) for repair in recovery.deadline_repairs)
                               + (count - 1) * state.turnaround_hours - state.return_to_airlock_h)
            if earliest_finish > recovery.repair_deadline_hours:
                return Decision('no_recovery_plan', 'Critical repair and prerequisites cannot fit before the assumed deadline')
            if earliest_finish + state.planned_eva_hours + state.turnaround_hours > recovery.repair_deadline_hours:
                deadline_priority = True
                repairs = tuple(repair for repair in repairs if repair in recovery.deadline_repairs)
        if not state.launch_allowed:
            return Decision('wait', state.restriction_reason)
        eligible = dict(recovery.eligible_crews)
        for repair in repairs:
            for name in state.available_astronauts:
                if name in eligible[repair]:
                    reason = ('Prioritize critical repair chain to preserve the assumed deadline'
                              if deadline_priority else 'Next configured repair satisfying shared case constraints')
                    return Decision('start', reason, name, repair)
        return Decision('wait', 'No feasible repair/crew pairing; retain shared safety constraints')
    if not state.outstanding_repairs:
        return Decision('wait', 'All required repairs completed')
    repairs = tuple(repair for repair in state.outstanding_repairs if repair not in radiation_held_repairs)
    if not repairs:
        return Decision('safe_hold', hold_reason)
    if not state.launch_allowed:
        return Decision('wait', state.restriction_reason)
    if not state.available_astronauts:
        return Decision('wait', 'No eligible crew: availability, consecutive-EVA rule or optional estimate budget')
    return Decision('start', 'Next priority repair; preset launch conditions satisfied',
                    state.available_astronauts[0], repairs[0])


def strategy_a(state: State) -> Decision:
    """Legacy immediate-repair implementation, excluded from numerical comparisons.

    Retained for historical reproducibility and low-level engineering tests; this
    is not a validated health-first baseline.
    """
    return _operational_candidate(state)


def _informed_strategy(state: State, *, use_biology=False, wait_for_lower_dose=False) -> Decision:
    """Apply common safety gates before strategy-specific crew and timing choices."""
    if state.radiation and state.radiation.matched_current_rate:
        # The radiation adapter supplies each policy's evidence-adjusted risk.
        # All use B's action rule, including rotation and reassessment timing.
        use_biology = wait_for_lower_dose = False
    radiation_holds = state.radiation.radiation_held_repairs if state.radiation else ()
    candidate = _operational_candidate(state, radiation_held_repairs=radiation_holds)
    if candidate.action == 'resume_mission':
        if state.radiation is None or not state.radiation.current:
            return Decision('safe_hold', 'Crew exposure assessment unavailable; reassess continuation')
        if use_biology and state.radiation.post_eva_review_pending:
            return Decision('safe_hold', 'Repairs complete; await post-EVA crew exposure review')
        if any(not estimate.acceptable for estimate in state.radiation.current):
            return Decision('safe_hold', 'Repairs complete; crew exposure assessment requires review before continuation')
        return candidate
    if candidate.action not in ('start', 'continue'):
        return candidate
    radiation = state.radiation
    if radiation is None:
        return Decision('abort' if state.active_eva else 'wait', 'Forecast unavailable; retain operational safety gates')
    if state.active_eva:
        if state.active_eva.returning:
            return candidate
        option = next(iter(radiation.options), None)
        if wait_for_lower_dose and radiation.live_markers and radiation.immediate_return is not None:
            if not radiation.immediate_return.acceptable:
                return Decision('abort', 'In-EVA biomarker assessment calls for immediate return: '
                                + radiation.immediate_return.reason)
            if option is None or not option.acceptable:
                return Decision('abort', 'In-EVA biomarker assessment does not support completing the work: '
                                + (option.reason if option else 'forecast coverage ends before planned return'))
            return Decision('continue', 'In-EVA biomarker assessment supports finishing the planned work: ' + option.reason)
        if option is None or not option.acceptable:
            return Decision('abort', option.reason if option else 'Forecast cannot cover remaining EVA')
        return Decision('continue', option.reason)
    eligible = (dict(state.recovery.eligible_crews)[candidate.repair_type]
                if state.recovery else state.available_astronauts)
    review_holds = set(radiation.post_eva_review_pending) if use_biology else set()
    current_holds = {estimate.astronaut for estimate in radiation.current if not estimate.acceptable} if use_biology else set()
    forecast_veto = use_biology and radiation.forecast_launch_veto
    restarting = candidate.repair_type in radiation.restart_ready_repairs
    feasible = []
    for option in radiation.options:
        if not use_biology and option.departure_h != state.current_mission_time:
            continue
        if (option.astronaut not in eligible or not option.acceptable
                or option.astronaut in review_holds or option.astronaut in current_holds):
            continue
        if option.repairs and candidate.repair_type not in option.repairs:
            continue
        if (forecast_veto or restarting) and option.forecast_exceedance_probability > radiation.launch_risk_tolerance + 1e-12:
            continue
        if any(start < option.end_h and end > option.departure_h for start, end in state.operational_restrictions):
            continue
        if state.recovery and state.recovery.repair_deadline_hours is not None:
            count = len(state.recovery.deadline_repairs)
            # A noncritical task still consumes an EVA and turnaround before the
            # outstanding critical chain. Count a critical candidate only once.
            chain = list(state.recovery.deadline_repairs)
            if count and candidate.repair_type not in chain:
                chain.append(candidate.repair_type)
            tasks = len(chain)
            completion = (option.departure_h + sum(_job_hours(state, repair) for repair in chain)
                          + max(0, tasks - 1) * state.turnaround_hours - state.return_to_airlock_h)
            if count and completion > state.recovery.repair_deadline_hours:
                continue
        feasible.append(option)
    if feasible:
        earliest = min(option.departure_h for option in feasible)
        if earliest > state.current_mission_time:
            return Decision('wait', f'Reassess before candidate departure at {earliest:g} h; '
                            'includes cabin exposure while waiting')
        ready = [option for option in feasible if option.departure_h == earliest]

        def exposure_score(option):
            # Rank by the upper dose of the organ closest to its own reference.
            posterior = max(dose / ref for dose, ref in zip(option.upper_mGy_eq, radiation.references))
            return max(posterior, option.forecast_upper_reference_fraction) if wait_for_lower_dose else posterior

        selected = min(ready, key=exposure_score) if use_biology else ready[0]
        repair = candidate.repair_type
        critical = state.recovery and repair in state.recovery.deadline_repairs
        if wait_for_lower_dose and not critical:
            # Optional delay only. Preserve enough time for all remaining work,
            # assume no later waits in that fit check, and never move a target later.
            latest = min(dict(state.dose_wait_targets).get(repair, earliest + 4),
                         radiation.forecast_end_h - sum(_job_hours(state, r) for r in state.outstanding_repairs)
                         - (len(state.outstanding_repairs) - 1) * state.turnaround_hours)
            alternatives = [option for option in feasible if earliest < option.departure_h <= latest]
            if alternatives:
                future = min(alternatives, key=lambda option: (exposure_score(option), option.departure_h))
                if exposure_score(future) < 0.8 * exposure_score(selected):
                    return Decision('wait', f'Lower projected exposure at hour {future.departure_h:g}; reassess before launch',
                                    repair_type=repair, dose_wait_until_h=future.departure_h)
        reason = selected.reason
        if restarting:
            reason = 'Restart after sustained improvement in common forecast; ' + reason
        if use_biology:
            reason += f'; selected crew by projected exposure ({exposure_score(selected):.1%} of organ reference)'
        return Decision('start', reason, selected.astronaut, repair)
    if state.current_mission_time + state.planned_eva_hours > radiation.forecast_end_h:
        return Decision('safe_hold', 'Forecast coverage insufficient for another EVA; recovery reassessment required')
    reasons = sorted({option.reason for option in radiation.options if option.departure_h == state.current_mission_time})
    if review_holds.intersection(eligible):
        reasons.append('Post-EVA H2AX review pending for eligible crew')
    if current_holds.intersection(eligible):
        reasons.append('Current dose estimate or conflicting readings require individual exposure review')
    if forecast_veto and any(option.acceptable and option.forecast_exceedance_probability
                           > radiation.launch_risk_tolerance + 1e-12 for option in radiation.options):
        reasons.append('Biological estimate alone cannot clear a forecast-blocked EVA')
    if restarting:
        reasons.append('Restart requires acceptable cumulative risk under both forecast and crew reassessment')
    if not use_biology:
        return Decision('wait', '; '.join([*reasons, 'No acceptable departure at the estimated current rate; reassess']))
    return Decision('wait', '; '.join(reasons) + '; no acceptable feasible window in current forecast search; reassess')


def strategy_b(state: State) -> Decision:
    """Assess departure and continuation using the currently estimated rate."""
    return _informed_strategy(state)


def strategy_c(state: State) -> Decision:
    """Choose a crew member using returned conventional biological estimates."""
    return _informed_strategy(state, use_biology=True)


def strategy_d(state: State) -> Decision:
    """Use advanced measurements for crew selection and short dose-saving waits."""
    return _informed_strategy(state, use_biology=True, wait_for_lower_dose=True)


INFORMED_STRATEGIES = {strategy_b: 'B', strategy_c: 'C', strategy_d: 'D'}
