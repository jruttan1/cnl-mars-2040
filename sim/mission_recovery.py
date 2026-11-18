"""Shared qualitative case constraints, not a second physics or scheduling model.

Scenario switches are assumptions, not measured reactor conditions. See
docs/mission_recovery.md for case facts, engineering context and limitations.
"""
from dataclasses import dataclass
from math import isfinite

REPAIRS = ('communications', 'monitoring', 'propulsion')
MODEL_VERSION = 'qualitative_constraints_v3'
PROPULSION_TASKS = {
    'NTP': 'External propellant-feed and control interfaces; no reactor-core repair',
    'NEP': 'External power, heat-rejection and electric-thruster interfaces',
}


@dataclass(frozen=True)
class CrewPermission:
    name: str
    consents_to_eva: bool = True
    qualified_repairs: tuple[str, ...] = REPAIRS


@dataclass(frozen=True)
class RecoveryConfig:
    """Shared scenario assumptions; deadlines are illustrative, not engineering limits."""
    shutdown_confirmed: bool = True
    decay_heat_removal_available: bool = True
    reactor_shield_integrity_confirmed: bool = True
    monitoring_before_propulsion: bool = True
    communications_before_propulsion: bool = False
    continuation_authorized: bool = True
    reactor_worksite_cleared: bool = True
    nep_remote_shutdown_available: bool = True
    ntp_restart_and_propellant_margin: bool = True
    nep_sustained_power_and_cooling: bool = True
    ntp_repair_deadline_hours: float | None = 32.0
    nep_repair_deadline_hours: float | None = 16.0
    crew_permissions: tuple[CrewPermission, ...] = ()


@dataclass(frozen=True)
class RecoveryObservation:
    propulsion_task: str
    safety_blockers: tuple[str, ...]
    ready_repairs: tuple[str, ...]
    blocked_repairs: tuple[tuple[str, str], ...]
    eligible_crews: tuple[tuple[str, tuple[str, ...]], ...]
    continuation_blockers: tuple[str, ...]
    stabilization_required: bool
    stabilization_action: str
    repair_deadline_hours: float | None


class MissionRecovery:
    """Stateless rule checks; the existing simulator owns time, EVAs and outcomes."""
    def __init__(self, engine, config, crew_names, required_repairs):
        if engine not in PROPULSION_TASKS:
            raise ValueError('Unknown recovery engine')
        self.config = config
        self.engine = engine
        self.deadline = getattr(config, f'{engine.lower()}_repair_deadline_hours')
        self.stabilization = ('Confirm coast shutdown and temporary cooling' if engine == 'NTP'
                              else 'Remotely shut down and isolate damaged cooling loop')
        self.propulsion_task = PROPULSION_TASKS[engine]
        self.names, self.required = tuple(crew_names), tuple(required_repairs)
        self.permissions = {permission.name: permission for permission in config.crew_permissions}
        if len(self.permissions) != len(config.crew_permissions) or not set(self.permissions) <= set(self.names):
            raise ValueError('Crew permissions must name distinct existing crew')
        if len(set(self.required)) != len(self.required) or not set(self.required) <= set(REPAIRS):
            raise ValueError('Invalid recovery repair scope')
        for permission in config.crew_permissions:
            if type(permission.consents_to_eva) is not bool or not set(permission.qualified_repairs) <= set(REPAIRS):
                raise ValueError('Invalid crew consent or repair qualification')
        for name, value in vars(config).items():
            if name.endswith('_deadline_hours'):
                if value is not None and (type(value) not in (int, float) or not isfinite(value) or value <= 0):
                    raise ValueError('Repair deadlines must be positive finite hours or None')
            elif name != 'crew_permissions' and type(value) is not bool:
                raise ValueError('Recovery assumptions must be boolean')

    def missed_deadline(self, hour, completed):
        return (self.deadline is not None and 'propulsion' in self.required
                and 'propulsion' not in completed and hour >= self.deadline)

    def observe(self, completed, stabilized=False):
        config = self.config
        safety = tuple(reason for confirmed, reason in (
            (config.shutdown_confirmed, 'Reactor shutdown not confirmed'),
            (config.decay_heat_removal_available, 'Decay-heat removal not confirmed'),
            (config.reactor_shield_integrity_confirmed, 'Reactor shielding integrity not confirmed'),
            (self.engine != 'NEP' or config.nep_remote_shutdown_available, 'NEP remote shutdown unavailable'),
        ) if not confirmed)
        ready, blocked, crews = [], [], []
        for repair in self.required:
            if repair in completed:
                continue
            reasons = list(safety)
            if not stabilized:
                reasons.append('Stabilize spacecraft before EVA')
            if (repair == 'propulsion' or self.engine == 'NEP') and not config.reactor_worksite_cleared:
                reasons.append('Reactor worksite access not cleared')
            if repair == 'propulsion':
                for prerequisite, enabled in (
                    ('monitoring', config.monitoring_before_propulsion),
                    ('communications', config.communications_before_propulsion),
                ):
                    if enabled and prerequisite in self.required and prerequisite not in completed:
                        reasons.append(f'Restore {prerequisite} before propulsion work')
            eligible = tuple(name for name in self.names
                             if (permission := self.permissions.get(name, CrewPermission(name))).consents_to_eva
                             and repair in permission.qualified_repairs)
            crews.append((repair, eligible))
            if not eligible:
                reasons.append('No consenting, qualified crew for this repair')
            if reasons:
                blocked.append((repair, '; '.join(reasons)))
            else:
                ready.append(repair)
        continuation = list(safety)
        if not stabilized:
            continuation.append('Spacecraft not stabilized')
        ready_to_continue = (config.ntp_restart_and_propellant_margin if self.engine == 'NTP'
                             else config.nep_sustained_power_and_cooling)
        if not ready_to_continue:
            continuation.append('NTP restart/propellant margin unconfirmed' if self.engine == 'NTP'
                                else 'NEP sustained power/cooling unconfirmed')
        if any(repair not in completed for repair in self.required):
            continuation.append('Required repairs remain incomplete')
        if not config.continuation_authorized:
            continuation.append('Mission continuation approval withheld')
        if self.engine == 'NEP':
            ready.sort(key=lambda repair: ('monitoring', 'propulsion', 'communications').index(repair))
        return RecoveryObservation(self.propulsion_task, safety, tuple(ready), tuple(blocked),
                                   tuple(crews), tuple(continuation), not stabilized,
                                   self.stabilization, self.deadline if 'propulsion' in self.required else None)

    def require_launch(self, repair, astronaut, completed, stabilized=False):
        observation = self.observe(completed, stabilized)
        if repair not in observation.ready_repairs:
            raise ValueError(dict(observation.blocked_repairs).get(repair, 'Repair is outside outstanding scope'))
        if astronaut not in dict(observation.eligible_crews)[repair]:
            raise ValueError('Crew consent or qualification constraint violated')
