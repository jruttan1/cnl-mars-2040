"""Qualitative recovery constraints shared by every policy; no radiation or RNG imports.

All numerical defaults are hypothetical testable scenario assumptions, not reactor design
limits. See docs/mission_recovery.md for case facts, engineering sources and exclusions.
"""
from dataclasses import dataclass, field
import math

REPAIRS = ('communications', 'monitoring', 'propulsion')
MODEL_VERSION = 'qualitative_recovery_v1'


@dataclass(frozen=True)
class EngineProfile:
    repair_priority: tuple[str, ...]
    propulsion_access_after_hours: float
    checkout_hours: float
    emergency_support_hours: float
    propulsion_task: str
    checkout_task: str


NTP_PROFILE = EngineProfile(
    ('monitoring', 'communications', 'propulsion'), 8.0, 2.0, 72.0,
    'External propellant-feed/valve/control interfaces; no reactor-core repair',
    'Feed integrity, control interlocks and assumed restart-readiness checkout')
NEP_PROFILE = EngineProfile(
    ('monitoring', 'propulsion', 'communications'), 4.0, 4.0, 36.0,
    'External power distribution, heat-rejection and thruster interfaces; no reactor-core repair',
    'Power-conversion, heat-rejection and sustained-load readiness checkout')


@dataclass(frozen=True)
class CrewPermission:
    name: str
    consents_to_eva: bool = True
    qualified_repairs: tuple[str, ...] = REPAIRS


@dataclass(frozen=True)
class RecoveryConfig:
    """One realized scenario, reused across policies; sample externally for future MC.

repair_success_attempt fixes the first successful *completed* attempt per repair.
It is hidden from policy observations. Aborted attempts consume kits but never count
as completed attempts. No failure distribution or individual health model is implied.
"""
    ntp: EngineProfile = NTP_PROFILE
    nep: EngineProfile = NEP_PROFILE
    shutdown_confirmed: bool = True
    decay_heat_removal_available: bool = True
    reactor_shield_integrity_confirmed: bool = True
    local_recovery_authority: bool = True
    ground_round_trip_hours: float = 0.5
    ground_review_hours: float = 1.0
    continuation_deadline_hours: float = 72.0
    eva_kits: int = 6
    minimum_crew_rest_hours: float = 8.0
    crew_eva_budget_hours: float = 14.0
    conserved_support_consumption: float = 0.5
    crew_permissions: tuple[CrewPermission, ...] = ()
    exclusion_intervals: tuple[tuple[float, float], ...] = ()
    repair_success_attempt: tuple[tuple[str, int], ...] = ()
    checkout_succeeds: bool = True
    continuation_authorized: bool = True

    def validate(self, names):
        for profile in (self.ntp, self.nep):
            if set(profile.repair_priority) != set(REPAIRS) or len(profile.repair_priority) != 3:
                raise ValueError('Recovery priorities must contain each repair exactly once')
            for value in (profile.propulsion_access_after_hours, profile.checkout_hours, profile.emergency_support_hours):
                if not math.isfinite(value) or value <= 0:
                    raise ValueError('Recovery profile durations/support must be finite and positive')
        for value in (self.ground_round_trip_hours, self.ground_review_hours, self.minimum_crew_rest_hours):
            if not math.isfinite(value) or value < 0:
                raise ValueError('Recovery delay/rest must be finite and nonnegative')
        for value in (self.continuation_deadline_hours, self.crew_eva_budget_hours):
            if not math.isfinite(value) or value <= 0:
                raise ValueError('Recovery deadline and crew budget must be finite and positive')
        if type(self.eva_kits) is not int or self.eva_kits < 0:
            raise ValueError('EVA kits must be a nonnegative integer')
        if not math.isfinite(self.conserved_support_consumption) or not 0 < self.conserved_support_consumption <= 1:
            raise ValueError('Conservation factor must be in (0, 1]')
        for start, end in self.exclusion_intervals:
            if not math.isfinite(start) or not math.isfinite(end) or not 0 <= start < end:
                raise ValueError('Exclusion intervals must be finite, ordered and nonnegative')
        permissions = [p.name for p in self.crew_permissions]
        if len(set(permissions)) != len(permissions) or not set(permissions) <= set(names):
            raise ValueError('Crew permissions must name distinct existing crew')
        for p in self.crew_permissions:
            if not set(p.qualified_repairs) <= set(REPAIRS):
                raise ValueError('Unknown crew repair qualification')
        failures = dict(self.repair_success_attempt)
        if len(failures) != len(self.repair_success_attempt) or not set(failures) <= set(REPAIRS):
            raise ValueError('Duplicate or unknown repair outcome specification')
        if any(type(n) is not int or n < 1 for n in failures.values()):
            raise ValueError('Successful repair attempt must be a positive integer')
        for value in (self.shutdown_confirmed, self.decay_heat_removal_available,
                      self.reactor_shield_integrity_confirmed, self.local_recovery_authority,
                      self.checkout_succeeds, self.continuation_authorized):
            if type(value) is not bool:
                raise ValueError('Recovery safety/authorization flags must be booleans')
        if any(type(p.consents_to_eva) is not bool for p in self.crew_permissions):
            raise ValueError('Consent must be boolean')


