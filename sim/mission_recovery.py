"""Shared qualitative case constraints, not a second physics or scheduling model.

Scenario switches are assumptions, not measured reactor conditions. See
docs/mission_recovery.md for case facts, engineering context and limitations.
"""
from dataclasses import dataclass
from math import isfinite

from .repair_tasks import REPAIRS, REFERENCE_ORDER, task_descriptions
MODEL_VERSION = 'qualitative_constraints_v7'
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
class RepairAccess:
    """Explicit access assessment for one task, including outbound/return route."""
    repair: str
    worksite_cleared: bool | None = False
    route_and_worksite_protected: bool | None = None
    alternative_access_approved: bool = False


@dataclass(frozen=True)
class RecoveryConfig:
    """Shared scenario assumptions; deadlines are illustrative, not engineering limits."""
    shutdown_confirmed: bool = True
    decay_heat_removal_available: bool = True
    reactor_shield_integrity_confirmed: bool = True
    monitoring_before_propulsion: bool = False
    communications_before_propulsion: bool = False
    continuation_authorized: bool = True
    reactor_worksite_cleared: bool = True
    nep_route_and_worksite_protected: bool | None = None
    nep_alternative_eva_access_approved: bool = False
    repair_access: tuple[RepairAccess, ...] = ()
    nep_remote_shutdown_available: bool = True
    ntp_restart_and_propellant_margin: bool = True
    nep_sustained_power_and_cooling: bool = True
    ntp_repair_deadline_hours: float | None = None
    nep_repair_deadline_hours: float | None = None
    crew_permissions: tuple[CrewPermission, ...] = ()
    urgent_repair: str | None = None
    repair_prerequisites: tuple[tuple[str, tuple[str, ...]], ...] = (('propulsion', ('propulsion_initial',)),)
    ground_contact_available: bool | None = True
    preapproved_repairs: tuple[str, ...] = ()
    continuation_requires_ground: bool = True


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
    deadline_repairs: tuple[str, ...] = ()


