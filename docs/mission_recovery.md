# Qualitative case constraints

**Purpose:** define what a strategy must take into account—not build another spacecraft simulator.
`sim/mission_recovery.py` checks a few shared rules. The existing simulator still owns EVA timing,
crew rotation, repair progress and radiation accumulation. Enable the rules with `--recovery`.

## What the case gives us

The CNL case describes competing NTP/NEP Mars missions, meteoroid damage to propulsion,
monitoring and communications, roughly seven-hour repair EVAs, an impending solar particle event,
and unreliable conventional radiation monitoring. Recovery, crew safety and ethics must be balanced.
The original case and engineering-reference snapshots remain in `data/raw/mission_recovery/`,
with URLs and hashes in `provenance.json`.

## What we take into account

| Consideration | Simple representation |
| --- | --- |
| NTP versus NEP | NTP repair context is external propellant-feed/control interfaces; NEP is external power/heat-rejection/thruster interfaces. Neither includes reactor-core repair. |
| Reactor hazards | All EVAs require assumed confirmation of shutdown, decay-heat removal and shielding integrity. Missing confirmation blocks work, rather than inventing an accident dose. |
| Damaged monitoring | By default, restore monitoring before propulsion work. This means engineering checks, **not** restored perfect radiation dosimetry. |
| Damaged communications | Optionally require communications before propulsion work when the scenario requires ground involvement. No invented signal/review delay. |
| Crew safety and ethics | A crew member must consent and be qualified for the repair. Existing EVA restrictions and crew rotation still apply. Competition never bypasses these checks. |
| Mission continuation | All required repairs must be complete, the EVA must have ended, and continuation approval must be supplied. Otherwise wait, hold or abandon the mission objective. |

**Evidence versus assumptions:** the case supplies the emergency, not these exact rules.
NASA's propulsion overview (`20210026680`) and the National Academies' NTP/NEP chapters support
the different engineering interfaces. CNSC guidance supports the general shutdown decay-heat concern;
NASA's Mars communications study (`20220013418`) supports communication constraints. Their archived
sources do not establish numerical limits or the particular gates used here. The repair abstraction,
prerequisites, consent/qualification policy and confirmation switches are configurable simulation assumptions.

## Configuration and integration

`RecoveryConfig` has six boolean assumptions and optional `CrewPermission` records:
- Shutdown, cooling and shielding confirmation default to `True` for a repairable scenario—not measured facts.
- `monitoring_before_propulsion=True`; `communications_before_propulsion=False` assumes local authority.
- `continuation_authorized=True` supplies approval; it does not calculate technical readiness or health safety.
- Crew default to consenting and qualified; explicit permissions override this assumption.

```python
from sim.mission_recovery import RecoveryConfig, CrewPermission

constraints = RecoveryConfig(
    communications_before_propulsion=True,
    continuation_authorized=False,
    crew_permissions=(CrewPermission('Crew 1', consents_to_eva=False),),
)
# Pass recovery_config=constraints to simulate_mission(...).
```

`MissionRecovery.observe(completed_repairs)` returns an immutable view of eligible repairs/crew,
blockers and engine context. `require_launch(...)` enforces those rules even if a strategy ignores them.
Repair order comes from the existing mission configuration, subject to prerequisites. Systems omitted
from an explicitly reduced repair scope are assumed already functional. Configuration is fixed per run.
Strategy A uses feasible repairs in configured order; B–D remain unimplemented. Future comparisons should
reuse the same scenario constraints across strategies and vary only their information and decisions.

## Deliberately not modeled

There are **no new** cooldown times, support reserves, consumable-kit budgets, rest/workload limits,
checkout durations, repair-failure schedules or recovery deadlines. NTP/NEP labels alone do not imply
different repair durations or radiation doses. Add such differences only if later evidence warrants them.
There is no reactor physics, trajectory calculation, health prediction or Monte Carlo implementation here.
Holding/abandoning ends the modeled decision window; it does not promise survival or an Earth return.
If the time/data horizon ends before a continuation decision, repairs alone do not imply authorization.

Frozen radiation inputs and calculations are unchanged. Calls without `recovery_config` retain legacy
behavior. Current output uses the existing `event_log.csv` for reasons and `summary.json` for configuration,
`recovery_model_version=qualitative_constraints_v2` and status; there is no separate recovery event/state ledger.
The earlier v1 recovery validation records are historical, not evidence for this simplified implementation.