@dataclass(frozen=True)
class RecoveryObservation:
    """Operationally known state only; no future outcomes, radiation truth or RNG."""
    phase: str
    ready_repairs: tuple[str, ...]
    blocked_repairs: tuple[tuple[str, str], ...]
    eligible_crews: tuple[tuple[str, tuple[str, ...]], ...]
    allowed_actions: tuple[str, ...]
    support_remaining_hours: float
    eva_kits_remaining: int
    power_conserved: bool
    checkout_ready_at: float | None
    ground_review_ready_at: float | None
    continuation_blockers: tuple[str, ...]


@dataclass
class RecoveryState:
    model_version: str = MODEL_VERSION
    phase: str = 'repairing'
    support_remaining_hours: float = 0.0
    eva_kits_remaining: int = 0
    power_conserved: bool = False
    checkout_ready_at: float | None = None
    ground_review_ready_at: float | None = None
    last_hour: float = 0.0
    crew_eva_hours: dict[str, float] = field(default_factory=dict)
    crew_rest_until: dict[str, float] = field(default_factory=dict)
    completed_attempts: dict[str, int] = field(default_factory=dict)
    events: list[dict] = field(default_factory=list)
    outcome: str | None = None
    outcome_reason: str | None = None


class MissionRecovery:
    """Physical/operational arbiter, never a strategy; each run owns fresh state."""
    def __init__(self, engine, config, crew_names, required_repairs, eva_duration):
        if engine not in ('NTP', 'NEP'):
            raise ValueError('Unknown recovery engine')
        config.validate(crew_names)
        if not set(required_repairs) <= set(REPAIRS) or len(set(required_repairs)) != len(required_repairs):
            raise ValueError('Invalid recovery repair scope')
        if not math.isfinite(eva_duration) or eva_duration <= 0:
            raise ValueError('Invalid EVA duration')
        self.engine, self.config = engine, config
        self.profile = config.ntp if engine == 'NTP' else config.nep
        self.names, self.required, self.duration = tuple(crew_names), tuple(required_repairs), eva_duration
        self.permissions = {p.name: p for p in config.crew_permissions}
        self.state = RecoveryState(support_remaining_hours=self.profile.emergency_support_hours,
                                   eva_kits_remaining=config.eva_kits,
                                   crew_eva_hours={n: 0.0 for n in crew_names},
                                   crew_rest_until={n: 0.0 for n in crew_names})
        self._event(0, 'initialized', 'Emergency reactor shutdown assumed; independent decay-heat removal must remain available')
        if not all((config.shutdown_confirmed, config.decay_heat_removal_available, config.reactor_shield_integrity_confirmed)):
            self._terminal(0, 'reactor_safety_unresolved', 'Shutdown, decay-heat removal or shielding integrity not confirmed; outside modeled repair capability')

    def _event(self, hour, event, reason, **details):
        self.state.events.append(dict(hour=hour, event=event, reason=reason, **details))

    def _terminal(self, hour, outcome, reason):
        self.state.phase = 'terminal'
        self.state.outcome, self.state.outcome_reason = outcome, reason
        self._event(hour, outcome, reason)

    def advance(self, hour, active_astronaut=None):
        s = self.state
        if not math.isfinite(hour) or hour < s.last_hour:
            raise ValueError('Recovery clock must be finite and nondecreasing')
        if s.outcome is not None:
            return
        dt = hour - s.last_hour
        rate = self.config.conserved_support_consumption if s.power_conserved else 1.0
        s.support_remaining_hours = max(0.0, s.support_remaining_hours - dt * rate)
        if active_astronaut is not None:
            s.crew_eva_hours[active_astronaut] += dt
        s.last_hour = hour
        if s.support_remaining_hours <= 1e-10:
            self._terminal(hour, 'emergency_support_exhausted', 'Assumed emergency-support reserve exhausted; no crew health outcome inferred')
        elif hour >= self.config.continuation_deadline_hours:
            self._terminal(hour, 'recovery_window_closed', 'Assumed continuation decision window closed; trajectory feasibility is not modeled')
        elif s.phase == 'checkout' and hour >= s.checkout_ready_at:
            if self.config.checkout_succeeds:
                s.phase = 'ready'
                self._event(hour, 'checkout_passed', self.profile.checkout_task)
            else:
                self._terminal(hour, 'checkout_failed', 'Readiness checkout failed; no restart or continuation authorized')

    def _ground_ready(self, hour):
        return (self.config.local_recovery_authority or
                self.state.ground_review_ready_at is not None and hour >= self.state.ground_review_ready_at)

    def repair_blocker(self, repair, hour, completed):
        s = self.state
        if s.outcome or s.phase != 'repairing':
            return 'Recovery is not in an EVA repair phase'
        if repair not in self.required or repair in completed:
            return 'Repair is outside outstanding scope'
        if s.eva_kits_remaining <= 0:
            return 'No EVA consumable kits remain'
        if any(start <= hour < end for start, end in self.config.exclusion_intervals):
            return 'Shared external-access exclusion is active'
        if repair == 'propulsion':
            if 'monitoring' in self.required and 'monitoring' not in completed:
                return 'Engineering monitoring/interlocks must be restored first'
            if hour < self.profile.propulsion_access_after_hours:
                return 'Propulsion-area isolation/cooldown clearance pending'
            if not self._ground_ready(hour):
                return 'Propulsion intervention awaits ground engineering review'
        return ''

    def crew_eligible(self, name, repair, hour):
        if name not in self.names:
            return False
        p = self.permissions.get(name, CrewPermission(name))
        return (p.consents_to_eva and repair in p.qualified_repairs and
                hour >= self.state.crew_rest_until[name] and
                self.state.crew_eva_hours[name] + self.duration <= self.config.crew_eva_budget_hours + 1e-10)

    def observe(self, hour, completed, active=False):
        ready, blocked, crews = [], [], []
        for repair in self.profile.repair_priority:
            if repair not in self.required or repair in completed:
                continue
            reason = self.repair_blocker(repair, hour, completed)
            eligible = tuple(n for n in self.names if self.crew_eligible(n, repair, hour))
            crews.append((repair, eligible))
            if not reason and not eligible:
                reason = 'No consenting, qualified, rested crew within the configured EVA workload budget'
            if reason: blocked.append((repair, reason))
            else: ready.append(repair)
        blockers = []
        if set(self.required) - set(completed): blockers.append('Required repairs remain')
        if active: blockers.append('All crew must be inside for checkout and continuation')
        if not self._ground_ready(hour): blockers.append('Ground engineering review pending')
        if not self.config.continuation_authorized: blockers.append('Mission continuation authority withheld')
        actions = []
        if not self.state.outcome:
            actions = ['wait', 'safe_hold', 'abort_mission']
            if not self.state.power_conserved: actions.append('conserve_support')
            if not active and not blockers:
                if self.state.phase == 'repairing': actions.append('begin_checkout')
                if self.state.phase == 'ready': actions.append('resume_mission')
        return RecoveryObservation(self.state.phase, tuple(ready), tuple(blocked), tuple(crews), tuple(actions),
                                   self.state.support_remaining_hours, self.state.eva_kits_remaining,
                                   self.state.power_conserved, self.state.checkout_ready_at,
                                   self.state.ground_review_ready_at, tuple(blockers))

    def start_eva(self, repair, name, hour, completed):
        reason = self.repair_blocker(repair, hour, completed)
        if reason or not self.crew_eligible(name, repair, hour):
            raise ValueError(reason or 'Crew consent, qualification, rest or workload constraint violated')
        self.state.eva_kits_remaining -= 1
        self._event(hour, 'eva_authorized', 'Shared safety and crew-permission checks passed', repair=repair, astronaut=name)

    def finish_eva(self, repair, name, hour, completed_work):
        self.state.crew_rest_until[name] = hour + self.config.minimum_crew_rest_hours
        if not completed_work:
            self._event(hour, 'eva_interrupted', 'No repair credited; consumed kit and exposure retained', repair=repair, astronaut=name)
            return False
        attempt = self.state.completed_attempts.get(repair, 0) + 1
        self.state.completed_attempts[repair] = attempt
        success = attempt >= dict(self.config.repair_success_attempt).get(repair, 1)
        self._event(hour, 'repair_verified' if success else 'repair_unsuccessful',
                    'Task-specific realized outcome; no probability model assumed', repair=repair, attempt=attempt)
        if success and repair == 'communications':
            self.state.ground_review_ready_at = hour + self.config.ground_round_trip_hours + self.config.ground_review_hours
        return success

    def eva_stop_reason(self, hour):
        if self.state.outcome:
            return self.state.outcome_reason
        if any(start <= hour < end for start, end in self.config.exclusion_intervals):
            return 'Shared external-access exclusion requires immediate EVA termination'
        return ''

    def command(self, action, hour, completed, active=False):
        if action not in self.observe(hour, completed, active).allowed_actions or action == 'wait':
            raise ValueError('Recovery command is not permitted in the current state')
        if action == 'conserve_support':
            self.state.power_conserved = True
            self._event(hour, action, 'Nonessential loads shed; essential load reserve consumed at configured reduced rate')
        elif action == 'begin_checkout':
            self.state.phase = 'checkout'
            self.state.checkout_ready_at = hour + self.profile.checkout_hours
            self._event(hour, action, self.profile.checkout_task)
        elif action == 'resume_mission':
            self._terminal(hour, 'mission_continuation_authorized', 'Repairs and readiness checkout complete; modeled authorization only, not certified trajectory or health safety')
        elif action == 'safe_hold':
            self._terminal(hour, 'safe_hold_requested', 'Suspend mission objective for reassessment; hold survival beyond this horizon is not modeled')
        elif action == 'abort_mission':
            self._terminal(hour, 'mission_objective_abandoned', 'Abandon onward mission objective; no return-to-Earth trajectory or rescue is implied')

    def next_boundaries(self, hour):
        s = self.state
        rate = self.config.conserved_support_consumption if s.power_conserved else 1.0
        candidates = [self.profile.propulsion_access_after_hours, self.config.continuation_deadline_hours,
                      hour + s.support_remaining_hours / rate, s.checkout_ready_at, s.ground_review_ready_at,
                      *s.crew_rest_until.values(), *[v for interval in self.config.exclusion_intervals for v in interval]]
        return [x for x in candidates if x is not None and x > hour]