class MissionRecovery:
    """Stateless rule checks; the existing simulator owns time, EVAs and outcomes."""
    def __init__(self, engine, config, crew_names, required_repairs):
        if engine not in PROPULSION_TASKS:
            raise ValueError('Unknown recovery engine')
        self.config = config
        self.engine = engine
        self.deadline = getattr(config, f'{engine.lower()}_repair_deadline_hours')
        self.stabilization = ('Verify assessed coast shutdown and temporary cooling' if engine == 'NTP'
                              else 'Verify assessed shutdown and damaged-loop isolation')
        self.propulsion_task = PROPULSION_TASKS[engine]
        self.names, self.required = tuple(crew_names), tuple(required_repairs)
        self.task_descriptions = task_descriptions(engine)
        self.access = {entry.repair: entry for entry in config.repair_access}
        if len(self.access) != len(config.repair_access) or not set(self.access) <= set(REPAIRS):
            raise ValueError('Repair access must name distinct known tasks')
        for entry in config.repair_access:
            if ((entry.worksite_cleared is not None and type(entry.worksite_cleared) is not bool) or
                    type(entry.alternative_access_approved) is not bool or
                    (entry.route_and_worksite_protected is not None and
                     type(entry.route_and_worksite_protected) is not bool)):
                raise ValueError('Invalid task reactor-access assessment')
        # Legacy global switches remain explicit all-task scenario assumptions.
        # A supplied task entry replaces them in full, including unknown/blocked.
        for repair in self.required:
            self.access.setdefault(repair, RepairAccess(repair,
                config.reactor_worksite_cleared, config.nep_route_and_worksite_protected,
                config.nep_alternative_eva_access_approved))
        self.permissions = {permission.name: permission for permission in config.crew_permissions}
        self.urgent_repair = config.urgent_repair
        self.critical_repair = config.urgent_repair or 'propulsion'
        if self.urgent_repair is not None and self.urgent_repair not in self.required:
            raise ValueError('Urgent repair must be in the scenario repair scope')
        self.dependencies = dict(config.repair_prerequisites)
        if len(self.dependencies) != len(config.repair_prerequisites):
            raise ValueError('Duplicate prerequisite definitions')
        if not set(config.preapproved_repairs) <= set(REPAIRS):
            raise ValueError('Unknown preapproved repair')
        for repair, prerequisites in self.dependencies.items():
            if repair not in REPAIRS or not set(prerequisites) <= set(REPAIRS):
                raise ValueError('Unknown prerequisite repair')
        for repair in ('propulsion_initial', 'propulsion'):
            additions = tuple(name for name, enabled in (('monitoring', config.monitoring_before_propulsion),
                              ('communications', config.communications_before_propulsion)) if enabled)
            self.dependencies[repair] = tuple(dict.fromkeys(self.dependencies.get(repair, ()) + additions))
        for repair in REPAIRS:
            self.chain(repair)
        if len(self.permissions) != len(config.crew_permissions) or not set(self.permissions) <= set(self.names):
            raise ValueError('Crew permissions must name distinct existing crew')
        if len(set(self.required)) != len(self.required) or not set(self.required) <= set(REPAIRS):
            raise ValueError('Invalid recovery repair scope')
        for permission in config.crew_permissions:
            if type(permission.consents_to_eva) is not bool or not set(permission.qualified_repairs) <= set(REPAIRS):
                raise ValueError('Invalid crew consent or repair qualification')
        for name, value in vars(config).items():
            if name in ('monitoring_before_propulsion', 'communications_before_propulsion', 'continuation_requires_ground') and type(value) is not bool:
                raise ValueError('Prerequisite and authorization policy switches must be boolean')
            if name in ('urgent_repair', 'repair_prerequisites', 'preapproved_repairs', 'crew_permissions', 'repair_access'):
                continue
            if name == 'nep_route_and_worksite_protected':
                if value is not None and type(value) is not bool:
                    raise ValueError('NEP protected access must be True, False or None (unknown)')
            elif name.endswith('_deadline_hours'):
                if value is not None and (type(value) not in (int, float) or not isfinite(value) or value <= 0):
                    raise ValueError('Repair deadlines must be positive finite hours or None')
            elif value is not None and type(value) is not bool:
                raise ValueError('Recovery assumptions must be boolean')

    def chain(self, repair, visiting=()):
        if repair in visiting:
            raise ValueError('Repair prerequisites contain a cycle')
        ordered = []
        for prerequisite in self.dependencies.get(repair, ()):
            ordered.extend(self.chain(prerequisite, visiting + (repair,)))
        return tuple(dict.fromkeys(ordered + [repair]))

    def missed_deadline(self, hour, completed):
        return (self.deadline is not None and self.critical_repair in self.required
                and self.critical_repair not in completed and hour >= self.deadline)

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
            if config.ground_contact_available is not True and repair not in config.preapproved_repairs:
                reasons.append('Ground authorization unavailable; repair not covered by emergency procedure')
            access = self.access[repair]
            if (self.engine == 'NEP' and access.route_and_worksite_protected is not True
                    and not access.alternative_access_approved):
                reasons.append(f'{repair}: NEP outbound/return route and worksite protection absent or unconfirmed; approved alternative access required')
            if access.worksite_cleared is not True:
                reasons.append(f'{repair}: reactor worksite access not cleared')
            reasons.extend(f'Restore {prerequisite} before {repair}'
                           for prerequisite in self.dependencies.get(repair, ())
                           if prerequisite in self.required and prerequisite not in completed)
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
        if config.continuation_requires_ground and config.ground_contact_available is not True:
            continuation.append('Separate ground mission-continuation approval unavailable')
        if self.engine == 'NEP':
            ready.sort(key=lambda repair: REFERENCE_ORDER.index(repair))
        if self.urgent_repair and self.urgent_repair not in completed:
            chain = self.chain(self.urgent_repair)
            ready.sort(key=lambda repair: chain.index(repair) if repair in chain else len(chain))
        critical = tuple(repair for repair in self.chain(self.critical_repair)
                         if repair in self.required and repair not in completed)
        return RecoveryObservation(self.propulsion_task, safety, tuple(ready), tuple(blocked),
                                   tuple(crews), tuple(continuation), not stabilized,
                                   self.stabilization, self.deadline if critical else None, critical)

    def require_launch(self, repair, astronaut, completed, stabilized=False):
        observation = self.observe(completed, stabilized)
        if repair not in observation.ready_repairs:
            raise ValueError(dict(observation.blocked_repairs).get(repair, 'Repair is outside outstanding scope'))
        if astronaut not in dict(observation.eligible_crews)[repair]:
            raise ValueError('Crew consent or qualification constraint violated')
