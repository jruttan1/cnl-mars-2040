"""Strategy rules receive only immutable operational observations."""
from .models import Decision, State


def strategy_a(state: State) -> Decision:
    if state.active_eva is not None:
        eva = state.active_eva
        if state.operational_abort:
            return Decision('abort', state.restriction_reason)
        if eva.elapsed_hours >= state.max_continuous_eva_hours:
            return Decision('abort', 'Predetermined continuous-EVA time cap reached')
        if (eva.estimated_dose_mGy is not None and
                eva.estimated_dose_mGy >= state.radiation_abort_threshold_mGy):
            return Decision('abort', 'Imperfect operational dose estimate reached configured threshold')
        return Decision('continue', 'No permitted operational abort condition triggered')
    recovery = state.recovery
    if recovery is not None:
        if not state.outstanding_repairs:
            if recovery.continuation_blockers:
                return Decision('safe_hold', '; '.join(recovery.continuation_blockers))
            return Decision('resume_mission', 'Required repairs complete and continuation approved')
        if not recovery.ready_repairs:
            return Decision('safe_hold', '; '.join(reason for _, reason in recovery.blocked_repairs))
        if not state.launch_allowed:
            return Decision('wait', state.restriction_reason)
        eligible = dict(recovery.eligible_crews)
        for repair in recovery.ready_repairs:
            for name in state.available_astronauts:
                if name in eligible[repair]:
                    return Decision('start', 'Next configured repair satisfying shared case constraints', name, repair)
        return Decision('wait', 'No feasible repair/crew pairing; retain shared safety constraints')
    if not state.outstanding_repairs:
        return Decision('wait', 'All required repairs completed')
    if not state.launch_allowed:
        return Decision('wait', state.restriction_reason)
    if not state.available_astronauts:
        return Decision('wait', 'No eligible crew: availability, consecutive-EVA rule or optional estimate budget')
    return Decision('start', 'Next priority repair; preset launch conditions satisfied',
                    state.available_astronauts[0], state.outstanding_repairs[0])


def strategy_b(state: State) -> Decision:
    raise NotImplementedError('Strategy B is not implemented')


def strategy_c(state: State) -> Decision:
    raise NotImplementedError('Strategy C is not implemented')


def strategy_d(state: State) -> Decision:
    raise NotImplementedError('Strategy D is not implemented')
