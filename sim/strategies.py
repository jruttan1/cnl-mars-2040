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
        if 'conserve_support' in recovery.allowed_actions:
            return Decision('conserve_support', 'Conservative fallback: shed nonessential loads')
        for action in ('resume_mission', 'begin_checkout'):
            if action in recovery.allowed_actions:
                return Decision(action, 'Shared recovery prerequisites satisfied')
        if not state.outstanding_repairs and 'Mission continuation authority withheld' in recovery.continuation_blockers:
            return Decision('safe_hold', 'Continuation authority withheld; request reassessment')
        if not state.launch_allowed:
            return Decision('wait', state.restriction_reason)
        eligible = dict(recovery.eligible_crews)
        for repair in recovery.ready_repairs:
            for name in state.available_astronauts:
                if name in eligible[repair]:
                    return Decision('start', 'Next feasible engine-specific repair within shared safety/crew constraints', name, repair)
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
